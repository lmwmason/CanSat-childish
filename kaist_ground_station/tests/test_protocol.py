import unittest

from kaist_ground_station.protocol import StreamParser, digital_command, time_command


# Literal independently checked wire fixtures, not produced by the decoder.
ATLM = bytes.fromhex("76 00 40 10 01 02 03 04 05 06 07 5d 79")
DTLM = bytes.fromhex("76 00 48 04 03 80 00 01 82")
GPS = (b"\x76\x00\x58\x00$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\r\n")
IMU = b"\x76\x00\x60\x00*1,2,3,18\r\n"  # sum('*1,2,3') mod 256 = 0x18


class ProtocolTests(unittest.TestCase):
    def test_every_split_and_bytewise_mixed_stream(self):
        stream = ATLM + GPS + DTLM + IMU
        for split in range(len(stream)+1):
            parser = StreamParser()
            frames = parser.feed(stream[:split]) + parser.feed(stream[split:])
            self.assertEqual([f.kind for f in frames], ["ATLM", "GPS", "DTLM", "IMU"], split)
            self.assertEqual(frames[0].data["raw"][-1], 93)
            self.assertAlmostEqual(frames[1].data["lat"], 48.1173)
            self.assertEqual(frames[2].data["bits"][15], 1)
        parser = StreamParser()
        frames = [f for b in stream for f in parser.feed(bytes([b]))]
        self.assertEqual(len(frames), 4)

    def test_pdf_and_compact_analog_and_digital_headers(self):
        for wire in [ATLM, ATLM[:3]+b"\0"+ATLM[3:]]:
            frames = StreamParser().feed(wire)
            self.assertEqual(frames[0].kind, "ATLM")
        for count in [2,3,4]:
            values = bytes(range(count))
            checksum = [1,3,0][count-2]
            compact = b"\x76\0\x48" + bytes([count]) + values + bytes([checksum])
            for wire in [compact,compact[:3]+b"\0"+compact[3:]]:
                frame = StreamParser().feed(wire)[0]
                self.assertEqual(frame.kind, "DTLM")
                self.assertEqual(len(frame.data["bits"]), count*8)

    def test_imu_checksum_basis_is_explicit(self):
        for checksum,basis in [(b"EE","excluding_star_exe"),(b"18","including_star_pdf")]:
            frame = StreamParser().feed(b"\x76\0\x60\0*1,2,3,"+checksum+b"\r\n")[0]
            self.assertEqual(frame.kind,"IMU")
            self.assertEqual(frame.data["checksum_basis"],basis)

    def test_corruption_noise_and_truncated_text_resynchronize(self):
        for frame in [ATLM, DTLM, GPS, IMU]:
            corrupt = bytearray(frame)
            corrupt[-4 if frame in (GPS,IMU) else -1] ^= 1
            parser = StreamParser()
            events = parser.feed(b"OK\r\n" + corrupt + ATLM)
            self.assertEqual(events[-1].kind, "ATLM")
            self.assertGreater(parser.errors, 0)
        parser = StreamParser()
        events = parser.feed(b"\x76\0\x60\0*1,"+GPS)
        self.assertEqual(events[-1].kind, "GPS")
        self.assertGreater(parser.errors, 0)

    def test_no_fix_clears_coordinates_and_rejects_bad_coordinates(self):
        from kaist_ground_station.protocol import xor8
        body = b"GNGGA,123519,,,,,0,00,99.9,,,,,,"
        wire = b"\x76\0\x58\0$"+body+f"*{xor8(body):02X}\r\n".encode()
        frame = StreamParser().feed(wire)[0]
        self.assertEqual(frame.kind, "GPS")
        self.assertIsNone(frame.data["lat"])
        bad = GPS.replace(b"4807.038", b"4867.038")
        self.assertEqual(StreamParser().feed(bad)[0].kind, "ERROR")

    def test_timeout_recovers_hidden_valid_packet_and_bounds_noise(self):
        parser = StreamParser(timeout_s=1)
        self.assertEqual(parser.feed(b"\x76\0\xa0\xff"+ATLM,0), [])
        events = parser.expire(2)
        self.assertEqual(events[-1].kind,"ATLM")
        parser.feed(b"x"*100000)
        self.assertLessEqual(len(parser.buffer),1)

    def test_messages_and_qlook_binary_contents(self):
        msg = b"\x76\0\xa3\x04\x00\x76\x00\xff"
        frame = StreamParser().feed(msg)[0]
        self.assertEqual(frame.kind,"MESSAGE")
        self.assertIsNone(frame.checksum)
        frame = StreamParser().feed(bytes.fromhex("76 00 80 08 20 00 40 00 01 02 03 04"))[0]
        self.assertEqual(frame.data,dict(x=32,y=64,pixels=[1,2,3,4]))

    def test_full_and_chunked_camera_with_embedded_header(self):
        jpeg = b"\xff\xd8" + ATLM + b"z"*120 + b"\xff\xd9"
        size = b"\x76\0\x34\0\x04\0\0"+len(jpeg).to_bytes(2,"big")
        marker = b"\x76\0\x32\0\0"
        for blocks in [[jpeg], [jpeg[i:i+64] for i in range(0,len(jpeg),64)]]:
            stream = size+b"".join(marker+block+marker for block in blocks)+GPS
            for step in [1,7,10000]:
                parser = StreamParser()
                events = [f for i in range(0,len(stream),step) for f in parser.feed(stream[i:i+step])]
                self.assertEqual(parser.errors,0)
                image = next(f for f in events if f.kind=="IMAGE")
                self.assertEqual(image.data["jpeg"],jpeg)
                self.assertEqual(events[-1].kind,"GPS")

    def test_command_bytes_match_distributed_exe_including_padding(self):
        self.assertEqual(digital_command(0,1),bytes.fromhex("56 00 48 00 00 01 01 00"))
        self.assertEqual(digital_command(71,255),bytes.fromhex("56 00 48 00 47 ff b8 00"))
        self.assertEqual(time_command(0x01020304),bytes.fromhex("56 00 49 00 01 02 03 04 04 00"))
        for channel,value in [(24,0),(64,256),(2,2),(-1,0),(True,0)]:
            with self.assertRaises(ValueError):
                digital_command(channel,value)


if __name__ == "__main__":
    unittest.main()
