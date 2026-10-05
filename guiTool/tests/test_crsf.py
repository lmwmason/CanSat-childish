"""Contract test: frames produced by the REAL mother firmware (crsf_telemetry.c, built on a host
with fixed inputs) must decode to those inputs.  If you change the frame layout in the firmware,
regenerate these hex strings from its output and update the expected values.

Run:  .venv/bin/python -m unittest discover -s tests
"""
import unittest

from cansat_gui import crsf

# Inputs used when the vectors were generated (firmware side):
#   roll 12.5, pitch -7.25, yaw -170, lat 37.6166667, lon 127.0, speed 11 m/s, course 273.4,
#   alt 85.5, sats 9, mission SPIN(3), elevon AUTO(2), flags dropping|gps|wings|landed,
#   imu 2, accel 9.81, yaw rate -182.3, wheel -0.55, roll target -25, dist 123.4,
#   desired course 315, elevon 1259/1740 us
FIRMWARE_FRAMES = {
    0x1E: "c8081efb0f08868c19e5",
    0x02: "c81102166bd90b4bb2a980018c6acc043e09d8",
    0x21: "c811215350494e204155544f204c414e440017",
    0x7F: "c8197f010302170203d5f8e1c9e7007b0c4e04eb06cc000000962f",
}


def decode(*types):
    d = crsf.CrsfDecoder()
    for t in types:
        d.feed(bytes.fromhex(FIRMWARE_FRAMES[t]))
    return d.state


class FirmwareContract(unittest.TestCase):
    def test_attitude(self):
        s = decode(0x1E)
        self.assertAlmostEqual(s.roll, 12.5, 1)
        self.assertAlmostEqual(s.pitch, -7.25, 1)
        self.assertAlmostEqual(s.yaw, -170.0, 1)

    def test_gps(self):
        s = decode(0x02)
        self.assertAlmostEqual(s.lat, 37.6166667, 6)
        self.assertAlmostEqual(s.lon, 127.0, 6)
        self.assertAlmostEqual(s.speed, 11.0, 1)
        self.assertAlmostEqual(s.course, 273.4, 1)
        self.assertEqual(s.sats, 9)

    def test_mode_text(self):
        self.assertEqual(decode(0x21).mode_text, "SPIN AUTO LAND")

    def test_status(self):
        s = decode(0x7F)
        self.assertEqual((s.mission, s.elevon_mode, s.imu_count), (3, 2, 2))
        self.assertTrue(s.flag(crsf.FLAG_DROPPING) and s.flag(crsf.FLAG_LANDED) and s.flag(crsf.FLAG_WINGS))
        self.assertFalse(s.flag(crsf.FLAG_DOOR))
        self.assertAlmostEqual(s.accel_ms2, 9.81, 2)
        self.assertAlmostEqual(s.yaw_rate, -182.3, 1)
        self.assertEqual((s.wheel_pct, s.roll_target, s.nav_dist), (-55.0, -25.0, 123))
        self.assertAlmostEqual(s.desired_course, 315.0, 1)
        self.assertEqual((s.elevon_left_us, s.elevon_right_us), (1259, 1740))
        self.assertEqual(s.state_name, "LANDED")

    def test_stream_resync_and_crc(self):
        d = crsf.CrsfDecoder()
        good = bytes.fromhex(FIRMWARE_FRAMES[0x1E])
        bad = bytearray(good)
        bad[-1] ^= 0xFF                                   # corrupt the CRC
        stream = b"\x00\x55" + bytes(bad) + good + good[:5]
        d.feed(stream)
        d.feed(good[5:])                                   # the cut-off frame completes later
        self.assertEqual(d.parser.frames_ok, 2)
        self.assertEqual(d.parser.crc_errors, 1)

    def test_rc_encode_roundtrip(self):
        ch = [992, 992, 172, 992, 1811, 172] + [992] * 10
        frames = crsf.FrameParser().feed(crsf.encode_rc(ch))
        self.assertEqual(frames[0][0], crsf.T_RC_CHANNELS)
        packed = int.from_bytes(frames[0][1], "little")
        self.assertEqual([(packed >> (11 * i)) & 0x7FF for i in range(16)], ch)


if __name__ == "__main__":
    unittest.main()
