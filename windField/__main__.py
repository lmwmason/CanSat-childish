"""Command line entry point for reproducible wind analysis and synthetic trials."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .core import Config, EARTH_RADIUS_M, G, MissingPositionData, bin_profiles, estimate, read_trajectory


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_demo(directory: Path, seed: int, gps_sigma_m: float) -> tuple[Path, Path]:
    """Generate a known vertical wind profile and three independently drifting children."""
    directory.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    lat0, lon0 = math.radians(37.5665), math.radians(126.9780)
    starts = [(0.0, 0.0), (24.0, 0.0), (10.0, 22.0)]
    observed, truth = [], []
    dt, vt, z0 = 0.1, 4.0, 160.0
    tau = vt / G
    for index, (x0, y0) in enumerate(starts, 1):
        child_id = f"child-{index}"
        x, y = x0, y0
        vx, vy = (8.0 * math.cos(index * 2 * math.pi / 3), 8.0 * math.sin(index * 2 * math.pi / 3))
        for j in range(401):
            t = round(j * dt, 6)
            z = max(0.0, z0 - vt * t)
            wind_e = 2.0 + 0.015 * z
            wind_n = 1.0 - 0.010 * z
            if j % 10 == 0:
                noisy_x = x + rng.normal(0, gps_sigma_m)
                noisy_y = y + rng.normal(0, gps_sigma_m)
                lat = math.degrees(lat0 + noisy_y / EARTH_RADIUS_M)
                lon = math.degrees(lon0 + noisy_x / (EARTH_RADIUS_M * math.cos(lat0)))
                observed.append({
                    "idx": j // 10, "child_id": child_id, "state": "DESCENT" if z > 0 else "LANDED",
                    "t_s": round(t, 2), "rel_alt_m": round(z + rng.normal(0, 0.3), 3),
                    "pressure_hPa": round(1013.25 * math.exp(-z / 8434.0), 3),
                    "temp_C": round(20 - 0.0065 * z, 2), "humidity_pct": 50, "accel_g": 1.0,
                    "lat": f"{lat:.8f}", "lon": f"{lon:.8f}", "gps_valid": 1,
                })
                truth.append({
                    "child_id": child_id, "t_s": round(t, 2), "alt_m": round(z, 3),
                    "east_m": round(x, 4), "north_m": round(y, 4),
                    "wind_e_ms": round(wind_e, 5), "wind_n_ms": round(wind_n, 5),
                })
            vx += dt * (wind_e - vx) / tau
            vy += dt * (wind_n - vy) / tau
            x += dt * vx
            y += dt * vy
    input_path, truth_path = directory / "synthetic_child.csv", directory / "synthetic_truth.csv"
    write_csv(input_path, observed)
    write_csv(truth_path, truth)
    (directory / "synthetic_conditions.json").write_text(json.dumps({
        "seed": seed, "gps_position_sigma_m": gps_sigma_m, "sample_period_s": 1.0,
        "integration_period_s": dt, "start_altitude_m": z0, "descent_speed_ms": vt,
        "wind_e_ms": "2 + 0.015*alt_m", "wind_n_ms": "1 - 0.010*alt_m",
        "horizontal_response_tau_s": tau,
        "initial_horizontal_speed_ms": 8.0,
        "note": "Synthetic algorithm test, not observed CanSat accuracy",
    }, indent=2), encoding="utf-8")
    return input_path, truth_path


def _score(rows: list[dict], truth_path: Path) -> dict:
    with truth_path.open(newline="", encoding="utf-8") as f:
        truth = {(r["child_id"], float(r["t_s"])): r for r in csv.DictReader(f)}
    errors, drift_errors, model_errors = [], [], []
    for r in rows:
        if not r["accepted"] or (r["child_id"], r["t_s"]) not in truth:
            continue
        target = truth[(r["child_id"], r["t_s"])]
        u, v = float(target["wind_e_ms"]), float(target["wind_n_ms"])
        errors.append((r["wind_e_ms"] - u) ** 2 + (r["wind_n_ms"] - v) ** 2)
        drift_errors.append((r["drift_e_ms"] - u) ** 2 + (r["drift_n_ms"] - v) ** 2)
        model_errors.append((r["model_wind_e_ms"] - u) ** 2 + (r["model_wind_n_ms"] - v) ** 2)
    return {
        "matched_accepted_samples": len(errors),
        "vector_rmse_ms": math.sqrt(float(np.mean(errors))) if errors else None,
        "drift_only_vector_rmse_ms": math.sqrt(float(np.mean(drift_errors))) if errors else None,
        "model_candidate_vector_rmse_ms": math.sqrt(float(np.mean(model_errors))) if errors else None,
        "note": "Scores are against synthetic truth only; they do not predict field accuracy",
    }


def _plot(input_rows: list[dict], estimates: list[dict], profile: list[dict], path: Path, bin_m: float) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.tri as tri

    children = sorted({r["child_id"] for r in input_rows})
    colors = plt.get_cmap("tab10")
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5), constrained_layout=True)
    ax = axes[0]
    for i, child in enumerate(children):
        p = [r for r in estimates if r["child_id"] == child]
        if p:
            ax.plot([r["east_m"] for r in p], [r["north_m"] for r in p],
                    marker=".", ms=2, lw=1, color=colors(i), label=child)
    ax.set(xlabel="East (m)", ylabel="North (m)", title="Child ground tracks")
    ax.axis("equal")
    ax.grid(alpha=0.25)
    ax.legend()

    ax = axes[1]
    for i, child in enumerate(children):
        p = [r for r in profile if r["child_id"] == child]
        if p:
            ax.plot([r["wind_e_ms"] for r in p], [r["alt_m"] for r in p],
                    color=colors(i), marker=".", label=f"{child} east")
            ax.plot([r["wind_n_ms"] for r in p], [r["alt_m"] for r in p],
                    color=colors(i), ls="--", alpha=0.8, label=f"{child} north")
    ax.set(xlabel="Wind component (m/s)", ylabel="Relative altitude (m)",
           title="Wind profile (solid E, dashed N)")
    ax.grid(alpha=0.25)

    ax = axes[2]
    bins = sorted({r["alt_m"] for r in profile})
    options = []
    for b in bins:
        selected = [r for r in profile if r["alt_m"] == b]
        coords = np.array([[r["east_m"], r["north_m"]] for r in selected])
        if len({r["child_id"] for r in selected}) >= 3 and np.linalg.matrix_rank(coords - coords.mean(axis=0)) == 2:
            options.append(selected)
    if options:
        selected = options[len(options) // 2]
        xs = np.array([r["east_m"] for r in selected])
        ys = np.array([r["north_m"] for r in selected])
        triangulation = tri.Triangulation(xs, ys)
        gx, gy = np.meshgrid(np.linspace(min(xs), max(xs), 9), np.linspace(min(ys), max(ys), 9))
        inside = triangulation.get_trifinder()(gx, gy) >= 0
        vectors = []
        for xx, yy in zip(gx[inside], gy[inside]):
            d2 = (xs - xx) ** 2 + (ys - yy) ** 2
            w = 1 / np.maximum(d2, 1.0)
            vectors.append((np.average([r["wind_e_ms"] for r in selected], weights=w),
                            np.average([r["wind_n_ms"] for r in selected], weights=w)))
        if vectors:
            u, v = np.array(vectors).T
            ax.quiver(gx[inside], gy[inside], u, v, color="#999999", alpha=0.75,
                      angles="xy", scale_units="xy", scale=0.2, label="IDW interpolation")
        for i, r in enumerate(selected):
            ax.quiver(r["east_m"], r["north_m"], r["wind_e_ms"], r["wind_n_ms"],
                      color=colors(children.index(r["child_id"])), angles="xy", scale_units="xy", scale=0.2)
            ax.text(r["east_m"], r["north_m"], r["child_id"], fontsize=8)
        ax.triplot(triangulation, color="#cccccc", lw=0.8)
        ax.set_title(f"~{selected[0]['alt_m']:.0f} m: track estimates (color), IDW (gray)")
    else:
        ax.text(0.5, 0.5, "Need 3 spatial tracks\nat one altitude", ha="center", va="center",
                transform=ax.transAxes)
        ax.set_title("Horizontal field")
    ax.set(xlabel="East (m)", ylabel="North (m)")
    ax.axis("equal")
    ax.grid(alpha=0.25)
    fig.suptitle("Child CanSat wind estimate — synthetic/estimated values are not field validated")
    fig.savefig(path, dpi=160)
    plt.close(fig)


def analyze(input_path: Path, output: Path, cfg: Config, truth: Path | None = None) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    raw, read_stats = read_trajectory(input_path)
    result, estimate_stats = estimate(raw, cfg)
    profile = bin_profiles(result, cfg.altitude_bin_m)
    write_csv(output / "wind_samples.csv", result)
    write_csv(output / "wind_profile.csv", profile)
    _plot(raw, result, profile, output / "wind_field.png", cfg.altitude_bin_m)
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(input_path.resolve()),
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "config": asdict(cfg), "read_stats": read_stats, "estimate_stats": estimate_stats,
        "profile_rows": len(profile),
        "units": "east/north m and m/s; wind_to_deg clockwise from north",
        "method": "local quadratic position smoothing; model correction reported as candidate unless mass/Cd/area provided",
        "limitations": "Wind only along tracks; map is IDW inside sampled hull. Field accuracy not validated.",
    }
    if truth:
        report["synthetic_score"] = _score(result, truth)
    (output / "analysis.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Generate and analyze reproducible synthetic child flights")
    demo.add_argument("--output-dir", type=Path, default=Path("log/demo"))
    demo.add_argument("--seed", type=int, default=20261007)
    demo.add_argument("--gps-sigma-m", type=float, default=1.5)
    run = sub.add_parser("analyze", help="Analyze an extended child CSV with positions")
    run.add_argument("input", type=Path)
    run.add_argument("--output-dir", type=Path, default=Path("log/analysis"))
    run.add_argument("--gps-sigma-m", type=float, default=2.0)
    for command in (demo, run):
        command.add_argument("--window-s", type=float, default=7)
        command.add_argument("--release-exclude-s", type=float, default=3)
        command.add_argument("--altitude-bin-m", type=float, default=10)
        command.add_argument("--mass-kg", type=float)
        command.add_argument("--cd", type=float)
        command.add_argument("--area-m2", type=float)
    args = parser.parse_args(argv)
    cfg = Config(args.window_s, args.release_exclude_s, args.gps_sigma_m,
                 args.altitude_bin_m, args.mass_kg, args.cd, args.area_m2)
    try:
        if args.command == "demo":
            if args.gps_sigma_m <= 0:
                raise ValueError("gps-sigma-m must be positive")
            input_path, truth = make_demo(args.output_dir, args.seed, args.gps_sigma_m)
            report = analyze(input_path, args.output_dir, cfg, truth)
        else:
            report = analyze(args.input, args.output_dir, cfg)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, MissingPositionData, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
