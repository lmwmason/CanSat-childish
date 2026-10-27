"""Live horizontal-drift estimate for the descent view (presentation-side, read-only).

The estimate itself is computed by the repository's windField package (the same code and method
as figure_20261026/METHODS.md), so live numbers and report numbers cannot diverge. This module
only adapts live GPS fixes to that package's input and the result to the page. If windField is
not importable the rest of the ground station still works; only the drift panels are empty.

Live differences from the offline analysis: only past fixes exist, so only estimates with a complete
window are shown and the newest one lags the newest fix by about half a window. The release time is
unknown here, so the offline 3 s release-exclusion is not applied.
"""
from __future__ import annotations

import math
from pathlib import Path
import sys

import numpy as np

EARTH_RADIUS_M = 6_371_000.0
WINDOW_S = 11.0          # primary window of the 2026-10-26 report
BIN_M = 5.0              # altitude bin of the report's drift profiles
MAX_EVALUATED_FIXES = 600


def _load_windfield():
    """windField lives at the repository root; find it from this file, not the working directory."""
    root = Path(__file__).resolve().parents[2]
    if (root / "windField").is_dir() and str(root) not in sys.path:
        sys.path.append(str(root))
    try:
        from windField import core
        return core, None
    except ImportError as exc:
        return None, f"windField를 불러올 수 없음: {exc}"


def aligned_fixes(altitude_history, track) -> list[tuple[float, float, float, float]]:
    """(t, lat, lon, alt) for the fixes both buffers still hold.

    Telemetry appends one entry to each buffer per valid GPS fix, but they have different
    capacities, so align from the newest end.
    """
    n = min(len(altitude_history), len(track))
    if n == 0:
        return []
    alts = list(altitude_history)[-n:]
    pos = list(track)[-n:]
    return [(a[0], p[0], p[1], a[1]) for a, p in zip(alts, pos)]


def to_local(fixes):
    """Fixes -> (origin, array[t, east, north, alt]) in metres from the first fix."""
    if not fixes:
        return None, np.empty((0, 4))
    lat0, lon0 = fixes[0][1], fixes[0][2]
    k = math.cos(math.radians(lat0))
    arr = np.array([[t, EARTH_RADIUS_M * math.radians(lon - lon0) * k,
                     EARTH_RADIUS_M * math.radians(lat - lat0), alt] for t, lat, lon, alt in fixes])
    return (lat0, lon0), arr


def estimate(fixes, window_s: float = WINDOW_S):
    """-> (samples, profile, error). samples: [t, east, north, alt, v_east, v_north] (accepted only);
    profile: [alt, v_east, v_north, count] per 5 m bin. error is a message when nothing can be shown."""
    core, error = _load_windfield()
    if core is None:
        return [], [], error
    rows = [{"t_s": t, "lat": lat, "lon": lon, "alt_m": alt, "child_id": "live",
             "pressure_hPa": math.nan, "temp_C": math.nan}
            for t, lat, lon, alt in fixes[-MAX_EVALUATED_FIXES:]
            if all(math.isfinite(v) for v in (t, lat, lon, alt))]
    if len(rows) < 5:
        return [], [], None
    cfg = core.Config(window_s=window_s, release_exclude_s=0.0, altitude_bin_m=BIN_M)
    try:
        result, _ = core.estimate(rows, cfg)
    except ValueError:      # not enough descending samples yet: show nothing rather than guess
        return [], [], None
    # windField also evaluates at the newest fixes with a one-sided window; the report only uses
    # complete windows, so drop estimates whose window reaches past the newest fix.
    complete = [r for r in result if r["t_s"] <= rows[-1]["t_s"] - window_s / 2]
    samples = [[r["t_s"], r["east_m"], r["north_m"], r["alt_m"], r["wind_e_ms"], r["wind_n_ms"]]
               for r in complete if r["accepted"]]
    profile = [[b["alt_m"], b["wind_e_ms"], b["wind_n_ms"], b["count"]]
               for b in core.bin_profiles(complete, BIN_M)]
    return samples, profile, None


def velocity_series(local: np.ndarray, span_s: float = 3.0) -> list[list[float]]:
    """[[t, v_east, v_north, v_up], ...] m/s from position change; the GGA sentence has no speed field.

    Causal: each value is the least-squares slope of the fixes of the last span_s seconds, so it
    reacts with about half a window of delay and is only as good as the GPS positions.
    """
    out = []
    t = local[:, 0] if len(local) else np.empty(0)
    start = 0
    for i in range(len(t)):
        while t[i] - t[start] > span_s:
            start += 1
        idx = slice(start, i + 1)
        if i - start + 1 < 3 or t[i] - t[start] < min(1.0, span_s / 2):
            continue
        tt = t[idx] - t[idx].mean()
        denom = float(np.dot(tt, tt))
        if denom <= 0:
            continue
        slope = lambda col: float(np.dot(tt, local[idx, col] - local[idx, col].mean()) / denom)
        out.append([float(t[i]), slope(1), slope(2), slope(3)])
    return out


def descent_rate(local: np.ndarray, span_s: float = 6.0) -> float | None:
    """Metres per second of GPS-altitude loss over the last span_s (positive = descending)."""
    if len(local) < 3:
        return None
    t = local[:, 0]
    recent = t >= t[-1] - span_s
    if np.count_nonzero(recent) < 3 or t[recent][-1] - t[recent][0] < span_s / 3:
        return None
    return float(-np.polyfit(t[recent], local[recent, 3], 1)[0])


def decimate(rows, limit):
    rows = list(rows)
    if len(rows) <= limit:
        return rows
    step = len(rows) / limit
    return [rows[int(i * step)] for i in range(limit - 1)] + [rows[-1]]
