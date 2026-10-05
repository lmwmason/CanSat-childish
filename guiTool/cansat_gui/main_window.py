from PyQt6.QtCore import QSettings, Qt, QTimer
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget,
                             QVBoxLayout, QWidget)

from . import theme
from .data_page import DataPage
from .link import SerialLink
from .mother import MotherLink
from .mission_page import MissionPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Space Chamchu Integral - Ground Station")
        self.setWindowIcon(theme.logo_icon())
        self.resize(1360, 860)
        self.settings = QSettings()

        self.mother_link = MotherLink(self)
        self.child_link = SerialLink(self)
        for link in (self.mother_link, self.child_link):
            link.error.connect(lambda m: self.statusBar().showMessage(m, 6000))

        self.pages = QStackedWidget()
        self.mission = MissionPage(self.mother_link)
        self.data = DataPage(self.child_link)
        self.pages.addWidget(self.mission)
        self.pages.addWidget(self.data)

        bar = QHBoxLayout()
        bar.setContentsMargins(14, 0, 16, 0)
        bar.setSpacing(8)
        bar.addWidget(self._brand())
        bar.addSpacing(18)
        self.tabs = []
        for i, name in enumerate(("MISSION", "DATA")):
            b = QPushButton(name)
            b.setObjectName("tab")
            b.setCheckable(True)
            b.clicked.connect(lambda _, i=i: self._select(i))
            bar.addWidget(b)
            self.tabs.append(b)
        bar.addStretch(1)
        self.chip_mother = QLabel()
        self.chip_child = QLabel()
        for c in (self.chip_mother, self.chip_child):
            bar.addWidget(c)
            bar.addSpacing(10)
        self.mission.linkStateChanged.connect(lambda t, c: self._chip(self.chip_mother, "MOTHER", t, c))
        self.child_link.connectionChanged.connect(
            lambda up: self._chip(self.chip_child, "CHILD", "CONNECTED" if up else "OFFLINE",
                                  theme.ACCENT if up else theme.MUTED))
        self._chip(self.chip_mother, "MOTHER", "OFFLINE", theme.MUTED)
        self._chip(self.chip_child, "CHILD", "OFFLINE", theme.MUTED)

        top = QFrame()
        top.setObjectName("panel")
        top.setStyleSheet(f"QFrame#panel {{ border: none; border-bottom: 2px solid {theme.BORDER}; border-radius: 0; "
                          f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0d1a3d, stop:1 {theme.PANEL}); }}")
        top.setLayout(bar)

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(top)
        body = QVBoxLayout()
        body.setContentsMargins(10, 10, 10, 10)
        body.addWidget(self.pages)
        lay.addLayout(body, 1)
        self.setCentralWidget(central)

        self._select(int(self.settings.value("page", 0)))
        self.statusBar().showMessage("Ready")
        self._port_timer = QTimer(self, interval=3000)
        self._port_timer.timeout.connect(lambda: (self.mission.conn.refresh(), self.data.conn.refresh()))
        self._port_timer.start()

    @staticmethod
    def _chip(label: QLabel, name: str, text: str, color: str) -> None:
        label.setText(f'<span style="color:{theme.MUTED}">{name}</span> '
                      f'<span style="color:{color}; font-weight:bold">● {text}</span>')

    def _brand(self) -> QWidget:
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(host)
        lay.setContentsMargins(0, 6, 0, 6)
        lay.setSpacing(10)
        pm = theme.logo_pixmap()
        if not pm.isNull():
            icon = QLabel()
            crop = pm.copy(60, 60, 1440, 620)
            icon.setPixmap(crop.scaledToHeight(58, Qt.TransformationMode.SmoothTransformation))
            lay.addWidget(icon)
        title = QLabel(f'<span style="color:{theme.BLUE}">SPACE</span> '
                       f'<span style="color:{theme.ORANGE}">CHAMCHU</span><br>'
                       f'<span style="color:{theme.MUTED}; font-size:8pt; letter-spacing:3px;">'
                       f'INTEGRAL · GROUND STATION</span>')
        title.setStyleSheet("font-size:15pt; font-weight:900; font-style:italic;")
        lay.addWidget(title)
        return host

    def _select(self, i: int) -> None:
        self.pages.setCurrentIndex(i)
        for k, b in enumerate(self.tabs):
            b.setChecked(k == i)
        self.settings.setValue("page", i)

    def closeEvent(self, e):
        self.mother_link.close()
        self.child_link.close()
        super().closeEvent(e)
