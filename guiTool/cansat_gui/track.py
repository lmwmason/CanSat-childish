"""Top-down ground track (north up) with the home point and the loiter circle."""
import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from . import theme

M_PER_DEG = 111320.0
MAX_POINTS = 6000


def _nice(span: float) -> float:
    """Grid step (m) for a visible span."""
    raw = span / 5
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


class TrackView(QWidget):
    def __init__(self, loiter_radius: float = 50.0, parent=None):
        super().__init__(parent)
        self.radius = loiter_radius
        self.origin: tuple[float, float] | None = None
        self.pts: list[tuple[float, float]] = []
        self.home: tuple[float, float] | None = None
        self.heading = 0.0
        self.setMinimumSize(300, 260)

    def clear(self) -> None:
        self.origin = None
        self.pts.clear()
        self.home = None
        self.update()

    def _xy(self, lat: float, lon: float) -> tuple[float, float]:
        if self.origin is None:
            self.origin = (lat, lon)
        return ((lon - self.origin[1]) * M_PER_DEG * math.cos(math.radians(self.origin[0])),
                (lat - self.origin[0]) * M_PER_DEG)

    def push(self, lat: float, lon: float, heading: float) -> None:
        if abs(lat) < 1e-6 and abs(lon) < 1e-6:
            return                              # no fix yet
        p = self._xy(lat, lon)
        if not self.pts or self.pts[-1] != p:
            self.pts.append(p)
            if len(self.pts) > MAX_POINTS:
                del self.pts[:1000]
        self.heading = heading
        self.update()

    def set_home(self, lat: float | None, lon: float | None) -> None:
        self.home = None if lat is None else self._xy(lat, lon)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(theme.PANEL))
        r = QRectF(8, 8, self.width() - 16, self.height() - 16)
        f = QFont(self.font())
        f.setPointSize(8)
        p.setFont(f)
        if not self.pts:
            p.setPen(QColor(theme.MUTED))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "waiting for GPS fix")
            return

        xs = [q[0] for q in self.pts]
        ys = [q[1] for q in self.pts]
        if self.home:
            xs += [self.home[0] - self.radius, self.home[0] + self.radius]
            ys += [self.home[1] - self.radius, self.home[1] + self.radius]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        span = max(max(xs) - min(xs), max(ys) - min(ys), 120.0) * 1.2
        scale = min(r.width(), r.height()) / span            # px per metre

        def px(x, y):
            return QPointF(r.center().x() + (x - cx) * scale, r.center().y() - (y - cy) * scale)

        # grid
        step = _nice(span)
        p.setPen(QPen(QColor(theme.BORDER), 1))
        x = math.floor((cx - span / 2) / step) * step
        while x <= cx + span / 2:
            p.drawLine(px(x, cy - span), px(x, cy + span))
            x += step
        y = math.floor((cy - span / 2) / step) * step
        while y <= cy + span / 2:
            p.drawLine(px(cx - span, y), px(cx + span, y))
            y += step

        if self.home:
            hp = px(*self.home)
            pen = QPen(QColor(theme.ACCENT), 1.5, Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(hp, self.radius * scale, self.radius * scale)
            p.setPen(QPen(QColor(theme.ACCENT), 2))
            p.drawLine(QPointF(hp.x() - 6, hp.y()), QPointF(hp.x() + 6, hp.y()))
            p.drawLine(QPointF(hp.x(), hp.y() - 6), QPointF(hp.x(), hp.y() + 6))
            p.drawText(QPointF(hp.x() + 8, hp.y() - 6), "HOME")

        # path
        p.setPen(QPen(QColor(theme.BLUE), 2))
        for a, b in zip(self.pts, self.pts[1:]):
            p.drawLine(px(*a), px(*b))

        # aircraft
        pos = px(*self.pts[-1])
        h = math.radians(self.heading)
        d = QPointF(math.sin(h), -math.cos(h))
        n = QPointF(-d.y(), d.x())
        tri = QPolygonF([pos + d * 11, pos - d * 7 + n * 6, pos - d * 7 - n * 6])
        p.setPen(QPen(QColor("#07101f"), 1))
        p.setBrush(QColor(theme.ORANGE))
        p.drawPolygon(tri)

        # scale bar + north arrow
        bar = step * scale
        y0 = r.bottom() - 6
        p.setPen(QPen(QColor(theme.TEXT), 2))
        p.drawLine(QPointF(r.left() + 6, y0), QPointF(r.left() + 6 + bar, y0))
        p.setPen(QColor(theme.TEXT))
        p.drawText(QPointF(r.left() + 10 + bar, y0 + 4), f"{step:g} m")
        p.drawText(QPointF(r.right() - 14, r.top() + 14), "N")
        p.setPen(QPen(QColor(theme.TEXT), 2))
        p.drawLine(QPointF(r.right() - 10, r.top() + 34), QPointF(r.right() - 10, r.top() + 18))
