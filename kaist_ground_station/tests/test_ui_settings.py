from pathlib import Path
import tempfile
import unittest

from kaist_ground_station.ui_settings import UISettings, load_ui_settings


class UISettingsTests(unittest.TestCase):
    def write(self, text):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        path = Path(d.name) / "ui.cfg"
        path.write_text(text, encoding="utf-8")
        return path

    def test_packaged_default_config_is_read_without_arguments(self):
        from kaist_ground_station.ui_settings import DEFAULT_PATH
        self.assertTrue(DEFAULT_PATH.is_file())
        self.assertEqual(load_ui_settings(None), load_ui_settings(DEFAULT_PATH))

    def test_partial_file_overrides_only_given_keys(self):
        s = load_ui_settings(self.write("[fonts]\nfont_family = A, B\n[sizes]\nstatus = 20\n"))
        self.assertEqual(s.font_family, ["A", "B"])
        self.assertEqual(s.size_status, 20)
        self.assertEqual(s.size_base, UISettings().size_base)

    def test_bad_values_and_missing_file_are_reported(self):
        with self.assertRaises(ValueError):
            load_ui_settings(self.write("[sizes]\nbase = big\n"))
        with self.assertRaises(ValueError):
            load_ui_settings(self.write("[sizes]\nbase = 0\n"))
        with self.assertRaises(OSError):
            load_ui_settings(Path("/nonexistent/ui.cfg"))

    def test_checkpoint_labels_default_override_and_limits(self):
        self.assertEqual(UISettings().checkpoints[1], "Drop")
        self.assertEqual(load_ui_settings(self.write("[checkpoints]\nlabels = A, B ,C\n")).checkpoints, ["A", "B", "C"])
        self.assertEqual(load_ui_settings(self.write("[checkpoints]\nlabels =\n")).checkpoints, [])
        with self.assertRaises(ValueError):
            load_ui_settings(self.write("[checkpoints]\nlabels = " + ",".join("x%d" % i for i in range(13)) + "\n"))

    def test_open_pages_default_override_and_validation(self):
        self.assertEqual(UISettings().open_pages, ["flight", "wind"])
        self.assertEqual(load_ui_settings(self.write("[ui]\nopen_pages = wind\n")).open_pages, ["wind"])
        self.assertEqual(load_ui_settings(self.write("[ui]\nopen_pages =\n")).open_pages, [])
        with self.assertRaises(ValueError):
            load_ui_settings(self.write("[ui]\nopen_pages = flight, moon\n"))

    def test_language_default_override_and_validation(self):
        self.assertEqual(UISettings().language, "en")
        self.assertEqual(load_ui_settings(self.write("[ui]\nlanguage = ko\n")).language, "ko")
        with self.assertRaises(ValueError):
            load_ui_settings(self.write("[ui]\nlanguage = xx\n"))

    def test_alarm_thresholds_override_and_validate(self):
        s = load_ui_settings(self.write("[alarms]\nmin_satellites = 6\n"))
        self.assertEqual(s.alarms["min_satellites"], 6.0)
        self.assertEqual(s.alarms["link_alarm_s"], UISettings().alarms["link_alarm_s"])
        for bad in ("[alarms]\nnope = 1\n", "[alarms]\nmax_hdop = x\n", "[alarms]\nmax_hdop = -1\n"):
            with self.assertRaises(ValueError):
                load_ui_settings(self.write(bad))

    def test_packaged_config_parses_whatever_values_it_holds(self):
        from kaist_ground_station.ui_settings import DEFAULT_PATH
        settings = load_ui_settings(DEFAULT_PATH)
        self.assertTrue(settings.font_family and settings.mono_family and settings.plot_family)
        self.assertGreater(settings.size_base, 0)

if __name__ == "__main__":
    unittest.main()
