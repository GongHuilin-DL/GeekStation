from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services import weather_service
from app.services.cities import CITY_GROUPS
from app.widgets.weather_chart import WeatherChart
from app.widgets.weather_icon import WeatherIcon
from app.workers.weather_worker import WeatherWorker


class WeatherTab(QWidget):
    city_changed = Signal(str)
    summary_ready = Signal(str)

    DAY_OPTIONS = [1, 2, 3, 5, 7, 10, 15]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread_pool = QThreadPool.globalInstance()
        self._thread_pool.setMaxThreadCount(2)
        self._request_id = 0
        self._active_workers: list[WeatherWorker] = []

        self._build_ui()
        self._refresh()

    # ---------- UI ----------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # 控制栏
        control = QHBoxLayout()
        control.setSpacing(10)

        city_label = QLabel("城市：")
        city_label.setStyleSheet("font-size: 10pt; font-weight: 500;")
        control.addWidget(city_label)

        self.city_combo = QComboBox()
        self.city_combo.setEditable(True)
        self.city_combo.setMinimumWidth(150)
        self.city_combo.setStyleSheet("font-size: 10pt; padding: 3px 6px;")
        first = True
        for group, cities in CITY_GROUPS.items():
            if not first:
                self.city_combo.insertSeparator(self.city_combo.count())
            first = False
            for c in cities:
                self.city_combo.addItem(c)
        self.city_combo.setCurrentText("北京")
        self.city_combo.currentTextChanged.connect(self._on_city_or_days_changed)
        control.addWidget(self.city_combo)

        control.addSpacing(20)
        days_label = QLabel("预报天数：")
        days_label.setStyleSheet("font-size: 10pt; font-weight: 500;")
        control.addWidget(days_label)

        self.days_combo = QComboBox()
        self.days_combo.setStyleSheet("font-size: 10pt; padding: 3px 6px;")
        for d in self.DAY_OPTIONS:
            self.days_combo.addItem(f"{d} 天", d)
        self.days_combo.setCurrentIndex(self.DAY_OPTIONS.index(7))
        self.days_combo.currentIndexChanged.connect(self._on_city_or_days_changed)
        control.addWidget(self.days_combo)

        control.addStretch()
        root.addLayout(control)

        # 今日摘要（移除写死颜色）
        self.today_label = QLabel("正在获取天气数据…")
        self.today_label.setStyleSheet(
            "font-size: 15px; font-weight: 600;"
        )
        root.addWidget(self.today_label)

        # 折线图
        self.chart = WeatherChart()
        self.chart.setMinimumHeight(280)
        root.addWidget(self.chart, stretch=1)

        # 每日天气卡片行（横向可滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(120)
        scroll.setStyleSheet("QScrollArea { background: transparent; } QWidget#scrollContent { background: transparent; }")

        self.weather_inner = QWidget()
        self.weather_inner.setObjectName("scrollContent")
        self.weather_row = QHBoxLayout(self.weather_inner)
        self.weather_row.setContentsMargins(0, 0, 0, 0)
        self.weather_row.setSpacing(6)
        self.weather_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self.weather_inner)
        root.addWidget(scroll)

    # ---------- 交互 ----------

    def set_city(self, city: str):
        """供外部（如顶部栏）切换城市。"""
        city = city.strip()
        if not city:
            return
        idx = self.city_combo.findText(city)
        if idx >= 0:
            self.city_combo.setCurrentIndex(idx)
        else:
            self.city_combo.setEditText(city)
            self._refresh()

    def _on_city_or_days_changed(self, *_):
        self._refresh()

    def _get_selected_city(self) -> str:
        return self.city_combo.currentText().strip()

    def _refresh(self):
        city = self._get_selected_city()
        if not city:
            return
        days = self.days_combo.currentData()

        self._request_id += 1
        rid = self._request_id

        self.today_label.setText(f"正在获取「{city}」的天气数据…")
        self.today_label.setStyleSheet("font-size: 15px;")

        worker = WeatherWorker(city, days)
        worker.signals.finished.connect(
            lambda result, rid=rid, w=worker: self._on_worker_finished(result, rid, w)
        )
        self._active_workers.append(worker)
        self._thread_pool.start(worker)

    def _on_worker_finished(self, result: dict, request_id: int, worker: WeatherWorker):
        if worker in self._active_workers:
            self._active_workers.remove(worker)

        if request_id != self._request_id:
            return

        if result["error"]:
            self.today_label.setText(f"⚠ {result['error']}")
            self.today_label.setStyleSheet(
                "color: #D32F2F; font-size: 15px; font-weight: 600;" # 错误提示保留红色
            )
            self.chart.update_data(None)
            self._clear_weather_cards()
            return

        forecast = result["forecast"]
        self.chart.update_data(forecast)
        self._update_today_summary(forecast)
        self._render_weather_cards(forecast)
        self.city_changed.emit(result["city"])

    # ---------- 今日摘要 ----------

    def _update_today_summary(self, forecast: dict):
        if not forecast["time"]:
            self.today_label.setText("暂无数据")
            return
        code = forecast["weather_code"][0]
        desc, _ = weather_service.describe_weather(code)
        hi = forecast["temp_max"][0]
        lo = forecast["temp_min"][0]
        wind = forecast["wind_max"][0]

        text = f"今日：{desc}   {lo:.0f} ~ {hi:.0f} ℃"
        if wind is not None:
            text += f"   最大风速 {wind:.0f} km/h"

        self.today_label.setText(text)
        self.today_label.setStyleSheet(
            "font-size: 15px; font-weight: 600;" # 移除硬编码蓝色
        )
        self.summary_ready.emit(text)

    # ---------- 每日天气卡片 ----------

    def _render_weather_cards(self, forecast: dict):
        self._clear_weather_cards()
        n = len(forecast["time"])
        icon_size = 42 if n <= 7 else 34

        for i in range(n):
            code = forecast["weather_code"][i]
            desc, kind = weather_service.describe_weather(code)
            hi = forecast["temp_max"][i]
            lo = forecast["temp_min"][i]
            date_str = forecast["time"][i][5:]

            card = QWidget()
            card.setFixedWidth(76)
            v = QVBoxLayout(card)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(4)

            icon = WeatherIcon(kind, size=icon_size)
            icon.setToolTip(desc)
            v.addWidget(icon, alignment=Qt.AlignmentFlag.AlignHCenter)

            temp = QLabel(f"{lo:.0f}~{hi:.0f}°")
            temp.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # 移除硬编码深色字体
            temp.setStyleSheet("font-size: 13px; font-weight: bold;")
            v.addWidget(temp)

            day = QLabel(date_str)
            day.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # 移除硬编码浅灰色字体
            day.setStyleSheet("font-size: 12px;")
            v.addWidget(day)

            self.weather_row.addWidget(card)

    def _clear_weather_cards(self):
        while self.weather_row.count():
            item = self.weather_row.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()