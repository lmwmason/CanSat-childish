"""Mock-data session for looking at the web UI without hardware.

Feeds a real GoPro GPS descent (data_20261026/*.csv) into a live service in real time, plus synthetic
IMU / ATLM / DTLM so every panel has something to show. The link is a no-op transport: nothing is
sent anywhere, and TX "succeeds" into the void. Never use this for flight data.

    python3 -m kaist_ground_station.tools.mock_web
    python3 -m kaist_ground_station.tools.mock_web --csv data_20261026/GS010116_GoPro\\ Max-GPS5.csv --speed 2 --loop
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import tempfile
import threading
import time

from ..service import StationService
from ..ui_settings import load_ui_settings
from ..web.server import WebServer, open_pages

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = ROOT / "data_20261026" / "GS010115_GoPro Max-GPS5.csv"
DEFAULT_WINDOW = ("23:06:42", "23:07:30")      # UTC; the report's provisional descent for record 115 (KST 08:06:42-08:07:30)


class NullTransport:
    """Accepts and discards everything; reads nothing."""

    def __init__(self, port, baud):
        pass

    def read(self):
        return b""

    def write(self, data):
        pass

    def close(self):
        pass


def read_fixes(path: Path, window):
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            hhmmss = r["date"][11:19]
            if window is None or window[0] <= hhmmss <= window[1]:
                rows.append((float(r["cts"]) / 1000, float(r["GPS (Lat.) [deg]"]), float(r["GPS (Long.) [deg]"]), float(r["GPS (Alt.) [m]"])))
    if len(rows) < 10:
        raise SystemExit(f"{path}: only {len(rows)} GPS rows in the chosen window")
    return rows


def run_gps(service, server, rows, speed, loop, stop):
    while not stop.is_set():
        t0, start = rows[0][0], time.monotonic()
        for cts, lat, lon, alt in rows:
            while (time.monotonic() - start) * speed < cts - t0:
                if stop.wait(0.02):
                    return
            with server.lock:
                now, tel = service.clock(), service.telemetry
                tel.gps = {"fix": 3, "lat": lat, "lon": lon, "altitude_m": alt, "satellites": 12, "hdop": 1.4, "utc": "000000.00"}
                tel.track.append((lat, lon))
                tel.altitude_history.append((now, alt))
                tel.seen["GPS"] = now
                tel.counts["GPS"] = tel.counts.get("GPS", 0) + 1
                service.last_frame = now
                service.parser.frames_ok += 1
        if not loop:
            return
        with server.lock:                       # start the next pass from an empty track
            service.telemetry.track.clear()
            service.telemetry.altitude_history.clear()


def run_sensors(service, server, stop):
    n = 0
    while not stop.wait(0.25):
        n += 1
        phase = n * 0.25
        with server.lock:
            now, tel = service.clock(), service.telemetry
            tel.imu = (20 * math.sin(phase / 3), 10 * math.sin(phase / 5 + 1), 180 + 30 * math.sin(phase / 7))
            tel.atlm = tuple(int(128 + 100 * math.sin(phase / (2 + i) + i)) for i in range(8))
            tel.dtlm = tuple(1 if (n // (4 + i)) % 2 else 0 for i in range(32))
            for kind in ("IMU", "ATLM", "DTLM"):
                tel.seen[kind] = now
                tel.counts[kind] = tel.counts.get(kind, 0) + 1
            service.last_frame = now


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="GoPro GPS CSV")
    p.add_argument("--all", action="store_true", help="use the whole CSV instead of the descent window of record 115")
    p.add_argument("--speed", type=float, default=1.0, help="playback speed (1 = real time)")
    p.add_argument("--loop", action="store_true", help="restart when the track ends")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--image", type=Path, help="a JPEG to show in the camera panel (plus a synthetic QLOOK gradient)")
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--ui-config", type=Path)
    args = p.parse_args(argv)
    if args.speed <= 0:
        p.error("--speed must be positive")
    if not args.csv.is_file():
        p.error(f"CSV not found: {args.csv}")

    rows = read_fixes(args.csv, None if args.all else DEFAULT_WINDOW)
    service = StationService(Path(tempfile.mkdtemp(prefix="mock-session-")), transport_factory=NullTransport)
    service.connect("mock", 115200)
    if args.image:
        if not args.image.is_file():
            p.error(f"image not found: {args.image}")
        jpeg = args.image.read_bytes()
        tel = service.telemetry
        tel.jpeg, tel.image_progress = jpeg, (len(jpeg), len(jpeg))
        tel.qlook[:] = bytes((x + y) // 4 % 256 for y in range(512) for x in range(512))
        tel.qlook_version = 1
    service.notice(f"MOCK DATA: {args.csv.name} ({len(rows)} GPS fixes) + synthetic IMU/ATLM/DTLM; nothing is real telemetry")
    settings = load_ui_settings(args.ui_config)
    server = WebServer(service, settings, port=args.port)
    server.start()
    stop = threading.Event()
    for target, extra in ((run_gps, (rows, args.speed, args.loop)), (run_sensors, ())):
        threading.Thread(target=target, args=(service, server, *extra, stop), daemon=True).start()
    print(f"Mock UI: {server.url}  ({len(rows)} fixes, {rows[-1][0] - rows[0][0]:.0f} s at {args.speed}x; Ctrl+C to quit)", flush=True)
    if not args.no_browser:
        open_pages(server, settings)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.stop()
        service.stop()


if __name__ == "__main__":
    main()
