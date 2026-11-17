import os
import time
import threading
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QMessageBox, QGroupBox, QGridLayout, QCheckBox,
    QSpinBox, QComboBox, QTextEdit, QDialog, QTabWidget, QDialogButtonBox,
    QSplitter
)

from app.services import scrcpy_service as svc


class HelpDialog(QDialog):
    """自定义帮助对话框，支持调整大小，放大字体。"""
    def __init__(self, help_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("scrcpy --help")
        self.resize(900, 700)
        self.setSizeGripEnabled(True)

        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                font-family: Consolas, 'Microsoft YaHei'; 
                font-size: 14pt; 
                background-color: #F8F9FA;
                padding: 10px;
            }
        """)
        self.text_edit.setText(help_text)
        layout.addWidget(self.text_edit)

        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn.accepted.connect(self.accept)
        layout.addWidget(btn)


class ScrcpyTab(QWidget):
    device_info_ready = Signal(dict) 

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cfg = svc.load_config()
        self._scrcpy_proc = svc.ScrcpyProcess()
        
        # 连接进程的信号
        self._scrcpy_proc.log_signal.connect(self._append_log)
        self._scrcpy_proc.finished_signal.connect(self._on_scrcpy_finished)
        
        self._devices = []
        
        self._build_ui()
        self._restore_config()
        self._refresh_devices()

        self.device_info_ready.connect(self._on_device_info_ready)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # ================= 1. 环境配置 =================
        env_group = QGroupBox("环境配置")
        env_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        env_layout = QHBoxLayout(env_group)
        
        env_layout.addWidget(QLabel("scrcpy:"))
        self.scrcpy_path_input = QLineEdit()
        self.scrcpy_path_input.setPlaceholderText("scrcpy.exe 路径")
        env_layout.addWidget(self.scrcpy_path_input, stretch=1)
        
        btn_browse_scrcpy = QPushButton("浏览...")
        btn_browse_scrcpy.clicked.connect(self._browse_scrcpy)
        env_layout.addWidget(btn_browse_scrcpy)
        
        btn_help = QPushButton("查看帮助")
        btn_help.clicked.connect(self._show_help)
        env_layout.addWidget(btn_help)

        env_layout.addSpacing(20)
        env_layout.addWidget(QLabel("adb:"))
        self.adb_path_input = QLineEdit()
        self.adb_path_input.setPlaceholderText("adb.exe 路径")
        env_layout.addWidget(self.adb_path_input, stretch=1)
        
        btn_browse_adb = QPushButton("浏览...")
        btn_browse_adb.clicked.connect(self._browse_adb)
        env_layout.addWidget(btn_browse_adb)

        root.addWidget(env_group)

        # ================= 2. 连接方式 =================
        self.conn_tabs = QTabWidget()
        
        # USB 面板
        self.usb_panel = QWidget()
        usb_layout = QVBoxLayout(self.usb_panel)
        usb_dev_row = QHBoxLayout()
        usb_dev_row.addWidget(QLabel("已连接的 USB 设备:"))
        self.usb_dev_combo = QComboBox()
        self.usb_dev_combo.setMinimumWidth(300)
        usb_dev_row.addWidget(self.usb_dev_combo, stretch=1)
        btn_refresh = QPushButton("刷新设备")
        btn_refresh.clicked.connect(self._refresh_devices)
        usb_dev_row.addWidget(btn_refresh)
        usb_layout.addLayout(usb_dev_row)
        usb_layout.addStretch()
        self.conn_tabs.addTab(self.usb_panel, "USB 有线连接")

        # Wi-Fi 面板
        self.wifi_panel = QWidget()
        wifi_layout = QVBoxLayout(self.wifi_panel)
        
        pair_group = QGroupBox("步骤 1：无线配对 (首次连接需要，已配对可跳过)")
        pair_layout = QHBoxLayout(pair_group)
        pair_layout.addWidget(QLabel("IP:"))
        self.pair_ip_input = QLineEdit()
        self.pair_ip_input.setMaximumWidth(150)
        pair_layout.addWidget(self.pair_ip_input)
        pair_layout.addWidget(QLabel("配对端口:"))
        self.pair_port_spin = QSpinBox()
        self.pair_port_spin.setRange(1, 65535)
        self.pair_port_spin.setMaximumWidth(90)
        pair_layout.addWidget(self.pair_port_spin)
        pair_layout.addWidget(QLabel("配对码:"))
        self.pair_code_input = QLineEdit()
        self.pair_code_input.setMaximumWidth(100)
        pair_layout.addWidget(self.pair_code_input)
        btn_pair = QPushButton("执行配对")
        btn_pair.setStyleSheet("background-color: #1565C0; color: white;")
        btn_pair.clicked.connect(self._do_pair)
        pair_layout.addWidget(btn_pair)
        pair_layout.addStretch()
        wifi_layout.addWidget(pair_group)

        conn_group = QGroupBox("步骤 2：网络连接 (IP 和端口不变时可重复使用)")
        conn_layout = QHBoxLayout(conn_group)
        conn_layout.addWidget(QLabel("IP:"))
        self.wifi_ip_input = QLineEdit()
        self.wifi_ip_input.setMaximumWidth(150)
        conn_layout.addWidget(self.wifi_ip_input)
        conn_layout.addWidget(QLabel("连接端口:"))
        self.wifi_port_spin = QSpinBox()
        self.wifi_port_spin.setRange(1, 65535)
        self.wifi_port_spin.setValue(5555)
        self.wifi_port_spin.setMaximumWidth(90)
        conn_layout.addWidget(self.wifi_port_spin)
        btn_connect = QPushButton("执行连接")
        btn_connect.setStyleSheet("background-color: #2E7D32; color: white;")
        btn_connect.clicked.connect(self._do_connect)
        conn_layout.addWidget(btn_connect)
        btn_disconnect = QPushButton("断开连接")
        btn_disconnect.setStyleSheet("color: #D32F2F;")
        btn_disconnect.clicked.connect(self._do_disconnect)
        conn_layout.addWidget(btn_disconnect)
        conn_layout.addStretch()
        wifi_layout.addWidget(conn_group)
        wifi_layout.addStretch()
        self.conn_tabs.addTab(self.wifi_panel, "Wi-Fi 无线连接")

        root.addWidget(self.conn_tabs)

        # ================= 3. 参数配置与快捷指南 =================
        args_group = QGroupBox("scrcpy 常用参数与快捷操作")
        args_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        args_layout = QVBoxLayout(args_group)

        # 参数网格
        args_grid = QGridLayout()
        args_grid.setSpacing(8)

        args_grid.addWidget(QLabel("视频编码:"), 0, 0)
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["h264", "h265", "av1"])
        args_grid.addWidget(self.codec_combo, 0, 1)

        args_grid.addWidget(QLabel("最大分辨率:"), 0, 2)
        self.max_size_combo = QComboBox()
        self.max_size_combo.addItem("手机原生", 0)
        self.max_size_combo.addItem("1920 (1080p)", 1920)
        self.max_size_combo.addItem("1280 (720p)", 1280)
        self.max_size_combo.addItem("1024 (轻量)", 1024)
        self.max_size_combo.addItem("720 (极简)", 720)
        args_grid.addWidget(self.max_size_combo, 0, 3)

        args_grid.addWidget(QLabel("最大帧率:"), 0, 4)
        self.max_fps_spin = QSpinBox()
        self.max_fps_spin.setRange(0, 240)
        self.max_fps_spin.setSpecialValueText("原始")
        args_grid.addWidget(self.max_fps_spin, 0, 5)

        args_grid.addWidget(QLabel("键盘模式:"), 1, 0)
        self.kb_combo = QComboBox()
        self.kb_combo.addItems(["uhid", "sdk", "disabled"])
        args_grid.addWidget(self.kb_combo, 1, 1)

        self.cb_turn_screen_off = QCheckBox("关闭手机屏幕 (-S)")
        self.cb_stay_awake = QCheckBox("保持设备常亮 (-w)")
        self.cb_no_audio = QCheckBox("禁用音频 (--no-audio)")
        
        args_grid.addWidget(self.cb_turn_screen_off, 2, 0, 1, 2)
        args_grid.addWidget(self.cb_stay_awake, 2, 2, 1, 2)
        args_grid.addWidget(self.cb_no_audio, 2, 4, 1, 2)
        args_layout.addLayout(args_grid)

        # 快捷指南提示区
        guide_label = QLabel(
            "💡 <b>快捷键指南（在手机镜像窗口上操作）：</b> "
            "全屏: <code>Alt+F</code> | 旋转: <code>Alt+←/→</code> | "
            "音量±: <code>Alt+↑/↓</code> | 窗口去黑边: <code>Alt+W</code> | 1:1像素: <code>Alt+G</code>"
        )
        guide_label.setStyleSheet("color: #546E7A; font-size: 10pt; background-color: #E3F2FD; padding: 5px; border-radius: 4px;")
        args_layout.addWidget(guide_label)

        root.addWidget(args_group)

        # ================= 4. 启动控制 =================
        ctrl_layout = QHBoxLayout()
        self.btn_start = QPushButton("启动 scrcpy 投屏")
        self.btn_start.setStyleSheet(
            "background-color: #2E7D32; color: white; font-weight: bold; font-size: 12pt; padding: 8px 20px;"
        )
        self.btn_start.clicked.connect(self._start_scrcpy)
        ctrl_layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("停止投屏")
        self.btn_stop.setStyleSheet("color: #D32F2F; font-weight: bold; padding: 8px 20px;")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_scrcpy)
        ctrl_layout.addWidget(self.btn_stop)
        ctrl_layout.addStretch()
        root.addLayout(ctrl_layout)

        # ================= 5. 底部选项卡（日志 + 设备信息） =================
        self.bottom_tabs = QTabWidget()
        
        # 5.1 实时日志
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #1E1E1E; color: #00FF00; font-family: Consolas; font-size: 10pt;")
        self.bottom_tabs.addTab(self.log_text, "实时日志")

        # 5.2 设备信息与 AI 能力
        self._build_device_info_panel(self.bottom_tabs)

        root.addWidget(self.bottom_tabs, stretch=1)

        QTimer.singleShot(100, self._auto_detect)

    def _build_device_info_panel(self, parent_tab_widget):
        """构建设备信息与 AI 能力面板"""
        panel = QWidget()
        v = QVBoxLayout(panel)
        v.setSpacing(10)

        btn_row = QHBoxLayout()
        self.btn_detect = QPushButton("一键检测硬件与软件信息")
        self.btn_detect.setStyleSheet("background-color: #F57C00; color: white; font-weight: bold; padding: 6px 15px;")
        self.btn_detect.clicked.connect(self._detect_device_info)
        btn_row.addWidget(self.btn_detect)
        btn_row.addStretch()
        v.addLayout(btn_row)

        # 原始信息输出
        v.addWidget(QLabel("原始信息采集："))
        self.info_output = QTextEdit()
        self.info_output.setReadOnly(True)
        self.info_output.setStyleSheet("font-family: Consolas; font-size: 10pt; background-color: #F8F9FA;")
        v.addWidget(self.info_output)

        # AI 建议输出
        v.addWidget(QLabel("AI 推理能力初步判断与建议："))
        self.ai_advice = QTextEdit()
        self.ai_advice.setReadOnly(True)
        self.ai_advice.setStyleSheet("background-color: #E8F5E9; font-size: 11pt; font-family: 'Microsoft YaHei';")
        v.addWidget(self.ai_advice)

        parent_tab_widget.addTab(panel, "设备信息与 AI 能力")

    # ================= 设备信息检测逻辑 =================

    def _detect_device_info(self):
        adb = self.adb_path_input.text().strip()
        if not adb:
            QMessageBox.warning(self, "提示", "请先配置 adb 路径。")
            return
        
        serial = self.usb_dev_combo.currentData() if self.conn_tabs.currentIndex() == 0 else ""
        self._append_log("开始采集设备信息...")
        self.btn_detect.setEnabled(False)
        self.info_output.setText("正在通过 ADB 采集数据，请稍候...")
        self.ai_advice.clear()
        
        def worker():
            # 调用底层的采集逻辑
            info = svc.collect_device_info(adb, serial)
            # 使用 Signal 安全地将数据发回主线程
            self.device_info_ready.emit(info)
        
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _on_device_info_ready(self, info: dict):
        self.btn_detect.setEnabled(True)
        
        lines = []
        for k, v in info.items():
            # 取消截断，直接展示原始信息
            if k == "gles":
                # 尝试从冗长的 SurfaceFlinger 输出中提取有用的一行
                for line in v.splitlines():
                    if "GLES" in line or "Mali" in line:
                        v = line.strip()
                        break
            elif k == "gpu_nodes":
                # 只显示关键的
                nodes = v.split()
                key_nodes = [n for n in nodes if any(x in n.lower() for x in ["adsp", "cdsp", "hexagon", "npu", "kgsl", "mali", "gpu"])]
                v = " ".join(key_nodes) if key_nodes else v
            elif k == "neural_service":
                v = "\n".join([l for l in v.splitlines() if "neural" in l.lower()]) or "(未发现 NNAPI 服务)"
            lines.append(f"[{k.upper()}]\n{v}\n")
            
        self.info_output.setPlainText("\n".join(lines))
        
        advice = self._generate_ai_advice(info)
        self.ai_advice.setPlainText(advice)
        self._append_log("设备信息采集完成。")

    def _generate_ai_advice(self, info: dict) -> str:
        advice = []
        abi = info.get("cpu_abi", "")
        model = info.get("model", "").upper()
        brand = info.get("brand", "").upper()
        gles = info.get("gles", "").lower()
        gpu_nodes = info.get("gpu_nodes", "").lower()
        neural = info.get("neural_service", "").lower()
        
        # 基础 CPU 判断
        if "arm64" in abi:
            advice.append("✅ CPU：64 位 ARM 架构，可运行绝大多数现代移动端推理引擎。")
        
        # 判断芯片厂商
        is_mtk = "mtk" in neural or "mali" in gles or "mali" in gpu_nodes or "mtk" in gpu_nodes
        is_qualcomm = "adreno" in gles or "qcom" in model or "hexagon" in gpu_nodes
        is_huawei = "kirin" in model or "hisilicon" in model or "npu" in gpu_nodes and "ascend" in gpu_nodes
        
        # GPU 判断
        if "mali" in gles or "mali" in gpu_nodes:
            advice.append("✅ GPU：检测到 ARM Mali 系列（通常伴随联发科/三星/麒麟芯片）。")
            advice.append("   建议：Mali GPU 支持 OpenCL / Vulkan 后端。TFLite 可使用 GPU Delegate，但更推荐使用 MNN 的 OpenCL 后端。")
        elif "adreno" in gles:
            advice.append("✅ GPU：检测到 Qualcomm Adreno 系列。")
            advice.append("   建议：可尝试 TFLite GPU Delegate 或 MNN OpenCL 后端，Adreno 640 以上对 FP16 支持极好。")
        else:
            advice.append("⚠️ GPU：未能明确识别型号。")
            
        # NPU 深度判断与建议
        advice.append("\n📌 NPU 与推理框架建议：")
        if is_mtk:
            advice.append("🚀 检测到【联发科 (MediaTek)】专属 NPU 服务 (mtk-neuron / mtk-mdla)。")
            advice.append("   - 官方方案：强烈建议使用 MediaTek NeuroPilot SDK，能极致调用 APU（AI Processing Unit）。")
            advice.append("   - 通用方案：TFLite / MNN / NCNN 均可通过 Android NNAPI 委托调用 APU，其中 TFLite 的 NNAPI 支持最完善。")
        elif is_qualcomm:
            advice.append("🚀 检测到【高通 (Qualcomm)】硬件加速能力。")
            advice.append("   - 官方方案：使用 Qualcomm AI Engine Direct (QNN) 或 SNPE，能充分调用 Hexagon DSP / NPU。")
            advice.append("   - 通用方案：TFLite NNAPI Delegate 或 QNN Execution Provider (ONNX Runtime)。")
        elif is_huawei:
            advice.append("🚀 检测到【华为 (Huawei/HiSilicon)】硬件特性。")
            advice.append("   - 官方方案：华为 HiAI Foundation 或 CANN (Compute Architecture for Neural Networks)。")
        else:
            advice.append("ℹ️ 未明确检测到专用 NPU。建议优先使用 CPU 或 GPU 推理。")
            
        # 场景推荐
        advice.append("\n💡 场景推荐：")
        advice.append("- 跑轻量视觉模型 (YOLO, 分类)：首选 NCNN 或 TFLite。")
        advice.append("- 跑本地大语言模型 (LLM)：首选 MNN (推理极快) 或 llama.cpp (GGUF 量化格式，纯 CPU 发挥出色)。")
        
        return "\n".join(advice)

    # ================= 状态与配置管理 =================

    def _append_log(self, msg: str):
        t = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{t}] {msg}")
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_scrcpy_finished(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._append_log("==== 投屏已关闭 ====")

    def _auto_detect(self):
        if not self.scrcpy_path_input.text():
            p = svc.find_scrcpy()
            if p: self.scrcpy_path_input.setText(p)
        if not self.adb_path_input.text():
            p = svc.find_adb()
            if p: self.adb_path_input.setText(p)

    def _restore_config(self):
        cfg = self._cfg
        self.scrcpy_path_input.setText(cfg.get("scrcpy_path", ""))
        self.adb_path_input.setText(cfg.get("adb_path", ""))
        
        self.wifi_ip_input.setText(cfg.get("last_wifi_ip", ""))
        self.pair_ip_input.setText(cfg.get("last_wifi_ip", ""))
        self.wifi_port_spin.setValue(cfg.get("last_connect_port", 5555))
        self.pair_port_spin.setValue(cfg.get("last_pair_port", 0))

        a = cfg.get("args", {})
        self.codec_combo.setCurrentText(a.get("video_codec", "h265"))
        
        # 恢复分辨率档位
        max_size_val = a.get("max_size", 1920)
        idx = self.max_size_combo.findData(max_size_val)
        self.max_size_combo.setCurrentIndex(idx if idx >= 0 else 0)
        
        self.max_fps_spin.setValue(a.get("max_fps", 60))
        self.kb_combo.setCurrentText(a.get("keyboard_mode", "uhid"))
        self.cb_turn_screen_off.setChecked(a.get("turn_screen_off", True))
        self.cb_stay_awake.setChecked(a.get("stay_awake", True))
        self.cb_no_audio.setChecked(a.get("no_audio", True))

    def _collect_config(self) -> dict:
        cfg = self._cfg.copy()
        cfg["scrcpy_path"] = self.scrcpy_path_input.text().strip()
        cfg["adb_path"] = self.adb_path_input.text().strip()
        cfg["last_wifi_ip"] = self.wifi_ip_input.text().strip()
        cfg["last_connect_port"] = self.wifi_port_spin.value()
        cfg["last_pair_port"] = self.pair_port_spin.value()
        cfg["args"] = {
            "video_codec": self.codec_combo.currentText(),
            "max_size": self.max_size_combo.currentData(),
            "max_fps": self.max_fps_spin.value(),
            "keyboard_mode": self.kb_combo.currentText(),
            "turn_screen_off": self.cb_turn_screen_off.isChecked(),
            "stay_awake": self.cb_stay_awake.isChecked(),
            "no_audio": self.cb_no_audio.isChecked(),
        }
        if self.usb_dev_combo.currentData():
            cfg["last_usb_serial"] = self.usb_dev_combo.currentData()
        return cfg

    # ================= 各类操作 =================

    def _browse_scrcpy(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 scrcpy", "", "scrcpy.exe (*.exe)")
        if path:
            self.scrcpy_path_input.setText(path)
            if not self.adb_path_input.text():
                adb = os.path.join(os.path.dirname(path), "adb.exe")
                if os.path.isfile(adb):
                    self.adb_path_input.setText(adb)

    def _browse_adb(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 adb", "", "adb.exe (*.exe)")
        if path:
            self.adb_path_input.setText(path)

    def _show_help(self):
        text = svc.get_help_text(self.scrcpy_path_input.text().strip())
        dlg = HelpDialog(text, self)
        dlg.exec()

    def _refresh_devices(self):
        adb = self.adb_path_input.text().strip() or svc.find_adb()
        if adb and not self.adb_path_input.text():
            self.adb_path_input.setText(adb)
        
        self._devices = svc.get_devices(adb)
        self.usb_dev_combo.clear()
        
        usb_devices = [d for d in self._devices if ":" not in d["serial"]]
        if not usb_devices:
            self.usb_dev_combo.addItem("（未检测到 USB 设备）", "")
        else:
            for d in usb_devices:
                self.usb_dev_combo.addItem(f"{d['model']} [{d['serial']}]", d["serial"])
            last = self._cfg.get("last_usb_serial", "")
            if last:
                idx = self.usb_dev_combo.findData(last)
                if idx >= 0: self.usb_dev_combo.setCurrentIndex(idx)

    def _do_pair(self):
        adb = self.adb_path_input.text().strip()
        ip = self.pair_ip_input.text().strip()
        port = self.pair_port_spin.value()
        code = self.pair_code_input.text().strip()
        if not adb or not ip or not code:
            QMessageBox.warning(self, "提示", "请填写 adb 路径、IP 和配对码。")
            return
        ok, msg = svc.adb_pair(adb, ip, port, code)
        self._append_log(f"配对: {msg}")
        if ok:
            QMessageBox.information(self, "配对成功", msg)

    def _do_connect(self):
        adb = self.adb_path_input.text().strip()
        ip = self.wifi_ip_input.text().strip()
        port = self.wifi_port_spin.value()
        if not adb or not ip:
            QMessageBox.warning(self, "提示", "请填写 adb 路径和手机 IP。")
            return
        ok, msg = svc.adb_connect(adb, ip, port)
        self._append_log(f"连接: {msg}")
        if ok:
            self._refresh_devices()
            QMessageBox.information(self, "连接成功", msg)

    def _do_disconnect(self):
        adb = self.adb_path_input.text().strip()
        ip = self.wifi_ip_input.text().strip()
        port = self.wifi_port_spin.value()
        if adb and ip:
            ok, msg = svc.adb_disconnect(adb, ip, port)
            self._append_log(f"断开: {msg}")

    def _start_scrcpy(self):
        if self._scrcpy_proc.running:
            QMessageBox.information(self, "提示", "scrcpy 已在运行中。")
            return

        scrcpy = self.scrcpy_path_input.text().strip()
        if not scrcpy or not os.path.isfile(scrcpy):
            QMessageBox.warning(self, "错误", "scrcpy 路径无效。")
            return

        self._cfg = self._collect_config()
        svc.save_config(self._cfg)

        mode = "usb" if self.conn_tabs.currentIndex() == 0 else "wifi"
        serial = self.usb_dev_combo.currentData() if mode == "usb" else ""
        
        args = svc.build_scrcpy_args(self._cfg, mode, serial)
        self._append_log("执行命令: " + " ".join(args))
        
        try:
            self._scrcpy_proc.start(args)
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            # 切换到日志页
            self.bottom_tabs.setCurrentIndex(0)
        except Exception as e:
            QMessageBox.critical(self, "启动失败", str(e))
            self._append_log(f"启动异常: {e}")

    def _stop_scrcpy(self):
        self._scrcpy_proc.stop()

    def shutdown(self):
        self._scrcpy_proc.stop()