"""Opt-in real Tk rendering checks; run under a virtual or desktop X display."""
import os
from pathlib import Path
import tempfile
import unittest


@unittest.skipUnless(os.environ.get("RUN_KAIST_UI_TESTS") == "1", "requires opt-in X display")
class UITests(unittest.TestCase):
    def test_demo_tree_is_visible_and_controls_fit_laptop_window(self):
        import tkinter as tk
        from kaist_ground_station.recording import DEMO_RECORDING
        from kaist_ground_station.service import StationService
        from kaist_ground_station.ui import StationWindow
        with tempfile.TemporaryDirectory() as tmp:
            root = tk.Tk()
            service = StationService(Path(tmp))
            try:
                service.start_replay(DEMO_RECORDING)
                window = StationWindow(root,service)
                root.update()
                window._render(service.snapshot())
                root.update()
                self.assertEqual(window.analog.item("7","values")[1],"93")
                x,y = window.analog.winfo_rootx()+10,window.analog.winfo_rooty()+40
                self.assertEqual(root.winfo_containing(x,y),window.analog)
                for geometry in ("1280x960","1040x720"):
                    root.geometry(geometry)
                    root.update()
                    for widget in (window.send_button,window.event_text,window.gps_label,window.imu_label):
                        bottom = widget.winfo_rooty()+widget.winfo_height()
                        self.assertLessEqual(bottom,root.winfo_rooty()+root.winfo_height())
                        self.assertGreater(widget.winfo_height(),5)
                    self.assertGreater(window.track_canvas.winfo_height(),30)
                self.assertEqual(str(window.send_button["state"]),"disabled")
                self.assertTrue(window.message_text.get("1.0","end").strip())
            finally:
                service.stop()
                root.destroy()
