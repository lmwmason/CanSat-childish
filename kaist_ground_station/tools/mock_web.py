"""A pretend kit for looking at the web UI without hardware.

It is a *transport*: it hands the service the same wire bytes the real kit would (GPS, IMU, ATLM, DTLM,
messages, JPEG pieces, QLOOK rows), so the real parser, recorder, Stop button, Record button and
alarms all behave exactly as they do with hardware. Nothing here writes into the service's state.

GPS positions come from a real GoPro descent (data_20261026/*.csv); everything else is synthetic and the
session says so ("MOCK DATA ..."). It also plays the Bluetooth adapter: AT lines are answered with OK/CONNECT.
Never use this for flight data.

    python3 -m kaist_ground_station.tools.mock_web
    python3 -m kaist_ground_station.tools.mock_web --image some.jpg --speed 2 --gps-hz 0.5
"""
from __future__ import annotations

import argparse
import csv
import io
import math
from pathlib import Path
import tempfile
import time

from ..protocol import CAM_START, xor8
from ..service import StationService
from ..ui_settings import load_ui_settings
from ..web.server import WebServer, open_pages

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = ROOT / "data_20261026" / "GS010115_GoPro Max-GPS5.csv"
DEFAULT_WINDOW = ("23:06:42", "23:07:30")      # UTC; the report's provisional descent for record 115 (KST 08:06:42-08:07:30)
SENSOR_PERIOD_S = 0.25
IMAGE_PERIOD_S = 2.0
QLOOK_PACKETS_PER_S = 8
QLOOK_PIXELS = 128                              # a packet holds up to 251 pixels; 128 divides a 512-wide row


def read_fixes(path: Path, window):
    """[(seconds, utc 'HHMMSS', lat, lon, alt)] of the chosen window, oldest first."""
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            hhmmss = r["date"][11:19]
            if window is None or window[0] <= hhmmss <= window[1]:
                rows.append((float(r["cts"]) / 1000, hhmmss.replace(":", ""), float(r["GPS (Lat.) [deg]"]),
                             float(r["GPS (Long.) [deg]"]), float(r["GPS (Alt.) [m]"])))
    if len(rows) < 10:
        raise SystemExit(f"{path}: only {len(rows)} GPS rows in the chosen window")
    return rows


# -- wire encoders: the same shapes the parser expects (see protocol.py / PROTOCOL.md) ----------------------
def gga_packet(utc: str, lat: float, lon: float, alt: float, sats: int = 12, hdop: float = 1.4) -> bytes:
    def dm(value, width):
        deg = int(abs(value))
        return f"{deg:0{width}d}{(abs(value) - deg) * 60:08.5f}"
    body = (f"GPGGA,{utc}.00,{dm(lat, 2)},{'N' if lat >= 0 else 'S'},{dm(lon, 3)},{'E' if lon >= 0 else 'W'},"
            f"1,{sats:02d},{hdop},{alt:.1f},M,20.0,M,,").encode()
    return b"\x76\x00\x58\x00$" + body + f"*{xor8(body):02X}\r\n".encode()


def imu_packet(a: float, b: float, c: float) -> bytes:
    body = f"*{a:.2f},{b:.2f},{c:.2f}".encode()
    return b"\x76\x00\x60\x00" + body + f",{sum(body[1:]) & 255:02X}\r\n".encode()


def atlm_packet(values: list[int]) -> bytes:
    raw = bytes(values)
    return b"\x76\x00\x40\x10" + raw + bytes([sum(raw) & 255])


def dtlm_packet(bits: bytes) -> bytes:
    return b"\x76\x00\x48\x04" + bits + bytes([xor8(bits)])


def message_packet(text: str) -> bytes:
    raw = text.encode()
    return b"\x76\x00\xa0" + bytes([len(raw)]) + raw


def image_packets(jpeg: bytes) -> list[bytes]:
    """Size announcement, then 64-byte pieces each framed by the camera marker (as the parser documents)."""
    out = [b"\x76\x00\x34\x00\x04\x00\x00" + len(jpeg).to_bytes(2, "big")]
    out += [CAM_START + jpeg[i:i + 64] + CAM_START for i in range(0, len(jpeg), 64)]
    return out


def qlook_packets(gray: bytes) -> list[bytes]:
    """512x512 8-bit rows cut into packets: 76 00 80 n  x(2 LE) y(2 LE) pixels."""
    out = []
    for y in range(512):
        for x in range(0, 512, QLOOK_PIXELS):
            pixels = gray[y * 512 + x: y * 512 + x + QLOOK_PIXELS]
            out.append(b"\x76\x00\x80" + bytes([4 + len(pixels)]) + x.to_bytes(2, "little") + y.to_bytes(2, "little") + pixels)
    return out


def test_pictures(path: Path | None) -> tuple[bytes, bytes]:
    """(320x240 JPEG small enough for the camera protocol, 512x512 grey QLOOK) from a file or a test pattern."""
    from PIL import Image, ImageDraw
    if path:
        im = Image.open(path).convert("RGB")
    else:
        im = Image.new("RGB", (320, 240), (20, 30, 50))
        d = ImageDraw.Draw(im)
        for i in range(0, 320, 40):
            d.line([(i, 0), (i, 240)], fill=(60, 90, 120))
        d.text((90, 110), "MOCK CAMERA", fill=(255, 255, 255))
    out = io.BytesIO()
    im.resize((320, 240)).save(out, "JPEG", quality=60)
    return out.getvalue(), im.convert("L").resize((512, 512)).tobytes()


