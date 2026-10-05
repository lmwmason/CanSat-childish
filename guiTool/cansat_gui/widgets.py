import math

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

from . import theme
from .protocol import STATES


class Tile(QFrame):
    """Small labelled value box (like Mission Planner's HUD read-outs)."""

    def __init__(self, title: str, value: str = "--", parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(0)
        self._title = QLabel(title.upper())
        self._title.setStyleSheet(f"color:{theme.MUTED}; font-size:9pt; font-weight:bold;")
        self._value = QLabel(value)
        self._value.setStyleSheet("font-size:20pt; font-weight:bold;")
        lay.addWidget(self._title)
        lay.addWidget(self._value)

    def set_value(self, text: str, color: str = theme.TEXT) -> None:
        self._value.setText(text)
        self._value.setStyleSheet(f"font-size:20pt; font-weight:bold; color:{color};")


class HealthLed(QWidget):
    """Sensor health indicator: grey unknown, green OK, red fault."""

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.ok: bool | None = None
        self.setMinimumSize(110, 56)

    def set_ok(self, ok: bool | None) -> None:
        self.ok = ok
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = QColor(theme.MUTED if self.ok is None else theme.ACCENT if self.ok else theme.RED)
        p.setPen(Qt.PenStyle.NoPen)
        glow = QColor(col)
        glow.setAlpha(60)
        p.setBrush(glow)
        p.drawEllipse(QPointF(22, self.height() / 2), 14, 14)
        p.setBrush(col)
        p.drawEllipse(QPointF(22, self.height() / 2), 8, 8)
        p.setPen(QColor(theme.TEXT))
        f = QFont(self.font())
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(44, 6, self.width() - 44, 24), Qt.AlignmentFlag.AlignVCenter, self.name)
        p.setPen(col)
        p.setFont(self.font())
        label = "--" if self.ok is None else "OK" if self.ok else "FAULT"
        p.drawText(QRectF(44, 28, self.width() - 44, 22), Qt.AlignmentFlag.AlignVCenter, label)


class StateBar(QWidget):
    """BOOT > ARMED > DESCENT > LANDED chevron pipeline."""

    def __init__(self, names=STATES, parent=None):
        super().__init__(parent)
        self.names = tuple(names)
        self.current: str | None = None
        self.setMinimumHeight(54)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_state(self, state: str | None) -> None:
        self.current = state
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        n = len(self.names)
        w = self.width() / n
        h = self.height() - 4
        tip = 16
        cur = self.names.index(self.current) if self.current in self.names else -1
        f = QFont(self.font())
        f.setBold(True)
        p.setFont(f)
        for i, name in enumerate(self.names):
            x = i * w
            poly = QPolygonF([QPointF(x, 2), QPointF(x + w - tip, 2), QPointF(x + w, 2 + h / 2),
                              QPointF(x + w - tip, 2 + h), QPointF(x, 2 + h),
                              QPointF(x + tip, 2 + h / 2)])
            if i == cur:
                fill, fg = QColor(theme.STATE_COLORS[name]), QColor("#0b0d10")
            elif 0 <= cur and i < cur:
                fill, fg = QColor(theme.PANEL_HI), QColor(theme.TEXT)
            else:
                fill, fg = QColor(theme.PANEL), QColor(theme.MUTED)
            p.setPen(QPen(QColor(theme.BG), 3))
            p.setBrush(fill)
            p.drawPolygon(poly)
            p.setPen(fg)
            p.drawText(QRectF(x, 2, w, h), Qt.AlignmentFlag.AlignCenter, name)


def _nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    span = hi - lo
    if span <= 0:
        return [lo]
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    t = math.ceil(lo / step) * step
    out = []
    while t <= hi + 1e-9:
        out.append(round(t, 10))
        t += step
    return out


