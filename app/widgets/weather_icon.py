from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QWidget

# 与 weather_service.describe_weather 的第二个返回值对应
ICON_KINDS = {
    "sunny", "partly", "cloudy", "fog",
    "rain_light", "rain_moderate", "rain_heavy",
    "snow_light", "snow_heavy", "thunder",
}


class WeatherIcon(QWidget):
    """根据天气类型键绘制矢量图标。"""

    def __init__(self, kind: str, size: int = 48, parent=None):
        super().__init__(parent)
        self._kind = kind if kind in ICON_KINDS else "cloudy"
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def set_kind(self, kind: str):
        self._kind = kind if kind in ICON_KINDS else "cloudy"
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height())
        p.translate(self.width() / 2.0, self.height() / 2.0)
        p.scale(side / 100.0, side / 100.0)
        self._dispatch(p)
        p.end()

    # ---------- 分派 ----------

    def _dispatch(self, p: QPainter):
        k = self._kind
        if k == "sunny":
            self._sun(p, 0, 0, 22)
        elif k == "partly":
            self._sun(p, -12, -14, 16, rays=False)
            self._cloud(p, 8, 8, 1.0)
        elif k == "cloudy":
            self._cloud(p, 0, 0, 1.15)
        elif k == "fog":
            self._cloud(p, 0, -10, 1.0)
            self._fog_lines(p, top=18)
        elif k == "rain_light":
            self._cloud(p, 0, -10, 1.0)
            self._rain(p, count=2)
        elif k == "rain_moderate":
            self._cloud(p, 0, -10, 1.0)
            self._rain(p, count=3)
        elif k == "rain_heavy":
            self._cloud(p, 0, -10, 1.0)
            self._rain(p, count=5)
        elif k == "snow_light":
            self._cloud(p, 0, -10, 1.0)
            self._snow(p, count=3)
        elif k == "snow_heavy":
            self._cloud(p, 0, -10, 1.0)
            self._snow(p, count=5)
        elif k == "thunder":
            self._cloud(p, 0, -12, 1.0)
            self._lightning(p)
        else:
            self._cloud(p, 0, 0, 1.15)

    # ---------- 元素绘制 ----------

    @staticmethod
    def _sun(p: QPainter, cx: float, cy: float, r: float, rays: bool = True):
        p.setPen(QPen(QColor("#F9A825"), 2))
        p.setBrush(QColor("#FFD54F"))
        p.drawEllipse(QPointF(cx, cy), r, r)
        if rays:
            p.setPen(QPen(QColor("#FBC02D"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for angle in range(0, 360, 45):
                p.save()
                p.translate(cx, cy)
                p.rotate(angle)
                p.drawLine(QPointF(0, -r - 6), QPointF(0, -r - 14))
                p.restore()

    @staticmethod
    def _cloud(p: QPainter, cx: float, cy: float, scale: float = 1.0):
        p.save()
        p.translate(cx, cy)
        p.scale(scale, scale)

        path = QPainterPath()
        path.addEllipse(QPointF(-16, 2), 13, 13)

        p2 = QPainterPath()
        p2.addEllipse(QPointF(0, -6), 16, 16)
        path = path.united(p2)

        p3 = QPainterPath()
        p3.addEllipse(QPointF(16, 2), 13, 13)
        path = path.united(p3)

        p4 = QPainterPath()
        p4.addRect(QRectF(-30, 2, 60, 14))
        path = path.united(p4)

        p.setPen(QPen(QColor("#546E7A"), 1.6))
        p.setBrush(QColor("#ECEFF1"))
        p.drawPath(path)
        p.restore()

    @staticmethod
    def _rain(p: QPainter, count: int):
        p.setPen(QPen(QColor("#1E88E5"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        if count <= 2:
            xs = [-12, 12]
        elif count == 3:
            xs = [-16, 0, 16]
        else:
            xs = [-20, -10, 0, 10, 20]
        for x in xs:
            p.drawLine(QPointF(x, 12), QPointF(x - 3, 26))

    @staticmethod
    def _snow(p: QPainter, count: int):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#42A5F5"))
        if count <= 2:
            xs = [-12, 12]
        elif count == 3:
            xs = [-16, 0, 16]
        else:
            xs = [-20, -10, 0, 10, 20]
        for x in xs:
            p.drawEllipse(QPointF(x, 20), 3, 3)

    @staticmethod
    def _fog_lines(p: QPainter, top: float):
        p.setPen(QPen(QColor("#90A4AE"), 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for y, w in [(top, 48), (top + 10, 36), (top + 20, 48)]:
            p.drawLine(QPointF(-w / 2, y), QPointF(w / 2, y))

    @staticmethod
    def _lightning(p: QPainter):
        poly = QPolygonF([
            QPointF(-3, 4), QPointF(7, 4), QPointF(1, 16),
            QPointF(11, 16), QPointF(-6, 38), QPointF(-2, 22),
            QPointF(-12, 22),
        ])
        p.setPen(QPen(QColor("#F57F17"), 1.5))
        p.setBrush(QColor("#FFD600"))
        p.drawPolygon(poly)