"""Regression checks for session changes, recording toggles and camera refresh."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from kaist_ground_station.protocol import Frame
from kaist_ground_station.service import StationService
from kaist_ground_station.tests.test_service import Clock, FakePort
from kaist_ground_station.web.checkpoints import Checkpoints, FILENAME
from kaist_ground_station.web.history import History
from kaist_ground_station.web.serialize import state_dict


class SessionStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = Clock()
        self.service = StationService(Path(self.tmp.name), clock=self.clock,
                                      transport_factory=lambda *_: FakePort(), auto_record=False)
        self.addCleanup(self.service.stop)

    def sample(self, value):
        self.service.telemetry.apply(Frame("IMU", {"values": [value, 0, 0]}, b""), self.clock())
        self.service.telemetry.apply(Frame("ATLM", {"raw": [value]*8}, b""), self.clock())

    def test_reconnect_same_port_same_clock_resets_history_and_keeps_first_frame(self):
        s, history = self.service, History()
        s.connect("same-port")
        self.sample(10)
        history.update(s.snapshot())
        s.connect("same-port")        # even identical source and clock identify a new session
        self.sample(80)
        history.update(s.snapshot())
        self.assertEqual(list(history.imu), [[self.clock(), 80, 0, 0]])
        self.assertEqual(list(history.atlm), [[self.clock(), *([80]*8)]])
        self.assertEqual(list(history.omega), [])
        self.clock.now += 1
        self.sample(85)
        history.update(s.snapshot())
        self.assertEqual(history.omega[-1][1], 5)

    def test_stop_preserves_history_but_a_new_empty_session_clears_it(self):
        s, history = self.service, History()
        s.connect("A"); self.sample(10); history.update(s.snapshot())
        s.stop(); history.update(s.snapshot())
        self.assertEqual(len(history.imu), 1)
        s.connect("B"); history.update(s.snapshot())
        self.assertEqual(history.as_dict(), {"imu": [], "omega": [], "atlm": []})

    def test_record_toggles_preserve_marks_and_copy_them_to_the_new_recording(self):
        s, marks = self.service, Checkpoints(self.service)
        s.connect("A"); marks.add("Ascent")
        s.start_recording()
        self.assertEqual(len(marks.as_dict()["items"]), 1)
        folder1 = Path(s.log_directory)
        marks.add("Drop")
        original = (folder1/FILENAME).read_bytes()
        s.stop_recording()
        self.assertEqual([m["label"] for m in marks.as_dict()["items"]], ["Ascent", "Drop"])
        self.assertFalse(marks.as_dict()["saved"])
        marks.add("Landing")
        self.assertEqual((folder1/FILENAME).read_bytes(), original)   # stopped recordings are untouched
        s.start_recording()
        folder2 = Path(s.log_directory)
        self.assertEqual([m["label"] for m in marks.as_dict()["items"]], ["Ascent", "Drop", "Landing"])
        rows = [json.loads(line) for line in (folder2/FILENAME).read_text().splitlines()]
        self.assertEqual([r["id"] for r in rows], [1, 2, 3])
        self.assertTrue(all(r["before_recording"] for r in rows))

    def test_switching_unrecorded_sessions_cannot_copy_old_marks_into_new_recording(self):
        s, marks = self.service, Checkpoints(self.service)
        s.connect("A"); marks.add("A-only")
        s.connect("B")
        self.assertEqual(marks.as_dict()["items"], [])
        marks.add("B-only"); s.start_recording()
        self.assertEqual([r["label"] for r in marks.as_dict()["items"]], ["B-only"])
        rows = [json.loads(line) for line in (Path(s.log_directory)/FILENAME).read_text().splitlines()]
        self.assertEqual([r["label"] for r in rows], ["B-only"])

    def test_camera_version_changes_on_equal_size_images_and_session_switch(self):
        s = self.service
        s.connect("A")
        def image(data):
            s.telemetry.apply(Frame("IMAGE", {"jpeg": data, "size": len(data)}, b""), self.clock())
            return state_dict(s.snapshot())
        first = image(b"jpeg-A")
        second = image(b"jpeg-B")
        self.assertEqual(first["jpeg_size"], second["jpeg_size"])
        self.assertNotEqual(first["jpeg_version"], second["jpeg_version"])
        self.assertEqual(second["jpeg_version"], state_dict(s.snapshot())["jpeg_version"])
        s.connect("A")
        third = image(b"jpeg-C")
        self.assertNotEqual(first["jpeg_version"], third["jpeg_version"])

    def test_web_publish_replaces_history_and_camera_payloads_on_new_session(self):
        from kaist_ground_station.web.server import WebServer
        s = self.service
        server = WebServer(s, port=0)
        self.addCleanup(server.httpd.server_close)
        def publish(port, value):
            s.connect(port)
            self.sample(value)
            s.telemetry.apply(Frame("IMAGE", {"jpeg": bytes([value])*6, "size": 6}, b""), self.clock())
            s.telemetry.apply(Frame("QLOOK", {"x": 0, "y": 0, "pixels": [value]}, b""), self.clock())
            server._publish()
            return json.loads(server.state_json), server.jpeg, server.qlook
        first, jpeg1, qlook1 = publish("A", 10)
        second, jpeg2, qlook2 = publish("B", 80)
        self.assertNotEqual(first["session_id"], second["session_id"])
        self.assertNotEqual(first["jpeg_version"], second["jpeg_version"])
        self.assertEqual(len(jpeg1), len(jpeg2))
        self.assertNotEqual(jpeg1, jpeg2)
        self.assertNotEqual(qlook1, qlook2)     # both sessions have qlook_version == 1
        self.assertEqual(second["history"]["imu"], [[self.clock(), 80, 0, 0]])

    @unittest.skipUnless(shutil.which("node"), "Node is needed to execute the shipped camera JavaScript")
    def test_shipped_camera_renderer_fetches_each_version_once(self):
        page = Path(__file__).resolve().parents[1]/"web/static/index.html"
        javascript = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.argv[1],'utf8');
const render=source.slice(source.indexOf('function renderCamera(s) {'),source.indexOf('function renderDriftTable'));
let jpegLoads=0,qlookLoads=0;const elements={};
const context={$:id=>elements[id]??={dataset:{},style:{},set src(value){
 if(id==='jpeg')jpegLoads++;if(id==='qlook')qlookLoads++;
}},ageOf:()=>0,t:()=>'',css:()=>''};
vm.createContext(context);vm.runInContext(render,context);
const frame={session_id:1,jpeg_size:12500,jpeg_version:'1:1',qlook_version:1};
context.renderCamera(frame);context.renderCamera({...frame,jpeg_version:'1:2'});
context.renderCamera({...frame,jpeg_version:'1:2'});
assert.equal(jpegLoads,2,'same-size new image must refresh; unchanged polls must not');
context.renderCamera({...frame,session_id:2,jpeg_version:'2:1'});
assert.equal(jpegLoads,3,'a new session must refresh even if its frame count matches');
assert.equal(qlookLoads,2,'QLOOK must also refresh across sessions');
"""
        result = subprocess.run([shutil.which("node"), "-e", javascript, str(page)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
