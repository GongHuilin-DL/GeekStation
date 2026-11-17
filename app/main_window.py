from app.tabs.calendar_tab import CalendarTab
from app.tabs.command_tab import CommandTab
from app.tabs.snippet_tab import SnippetTab
from app.tabs.path_tab import PathTab
from app.tabs.note_tab import NoteTab
from app.tabs.system_tab import SystemTab
from app.tabs.formatter_tab import FormatterTab
from app.tabs.diff_tab import DiffTab
from app.tabs.translate_tab import TranslateTab
from app.tabs.navigation_tab import NavigationTab
from app.tabs.security_tab import SecurityTab
from app.tabs.image_viewer_tab import ImageViewerTab
from app.tabs.m3u8_tab import M3U8Tab
from app.tabs.merge_tab import MergeTab
from app.tabs.short_video_tab import ShortVideoTab
from app.tabs.scrcpy_tab import ScrcpyTab
from app.tabs.env_detect_tab import EnvDetectTab
from app.tabs.video_player_tab import VideoPlayerTab

from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from app.services.cities import all_city_names
from app.tabs.weather_tab import WeatherTab
from app.widgets.analog_clock import AnalogClock


class MainWindow(QMainWindow):
    TAB_NAMES = ["天气", "日历", "命令管理", "文本片段", "路径快捷", "便签", "网址导航", "系统工具"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("日常工具集中台")

        # 修改为更安全的初始尺寸，防止在 1080p 屏幕上触发 Windows 几何报警
        self.resize(1366, 768) 
        self.setMinimumSize(1024, 600) # 设置合理的最小尺寸
        
        self._build_ui()

        # --- 绑定 ESC 键退出 ---
        self.esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.esc_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.esc_shortcut.activated.connect(self._confirm_exit)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        root.addWidget(self._build_top_bar())
        root.addWidget(self._build_tabs(), stretch=1)
        self.statusBar().showMessage("就绪")

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("topBar")
        # 去除写死的背景色，改用边框，由全局 Palette 接管背景
        bar.setStyleSheet(
            """
            #topBar {
                border: 1px solid #cddcea;
                border-radius: 8px;
            }
            """
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 10, 14, 10)

        left = QVBoxLayout()
        left.setSpacing(4)

        city_row = QHBoxLayout()
        city_row.setSpacing(6)
        
        city_title = QLabel("当前城市：")
        city_title.setStyleSheet("font-size: 10pt; font-weight: 500;")
        city_row.addWidget(city_title)

        self.top_city_combo = QComboBox()
        self.top_city_combo.setEditable(True)
        self.top_city_combo.setMinimumWidth(160)
        self.top_city_combo.setStyleSheet("font-size: 10pt; padding: 2px 6px;")
        self.top_city_combo.addItems(all_city_names())
        self.top_city_combo.setCurrentText("北京")
        self.top_city_combo.currentTextChanged.connect(self._on_top_city_changed)
        city_row.addWidget(self.top_city_combo)
        city_row.addStretch()
        left.addLayout(city_row)

        self.top_weather_label = QLabel("天气数据加载中…")
        self.top_weather_label.setStyleSheet(
            "font-size: 15px; font-weight: 600;" # 去除写死的颜色
        )
        left.addWidget(self.top_weather_label)
        layout.addLayout(left, stretch=1)

        self.clock = AnalogClock()
        layout.addWidget(
            self.clock,
            alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        return bar

    def _build_tabs(self) -> QTabWidget:
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            """
            QTabBar::tab {
                padding: 8px 16px;
                font-size: 10pt;
            }
            QTabBar::tab:selected {
                font-weight: bold;
            }
            """
        )

        self.weather_tab = WeatherTab()
        self.weather_tab.city_changed.connect(self._on_weather_city_changed)
        self.weather_tab.summary_ready.connect(self._on_weather_summary)

        self.env_detect_tab = EnvDetectTab()
        self.tabs.addTab(self.env_detect_tab, "AI环境诊断")
        
        self.tabs.addTab(self.weather_tab, "天气")

        self.calendar_tab = CalendarTab()
        self.tabs.addTab(self.calendar_tab, "日历")

        self.command_tab = CommandTab()
        self.tabs.addTab(self.command_tab, "命令管理")

        self.snippet_tab = SnippetTab()
        self.tabs.addTab(self.snippet_tab, "文本片段")

        self.path_tab = PathTab()
        self.tabs.addTab(self.path_tab, "路径快捷")

        self.note_tab = NoteTab()
        self.tabs.addTab(self.note_tab, "便签")

        self.formatter_tab = FormatterTab()
        self.tabs.addTab(self.formatter_tab, "文本格式化")

        self.diff_tab = DiffTab()
        self.tabs.addTab(self.diff_tab, "文本比较")

        self.translate_tab = TranslateTab()
        self.tabs.addTab(self.translate_tab, "在线翻译")

        self.navigation_tab = NavigationTab()
        self.tabs.addTab(self.navigation_tab, "网址导航")

        self.security_tab = SecurityTab()
        self.tabs.addTab(self.security_tab, "文件安全")

        self.image_viewer_tab = ImageViewerTab()
        self.tabs.addTab(self.image_viewer_tab, "图片查看")

        self.m3u8_tab = M3U8Tab()
        self.tabs.addTab(self.m3u8_tab, "m3u8下载")

        self.merge_tab = MergeTab()
        self.tabs.addTab(self.merge_tab, "ts合并")

        self.video_player_tab = VideoPlayerTab()
        self.tabs.addTab(self.video_player_tab, "视频播放")

        self.short_video_tab = ShortVideoTab()
        self.tabs.addTab(self.short_video_tab, "短视频下载")

        self.scrcpy_tab = ScrcpyTab()
        self.tabs.addTab(self.scrcpy_tab, "scrcpy投屏")

        self.system_tab = SystemTab()
        self.tabs.addTab(self.system_tab, "系统工具")

        return self.tabs

    def _on_top_city_changed(self, city: str):
        city = city.strip()
        if city:
            self.weather_tab.set_city(city)

    def _on_weather_city_changed(self, city: str):
        self.top_city_combo.blockSignals(True)
        self.top_city_combo.setCurrentText(city)
        self.top_city_combo.blockSignals(False)

    def _on_weather_summary(self, summary: str):
        self.top_weather_label.setText(summary)

    @staticmethod
    def _build_placeholder_page(name: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(f"【{name}】模块 · 待实现")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 14px;")
        layout.addWidget(label)
        return page

    def _confirm_exit(self):
        """ESC 键触发的退出请求（统一由 closeEvent 处理弹窗）"""
        self.close()

    def closeEvent(self, event):
        """主窗口关闭时，拦截并弹出确认框，确认后安全释放子模块资源。"""
        reply = QMessageBox.question(
            self, 
            "确认退出", 
            "确定要退出整个工具箱程序吗？\n（所有后台任务将被停止）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            event.ignore()
            return

        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if hasattr(widget, 'shutdown'):
                try:
                    widget.shutdown()
                except Exception as e:
                    print(f"Shutdown error in tab {i}: {e}")
                    
        event.accept()