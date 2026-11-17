from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.services.calendar_service import get_date_info, get_month_festivals


class CalendarTab(QWidget):
    """日历选项卡：左侧日历，右侧详情。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        
        # 首次加载当前月份的标记
        today = QDate.currentDate()
        self._update_month_format(today.year(), today.month())
        
        # 选中今天
        self.calendar.setSelectedDate(today)
        self._on_date_selected()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(15)

        # ================= 左侧：日历 =================
        left_layout = QVBoxLayout()
        
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        
        # 放大日历字体
        cal_font = QFont()
        cal_font.setPointSize(11)
        self.calendar.setFont(cal_font)
        
        # 设置简单的样式
        self.calendar.setStyleSheet("""
            QCalendarWidget QWidget {
                alternate-background-color: #F5F7FA;
            }
            QCalendarWidget QAbstractItemView:enabled {
                font-size: 14px;
                color: #212121;
                selection-background-color: #1565C0;
                selection-color: white;
            }
            QCalendarWidget QToolButton {
                font-size: 14px;
                font-weight: bold;
                color: #212121;
            }
            QCalendarWidget QSpinBox {
                font-size: 14px;
            }
        """)
        
        self.calendar.selectionChanged.connect(self._on_date_selected)
        # 切换月份时，重新加载该月节日标记
        self.calendar.currentPageChanged.connect(self._update_month_format)
        
        left_layout.addWidget(self.calendar)
        root.addLayout(left_layout, stretch=1)

        # ================= 右侧：详情面板 =================
        self.detail_frame = QFrame()
        self.detail_frame.setFixedWidth(320)
        self.detail_frame.setStyleSheet("""
            #detailFrame {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
        """)
        self.detail_frame.setObjectName("detailFrame")
        
        detail_layout = QVBoxLayout(self.detail_frame)
        detail_layout.setContentsMargins(20, 20, 20, 20)
        detail_layout.setSpacing(15)

        # 阳历大字号
        self.lbl_solar = QLabel("2026-11-12")
        self.lbl_solar.setStyleSheet("font-size: 26px; font-weight: bold; color: #0D47A1;")
        detail_layout.addWidget(self.lbl_solar)

        # 星期
        self.lbl_week = QLabel("星期四")
        self.lbl_week.setStyleSheet("font-size: 14px; color: #546E7A;")
        detail_layout.addWidget(self.lbl_week)

        detail_layout.addSpacing(10)

        # 农历 + 生肖
        self.lbl_lunar = QLabel("农历 十月初一")
        self.lbl_lunar.setStyleSheet("font-size: 16px; font-weight: bold; color: #212121;")
        detail_layout.addWidget(self.lbl_lunar)
        
        self.lbl_zodiac = QLabel("丙午年 马年")
        self.lbl_zodiac.setStyleSheet("font-size: 14px; color: #757575;")
        detail_layout.addWidget(self.lbl_zodiac)

        detail_layout.addSpacing(15)

        # 节日 / 假期 标签
        self.lbl_holiday = QLabel("")
        self.lbl_holiday.setWordWrap(True)
        self.lbl_holiday.setStyleSheet("font-size: 14px; font-weight: bold; color: #D32F2F;")
        detail_layout.addWidget(self.lbl_holiday)

        detail_layout.addStretch()
        root.addWidget(self.detail_frame)

    # ---------- 交互逻辑 ----------

    def _on_date_selected(self):
        qdate = self.calendar.selectedDate()
        year, month, day = qdate.year(), qdate.month(), qdate.day()

        info = get_date_info(year, month, day)

        self.lbl_solar.setText(f"{year}年{month}月{day}日")
        self.lbl_week.setText(info["week_str"])
        self.lbl_lunar.setText(f"农历 {info['lunar_month']}{info['lunar_day']}")
        self.lbl_zodiac.setText(f"{info['zodiac']} · {info['jieqi'] if info['jieqi'] else '无节气'}")

        # 组装节日、假期信息
        tags = []
        if info["is_workday"]:
            tags.append("【调休上班】")
        elif info["is_holiday"]:
            tags.append(f"【休假：{info['holiday_name']}】")
            
        if info["festivals"]:
            tags.extend(info["festivals"])

        if tags:
            self.lbl_holiday.setText(" · ".join(tags))
            if info["is_holiday"] or info["is_workday"]:
                self.lbl_holiday.setStyleSheet("font-size: 15px; font-weight: bold; color: #D32F2F;")
            else:
                self.lbl_holiday.setStyleSheet("font-size: 14px; font-weight: bold; color: #F57C00;")
        else:
            self.lbl_holiday.setText("普通工作日" if not info["is_weekend"] else "周末")

    def _update_month_format(self, year: int, month: int):
        """更新日历网格，把有节日的日期标红，周末标蓝。"""
        # 每次切换月份，先清除旧的格式
        self.calendar.setDateTextFormat(QDate(), QTextCharFormat())

        month_data = get_month_festivals(year, month)

        # 1. 标记周末
        import calendar
        _, days_in_month = calendar.monthrange(year, month)
        weekend_format = QTextCharFormat()
        weekend_format.setForeground(QColor("#D32F2F")) # 周末红
        for day in range(1, days_in_month + 1):
            date = QDate(year, month, day)
            # 0=Monday, 5=Saturday, 6=Sunday
            if date.dayOfWeek() in (6, 7):
                self.calendar.setDateTextFormat(date, weekend_format)

        # 2. 标记节日 / 节气
        festival_format = QTextCharFormat()
        festival_format.setFontWeight(QFont.Weight.Bold)
        festival_format.setForeground(QColor("#0D47A1")) # 节日用深蓝加粗

        for day, tags in month_data.items():
            date = QDate(year, month, day)
            # 如果是法定假期，直接加背景色
            info = get_date_info(year, month, day)
            if info["is_holiday"]:
                festival_format.setBackground(QColor("#FFF59D")) # 浅黄背景
            self.calendar.setDateTextFormat(date, festival_format)