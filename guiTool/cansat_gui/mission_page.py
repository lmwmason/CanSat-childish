import time

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import (QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
                             QPlainTextEdit, QPushButton, QSplitter, QTabWidget, QVBoxLayout,
                             QWidget)

from . import theme
from .conn_bar import ConnectionBar
from .hud import HUD, Dial, LivePlot, VehicleView
from .mother import (CHUTE_NAMES, CMD_DEPLOY_CHUTE, CMD_DEPLOY_WINGS, DEMO, MODE_NAMES,
                     SIM_UDP_PORT, STATE_NAMES, WING_NAMES, MotherLink, parse_telemetry)
from .widgets import HealthLed, StateBar, Tile

STALE_S = 2.0
WHEEL_MAX_RPM = 6000
WING_COLORS = (theme.MUTED, theme.AMBER, theme.ACCENT)
CHUTE_COLORS = (theme.MUTED, theme.AMBER, theme.RED)


class Console(QPlainTextEdit):
    """Message console with a faint logo watermark."""

    def paintEvent(self, e):
        super().paintEvent(e)
        pm = theme.logo_pixmap()
        if pm.isNull():
            return
        p = QPainter(self.viewport())
        p.setOpacity(0.10)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w = min(self.viewport().width() - 40, 420)
        pm = pm.scaledToWidth(w, Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap((self.viewport().width() - pm.width()) // 2,
                     (self.viewport().height() - pm.height()) // 2, pm)


class MissionPage(QWidget):
    """Flight view of the mother CanSat (ArduPilot / Mission Planner style)."""

    linkStateChanged = pyqtSignal(str, str)   # text, color

    def __init__(self, link: MotherLink, parent=None):
        super().__init__(parent)
        self.link = link
        self.v: dict[str, float] = {}
        self._last_rx = 0.0

        self.conn = ConnectionBar(
            "Mother", link,
            extras=[("Demo (synthetic flight)", DEMO), (f"Simulator UDP :{SIM_UDP_PORT}", f"udp:{SIM_UDP_PORT}")],
            bauds=(9600, 19200, 57600, 115200, 230400), default_baud=115200)

        self.bar = StateBar(STATE_NAMES)
        self.bar.setMinimumHeight(44)
        self.hud = HUD()

        # ---- Quick tab ----
        self.tiles = {k: Tile(k) for k in ("Roll", "Pitch", "Yaw", "Wheel", "Gyro Z", "Accel", "Battery", "RSSI")}
        quick = QWidget()
        g = QGridLayout(quick)
        for i, t in enumerate(self.tiles.values()):
            g.addWidget(t, i // 4, i % 4)
        for t in self.tiles.values():
            t._value.setStyleSheet("font-size:16pt; font-weight:bold;")

        # ---- Status tab ----
        self.dial = Dial("reaction wheel", -WHEEL_MAX_RPM, WHEEL_MAX_RPM, "rpm")
        self.vehicle = VehicleView()
        self.led_imu, self.led_wheel, self.led_link = HealthLed("IMU"), HealthLed("WHEEL"), HealthLed("LINK")
        leds = QHBoxLayout()
        for led in (self.led_imu, self.led_wheel, self.led_link):
            leds.addWidget(led)
        status = QWidget()
        sl = QGridLayout(status)
        sl.addWidget(self.dial, 0, 0)
        sl.addWidget(self.vehicle, 0, 1)
        sl.addLayout(leds, 1, 0, 1, 2)
        sl.setColumnStretch(1, 1)

        # ---- Actions tab ----
        self.btn_wings = QPushButton("DEPLOY WINGS")
        self.btn_chute = QPushButton("EMERGENCY: DEPLOY PARACHUTE")
        self.btn_chute.setObjectName("danger")
        for b in (self.btn_wings, self.btn_chute):
            b.setMinimumHeight(52)
            b.setStyleSheet("font-size:12pt; font-weight:bold;")
        self.btn_wings.clicked.connect(self._deploy_wings)
        self.btn_chute.clicked.connect(self._deploy_chute)
        actions = QWidget()
        al = QVBoxLayout(actions)
        note = QLabel("Commands are sent over the mother link. The parachute cannot be re-packed in flight, "
                      "so it always asks for confirmation.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{theme.MUTED};")
        al.addWidget(self.btn_wings)
        al.addWidget(self.btn_chute)
        al.addWidget(note)
        al.addStretch(1)

        # ---- Messages tab ----
        self.console = Console()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(2000)
        self.console.setStyleSheet("font-family: monospace;")

        self.tabs = QTabWidget()
        self.tabs.addTab(quick, "Quick")
        self.tabs.addTab(status, "Status")
        self.tabs.addTab(actions, "Actions")
        self.tabs.addTab(self.console, "Messages")
        self.tabs.setStyleSheet(f"QTabBar::tab {{ padding: 7px 18px; background:{theme.PANEL}; "
                                f"border:1px solid {theme.BORDER}; }} "
                                f"QTabBar::tab:selected {{ background:{theme.PANEL_HI}; color:{theme.ORANGE}; }} "
                                f"QTabWidget::pane {{ border:1px solid {theme.BORDER}; }}")

        left = QSplitter(Qt.Orientation.Vertical)
        left.addWidget(self.hud)
        left.addWidget(self.tabs)
        left.setStretchFactor(0, 3)
        left.setStretchFactor(1, 2)

        red, grn, blu, amb = theme.RED, theme.ACCENT, theme.BLUE, theme.ORANGE
        self.plots = {
            "att": LivePlot("Attitude", "deg", [("roll", blu), ("pitch", amb)], min_span=10),
            "gyro": LivePlot("Gyro", "dps", [("x", red), ("y", grn), ("z", blu)], min_span=10),
            "acc": LivePlot("Accel", "g", [("x", red), ("y", grn), ("z", blu)], min_span=0.5),
            "rw": LivePlot("Reaction wheel", "rpm", [("rpm", "#bc8cff")], min_span=200),
        }
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)
        for pw in self.plots.values():
            rl.addWidget(pw)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(0, 5)
        split.setStretchFactor(1, 4)
        split.setChildrenCollapsible(False)
        split.setSizes([760, 540])
        right.setMinimumWidth(360)
        left.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.addWidget(self.conn)
        root.addWidget(self.bar)
        root.addWidget(split, 1)

        link.line.connect(self._on_line)
        link.connectionChanged.connect(self._on_connection)
        self._tick = QTimer(self, interval=250)
        self._tick.timeout.connect(self._refresh_link)
        self._tick.start()
        self._on_connection(False)

    # ---- helpers -----------------------------------------------------------
    def log(self, text: str, color: str = theme.TEXT) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.console.appendHtml(f'<span style="color:{theme.MUTED}">{stamp}</span> '
                                f'<span style="color:{color}">{text.replace("<", "&lt;")}</span>')

    def _send_confirmed(self, cmd: str, title: str, text: str, label: str) -> None:
        if not self.link.is_open:
            self.log("Not connected - command not sent", theme.AMBER)
            return
        box = QMessageBox(QMessageBox.Icon.Warning, title, text,
                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, self)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if box.exec() == QMessageBox.StandardButton.Yes:
            self.link.send(cmd)
            self.log(f"Command sent: {label}", theme.ORANGE)

    def _deploy_wings(self) -> None:
        self._send_confirmed(CMD_DEPLOY_WINGS, "Deploy wings", "Unfold the wings now?", "DEPLOY WINGS")

    def _deploy_chute(self) -> None:
        self._send_confirmed(CMD_DEPLOY_CHUTE, "Deploy parachute",
                             "EMERGENCY: release the parachute now?\nThis cannot be undone in flight.",
                             "DEPLOY PARACHUTE")

    # ---- link events -------------------------------------------------------
    def _on_connection(self, up: bool) -> None:
        if up:
            self.v = {}
            for pw in self.plots.values():
                pw.clear()
            self.log("Connected", theme.ACCENT)
        else:
            self.log("Disconnected", theme.AMBER)
            self.bar.set_state(None)
            self.hud.update_values(mode_text="--", armed=False, batt=None, rssi=None,
                                   wing_text="WING --", wing_color=theme.MUTED,
                                   chute_text="CHUTE --", chute_color=theme.MUTED)
            for led in (self.led_imu, self.led_wheel, self.led_link):
                led.set_ok(None)
        self._refresh_link()

    def _on_line(self, line: str) -> None:
        d = parse_telemetry(line)
        if d is None:
            if not line.startswith("#"):
                self.log(line)
            return
        self._last_rx = time.monotonic()
        old = self.v
        self.v = {**old, **d}
        self._log_changes(old, self.v)
        self._apply(d)

    def _log_changes(self, old: dict, new: dict) -> None:
        def name(table, val):
            i = int(val)
            return table[i] if 0 <= i < len(table) else str(i)
        if "state" in new and old.get("state") != new["state"]:
            s = name(STATE_NAMES, new["state"])
            self.log(f"Flight state: {s}", theme.STATE_COLORS.get(s, theme.TEXT))
        if "mode" in new and old.get("mode") != new["mode"]:
            self.log(f"Mode: {MODE_NAMES.get(int(new['mode']), int(new['mode']))}", theme.ORANGE)
        if "wing" in new and old.get("wing") != new["wing"]:
            self.log(f"Wings: {name(WING_NAMES, new['wing'])}", WING_COLORS[min(int(new["wing"]), 2)])
        if "chute" in new and old.get("chute") != new["chute"]:
            self.log(f"Parachute: {name(CHUTE_NAMES, new['chute'])}", CHUTE_COLORS[min(int(new["chute"]), 2)])
        if "fault" in new and old.get("fault", 0) != new["fault"] and new["fault"]:
            self.log("IMU FAULT", theme.RED)

    def _apply(self, d: dict) -> None:
        v = self.v
        g = v.get
        roll, pitch, yaw = g("roll", 0.0), g("pitch", 0.0), g("yaw", 0.0)
        acc = (g("ax", 0.0) ** 2 + g("ay", 0.0) ** 2 + g("az", 0.0) ** 2) ** 0.5
        wheel = g("wheel", 0.0)
        wing = min(max(int(g("wing", 0)), 0), 2)
        chute = min(max(int(g("chute", 0)), 0), 2)
        state = int(g("state", 0))
        mode = int(g("mode", 0))
        sname = STATE_NAMES[state] if 0 <= state < len(STATE_NAMES) else None

        self.bar.set_state(sname)
        self.hud.update_values(
            roll=roll, pitch=pitch, yaw=yaw, wheel=wheel, gmag=acc,
            mode_text=MODE_NAMES.get(mode, f"MODE {mode}"),
            armed=bool(g("armed", g("motors", mode > 0))),
            wing_text=f"WING {WING_NAMES[wing]}", wing_color=WING_COLORS[wing],
            chute_text=f"CHUTE {CHUTE_NAMES[chute]}", chute_color=CHUTE_COLORS[chute],
            batt=v.get("batt"), rssi=v.get("rssi"))
        self.vehicle.set_state(wing, chute)
        self.dial.set_value(wheel)

        t = self.tiles
        t["Roll"].set_value(f"{roll:.1f}°")
        t["Pitch"].set_value(f"{pitch:.1f}°")
        t["Yaw"].set_value(f"{yaw % 360:.0f}°")
        t["Wheel"].set_value(f"{wheel:.0f} rpm", theme.ORANGE if abs(wheel) > 0.8 * WHEEL_MAX_RPM else theme.TEXT)
        t["Gyro Z"].set_value(f"{g('gz', 0.0):.1f} °/s")
        t["Accel"].set_value(f"{acc:.2f} g")
        t["Battery"].set_value(f"{v['batt']:.2f} V" if "batt" in v else "--")
        t["RSSI"].set_value(f"{v['rssi']:.0f} dBm" if "rssi" in v else "--")

        self.led_imu.set_ok(not g("fault", 0))
        self.led_wheel.set_ok(abs(wheel) < WHEEL_MAX_RPM)

        self.plots["att"].push([roll, pitch])
        self.plots["gyro"].push([g("gx", 0.0), g("gy", 0.0), g("gz", 0.0)])
        self.plots["acc"].push([g("ax", 0.0), g("ay", 0.0), g("az", 0.0)])
        self.plots["rw"].push([wheel])

    def _refresh_link(self) -> None:
        if not self.link.is_open:
            text, color = "OFFLINE", theme.MUTED
        elif time.monotonic() - self._last_rx > STALE_S:
            text, color = "NO DATA", theme.RED
        else:
            text, color = "LIVE", theme.ACCENT
        self.hud.update_values(link_text=text, link_color=color)
        self.led_link.set_ok(None if text == "OFFLINE" else text == "LIVE")
        self.linkStateChanged.emit(text, color)
