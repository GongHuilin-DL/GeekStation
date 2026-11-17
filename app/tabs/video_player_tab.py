import os
import json
from PySide6.QtCore import Qt, QUrl, QSize, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider,
    QLabel, QFileDialog, QStyle, QSplitter, QListWidget, 
    QListWidgetItem, QComboBox, QMenu, QAbstractItemView, 
    QMessageBox, QInputDialog, QLineEdit, QDialog, QFormLayout, 
    QCheckBox, QDialogButtonBox
)
from PySide6.QtGui import QColor, QKeySequence, QFont, QShortcut
from PySide6.QtNetwork import QNetworkProxy, QNetworkProxyFactory

from app.utils.storage import load_json, save_json, get_base_dir
from app.players.qt_adapter import QtPlayerAdapter
from app.players.mpv_adapter import MpvPlayerAdapter

# DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DATA_DIR = get_base_dir()
PLAYLIST_FILE = os.path.join(DATA_DIR, "data", "video_playlist.json")
CONFIG_FILE = os.path.join(DATA_DIR, "data", "video_player_config.json") 

SUPPORTED_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.ts', '.webm', '.m4v', '.mpg', '.mpeg'}

# ==================== 代理设置对话框 ====================
class ProxyDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("网络代理设置")
        self.setMinimumWidth(450)
        self.config = config

        layout = QVBoxLayout(self)
        
        # 1. 启用开关
        self.cb_enable = QCheckBox("启用网络代理 (仅在播放网络流时生效)")
        self.cb_enable.setChecked(config.get("enable_proxy", False))
        layout.addWidget(self.cb_enable)
        
        form = QFormLayout()
        
        # 2. HTTP 代理
        self.input_http = QLineEdit(config.get("http_proxy", "http://127.0.0.1:7890"))
        self.input_http.setPlaceholderText("例如: http://127.0.0.1:7890")
        form.addRow("HTTP 代理:", self.input_http)
        
        # 3. HTTPS 代理
        self.input_https = QLineEdit(config.get("https_proxy", "http://127.0.0.1:7890"))
        self.input_https.setPlaceholderText("留空则自动复用 HTTP 代理地址")
        form.addRow("HTTPS 代理:", self.input_https)
        
        # 4. SOCKS5 代理
        self.input_socks5 = QLineEdit(config.get("socks5_proxy", ""))
        self.input_socks5.setPlaceholderText("例如: socks5://127.0.0.1:7891 (可选)")
        form.addRow("SOCKS5 代理:", self.input_socks5)
        
        layout.addLayout(form)

        # 提示信息
        tip = QLabel("提示：\n1. 勾选启用后，若 HTTPS 留空，将自动使用 HTTP 代理。\n2. 大多数代理软件（如 Clash）只需填 HTTP 即可同时代理 HTTPS。\n3. 关闭代理时，所有环境变量将被清空。")
        tip.setStyleSheet("color: #757575; font-size: 10pt;")
        layout.addWidget(tip)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _accept(self):
        self.config["enable_proxy"] = self.cb_enable.isChecked()
        self.config["http_proxy"] = self.input_http.text().strip()
        
        # 如果 HTTPS 未填写，但 HTTP 填了，自动复用 HTTP 的配置
        https_val = self.input_https.text().strip()
        if not https_val and self.config["http_proxy"]:
            https_val = self.config["http_proxy"]
        self.config["https_proxy"] = https_val
        
        self.config["socks5_proxy"] = self.input_socks5.text().strip()
        self.accept()
        

