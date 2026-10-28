"""Recording is separate from the session: watch without keeping, start/stop recording on demand."""
import json
from pathlib import Path
import tempfile
import unittest

from kaist_ground_station.service import StationService


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class RecordingControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.clock = Clock()

    def service(self, **kw):
        s = StationService(self.root, clock=self.clock, **kw)
        self.addCleanup(s.stop)
        return s

    def run_for(self, s, seconds, step=0.25):
        for _ in range(int(seconds / step)):
            self.clock.t += step
            s.tick()

    def folders(self):
        return sorted(p for p in self.root.iterdir() if p.is_dir())

    def test_default_still_records_from_the_first_byte(self):
        s = self.service()
        s.start_demo()
        self.assertTrue(s.recording)
        self.assertEqual(len(self.folders()), 1)

    def test_without_auto_record_the_session_runs_but_nothing_is_written(self):
        s = self.service(auto_record=False)
        s.start_demo()
        self.run_for(s, 3)
        self.assertEqual(self.folders(), [])
        self.assertFalse(s.recording)
        self.assertGreater(s.telemetry.counts.get("GPS", 0), 0)              # still parsed and shown
        self.assertIn("not recording", s.snapshot().notices[-1][1])
        self.assertEqual(s.snapshot().log_directory, "")

    def test_start_mid_session_keeps_only_what_follows_and_times_start_at_zero(self):
        s = self.service(auto_record=False)
        s.start_demo()
        self.run_for(s, 30)                                                  # 30 s before anyone pressed Record
        s.start_recording()
        self.assertTrue(s.recording)
        self.run_for(s, 5)
        s.stop_recording()
        (folder,) = self.folders()
        rows = [json.loads(l) for l in (folder / "traffic.jsonl").read_text().splitlines()]
        self.assertGreater(len(rows), 10)
        self.assertLess(rows[0]["t"], 1.0)                                   # not 30 s: a replay must not wait out the gap
        self.assertLess(rows[-1]["t"], 6.0)
        events = (folder / "events.csv").read_text().splitlines()
        self.assertGreater(len(events), 5)

    def test_stop_recording_keeps_the_session_alive_and_stops_writing(self):
        s = self.service(auto_record=False)
        s.start_demo()
        s.start_recording()
        self.run_for(s, 3)
        s.stop_recording()
        (folder,) = self.folders()
        size = (folder / "rx.bin").stat().st_size
        self.assertGreater(size, 0)
        self.run_for(s, 3)
        self.assertEqual(s.mode, "DEMO")                                     # still receiving and displaying
        self.assertEqual((folder / "rx.bin").stat().st_size, size)           # but no longer being kept
        s.start_recording()                                                  # a second, separate recording
        self.assertEqual(len(self.folders()), 2)

    def test_misuse_is_refused_with_a_clear_error(self):
        s = self.service(auto_record=False)
        with self.assertRaises(ValueError):
            s.start_recording()                                              # no session yet
        s.start_demo()
        with self.assertRaises(ValueError):
            s.stop_recording()                                               # nothing to stop
        s.start_recording()
        with self.assertRaises(ValueError):
            s.start_recording()                                              # already recording

    def test_ending_the_session_closes_the_recording(self):
        s = self.service(auto_record=False)
        s.start_demo()
        s.start_recording()
        s.stop()
        self.assertFalse(s.recording)
        self.assertEqual(s.mode, "IDLE")

    def test_a_late_started_recording_replays_without_waiting(self):
        s = self.service(auto_record=False)
        s.start_demo()
        self.run_for(s, 20)
        s.start_recording()
        self.run_for(s, 4)
        s.stop()
        (folder,) = self.folders()
        replay = StationService(self.root / "replays", clock=self.clock)
        self.addCleanup(replay.stop)
        replay.start_replay(folder / "traffic.jsonl")
        self.run_for(replay, 1.0)
        self.assertGreater(replay.rx_bytes, 0)                               # data within the first second


if __name__ == "__main__":
    unittest.main()
