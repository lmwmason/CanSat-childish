"""Mother CanSat telemetry: line parser, UDP/demo sources and a link facade.

Wire format (one line per packet, same style as simulator/core/src/telemetry.c):

    mothership,t=12345,state=2,mode=1,roll=3.2,pitch=-1.5,yaw=181.0,
    gx=0.1,gy=0.0,gz=-0.3,ax=0.01,ay=0.0,az=1.0,wheel=1200,wing=2,chute=0,
    batt=7.4,rssi=-71,fault=0

Every key is optional.  wing: 0 folded / 1 deploying / 2 deployed.
chute: 0 stowed / 1 armed / 2 deployed.  wheel: reaction wheel rpm (signed).
"""
import math
import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtNetwork import QHostAddress, QUdpSocket

from .link import SerialLink

STATE_NAMES = ("BOOT", "STANDBY", "GLIDE", "LANDED")
MODE_NAMES = {0: "DISARMED", 1: "GUIDED", 2: "FAILSAFE"}
WING_NAMES = ("FOLDED", "DEPLOYING", "DEPLOYED")
CHUTE_NAMES = ("STOWED", "ARMED", "DEPLOYED")

# Uplink commands.  ASSUMPTION: the mother firmware does not exist yet, so
# these single-byte commands are placeholders - change them to match it.
CMD_DEPLOY_WINGS = "W"
CMD_DEPLOY_CHUTE = "P"

SIM_UDP_PORT = 41000
DEMO = "demo"


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
            if k.strip() == "dep" and v.isdigit():
                continue
    if len(out) < 2:
        return None
    first = line.split(",", 1)[0]
    if "=" not in first and not first.lower().startswith("mother"):
        return None  # another vehicle (e.g. a child satellite)
    return out


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


class DemoSource(QObject):
    """Synthetic mother flight so the UI can be used without hardware."""

    line = pyqtSignal(str)
    connectionChanged = pyqtSignal(bool)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self, interval=100)
        self._timer.timeout.connect(self._tick)
        self.is_open = False
        self._t0 = 0.0
        self._wing_cmd = False
        self._chute = 0

    def open(self) -> bool:
        self._t0 = time.monotonic()
        self._wing_cmd, self._chute = False, 0
        self.is_open = True
        self._timer.start()
        self.connectionChanged.emit(True)
        return True

    def close(self) -> None:
        self._timer.stop()
        self.is_open = False
        self.connectionChanged.emit(False)

    def send(self, text: str) -> None:
        if text == CMD_DEPLOY_WINGS:
            self._wing_cmd = True
        elif text == CMD_DEPLOY_CHUTE:
            self._chute = 2

    def _tick(self) -> None:
        t = (time.monotonic() - self._t0) % 120
        state = 0 if t < 3 else 1 if t < 8 else 2 if t < 100 else 3
        dropped = t - 8
        wing = 0
        if state == 2 or (state == 1 and self._wing_cmd):
            wing = 1 if dropped < 2.5 else 2
        if state == 3:
            wing = 2
        glide = state == 2 and wing == 2 and self._chute == 0
        amp = 1.0 if glide else 0.2 if state == 2 else 0.0
        roll = amp * 18 * math.sin(t * 0.7) + (35 * math.sin(t * 2.5) * math.exp(-max(dropped, 0) ** 2 / 4) if state == 2 else 0)
        pitch = -6 + amp * 6 * math.sin(t * 0.45) if state == 2 else 0.0
        yaw = (t * 9) % 360
        rate = amp * 18 * 0.7 * math.cos(t * 0.7)
        wheel = -rate * 40 + 300 * math.sin(t * 0.3) if state in (1, 2) else 0
        gz = 9 if state == 2 else 0
        self.line.emit(
            f"mothership,t={int(t * 1000)},state={state},mode={0 if state < 2 else 1},"
            f"roll={roll:.1f},pitch={pitch:.1f},yaw={yaw:.1f},gx={rate:.1f},gy={amp * 3 * math.cos(t):.1f},"
            f"gz={gz:.1f},ax={0.05 * math.sin(t * 3):.2f},ay={0.04 * math.cos(t * 2):.2f},"
            f"az={1.0 + 0.15 * math.sin(t * 1.3) * amp:.2f},wheel={wheel:.0f},wing={wing},chute={self._chute},"
            f"batt={7.4 - t * 0.002:.2f},rssi={-62 - 8 * math.sin(t * 0.2):.0f},fault=0")


class MotherLink(QObject):
    """One interface over serial, simulator UDP and demo sources."""

    line = pyqtSignal(str)
    connectionChanged = pyqtSignal(bool)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._serial = SerialLink(self, poll=False)
        self._udp = UdpSource(self)
        self._demo = DemoSource(self)
        self._active = None
        for src in (self._serial, self._udp, self._demo):
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

    def open(self, spec: str, baud: int) -> bool:
        if spec == DEMO:
            self._active = self._demo
            return self._demo.open()
        if spec.startswith("udp:"):
            self._active = self._udp
            return self._udp.open(int(spec[4:]))
        self._active = self._serial
        return self._serial.open(spec, baud)

    def close(self) -> None:
        if self._active:
            self._active.close()

    def send(self, text: str) -> None:
        if self._active:
            self._active.send(text)
