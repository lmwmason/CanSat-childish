import tempfile
import unittest
from pathlib import Path

from windField.view3d import _data, write_html, write_preview


class View3dTests(unittest.TestCase):
    def test_3d_artifacts_use_altitude_and_keep_interpolation_distinct(self):
        estimates = [
            {"child_id": child, "east_m": x, "north_m": y, "alt_m": 50.0, "accepted": 1}
            for child, x, y in (("A", 0.0, 0.0), ("B", 20.0, 0.0), ("C", 0.0, 20.0))
        ]
        profile = [
            {"child_id": r["child_id"], "east_m": r["east_m"], "north_m": r["north_m"],
             "alt_m": r["alt_m"], "wind_e_ms": 3.0, "wind_n_ms": 1.0}
            for r in estimates
        ]
        data = _data(estimates, profile)
        self.assertEqual(len(data["measured"]), 3)
        self.assertEqual(len(data["inferred"]), 1)
        self.assertEqual(data["inferred"][0]["z"], 50.0)
        self.assertEqual(data["inferred"][0]["kind"], "interpolated centroid")
        with tempfile.TemporaryDirectory() as folder:
            html, png = Path(folder) / "3d.html", Path(folder) / "3d.png"
            write_html(estimates, profile, html)
            write_preview(estimates, profile, png)
            content = html.read_text()
            self.assertIn("Drag to rotate", content)
            self.assertIn('"z":50.0', content)
            self.assertNotIn("https://", content)
            self.assertTrue(png.exists())

    def test_empty_quality_result_still_writes_viewer(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "empty.html"
            write_html([], [], path)
            self.assertIn("all.length?", path.read_text())


if __name__ == "__main__":
    unittest.main()
