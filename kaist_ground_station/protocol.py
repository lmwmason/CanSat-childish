"""KAIST 2026 wire protocol. No GUI, serial, file, or wall-clock dependencies.

See PROTOCOL.md for evidence, ambiguous fields, and hardware validation status.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
import math
import operator
import re

SYNC = b"\x76\x00"
CAM_START = b"\x76\x00\x32\x00\x00"
CAM_END = b"\x76\x00\x32\x00"
MAX_IMAGE = 512 * 1024


def xor8(data: bytes) -> int:
    return reduce(operator.xor, data, 0)


def digital_command(channel: int, value: int) -> bytes:
    if type(channel) is not int or type(value) is not int:
        raise ValueError("ID and value must be integers")
    if not (0 <= channel <= 23 or 64 <= channel <= 71):
        raise ValueError("Digital ID: 0–23; value ID: 64–71")
    if not 0 <= value <= (1 if channel < 24 else 255):
        raise ValueError("Digital values: 0/1; value commands: 0–255")
    # The distributed EXE writes 8 bytes (7 documented bytes + a trailing zero).
    return b"\x56\x00\x48\x00" + bytes((channel, value, channel ^ value, 0))


def time_command(unix_seconds: int) -> bytes:
    if type(unix_seconds) is not int or not 0 <= unix_seconds <= 0xFFFFFFFF:
        raise ValueError("Time must be an unsigned 32-bit Unix timestamp")
    payload = unix_seconds.to_bytes(4, "big")
    return b"\x56\x00\x49\x00" + payload + bytes((xor8(payload), 0))


@dataclass(frozen=True)
class Frame:
    kind: str
    data: dict
    raw: bytes
    # None means that the wire format has no checksum, not verified integrity.
    checksum: bool | None = None


def _coordinate(value: str, hemisphere: str, latitude: bool) -> float:
    if not re.fullmatch(r"\d+\.\d+|\d+", value):
        raise ValueError("Invalid NMEA coordinate")
    raw = float(value)
    deg = int(raw // 100)
    minutes = raw - deg * 100
    limit = 90 if latitude else 180
    if minutes >= 60 or deg > limit or (deg == limit and minutes != 0):
        raise ValueError("NMEA coordinate out of range")
    if hemisphere not in (("N", "S") if latitude else ("E", "W")):
        raise ValueError("Invalid NMEA hemisphere")
    return (deg + minutes / 60) * (-1 if hemisphere in "SW" else 1)


def decode_gga(sentence: bytes) -> dict:
    # Real KAIST ESD100V2 bench capture: the firmware preserves the original
    # '*HH\r' and appends '*HH' again. Validate both copies and the NMEA body.
    repeated = re.fullmatch(rb"(\$[^*\r\n]+\*([0-9a-fA-F]{2}))\r\*([0-9a-fA-F]{2})", sentence)
    if repeated:
        if repeated[2].upper() != repeated[3].upper():
            raise ValueError("GPS repeated checksum copies disagree")
        result = decode_gga(repeated[1])
        result["checksum_envelope"] = "repeated_after_cr"
        return result
    body, check = sentence[1:].rsplit(b"*", 1)
    if not sentence.startswith(b"$") or not re.fullmatch(rb"[0-9a-fA-F]{2}", check):
        raise ValueError("Malformed NMEA checksum")
    if xor8(body) != int(check, 16):
        raise ValueError("GPS checksum mismatch")
    fields = body.decode("ascii").split(",")
    if fields[0] not in ("GPGGA", "GNGGA") or len(fields) < 15:
        raise ValueError("Expected GPGGA/GNGGA")
    fix = int(fields[6])
    result = dict(sentence=sentence.decode("ascii"), utc=fields[1], fix=fix,
                  satellites=int(fields[7] or 0), lat=None, lon=None, altitude_m=None,
                  hdop=float(fields[8]) if fields[8] else None)
    if fix:
        if fields[10] != "M":
            raise ValueError("GPS altitude must be in metres")
        result.update(lat=_coordinate(fields[2], fields[3], True),
                      lon=_coordinate(fields[4], fields[5], False),
                      altitude_m=float(fields[9]))
    if any(isinstance(x, float) and not math.isfinite(x) for x in result.values()):
        raise ValueError("Non-finite GPS value")
    return result


def decode_imu(line: bytes) -> dict:
    body, checksum = line.rsplit(b",", 1)
    if not body.startswith(b"*") or not re.fullmatch(rb"[0-9a-fA-F]{2}", checksum):
        raise ValueError("Malformed IMU checksum")
    check = int(checksum, 16)
    # EXE 0x424231 starts summing at index 1 (excludes '*'). The PDF says
    # IMU_DATA sum, which can be read as including '*'; record the variant.
    if sum(body[1:]) & 255 == check:
        basis = "excluding_star_exe"
    elif sum(body) & 255 == check:
        basis = "including_star_pdf"
    else:
        raise ValueError("IMU checksum mismatch")
    # Documentation includes both '*x,y,z' and '*,x,y,z'. Preserve actual values.
    values = [float(x) for x in body[1:].lstrip(b",").split(b",")]
    if len(values) not in (3, 4, 6, 7, 9, 10, 12, 13, 15, 16):
        raise ValueError("Unsupported IMU field count")
    if not all(math.isfinite(x) for x in values):
        raise ValueError("Non-finite IMU value")
    return dict(values=values, angles_deg=values[:3], field_count=len(values), checksum_basis=basis)


class StreamParser:
    """Incremental parser: bounded buffering, checksums, resync, explicit timeout.

    The caller supplies monotonic seconds to feed/expire. Timeouts discard a
    stalled partial frame and resume at the next header; they do not accept it.
    Camera payloads are length delimited so embedded sync bytes remain data.
    """

    def __init__(self, timeout_s: float = 3.0):
        self.buffer = bytearray()
        self.timeout_s = timeout_s
        self.last_rx: float | None = None
        self.frames_ok = 0
        self.errors = 0
        self.discarded = 0
        self.image_size = 0
        self.image = bytearray()

    def _error(self, message: str, raw: bytes = b"") -> Frame:
        self.errors += 1
        return Frame("ERROR", {"message": message}, raw, False)

    def expire(self, now: float) -> list[Frame]:
        if self.last_rx is None or now - self.last_rx < self.timeout_s:
            return []
        events = []
        if self.buffer:
            events.append(self._error("Partial frame timed out", bytes(self.buffer[:64])))
            del self.buffer[0]
            events.extend(self._parse())
        if self.image:
            events.append(self._error("Incomplete camera image timed out"))
            self.image.clear()
            self.image_size = 0
        self.last_rx = now
        return events

    def feed(self, data: bytes, now: float = 0.0) -> list[Frame]:
        events = self.expire(now)
        if data:
            self.last_rx = now
            self.buffer.extend(data)
        events.extend(self._parse())
        return events

    def _parse(self) -> list[Frame]:
        events = []
        while len(self.buffer) >= 3:
            start = self.buffer.find(SYNC)
            if start < 0:
                keep = int(self.buffer[-1] == 0x76)
                count = len(self.buffer) - keep
                self.discarded += count
                del self.buffer[:count]
                break
            if start:
                self.discarded += start
                del self.buffer[:start]
            if len(self.buffer) < 4:
                break
            kind = self.buffer[2]
            size = None
            try:
                if 0xA0 <= kind <= 0xAF or kind == 0x80:
                    size = 4 + self.buffer[3]
                elif kind == 0x4C:
                    # EXE state 120 at 0x425A88; observed on the actual kit.
                    if self.buffer[3] != 9:
                        raise ValueError("Unsupported LIFESIGN payload length")
                    size = 13
                elif kind in (0x40, 0x48):
                    # EXE expects compact headers; PDF includes an extra 00.
                    offset = 4 if self.buffer[3] else 5
                    if len(self.buffer) < offset:
                        break
                    marker = self.buffer[offset - 1]
                    if kind == 0x40:
                        if marker != 0x10:
                            raise ValueError("Invalid ATLM marker (expected 0x10)")
                        size = offset + 9
                    else:
                        if marker not in (2, 3, 4):
                            raise ValueError("Invalid DTLM length")
                        size = offset + marker + 1
                elif self.buffer[3] != 0:
                    raise ValueError("Invalid reserved header byte")
                elif kind == 0x36:
                    size = 5
                elif kind == 0x34:
                    size = 9
                    if len(self.buffer) >= 5:
                        expected = 4
                        if self.buffer[4] != expected:
                            raise ValueError("Invalid packet length marker")
                elif kind in (0x58, 0x60):
                    end = self.buffer.find(b"\n", 4)
                    next_sync = self.buffer.find(SYNC, 4)
                    if next_sync >= 0 and (end < 0 or next_sync < end):
                        raise ValueError("Truncated text frame before next header")
                    if end < 0:
                        if len(self.buffer) > 1024:
                            raise ValueError("Text frame exceeds 1024 bytes")
                        break
                    size = end + 1
                elif kind == 0x32:
                    if len(self.buffer) < 5:
                        break
                    if not self.buffer.startswith(CAM_START) or not self.image_size:
                        raise ValueError("Camera data without a valid size announcement")
                    remaining = self.image_size - len(self.image)
                    # Documented full-frame form, plus 64-byte chunks noted in
                    # data-processing p9. Chunk framing still needs a real capture.
                    block = min(64, remaining)
                    chunk_end = 5 + block
                    if len(self.buffer) < chunk_end + 5:
                        break
                    if self.buffer[chunk_end:chunk_end + 5] == CAM_START:
                        size = chunk_end + 5
                    else:
                        size = 5 + remaining + 5
                        if len(self.buffer) < size:
                            break
                    if self.buffer[size - 5:size] != CAM_START:
                        raise ValueError("Invalid camera trailer")
                else:
                    raise ValueError(f"Unknown packet type 0x{kind:02X}")
                if len(self.buffer) < size:
                    break
                raw = bytes(self.buffer[:size])
                frame = self._decode(kind, raw)
                del self.buffer[:size]
                if frame is not None:
                    self.frames_ok += 1
                    events.append(frame)
            except (ValueError, UnicodeError, IndexError) as exc:
                events.append(self._error(str(exc), bytes(self.buffer[:min(size or 4, 64)])))
                self.discarded += 1
                del self.buffer[0]
                if kind == 0x32:
                    self.image.clear()
                    self.image_size = 0
        # A short modem response/noise tail is not an incomplete CanSat frame.
        # Keep only a possible sync prefix for the next serial read.
        if 0 < len(self.buffer) < 3 and not SYNC.startswith(bytes(self.buffer)):
            keep = int(self.buffer[-1] == SYNC[0])
            count = len(self.buffer) - keep
            self.discarded += count
            del self.buffer[:count]
        return events

    def _decode(self, kind: int, raw: bytes) -> Frame | None:
        if kind == 0x4C:
            if xor8(raw[4:-1]) != raw[-1]:
                raise ValueError("LIFESIGN checksum mismatch")
            return Frame("LIFESIGN", {"satellite_time_raw": int.from_bytes(raw[4:8], "big"),
                                      "uptime_s": int.from_bytes(raw[8:12], "big")}, raw, True)
        if kind == 0x36:
            if raw[4] != 0:
                raise ValueError("Unsupported camera acknowledgement status")
            return Frame("CAMERA_ACK", {"command": "capture_control", "status": raw[4]}, raw)
        if kind == 0x40:
            offset = 4 if raw[3] else 5
            values = raw[offset:-1]
            if sum(values) & 255 != raw[-1]:
                raise ValueError("ATLM checksum mismatch")
            return Frame("ATLM", {"raw": list(values), "header": "compact" if offset == 4 else "pdf"}, raw, True)
        if kind == 0x48:
            offset = 4 if raw[3] else 5
            values = raw[offset:-1]
            if xor8(values) != raw[-1]:
                raise ValueError("DTLM checksum mismatch")
            return Frame("DTLM", {"bytes": list(values),
                                  "bits": [(x >> i) & 1 for x in values for i in range(8)],
                                  "header": "compact" if offset == 4 else "pdf"}, raw, True)
        if kind == 0x58:
            return Frame("GPS", decode_gga(raw[4:].rstrip(b"\r\n")), raw, True)
        if kind == 0x60:
            return Frame("IMU", decode_imu(raw[4:].rstrip(b"\r\n")), raw, True)
        if kind == 0x80:
            if len(raw) < 8:
                raise ValueError("QLOOK requires X and Y")
            x, y = int.from_bytes(raw[4:6], "little"), int.from_bytes(raw[6:8], "little")
            if x >= 512 or y >= 512 or x + len(raw[8:]) > 512:
                raise ValueError("QLOOK row outside 512 × 512")
            return Frame("QLOOK", {"x": x, "y": y, "pixels": list(raw[8:])}, raw)
        if 0xA0 <= kind <= 0xAF:
            return Frame("MESSAGE", {"channel": kind - 0xA0,
                                      "text": raw[4:].decode("utf-8", errors="replace"),
                                      "hex": raw[4:].hex()}, raw)
        if kind == 0x34:
            if raw[5:7] != b"\x00\x00":
                raise ValueError("Unsupported camera size prefix")
            length = int.from_bytes(raw[7:9], "big")
            if not 4 <= length <= MAX_IMAGE:
                raise ValueError("Camera size out of bounds")
            self.image_size = length
            self.image.clear()
            return Frame("IMAGE_SIZE", {"size": length}, raw)
        if kind == 0x32:
            self.image.extend(raw[5:-5])
            if len(self.image) < self.image_size:
                return Frame("IMAGE_PROGRESS", {"received": len(self.image), "size": self.image_size}, raw)
            jpeg = bytes(self.image)
            self.image.clear()
            self.image_size = 0
            if not jpeg.startswith(b"\xff\xd8") or not jpeg.endswith(b"\xff\xd9"):
                raise ValueError("Camera data does not have JPEG SOI/EOI markers")
            return Frame("IMAGE", {"jpeg": jpeg, "size": len(jpeg)}, raw)
        raise ValueError("Unsupported packet")
