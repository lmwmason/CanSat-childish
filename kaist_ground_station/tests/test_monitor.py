import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kaist_ground_station.tools.monitor import ModemConnection, MonitorService, run, remote_address, status_line
from kaist_ground_station.tests.test_protocol import ATLM, GPS, IMU
from kaist_ground_station.tests.test_service import Clock, FakePort


class MonitorTests(unittest.TestCase):
    def test_query_then_dial_requires_connect_or_new_telemetry(self):
        writes=[]
        m=ModemConnection(writes.append)
        m.tick(0);m.tick(1.5)
        self.assertEqual(writes,['AT+BTINFO?'])
        m.feed(b'000195000000,SD1000U,MODE0,STANDBY,0,0,NoFC\r\n')
        m.tick(2)
        self.assertEqual(writes[-1],'ATD')
        m.feed(b'\r\nOK\r\n');m.tick(3)
        self.assertEqual(m.state,'DIALING')
        m.feed(b'\r\nCON');m.tick(4)
        m.feed(b'NECT 000195123456\r\n');m.tick(5)
        self.assertEqual(m.state,'CONNECTED')

    def test_retry_does_not_mistake_old_packets_for_reconnection(self):
        writes=[];m=ModemConnection(writes.append)
        m.tick(0,valid_frames=5)
        self.assertEqual(writes,[])
        m.feed(b'\r\nDISCON');m.tick(1,valid_frames=5)
        m.feed(b'NECT\r\n');m.tick(2,valid_frames=5)
        self.assertEqual(m.state,'RETRY')
        m.tick(3,valid_frames=5)
        self.assertEqual(m.state,'RETRY')
        m.tick(7,valid_frames=5)
        self.assertEqual(writes,['ATD'])
        m.feed(b'\r\nERROR\r\n');m.tick(8,valid_frames=5)
        m.tick(13,valid_frames=5)
        self.assertEqual(writes,['ATD','ATD'])

    def test_no_dial_never_sends_and_pending_does_not_redial(self):
        writes=[];m=ModemConnection(writes.append,enabled=False)
        m.feed(b'\r\nERROR\r\n')
        for t in (0,2,100):m.tick(t)
        self.assertEqual(writes,[])
        m=ModemConnection(writes.append,remote='000195123456')
        m.tick(0);m.tick(2)
        m.feed(b',STANDBY,');m.tick(3)
        self.assertEqual(writes[-1],'ATD000195123456')
        m.tick(100)
        self.assertEqual(writes.count('ATD000195123456'),1)

    def test_status_distinguishes_modem_ok_from_real_packets(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock=Clock();port=FakePort()
            service=MonitorService(Path(tmp),clock=clock,transport_factory=lambda *_:port)
            try:
                service.connect('fake')
                modem=ModemConnection(lambda _:None)
                port.incoming=b'\r\nOK\r\nCONNECT 000195123456\r\n'
                service.tick()
                self.assertNotIn('실시간 수신 중',status_line(service.snapshot(),modem,(0,0)))
                port.incoming=ATLM+GPS;service.tick()
                self.assertIn('실시간 수신 중',status_line(service.snapshot(),modem,(0,0)))
                clock.now=10
                self.assertIn('수신 지연/끊김',status_line(service.snapshot(),modem,(0,0)))
            finally:service.stop()

    def test_cli_handshake_capture_summary_and_only_modem_writes(self):
        class ModemPort(FakePort):
            def write(self,data):
                super().write(data)
                if data==b'AT+BTINFO?\r\n':self.incoming=b'001234000000,SD1000U,MODE0,STANDBY,0,0,NoFC\r\n'
                elif data==b'ATD\r\n':self.incoming=b'\r\nOK\r\nCONNECT 000195123456\r\n'+ATLM+GPS+IMU
        with tempfile.TemporaryDirectory() as tmp:
            clock=Clock();port=ModemPort()
            service=MonitorService(Path(tmp),clock=clock,transport_factory=lambda *_:port)
            args=argparse.Namespace(port='fake',baud=115200,remote=None,no_dial=False,interval=.2,
                                    stale_seconds=5,duration=3,log_dir=Path(tmp))
            def sleep(seconds):clock.now+=seconds
            with patch('kaist_ground_station.tools.monitor.time.monotonic',clock),contextlib.redirect_stdout(io.StringIO()) as output:
                result=run(args,service=service,sleep=sleep)
            self.assertEqual(result,0)
            self.assertEqual(port.writes,[b'AT+BTINFO?\r\n',b'ATD\r\n'])
            self.assertIn('실시간 수신 중',output.getvalue())
            folder=Path(service.log_directory)
            report=json.loads((folder/'monitor_summary.json').read_text())
            self.assertEqual(report['valid_frames'],3)
            self.assertEqual(report['parser_errors'],0)
            self.assertTrue(port.closed)

    def test_remote_address_validation(self):
        self.assertEqual(remote_address('00:01:95:8d:78:ec'),'0001958D78EC')
        for value in ('ATD\r','xyz','0001'):
            with self.assertRaises(argparse.ArgumentTypeError):remote_address(value)
