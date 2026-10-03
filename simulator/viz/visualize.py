#!/usr/bin/env python3
"""Real-time 3D visualizer for the CanSat-childish firmware sims.

Listens for UDP telemetry broadcast by firmware/sim/sim_world.c
(hal_lora_send -> 127.0.0.1:CANSAT_VIZ_PORT, default 41000) and renders,
live: the mothership + up to 3 small wind-observer satellites' real 3D
flight paths (x/y drift + altitude), a simple attitude indicator built
from roll/pitch, color-coded control mode (so a Pi-link failsafe
transition is visible the moment it happens), and - the actual point of
the R&E research plan - a low-altitude wind vector field derived from
the observers' GPS/baro trajectories.

This only listens - it never drives the sims. Run them normally in
their own terminals (or via ./run.sh all) alongside this script:

    python3 viz/visualize.py [--port 41000]
"""
import argparse
import socket
import time
from collections import deque

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers the 3d projection)
from matplotlib.animation import FuncAnimation

STATE_NAMES = {0: "BOOT", 1: "STANDBY", 2: "DESCENT", 3: "LANDED"}
MODE_NAMES = {0: "SAFE_DISARMED", 1: "PI_GUIDED", 2: "FAILSAFE_AUTO"}
MODE_COLORS = {0: "#d62728", 1: "#2ca02c", 2: "#ff7f0e"}  # red / green / orange

HISTORY_LEN = 900
STALE_AFTER_S = 5.0
WIND_BIN_SIZE_M = 50.0  # altitude bin width for the derived wind profile


class Vehicle:
    def __init__(self, name):
        self.name = name
        self.t = 0
        self.state = 0
        self.mode = 0
        self.pi = 0
        self.fault = 0
        self.alt = 0.0
        self.vs = 0.0
        self.roll = 0.0
        self.pitch = 0.0
        self.motors = 0
        self.x = 0.0
        self.y = 0.0
        self.fix = 0
        self.hum = 0.0
        self.dep = [0, 0, 0]
        self.history = deque(maxlen=HISTORY_LEN)  # (t_s, x, y, alt, state)
        self.deploy_marks = []  # (t_s, x, y, alt), once per channel on 0->1 edge
        self.last_update = time.time()

    def apply(self, fields):
        self.t = int(float(fields.get("t", self.t)))
        self.state = int(fields.get("state", self.state))
        self.mode = int(fields.get("mode", self.mode))
        self.pi = int(fields.get("pi", self.pi))
        self.fault = int(fields.get("fault", self.fault))
        self.alt = float(fields.get("alt", self.alt))
        self.vs = float(fields.get("vs", self.vs))
        self.roll = float(fields.get("roll", self.roll))
        self.pitch = float(fields.get("pitch", self.pitch))
        self.motors = int(fields.get("motors", self.motors))
        self.x = float(fields.get("x", self.x))
        self.y = float(fields.get("y", self.y))
        self.fix = int(fields.get("fix", self.fix))
        self.hum = float(fields.get("hum", self.hum))

        dep_str = fields.get("dep")
        if dep_str and len(dep_str) == 3 and dep_str.isdigit():
            new_dep = [int(ch) for ch in dep_str]
            for i in range(3):
                if new_dep[i] and not self.dep[i]:
                    self.deploy_marks.append((self.t / 1000.0, self.x, self.y, self.alt))
            self.dep = new_dep

        self.history.append((self.t / 1000.0, self.x, self.y, self.alt, self.state))
        self.last_update = time.time()

    def is_observer(self):
        return self.name.startswith("child")

    def is_stale(self):
        return (time.time() - self.last_update) > STALE_AFTER_S


def nose_and_right(roll_deg, pitch_deg):
    """Body 'nose' (~vertical when stable) and 'right' axis after
    applying roll about X then pitch about Y - purely for visualizing
    how far off-vertical the attitude estimate has drifted."""
    r = np.radians(roll_deg)
    p = np.radians(pitch_deg)
    rx = np.array([[1, 0, 0], [0, np.cos(r), -np.sin(r)], [0, np.sin(r), np.cos(r)]])
    ry = np.array([[np.cos(p), 0, np.sin(p)], [0, 1, 0], [-np.sin(p), 0, np.cos(p)]])
    m = rx @ ry
    nose = m @ np.array([0.0, 0.0, 1.0])
    right = m @ np.array([1.0, 0.0, 0.0])
    return nose, right


