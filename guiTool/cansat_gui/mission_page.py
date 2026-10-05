import time

from PyQt6.QtCore import QUrl, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QPainter
from PyQt6.QtWidgets import (QCheckBox, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
                             QPlainTextEdit, QPushButton, QSplitter, QTabWidget, QVBoxLayout,
                             QWidget)

from . import theme
from .conn_bar import ConnectionBar
from .hud import HUD, Dial, LivePlot, VehicleView
from .mother import (CH_AUX1_DROP, CH_AUX2_MODE, CRSF_BAUD, CRSF_BAUDS, DEMO, MODE_NAMES,
                     SIM_UDP_PORT, STATE_NAMES, WING_NAMES, MotherLink, parse_telemetry)
from .telemetry_log import LOG_DIR
from .track import TrackView
from .widgets import HealthLed, StateBar, Tile

STALE_S = 3.0
LOITER_RADIUS_M = 50.0          # firmware NAV_LOITER_RADIUS_M
WING_COLORS = (theme.MUTED, theme.AMBER, theme.ACCENT)


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


def _chip_style(on: bool, color: str) -> str:
    c = color if on else theme.MUTED
    return (f"color:{c}; font-weight:bold; border:1px solid {c if on else theme.BORDER}; "
            f"border-radius:9px; padding:3px 12px; background:{theme.PANEL};")


