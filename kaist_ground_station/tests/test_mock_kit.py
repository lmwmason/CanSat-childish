"""The pretend kit speaks the real wire protocol, so the real service handles it like hardware."""
from pathlib import Path
import tempfile
import unittest

from kaist_ground_station.service import StationService
from kaist_ground_station.tools.mock_web import MockKit, test_pictures
from kaist_ground_station.web.serialize import text_lines


def fixes(n=40):
    # (seconds, 'HHMMSS', lat, lon, alt): a straight 5 m/s descent drifting east
    return [(float(i), f"2306{42 + i % 60:02d}", 36.5888 + i * 1e-6, 127.5694 + i * 2e-5, 200.0 - 5 * i) for i in range(n)]


class Clock:
    t = 100.0

    def __call__(self):
        return self.t


class MockKitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = Clock()

    def live(self, picture=None, **kit_args):
        kit = MockKit(fixes(), picture=picture, clock=self.clock, **kit_args)
        service = StationService(Path(self.tmp.name), clock=self.clock, transport_factory=lambda port, baud: kit)
        self.addCleanup(service.stop)
        service.connect("mock")
        return kit, service

    def run_for(self, service, seconds, step=0.1):
        for _ in range(int(seconds / step)):
            self.clock.t += step
            service.tick()

    def test_every_stream_parses_cleanly_through_the_real_parser(self):
        kit, service = self.live()
        self.run_for(service, 12)
        counts = service.telemetry.counts
        for kind in ("GPS", "IMU", "ATLM", "DTLM", "MESSAGE"):
            self.assertGreater(counts.get(kind, 0), 0, kind)
        self.assertNotIn("ERROR", counts)
        self.assertEqual((service.parser.errors, service.parser.discarded), (0, 0))
        gps = service.telemetry.gps
        self.assertEqual((gps["fix"], gps["satellites"]), (1, 12))
        self.assertAlmostEqual(gps["lat"], 36.5888 + 11 * 1e-6, places=5)

    def test_pictures_arrive_as_complete_jpegs_and_qlook_fills_in(self):
        picture = test_pictures(None)
        kit, service = self.live(picture=picture)
        self.run_for(service, 12)
        tel = service.telemetry
        self.assertGreater(tel.counts.get("IMAGE", 0), 3)
        self.assertTrue(tel.jpeg.startswith(b"\xff\xd8") and tel.jpeg.endswith(b"\xff\xd9"))
        self.assertGreater(tel.qlook_version, 20)
        self.assertNotIn("ERROR", tel.counts)

    def test_stop_stops_the_data_because_it_is_a_real_link(self):
        kit, service = self.live()
        self.run_for(service, 5)
        before = service.rx_bytes
        service.stop()
        self.assertTrue(kit.closed)
        self.clock.t += 30
        service.tick()
        self.assertEqual((service.mode, service.rx_bytes), ("IDLE", before))     # nothing keeps arriving

    def test_the_adapter_answers_the_dial_line_like_the_real_one(self):
        kit, service = self.live()
        service.enable_transmit(True)
        service.send_terminal("ATD0001958D78EC")
        self.assertEqual(kit.written, [b"ATD0001958D78EC\r\n"])
        self.run_for(service, 1)
        lines = [line for _, line in text_lines(service.terminal)]
        self.assertIn("OK", lines)
        self.assertIn("CONNECT 0001958D78EC", lines)

    def test_gps_rate_can_mimic_the_slow_real_kit(self):
        kit, service = self.live(gps_hz=0.5)
        self.run_for(service, 30)
        self.assertEqual(service.telemetry.counts["GPS"], 15)                     # one fix every 2 s
        self.assertEqual(len(kit.timeline), 20)


if __name__ == "__main__":
    unittest.main()
