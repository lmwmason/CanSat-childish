"""Camera recovery ACKs and serial reception during slow snapshot analysis."""
import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest import mock

from kaist_ground_station.models import Telemetry
from kaist_ground_station.protocol import StreamParser
from kaist_ground_station.service import StationService
from kaist_ground_station.tests.test_protocol import ATLM, GPS
from kaist_ground_station.tests.test_service import FakePort
from kaist_ground_station.web import serialize
from kaist_ground_station.web.server import WebServer


class CameraRecoveryTests(unittest.TestCase):
    def test_documented_settings_ack_at_every_split_preserves_following_gps(self):
        wire = bytes.fromhex("76 00 31 00 00") + GPS
        for split in range(len(wire) + 1):
            parser = StreamParser()
            frames = parser.feed(wire[:split]) + parser.feed(wire[split:])
            self.assertEqual([f.kind for f in frames], ["CAMERA_ACK", "GPS"])
            self.assertEqual(frames[0].data, {"command": "image_settings", "status": 0})
            self.assertIsNone(frames[0].checksum)
            self.assertEqual((parser.errors, parser.discarded), (0, 0))

    def test_settings_ack_does_not_hide_bad_status_or_reserved_byte(self):
        for bad in ("76 00 31 00 01", "76 00 31 01 00"):
            parser = StreamParser()
            frames = parser.feed(bytes.fromhex(bad) + GPS)
            self.assertEqual([f.kind for f in frames], ["ERROR", "GPS"])


class DriftCacheTests(unittest.TestCase):
    def test_deep_copied_snapshots_reuse_estimate_but_changed_coordinates_do_not(self):
        serialize._drift_for_fixes.cache_clear()
        self.addCleanup(serialize._drift_for_fixes.cache_clear)
        t = Telemetry()
        t.track.append((36.5, 127.5))
        t.altitude_history.append((1.0, 140.0))
        with mock.patch.object(serialize.drift, "estimate", return_value=([], [], None)) as estimate:
            a = serialize.drift_dict(copy.deepcopy(t))
            b = serialize.drift_dict(copy.deepcopy(t))
            self.assertEqual(estimate.call_count, 1)
            self.assertEqual(a, b)
            # Same length and timestamp, different input (including another session).
            t.track[0] = (36.6, 127.6)
            c = serialize.drift_dict(copy.deepcopy(t))
            self.assertEqual(estimate.call_count, 2)
            self.assertNotEqual(a["origin"], c["origin"])


class ReceiveIsolationTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "Linux PTY integration")
    def test_serial_read_and_raw_logging_continue_while_analysis_is_blocked(self):
        import pty
        from kaist_ground_station.transport import SerialTransport
        from kaist_ground_station.web import server as web

        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        with tempfile.TemporaryDirectory() as tmp:
            service = StationService(Path(tmp), transport_factory=SerialTransport)
            service.connect(os.ttyname(slave))
            folder = Path(service.log_directory)
            server = WebServer(service, port=0)
            entered, release = threading.Event(), threading.Event()
            original = web.state_dict

            def slow_analysis(*args, **kwargs):
                entered.set()
                if not release.wait(5):
                    raise TimeoutError("test did not release analysis")
                return original(*args, **kwargs)

            try:
                with mock.patch.object(web, "state_dict", side_effect=slow_analysis):
                    server.start()
                    self.assertTrue(entered.wait(2), "publisher did not start")
                    packet = ATLM + GPS
                    expected = packet * 24
                    # A finite serial buffer cannot stand in for an active reader:
                    # assert receipt and durable raw output before releasing analysis.
                    for _ in range(24):
                        os.write(master, packet)
                        time.sleep(0.02)
                    deadline = time.monotonic() + 2
                    while time.monotonic() < deadline:
                        with server.lock:
                            received = service.rx_bytes
                        if received == len(expected):
                            break
                        time.sleep(0.01)
                    self.assertFalse(release.is_set())
                    with server.lock:
                        self.assertEqual(service.rx_bytes, len(expected))
                        self.assertEqual(service.telemetry.counts.get("GPS"), 24)
                        self.assertEqual(service.parser.errors, 0)
                        service.recorder.flush()
                    self.assertEqual((folder / "rx.bin").read_bytes(), expected)
            finally:
                release.set()
                server.stop()
                service.stop()
            self.assertTrue(all(not t.is_alive() for t in server._threads))

    def test_slow_old_publication_cannot_overwrite_a_new_session(self):
        from kaist_ground_station.web import server as web
        with tempfile.TemporaryDirectory() as tmp:
            service = StationService(Path(tmp), transport_factory=lambda *_: FakePort(), auto_record=False)
            service.connect("A")
            server = WebServer(service, port=0)
            entered, release = threading.Event(), threading.Event()
            original = web.state_dict

            def slow_analysis(*args, **kwargs):
                entered.set()
                release.wait(5)
                return original(*args, **kwargs)

            thread = threading.Thread(target=server._publish)
            try:
                with mock.patch.object(web, "state_dict", side_effect=slow_analysis):
                    thread.start()
                    self.assertTrue(entered.wait(2))
                    with server.lock:
                        service.connect("B")
                    release.set()
                    thread.join(2)
                    self.assertFalse(thread.is_alive())
                server._publish()
                state = json.loads(server.state_json)
                self.assertEqual(state["session_id"], service.session_id)
                self.assertIn("B", state["source"])
            finally:
                release.set()
                if thread.ident is not None:
                    thread.join(2)
                server.httpd.server_close()
                service.stop()
