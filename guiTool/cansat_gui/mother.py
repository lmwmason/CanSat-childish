"""Mother CanSat telemetry sources and a link facade.

The mother firmware reports over CRSF (Crossfire).  `CrsfSource` reads the CRSF byte stream from a
serial port (400000 baud to a TX module), decodes it (see crsf.py), records every frame to CSV
(telemetry_log.py) and hands the UI one key=value line per update, in the same format the simulator
uses:

    mothership,t=12345,state=3,mode=2,roll=3.2,pitch=-1.5,yaw=181.0,gz=-12.6,acc=1.0,wheel=100,...

Every key is numeric and optional.  The full key list is in crsf.MotherState.to_line().

Other sources: simulator UDP (text lines), plain serial text lines, and a synthetic demo flight that
goes through the real CRSF encoder -> decoder -> CSV path, so the whole chain can be tried
without hardware.
"""
import math
import time

from PyQt6.QtCore import QIODeviceBase, QObject, QTimer, pyqtSignal
from PyQt6.QtNetwork import QHostAddress, QUdpSocket
from PyQt6.QtSerialPort import QSerialPort

from . import crsf
from .crsf import STATE_NAMES  # noqa: F401  (re-exported for the UI)
from .link import SerialLink
from .telemetry_log import TelemetryLogger

MODE_NAMES = {0: "ELEVON OFF", 1: "MANUAL", 2: "AUTO"}
WING_NAMES = ("FOLDED", "DEPLOYING", "DEPLOYED")
CHUTE_NAMES = ("STOWED", "ARMED", "DEPLOYED")

SIM_UDP_PORT = 41000
# Pi <-> Crossfire TX module (JR bay) normally runs at 400000; receiver <-> flight controller at
# 416666 / 420000.  Any of these opens the port as a CRSF link.
CRSF_BAUD = 400000
CRSF_BAUDS = (400000, 416666, 420000)
RC_HZ = 50
DEMO = "demo"

# RC channel numbers (1..16) the mother firmware listens to (see firmware pinmap.md)
CH_AUX1_DROP = 5
CH_AUX2_MODE = 6


def parse_telemetry(line: str) -> dict[str, float] | None:
    """Return the numeric key=value fields of a telemetry line, or None."""
    out: dict[str, float] = {}
    for tok in line.split(","):
        k, eq, v = tok.partition("=")
        if not eq:
            continue
        try:
            out[k.strip()] = float(v)
        except ValueError:
            continue
    if len(out) < 2:
        return None
    first = line.split(",", 1)[0]
    if "=" not in first and not first.lower().startswith("mother"):
        return None  # another vehicle (e.g. a child satellite)
    return out


class _Sink(QObject):
    """Common part of the CRSF sources: decode -> log -> emit a line."""

    line = pyqtSignal(str)
    connectionChanged = pyqtSignal(bool)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.decoder = crsf.CrsfDecoder()
        self.logger = TelemetryLogger()
        self.is_open = False

    @property
    def log_path(self):
        return self.logger.path if self.logger.active else None

    def _begin(self) -> None:
        self.decoder = crsf.CrsfDecoder()
        self.logger.start()

    def _end(self) -> None:
        self.logger.stop()

    def ingest(self, data: bytes) -> None:
        self.logger.write_raw(data)
        types = self.decoder.feed(data, self.logger.write_frame)
        if types:
            self.line.emit(self.decoder.state.to_line())

    def send(self, text: str) -> None:
        self.error.emit("CRSF link has no text commands - use the AUX switches on the Actions tab")


