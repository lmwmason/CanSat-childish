import math
import unittest

import numpy as np

from kaist_ground_station.web import drift


def synthetic(ve=2.0, vn=-1.0, fall=5.0, seconds=60, hz=1.0):
    """A steady descent drifting at (ve, vn) m/s starting at 36.37N 127.36E."""
    lat0, lon0 = 36.37, 127.36
    fixes = []
    for i in range(int(seconds * hz)):
        t = i / hz
        lat = lat0 + math.degrees(vn * t / drift.EARTH_RADIUS_M)
        lon = lon0 + math.degrees(ve * t / (drift.EARTH_RADIUS_M * math.cos(math.radians(lat0))))
        fixes.append((1000 + t, lat, lon, 300 - fall * t))
    return fixes


class DriftTests(unittest.TestCase):
    def test_windfield_is_found_from_the_package_location(self):
        core, error = drift._load_windfield()
        self.assertIsNone(error)
        self.assertTrue(hasattr(core, "estimate"))

    def test_recovers_constant_drift_descent_rate_and_profile(self):
        fixes = synthetic()
        samples, profile, error = drift.estimate(fixes)
        self.assertIsNone(error)
        self.assertGreater(len(samples), 20)
        for _, _, _, _, ve, vn in samples:
            self.assertAlmostEqual(ve, 2.0, delta=0.1)
            self.assertAlmostEqual(vn, -1.0, delta=0.1)
        self.assertGreater(len(profile), 10)
        self.assertAlmostEqual(drift.descent_rate(drift.to_local(fixes)[1]), 5.0, delta=0.05)

    def test_newest_estimate_lags_the_newest_fix(self):
        fixes = synthetic(seconds=60)
        samples, _, _ = drift.estimate(fixes)
        lag = fixes[-1][0] - samples[-1][0]
        self.assertGreaterEqual(lag, 2)
        self.assertLessEqual(lag, drift.WINDOW_S / 2 + 1)

    def test_too_little_data_or_no_descent_gives_nothing_instead_of_a_guess(self):
        self.assertEqual(drift.estimate(synthetic(seconds=4)), ([], [], None))
        self.assertEqual(drift.estimate(synthetic(fall=0.0)), ([], [], None))
        self.assertEqual(drift.estimate([]), ([], [], None))
        self.assertIsNone(drift.descent_rate(drift.to_local(synthetic(seconds=1))[1]))

    def test_buffers_of_different_length_align_at_the_newest_end(self):
        fixes = synthetic(seconds=10)
        alts = [(t, a) for t, _, _, a in fixes][-6:]          # shorter altitude buffer
        track = [(la, lo) for _, la, lo, _ in fixes]
        got = drift.aligned_fixes(alts, track)
        self.assertEqual(len(got), 6)
        self.assertEqual(got[-1], fixes[-1])


if __name__ == "__main__":
    unittest.main()


class VelocityTests(unittest.TestCase):
    def test_recovers_east_north_and_vertical_velocity(self):
        _, local = drift.to_local(synthetic(ve=2.0, vn=-1.0, fall=5.0, seconds=30))
        series = drift.velocity_series(local)
        self.assertGreater(len(series), 20)
        for _, ve, vn, vu in series:
            self.assertAlmostEqual(ve, 2.0, delta=0.05)
            self.assertAlmostEqual(vn, -1.0, delta=0.05)
            self.assertAlmostEqual(vu, -5.0, delta=0.05)            # falling = negative up-velocity

    def test_needs_enough_fixes_and_no_division_by_a_zero_span(self):
        self.assertEqual(drift.velocity_series(np.empty((0, 4))), [])
        _, two = drift.to_local(synthetic(seconds=2))
        self.assertEqual(drift.velocity_series(two), [])
        same_time = np.array([[1.0, 0, 0, 0]] * 5)
        self.assertEqual(drift.velocity_series(same_time), [])


class SlowGpsTests(unittest.TestCase):
    """The real kit sends GGA at about 0.5 Hz: a fixed 3 s window held 2 fixes and produced nothing."""

    def test_velocity_and_descent_rate_work_at_half_a_hertz(self):
        fixes = synthetic(ve=2.0, vn=-1.0, fall=5.0, seconds=60, hz=0.5)
        _, local = drift.to_local(fixes)
        series = drift.velocity_series(local)
        self.assertGreater(len(series), 20)
        for _, ve, vn, vu in series:
            self.assertAlmostEqual(ve, 2.0, delta=0.05)
            self.assertAlmostEqual(vn, -1.0, delta=0.05)
            self.assertAlmostEqual(vu, -5.0, delta=0.05)
        self.assertAlmostEqual(drift.descent_rate(local), 5.0, delta=0.05)

    def test_fast_gps_keeps_the_short_window(self):
        _, local = drift.to_local(synthetic(hz=10.0, seconds=10))
        self.assertEqual(drift.window_for(local[:, 0], 3.0), 3.0)
        _, slow = drift.to_local(synthetic(hz=0.5, seconds=30))
        self.assertAlmostEqual(drift.window_for(slow[:, 0], 3.0), 7.0)

    def test_drift_estimate_still_works_at_half_a_hertz(self):
        samples, profile, error = drift.estimate(synthetic(ve=2.0, vn=-1.0, fall=5.0, seconds=120, hz=0.5))
        self.assertIsNone(error)
        self.assertGreater(len(samples), 10)
        self.assertAlmostEqual(samples[-1][4], 2.0, delta=0.15)