class PlotWidget(QWidget):
    """Minimal line plot with grid, auto-scaling and a hover cursor.

    The cursor is expressed as a sample index so several plots can stay in sync.
    """

    cursorChanged = pyqtSignal(int)

    def __init__(self, title: str, unit: str, color: str, parent=None):
        super().__init__(parent)
        self.title, self.unit, self.color = title, unit, QColor(color)
        self.xs: list[float] = []
        self.ys: list[float] = []
        self.cursor = -1
        self.setMouseTracking(True)
        self.setMinimumHeight(110)

    def set_data(self, xs: list[float], ys: list[float]) -> None:
        self.xs, self.ys, self.cursor = xs, ys, -1
        self.update()

    def set_cursor(self, i: int) -> None:
        self.cursor = i
        self.update()

    def _plot_rect(self) -> QRectF:
        return QRectF(56, 22, max(self.width() - 72, 10), max(self.height() - 40, 10))

    def mouseMoveEvent(self, e):
        if not self.xs:
            return
        r = self._plot_rect()
        x0, x1 = self.xs[0], self.xs[-1]
        fx = (e.position().x() - r.left()) / r.width()
        target = x0 + min(max(fx, 0.0), 1.0) * (x1 - x0)
        i = min(range(len(self.xs)), key=lambda k: abs(self.xs[k] - target))
        self.cursorChanged.emit(i)

    def leaveEvent(self, _):
        self.cursorChanged.emit(-1)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(theme.PANEL))
        r = self._plot_rect()
        p.setPen(QColor(theme.TEXT))
        f = QFont(self.font())
        f.setBold(True)
        p.setFont(f)
        p.drawText(8, 16, f"{self.title} [{self.unit}]" if self.unit else self.title)
        p.setFont(self.font())
        if len(self.xs) < 1:
            p.setPen(QColor(theme.MUTED))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "no data")
            return

        x0, x1 = self.xs[0], self.xs[-1]
        if x1 <= x0:
            x1 = x0 + 1
        y0, y1 = min(self.ys), max(self.ys)
        if y1 - y0 < 1e-9:
            y0, y1 = y0 - 1, y1 + 1
        pad = (y1 - y0) * 0.08
        y0, y1 = y0 - pad, y1 + pad

        def px(x): return r.left() + (x - x0) / (x1 - x0) * r.width()
        def py(y): return r.bottom() - (y - y0) / (y1 - y0) * r.height()

        small = QFont(self.font())
        small.setPointSize(8)
        p.setFont(small)
        for t in _nice_ticks(y0, y1):
            p.setPen(QPen(QColor(theme.BORDER), 1, Qt.PenStyle.DotLine))
            p.drawLine(QPointF(r.left(), py(t)), QPointF(r.right(), py(t)))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(0, py(t) - 8, r.left() - 4, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{t:g}")
        for t in _nice_ticks(x0, x1, 8):
            p.setPen(QPen(QColor(theme.BORDER), 1, Qt.PenStyle.DotLine))
            p.drawLine(QPointF(px(t), r.top()), QPointF(px(t), r.bottom()))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(px(t) - 25, r.bottom() + 2, 50, 14), Qt.AlignmentFlag.AlignCenter, f"{t:g}")
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.drawRect(r)

        p.setPen(QPen(self.color, 2))
        pts = [QPointF(px(x), py(y)) for x, y in zip(self.xs, self.ys)]
        if len(pts) == 1:
            p.setBrush(self.color)
            p.drawEllipse(pts[0], 3, 3)
        else:
            p.drawPolyline(QPolygonF(pts))

        if 0 <= self.cursor < len(pts):
            c = pts[self.cursor]
            p.setPen(QPen(QColor(theme.TEXT), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(c.x(), r.top()), QPointF(c.x(), r.bottom()))
            p.setBrush(self.color)
            p.drawEllipse(c, 4, 4)
            p.setFont(self.font())
            p.setPen(QColor(theme.TEXT))
            txt = f"{self.ys[self.cursor]:g} {self.unit}  @ {self.xs[self.cursor]:g}"
            p.drawText(QRectF(r.left(), 2, r.width(), 18),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, txt)
