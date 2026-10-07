import csv
import math
import tempfile
import unittest
from pathlib import Path

from windField.__main__ import make_demo
from windField.core import Config, MissingPositionData, estimate, read_trajectory


class AnalysisTests(unittest.TestCase):
    def test_existing_child_csv_cannot_claim_wind(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "old.csv"
            path.write_text("idx,state,t_s,rel_alt_m,pressure_hPa,temp_C,humidity_pct,accel_g\n"
                            "0,DESCENT,0,100,1000,20,50,1\n", encoding="utf-8")
            with self.assertRaisesRegex(MissingPositionData, "no lat/lon"):
                read_trajectory(path)

    def test_synthetic_wind_recovery_and_spike_filter(self):
        with tempfile.TemporaryDirectory() as d:
            path, truth_path = make_demo(Path(d), seed=20261007, gps_sigma_m=1.5)
            rows, _ = read_trajectory(path)
            result, stats = estimate(rows, Config(gps_sigma_m=1.5))
            with truth_path.open(newline="") as f:
                truth = {(r["child_id"], float(r["t_s"])): r for r in csv.DictReader(f)}
            errors = []
            for r in result:
                if not r["accepted"]:
                    continue
                target = truth[(r["child_id"], r["t_s"])]
                errors.append((r["wind_e_ms"] - float(target["wind_e_ms"])) ** 2 +
                              (r["wind_n_ms"] - float(target["wind_n_ms"])) ** 2)
            self.assertEqual(stats["accepted"], 108)
            self.assertLess(math.sqrt(sum(errors) / len(errors)), 0.8)
            spike = next(r for r in rows if r["child_id"] == "child-1" and r["t_s"] == 20)
            spike["lon"] += 0.001
            _, dirty_stats = estimate(rows, Config(gps_sigma_m=1.5))
            self.assertEqual(dirty_stats["gps_spikes"], 1)


if __name__ == "__main__":
    unittest.main()
