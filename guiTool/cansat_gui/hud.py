"""ArduPilot / Mission Planner style flight widgets: HUD, dial, vehicle view, live plot."""
import math
import time
from collections import deque

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
                         QPolygonF)
from PyQt6.QtWidgets import QWidget

from . import theme
from .widgets import _nice_ticks

SKY_TOP, SKY_BOT = QColor("#1f5fa8"), QColor("#6fb8ff")
GND_TOP, GND_BOT = QColor("#8a5a2b"), QColor("#4a2d12")
WHITE = QColor("#ffffff")
HUD_ORANGE = QColor(theme.ORANGE)


class HUD(QWidget):
    """Artificial horizon with roll arc, heading tape, side tapes and annunciators."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.roll = self.pitch = self.yaw = 0.0
        self.wheel = 0.0
        self.gmag = 1.0
        self.mode_text = "--"
        self.armed = False
        self.link_text, self.link_color = "OFFLINE", theme.MUTED
        self.wing_text, self.wing_color = "WING --", theme.MUTED
        self.chute_text, self.chute_color = "CHUTE --", theme.MUTED
        self.batt: float | None = None
        self.rssi: float | None = None
        self.setMinimumSize(380, 300)

    def update_values(self, **kw) -> None:
        for k, v in kw.items():
            setattr(self, k, v)
        self.update()

    # -- drawing helpers ---------------------------------------------------
    def _font(self, size=9, bold=True) -> QFont:
        f = QFont(self.font())
        f.setPointSize(size)
        f.setBold(bold)
        return f

    def _tape(self, p: QPainter, x: float, w: float, cy: float, h: float, value: float,
              step: float, ppu: float, title: str, fmt: str, right: bool) -> None:
        box = QRectF(x, cy - h / 2, w, h)
        p.save()
        p.setClipRect(box)
        p.fillRect(box, QColor(0, 0, 0, 110))
        p.setFont(self._font(8))
        lo = value - h / 2 / ppu
        hi = value + h / 2 / ppu
        t = math.floor(lo / step) * step
        while t <= hi + step:
            y = cy - (t - value) * ppu
            major = abs(round(t / step)) % 2 == 0
            tick = 12 if major else 7
            p.setPen(QPen(WHITE, 1.5))
            if right:
                p.drawLine(QPointF(x, y), QPointF(x + tick, y))
            else:
                p.drawLine(QPointF(x + w, y), QPointF(x + w - tick, y))
            if major:
                p.setPen(WHITE)
                al = Qt.AlignmentFlag.AlignLeft if right else Qt.AlignmentFlag.AlignRight
                p.drawText(QRectF(x + (16 if right else 0), y - 8, w - 18, 16),
                           al | Qt.AlignmentFlag.AlignVCenter, fmt.format(t))
            t += step
        p.restore()
        # value read-out box
        rb = QRectF(x - (6 if right else 0), cy - 12, w + 6, 24)
        p.setPen(QPen(HUD_ORANGE, 1.5))
        p.setBrush(QColor(0, 0, 0, 200))
        p.drawRect(rb)
        p.setPen(WHITE)
        p.setFont(self._font(10))
        p.drawText(rb, Qt.AlignmentFlag.AlignCenter, fmt.format(value))
        p.setPen(QColor(theme.MUTED))
        p.setFont(self._font(8))
        p.drawText(QRectF(x - 6, cy - h / 2 - 18, w + 12, 16), Qt.AlignmentFlag.AlignCenter, title)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), 8, 8)
        p.setClipPath(clip)

        # --- horizon -------------------------------------------------------
        ppd = h / 46.0
        big = math.hypot(w, h) * 1.6
        p.save()
        p.translate(cx, cy)
        p.rotate(-self.roll)
        p.translate(0, self.pitch * ppd)
        sky = QLinearGradient(0, -big, 0, 0)
        sky.setColorAt(0, SKY_TOP)
        sky.setColorAt(1, SKY_BOT)
        gnd = QLinearGradient(0, 0, 0, big)
        gnd.setColorAt(0, GND_TOP)
        gnd.setColorAt(1, GND_BOT)
        p.fillRect(QRectF(-big, -big, 2 * big, big), sky)
        p.fillRect(QRectF(-big, 0, 2 * big, big), gnd)
        p.setPen(QPen(WHITE, 2))
        p.drawLine(QPointF(-big, 0), QPointF(big, 0))
        p.setFont(self._font(8))
        for deg in range(-60, 61, 5):
            if deg == 0:
                continue
            y = -deg * ppd
            half = 34 if deg % 10 == 0 else 16
            p.setPen(QPen(WHITE, 1.5))
            p.drawLine(QPointF(-half, y), QPointF(half, y))
            if deg % 10 == 0:
                p.drawText(QRectF(half + 4, y - 8, 30, 16), Qt.AlignmentFlag.AlignVCenter, str(abs(deg)))
                p.drawText(QRectF(-half - 34, y - 8, 30, 16),
                           Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, str(abs(deg)))
        p.restore()

        # --- roll arc ------------------------------------------------------
        R = min(w, h) * 0.40
        p.save()
        p.translate(cx, cy)
        p.setPen(QPen(WHITE, 2))
        p.drawArc(QRectF(-R, -R, 2 * R, 2 * R), int((90 - 60) * 16), int(120 * 16))
        for a in (-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60):
            p.save()
            p.rotate(a)
            p.drawLine(QPointF(0, -R), QPointF(0, -R - (12 if a % 30 == 0 else 7)))
            p.restore()
        p.rotate(-self.roll)
        p.setBrush(HUD_ORANGE)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygonF([QPointF(0, -R + 1), QPointF(-8, -R + 15), QPointF(8, -R + 15)]))
        p.restore()

        # --- aircraft symbol ----------------------------------------------
        p.setPen(QPen(HUD_ORANGE, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(cx - 80, cy), QPointF(cx - 28, cy))
        p.drawLine(QPointF(cx - 28, cy), QPointF(cx - 28, cy + 10))
        p.drawLine(QPointF(cx + 28, cy), QPointF(cx + 80, cy))
        p.drawLine(QPointF(cx + 28, cy), QPointF(cx + 28, cy + 10))
        p.setBrush(HUD_ORANGE)
        p.drawEllipse(QPointF(cx, cy), 4, 4)

        # --- heading tape --------------------------------------------------
        tape_h = 30
        p.fillRect(QRectF(0, 0, w, tape_h), QColor(0, 0, 0, 120))
        p.save()
        p.setClipRect(QRectF(0, 0, w, tape_h))
        px_per_deg = max(w / 100.0, 3.0)
        p.setFont(self._font(8))
        for d in range(int(self.yaw) - 60, int(self.yaw) + 61):
            if d % 5:
                continue
            x = cx + (d - self.yaw) * px_per_deg
            p.setPen(QPen(WHITE, 1.5))
            p.drawLine(QPointF(x, tape_h), QPointF(x, tape_h - (12 if d % 10 == 0 else 6)))
            if d % 10 == 0:
                dd = d % 360
                label = {0: "N", 90: "E", 180: "S", 270: "W"}.get(dd, str(dd))
                p.drawText(QRectF(x - 20, 1, 40, 14), Qt.AlignmentFlag.AlignCenter, label)
        p.restore()
        p.setPen(QPen(HUD_ORANGE, 1.5))
        p.setBrush(QColor(0, 0, 0, 220))
        p.drawRect(QRectF(cx - 24, 3, 48, 20))
        p.setPen(WHITE)
        p.setFont(self._font(10))
        p.drawText(QRectF(cx - 24, 3, 48, 20), Qt.AlignmentFlag.AlignCenter, f"{self.yaw % 360:03.0f}°")

        # --- side tapes ----------------------------------------------------
        th = h * 0.50
        self._tape(p, 10, 62, cy, th, self.wheel, 500, 0.06, "RW rpm", "{:.0f}", False)
        self._tape(p, w - 72, 62, cy, th, self.gmag, 0.5, 70, "G", "{:.2f}", True)

        # --- bottom bar ----------------------------------------------------
        bar_h = 30
        p.fillRect(QRectF(0, h - bar_h, w, bar_h), QColor(0, 0, 0, 160))
        p.setFont(self._font(10))
        p.setPen(QColor(theme.ORANGE))
        p.drawText(QRectF(10, h - bar_h, w / 3, bar_h), Qt.AlignmentFlag.AlignVCenter, self.mode_text)
        p.setPen(QColor(theme.ACCENT if self.armed else theme.RED))
        p.drawText(QRectF(0, h - bar_h, w, bar_h), Qt.AlignmentFlag.AlignCenter,
                   "ARMED" if self.armed else "DISARMED")
        p.setPen(QColor(self.link_color))
        extra = ""
        if self.batt is not None:
            extra += f"  {self.batt:.2f} V"
        if self.rssi is not None:
            extra += f"  {self.rssi:.0f} dBm"
        p.drawText(QRectF(w * 2 / 3 - 10, h - bar_h, w / 3, bar_h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, self.link_text + extra)

        # --- annunciators --------------------------------------------------
        y = h - bar_h - 28
        p.setFont(self._font(9))
        for i, (txt, col) in enumerate(((self.wing_text, self.wing_color), (self.chute_text, self.chute_color))):
            r = QRectF(10 + i * 150, y, 140, 22)
            c = QColor(col)
            fill = QColor(c)
            fill.setAlpha(60)
            p.setPen(QPen(c, 1.5))
            p.setBrush(fill)
            p.drawRoundedRect(r, 5, 5)
            p.setPen(WHITE)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, txt)

        p.setClipping(False)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(theme.BORDER), 2))
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 8, 8)


class Dial(QWidget):
    """Round gauge with a needle (reaction-wheel rpm)."""

    def __init__(self, title: str, vmin: float, vmax: float, unit: str = "", parent=None):
        super().__init__(parent)
        self.title, self.vmin, self.vmax, self.unit = title, vmin, vmax, unit
        self.value = 0.0
        self.setMinimumSize(170, 170)

    def set_value(self, v: float) -> None:
        self.value = v
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = min(self.width(), self.height()) - 16
        c = QPointF(self.width() / 2, self.height() / 2 + 6)
        R = s / 2
        start, span = 225, -270  # degrees, clockwise sweep

        def ang(v):
            f = (min(max(v, self.vmin), self.vmax) - self.vmin) / (self.vmax - self.vmin)
            return math.radians(start + span * f)

        p.setPen(QPen(QColor(theme.BORDER), 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(c.x() - R, c.y() - R, 2 * R, 2 * R), int(start * 16), int(span * 16))
        zero = ang(0) if self.vmin < 0 < self.vmax else ang(self.vmin)
        cur = ang(self.value)
        grad_col = QColor(theme.ORANGE if abs(self.value) > 0.8 * max(abs(self.vmin), abs(self.vmax)) else theme.BLUE)
        p.setPen(QPen(grad_col, 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        a0, a1 = math.degrees(zero), math.degrees(cur)
        p.drawArc(QRectF(c.x() - R, c.y() - R, 2 * R, 2 * R), int(a0 * 16), int((a1 - a0) * 16))
        p.setPen(QPen(QColor(theme.MUTED), 1.5))
        for t in _nice_ticks(self.vmin, self.vmax, 6):
            a = ang(t)
            p.drawLine(QPointF(c.x() + (R - 16) * math.cos(a), c.y() - (R - 16) * math.sin(a)),
                       QPointF(c.x() + (R - 24) * math.cos(a), c.y() - (R - 24) * math.sin(a)))
        a = cur
        p.setPen(QPen(QColor(theme.ORANGE), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(c, QPointF(c.x() + (R - 30) * math.cos(a), c.y() - (R - 30) * math.sin(a)))
        p.setBrush(QColor(theme.ORANGE))
        p.drawEllipse(c, 5, 5)
        p.setPen(QColor(theme.TEXT))
        f = QFont(self.font())
        f.setPointSize(14)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(c.x() - 60, c.y() + R * 0.28, 120, 26), Qt.AlignmentFlag.AlignCenter,
                   f"{self.value:.0f}")
        f.setPointSize(8)
        p.setFont(f)
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(c.x() - 60, c.y() + R * 0.28 + 24, 120, 16), Qt.AlignmentFlag.AlignCenter,
                   f"{self.title} {self.unit}".strip())


class VehicleView(QWidget):
    """Top-view of the mother: wings fold out, parachute canopy opens."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.wing_target = 0.0   # 0 folded .. 1 deployed
        self.wing = 0.0
        self.chute = 0           # 0 stowed, 1 armed, 2 deployed
        self.deploying = False
        self.setMinimumSize(260, 170)
        self._timer = QTimer(self, interval=33)
        self._timer.timeout.connect(self._anim)
        self._timer.start()

    def set_state(self, wing: int | None, chute: int | None) -> None:
        if wing is not None:
            self.wing_target = {0: 0.0, 1: 0.55, 2: 1.0}.get(int(wing), 0.0)
        if chute is not None:
            self.chute = int(chute)

    def _anim(self) -> None:
        d = self.wing_target - self.wing
        if abs(d) > 0.004:
            self.wing += max(-0.03, min(0.03, d))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # --- wings (left half) ---
        cx, cy = w * 0.28, h * 0.5
        scale = min(w * 0.5, h) / 200
        p.save()
        p.translate(cx, cy)
        p.scale(scale, scale)
        for side in (-1, 1):
            p.save()
            p.translate(side * 10, -18)
            # folded: wing lies alongside the body (pointing down); deployed: perpendicular
            p.rotate(side * (-(90 - 90 * self.wing)) + 0)
            p.setPen(QPen(QColor("#0b1330"), 2))
            grad = QLinearGradient(0, 0, 80 * side, 0)
            grad.setColorAt(0, QColor(theme.BLUE))
            grad.setColorAt(1, QColor("#2c6cb8"))
            p.setBrush(grad)
            path = QPainterPath()
            path.moveTo(0, 0)
            path.lineTo(side * 86, 8)
            path.lineTo(side * 86, 26)
            path.lineTo(0, 34)
            path.closeSubpath()
            p.drawPath(path)
            p.restore()
        p.setPen(QPen(QColor("#0b1330"), 2))
        p.setBrush(QColor("#dfe7fb"))
        p.drawRoundedRect(QRectF(-14, -52, 28, 104), 12, 12)
        p.setBrush(QColor(theme.ORANGE))
        p.drawEllipse(QPointF(0, -34), 6, 6)
        p.restore()
        p.setPen(QColor(theme.MUTED))
        p.setFont(self.font())
        p.drawText(QRectF(0, h - 22, w * 0.56, 20), Qt.AlignmentFlag.AlignCenter, "WINGS")

        # --- parachute (right half) ---
        px, py = w * 0.78, h * 0.62
        deployed = self.chute == 2
        col = QColor(theme.RED if deployed else theme.AMBER if self.chute == 1 else theme.MUTED)
        if deployed:
            r = min(w * 0.17, h * 0.34)
            path = QPainterPath()
            path.moveTo(px - r, py - h * 0.2)
            path.arcTo(QRectF(px - r, py - h * 0.2 - r, 2 * r, 2 * r), 180, -180)
            path.closeSubpath()
            p.setPen(QPen(WHITE, 1.5))
            p.setBrush(col)
            p.drawPath(path)
            for dx in (-r, -r / 3, r / 3, r):
                p.drawLine(QPointF(px + dx, py - h * 0.2), QPointF(px, py))
        else:
            p.setPen(QPen(col, 2))
            p.setBrush(QColor(col.red(), col.green(), col.blue(), 50))
            p.drawRoundedRect(QRectF(px - 22, py - 30, 44, 24), 6, 6)
        p.setPen(QPen(QColor("#0b1330"), 2))
        p.setBrush(QColor("#dfe7fb"))
        p.drawRoundedRect(QRectF(px - 9, py, 18, 26), 5, 5)
        p.setPen(col)
        p.drawText(QRectF(w * 0.56, h - 22, w * 0.44, 20), Qt.AlignmentFlag.AlignCenter, "PARACHUTE")


