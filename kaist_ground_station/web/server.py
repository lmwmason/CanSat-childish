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
from ..autodetect import ranked_ports
from ..transport import TRANSPORTS
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
        self._view_now = None
        self.checkpoints = Checkpoints(service)
        self._qlook_version = -1
        self.actions = {
            "connect": lambda a: service.connect(str(a["port"]).strip(), int(a["baud"]), str(a.get("kind", "serial"))),
            "stop": lambda a: service.stop(),
            "replay": lambda a: service.start_replay(Path(str(a["path"])).expanduser()),
            "calibration": lambda a: service.configure_calibration(Path(str(a["path"])).expanduser()),
            "tx": lambda a: service.enable_transmit(bool(a["enabled"])),
            "command": lambda a: service.send_command(int(a["id"]), int(a["value"])),
            "time": lambda a: service.send_time(),
            "bt_scan": lambda a: self._adapter_line("AT+BTINQ?"),
            "bt_connect": lambda a: self._adapter_line(self._dial()),
            "checkpoint": lambda a: self.checkpoints.add(str(a["label"])),
            "record_start": lambda a: service.start_recording(),
            "record_stop": lambda a: service.stop_recording(),
            "checkpoint_mark": lambda a: self.checkpoints.add(unnamed=True),
            "checkpoint_undo": lambda a: self.checkpoints.undo(),
            "terminal": lambda a: service.send_terminal(str(a["text"]), bool(a.get("hex", False))),
        }
        self.httpd = ThreadingHTTPServer((host, port), self._handler())
        self.httpd.daemon_threads = True
        self.address = self.httpd.server_address
        self._threads = []
        self._publish()

    # -- Bluetooth adapter -------------------------------------------------------------------
    def _dial(self) -> str:
        if not self.settings.bluetooth_address:
            raise ValueError("no Bluetooth address: set [bluetooth] address in config/ui.cfg")
        return "ATD" + self.settings.bluetooth_address

    def _adapter_line(self, text: str) -> None:
        """Send one AT line to the USB Bluetooth adapter (not to the satellite).

        Uses the service's own public methods: TX is switched on only for this line and put back
        afterwards, and the write is recorded like any other TX. Called with the lock held.
        """
        was_on = self.service.tx_enabled
        if not was_on:
            self.service.enable_transmit(True)          # raises unless a live serial session exists
        try:
            self.service.send_terminal(text)
        finally:
            if not was_on and self.service.mode == "LIVE":
                self.service.enable_transmit(False)

    # -- publishing -------------------------------------------------------------------------
    def _publish(self):
        with self.lock:
            self.service.tick()
            snap = self.service.snapshot()
            marks = self.checkpoints.as_dict()
            rec = {"on": self.service.recording,
                   "elapsed": self.service.clock() - self.service.rec_origin if self.service.recording else None}
        if snap.mode != "IDLE" or self._view_now is None:
            self._view_now = snap.now                   # stops advancing the moment the session ends
        self.history.update(snap)
        self.state_json = json.dumps(state_dict(snap, self.history.as_dict(), marks, rec, self._view_now), allow_nan=False, ensure_ascii=False).encode()
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
                           "alarms": s.alarms, "checkpoints": s.checkpoints, "bluetooth": {"address": s.bluetooth_address}, "transports": list(TRANSPORTS)}).encode()

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
                    ports = [{"device": d, "description": t} for d, t in ranked_ports()]
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
                if code == 200 and action.get("name") == "connect":
                    # Connect opens the serial port; the adapter still has to dial the satellite. Do it for the
                    # operator when configured, off the request thread (auto_dial waits for the adapter to settle).
                    threading.Thread(target=auto_dial, args=(server,), daemon=True).start()
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


def auto_dial(server, wait: float = 0.5) -> str | None:
    """At start-up on a live serial port, dial the configured Bluetooth address once. Returns the line
    sent, or None when disabled / nothing to dial / not live. A failure is reported, never fatal."""
    if not server.settings.bluetooth_auto or not server.settings.bluetooth_address:
        return None
    with server.lock:
        if server.service.mode != "LIVE":
            return None
    time.sleep(wait)                                   # let the adapter settle after the port opens
    try:
        with server.lock:
            line = server._dial()
            server._adapter_line(line)
        return line
    except (OSError, ValueError) as exc:
        print(f"Bluetooth auto-connect failed: {exc}", flush=True)
        return None


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
    dialled = auto_dial(server)
    if dialled:
        print(f"sent {dialled} to the adapter (config/ui.cfg [bluetooth] auto_connect); the link needs a few seconds", flush=True)
    open_pages(server, settings)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
