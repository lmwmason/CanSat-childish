"""Browser frontend: a tiny stdlib HTTP server around a StationService.

The service is single-threaded by design, so one lock guards every call into it. A tick thread
drives the service and publishes the latest state; request handlers only read that published copy
or run a user action under the lock. No wire protocol, serial or logging code lives here.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time
import webbrowser

from ..frontends import FrontendUnavailable
from ..service import StationService
from ..transport import TRANSPORTS, list_ports
from ..ui_settings import UISettings
from .checkpoints import Checkpoints
from .history import History
from .serialize import qlook_png, state_dict

STATIC = Path(__file__).resolve().parent / "static"
STATIC_FILES = {"/i18n.js": ("i18n.js", "text/javascript; charset=utf-8"), "/logo.png": ("logo.png", "image/png")}   # explicit list: no path traversal
DEFAULT_PORT = 8765
TICK_S = 0.1
MAX_BODY = 64 * 1024


class WebServer:
    def __init__(self, service: StationService, settings: UISettings | None = None,
                 host: str = "127.0.0.1", port: int = DEFAULT_PORT):
        self.service, self.settings = service, settings or UISettings()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.state_json = b"{}"
        self.jpeg = b""
        self.qlook = b""
        self.history = History()
        self.checkpoints = Checkpoints(service)
        self._qlook_version = -1
        self.actions = {
            "connect": lambda a: service.connect(str(a["port"]).strip(), int(a["baud"]), str(a.get("kind", "serial"))),
            "stop": lambda a: service.stop(),
            "demo": lambda a: service.start_demo(),
            "replay": lambda a: service.start_replay(Path(str(a["path"])).expanduser()),
            "calibration": lambda a: service.configure_calibration(Path(str(a["path"])).expanduser()),
            "tx": lambda a: service.enable_transmit(bool(a["enabled"])),
            "command": lambda a: service.send_command(int(a["id"]), int(a["value"])),
            "time": lambda a: service.send_time(),
            "checkpoint": lambda a: self.checkpoints.add(str(a["label"])),
            "checkpoint_mark": lambda a: self.checkpoints.add(unnamed=True),
            "checkpoint_undo": lambda a: self.checkpoints.undo(),
            "terminal": lambda a: service.send_terminal(str(a["text"]), bool(a.get("hex", False))),
        }
        self.httpd = ThreadingHTTPServer((host, port), self._handler())
        self.httpd.daemon_threads = True
        self.address = self.httpd.server_address
        self._threads = []
        self._publish()

    # -- publishing -------------------------------------------------------------------------
    def _publish(self):
        with self.lock:
            self.service.tick()
            snap = self.service.snapshot()
            marks = self.checkpoints.as_dict()
        self.history.update(snap)
        self.state_json = json.dumps(state_dict(snap, self.history.as_dict(), marks), allow_nan=False, ensure_ascii=False).encode()
        self.jpeg = snap.telemetry.jpeg
        if snap.telemetry.qlook_version != self._qlook_version:
            self._qlook_version = snap.telemetry.qlook_version
            self.qlook = qlook_png(snap.telemetry.qlook) if self._qlook_version else b""

    def _tick_loop(self):
        while not self.stop_event.wait(TICK_S):
            try:
                self._publish()
            except Exception as exc:  # keep serving; surface it as a notice instead of dying silently
                with self.lock:
                    self.service.notice(f"Web frontend error: {exc}")

    def config_json(self) -> bytes:
        s = self.settings
        return json.dumps({"language": s.language, "colors": s.colors, "font_family": s.font_family, "mono_family": s.mono_family,
                           "sizes": {"base": s.size_base, "status": s.size_status, "metric": s.size_metric,
                                     "log": s.size_log, "plot": s.size_plot},
                           "alarms": s.alarms, "checkpoints": s.checkpoints, "transports": list(TRANSPORTS)}).encode()

    # -- http -------------------------------------------------------------------------------
    def _handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, body: bytes, kind: str, code: int = 200):
                self.send_response(code)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = self.path.split("?")[0]
                if path in ("/", "/index.html", "/wind"):            # one page, two layouts: the page reads its own path
                    return self._send((STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
                if path in STATIC_FILES:
                    return self._send((STATIC / STATIC_FILES[path][0]).read_bytes(), STATIC_FILES[path][1])
                if path == "/api/state":
                    return self._send(server.state_json, "application/json")
                if path == "/api/config":
                    return self._send(server.config_json(), "application/json")
                if path == "/api/ports":
                    ports = [{"device": d, "description": t} for d, t in list_ports()]
                    return self._send(json.dumps(ports).encode(), "application/json")
                if path == "/api/jpeg" and server.jpeg:
                    return self._send(server.jpeg, "image/jpeg")
                if path == "/api/qlook.png" and server.qlook:
                    return self._send(server.qlook, "image/png")
                self._send(b"not found", "text/plain", 404)

            def do_POST(self):
                if self.path != "/api/action":
                    return self._send(b"not found", "text/plain", 404)
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    if length > MAX_BODY:
                        raise ValueError("request too large")
                    action = json.loads(self.rfile.read(length) or b"{}")
                    handler = server.actions.get(action.get("name"))
                    if handler is None:
                        raise ValueError(f"unknown action {action.get('name')!r}")
                    with server.lock:
                        handler(action)
                    reply, code = {"ok": True}, 200
                except Exception as exc:
                    reply, code = {"error": str(exc) or exc.__class__.__name__}, 400
                server._publish()
                self._send(json.dumps(reply, ensure_ascii=False).encode(), "application/json", code)

        return Handler

    # -- lifecycle --------------------------------------------------------------------------
    def start(self):
        for target in (self._tick_loop, self.httpd.serve_forever):
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self):
        self.stop_event.set()
        self.httpd.shutdown()
        self.httpd.server_close()

    @property
    def url(self) -> str:
        host, port = self.address[:2]
        return f"http://{host}:{port}/"


def open_pages(server, settings, delay: float = 0.6) -> list[str]:
    """Open one browser window per configured screen. Which monitor each lands on is up to the
    window manager; drag them where you want them."""
    urls = [server.url.rstrip("/") + ("/wind" if page == "wind" else "/") for page in settings.open_pages]
    for i, url in enumerate(urls):
        try:
            webbrowser.open_new(url)
        except webbrowser.Error:
            pass
        if i + 1 < len(urls):
            time.sleep(delay)                   # browsers can merge two opens that arrive at the same instant
    return urls


def run(service: StationService, settings: UISettings | None = None) -> None:
    """Frontend entry point (see frontends.py)."""
    try:
        server = WebServer(service, settings)
    except OSError:
        try:
            server = WebServer(service, settings, port=0)  # default port busy: take any free one
        except OSError as exc:
            raise FrontendUnavailable(f"cannot start web server: {exc}") from exc
    server.start()
    settings = settings or UISettings()
    print(f"Ground station UI: {server.url} (flight)  {server.url}wind (wind field)  (Ctrl+C to quit)", flush=True)
    open_pages(server, settings)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