class CrsfSource(_Sink):
    """Crossfire module on a serial port.  Optionally also acts as the transmitter (RC frames)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._port = QSerialPort(self)
        self._port.readyRead.connect(self._on_ready)
        self._port.errorOccurred.connect(self._on_error)
        self.send_rc = True
        self.rc = [crsf.RC_MID] * 16
        self.rc[2] = crsf.RC_LOW                    # throttle low
        self.rc[CH_AUX1_DROP - 1] = self.rc[CH_AUX2_MODE - 1] = crsf.RC_LOW
        self._rc_timer = QTimer(self, interval=int(1000 / RC_HZ))
        self._rc_timer.timeout.connect(self._send_rc)

    @property
    def frames_ok(self) -> int:
        return self.decoder.parser.frames_ok

    @property
    def crc_errors(self) -> int:
        return self.decoder.parser.crc_errors

    def open(self, name: str, baud: int = CRSF_BAUD) -> bool:
        self._port.setPortName(name)
        self._port.setBaudRate(baud)
        self._port.setDataBits(QSerialPort.DataBits.Data8)
        self._port.setParity(QSerialPort.Parity.NoParity)
        self._port.setStopBits(QSerialPort.StopBits.OneStop)
        self._port.setFlowControl(QSerialPort.FlowControl.NoFlowControl)
        if not self._port.open(QIODeviceBase.OpenModeFlag.ReadWrite):
            self.error.emit(self._port.errorString())
            return False
        self._begin()
        self.is_open = True
        self._rc_timer.start()
        self.connectionChanged.emit(True)
        return True

    def close(self) -> None:
        self._rc_timer.stop()
        if self._port.isOpen():
            self._port.close()
        self._end()
        self.is_open = False
        self.connectionChanged.emit(False)

    def set_switch(self, channel: int, on: bool) -> None:
        self.rc[channel - 1] = crsf.RC_HIGH if on else crsf.RC_LOW

    def _send_rc(self) -> None:
        if self.send_rc and self._port.isOpen():
            self._port.write(crsf.encode_rc(self.rc))

    def _on_ready(self) -> None:
        self.ingest(bytes(self._port.readAll()))

    def _on_error(self, err) -> None:
        if err == QSerialPort.SerialPortError.ResourceError:
            self.error.emit("Device disconnected")
            self.close()


class DemoSource(_Sink):
    """Synthetic mother flight, pushed through the real CRSF encode -> decode -> CSV path.

    Follows the firmware mission: IDLE -> drop -> WAIT 2 s -> STAB -> SPIN -> door OPEN, 5 s at
    max speed -> REST -> wings out and AUTO loiter around the drop point -> LANDED.
    """

    CYCLE_S = 90.0
    LAT0, LON0 = 37.5665, 126.9780
    LOITER_R = 50.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self, interval=50)
        self._timer.timeout.connect(self._tick)
        self._t0 = 0.0
        self._next = {}

    def open(self) -> bool:
        self._begin()
        self._t0 = time.monotonic()
        self._next = {k: 0.0 for k in ("att", "gps", "mode", "stat", "link")}
        self.is_open = True
        self._timer.start()
        self.connectionChanged.emit(True)
        return True

    def close(self) -> None:
        self._timer.stop()
        self._end()
        self.is_open = False
        self.connectionChanged.emit(False)

    # -- scenario ----------------------------------------------------------
    def _scene(self, t: float) -> dict:
        drop_t, wait_end, stab_end, door_t = 5.0, 7.0, 10.0, 14.0
        rest_t, wing_t = door_t + 5.0, door_t + 10.0
        dropping = t >= drop_t
        alt = 300.0 if not dropping else max(50.0, 300.0 - 4.0 * (t - drop_t))
        landed = dropping and alt <= 50.0 and t > wing_t
        mission = 0
        wheel, rate = 0.0, 0.0
        if dropping:
            mission = 1
        if t >= wait_end:
            mission, wheel, rate = 2, 0.04 * math.sin(t * 2), 1.5 * math.sin(t * 1.3)
        if t >= stab_end:
            mission = 3
            k = min((t - stab_end) / 4.0, 1.0)
            wheel, rate = 1.0, 240.0 * k * k
        door = t >= door_t + 0.5
        if t >= door_t:
            mission = 4
            wheel, rate = 1.0, 240.0 + 20.0 * min((t - door_t) / 5.0, 1.0)
        if t >= rest_t:
            mission = 5
            k = min((t - rest_t) / 4.5, 1.0)
            wheel, rate = -1.0 + 1.0 * k, 260.0 * (1 - k) ** 2
        wings = t >= wing_t
        if wings:
            mission, wheel, rate = 6, 0.0, 0.0

        # position: drift east, then circle (clockwise) around the drop point
        v, bank = 3.0, 0.0
        east, north = v * max(t - drop_t, 0.0), 0.0
        heading = 90.0
        dist, desired, rtgt = 0.0, 0.0, 0.0
        if wings and not landed:
            v = 11.0
            r = self.LOITER_R
            phi = math.pi / 2 + (v / r) * (t - wing_t)         # azimuth of the aircraft from home
            east, north = r * math.sin(phi), r * math.cos(phi)
            heading = math.degrees(phi + math.pi / 2) % 360
            bank = math.degrees(math.atan(v * v / (9.80665 * r)))
            rate = -math.degrees(v / r)                         # clockwise = negative gz
            dist, desired, rtgt = r, heading, bank
        if landed:
            v, rate = 0.0, 0.0
        lat = self.LAT0 + north / 111320.0
        lon = self.LON0 + east / (111320.0 * math.cos(math.radians(self.LAT0)))

        flags = crsf.FLAG_GPS_FIX
        if dropping:
            flags |= crsf.FLAG_DROPPING | crsf.FLAG_AUX1
        if landed:
            flags |= crsf.FLAG_LANDED
        if wings:
            flags |= crsf.FLAG_WINGS
        if door:
            flags |= crsf.FLAG_DOOR
        if wings and not landed:
            flags |= crsf.FLAG_NAV_ACTIVE

        yaw = (heading if wings else (t * 9) % 360) % 360
        return dict(
            mission=mission, wheel=wheel, rate=rate, flags=flags, alt=alt, lat=lat, lon=lon, v=v,
            heading=heading, roll=0.0 if landed else bank + 1.5 * math.sin(t * 1.7),
            pitch=-6 + 2 * math.sin(t * 0.8) if dropping and not landed else 0.0,
            yaw=yaw - 360 if yaw >= 180 else yaw, dist=dist, desired=desired, rtgt=rtgt,
            elevon=2 if wings and not landed else 0,
            ev=(1500 + 250 * math.sin(t * 2)) if wings and not landed else 1500)

    def _tick(self) -> None:
        t = (time.monotonic() - self._t0) % self.CYCLE_S
        now = time.monotonic()
        sc = self._scene(t)
        out = b""
        if now >= self._next["att"]:
            self._next["att"] = now + 0.25
            out += crsf.encode_attitude(sc["roll"], sc["pitch"], sc["yaw"])
        if now >= self._next["gps"]:
            self._next["gps"] = now + 1.0
            out += crsf.encode_gps(sc["lat"], sc["lon"], sc["v"], sc["heading"], sc["alt"], 9)
        if now >= self._next["mode"]:
            self._next["mode"] = now + 1.0
            name = crsf.MISSION_NAMES[sc["mission"]]
            land = " LAND" if sc["flags"] & crsf.FLAG_LANDED else ""
            out += crsf.encode_mode(f"{name} {crsf.ELEVON_NAMES[sc['elevon']]}{land}")
        if now >= self._next["stat"]:
            self._next["stat"] = now + 0.5
            acc = 9.81 + 0.08 * math.sin(t * 5) + (0.4 if sc["mission"] in (3, 4) else 0)
            out += crsf.encode_status(
                sc["mission"], sc["elevon"], sc["flags"], 2, acc, sc["rate"], sc["wheel"], sc["rtgt"],
                sc["dist"], sc["desired"], int(sc["ev"]), int(3000 - sc["ev"]), int(t * 1000))
        if now >= self._next["link"]:
            self._next["link"] = now + 1.0
            out += crsf.encode_link_stats(-62 - 8 * math.sin(t * 0.2), 100 if t % 40 < 36 else 88)
        if out:
            self.ingest(out)


class UdpSource(QObject):
    """Receives the simulator's telemetry broadcast (127.0.0.1:41000)."""

    line = pyqtSignal(str)
    connectionChanged = pyqtSignal(bool)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sock = QUdpSocket(self)
        self._sock.readyRead.connect(self._on_ready)
        self.is_open = False

    def open(self, port: int) -> bool:
        if not self._sock.bind(QHostAddress.SpecialAddress.LocalHost, port):
            self.error.emit(self._sock.errorString())
            return False
        self.is_open = True
        self.connectionChanged.emit(True)
        return True

    def close(self) -> None:
        self._sock.close()
        self.is_open = False
        self.connectionChanged.emit(False)

    def send(self, text: str) -> None:
        self.error.emit("UDP simulator link is receive-only")

    def _on_ready(self) -> None:
        while self._sock.hasPendingDatagrams():
            data = bytes(self._sock.receiveDatagram().data())
            for raw in data.decode("ascii", errors="replace").splitlines():
                if raw.strip():
                    self.line.emit(raw.strip())


