"""Short rolling history of the streams the service only keeps the latest value of (IMU, ATLM).

Lives in the web layer so a page reload does not lose the strip charts. Entries are appended once
per received frame, detected by the frame counter changing, and stamped with the time the frame
arrived (not the time of this poll), so rates derived from them are not quantised by the poll rate.

Angular rate is *derived* from the first three IMU fields (angles in degrees) as the change between
consecutive samples, unwrapped across the +-180 boundary. It is not a gyro reading: the kit's extra
IMU fields could be gyro or accelerometer depending on its output setting and are not interpreted.
"""
from __future__ import annotations

from collections import deque


def _wrap(delta: float) -> float:
    return (delta + 180.0) % 360.0 - 180.0


class History:
    def __init__(self, maxlen: int = 600):
        self.imu = deque(maxlen=maxlen)      # [t, field0, field1, field2]
        self.omega = deque(maxlen=maxlen)    # [t, d(field0)/dt, d(field1)/dt, d(field2)/dt]  deg/s
        self.atlm = deque(maxlen=maxlen)     # [t, ch0 ... ch7]
        self._seen = {"IMU": None, "ATLM": None}
        self._prev = None

    def update(self, snap) -> None:
        t, counts = snap.telemetry, snap.telemetry.counts
        if len(t.imu) >= 3 and counts.get("IMU") != self._seen["IMU"]:
            self._seen["IMU"] = counts.get("IMU")
            ts, angles = t.seen.get("IMU", snap.now), tuple(t.imu[:3])
            self.imu.append([ts, *angles])
            if self._prev is not None and ts - self._prev[0] > 1e-3:
                dt = ts - self._prev[0]
                self.omega.append([ts, *[_wrap(a - b) / dt for a, b in zip(angles, self._prev[1])]])
            self._prev = (ts, angles)
        if t.atlm and counts.get("ATLM") != self._seen["ATLM"]:
            self._seen["ATLM"] = counts.get("ATLM")
            self.atlm.append([t.seen.get("ATLM", snap.now), *t.atlm[:8]])

    def as_dict(self) -> dict:
        return {"imu": list(self.imu), "omega": list(self.omega), "atlm": list(self.atlm)}