# ==================== 主播放器组件 ====================
class VideoPlayerTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 1. 状态变量初始化
        self._playlist_data = []
        self._current_index = -1
        self._is_fullscreen = False
        self._last_volume = 80
        self._seek_step_ms = 10000
        self._current_pos = 0
        self._duration = 0
        
        self._config = load_json(CONFIG_FILE, {
            "enable_proxy": False, 
            "http_proxy": "http://127.0.0.1:7890",
            "https_proxy": "http://127.0.0.1:7890",
            "socks5_proxy": ""
        })
        
        # ====================================================
        # 2. 优先实例化两套引擎的适配器
        # ====================================================
        self.qt_adapter = QtPlayerAdapter(self)
        self.mpv_adapter = MpvPlayerAdapter(self)
        
        # 当前活跃的引擎适配器，默认使用 QtMultimedia
        self.current_adapter = self.qt_adapter
        
        # 3. 构建 UI
        self._build_ui()
        
        # 4. 连接信号与快捷键
        self._setup_shortcuts()
        self._connect_adapter_signals(self.current_adapter) 
        
        # 5. 加载历史列表
        self._load_playlist_from_disk()

    def _build_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(self.splitter)
        
        # ==================== 左侧：播放列表区 ====================
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 5, 0)
        
        list_toolbar1 = QHBoxLayout()
        self.btn_add_file = QPushButton("添加文件")
        self.btn_add_file.clicked.connect(self._open_files)
        self.btn_add_folder = QPushButton("添加文件夹")
        self.btn_add_folder.clicked.connect(self._open_folder)
        self.btn_add_url = QPushButton("添加网络流")
        self.btn_add_url.clicked.connect(self._open_url_input)

        # 代理设置按钮
        self.btn_proxy = QPushButton("代理设置")
        self.btn_proxy.clicked.connect(self._open_proxy_dialog)
        
        list_toolbar1.addWidget(self.btn_add_file)
        list_toolbar1.addWidget(self.btn_add_folder)
        list_toolbar1.addWidget(self.btn_add_url)
        list_toolbar1.addWidget(self.btn_proxy)
        left_layout.addLayout(list_toolbar1)
        
        list_toolbar2 = QHBoxLayout()
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("默认顺序", "default")
        self.sort_combo.addItem("按名称", "name")
        self.sort_combo.addItem("按大小", "size")
        self.sort_combo.addItem("按类型", "ext")
        self.sort_combo.currentIndexChanged.connect(self._apply_sorting)
        
        # === 播放引擎切换 ===
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["QtMultimedia", "libmpv"])
        self.engine_combo.currentTextChanged.connect(self._switch_engine)
        
        self.btn_hide_list = QPushButton("隐藏列表")
        self.btn_hide_list.clicked.connect(self._toggle_playlist)
        
        list_toolbar2.addWidget(self.sort_combo)
        list_toolbar2.addWidget(self.engine_combo) 
        list_toolbar2.addWidget(self.btn_hide_list)
        left_layout.addLayout(list_toolbar2)
        
        self.playlist_widget = QListWidget()
        self.playlist_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.playlist_widget.itemDoubleClicked.connect(self._play_item_by_double_click)
        self.playlist_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playlist_widget.customContextMenuRequested.connect(self._show_list_context_menu)
        self.playlist_widget.setStyleSheet("font-size: 11pt;")
        left_layout.addWidget(self.playlist_widget)
        
        self.splitter.addWidget(self.left_panel)
        
        # ==================== 右侧：视频与控制区 ====================
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(5, 0, 0, 0)
        
        # === 使用容器承载两套引擎的视频画面 ===
        self.video_container = QWidget()
        self.video_container.setMinimumWidth(320)
        self.video_layout = QVBoxLayout(self.video_container)
        self.video_layout.setContentsMargins(0, 0, 0, 0)
        self.video_layout.setSpacing(0)
        
        self.qt_widget = self.qt_adapter.get_widget()
        self.mpv_widget = self.mpv_adapter.get_widget()
        
        self.video_layout.addWidget(self.qt_widget)
        self.video_layout.addWidget(self.mpv_widget)
        self.mpv_widget.hide()
        
        right_layout.addWidget(self.video_container, stretch=1)
        
        progress_layout = QHBoxLayout()
        self.time_label = QLabel("00:00 / 00:00")
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self._on_slider_moved) # 绑定到通用方法
        progress_layout.addWidget(self.time_label)
        progress_layout.addWidget(self.position_slider, stretch=1)
        right_layout.addLayout(progress_layout)
        
        self.ctrl_container = QWidget()
        ctrl_layout = QHBoxLayout(self.ctrl_container)
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_prev = QPushButton()
        self.btn_prev.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipBackward))
        self.btn_prev.clicked.connect(self._play_prev)
        
        self.btn_rewind = QPushButton("<< 10s")
        self.btn_rewind.clicked.connect(self._seek_backward)
        
        self.seek_step_combo = QComboBox()
        self.seek_step_combo.addItem("5 秒", 5000)
        self.seek_step_combo.addItem("10 秒", 10000)
        self.seek_step_combo.addItem("30 秒", 30000)
        self.seek_step_combo.addItem("60 秒", 60000)
        self.seek_step_combo.setCurrentIndex(1)
        self.seek_step_combo.currentIndexChanged.connect(self._on_seek_step_changed)
        
        self.btn_play_pause = QPushButton()
        self.btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_play_pause.clicked.connect(self._toggle_play_pause)
        
        self.btn_forward = QPushButton("10s >>")
        self.btn_forward.clicked.connect(self._seek_forward)
        
        self.btn_next = QPushButton()
        self.btn_next.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipForward))
        self.btn_next.clicked.connect(self._play_next)
        
        self.btn_stop = QPushButton()
        self.btn_stop.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.btn_stop.clicked.connect(self._stop_playback)
        
        self.btn_fullscreen = QPushButton("全屏 (F11)")
        self.btn_fullscreen.clicked.connect(self._toggle_fullscreen)
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self._last_volume)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        
        ctrl_layout.addWidget(self.btn_prev)
        ctrl_layout.addWidget(self.btn_rewind)
        ctrl_layout.addWidget(self.seek_step_combo)
        ctrl_layout.addWidget(self.btn_play_pause)
        ctrl_layout.addWidget(self.btn_forward)
        ctrl_layout.addWidget(self.btn_next)
        ctrl_layout.addWidget(self.btn_stop)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.btn_fullscreen)
        ctrl_layout.addWidget(QLabel("音量"))
        ctrl_layout.addWidget(self.volume_slider)
        
        right_layout.addWidget(self.ctrl_container)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setSizes([300, 700])

    def _connect_adapter_signals(self, adapter):
        """统一连接适配器信号"""
        adapter.state_changed.connect(self._on_adapter_state_changed)
        adapter.position_changed.connect(self._on_adapter_position_changed)
        adapter.duration_changed.connect(self._on_adapter_duration_changed)
        adapter.set_volume(self.volume_slider.value())

    def _switch_engine(self, engine_name: str):
        was_playing = self.current_adapter.is_playing()
        current_url = self.current_adapter.get_current_url()
        current_pos = self._current_pos

        self.current_adapter.pause()
        self.current_adapter.get_widget().hide()
        
        try:
            self.current_adapter.state_changed.disconnect()
            self.current_adapter.position_changed.disconnect()
            self.current_adapter.duration_changed.disconnect()
        except Exception:
            pass

        if engine_name == "QtMultimedia":
            self.current_adapter = self.qt_adapter
        else:
            self.current_adapter = self.mpv_adapter
        
        self.current_adapter.get_widget().show()
        self._connect_adapter_signals(self.current_adapter)

        if current_url:
            self.current_adapter.play(current_url)
            
            # === 核心修复：判断是否为不支持 Seek 的流 ===
            # 如果是 RTMP/RTSP 直播流，或者时长为 0，则不执行进度恢复
            is_live_stream = current_url.startswith(("rtmp://", "rtsp://")) or self._duration <= 0
            
            if not is_live_stream and current_pos > 0:
                # 延迟 500ms 等播放器初始化后再 seek
                QTimer.singleShot(500, lambda: self.current_adapter.seek(current_pos))
                
            if was_playing:
                self.current_adapter.resume()

    # def _switch_engine(self, engine_name: str):
    #     was_playing = self.current_adapter.is_playing()
    #     current_url = self.current_adapter.get_current_url()
    #     current_pos = self._current_pos

    #     self.current_adapter.pause()
    #     self.current_adapter.get_widget().hide()
        
    #     try:
    #         self.current_adapter.state_changed.disconnect()
    #         self.current_adapter.position_changed.disconnect()
    #         self.current_adapter.duration_changed.disconnect()
    #     except Exception:
    #         pass

    #     if engine_name == "QtMultimedia":
    #         self.current_adapter = self.qt_adapter
    #     else:
    #         self.current_adapter = self.mpv_adapter
        
    #     self.current_adapter.get_widget().show()
    #     self._connect_adapter_signals(self.current_adapter)

    #     if current_url:
    #         self.current_adapter.play(current_url)
    #         QTimer.singleShot(500, lambda: self.current_adapter.seek(current_pos))
    #         if was_playing:
    #             self.current_adapter.resume()

    def _setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, activated=self._toggle_play_pause)
        QShortcut(QKeySequence(Qt.Key.Key_F11), self, activated=self._toggle_fullscreen)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, activated=self._seek_backward)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, activated=self._seek_forward)
        QShortcut(QKeySequence(Qt.Key.Key_Up), self, activated=lambda: self.volume_slider.setValue(min(100, self.volume_slider.value() + 5)))
        QShortcut(QKeySequence(Qt.Key.Key_Down), self, activated=lambda: self.volume_slider.setValue(max(0, self.volume_slider.value() - 5)))
        QShortcut(QKeySequence(Qt.Key.Key_N), self, activated=self._play_next)
        QShortcut(QKeySequence(Qt.Key.Key_P), self, activated=self._play_prev)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self._toggle_playlist)

    # ==================== 持久化与去重 ====================

    def _get_file_info(self, path: str) -> dict:
        is_url = path.startswith(("http://", "https://", "rtmp://", "rtsp://"))
        name = path.split("/")[-1] if is_url else os.path.basename(path)
        ext = "" if is_url else os.path.splitext(name)[1].lower()
        try:
            size = 0 if is_url else os.path.getsize(path)
        except OSError:
            size = 0
        return {"path": path, "name": name, "size": size, "ext": ext, "is_url": is_url}

    def _normalize_path(self, path: str) -> str:
        if path.startswith(("http://", "https://", "rtmp://", "rtsp://")):
            return path.strip()
        return os.path.normcase(os.path.abspath(path))

    def _load_playlist_from_disk(self):
        raw_data = load_json(PLAYLIST_FILE, [])
        self._playlist_data = []
        for d in raw_data:
            if not d.get("is_url") and not os.path.exists(d["path"]):
                d["missing"] = True
            else:
                d["missing"] = False
            self._playlist_data.append(d)
        self._refresh_list_ui()

    def _save_playlist_to_disk(self):
        data_to_save = [{k: v for k, v in d.items() if k != "missing"} for d in self._playlist_data]
        save_json(PLAYLIST_FILE, data_to_save)

    def _add_to_playlist(self, file_paths: list) -> bool:
        existing_norms = {self._normalize_path(item["path"]) for item in self._playlist_data}
        added = False
        for p in file_paths:
            norm_p = self._normalize_path(p)
            if norm_p not in existing_norms:
                self._playlist_data.append(self._get_file_info(p))
                existing_norms.add(norm_p)
                added = True
        if added:
            self._refresh_list_ui()
            self._save_playlist_to_disk()
            return True
        return False

    def _refresh_list_ui(self):
        self.playlist_widget.clear()
        for data in self._playlist_data:
            if data.get("is_url"):
                display_text = f"🌐 {data['name']}"
            else:
                size_mb = data["size"] / (1024 * 1024)
                display_text = f"🎬 {data['name']}  ({size_mb:.1f} MB)"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, data["path"])
            
            if data.get("missing"):
                item.setForeground(QColor("#D32F2F"))
                font = item.font()
                font.setStrikeOut(True)
                item.setFont(font)
                item.setToolTip("警告：该文件在磁盘上不存在或已被移动")
            else:
                item.setToolTip(data["path"])
                
            self.playlist_widget.addItem(item)
            
        if 0 <= self._current_index < self.playlist_widget.count():
            self.playlist_widget.setCurrentRow(self._current_index)

    # ==================== 拖拽支持 ====================

    def _handle_video_drop(self, event):
        urls = event.mimeData().urls()
        local_paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
        if not local_paths: return

        video_files = []
        for path in local_paths:
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for file in files:
                        if os.path.splitext(file)[1].lower() in SUPPORTED_EXTENSIONS:
                            video_files.append(os.path.join(root, file))
            elif os.path.isfile(path):
                if os.path.splitext(path)[1].lower() in SUPPORTED_EXTENSIONS:
                    video_files.append(path)

        if video_files:
            self._handle_drop_and_play(video_files[0])

    def _handle_drop_and_play(self, file_path: str):
        norm_path = self._normalize_path(file_path)
        for i, data in enumerate(self._playlist_data):
            if self._normalize_path(data["path"]) == norm_path:
                self._play_item(i)
                return

        if self._add_to_playlist([file_path]):
            for i, data in enumerate(self._playlist_data):
                if self._normalize_path(data["path"]) == norm_path:
                    self._play_item(i)
                    break

    # ==================== 列表管理 ====================

    def _open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择视频文件", "", "视频文件 (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.ts *.webm);;所有文件 (*)")
        if paths:
            if self._add_to_playlist(paths) and self._current_index == -1:
                self._play_item(0)

    def _open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择包含视频的文件夹")
        if not folder: return
        video_files = []
        for root, _, files in os.walk(folder):
            for file in files:
                if os.path.splitext(file)[1].lower() in SUPPORTED_EXTENSIONS:
                    video_files.append(os.path.join(root, file))
        if video_files:
            added = self._add_to_playlist(video_files)
            QMessageBox.information(self, "扫描完成", f"共找到 {len(video_files)} 个文件。")
            if added and self._current_index == -1:
                self._play_item(0)
        else:
            QMessageBox.information(self, "提示", "该文件夹中未找到支持的视频文件。")

    def _open_url_input(self):
        url, ok = QInputDialog.getText(self, "添加网络流", "请输入视频流地址 (支持 http/rtmp/rtsp/m3u8 等):", QLineEdit.EchoMode.Normal, "rtmp://")
        if ok and url.strip():
            if self._add_to_playlist([url.strip()]):
                if self._current_index == -1:
                    self._play_item(0)

    def _apply_sorting(self):
        mode = self.sort_combo.currentData()
        if mode == "default": return
        current_path = self._playlist_data[self._current_index]["path"] if 0 <= self._current_index < len(self._playlist_data) else None
        
        if mode == "name": self._playlist_data.sort(key=lambda x: x["name"].lower())
        elif mode == "size": self._playlist_data.sort(key=lambda x: x["size"], reverse=True)
        elif mode == "ext": self._playlist_data.sort(key=lambda x: x["ext"])
        self._refresh_list_ui()
        
        if current_path:
            for i, data in enumerate(self._playlist_data):
                if data["path"] == current_path:
                    self._current_index = i
                    self.playlist_widget.setCurrentRow(i)
                    break

    def _show_list_context_menu(self, pos):
        item = self.playlist_widget.itemAt(pos)
        if not item: return
        menu = QMenu()
        act_delete = menu.addAction("从列表中删除选中项")
        if menu.exec(self.playlist_widget.mapToGlobal(pos)) == act_delete:
            selected_items = self.playlist_widget.selectedItems()
            if not selected_items: return
            
            paths_to_delete = {it.data(Qt.ItemDataRole.UserRole) for it in selected_items}
            curr_playing_path = self._playlist_data[self._current_index]["path"] if 0 <= self._current_index < len(self._playlist_data) else None
            
            self._playlist_data = [d for d in self._playlist_data if d["path"] not in paths_to_delete]
            if curr_playing_path in paths_to_delete:
                self.current_adapter.stop()
                self._current_index = -1
            self._refresh_list_ui()
            self._save_playlist_to_disk()

    def _toggle_playlist(self):
        is_visible = self.left_panel.isVisible()
        self.left_panel.setVisible(not is_visible)
        self.btn_hide_list.setText("显示列表" if is_visible else "隐藏列表")
        if not is_visible:
            self.splitter.setSizes([300, 700])

    # ==================== 全局拖拽（作用于左侧列表区） ====================
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasUrls(): return
        urls = event.mimeData().urls()
        local_paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
        if not local_paths: return

        video_files = []
        for path in local_paths:
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for file in files:
                        if os.path.splitext(file)[1].lower() in SUPPORTED_EXTENSIONS:
                            video_files.append(os.path.join(root, file))
            elif os.path.isfile(path):
                if os.path.splitext(path)[1].lower() in SUPPORTED_EXTENSIONS:
                    video_files.append(path)

        if video_files:
            old_count = len(self._playlist_data)
            if self._add_to_playlist(video_files):
                event.acceptProposedAction()
                if self._current_index == -1:
                    self._play_item(old_count)
            else:
                event.ignore()

    # ==================== 播放控制 ====================

    def _play_item(self, index: int):
        if 0 <= index < len(self._playlist_data):
            data = self._playlist_data[index]
            if not data.get("is_url") and not os.path.exists(data["path"]):
                QMessageBox.warning(self, "文件不存在", f"找不到文件：\n{data['path']}\n请检查文件是否已被移动或删除。")
                return
                
            self._current_index = index
            self.playlist_widget.setCurrentRow(index)
            
            # 播放前应用代理
            self._apply_proxy_env()

            self.current_adapter.play(data["path"])

    def _play_item_by_double_click(self, item: QListWidgetItem):
        self._play_item(self.playlist_widget.row(item))

    def _play_next(self):
        if not self._playlist_data: return
        self._play_item((self._current_index + 1) % len(self._playlist_data))

    def _play_prev(self):
        if not self._playlist_data: return
        self._play_item((self._current_index - 1 + len(self._playlist_data)) % len(self._playlist_data))

    def _seek_forward(self):
        if self._duration > 0:
            self.current_adapter.seek(min(self._current_pos + self._seek_step_ms, self._duration))

    def _seek_backward(self):
        if self._duration > 0:
            self.current_adapter.seek(max(self._current_pos - self._seek_step_ms, 0))

    def _on_slider_moved(self, position):
        self.current_adapter.seek(position)

    def _on_seek_step_changed(self):
        self._seek_step_ms = self.seek_step_combo.currentData()
        sec = self._seek_step_ms // 1000
        self.btn_rewind.setText(f"<< {sec}s")
        self.btn_forward.setText(f"{sec}s >>")

    def _toggle_play_pause(self):
        if self.current_adapter.is_playing():
            self.current_adapter.pause()
        else:
            if self.current_adapter.get_current_url():
                self.current_adapter.resume()
            elif self._playlist_data:
                self._play_item(0 if self._current_index == -1 else self._current_index)

    def _stop_playback(self):
        self.current_adapter.stop()
        self.btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.position_slider.setValue(0)
        self._current_pos = 0
        self._update_time_label(0, self._duration)

    # ==================== 全屏控制 ====================

    def _toggle_fullscreen(self, event=None):
        if self._is_fullscreen:
            self.window().showNormal()
            self.left_panel.show()
            self.ctrl_container.show()
            self.btn_hide_list.show()
            self.btn_fullscreen.setText("全屏 (F11)")
            self._is_fullscreen = False
        else:
            self.window().showFullScreen()
            self.left_panel.hide()
            self.ctrl_container.hide()
            self.btn_hide_list.hide()
            self.btn_fullscreen.setText("退出全屏")
            self._is_fullscreen = True

    # ==================== 信号处理 ====================

    def _on_adapter_state_changed(self, state_str):
        if state_str == "playing":
            self.btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            self.btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def _on_adapter_position_changed(self, position):
        self._current_pos = position
        if not self.position_slider.isSliderDown():
            self.position_slider.setValue(position)
        self._update_time_label(position, self._duration)

    def _on_adapter_duration_changed(self, duration):
        self._duration = duration
        self.position_slider.setRange(0, duration)
        self._update_time_label(self._current_pos, duration)

        # 如果时长为 0 (直播流)，禁用进度条和快进按钮
        is_live = (duration <= 0)
        self.position_slider.setEnabled(not is_live)
        self.btn_rewind.setEnabled(not is_live)
        self.btn_forward.setEnabled(not is_live)

    def _on_volume_changed(self, value):
        self.current_adapter.set_volume(value)
        self._last_volume = value

    def _update_time_label(self, position, duration):
        def fmt(ms):
            if ms < 0: return "00:00"
            s = ms // 1000
            h, s = divmod(s, 3600)
            m, s = divmod(s, 60)
            return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
        self.time_label.setText(f"{fmt(position)} / {fmt(duration)}")

    def shutdown(self):
        self.current_adapter.stop()
        self._save_playlist_to_disk()


    def _open_proxy_dialog(self):
        dlg = ProxyDialog(self._config, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            save_json(CONFIG_FILE, self._config)
            QMessageBox.information(self, "保存成功", "代理配置已更新。")

    def _apply_proxy_env(self):
        """应用或关闭代理环境"""
        # 如果总开关关闭，彻底清理代理
        if not self._config.get("enable_proxy"):
            for key in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"]:
                os.environ.pop(key, None)
            QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
            return

        http_proxy = self._config.get("http_proxy", "")
        https_proxy = self._config.get("https_proxy", "")
        socks5_proxy = self._config.get("socks5_proxy", "")

        if http_proxy:
            os.environ["http_proxy"] = http_proxy
            os.environ["HTTP_PROXY"] = http_proxy
        if https_proxy:
            os.environ["https_proxy"] = https_proxy
            os.environ["HTTPS_PROXY"] = https_proxy
        if socks5_proxy:
            os.environ["all_proxy"] = socks5_proxy
            os.environ["ALL_PROXY"] = socks5_proxy

        if socks5_proxy:
            try:
                parts = socks5_proxy.replace("socks5://", "").split(":")
                host, port = parts[0], int(parts[1])
                proxy = QNetworkProxy(QNetworkProxy.ProxyType.Socks5Proxy, host, port)
                QNetworkProxy.setApplicationProxy(proxy)
            except Exception:
                pass
        elif http_proxy:
            try:
                clean_url = http_proxy.replace("http://", "").replace("https://", "")
                parts = clean_url.split(":")
                host, port = parts[0], int(parts[1])
                proxy = QNetworkProxy(QNetworkProxy.ProxyType.HttpProxy, host, port)
                QNetworkProxy.setApplicationProxy(proxy)
            except Exception:
                pass
        else:
            QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))