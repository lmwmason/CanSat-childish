"""Operator checkpoints ("drone ascent start", "drop", ...): timestamped marks stored with the session.

Presentation-layer only: it reads the service's clock/GPS and the session folder name, and writes
its own file (checkpoints.jsonl) next to the service's recording. Nothing in the service changes.
Undo appends a tombstone instead of rewriting, so the file stays an honest append-only record.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

FILENAME = "checkpoints.jsonl"
MAX_LABEL = 80


class Checkpoints:
    def __init__(self, service):
        self.service = service
        self._dir = None
        self.items: list[dict] = []

    # the list belongs to one session: a new session folder starts a new list
    def _sync(self) -> None:
        directory = self.service.log_directory or ""
        if directory != self._dir:
            self._dir, self.items = directory, self._load(directory)

    @staticmethod
    def _load(directory: str) -> list[dict]:
        path = Path(directory) / FILENAME if directory else None
        if not path or not path.is_file():
            return []
        items: dict[int, dict] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if "undo" in row:
                items.pop(row["undo"], None)
            elif "id" in row:
                items[row["id"]] = row
        return sorted(items.values(), key=lambda r: r["id"])

    def _append(self, row: dict) -> None:
        if self._dir:
            with open(Path(self._dir) / FILENAME, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def add(self, label: str = "", unnamed: bool = False) -> dict:
        """Record now. A named checkpoint must have a label (an empty one is almost certainly a mistake);
        an unnamed mark is stored with an empty label and shown by its number."""
        label = label.strip()
        if unnamed:
            label = ""
        elif not label:
            raise ValueError("checkpoint label is empty")
        self._sync()
        gps = self.service.telemetry.gps or {}
        fix = bool(gps.get("fix"))
        row = {
            "id": max((r["id"] for r in self.items), default=0) + 1,
            "label": label[:MAX_LABEL],
            "utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "service_t": self.service.clock(),
            "gps_utc": gps.get("utc") if fix else None,
            "alt_m": gps.get("altitude_m") if fix else None,
            "lat": gps.get("lat") if fix else None,
            "lon": gps.get("lon") if fix else None,
        }
        self._append(row)
        self.items.append(row)
        return row

    def undo(self) -> dict | None:
        self._sync()
        if not self.items:
            return None
        row = self.items.pop()
        self._append({"undo": row["id"], "utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds")})
        return row

    def as_dict(self) -> dict:
        self._sync()
        return {"items": list(self.items), "saved": bool(self._dir)}