class MotherLink(QObject):
    """One interface over CRSF serial, plain serial text, simulator UDP and demo sources.

    A serial port opened at a CRSF baud rate (400000 / 416666 / 420000) is treated as a CRSF link;
    any other baud rate as the old text-line protocol.
    """

    line = pyqtSignal(str)
    connectionChanged = pyqtSignal(bool)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._serial = SerialLink(self, poll=False)
        self._crsf = CrsfSource(self)
        self._udp = UdpSource(self)
        self._demo = DemoSource(self)
        self._active = None
        for src in (self._serial, self._crsf, self._udp, self._demo):
            src.line.connect(self.line)
            src.error.connect(self.error)
            src.connectionChanged.connect(lambda up, s=src: self._on_conn(s, up))

    def _on_conn(self, src, up: bool) -> None:
        if src is self._active or up:
            self.connectionChanged.emit(up)
            if not up:
                self._active = None

    @property
    def is_open(self) -> bool:
        return self._active is not None and self._active.is_open

    @property
    def is_crsf_serial(self) -> bool:
        return self._active is self._crsf

    @property
    def log_path(self):
        return getattr(self._active, "log_path", None) if self._active else None

    @property
    def stats(self) -> tuple[int, int] | None:
        """(frames ok, crc errors) for a CRSF serial link."""
        return (self._crsf.frames_ok, self._crsf.crc_errors) if self._active is self._crsf else None

    def open(self, spec: str, baud: int) -> bool:
        if spec == DEMO:
            self._active = self._demo
            return self._demo.open()
        if spec.startswith("udp:"):
            self._active = self._udp
            return self._udp.open(int(spec[4:]))
        if baud in CRSF_BAUDS:
            self._active = self._crsf
            return self._crsf.open(spec, baud)
        self._active = self._serial
        return self._serial.open(spec, baud)

    def close(self) -> None:
        if self._active:
            self._active.close()

    def send(self, text: str) -> None:
        if self._active:
            self._active.send(text)

    # -- RC uplink (only acts on a CRSF serial link) --------------------------
    def set_switch(self, channel: int, on: bool) -> None:
        self._crsf.set_switch(channel, on)

    def set_send_rc(self, enabled: bool) -> None:
        self._crsf.send_rc = enabled