class LivePlot(QWidget):
    """Rolling multi-series strip chart (last `window` seconds)."""

    def __init__(self, title: str, unit: str, series: list[tuple[str, str]], window: float = 30.0,
                 min_span: float = 1.0, parent=None):
        super().__init__(parent)
        self.title, self.unit, self.series, self.window, self.min_span = title, unit, series, window, min_span
        self.data: deque = deque()
        self.setMinimumHeight(120)

    def push(self, values: list[float]) -> None:
        now = time.monotonic()
        self.data.append((now, values))
        while self.data and now - self.data[0][0] > self.window:
            self.data.popleft()
        self.update()

    def clear(self) -> None:
        self.data.clear()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(theme.PANEL))
        r = QRectF(56, 24, max(self.width() - 72, 10), max(self.height() - 42, 10))
        p.setPen(QColor(theme.TEXT))
        f = QFont(self.font())
        f.setBold(True)
        p.setFont(f)
        p.drawText(8, 17, f"{self.title} [{self.unit}]")
        small = QFont(self.font())
        small.setPointSize(8)
        p.setFont(small)
        # legend with latest values
        x = self.width() - 10
        last = self.data[-1][1] if self.data else None
        for i in range(len(self.series) - 1, -1, -1):
            name, color = self.series[i]
            txt = f"{name} {last[i]:.1f}" if last and last[i] is not None else name
            tw = p.fontMetrics().horizontalAdvance(txt)
            p.setPen(QColor(color))
            p.drawText(QPointF(x - tw, 17), txt)
            x -= tw + 14
        vals = [v for _, row in self.data for v in row if v is not None]
        if not vals:
            p.setPen(QColor(theme.MUTED))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "no data")
            return
        y0, y1 = min(vals), max(vals)
        if y1 - y0 < self.min_span:
            mid = (y0 + y1) / 2
            y0, y1 = mid - self.min_span / 2, mid + self.min_span / 2
        pad = (y1 - y0) * 0.1
        y0, y1 = y0 - pad, y1 + pad
        now = self.data[-1][0]

        def px(t): return r.right() - (now - t) / self.window * r.width()
        def py(v): return r.bottom() - (v - y0) / (y1 - y0) * r.height()

        for t in _nice_ticks(y0, y1, 4):
            p.setPen(QPen(QColor(theme.BORDER), 1, Qt.PenStyle.DotLine))
            p.drawLine(QPointF(r.left(), py(t)), QPointF(r.right(), py(t)))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(0, py(t) - 8, r.left() - 4, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{t:g}")
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.drawRect(r)
        p.setPen(QColor(theme.MUTED))
        for s in (0, 10, 20, 30):
            if s <= self.window:
                p.drawText(QRectF(r.right() - s / self.window * r.width() - 20, r.bottom() + 2, 40, 14),
                           Qt.AlignmentFlag.AlignCenter, f"-{s}s" if s else "now")
        p.setClipRect(r)
        for i, (_, color) in enumerate(self.series):
            pts = [QPointF(px(t), py(row[i])) for t, row in self.data if row[i] is not None]
            if len(pts) > 1:
                p.setPen(QPen(QColor(color), 2))
                p.drawPolyline(QPolygonF(pts))