def drain_socket(sock, vehicles):
    while True:
        try:
            data, _ = sock.recvfrom(4096)
        except BlockingIOError:
            break
        text = data.decode("utf-8", errors="replace")
        parts = text.split(",")
        if not parts or not parts[0]:
            continue
        name = parts[0]
        fields = {}
        for part in parts[1:]:
            if "=" in part:
                k, v = part.split("=", 1)
                fields[k] = v
        vehicle = vehicles.setdefault(name, Vehicle(name))
        try:
            vehicle.apply(fields)
        except ValueError:
            pass  # malformed packet, drop it


def compute_wind_profile(vehicles, bin_size=WIND_BIN_SIZE_M):
    """Derives a horizontal wind vector at each altitude band from the
    observers' own (t, x, y, alt) trajectories - finite-difference
    horizontal velocity between consecutive samples, averaged within
    each altitude bin across all observers. This is exactly the
    "기압 센서로 계산한 고도와 GPS 위치 정보를 결합하여 고도별 바람 벡터를
    정리한다" step from the R&E plan, just done live instead of in
    post-processing.
    """
    bins = {}
    for v in vehicles.values():
        if not v.is_observer():
            continue
        pts = list(v.history)
        for i in range(1, len(pts)):
            t1, x1, y1, a1, s1 = pts[i - 1]
            t2, x2, y2, a2, s2 = pts[i]
            # Only MISSION_DESCENT (=2) samples are the observer actually
            # falling on its own - state 1 (STANDBY) is still "carried"
            # inside the mothership (that motion is the mothership's, not
            # wind), and state 3 (LANDED) means it has stopped moving.
            if s1 != 2 or s2 != 2:
                continue
            dt = t2 - t1
            if dt < 0.02:
                continue
            vx = (x2 - x1) / dt
            vy = (y2 - y1) / dt
            mid_alt = (a1 + a2) / 2.0
            mid_x = (x1 + x2) / 2.0
            mid_y = (y1 + y2) / 2.0
            b = int(mid_alt // bin_size)
            e = bins.setdefault(b, {"vx": 0.0, "vy": 0.0, "x": 0.0, "y": 0.0, "alt": 0.0, "n": 0})
            e["vx"] += vx
            e["vy"] += vy
            e["x"] += mid_x
            e["y"] += mid_y
            e["alt"] += mid_alt
            e["n"] += 1

    out = []
    for b in sorted(bins):
        e = bins[b]
        n = e["n"]
        out.append((e["x"] / n, e["y"] / n, e["vx"] / n, e["vy"] / n, e["alt"] / n))
    return out


def build_figure(port):
    fig = plt.figure(figsize=(16, 6))
    ax3d = fig.add_subplot(1, 3, 1, projection="3d")
    ax2d = fig.add_subplot(1, 3, 2)
    ax_wind = fig.add_subplot(1, 3, 3)
    fig.suptitle(f"CanSat-childish live telemetry - UDP 127.0.0.1:{port}")
    return fig, ax3d, ax2d, ax_wind


def draw_frame(ax3d, ax2d, ax_wind, vehicles):
    ax3d.cla()
    ax2d.cla()
    ax_wind.cla()

    ax3d.set_title("Flight path (real x/y drift + altitude)")
    ax3d.set_xlabel("east (m)")
    ax3d.set_ylabel("north (m)")
    ax3d.set_zlabel("altitude (m)")
    ax3d.view_init(elev=22, azim=-55)

    ax2d.set_title("Altitude vs time")
    ax2d.set_xlabel("t (s)")
    ax2d.set_ylabel("altitude (m)")
    ax2d.grid(True, alpha=0.3)

    ax_wind.set_title("Derived wind vector field (observers only)")
    ax_wind.set_xlabel("east (m)")
    ax_wind.set_ylabel("north (m)")
    ax_wind.grid(True, alpha=0.3)

    max_alt = 50.0
    xs_all, ys_all = [0.0], [0.0]
    for v in vehicles.values():
        max_alt = max(max_alt, v.alt)
        for (_, x, y, _, _s) in v.history:
            xs_all.append(x)
            ys_all.append(y)
    ax3d.set_zlim(0, max_alt * 1.1)

    for idx, name in enumerate(sorted(vehicles)):
        v = vehicles[name]
        color = MODE_COLORS.get(v.mode, "#999999")
        alpha = 0.35 if v.is_stale() else 1.0

        if v.history:
            ts, xs, ys, alts, _states = zip(*v.history)
            ax3d.plot(xs, ys, alts, color=color, linewidth=1.2, alpha=alpha * 0.7)

        nose, right = nose_and_right(v.roll, v.pitch)
        scale = max(3.0, max_alt * 0.06)
        p0 = np.array([v.x, v.y, v.alt])
        p_nose = p0 + nose * scale
        p_right = p0 + right * scale * 0.6

        ax3d.scatter([p0[0]], [p0[1]], [p0[2]], color=color, s=60, alpha=alpha)
        ax3d.plot([p0[0], p_nose[0]], [p0[1], p_nose[1]], [p0[2], p_nose[2]],
                  color=color, linewidth=2, alpha=alpha)
        ax3d.plot([p0[0], p_right[0]], [p0[1], p_right[1]], [p0[2], p_right[2]],
                  color="gray", linewidth=1, alpha=alpha * 0.8)

        label = f"{name}  {STATE_NAMES.get(v.state, '?')}/{MODE_NAMES.get(v.mode, '?')}  {v.alt:.0f}m"
        label_z = p0[2] + max_alt * (0.04 + 0.05 * idx)
        ax3d.text(p0[0], p0[1], label_z, label, fontsize=7, color=color)

        for (_, dx, dy, dalt) in v.deploy_marks:
            ax3d.scatter([dx], [dy], [dalt], color="black", marker="x", s=50)

        if v.history:
            ax2d.plot(ts, alts, color=color, label=name)
            for (dt, *_rest) in v.deploy_marks:
                ax2d.axvline(dt, color="black", linestyle=":", linewidth=1, alpha=0.5)

    if vehicles:
        ax2d.legend(loc="upper right", fontsize=8)

    pad = 10.0
    xr = (min(xs_all) - pad, max(xs_all) + pad)
    yr = (min(ys_all) - pad, max(ys_all) + pad)
    ax3d.set_xlim(*xr)
    ax3d.set_ylim(*yr)

    wind_pts = compute_wind_profile(vehicles)
    if wind_pts:
        xs, ys, us, vspds, alts = zip(*wind_pts)
        ax_wind.quiver(xs, ys, us, vspds, color="#1f77b4", angles="xy",
                        scale_units="xy", scale=0.3, width=0.005)
        for x, y, alt in zip(xs, ys, alts):
            ax_wind.annotate(f"{alt:.0f}m", (x, y), fontsize=7, color="#1f77b4",
                              xytext=(4, 4), textcoords="offset points")
        ax_wind.set_xlim(*xr)
        ax_wind.set_ylim(*yr)
    else:
        ax_wind.text(0.5, 0.5, "waiting for observer data...", ha="center", va="center",
                      transform=ax_wind.transAxes, fontsize=9, color="#999999")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=41000,
                     help="UDP port to listen on (must match CANSAT_VIZ_PORT if set)")
    ap.add_argument("--interval-ms", type=int, default=150, help="redraw interval")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", args.port))
    sock.setblocking(False)
    print(f"Listening for CanSat telemetry on udp://127.0.0.1:{args.port} ...")

    vehicles = {}
    fig, ax3d, ax2d, ax_wind = build_figure(args.port)

    def update(_frame):
        drain_socket(sock, vehicles)
        draw_frame(ax3d, ax2d, ax_wind, vehicles)

    anim = FuncAnimation(fig, update, interval=args.interval_ms, cache_frame_data=False)
    plt.tight_layout()
    plt.show()
    return anim  # keep a reference alive for the lifetime of plt.show()


if __name__ == "__main__":
    main()
