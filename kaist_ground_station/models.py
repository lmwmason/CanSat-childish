"""Presentation-independent telemetry state and calibration configuration."""
from collections import deque
from dataclasses import dataclass, field
import csv
import math
from pathlib import Path

from .protocol import Frame


@dataclass(frozen=True)
class Calibration:
    enabled: bool = False
    a: float = 1.0
    b: float = 0.0
    unit: str = "raw"

    def apply(self, raw: int) -> float:
        return self.a * raw + self.b if self.enabled else float(raw)


def load_calibration(path: Path) -> tuple[Calibration, ...]:
    result = [Calibration() for _ in range(8)]
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(line for line in f if line.strip() and not line.lstrip().startswith("#")):
            if len(row) != 5:
                raise ValueError("Calibration rows require ID,MODE,A,B,UNIT")
            channel, mode = int(row[0]), int(row[1])
            a, b = float(row[2]), float(row[3])
            if not 0 <= channel < 8 or mode not in (0, 1) or not math.isfinite(a + b):
                raise ValueError("Invalid calibration channel, mode or coefficient")
            result[channel] = Calibration(bool(mode), a, b, row[4])
    return tuple(result)


@dataclass
class Telemetry:
    gps: dict = field(default_factory=dict)
    imu: tuple = ()
    atlm: tuple = ()
    dtlm: tuple = ()
    seen: dict = field(default_factory=dict)
    counts: dict = field(default_factory=dict)
    track: deque = field(default_factory=lambda: deque(maxlen=5000))
    altitude_history: deque = field(default_factory=lambda: deque(maxlen=600))
    messages: deque = field(default_factory=lambda: deque(maxlen=200))
    jpeg: bytes = b""
    image_progress: tuple = (0, 0)
    qlook: bytearray = field(default_factory=lambda: bytearray(512 * 512))
    qlook_version: int = 0

    def apply(self, frame: Frame, now: float) -> None:
        self.counts[frame.kind] = self.counts.get(frame.kind, 0) + 1
        if frame.kind == "ERROR":
            return
        self.seen[frame.kind] = now
        data = frame.data
        if frame.kind == "GPS":
            self.gps = dict(data)
            if data["fix"]:
                self.track.append((data["lat"], data["lon"]))
                self.altitude_history.append((now, data["altitude_m"]))
        elif frame.kind == "IMU":
            self.imu = tuple(data["values"])
        elif frame.kind == "ATLM":
            self.atlm = tuple(data["raw"])
        elif frame.kind == "DTLM":
            self.dtlm = tuple(data["bits"])
        elif frame.kind == "MESSAGE":
            self.messages.append((now, data["channel"], data["text"]))
        elif frame.kind == "IMAGE_SIZE":
            self.image_progress = (0, data["size"])
        elif frame.kind == "IMAGE_PROGRESS":
            self.image_progress = (data["received"], data["size"])
        elif frame.kind == "IMAGE":
            self.jpeg = data["jpeg"]
            self.image_progress = (data["size"], data["size"])
        elif frame.kind == "QLOOK":
            start = data["y"] * 512 + data["x"]
            self.qlook[start:start + len(data["pixels"])] = bytes(data["pixels"])
            self.qlook_version += 1
