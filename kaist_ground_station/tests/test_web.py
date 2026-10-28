import json
from pathlib import Path
import tempfile
import unittest
import urllib.request

from kaist_ground_station.frontends import FRONTENDS, load_frontend
from kaist_ground_station.recording import DEMO_RECORDING
from kaist_ground_station.tests.support import RecordedKit
from kaist_ground_station.service import StationService
from kaist_ground_station.web.serialize import state_dict
from kaist_ground_station.web.server import WebServer


def get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read()


def post(url, body):
    req = urllib.request.Request(url, json.dumps(body).encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = StationService(Path(self.tmp.name))
        self.addCleanup(self.service.stop)

    def test_registry_lists_web_and_loads_it(self):
        self.assertIn("web", FRONTENDS)
        self.assertTrue(callable(load_frontend("web")))

    def test_state_is_strict_json_and_has_no_raw_bytes(self):
        self.service.start_replay(DEMO_RECORDING)
        for _ in range(60):
            self.service.tick()
        text = json.dumps(state_dict(self.service.snapshot()), allow_nan=False)
        data = json.loads(text)
        for key in ("mode", "gps", "imu", "atlm", "dtlm", "track", "altitude", "seen_age", "counts"):
            self.assertIn(key, data)
        self.assertLessEqual(len(data["track"]), 500)
        self.assertLess(len(text), 200_000)

    def test_http_endpoints_and_actions(self):
        server = WebServer(self.service, port=0)
        server.start()
        self.addCleanup(server.stop)
        base = server.url.rstrip("/")
        self.assertIn(b"<canvas", get(base + "/")[1])
        status, logo = get(base + "/logo.png")
        self.assertEqual((status, logo[:4]), (200, b"\x89PNG"))
        self.assertEqual(get(base + "/api/state")[0], 200)
        self.assertEqual(json.loads(get(base + "/api/state")[1])["mode"], "IDLE")
        self.assertIn("colors", json.loads(get(base + "/api/config")[1]))
        self.assertEqual(post(base + "/api/action", {"name": "replay", "path": str(DEMO_RECORDING)})[0], 200)
        self.assertEqual(json.loads(get(base + "/api/state")[1])["mode"], "REPLAY")
        code, reply = post(base + "/api/action", {"name": "nope"})
        self.assertEqual(code, 400)
        self.assertIn("error", reply)
        code, reply = post(base + "/api/action", {"name": "tx", "enabled": True})
        self.assertEqual(code, 400)  # TX only allowed on a LIVE link; the service refuses, UI shows the text


if __name__ == "__main__":
    unittest.main()


class SerializeTextTests(unittest.TestCase):
    def test_terminal_text_is_printable_ascii_not_bytes_repr(self):
        from kaist_ground_station.web.serialize import printable
        self.assertEqual(printable("00 24 47 50 47 47 41 0d 0a"), "·$GPGGA··")
        self.assertEqual(printable("zz"), "")


class OpenPagesTests(unittest.TestCase):
    def test_one_window_per_configured_screen_in_order(self):
        from unittest import mock
        from kaist_ground_station.ui_settings import UISettings
        from kaist_ground_station.web import server as web
        fake = mock.Mock(url="http://127.0.0.1:9/")
        with mock.patch.object(web.webbrowser, "open_new") as opener:
            urls = web.open_pages(fake, UISettings(), delay=0)
            self.assertEqual(urls, ["http://127.0.0.1:9/", "http://127.0.0.1:9/wind"])
            self.assertEqual([c.args[0] for c in opener.call_args_list], urls)
            opener.reset_mock()
            only = UISettings(open_pages=["wind"])
            self.assertEqual(web.open_pages(fake, only, delay=0), ["http://127.0.0.1:9/wind"])
            self.assertEqual(opener.call_count, 1)
            opener.reset_mock()
            self.assertEqual(web.open_pages(fake, UISettings(open_pages=[]), delay=0), [])
            opener.assert_not_called()


class HistoryTests(unittest.TestCase):
    def test_history_appends_once_per_frame_and_survives_in_state(self):
        import tempfile
        from pathlib import Path
        from kaist_ground_station.service import StationService
        from kaist_ground_station.web.history import History
        with tempfile.TemporaryDirectory() as tmp:
            now = [0.0]
            service = StationService(Path(tmp), clock=lambda: now[0])     # the demo paces itself by the clock
            service.start_replay(DEMO_RECORDING)
            history = History(maxlen=5)
            for _ in range(80):
                now[0] += 0.25
                service.tick()
                history.update(service.snapshot())
                history.update(service.snapshot())          # same frame count: must not duplicate
            service.stop()
        d = history.as_dict()
        self.assertEqual(len(d["imu"]), 5)
        self.assertEqual(len(d["imu"][0]), 4)
        self.assertEqual(len(d["atlm"][0]), 9)
        self.assertEqual(len({row[0] for row in d["imu"]}), 5)


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = [100.0]
        from kaist_ground_station.service import StationService
        self.service = StationService(Path(self.tmp.name), clock=lambda: self.now[0],
                                      transport_factory=lambda port, baud: RecordedKit(lambda: self.now[0]))
        self.addCleanup(self.service.stop)

    def live(self):
        self.service.connect("recorded", 115200)

    def test_records_time_and_flight_state_and_persists_in_the_session_folder(self):
        from kaist_ground_station.web.checkpoints import Checkpoints, FILENAME
        self.live()
        for _ in range(20):
            self.now[0] += 0.25
            self.service.tick()
        marks = Checkpoints(self.service)
        row = marks.add("  Drop ")
        self.assertEqual(row["label"], "Drop")
        self.assertEqual(row["service_t"], self.now[0])
        self.assertTrue(row["utc"].endswith("+00:00"))
        self.assertIsNotNone(row["alt_m"])
        self.assertEqual([r["label"] for r in marks.as_dict()["items"]], ["Drop"])
        # a fresh object (server restart / page reload) reads the same record back
        again = Checkpoints(self.service)
        self.assertEqual([r["id"] for r in again.as_dict()["items"]], [1])
        self.assertTrue((Path(self.service.log_directory) / FILENAME).is_file())

    def test_undo_removes_only_the_last_and_is_append_only(self):
        from kaist_ground_station.web.checkpoints import Checkpoints, FILENAME
        self.live()
        marks = Checkpoints(self.service)
        marks.add("A"); marks.add("B")
        self.assertEqual(marks.undo()["label"], "B")
        self.assertEqual([r["label"] for r in Checkpoints(self.service).as_dict()["items"]], ["A"])
        lines = (Path(self.service.log_directory) / FILENAME).read_text().splitlines()
        self.assertEqual(len(lines), 3)                      # A, B and the undo marker: nothing was rewritten
        marks.add("C")
        self.assertEqual([r["id"] for r in marks.as_dict()["items"]], [1, 2])   # ids never reuse a visible one

    def test_unnamed_mark_is_stored_without_a_label_and_keeps_its_number(self):
        from kaist_ground_station.web.checkpoints import Checkpoints
        self.live()
        marks = Checkpoints(self.service)
        marks.add("Drop")
        row = marks.add(unnamed=True)
        self.assertEqual((row["id"], row["label"]), (2, ""))
        marks.add("ignored text", unnamed=True)                       # unnamed wins: nothing invented or smuggled in
        self.assertEqual([r["label"] for r in Checkpoints(self.service).as_dict()["items"]], ["Drop", "", ""])
        self.assertEqual(marks.undo()["id"], 3)

    def test_empty_label_is_refused_and_idle_marks_stay_in_memory(self):
        from kaist_ground_station.web.checkpoints import Checkpoints
        marks = Checkpoints(self.service)
        with self.assertRaises(ValueError):
            marks.add("   ")
        marks.add("before connecting")                        # no session folder yet
        self.assertEqual(marks.as_dict()["saved"], False)
        self.assertEqual(len(marks.as_dict()["items"]), 1)

    def test_new_session_starts_a_new_list(self):
        from kaist_ground_station.web.checkpoints import Checkpoints
        self.live()
        marks = Checkpoints(self.service)
        marks.add("one")
        self.service.stop()
        self.live()                                                           # new recording folder
        self.assertEqual(marks.as_dict()["items"], [])

    def test_http_action_round_trip(self):
        server = WebServer(self.service, port=0)
        server.start()
        self.addCleanup(server.stop)
        base = server.url.rstrip("/")
        self.assertEqual(post(base + "/api/action", {"name": "connect", "port": "recorded", "baud": 115200})[0], 200)
        self.assertEqual(post(base + "/api/action", {"name": "checkpoint", "label": "Drop"})[0], 200)
        state = json.loads(get(base + "/api/state")[1])
        self.assertEqual([c["label"] for c in state["checkpoints"]["items"]], ["Drop"])
        self.assertTrue(state["checkpoints"]["saved"])
        self.assertEqual(post(base + "/api/action", {"name": "checkpoint", "label": ""})[0], 400)
        self.assertEqual(post(base + "/api/action", {"name": "checkpoint_mark"})[0], 200)
        items = json.loads(get(base + "/api/state")[1])["checkpoints"]["items"]
        self.assertEqual([c["label"] for c in items], ["Drop", ""])
        self.assertEqual(post(base + "/api/action", {"name": "checkpoint_undo"})[0], 200)
        self.assertEqual(post(base + "/api/action", {"name": "checkpoint_undo"})[0], 200)
        self.assertEqual(json.loads(get(base + "/api/state")[1])["checkpoints"]["items"], [])


class AngularRateTests(unittest.TestCase):
    def snap(self, ts, angles, count):
        from types import SimpleNamespace
        tel = SimpleNamespace(imu=angles, atlm=(), counts={"IMU": count}, seen={"IMU": ts})
        return SimpleNamespace(telemetry=tel, now=ts + 0.07)      # poll time deliberately differs from arrival time

    def test_rate_uses_frame_arrival_time_and_unwraps_the_180_boundary(self):
        from kaist_ground_station.web.history import History
        h = History()
        h.update(self.snap(10.0, (179.0, 0.0, 10.0), 1))
        h.update(self.snap(11.0, (-179.0, 5.0, 8.0), 2))           # +2 deg across the boundary, not -358
        _, wx, wy, wz = h.omega[-1]
        self.assertAlmostEqual(wx, 2.0)
        self.assertAlmostEqual(wy, 5.0)
        self.assertAlmostEqual(wz, -2.0)
        self.assertEqual(h.omega[-1][0], 11.0)

    def test_repeated_poll_of_the_same_frame_adds_nothing(self):
        from kaist_ground_station.web.history import History
        h = History()
        h.update(self.snap(10.0, (0.0, 0.0, 0.0), 1))
        for _ in range(3):
            h.update(self.snap(11.0, (1.0, 0.0, 0.0), 2))
        self.assertEqual(len(h.imu), 2)
        self.assertEqual(len(h.omega), 1)


class AutodetectTests(unittest.TestCase):
    def ports(self, *rows):
        from types import SimpleNamespace
        return [SimpleNamespace(device=d, description=desc, vid=vid) for d, desc, vid in rows]

    def test_usb_serial_beats_everything_and_legacy_uarts_are_dropped(self):
        from unittest import mock
        from kaist_ground_station import autodetect
        listed = self.ports(("/dev/ttyS31", "n/a", None), ("/dev/ttyS0", "n/a", None), ("/dev/rfcomm0", "n/a", None),
                            ("/dev/ttyUSB0", "FT232R USB UART", 0x0403), ("/dev/ttyAMA0", "n/a", None))
        with mock.patch("serial.tools.list_ports.comports", return_value=listed):
            ranked = [d for d, _ in autodetect.ranked_ports()]
            self.assertEqual(ranked, ["/dev/ttyUSB0", "/dev/rfcomm0", "/dev/ttyAMA0"])
            self.assertEqual(autodetect.detect_port(), "/dev/ttyUSB0")

    def test_nothing_plugged_in_means_none_not_a_guess(self):
        from unittest import mock
        from kaist_ground_station import autodetect
        with mock.patch("serial.tools.list_ports.comports", return_value=self.ports(("/dev/ttyS3", "n/a", None))):
            self.assertIsNone(autodetect.detect_port())

    def test_cli_port_auto_fails_clearly_when_nothing_is_found(self):
        from unittest import mock
        from kaist_ground_station import __main__ as cli
        with mock.patch("kaist_ground_station.autodetect.detect_port", return_value=None):
            with self.assertRaises(SystemExit) as ctx:
                cli.main(["--port", "auto", "--headless", "--duration", "1"])
            self.assertEqual(ctx.exception.code, 2)


class BluetoothAdapterTests(unittest.TestCase):
    """The USB adapter dials the satellite with AT lines; the buttons must not leave TX switched on."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.written = []
        outer = self

        class Link:
            def __init__(self, port, baud): pass
            def read(self): return b""
            def write(self, data): outer.written.append(data)
            def close(self): pass

        from kaist_ground_station.service import StationService
        from kaist_ground_station.ui_settings import UISettings
        self.service = StationService(Path(self.tmp.name), transport_factory=Link)
        self.addCleanup(self.service.stop)
        self.settings = UISettings(bluetooth_address="0001958D78EC")

    def server(self):
        server = WebServer(self.service, self.settings, port=0)
        server.start()
        self.addCleanup(server.stop)
        return server.url.rstrip("/")

    def test_dial_sends_exactly_the_atd_line_then_puts_tx_back(self):
        base = self.server()
        self.service.connect("fake")
        self.assertFalse(self.service.tx_enabled)
        self.assertEqual(post(base + "/api/action", {"name": "bt_connect"})[0], 200)
        self.assertEqual(self.written, [b"ATD0001958D78EC\r\n"])
        self.assertFalse(self.service.tx_enabled)                    # was off before, off after
        self.assertEqual(post(base + "/api/action", {"name": "bt_scan"})[0], 200)
        self.assertEqual(self.written[-1], b"AT+BTINQ?\r\n")

    def test_tx_that_the_operator_already_enabled_stays_enabled(self):
        base = self.server()
        self.service.connect("fake")
        self.service.enable_transmit(True)
        post(base + "/api/action", {"name": "bt_connect"})
        self.assertTrue(self.service.tx_enabled)

    def test_refused_without_a_live_session_or_an_address(self):
        base = self.server()
        code, reply = post(base + "/api/action", {"name": "bt_connect"})   # not connected yet
        self.assertEqual(code, 400)
        self.assertEqual(self.written, [])
        self.service.connect("fake")
        self.settings.bluetooth_address = ""
        code, reply = post(base + "/api/action", {"name": "bt_connect"})
        self.assertEqual(code, 400)
        self.assertIn("address", reply["error"])
        self.assertEqual(self.written, [])


class AutoDialTests(unittest.TestCase):
    def test_start_up_dial_goes_out_over_a_real_serial_device_once(self):
        import os, tempfile
        from kaist_ground_station.service import StationService
        from kaist_ground_station.transport import SerialTransport
        from kaist_ground_station.ui_settings import UISettings
        from kaist_ground_station.web.server import auto_dial
        master, slave = os.openpty()
        self.addCleanup(os.close, master)
        with tempfile.TemporaryDirectory() as tmp:
            service = StationService(Path(tmp), transport_factory=SerialTransport)
            service.connect(os.ttyname(slave))
            self.addCleanup(service.stop)

            def server_with(**kw):
                server = WebServer(service, UISettings(**kw), port=0)
                self.addCleanup(server.httpd.server_close)
                return server

            self.assertIsNone(auto_dial(server_with(bluetooth_address="0001958D78EC", bluetooth_auto=False), wait=0))   # opt-in
            self.assertEqual(auto_dial(server_with(bluetooth_address="0001958D78EC", bluetooth_auto=True), wait=0), "ATD0001958D78EC")
            self.assertEqual(os.read(master, 100), b"ATD0001958D78EC\r\n")
            self.assertFalse(service.tx_enabled)
            self.assertIsNone(auto_dial(server_with(bluetooth_auto=True), wait=0))        # no address: nothing sent

    def test_not_live_means_nothing_is_sent(self):
        import tempfile
        from kaist_ground_station.service import StationService
        from kaist_ground_station.ui_settings import UISettings
        from kaist_ground_station.web.server import auto_dial
        with tempfile.TemporaryDirectory() as tmp:
            service = StationService(Path(tmp))
            service.start_replay(DEMO_RECORDING)
            self.addCleanup(service.stop)
            server = WebServer(service, UISettings(bluetooth_address="0001958D78EC", bluetooth_auto=True), port=0)
            self.addCleanup(server.httpd.server_close)
            self.assertIsNone(auto_dial(server, wait=0))


class TerminalTextTests(unittest.TestCase):
    def entry(self, raw: bytes):
        return [1.0, raw.hex(" "), ""]

    def test_adapter_replies_are_kept(self):
        from kaist_ground_station.web.serialize import text_lines
        got = text_lines([self.entry(b"OK\r\n"), self.entry(b"+BTINQ: 0001958D78EC,KAIST,1F00\r\nOK\r\n"), self.entry(b"CONNECT 0001958D78EC\r\n")])
        self.assertEqual([l for _, l in got], ["OK", "+BTINQ: 0001958D78EC,KAIST,1F00", "OK", "CONNECT 0001958D78EC"])

    def test_telemetry_frames_and_their_fragments_are_not_text(self):
        from kaist_ground_station.web.serialize import text_lines
        lines = DEMO_RECORDING.read_text().splitlines()[:40]                   # real telemetry frames, as recorded
        stream = b"".join(bytes.fromhex(json.loads(l)["hex"]) for l in lines)
        chunks = [self.entry(stream[i:i + 200]) for i in range(0, len(stream), 200)]    # chunks cut mid-frame, like a serial read
        self.assertEqual(text_lines(chunks), [])

    def test_bad_hex_and_noise_never_raise(self):
        from kaist_ground_station.web.serialize import text_lines
        self.assertEqual(text_lines([[1.0, "zz", ""], self.entry(b"\x00\x01\x02\r\n"), self.entry(b"")]), [])


class ConnectButtonDialsTests(unittest.TestCase):
    def run_connect(self, **settings):
        import os, tempfile, time
        from kaist_ground_station.service import StationService
        from kaist_ground_station.transport import SerialTransport
        from kaist_ground_station.ui_settings import UISettings
        master, slave = os.openpty()
        self.addCleanup(os.close, master)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        service = StationService(Path(tmp.name), transport_factory=SerialTransport)
        self.addCleanup(service.stop)
        server = WebServer(service, UISettings(**settings), port=0)
        server.start()
        self.addCleanup(server.stop)
        code, _ = post(server.url.rstrip("/") + "/api/action", {"name": "connect", "port": os.ttyname(slave), "baud": 115200})
        self.assertEqual(code, 200)
        time.sleep(1.4)                                           # auto_dial waits 0.5 s for the adapter
        os.set_blocking(master, False)
        try:
            return os.read(master, 100), service
        except BlockingIOError:
            return b"", service

    def test_connect_also_dials_when_configured(self):
        sent, service = self.run_connect(bluetooth_address="0001958D78EC", bluetooth_auto=True)
        self.assertEqual(sent, b"ATD0001958D78EC\r\n")
        self.assertFalse(service.tx_enabled)

    def test_connect_only_opens_the_port_when_auto_connect_is_off(self):
        sent, service = self.run_connect(bluetooth_address="0001958D78EC", bluetooth_auto=False)
        self.assertEqual(sent, b"")
        self.assertEqual(service.mode, "LIVE")


class RecordButtonTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from kaist_ground_station.service import StationService
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = [100.0]
        self.service = StationService(Path(self.tmp.name), auto_record=False, clock=lambda: self.now[0],
                                      transport_factory=lambda port, baud: RecordedKit(lambda: self.now[0]))
        self.addCleanup(self.service.stop)
        server = WebServer(self.service, port=0)
        server.start()
        self.addCleanup(server.stop)
        self.base = server.url.rstrip("/")

    def state(self):
        return json.loads(get(self.base + "/api/state")[1])

    def act(self, **body):
        return post(self.base + "/api/action", body)

    def test_state_says_whether_a_session_is_being_kept(self):
        self.act(name="connect", port="recorded", baud=115200)
        self.assertEqual(self.state()["recording"], {"on": False, "elapsed": None})
        self.assertEqual(self.state()["log_directory"], "")
        self.assertEqual(self.act(name="record_start")[0], 200)
        rec = self.state()["recording"]
        self.assertTrue(rec["on"])
        self.assertGreaterEqual(rec["elapsed"], 0)
        self.assertNotEqual(self.state()["log_directory"], "")
        self.assertEqual(self.act(name="record_stop")[0], 200)
        self.assertFalse(self.state()["recording"]["on"])

    def test_misuse_is_a_400_with_the_reason(self):
        code, reply = self.act(name="record_start")                # no session yet
        self.assertEqual(code, 400)
        self.assertIn("session", reply["error"])
        self.act(name="connect", port="recorded", baud=115200)
        code, reply = self.act(name="record_stop")
        self.assertEqual(code, 400)
        self.assertIn("Not recording", reply["error"])

    def test_marks_made_before_recording_move_into_the_recording(self):
        from kaist_ground_station.web.checkpoints import FILENAME
        self.act(name="connect", port="recorded", baud=115200)
        self.act(name="checkpoint", label="Drone ascent start")           # nothing is being kept yet
        self.assertFalse(self.state()["checkpoints"]["saved"])
        self.act(name="record_start")
        marks = self.state()["checkpoints"]
        self.assertTrue(marks["saved"])
        self.assertEqual([c["label"] for c in marks["items"]], ["Drone ascent start"])   # not dropped
        lines = (Path(self.service.log_directory) / FILENAME).read_text().splitlines()
        self.assertEqual(json.loads(lines[0])["before_recording"], True)
        self.act(name="checkpoint", label="Drop")                          # now saved immediately
        self.assertEqual([c["label"] for c in self.state()["checkpoints"]["items"]], ["Drone ascent start", "Drop"])


class ReplayCheckpointTests(unittest.TestCase):
    """Replaying a recorded session shows the marks that were made during it, as the replay reaches them."""

    def make_session(self, root):
        from datetime import datetime, timedelta, timezone
        from kaist_ground_station.service import StationService
        from kaist_ground_station.web.checkpoints import FILENAME
        now = [0.0]
        s = StationService(root / "rec", clock=lambda: now[0])
        s.start_replay(DEMO_RECORDING)
        for _ in range(80):
            now[0] += 0.25
            s.tick()
        s.stop()
        (folder,) = (root / "rec").iterdir()
        meta = json.loads((folder / "session.json").read_text())
        t0 = datetime.strptime(meta["started_utc"], "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=timezone.utc)
        rows = [{"id": 1, "label": "Drone ascent start", "utc": (t0 + timedelta(seconds=4)).isoformat(), "service_t": 0, "alt_m": 120.0},
                {"id": 2, "label": "Drop", "utc": (t0 + timedelta(seconds=10)).isoformat(), "service_t": 0, "alt_m": 130.0},
                {"id": 3, "label": "", "utc": (t0 + timedelta(seconds=15)).isoformat(), "service_t": 0, "alt_m": 140.0},
                {"undo": 3, "utc": (t0 + timedelta(seconds=16)).isoformat()}]
        (folder / FILENAME).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        return folder

    def test_marks_appear_when_the_replay_reaches_them_and_undone_ones_never_do(self):
        import tempfile
        from kaist_ground_station.service import StationService
        from kaist_ground_station.web.checkpoints import Checkpoints
        with tempfile.TemporaryDirectory() as tmp:
            folder = self.make_session(Path(tmp))
            now = [500.0]
            replay = StationService(Path(tmp) / "again", clock=lambda: now[0], auto_record=False)
            self.addCleanup(replay.stop)
            replay.start_replay(folder / "traffic.jsonl")
            marks = Checkpoints(replay)

            def step(seconds):
                for _ in range(int(seconds / 0.25)):
                    now[0] += 0.25
                    replay.tick()
                return marks.as_dict()

            first = step(2)
            self.assertEqual((first["items"], first["replay"]), ([], True))               # not reached yet
            self.assertEqual([m["label"] for m in step(3)["items"]], ["Drone ascent start"])   # t = 5 s
            got = step(7)                                                                   # t = 12 s
            self.assertEqual([m["label"] for m in got["items"]], ["Drone ascent start", "Drop"])
            # placed on the replay clock: replay start + offset
            self.assertAlmostEqual(got["items"][1]["service_t"], replay.started + 10.0, places=3)
            done = step(5)                                                                  # t = 17 s: the undone mark never shows
            self.assertEqual([m["id"] for m in done["items"]], [1, 2])

    def test_marks_cannot_be_added_or_undone_during_a_replay(self):
        import tempfile
        from kaist_ground_station.service import StationService
        from kaist_ground_station.web.checkpoints import Checkpoints
        with tempfile.TemporaryDirectory() as tmp:
            folder = self.make_session(Path(tmp))
            replay = StationService(Path(tmp) / "again", auto_record=False)
            self.addCleanup(replay.stop)
            replay.start_replay(folder / "traffic.jsonl")
            marks = Checkpoints(replay)
            for call in (lambda: marks.add("Drop"), lambda: marks.add(unnamed=True), marks.undo):
                with self.assertRaises(ValueError):
                    call()
            self.assertEqual(len((folder / "checkpoints.jsonl").read_text().splitlines()), 4)   # the recording is untouched

    def test_a_session_without_marks_or_metadata_just_shows_nothing(self):
        import tempfile
        from kaist_ground_station.service import StationService
        from kaist_ground_station.web.checkpoints import Checkpoints, FILENAME
        with tempfile.TemporaryDirectory() as tmp:
            folder = self.make_session(Path(tmp))
            (folder / FILENAME).unlink()
            replay = StationService(Path(tmp) / "again", auto_record=False)
            self.addCleanup(replay.stop)
            replay.start_replay(folder / "traffic.jsonl")
            self.assertEqual(Checkpoints(replay).as_dict()["items"], [])
            (folder / "session.json").write_text("not json")
            (folder / FILENAME).write_text('{"id": 1, "label": "x", "utc": "2026-10-27T00:00:00+00:00"}\n')
            self.assertEqual(Checkpoints(replay).as_dict()["items"], [])


class ReplayEndKeepsMarksTests(unittest.TestCase):
    def test_marks_stay_after_the_replay_finishes_and_leave_when_a_new_session_starts(self):
        import tempfile
        from kaist_ground_station.service import StationService
        from kaist_ground_station.web.checkpoints import Checkpoints
        with tempfile.TemporaryDirectory() as tmp:
            folder = ReplayCheckpointTests().make_session(Path(tmp))
            now = [500.0]
            replay = StationService(Path(tmp) / "again", clock=lambda: now[0], auto_record=False)
            self.addCleanup(replay.stop)
            replay.start_replay(folder / "traffic.jsonl")
            marks = Checkpoints(replay)
            while replay.mode == "REPLAY":
                now[0] += 0.25
                replay.tick()
            self.assertEqual(replay.mode, "IDLE")                          # the replay is over ...
            shown = marks.as_dict()
            self.assertTrue(shown["replay"])
            self.assertEqual([m["id"] for m in shown["items"]], [1, 2])    # ... and its marks are still there
            with self.assertRaises(ValueError):
                marks.add("Drop")                                          # still read-only while that session is on screen
            now[0] += 3600                                                 # an hour later they are still there
            self.assertEqual(len(marks.as_dict()["items"]), 2)
            replay.transport_factory = lambda port, baud: RecordedKit(lambda: now[0])
            replay.connect("recorded", 115200)                                             # a new session replaces them
            after = marks.as_dict()
            self.assertEqual((after["items"], after.get("replay")), ([], None))


class FrozenViewTests(unittest.TestCase):
    """After Stop / end of replay the charts must hold still: they are drawn against view_now, not the live clock."""

    def test_view_now_follows_the_clock_while_running_and_stops_when_the_session_ends(self):
        import tempfile
        from kaist_ground_station.service import StationService
        now = [100.0]
        with tempfile.TemporaryDirectory() as tmp:
            service = StationService(Path(tmp), clock=lambda: now[0], auto_record=False)
            self.addCleanup(service.stop)
            server = WebServer(service, port=0)
            self.addCleanup(server.httpd.server_close)
            state = lambda: json.loads(server.state_json)
            service.start_replay(DEMO_RECORDING)
            for _ in range(8):
                now[0] += 0.5
                server._publish()
            running = state()
            self.assertEqual(running["view_now"], running["now"])                    # live: follows the clock
            service.stop()
            server._publish()
            stopped_at = state()["view_now"]
            now[0] += 120                                                            # two minutes pass
            server._publish()
            later = state()
            self.assertGreater(later["now"], stopped_at + 100)
            self.assertEqual(later["view_now"], stopped_at)                          # the picture did not move
            self.assertAlmostEqual(stopped_at, running["now"], delta=0.6)            # and froze at the end, not at zero
            service.start_replay(DEMO_RECORDING)                                                     # a new session resumes the clock
            now[0] += 1
            server._publish()
            self.assertEqual(state()["view_now"], state()["now"])

    def test_last_frame_time_is_published_so_its_age_can_be_frozen_too(self):
        import tempfile
        from kaist_ground_station.service import StationService
        now = [100.0]
        with tempfile.TemporaryDirectory() as tmp:
            service = StationService(Path(tmp), clock=lambda: now[0], auto_record=False)
            self.addCleanup(service.stop)
            server = WebServer(service, port=0)
            self.addCleanup(server.httpd.server_close)
            service.start_replay(DEMO_RECORDING)
            for _ in range(6):
                now[0] += 0.5
                server._publish()
            state = json.loads(server.state_json)
            self.assertAlmostEqual(state["last_frame_t"], state["now"] - state["link_age_s"])
