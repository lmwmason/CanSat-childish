"""Lossless RX/TX capture, replay timing, decoded CSV, and camera artifacts."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path

from .protocol import Frame


class NullRecorder:
    """Stands in while a session is not being recorded: same calls, nothing written."""
    directory = None

    def bytes(self, direction: str, data: bytes, elapsed: float) -> None:
        pass

    def event(self, event: Frame, elapsed: float) -> None:
        pass

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class Recorder:
    def __init__(self, root: Path, mode: str, source: str, calibration: tuple):
        from dataclasses import asdict
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        self.directory = root / f"{stamp}-{mode.lower()}"
        self.directory.mkdir(parents=True, exist_ok=False)
        self.handles = []
        self.image_count = 0
        try:
            self.rx = self._open("rx.bin", "wb")
            self.tx = self._open("tx.bin", "wb")
            self.traffic = self._open("traffic.jsonl", "w")
            self.csv_file = self._open("events.csv", "w", newline="")
            self.csv = csv.writer(self.csv_file)
            self.csv.writerow(["utc", "elapsed_s", "kind", "checksum", "data_json", "frame_hex"])
            (self.directory / "session.json").write_text(json.dumps({
                "format": 1, "mode": mode, "source": source, "started_utc": stamp,
                "hardware_verified": False, "calibration": [asdict(c) for c in calibration],
            }, indent=2), encoding="utf-8")
        except OSError:
            self.close()
            raise

    def _open(self, name, mode, **kwargs):
        f = (self.directory / name).open(mode, **({} if "b" in mode else {"encoding": "utf-8"}), **kwargs)
        self.handles.append(f)
        return f

    def bytes(self, direction: str, data: bytes, elapsed: float) -> None:
        (self.rx if direction == "rx" else self.tx).write(data)
        self.traffic.write(json.dumps({"t": elapsed, "direction": direction, "hex": data.hex()}) + "\n")

    def event(self, event: Frame, elapsed: float) -> None:
        data = dict(event.data)
        if event.kind == "IMAGE":
            self.image_count += 1
            name = f"image-{self.image_count:05d}.jpg"
            (self.directory / name).write_bytes(data.pop("jpeg"))
            data["file"] = name
        self.csv.writerow([datetime.now(timezone.utc).isoformat(), f"{elapsed:.6f}", event.kind,
                           event.checksum, json.dumps(data, ensure_ascii=False), event.raw.hex()])

    def flush(self) -> None:
        for f in self.handles:
            f.flush()

    def close(self) -> None:
        for f in self.handles:
            f.close()


class Replay:
    """Streams RX records only. TX records can never be sent to hardware."""
    def __init__(self, path: Path):
        self.file = path.open(encoding="utf-8")
        self.pending = None
        self.finished = False
        self.last_t = -1.0

    def poll(self, elapsed: float) -> list[tuple[float, bytes]]:
        result = []
        for _ in range(1000):
            if self.pending is None:
                line = self.file.readline()
                if not line:
                    self.finished = True
                    break
                obj = json.loads(line)
                t = float(obj["t"])
                import math
                if not math.isfinite(t) or t < self.last_t:
                    raise ValueError("Replay timestamps must be finite and nondecreasing")
                self.last_t = t
                if obj["direction"] != "rx":
                    continue
                self.pending = (t, bytes.fromhex(obj["hex"]))
            if self.pending[0] > elapsed:
                break
            result.append(self.pending)
            self.pending = None
        return result

    def close(self):
        self.file.close()
