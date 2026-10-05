from PyQt6.QtCore import QIODeviceBase, QObject, QTimer, pyqtSignal
from PyQt6.QtSerialPort import QSerialPort, QSerialPortInfo

BAUD = 115200
POLL_MS = 1000


def list_ports() -> list[tuple[str, str]]:
    return [(p.portName(), p.description()) for p in QSerialPortInfo.availablePorts()]


class SerialLink(QObject):
    """Line-oriented serial connection with periodic 's' status polling."""

    line = pyqtSignal(str)
    connectionChanged = pyqtSignal(bool)
    error = pyqtSignal(str)

    def __init__(self, parent=None, poll: bool = True):
        super().__init__(parent)
        self._poll_enabled = poll
        self._port = QSerialPort(self)
        self._port.readyRead.connect(self._on_ready)
        self._port.errorOccurred.connect(self._on_error)
        self._buf = b""
        self.poll_paused = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)

    @property
    def is_open(self) -> bool:
        return self._port.isOpen()

    def open(self, name: str, baud: int = BAUD) -> bool:
        self._port.setPortName(name)
        self._port.setBaudRate(baud)
        if not self._port.open(QIODeviceBase.OpenModeFlag.ReadWrite):
            self.error.emit(self._port.errorString())
            return False
        # Opening usually pulses DTR, which resets an Arduino Pro Mini
        # (the firmware resumes a flight in progress, see resumeFlight()).
        self._port.setDataTerminalReady(False)
        self._buf = b""
        self.poll_paused = False
        if self._poll_enabled:
            self._timer.start(POLL_MS)
        self.connectionChanged.emit(True)
        return True

    def close(self) -> None:
        self._timer.stop()
        if self._port.isOpen():
            self._port.close()
        self.connectionChanged.emit(False)

    def send(self, text: str) -> None:
        if self._port.isOpen():
            self._port.write(text.encode("ascii"))

    def _poll(self) -> None:
        if not self.poll_paused:
            self.send("s")

    def _on_ready(self) -> None:
        self._buf += bytes(self._port.readAll())
        *lines, self._buf = self._buf.split(b"\n")
        for raw in lines:
            text = raw.decode("ascii", errors="replace").strip()
            if text:
                self.line.emit(text)

    def _on_error(self, err) -> None:
        if err == QSerialPort.SerialPortError.ResourceError:
            self.error.emit("Device disconnected")
            self.close()
