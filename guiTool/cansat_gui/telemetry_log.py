"""Flight data recorder: one CSV row per received telemetry frame + the raw CRSF byte stream.

Files go to  guiTool/logs/  (packaged app / .pyz: ~/CanSat Logs/)  as  mother_YYYYmmdd_HHMMSS.csv  and  .crsf  (raw bytes, for replay/debug).
Every row is flushed immediately so a power cut on the ground station loses at most one row.
"""
import csv
import sys
import time
from pathlib import Path

from .crsf import CSV_COLUMNS, MotherState, csv_row


def _default_log_dir() -> Path:
    src = Path(__file__).resolve().parent.parent
    # packaged app (PyInstaller) or zipapp (.pyz): the install location is read-only or not a folder
    if getattr(sys, "frozen", False) or not src.is_dir():
        return Path.home() / "CanSat Logs"
    return src / "logs"


LOG_DIR = _default_log_dir()


class TelemetryLogger:
    def __init__(self, directory: Path = LOG_DIR):
        self.directory = Path(directory)
        self._csv_file = None
        self._raw_file = None
        self._writer = None
        self._t0 = 0.0
        self.path: Path | None = None
        self.rows = 0

    @property
    def active(self) -> bool:
        return self._csv_file is not None

    def start(self) -> Path:
        self.stop()
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.path = self.directory / f"mother_{stamp}.csv"
        self._csv_file = open(self.path, "w", newline="", encoding="utf-8")
        self._raw_file = open(self.path.with_suffix(".crsf"), "wb")
        self._writer = csv.writer(self._csv_file)
        self._writer.writerow(CSV_COLUMNS)
        self._csv_file.flush()
        self._t0 = time.monotonic()
        self.rows = 0
        return self.path

    def write_raw(self, data: bytes) -> None:
        if self._raw_file:
            self._raw_file.write(data)
            self._raw_file.flush()

    def write_frame(self, ftype: int, state: MotherState) -> None:
        """Matches CrsfDecoder.feed(on_frame=...)."""
        if not self._writer:
            return
        now = time.time()
        pc_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)) + f".{int(now % 1 * 1000):03d}"
        self._writer.writerow(csv_row(state, ftype, pc_time, time.monotonic() - self._t0))
        self._csv_file.flush()
        self.rows += 1

    def stop(self) -> None:
        for f in (self._csv_file, self._raw_file):
            if f:
                f.close()
        self._csv_file = self._raw_file = self._writer = None
