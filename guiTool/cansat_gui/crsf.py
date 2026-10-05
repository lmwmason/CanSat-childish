"""CRSF (Crossfire) telemetry decoding for the mother CanSat.

Pure Python (no Qt) so it can be tested and reused on its own.

Frame layout:  [sync][len][type][payload...][crc8]
  len  = number of bytes after the len byte (type + payload + crc)
  crc8 = poly 0xD5 over type + payload
All multi-byte fields are big-endian.

Frames the mother firmware sends (see firmware crsf_telemetry.h):
  0x1E attitude, 0x02 GPS, 0x21 flight-mode text, 0x7F custom mother status.
Frames the Crossfire module adds itself:
  0x14 link statistics.
"""
import math
import struct
import time
from dataclasses import dataclass, field

SYNC_BYTES = (0xC8, 0xEA, 0xEE, 0xEC)
ADDR_TRANSMITTER = 0xEE          # handset -> TX module (RC channels)
MAX_FRAME_LEN = 62

T_GPS = 0x02
T_BATTERY = 0x08
T_LINK_STATS = 0x14
T_RC_CHANNELS = 0x16
T_ATTITUDE = 0x1E
T_FLIGHT_MODE = 0x21
T_MOTHER_STATUS = 0x7F

# firmware MissionState enum order
MISSION_NAMES = ("IDLE", "WAIT", "STAB", "SPIN", "OPEN", "REST", "WING")
LANDED_STATE = 7                                  # GUI-only state: landed flag set
STATE_NAMES = MISSION_NAMES + ("LANDED",)
ELEVON_NAMES = ("OFF", "MANUAL", "AUTO")
TX_POWER_MW = {0: 0, 1: 10, 2: 25, 3: 100, 4: 500, 5: 1000, 6: 2000, 7: 250, 8: 50}

FLAG_DROPPING = 1 << 0
FLAG_LANDED = 1 << 1
FLAG_WINGS = 1 << 2
FLAG_DOOR = 1 << 3
FLAG_GPS_FIX = 1 << 4
FLAG_AUX1 = 1 << 5
FLAG_IMU_DISAGREE = 1 << 6
FLAG_NAV_ACTIVE = 1 << 7

RC_LOW, RC_MID, RC_HIGH = 172, 992, 1811
G = 9.80665


def crc8(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0xD5) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def build_frame(sync: int, ftype: int, payload: bytes) -> bytes:
    body = bytes([ftype]) + payload
    return bytes([sync, len(body) + 1]) + body + bytes([crc8(body)])


