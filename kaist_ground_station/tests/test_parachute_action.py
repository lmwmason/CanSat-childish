"""Exercise the one-click deployment without opening hardware or a server."""
import unittest
from unittest.mock import Mock
from kaist_ground_station.web.server import WebServer


class ParachuteActionTests(unittest.TestCase):
    def make_server(self, enabled=False):
        server = object.__new__(WebServer)
        server.service = Mock(mode='LIVE', tx_enabled=enabled)
        server.checkpoints = Mock()
        return server

    def test_sends_once_marks_and_restores_tx(self):
        for enabled in (False, True):
            server = self.make_server(enabled)
            server._parachute_open()
            server.service.send_command.assert_called_once_with(71, 180)
            server.checkpoints.add.assert_called_once_with('Parachute open')
            self.assertEqual(server.service.enable_transmit.call_args.args, (enabled,))

    def test_failed_send_does_not_mark_or_leave_tx_enabled(self):
        server = self.make_server()
        server.service.send_command.side_effect = OSError('write failed')
        with self.assertRaises(OSError):
            server._parachute_open()
        server.checkpoints.add.assert_not_called()
        self.assertEqual(server.service.enable_transmit.call_args.args, (False,))

    def test_replay_cannot_send(self):
        server = self.make_server()
        server.service.mode = 'REPLAY'
        server.service.enable_transmit.side_effect = lambda value: (_ for _ in ()).throw(ValueError('not live')) if value else None
        with self.assertRaises(ValueError):
            server._parachute_open()
        server.service.send_command.assert_not_called()
        server.checkpoints.add.assert_not_called()
