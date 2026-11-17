import math

from PySide6.QtCore import QPointF, QRectF, QTime, QTimer, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


class AnalogClock(QWidget):
    """圆形模拟时钟控件，每秒刷新一次。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(160, 160)
        self._time = QTime.currentTime()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(1000)  # 每秒刷新

    def _on_tick(self):
        self._time = QTime.currentTime()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 以控件中心为原点，并把坐标缩放到 200x200 的逻辑画布
        side = min(self.width(), self.height())
        painter.translate(self.width() / 2.0, self.height() / 2.0)
        painter.scale(side / 200.0, side / 200.0)

        self._draw_face(painter)
        self._draw_ticks(painter)
        self._draw_numbers(painter)
        self._draw_hands(painter)
        self._draw_center(painter)

        painter.end()

    # ---------- 绘制细节 ----------

    def _draw_face(self, painter: QPainter):
        painter.setPen(QPen(QColor("#4a90d9"), 3))
        painter.setBrush(QBrush(QColor("#f8fbff")))
        painter.drawEllipse(QPointF(0, 0), 95, 95)

        painter.setPen(QPen(QColor("#c9d9e8"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(0, 0), 88, 88)

    def _draw_ticks(self, painter: QPainter):
        for i in range(60):
            painter.save()
            painter.rotate(6 * i)  # 每个刻度 6 度，顺时针
            if i % 5 == 0:
                # 整点刻度：粗、长、深色
                painter.setPen(QPen(QColor("#2c3e50"), 2.5))
                painter.drawLine(QPointF(0, -86), QPointF(0, -78))
            else:
                # 分钟刻度：细、短、浅色
                painter.setPen(QPen(QColor("#9bb0c4"), 1))
                painter.drawLine(QPointF(0, -86), QPointF(0, -82))
            painter.restore()

    # def _draw_numbers(self, painter: QPainter):
    #     font = QFont("Segoe UI", 10)
    #     font.setWeight(QFont.Weight.Bold)
    #     painter.setFont(font)
    #     painter.setPen(QPen(QColor("#2c3e50")))

    #     for i in range(1, 13):
    #         rad = math.radians(30 * i)
    #         x = 68 * math.sin(rad)
    #         y = -68 * math.cos(rad)
    #         rect = QRectF(x - 12, y - 12, 24, 24)
    #         painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(i))

    def _draw_numbers(self, painter: QPainter):
        # 改用先实例化，再 setPointSize 的方式
        font = QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(10)
        font.setWeight(QFont.Weight.Bold)
        
        painter.setFont(font)
        painter.setPen(QPen(QColor("#2c3e50")))

        for i in range(1, 13):
            rad = math.radians(30 * i)
            x = 68 * math.sin(rad)
            y = -68 * math.cos(rad)
            rect = QRectF(x - 12, y - 12, 24, 24)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(i))

    def _draw_hands(self, painter: QPainter):
        hour = self._time.hour() % 12
        minute = self._time.minute()
        second = self._time.second()

        # 时针：30°/小时 + 0.5°/分钟
        painter.save()
        painter.rotate(30.0 * hour + 0.5 * minute)
        pen = QPen(QColor("#1a2b3c"), 6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(0, 8), QPointF(0, -45))
        painter.restore()

        # 分针：6°/分钟 + 0.1°/秒
        painter.save()
        painter.rotate(6.0 * minute + 0.1 * second)
        pen = QPen(QColor("#34495e"), 4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(0, 10), QPointF(0, -68))
        painter.restore()

        # 秒针：6°/秒
        painter.save()
        painter.rotate(6.0 * second)
        pen = QPen(QColor("#e74c3c"), 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(0, 18), QPointF(0, -78))
        painter.restore()

    def _draw_center(self, painter: QPainter):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#e74c3c")))
        painter.drawEllipse(QPointF(0, 0), 4.5, 4.5)

        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawEllipse(QPointF(0, 0), 1.8, 1.8)