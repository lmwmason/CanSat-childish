from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QWidget

from . import theme
from .link import list_ports


class ConnectionBar(QWidget):
    """Port selector + Connect button for one link (works with SerialLink / MotherLink)."""

    def __init__(self, title: str, link, extras: list[tuple[str, str]] = (), bauds=(115200,),
                 default_baud: int = 115200, parent=None):
        super().__init__(parent)
        self.link, self.extras, self.key = link, list(extras), title.lower()
        self.settings = QSettings()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        name = QLabel(title.upper())
        name.setStyleSheet(f"color:{theme.ORANGE}; font-weight:bold; letter-spacing:2px;")
        lay.addWidget(name)
        self.port = QComboBox()
        self.port.setMinimumWidth(260)
        lay.addWidget(self.port)
        self.btn_refresh = QPushButton("⟳")
        self.btn_refresh.setToolTip("Refresh port list")
        self.btn_refresh.clicked.connect(self.refresh)
        lay.addWidget(self.btn_refresh)
        self.baud = QComboBox()
        for b in bauds:
            self.baud.addItem(f"{b} baud", b)
        self.baud.setCurrentIndex(max(self.baud.findData(default_baud), 0))
        self.baud.setMinimumWidth(100)
        self.baud.setEnabled(len(bauds) > 1)
        lay.addWidget(self.baud)
        self.btn = QPushButton("CONNECT")
        self.btn.setObjectName("connect")
        self.btn.setProperty("on", False)
        self.btn.clicked.connect(self._toggle)
        lay.addWidget(self.btn)
        self.status = QLabel("")
        self.status.setStyleSheet(f"color:{theme.MUTED};")
        lay.addWidget(self.status, 1)
        link.connectionChanged.connect(self._on_connection)
        self.refresh()

    def refresh(self) -> None:
        if self.link.is_open:
            return
        current = self.port.currentData() or self.settings.value(f"conn/{self.key}", "")
        self.port.clear()
        for label, spec in self.extras:
            self.port.addItem(label, spec)
        for name, desc in list_ports():
            self.port.addItem(f"{name}  {desc}".strip(), name)
        idx = self.port.findData(current)
        if idx >= 0:
            self.port.setCurrentIndex(idx)

    def _toggle(self) -> None:
        if self.link.is_open:
            self.link.close()
            return
        spec = self.port.currentData()
        if not spec:
            self.status.setText("No port selected")
            return
        if self.link.open(spec, self.baud.currentData()):
            self.settings.setValue(f"conn/{self.key}", spec)
            self.status.setText("")

    def _on_connection(self, up: bool) -> None:
        self.btn.setText("DISCONNECT" if up else "CONNECT")
        self.btn.setProperty("on", up)
        self.btn.style().unpolish(self.btn)
        self.btn.style().polish(self.btn)
        self.port.setEnabled(not up)
        self.btn_refresh.setEnabled(not up)
        self.baud.setEnabled(not up and self.baud.count() > 1)
