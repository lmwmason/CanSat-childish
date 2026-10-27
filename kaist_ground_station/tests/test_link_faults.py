"""Backend-only fault injection. Does not import or modify any frontend."""
import random
import unittest

from kaist_ground_station.protocol import StreamParser, xor8
from kaist_ground_station.tests.test_protocol import ATLM, DTLM, GPS, IMU


def gps_with_fields(**changes):
    fields = [b'GPGGA', b'123519', b'4807.038', b'N', b'01131.000', b'E',
              b'1', b'08', b'0.9', b'545.4', b'M', b'46.9', b'M', b'', b'']
    for index,value in changes.items():
        fields[int(index)] = value
    body = b','.join(fields)
    return b'\x76\x00\x58\x00$' + body + f'*{xor8(body):02X}\r\n'.encode()


class LinkFaultTests(unittest.TestCase):
    def test_short_modem_noise_is_discarded_without_false_frame_timeout(self):
        for noise in (b'\r\n',b'\0\n',b'\n'):
            parser=StreamParser()
            self.assertEqual(parser.feed(noise,0),[])
            self.assertEqual(parser.expire(10),[])
            self.assertEqual(parser.errors,0)
            self.assertEqual(parser.discarded,len(noise))
        parser=StreamParser()
        self.assertEqual(parser.feed(b'\nv'),[])
        self.assertEqual(parser.feed(ATLM[1:])[0].kind,'ATLM')

    def test_real_kit_repeated_gps_checksum_keeps_no_fix_valid(self):
        raw = b'\x76\0\x58\0$GPGGA,,,,,,0,00,99.99,,,,,,*48\r*48\r\n'
        for split in range(len(raw)+1):
            parser = StreamParser()
            frames = parser.feed(raw[:split])+parser.feed(raw[split:])
            self.assertEqual(len(frames),1)
            frame=frames[0]
            self.assertEqual(frame.kind,'GPS')
            self.assertEqual(frame.data['fix'],0)
            self.assertIsNone(frame.data['lat'])
            self.assertEqual(frame.data['checksum_envelope'],'repeated_after_cr')
            self.assertEqual(frame.raw,raw)
        for broken in (raw.replace(b'\r*48',b'\r*49'),raw.replace(b'*48',b'*49')):
            self.assertEqual(StreamParser().feed(broken)[0].kind,'ERROR')

    def test_real_kit_lifesign_and_camera_ack_are_frames(self):
        raw=bytes.fromhex('76 00 4c 09 ff fd 8a c6 00 00 00 59 17 76 00 36 00 00')
        for split in range(len(raw)+1):
            parser=StreamParser()
            frames=parser.feed(raw[:split])+parser.feed(raw[split:])
            self.assertEqual([f.kind for f in frames],['LIFESIGN','CAMERA_ACK'])
            self.assertEqual(frames[0].data['uptime_s'],89)
            self.assertIsNone(frames[1].checksum)
        broken=bytearray(raw[:13]);broken[-1]^=1
        self.assertEqual(StreamParser().feed(bytes(broken))[0].kind,'ERROR')

    def test_invalid_hemispheres_cannot_create_false_coordinates(self):
        for field in ('3', '5'):
            for value in (b'', b'NS', b'EW', b' ', b'X'):
                with self.subTest(field=field,value=value):
                    parser = StreamParser()
                    events = parser.feed(gps_with_fields(**{field:value})+ATLM)
                    self.assertEqual([f.kind for f in events], ['ERROR','ATLM'])
        frame = StreamParser().feed(gps_with_fields(**{'3':b'S','5':b'W'}))[0]
        self.assertAlmostEqual(frame.data['lat'], -48.1173)
        self.assertAlmostEqual(frame.data['lon'], -11.5166666667)

    def test_random_serial_read_boundaries_preserve_frames(self):
        rng = random.Random(20261027)
        stream = (ATLM+DTLM+GPS+IMU)*30
        expected = [(f.kind,f.raw) for f in StreamParser().feed(stream)]
        for trial in range(100):
            parser = StreamParser()
            actual = []
            pos = 0
            while pos < len(stream):
                length = rng.randint(1,257)
                actual.extend((f.kind,f.raw) for f in parser.feed(stream[pos:pos+length]))
                pos += length
            self.assertEqual(actual,expected,trial)
            self.assertEqual(parser.errors,0)
            self.assertEqual(parser.buffer,b'')

    def test_each_single_bit_error_in_checked_analog_payload_is_rejected(self):
        for index in range(4,len(ATLM)):
            for bit in range(8):
                broken = bytearray(ATLM)
                broken[index] ^= 1 << bit
                parser = StreamParser()
                frames = parser.feed(bytes(broken)+GPS)
                self.assertFalse(any(f.kind=='ATLM' for f in frames),(index,bit))
                self.assertEqual(frames[-1].kind,'GPS')
                self.assertGreater(parser.errors,0)

    def test_deleted_analog_byte_recovers_next_packet(self):
        for index in range(len(ATLM)):
            parser = StreamParser()
            damaged = ATLM[:index]+ATLM[index+1:]
            frames = parser.feed(damaged+GPS)
            self.assertEqual(frames[-1].kind,'GPS',index)
            self.assertFalse(any(f.kind=='ATLM' for f in frames),index)