class MockKit:
    """Transport (read/write/close) that behaves like the kit plus its Bluetooth adapter."""

    def __init__(self, fixes, speed: float = 1.0, gps_hz: float = 1.0, picture: tuple[bytes, bytes] | None = None,
                 clock=time.monotonic):
        self.clock, self.speed, self.closed = clock, speed, False
        self.written: list[bytes] = []
        self._pending = bytearray()
        self.started = clock()
        t0 = fixes[0][0]
        picked, last = [], -1e9
        for f in fixes:
            if f[0] - last >= 1.0 / gps_hz:
                picked.append(f)
                last = f[0]
        self.timeline = [(f[0] - t0, "gps", f) for f in picked]                      # media seconds
        self.duration = fixes[-1][0] - t0
        self.picture = picture
        self._next_sensor = 0.0
        self._next_image = 0.0
        self._image_queue: list[tuple[float, bytes]] = []
        self._qlook_queue = qlook_packets(picture[1]) if picture else []
        self._qlook_at = 0
        self._next_qlook = 0.0
        self._gps_at = 0
        self._tick = 0

    def media_time(self) -> float:
        return (self.clock() - self.started) * self.speed

    def read(self) -> bytes:
        if self.closed:
            return b""
        now = self.media_time()
        out = bytearray(self._pending)
        self._pending.clear()
        while self._gps_at < len(self.timeline) and self.timeline[self._gps_at][0] <= now:
            _, _, (_, utc, lat, lon, alt) = self.timeline[self._gps_at]
            out += gga_packet(utc, lat, lon, alt)
            self._gps_at += 1
        end = min(now, self.duration)
        while self._next_sensor <= end:
            self._tick += 1
            p = self._next_sensor
            out += imu_packet(20 * math.sin(p / 3), 10 * math.sin(p / 5 + 1), 180 + 30 * math.sin(p / 7))
            out += atlm_packet([int(128 + 100 * math.sin(p / (2 + i) + i)) for i in range(8)])
            out += dtlm_packet(bytes(((self._tick // (4 + i)) & 1) << i for i in range(4)))
            if self._tick % 20 == 1:
                out += message_packet("MOCK DATA: synthetic IMU/ATLM/DTLM")
            self._next_sensor += SENSOR_PERIOD_S
        if self.picture:
            while self._next_image <= end:
                self._image_queue += [(self._next_image + i * 0.004, pkt) for i, pkt in enumerate(image_packets(self.picture[0]))]
                self._next_image += IMAGE_PERIOD_S
            while self._image_queue and self._image_queue[0][0] <= now:
                out += self._image_queue.pop(0)[1]
            while self._next_qlook <= end and self._qlook_at < len(self._qlook_queue):
                out += self._qlook_queue[self._qlook_at]
                self._qlook_at += 1
                self._next_qlook += 1.0 / QLOOK_PACKETS_PER_S
        return bytes(out)

    def write(self, data: bytes) -> None:
        """The adapter answers AT lines; everything written is kept for inspection."""
        self.written.append(data)
        line = data.strip()
        if line.startswith(b"ATD"):
            self._pending += b"\r\nOK\r\n\r\nCONNECT " + line[3:] + b"\r\n"
        elif line.startswith(b"AT"):
            self._pending += b"\r\nOK\r\n"

    def close(self) -> None:
        self.closed = True


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="GoPro GPS CSV")
    p.add_argument("--all", action="store_true", help="use the whole CSV instead of the descent window of record 115")
    p.add_argument("--speed", type=float, default=1.0, help="playback speed (1 = real time)")
    p.add_argument("--gps-hz", type=float, default=1.0, help="GGA rate; the real kit sends about 0.5")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--image", type=Path, help="a picture to send as the camera JPEG and QLOOK (default: a test pattern)")
    p.add_argument("--no-images", action="store_true", help="send no camera/QLOOK data")
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--ui-config", type=Path)
    args = p.parse_args(argv)
    if args.speed <= 0 or args.gps_hz <= 0:
        p.error("--speed and --gps-hz must be positive")
    if not args.csv.is_file():
        p.error(f"CSV not found: {args.csv}")
    if args.image and not args.image.is_file():
        p.error(f"image not found: {args.image}")

    fixes = read_fixes(args.csv, None if args.all else DEFAULT_WINDOW)
    kit = MockKit(fixes, args.speed, args.gps_hz, None if args.no_images else test_pictures(args.image))
    settings = load_ui_settings(args.ui_config)
    service = StationService(Path(tempfile.mkdtemp(prefix="mock-session-")), transport_factory=lambda port, baud: kit,
                             auto_record=settings.record_auto)
    service.connect("mock", 115200)
    service.notice(f"MOCK DATA: {args.csv.name} GPS ({len(fixes)} fixes) + synthetic sensors; nothing is real telemetry")
    server = WebServer(service, settings, port=args.port)
    server.start()
    print(f"Mock UI: {server.url}  ({kit.duration:.0f} s of data at {args.speed}x; Ctrl+C to quit)", flush=True)
    if not args.no_browser:
        open_pages(server, settings)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        service.stop()


if __name__ == "__main__":
    main()
