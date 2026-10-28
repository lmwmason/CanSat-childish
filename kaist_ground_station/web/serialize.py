"""Snapshot -> JSON-able dict. Presentation only: the service owns all state."""
from __future__ import annotations

import io
import math
import re

from . import drift

MAX_TRACK_POINTS = 500


def clean(value):
    """Make nested data strict-JSON safe (NaN/inf -> None, tuples/bytes handled)."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (bytes, bytearray)):
        return None
    return value


def printable(hexdata: str) -> str:
    """Text view of a received chunk, like the ASCII column of a hex dump (non-text bytes -> '·')."""
    try:
        raw = bytes.fromhex(hexdata.replace(" ", ""))
    except ValueError:
        return ""
    return "".join(chr(b) if 32 <= b < 127 else "·" for b in raw)


_FRAGMENT = (
    re.compile(r"\*[0-9A-Fa-f]{2}$"),                       # NMEA / IMU checksum tail
    re.compile(r"^\$"),                                      # NMEA sentence start
    re.compile(r"^-?\d+(\.\d+)?(,-?\d*\.?\d+){2,}"),         # numeric CSV (IMU values, GGA body)
    re.compile(r"^[,.\-\dA-Fa-f ]*[,.][,.\-\dA-Fa-f ]*$"),     # digits/hex with separators only: a chunk cut inside a frame
)


def text_lines(entries) -> list[list]:
    """[[t, line]] of the human-readable lines in the received chunks: the adapter's replies (OK, CONNECT,
    +BTINQ ...). Telemetry frames are binary with text embedded in them, so a line is kept only when it is
    plain printable ASCII from end to end and does not look like a piece of NMEA/IMU data. This is a
    heuristic on chunks, not a parser: the full byte-exact stream is the raw stream panel."""
    out = []
    for at, hexdata, _ in entries:
        try:
            raw = bytes.fromhex(hexdata.replace(" ", ""))
        except ValueError:
            continue
        for line in re.split(rb"\r\n|\n|\r", raw):
            if len(line) >= 2 and all(32 <= b < 127 for b in line):          # 2 keeps "OK"
                text = line.decode("ascii")
                if not any(p.search(text) for p in _FRAGMENT):
                    out.append([at, text])
    return out


def health(s) -> str:
    """Language-neutral code; the page translates it."""
    if s.mode == "IDLE":
        return "idle"
    if s.link_age_s is None:
        return "waiting"
    return "receiving" if s.link_age_s < 3 else "delayed"


def _decimate(points, limit):
    points = list(points)
    if len(points) <= limit:
        return points
    step = len(points) / limit
    picked = [points[int(i * step)] for i in range(limit - 1)]
    picked.append(points[-1])
    return picked


_drift_cache: dict = {}


def drift_dict(t) -> dict:
    """Local-metre fixes, drift estimates and descent rate for the descent view.

    The estimate only changes when a new GPS fix arrives, so it is cached per telemetry object.
    """
    fixes = drift.aligned_fixes(t.altitude_history, t.track)
    key = (id(t), len(fixes), fixes[-1][0] if fixes else None)
    if _drift_cache.get("key") == key:
        return _drift_cache["value"]
    origin, local = drift.to_local(fixes)
    samples, profile, error = drift.estimate(fixes)
    value = {
        "origin": origin,
        "fixes": drift.decimate(local.tolist(), MAX_TRACK_POINTS),   # [t, east, north, alt]
        "samples": drift.decimate(samples, MAX_TRACK_POINTS),        # [t, e, n, alt, v_e, v_n]
        "profile": profile,                                          # [alt, v_e, v_n, count] per 5 m
        "descent_rate": drift.descent_rate(local),
        "velocity": drift.decimate(drift.velocity_series(local), MAX_TRACK_POINTS),   # [t, east, north, up] m/s
        "window_s": drift.WINDOW_S,
        "error": error,
    }
    _drift_cache.update(key=key, value=value)
    return value


def state_dict(s, history: dict | None = None, checkpoints: dict | None = None, recording: dict | None = None,
               view_now: float | None = None) -> dict:
    t = s.telemetry
    seen = {kind: s.now - at for kind, at in t.seen.items()}
    return clean({
        "mode": s.mode, "source": s.source, "session_id": s.session_id, "health": health(s), "now": s.now,
        # The time the charts are drawn against. It follows the clock while a session runs and stays where the
        # session ended, so the screen freezes on Stop / end of replay instead of sliding away.
        "view_now": s.now if view_now is None else view_now,
        "last_frame_t": None if s.link_age_s is None else s.now - s.link_age_s,
        "link_age_s": s.link_age_s, "can_transmit": s.can_transmit,
        "rx_bytes": s.rx_bytes, "tx_bytes": s.tx_bytes, "valid_frames": s.valid_frames,
        "errors": s.errors, "discarded": s.discarded, "log_directory": s.log_directory,
        "gps": t.gps, "imu": t.imu, "atlm": t.atlm, "dtlm": t.dtlm,
        "analog": s.analog_values,
        "calibration": [{"enabled": c.enabled, "unit": c.unit} for c in s.calibration],
        "seen_age": seen, "counts": t.counts,
        "track": _decimate(t.track, MAX_TRACK_POINTS),
        "altitude": [[at, z] for at, z in t.altitude_history],
        "messages": [[at, ch, text] for at, ch, text in t.messages],
        "notices": [[at, text] for at, text in s.notices],
        "terminal": [[at, hexdata, printable(hexdata)] for at, hexdata, _ in s.terminal],
        "terminal_text": text_lines(s.terminal),
        "image_progress": t.image_progress, "jpeg_size": len(t.jpeg),
        "jpeg_version": f"{s.session_id}:{t.counts.get('IMAGE', 0)}",
        "qlook_version": t.qlook_version,
        "drift": drift_dict(t),
        "history": history or {"imu": [], "atlm": []},
        "checkpoints": checkpoints or {"items": [], "saved": False},
        "recording": recording or {"on": False, "elapsed": None},
    })


def qlook_png(pixels: bytes) -> bytes:
    from PIL import Image
    out = io.BytesIO()
    Image.frombytes("L", (512, 512), bytes(pixels)).save(out, "PNG")
    return out.getvalue()