class MissionPage(QWidget):
    """Flight view of the mother CanSat (ArduPilot / Mission Planner style)."""

    linkStateChanged = pyqtSignal(str, str)   # text, color

    def __init__(self, link: MotherLink, parent=None):
        super().__init__(parent)
        self.link = link
        self.v: dict[str, float] = {}
        self._last_rx = 0.0
        self._home_set = False

        self.conn = ConnectionBar(
            "Mother", link,
            extras=[("Demo (synthetic flight)", DEMO), (f"Simulator UDP :{SIM_UDP_PORT}", f"udp:{SIM_UDP_PORT}")],
            bauds=(9600, 19200, 57600, 115200, 230400) + CRSF_BAUDS, default_baud=CRSF_BAUD)
        self.conn.baud.setToolTip("400000 (TX module) / 416666 / 420000 (receiver) = Crossfire CRSF; "
                                  "anything else = text lines")

        self.bar = StateBar(STATE_NAMES)
        self.bar.setMinimumHeight(44)
        self.hud = HUD()

        # ---- Quick tab ----
        self.tiles = {k: Tile(k) for k in ("Roll", "Pitch", "Yaw", "Wheel", "Yaw rate", "Accel",
                                           "Altitude", "Speed", "GPS", "Home dist", "RSSI", "LQ")}
        quick = QWidget()
        g = QGridLayout(quick)
        for i, t in enumerate(self.tiles.values()):
            g.addWidget(t, i // 4, i % 4)
            t._value.setStyleSheet("font-size:16pt; font-weight:bold;")

        # ---- Status tab ----
        self.dial = Dial("reaction wheel", -100, 100, "%")
        self.vehicle = VehicleView()
        self.led_imu, self.led_gps, self.led_link = HealthLed("IMU"), HealthLed("GPS"), HealthLed("LINK")
        leds = QHBoxLayout()
        for led in (self.led_imu, self.led_gps, self.led_link):
            leds.addWidget(led)
        self.chips = {k: QLabel(k) for k in ("AUX1", "DROP", "DOOR", "WINGS", "NAV", "LANDED")}
        chips = QHBoxLayout()
        for c in self.chips.values():
            chips.addWidget(c)
        chips.addStretch(1)
        self.elevon_label = QLabel("Elevon  --")
        self.elevon_label.setStyleSheet(f"color:{theme.MUTED};")
        status = QWidget()
        sl = QGridLayout(status)
        sl.addWidget(self.dial, 0, 0)
        sl.addWidget(self.vehicle, 0, 1)
        sl.addLayout(leds, 1, 0, 1, 2)
        sl.addLayout(chips, 2, 0, 1, 2)
        sl.addWidget(self.elevon_label, 3, 0, 1, 2)
        sl.setColumnStretch(1, 1)

        # ---- Track tab ----
        self.track = TrackView(LOITER_RADIUS_M)

        # ---- Actions tab ----
        self.chk_rc = QCheckBox("Send RC frames (this PC acts as the transmitter)")
        self.chk_rc.setChecked(True)
        self.chk_rc.toggled.connect(self.link.set_send_rc)
        self.btn_aux1 = QPushButton("AUX1 · DROP ARM  (OFF)")
        self.btn_aux2 = QPushButton("AUX2 · ELEVON MANUAL  (OFF = AUTO)")
        for b in (self.btn_aux1, self.btn_aux2):
            b.setCheckable(True)
            b.setMinimumHeight(52)
            b.setStyleSheet("font-size:12pt; font-weight:bold;")
        self.btn_aux1.clicked.connect(self._toggle_aux1)
        self.btn_aux2.clicked.connect(self._toggle_aux2)
        self.log_label = QLabel("Log: not recording")
        self.log_label.setWordWrap(True)
        self.log_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(f"color:{theme.MUTED};")
        btn_logs = QPushButton("Open log folder")
        btn_logs.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOG_DIR))))
        note = QLabel("The switches are sent to the CanSat over the Crossfire link, exactly like the "
                      "AUX1/AUX2 switches on a radio. They are only active on a CRSF serial connection "
                      "(400000 / 416666 / 420000 baud). AUX1 must stay OFF until you want the drop "
                      "sequence armed.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{theme.MUTED};")
        actions = QWidget()
        al = QVBoxLayout(actions)
        al.addWidget(self.chk_rc)
        al.addWidget(self.btn_aux1)
        al.addWidget(self.btn_aux2)
        al.addWidget(note)
        al.addSpacing(8)
        al.addWidget(self.log_label)
        al.addWidget(self.stats_label)
        al.addWidget(btn_logs)
        al.addStretch(1)

        # ---- Messages tab ----
        self.console = Console()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(2000)
        self.console.setStyleSheet("font-family: monospace;")

        self.tabs = QTabWidget()
        self.tabs.addTab(quick, "Quick")
        self.tabs.addTab(status, "Status")
        self.tabs.addTab(self.track, "Track")
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
            "rate": LivePlot("Yaw rate", "dps", [("gz", red)], min_span=10),
            "acc": LivePlot("Accel", "g", [("|a|", grn)], min_span=0.5),
            "rw": LivePlot("Reaction wheel", "%", [("cmd", "#bc8cff")], min_span=20),
            "alt": LivePlot("Altitude", "m", [("alt", blu)], min_span=10),
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

    def _reset_switches(self) -> None:
        for b, ch, label in ((self.btn_aux1, CH_AUX1_DROP, "AUX1 · DROP ARM"),
                             (self.btn_aux2, CH_AUX2_MODE, "AUX2 · ELEVON MANUAL")):
            b.setChecked(False)
            self.link.set_switch(ch, False)
            b.setText(f"{label}  (OFF{' = AUTO' if ch == CH_AUX2_MODE else ''})")
            b.setStyleSheet("font-size:12pt; font-weight:bold;")

    def _toggle_aux1(self, on: bool) -> None:
        if on:
            box = QMessageBox(QMessageBox.Icon.Warning, "Arm drop sequence",
                              "AUX1 ON arms the mission: when the CanSat detects falling it will start the "
                              "wheel / door / wing sequence.\n\nOnly arm when the CanSat is ready to be dropped.",
                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, self)
            box.setDefaultButton(QMessageBox.StandardButton.Cancel)
            if box.exec() != QMessageBox.StandardButton.Yes:
                self.btn_aux1.setChecked(False)
                return
        self.link.set_switch(CH_AUX1_DROP, on)
        self.btn_aux1.setText(f"AUX1 · DROP ARM  ({'ON - ARMED' if on else 'OFF'})")
        self.btn_aux1.setStyleSheet(f"font-size:12pt; font-weight:bold; color:{theme.RED if on else theme.TEXT};")
        self.log(f"AUX1 {'ON (drop armed)' if on else 'OFF'}", theme.RED if on else theme.ORANGE)

    def _toggle_aux2(self, on: bool) -> None:
        self.link.set_switch(CH_AUX2_MODE, on)
        self.btn_aux2.setText(f"AUX2 · ELEVON MANUAL  ({'ON = MANUAL' if on else 'OFF = AUTO'})")
        self.btn_aux2.setStyleSheet(f"font-size:12pt; font-weight:bold; color:{theme.ORANGE if on else theme.TEXT};")
        self.log(f"AUX2 {'ON (elevon manual)' if on else 'OFF (elevon auto)'}", theme.ORANGE)

    # ---- link events -------------------------------------------------------
    def _on_connection(self, up: bool) -> None:
        crsf_serial = up and self.link.is_crsf_serial
        for w in (self.chk_rc, self.btn_aux1, self.btn_aux2):
            w.setEnabled(crsf_serial)
        self._reset_switches()
        if up:
            self.v = {}
            self._home_set = False
            self.track.clear()
            for pw in self.plots.values():
                pw.clear()
            self.log("Connected", theme.ACCENT)
            path = self.link.log_path
            if path:
                self.log_label.setText(f"Log: {path}")
                self.log(f"Recording to {path}", theme.MUTED)
        else:
            self.log("Disconnected", theme.AMBER)
            self.log_label.setText("Log: not recording")
            self.bar.set_state(None)
            self.hud.update_values(mode_text="--", armed=False, batt=None, rssi=None,
                                   wing_text="WING --", wing_color=theme.MUTED,
                                   chute_text="", chute_color=theme.MUTED)
            for led in (self.led_imu, self.led_gps, self.led_link):
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
        def changed(k):
            return k in new and old.get(k) != new[k]
        if changed("state"):
            i = int(new["state"])
            s = STATE_NAMES[i] if 0 <= i < len(STATE_NAMES) else str(i)
            self.log(f"Mission state: {s}", theme.STATE_COLORS.get(s, theme.TEXT))
        if changed("mode"):
            self.log(f"Elevon mode: {MODE_NAMES.get(int(new['mode']), int(new['mode']))}", theme.ORANGE)
        if changed("drop") and new["drop"]:
            self.log("DROP DETECTED", theme.RED)
        if changed("door") and new["door"]:
            self.log("Door opened", theme.ORANGE)
        if changed("wing") and new["wing"] >= 2:
            self.log("Wings ejected", theme.ACCENT)
        if changed("landed") and new["landed"]:
            self.log("LANDED", theme.ACCENT)
        if changed("fix") and "fix" in old:
            self.log("GPS fix acquired" if new["fix"] else "GPS fix lost", theme.ACCENT if new["fix"] else theme.AMBER)
        if changed("fault") and new["fault"]:
            self.log(f"IMU warning ({int(new.get('imu', 0))}/2 sensors OK)", theme.RED)

    def _apply(self, d: dict) -> None:
        v = self.v
        g = v.get
        roll, pitch, yaw = g("roll", 0.0), g("pitch", 0.0), g("yaw", 0.0)
        acc = g("acc", 1.0)
        wheel = g("wheel", 0.0)
        wing = min(max(int(g("wing", 0)), 0), 2)
        state = int(g("state", 0))
        mode = int(g("mode", 0))
        sname = STATE_NAMES[state] if 0 <= state < len(STATE_NAMES) else None
        fix = bool(g("fix", 0))

        self.bar.set_state(sname)
        self.hud.update_values(
            roll=roll, pitch=pitch, yaw=yaw, wheel=wheel, gmag=acc,
            mode_text=MODE_NAMES.get(mode, f"MODE {mode}"), armed=bool(g("armed", 0)),
            wing_text=f"WING {WING_NAMES[wing]}", wing_color=WING_COLORS[wing],
            chute_text=f"DOOR {'OPEN' if g('door', 0) else 'CLOSED'}",
            chute_color=theme.ORANGE if g("door", 0) else theme.MUTED,
            batt=None, rssi=v.get("rssi"))
        self.vehicle.set_state(wing, 2 if g("door", 0) else 0)
        self.dial.set_value(wheel)

        t = self.tiles
        t["Roll"].set_value(f"{roll:.1f}°")
        t["Pitch"].set_value(f"{pitch:.1f}°")
        t["Yaw"].set_value(f"{yaw % 360:.0f}°")
        t["Wheel"].set_value(f"{wheel:.0f} %", theme.ORANGE if abs(wheel) >= 99 else theme.TEXT)
        t["Yaw rate"].set_value(f"{g('gz', 0.0):.1f} °/s")
        t["Accel"].set_value(f"{acc:.2f} g")
        t["Altitude"].set_value(f"{g('alt', 0.0):.0f} m" if fix else "--")
        t["Speed"].set_value(f"{g('spd', 0.0) * 3.6:.0f} km/h" if fix else "--")
        t["GPS"].set_value(f"{'FIX' if fix else 'NO FIX'} · {int(g('sats', 0))}",
                           theme.ACCENT if fix else theme.AMBER)
        t["Home dist"].set_value(f"{g('dist', 0.0):.0f} m" if g("navact", 0) else "--")
        t["RSSI"].set_value(f"{v['rssi']:.0f} dBm" if "rssi" in v else "--")
        lq = v.get("lq")
        t["LQ"].set_value(f"{lq:.0f} %" if lq is not None else "--",
                          theme.TEXT if lq is None or lq >= 70 else theme.AMBER if lq >= 40 else theme.RED)

        self.led_imu.set_ok(not g("fault", 0))
        self.led_gps.set_ok(fix)
        for key, on, color in (("AUX1", g("aux1", 0), theme.RED), ("DROP", g("drop", 0), theme.ORANGE),
                               ("DOOR", g("door", 0), theme.ORANGE), ("WINGS", wing >= 2, theme.ACCENT),
                               ("NAV", g("navact", 0), theme.BLUE), ("LANDED", g("landed", 0), theme.ACCENT)):
            self.chips[key].setStyleSheet(_chip_style(bool(on), color))
        if "elL" in v:
            self.elevon_label.setText(f"Elevon  L {v['elL']:.0f} µs   R {v['elR']:.0f} µs   "
                                      f"roll target {g('rtgt', 0):.0f}°   desired course {g('dcrs', 0):.0f}°")

        # ground track: home = position at the moment the drop is detected (same as the firmware)
        if fix:
            self.track.push(g("lat", 0.0), g("lon", 0.0), g("crs", 0.0))
        if g("drop", 0) and fix and not self._home_set:
            self.track.set_home(g("lat", 0.0), g("lon", 0.0))
            self._home_set = True
        elif not g("drop", 0) and self._home_set:
            self.track.set_home(None, None)
            self._home_set = False

        self.plots["att"].push([roll, pitch])
        self.plots["rate"].push([g("gz", 0.0)])
        self.plots["acc"].push([acc])
        self.plots["rw"].push([wheel])
        if fix:
            self.plots["alt"].push([g("alt", 0.0)])

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
        stats = self.link.stats
        if stats:
            self.stats_label.setText(f"CRSF frames: {stats[0]}   CRC errors: {stats[1]}")
        else:
            self.stats_label.setText("")
