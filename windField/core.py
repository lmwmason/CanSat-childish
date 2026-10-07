"""Read child trajectories and estimate local horizontal wind along their descent.

Coordinates are local east/north/up (metres). The drag adjustment is a small-slip,
near-terminal approximation, not a measurement of a complete 3-D wind field.
"""

from __future__ import annotations

import csv
import itertools
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

EARTH_RADIUS_M = 6_371_000.0
G = 9.80665
R_DRY_AIR = 287.05


class MissingPositionData(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    window_s: float = 7.0
    release_exclude_s: float = 3.0
    gps_sigma_m: float = 2.0
    altitude_bin_m: float = 10.0
    mass_kg: float | None = None
    cd: float | None = None
    area_m2: float | None = None

    def validate(self) -> None:
        if self.window_s <= 0 or self.gps_sigma_m <= 0 or self.altitude_bin_m <= 0:
            raise ValueError("window, GPS sigma and altitude bin must be positive")
        physics = (self.mass_kg, self.cd, self.area_m2)
        if any(x is not None for x in physics) and not all(x is not None and x > 0 for x in physics):
            raise ValueError("mass_kg, cd and area_m2 must all be positive when supplied")


def _number(row: dict, name: str, default: float = math.nan) -> float:
    try:
        return float(row[name]) if row.get(name, "") != "" else default
    except (TypeError, ValueError):
        return math.nan


def read_trajectory(path: str | Path) -> tuple[list[dict], dict]:
    """Read a superset of the current child CSV; never invent missing positions."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = csv.DictReader(line for line in f if not line.lstrip().startswith("#"))
        fields = set(rows.fieldnames or ())
        if not {"lat", "lon"}.issubset(fields):
            raise MissingPositionData(
                "Child CSV has no lat/lon. Existing EEPROM logs contain altitude and "
                "acceleration magnitude only; horizontal wind cannot be inferred. "
                "Supply an extended child CSV with child_id,t_s,lat,lon,rel_alt_m."
            )
        if "t_s" not in fields:
            raise ValueError("CSV requires t_s in seconds")
        alt_key = "rel_alt_m" if "rel_alt_m" in fields else "alt_m"
        if alt_key not in fields:
            raise ValueError("CSV requires rel_alt_m or alt_m")
        parsed = []
        counts = defaultdict(int)
        for row in rows:
            counts["input_rows"] += 1
            if row.get("state", "DESCENT").upper() != "DESCENT":
                counts["non_descent"] += 1
                continue
            if row.get("gps_valid", "1").strip().lower() in {"0", "false", "no"}:
                counts["no_fix"] += 1
                continue
            vals = {key: _number(row, key) for key in ("t_s", "lat", "lon")}
            vals["alt_m"] = _number(row, alt_key)
            if not all(math.isfinite(v) for v in vals.values()) or not (-90 <= vals["lat"] <= 90 and -180 <= vals["lon"] <= 180):
                counts["invalid_numeric"] += 1
                continue
            vals.update(
                child_id=(row.get("child_id") or "child-1").strip(),
                pressure_hPa=_number(row, "pressure_hPa"),
                temp_C=_number(row, "temp_C"),
            )
            parsed.append(vals)
    if not parsed:
        raise ValueError("No usable descent positions in CSV")
    return parsed, dict(counts)


def _local_fit(t: np.ndarray, y: np.ndarray, at: float, half_window: float) -> tuple[float, float, float, float] | None:
    near = np.abs(t - at) <= half_window
    if np.count_nonzero(near) < 5:
        return None
    x = t[near] - at
    weight = (1 - (np.abs(x) / (half_window + 1e-9)) ** 3) ** 3
    design = np.column_stack((np.ones(len(x)), x, x * x))
    try:
        fit = np.linalg.lstsq(design * np.sqrt(weight[:, None]), y[near] * np.sqrt(weight), rcond=None)[0]
    except np.linalg.LinAlgError:
        return None
    residual = y[near] - design @ fit
    scatter = math.sqrt(float(np.average(residual**2, weights=weight)))
    return float(fit[0]), float(fit[1]), float(2 * fit[2]), scatter


def estimate(rows: list[dict], cfg: Config) -> tuple[list[dict], dict]:
    cfg.validate()
    lat0 = math.radians(rows[0]["lat"])
    lon0 = math.radians(rows[0]["lon"])
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        p = dict(row)
        p["east_m"] = EARTH_RADIUS_M * math.cos(lat0) * (math.radians(p["lon"]) - lon0)
        p["north_m"] = EARTH_RADIUS_M * (math.radians(p["lat"]) - lat0)
        groups[p["child_id"]].append(p)
    out = []
    stats = defaultdict(int)
    for child_id, points in sorted(groups.items()):
        points.sort(key=lambda p: p["t_s"])
        unique = []
        for p in points:
            if unique and p["t_s"] <= unique[-1]["t_s"]:
                stats["duplicate_time"] += 1
                continue
            unique.append(p)
        if len(unique) < 5:
            stats["short_tracks"] += 1
            continue
        # Remove isolated GPS spikes using neighbours on both sides; a single bad
        # fix must not also cause its adjacent good fixes to be removed.
        keep = np.ones(len(unique), dtype=bool)
        for i in range(2, len(unique) - 2):
            p = unique[i]
            neighbours = [unique[j] for j in (i - 2, i - 1, i + 1, i + 2)]
            if neighbours[-1]["t_s"] - neighbours[0]["t_s"] > 4 * cfg.window_s:
                continue
            nt = np.array([q["t_s"] - p["t_s"] for q in neighbours])
            coords = np.array([[q["east_m"], q["north_m"]] for q in neighbours])
            threshold = max(8 * cfg.gps_sigma_m, 12.0)
            best = None
            for j, k in itertools.combinations(range(4), 2):
                slope = (coords[k] - coords[j]) / (nt[k] - nt[j])
                intercept = coords[j] - slope * nt[j]
                residuals = np.linalg.norm(coords - (intercept + nt[:, None] * slope), axis=1)
                inliers = residuals <= threshold / 2
                score = (int(np.sum(inliers)), -float(np.sum(np.minimum(residuals, threshold))))
                if best is None or score > best[0]:
                    best = score, inliers
            inliers = best[1]
            design = np.column_stack((np.ones(int(np.sum(inliers))), nt[inliers]))
            predicted = np.linalg.lstsq(design, coords[inliers], rcond=None)[0][0]
            if float(np.linalg.norm(np.array([p["east_m"], p["north_m"]]) - predicted)) > threshold:
                keep[i] = False
                stats["gps_spikes"] += 1
        clean = [p for p, yes in zip(unique, keep) if yes]
        t = np.array([p["t_s"] for p in clean])
        e = np.array([p["east_m"] for p in clean])
        n = np.array([p["north_m"] for p in clean])
        z = np.array([p["alt_m"] for p in clean])
        for p in clean:
            if p["t_s"] - t[0] < cfg.release_exclude_s:
                stats["release_excluded"] += 1
                continue
            fits = [_local_fit(t, x, p["t_s"], cfg.window_s / 2) for x in (e, n, z)]
            if any(f is None for f in fits):
                stats["insufficient_window"] += 1
                continue
            ef, nf, zf = fits
            if zf[1] >= -0.2:
                stats["not_descending"] += 1
                continue
            vt = -zf[1]
            # Horizontal linearisation of m*a = m*g + 0.5*rho*Cd*A*|w-v|*(w-v).
            # At near-terminal descent: tau = 1/(k*|v_z|), or v_t/g without Cd*A/m.
            if cfg.mass_kg is None:
                tau = vt / G
                tau_source = "terminal_fall_rate"
            else:
                pressure = p["pressure_hPa"]
                temp = p["temp_C"]
                if not (math.isfinite(pressure) and pressure > 0 and math.isfinite(temp) and temp > -273.15):
                    stats["missing_density"] += 1
                    continue
                rho = pressure * 100 / (R_DRY_AIR * (temp + 273.15))
                k = rho * cfg.cd * cfg.area_m2 / (2 * cfg.mass_kg)
                tau = 1 / (k * vt)
                tau_source = "calibrated_drag"
            correction_e, correction_n = tau * ef[2], tau * nf[2]
            correction = math.hypot(correction_e, correction_n)
            # A large correction indicates launch dynamics, oscillation, or bad GPS.
            accepted = correction <= 3.0 and max(ef[3], nf[3]) <= max(5 * cfg.gps_sigma_m, 6.0)
            if not accepted:
                stats["unstable"] += 1
            use_model = cfg.mass_kg is not None
            result = {
                "child_id": child_id, "t_s": p["t_s"], "lat": p["lat"], "lon": p["lon"],
                "east_m": p["east_m"], "north_m": p["north_m"], "alt_m": p["alt_m"],
                "drift_e_ms": ef[1], "drift_n_ms": nf[1], "vertical_ms": zf[1],
                "drag_correction_e_ms": correction_e, "drag_correction_n_ms": correction_n,
                "model_wind_e_ms": ef[1] + correction_e, "model_wind_n_ms": nf[1] + correction_n,
                "wind_e_ms": ef[1] + correction_e if use_model else ef[1],
                "wind_n_ms": nf[1] + correction_n if use_model else nf[1],
                "position_residual_m": math.hypot(ef[3], nf[3]),
                "tau_s": tau, "tau_source": tau_source,
                "wind_method": "calibrated_drag" if use_model else "smoothed_drift",
                "accepted": int(accepted),
            }
            result["wind_speed_ms"] = math.hypot(result["wind_e_ms"], result["wind_n_ms"])
            result["wind_to_deg"] = math.degrees(math.atan2(result["wind_e_ms"], result["wind_n_ms"])) % 360
            out.append(result)
    if not out:
        raise ValueError("No track has enough valid descending samples for the smoothing window")
    stats["estimated"] = len(out)
    stats["accepted"] = sum(r["accepted"] for r in out)
    return out, dict(stats)


def bin_profiles(rows: list[dict], step: float) -> list[dict]:
    buckets: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in rows:
        if r["accepted"]:
            buckets[(r["child_id"], math.floor(r["alt_m"] / step))].append(r)
    profile = []
    for (child_id, b), values in sorted(buckets.items()):
        profile.append({
            "child_id": child_id, "alt_m": (b + 0.5) * step,
            "east_m": float(np.mean([v["east_m"] for v in values])),
            "north_m": float(np.mean([v["north_m"] for v in values])),
            "wind_e_ms": float(np.mean([v["wind_e_ms"] for v in values])),
            "wind_n_ms": float(np.mean([v["wind_n_ms"] for v in values])),
            "count": len(values),
        })
    return profile
