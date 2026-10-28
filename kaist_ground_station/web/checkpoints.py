"""Operator checkpoints ("drone ascent start", "drop", ...): timestamped marks stored with the session.

Presentation-layer only: it reads the service's clock/GPS and session identity, and writes
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
        self._session_id = None
        self.items: list[dict] = []
        self._replay_key = None
        self._replay_rows: list[tuple[float, dict]] = []

    # A session can have no recording or several recording folders. Its marks
    # stay in memory across recording toggles and reset only on a new session.
    def _sync(self) -> None:
        directory = self.service.log_directory or ""
        session_id = self.service.session_id
        if session_id != self._session_id:
            self._session_id, self._dir = session_id, directory
            self.items = self._load(directory)
            self._replay_key, self._replay_rows = None, []
            return
        if directory == self._dir:
            return
        self._dir = directory
        if directory:
            # Keep all marks from this run in each new recording, including marks
            # made while recording was off. Never modify a stopped recording.
            for row in self.items:
                self._append({**row, "before_recording": True})

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

    # -- replay: show the marks that were made when the replayed session was recorded ---------------------
    def _replayed(self) -> list[dict]:
        """Marks stored beside the replayed traffic.jsonl, placed on the replay clock.

        Recorded times are seconds since the folder's started_utc (session.json), and every mark carries its
        UTC, so replay position = mark UTC - started_utc. A mark appears once the replay has reached it.
        """
        folder = Path(self.service.source).parent
        key = str(folder)
        if self._replay_key != key:
            self._replay_key, self._replay_rows = key, []
            try:
                started = datetime.strptime(json.loads((folder / "session.json").read_text(encoding="utf-8"))["started_utc"],
                                            "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=timezone.utc)
                for row in self._load(key):
                    offset = (datetime.fromisoformat(row["utc"]) - started).total_seconds()
                    self._replay_rows.append((offset, row))
            except (OSError, ValueError, KeyError):
                self._replay_rows = []                       # no readable session.json / marks: nothing to show
        now = self.service.clock()
        return [{**row, "service_t": self.service.started + offset}
                for offset, row in self._replay_rows if self.service.started + offset <= now]

    def _showing_replay(self) -> bool:
        """True while a replay runs and after it has finished (the service goes IDLE at the end, but the
        replayed session is still what is on screen until a new session starts)."""
        service = self.service
        if service.mode == "REPLAY":
            return True
        return service.mode == "IDLE" and Path(service.source or "").name == "traffic.jsonl"

    def _refuse_in_replay(self) -> None:
        if self._showing_replay():
            raise ValueError("Replay shows the recorded session's marks; marks cannot be added or removed here")

    def add(self, label: str = "", unnamed: bool = False) -> dict:
        self._refuse_in_replay()
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
        self._refuse_in_replay()
        self._sync()
        if not self.items:
            return None
        row = self.items.pop()
        self._append({"undo": row["id"], "utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds")})
        return row

    def as_dict(self) -> dict:
        if self._showing_replay():
            return {"items": self._replayed(), "saved": True, "replay": True}
        self._sync()
        return {"items": list(self.items), "saved": bool(self._dir)}
