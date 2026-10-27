import json
from pathlib import Path
import tempfile
import unittest
import urllib.request

from kaist_ground_station.frontends import FRONTENDS, load_frontend
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
        self.service.start_demo()
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
        self.assertEqual(post(base + "/api/action", {"name": "demo"})[0], 200)
        self.assertEqual(json.loads(get(base + "/api/state")[1])["mode"], "DEMO")
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
            service.start_demo()
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
        self.service = StationService(Path(self.tmp.name), clock=lambda: self.now[0])
        self.addCleanup(self.service.stop)

    def test_records_time_and_flight_state_and_persists_in_the_session_folder(self):
        from kaist_ground_station.web.checkpoints import Checkpoints, FILENAME
        self.service.start_demo()
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
        self.service.start_demo()
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
        self.service.start_demo()
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
        self.service.start_demo()
        marks = Checkpoints(self.service)
        marks.add("one")
        self.service.stop()
        self.service.start_demo()                             # new recording folder
        self.assertEqual(marks.as_dict()["items"], [])

    def test_http_action_round_trip(self):
        server = WebServer(self.service, port=0)
        server.start()
        self.addCleanup(server.stop)
        base = server.url.rstrip("/")
        self.assertEqual(post(base + "/api/action", {"name": "demo"})[0], 200)
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
