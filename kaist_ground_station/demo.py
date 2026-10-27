"""Deterministic simulated wire data; never updates telemetry state directly."""
import math
from .protocol import xor8


def demo_packet(t: float) -> bytes:
    latitude = 36.3723 + 0.0003 * math.sin(t / 20)
    longitude = 127.361 + 0.0004 * math.cos(t / 20)

    def nmea(value, width):
        deg = int(value)
        return f"{deg:0{width}d}{(value-deg)*60:08.5f}"

    sec = int(t) % 86400
    altitude = 120 + 25 * math.sin(t / 30)
    body = (f"GPGGA,{sec//3600:02d}{sec//60%60:02d}{sec%60:02d}.00,"
            f"{nmea(latitude,2)},N,{nmea(longitude,3)},E,1,10,0.9,{altitude:.1f},M,20.0,M,,").encode()
    gps = b"\x76\x00\x58\x00$" + body + f"*{xor8(body):02X}\r\n".encode()
    body = f"*{15*math.sin(t/4):.2f},{8*math.cos(t/5):.2f},{t*4%360:.2f}".encode()
    imu = b"\x76\x00\x60\x00" + body + f",{sum(body[1:])&255:02X}\r\n".encode()
    values = bytes([int(120 + 50 * math.sin(t / 5 + i)) for i in range(7)] + [93])
    atlm = b"\x76\x00\x40\x10" + values + bytes([sum(values) & 255])
    bits = bytes([3, int(t) & 255, 0, 0])
    dtlm = b"\x76\x00\x48\x04" + bits + bytes([xor8(bits)])
    message = b"DEMO / simulated telemetry"
    return gps + imu + atlm + dtlm + b"\x76\x00\xa0" + bytes([len(message)]) + message
