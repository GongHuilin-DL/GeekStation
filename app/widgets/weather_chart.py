from PySide6.QtCharts import (
    QCategoryAxis,
    QChart,
    QChartView,
    QLineSeries,
    QValueAxis,
)
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen


class WeatherChart(QChartView):
    """温度折线图：日最高温 + 日最低温。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

        self._chart = QChart()
        self._chart.setTitle("未来天气 · 温度趋势")
        self._chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        self._chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

        self._high_series = QLineSeries()
        self._high_series.setName("最高温")
        pen_high = QPen(QColor("#e67e22"), 2.5)
        self._high_series.setPen(pen_high)

        self._low_series = QLineSeries()
        self._low_series.setName("最低温")
        pen_low = QPen(QColor("#3498db"), 2.5)
        self._low_series.setPen(pen_low)

        self._chart.addSeries(self._high_series)
        self._chart.addSeries(self._low_series)

        self.setChart(self._chart)

        # 轴对象只创建一次，后续 update_data 里只改范围和标签
        self._axis_x = QCategoryAxis()
        self._axis_x.setTitleText("日期")
        self._axis_x.setLabelsPosition(QCategoryAxis.AxisLabelsPosition.AxisLabelsPositionOnValue)

        self._axis_y = QValueAxis()
        self._axis_y.setTitleText("温度 (℃)")
        self._axis_y.setLabelFormat("%.0f")

        self._chart.addAxis(self._axis_x, Qt.AlignmentFlag.AlignBottom)
        self._chart.addAxis(self._axis_y, Qt.AlignmentFlag.AlignLeft)
        self._high_series.attachAxis(self._axis_x)
        self._high_series.attachAxis(self._axis_y)
        self._low_series.attachAxis(self._axis_x)
        self._low_series.attachAxis(self._axis_y)

    def update_data(self, forecast: dict):
        """
        用 fetch_daily_forecast 返回的字典刷新图表。
        forecast 为 None 或字段缺失时，静默清空图表。
        """
        self._high_series.clear()
        self._low_series.clear()

        # 清空旧 X 轴标签（QCategoryAxis 没有 clear，需要移除后重建）
        self._chart.removeAxis(self._axis_x)
        self._axis_x = QCategoryAxis()
        self._axis_x.setTitleText("日期")
        self._axis_x.setLabelsPosition(QCategoryAxis.AxisLabelsPosition.AxisLabelsPositionOnValue)
        self._chart.addAxis(self._axis_x, Qt.AlignmentFlag.AlignBottom)
        self._high_series.attachAxis(self._axis_x)
        self._low_series.attachAxis(self._axis_x)

        if not forecast or not forecast.get("time"):
            self._axis_y.setRange(0, 1)
            return

        times = forecast["time"]
        highs = forecast["temp_max"]
        lows = forecast["temp_min"]

        # 计算 Y 轴范围，上下各留 3℃ 余量
        valid = [v for v in highs + lows if v is not None]
        if valid:
            y_min = min(valid) - 3
            y_max = max(valid) + 3
            self._axis_y.setRange(y_min, y_max)
        else:
            self._axis_y.setRange(0, 1)

        n = len(times)
        for i, (t, hi, lo) in enumerate(zip(times, highs, lows)):
            x = float(i)
            if hi is not None:
                self._high_series.append(QPointF(x, hi))
            if lo is not None:
                self._low_series.append(QPointF(x, lo))
            # 标签只显示月-日，避免拥挤
            label = t[5:] if len(t) >= 10 else t
            self._axis_x.append(label, x)

        self._axis_x.setRange(0, max(n - 1, 1))