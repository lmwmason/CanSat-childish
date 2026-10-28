import csv
import json
import os
from pathlib import Path
import tempfile
import unittest

from kaist_ground_station.models import load_calibration
from kaist_ground_station.recording import DEMO_RECORDING
from kaist_ground_station.service import StationService
from kaist_ground_station.tests.test_protocol import ATLM, GPS


class Clock:
    now = 0.0
    def __call__(self):
        return self.now


class FakePort:
    def __init__(self,*args):
        self.incoming = b""
        self.writes = []
        self.closed = False
    def read(self):
        data,self.incoming = self.incoming,b""
        return data
    def write(self,data):
        self.writes.append(data)
    def close(self):
        self.closed = True


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.port = FakePort()
        self.service = StationService(Path(self.tmp.name),self.clock,lambda *_: self.port)
    def tearDown(self):
        self.service.stop()
        self.tmp.cleanup()

    def test_live_capture_round_trip_and_replay_never_writes(self):
        s = self.service
        s.connect("fake")
        with self.assertRaises(ValueError): s.send_command(0,1)
        self.port.incoming = ATLM+GPS
        self.clock.now = 0.2
        s.tick()
        snap = s.snapshot()
        self.assertEqual(snap.valid_frames,2)
        snap.telemetry.gps.clear()
        self.assertTrue(s.snapshot().telemetry.gps)
        s.enable_transmit(True)
        s.send_command(0,1)
        self.assertEqual(self.port.writes,[bytes.fromhex("56 00 48 00 00 01 01 00")])
        folder = Path(s.log_directory)
        s.stop()
        self.assertEqual((folder/"rx.bin").read_bytes(),ATLM+GPS)
        with (folder/"events.csv").open() as f:
            self.assertEqual(len(list(csv.DictReader(f))),4)
        s.start_replay(folder/"traffic.jsonl")
        with self.assertRaises(ValueError): s.enable_transmit(True)
        self.clock.now += 1
        s.tick()
        self.assertEqual(s.mode,"IDLE")
        self.assertEqual(s.snapshot().valid_frames,2)
        self.assertEqual(len(self.port.writes),1)

    def test_source_switch_resets_telemetry_and_tx(self):
        s = self.service
        s.connect("fake")
        s.enable_transmit(True)
        self.port.incoming = GPS
        s.tick()
        s.start_replay(DEMO_RECORDING)
        self.assertFalse(s.snapshot().can_transmit)
        self.assertFalse(s.snapshot().telemetry.gps)
        self.assertTrue(self.port.closed)
        s.tick()
        self.assertEqual(s.snapshot().valid_frames,5)
        self.clock.now = 10
        self.assertGreater(s.snapshot().link_age_s,3)

    def test_calibration_file_and_session_metadata(self):
        cfg = Path(self.tmp.name)/"csAtlmSet.cfg"
        cfg.write_text("# header\n7,1,0.0815053,0,V\n")
        self.service.configure_calibration(cfg)
        self.service.start_replay(DEMO_RECORDING)
        self.service.tick()
        s = self.service.snapshot()
        self.assertAlmostEqual(s.calibration[7].apply(s.telemetry.atlm[7]),7.580,places=3)
        metadata = json.loads((Path(s.log_directory)/"session.json").read_text())
        self.assertTrue(metadata["calibration"][7]["enabled"])
        with self.assertRaises(ValueError): self.service.configure_calibration(cfg)
        cfg.write_text("8,1,1,0,V")
        with self.assertRaises(ValueError): load_calibration(cfg)

    def test_disconnect_and_recording_failure_close_connection(self):
        def fail(): raise OSError("USB unplugged")
        s = self.service
        s.connect("fake")
        self.port.read = fail
        s.tick()
        self.assertEqual(s.mode,"IDLE")
        self.assertTrue(self.port.closed)
        self.assertTrue(any("USB unplugged" in msg for _,msg in s.snapshot().notices))

    @unittest.skipUnless(os.name=="posix","Linux PTY integration")
    def test_real_serial_transport_over_linux_pty(self):
        import pty
        import time
        from kaist_ground_station.transport import SerialTransport
        master,slave = pty.openpty()
        s = StationService(Path(self.tmp.name),transport_factory=SerialTransport)
        try:
            s.connect(os.ttyname(slave))
            os.write(master,ATLM[:5])
            for _ in range(10): s.tick(); time.sleep(0.001)
            self.assertEqual(s.snapshot().valid_frames,0)
            os.write(master,ATLM[5:]+GPS)
            for _ in range(20): s.tick(); time.sleep(0.001)
            self.assertEqual(s.snapshot().valid_frames,2)
            s.enable_transmit(True)
            s.send_command(1,0)
            import select
            self.assertTrue(select.select([master],[],[],1)[0])
            self.assertEqual(os.read(master,100),bytes.fromhex("56 00 48 00 01 00 01 00"))
        finally:
            s.stop()
            os.close(master)
            os.close(slave)


if __name__ == "__main__":
    unittest.main()