# ---------------------------------------------------------------------------
# Stream parser
# ---------------------------------------------------------------------------
class FrameParser:
    """Turns a raw byte stream into (type, payload) tuples; resyncs on garbage."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self.frames_ok = 0
        self.crc_errors = 0

    def feed(self, data: bytes) -> list[tuple[int, bytes]]:
        self._buf += data
        out: list[tuple[int, bytes]] = []
        buf = self._buf
        while True:
            # drop everything before a plausible sync byte
            i = 0
            while i < len(buf) and buf[i] not in SYNC_BYTES:
                i += 1
            if i:
                del buf[:i]
            if len(buf) < 2:
                break
            length = buf[1]
            if length < 2 or length > MAX_FRAME_LEN:
                del buf[0]
                continue
            if len(buf) < length + 2:
                break
            body = bytes(buf[2:length + 1])        # type + payload
            if crc8(body) == buf[length + 1]:
                out.append((body[0], body[1:]))
                self.frames_ok += 1
                del buf[:length + 2]
            else:
                self.crc_errors += 1
                del buf[0]
        if len(buf) > 512:                         # never grow without bound
            del buf[:-64]
        return out


# ---------------------------------------------------------------------------
# Telemetry state
# ---------------------------------------------------------------------------
@dataclass
class MotherState:
    """Latest value of everything the mother reports (None / 0 until first frame)."""

    # attitude 0x1E
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    # gps 0x02
    lat: float = 0.0
    lon: float = 0.0
    speed: float = 0.0            # ground speed, m/s
    course: float = 0.0
    alt: float = 0.0
    sats: int = 0
    # flight mode 0x21
    mode_text: str = ""
    # status 0x7F
    mission: int = 0
    elevon_mode: int = 0
    flags: int = 0
    imu_count: int = 0
    accel_ms2: float = 0.0
    yaw_rate: float = 0.0
    wheel_pct: float = 0.0
    roll_target: float = 0.0
    nav_dist: float = 0.0
    desired_course: float = 0.0
    elevon_left_us: int = 1500
    elevon_right_us: int = 1500
    uptime_ms: int = 0
    # link statistics 0x14
    rssi: float | None = None     # dBm
    lq: int | None = None         # %
    snr: int | None = None
    rf_mode: int | None = None
    tx_power_mw: int | None = None
    dl_rssi: float | None = None
    dl_lq: int | None = None
    # bookkeeping
    seen: set = field(default_factory=set)

    def flag(self, mask: int) -> bool:
        return bool(self.flags & mask)

    @property
    def state_index(self) -> int:
        """0..6 firmware mission state, 7 once landed."""
        if self.flag(FLAG_LANDED):
            return LANDED_STATE
        return min(max(self.mission, 0), len(MISSION_NAMES) - 1)

    @property
    def state_name(self) -> str:
        return STATE_NAMES[self.state_index]

    @property
    def fault(self) -> bool:
        return self.imu_count < 2 or self.flag(FLAG_IMU_DISAGREE)

    def update(self, ftype: int, p: bytes) -> bool:
        """Decode one frame into the state. Returns False if it was not understood."""
        try:
            if ftype == T_ATTITUDE and len(p) == 6:
                pi, ro, ya = struct.unpack(">hhh", p)
                k = 180.0 / math.pi / 10000.0
                self.pitch, self.roll, self.yaw = pi * k, ro * k, ya * k
            elif ftype == T_GPS and len(p) == 15:
                lat, lon, spd, hdg, alt, sats = struct.unpack(">iiHHHB", p)
                self.lat, self.lon = lat / 1e7, lon / 1e7
                self.speed = spd / 10.0 / 3.6
                self.course = hdg / 100.0
                self.alt = alt - 1000.0
                self.sats = sats
            elif ftype == T_FLIGHT_MODE:
                self.mode_text = p.split(b"\0", 1)[0].decode("ascii", errors="replace")
            elif ftype == T_MOTHER_STATUS and len(p) == 23 and p[0] == 1:
                (_, self.mission, self.elevon_mode, self.flags, self.imu_count, acc, yr, wc, rt,
                 self.nav_dist, dc, self.elevon_left_us, self.elevon_right_us,
                 self.uptime_ms) = struct.unpack(">BBBBBHhbbHHHHI", p)
                self.accel_ms2 = acc / 100.0
                self.yaw_rate = yr / 10.0
                self.wheel_pct = float(wc)
                self.roll_target = float(rt)
                self.desired_course = dc / 10.0
            elif ftype == T_LINK_STATS and len(p) == 10:
                (r1, r2, lq, snr, _ant, rfm, txp, dr, dlq, _dsnr) = struct.unpack(">BBBbBBBBBb", p)
                self.rssi = -float(min(r1, r2) if r1 and r2 else (r1 or r2))
                self.lq, self.snr, self.rf_mode = lq, snr, rfm
                self.tx_power_mw = TX_POWER_MW.get(txp)
                self.dl_rssi, self.dl_lq = -float(dr), dlq
            else:
                return False
        except struct.error:
            return False
        self.seen.add(ftype)
        return True

    # -- exports ----------------------------------------------------------
    def to_line(self) -> str:
        """key=value line understood by mother.parse_telemetry (all values numeric)."""
        v = {
            "t": self.uptime_ms, "state": self.state_index, "mode": self.elevon_mode,
            "roll": round(self.roll, 2), "pitch": round(self.pitch, 2), "yaw": round(self.yaw, 2),
            "gz": round(self.yaw_rate, 1), "acc": round(self.accel_ms2 / G, 3),
            "wheel": round(self.wheel_pct), "wing": 2 if self.flag(FLAG_WINGS) else 0, "chute": 0,
            "door": int(self.flag(FLAG_DOOR)), "drop": int(self.flag(FLAG_DROPPING)),
            "landed": int(self.flag(FLAG_LANDED)), "aux1": int(self.flag(FLAG_AUX1)),
            "armed": int(self.flag(FLAG_AUX1)), "fix": int(self.flag(FLAG_GPS_FIX)),
            "navact": int(self.flag(FLAG_NAV_ACTIVE)), "imu": self.imu_count,
            "fault": int(self.fault), "lat": f"{self.lat:.7f}", "lon": f"{self.lon:.7f}",
            "alt": round(self.alt, 1), "spd": round(self.speed, 2), "crs": round(self.course, 1),
            "sats": self.sats, "dist": round(self.nav_dist), "dcrs": round(self.desired_course, 1),
            "rtgt": round(self.roll_target), "elL": self.elevon_left_us, "elR": self.elevon_right_us,
        }
        if self.rssi is not None:
            v.update(rssi=round(self.rssi), lq=self.lq, snr=self.snr, rfmode=self.rf_mode,
                     txpow=self.tx_power_mw or 0)
        return "mothership," + ",".join(f"{k}={x}" for k, x in v.items())


CSV_COLUMNS = (
    "pc_time", "elapsed_s", "frame", "uptime_ms", "mission", "elevon", "mode_text",
    "dropping", "landed", "wings", "door", "gps_fix", "aux1", "nav_active", "imu_count", "imu_disagree",
    "roll_deg", "pitch_deg", "yaw_deg", "yaw_rate_dps", "accel_ms2", "wheel_pct",
    "lat", "lon", "alt_m", "speed_ms", "course_deg", "sats",
    "roll_target_deg", "nav_dist_m", "desired_course_deg", "elevon_left_us", "elevon_right_us",
    "rssi_dbm", "lq_pct", "snr_db", "rf_mode", "tx_power_mw",
)

FRAME_NAMES = {T_ATTITUDE: "attitude", T_GPS: "gps", T_FLIGHT_MODE: "mode",
               T_MOTHER_STATUS: "status", T_LINK_STATS: "link"}


def csv_row(s: MotherState, ftype: int, pc_time: str, elapsed: float) -> list:
    def b(mask):
        return int(s.flag(mask))
    r = lambda x, n=2: "" if x is None else round(x, n)       # noqa: E731
    return [
        pc_time, f"{elapsed:.3f}", FRAME_NAMES.get(ftype, hex(ftype)), s.uptime_ms, s.state_name,
        ELEVON_NAMES[s.elevon_mode] if 0 <= s.elevon_mode < len(ELEVON_NAMES) else s.elevon_mode,
        s.mode_text, b(FLAG_DROPPING), b(FLAG_LANDED), b(FLAG_WINGS), b(FLAG_DOOR), b(FLAG_GPS_FIX),
        b(FLAG_AUX1), b(FLAG_NAV_ACTIVE), s.imu_count, b(FLAG_IMU_DISAGREE),
        r(s.roll), r(s.pitch), r(s.yaw), r(s.yaw_rate, 1), r(s.accel_ms2), r(s.wheel_pct, 0),
        f"{s.lat:.7f}", f"{s.lon:.7f}", r(s.alt, 1), r(s.speed), r(s.course, 1), s.sats,
        r(s.roll_target, 0), r(s.nav_dist, 0), r(s.desired_course, 1), s.elevon_left_us, s.elevon_right_us,
        r(s.rssi, 0), "" if s.lq is None else s.lq, "" if s.snr is None else s.snr,
        "" if s.rf_mode is None else s.rf_mode, "" if s.tx_power_mw is None else s.tx_power_mw,
    ]


class CrsfDecoder:
    """Parser + state in one object: feed bytes, get back the frames that changed the state."""

    def __init__(self) -> None:
        self.parser = FrameParser()
        self.state = MotherState()
        self.t0 = time.monotonic()

    def feed(self, data: bytes, on_frame=None) -> list[int]:
        """Returns the frame types (in order) that were decoded from `data`.

        on_frame(ftype, state) is called right after each frame updated the state, so a
        logger sees the values as they were at that frame, not only the end of the chunk.
        """
        done = []
        for ftype, payload in self.parser.feed(data):
            if self.state.update(ftype, payload):
                done.append(ftype)
                if on_frame:
                    on_frame(ftype, self.state)
        return done


# ---------------------------------------------------------------------------
# Encoders: used for the RC uplink and by the demo / tests (mirror the firmware)
# ---------------------------------------------------------------------------
def encode_rc(channels: list[int]) -> bytes:
    """RC channels frame (handset -> TX module). 16 channels, 11 bit each, LSB first."""
    ch = (list(channels) + [RC_MID] * 16)[:16]
    bits = 0
    for i, c in enumerate(ch):
        bits |= (max(0, min(2047, int(c)))) << (11 * i)
    return build_frame(ADDR_TRANSMITTER, T_RC_CHANNELS, bits.to_bytes(22, "little"))


def encode_attitude(roll: float, pitch: float, yaw: float, sync: int = 0xC8) -> bytes:
    k = math.pi / 180.0 * 10000.0
    cl = lambda x: max(-32768, min(32767, round(x * k)))      # noqa: E731
    return build_frame(sync, T_ATTITUDE, struct.pack(">hhh", cl(pitch), cl(roll), cl(yaw)))


def encode_gps(lat: float, lon: float, speed_ms: float, course: float, alt: float, sats: int,
               sync: int = 0xC8) -> bytes:
    u16 = lambda x: max(0, min(65535, round(x)))               # noqa: E731
    return build_frame(sync, T_GPS, struct.pack(
        ">iiHHHB", round(lat * 1e7), round(lon * 1e7), u16(speed_ms * 3.6 * 10), u16(course * 100),
        u16(alt + 1000), sats))


def encode_mode(text: str, sync: int = 0xC8) -> bytes:
    return build_frame(sync, T_FLIGHT_MODE, text.encode("ascii", "replace")[:23] + b"\0")


def encode_status(mission: int, elevon: int, flags: int, imu_count: int, accel_ms2: float,
                  yaw_rate: float, wheel_cmd: float, roll_target: float, nav_dist: float,
                  desired_course: float, left_us: int, right_us: int, uptime_ms: int,
                  sync: int = 0xC8) -> bytes:
    u16 = lambda x: max(0, min(65535, round(x)))               # noqa: E731
    i8 = lambda x: max(-128, min(127, round(x)))               # noqa: E731
    return build_frame(sync, T_MOTHER_STATUS, struct.pack(
        ">BBBBBHhbbHHHHI", 1, mission, elevon, flags, imu_count, u16(accel_ms2 * 100),
        max(-32768, min(32767, round(yaw_rate * 10))), i8(wheel_cmd * 100), i8(roll_target),
        u16(nav_dist), u16(desired_course * 10), left_us, right_us, uptime_ms & 0xFFFFFFFF))


def encode_link_stats(rssi_dbm: float, lq: int, snr: int = 10, rf_mode: int = 4, tx_power: int = 3,
                      sync: int = 0xC8) -> bytes:
    r = max(0, min(255, round(-rssi_dbm)))
    return build_frame(sync, T_LINK_STATS, struct.pack(">BBBbBBBBBb", r, r, lq, snr, 0, rf_mode,
                                                       tx_power, r, lq, snr))
