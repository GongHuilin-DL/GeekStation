import os
from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QTextEdit, QFileDialog, QMessageBox, QSplitter, QHeaderView,
    QComboBox, QFormLayout, QDialog, QDialogButtonBox, QInputDialog, QTabWidget
)
from PySide6.QtGui import QColor

from app.services.env_detect_service import EnvDetectService


class EnvDetectTab(QWidget):
    scan_done_signal = Signal(list)
    inspect_done_signal = Signal(dict)
    demo_done_signal = Signal(str)
    export_done_signal = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._environments = []
        self._current_env = None
        self._current_inspect_data = None
        self._is_scanning = False
        self._inspect_task_id = 0
        
        self._build_ui()
        self._connect_signals()
        self._do_scan()

    def _connect_signals(self):
        self.scan_done_signal.connect(self._on_scan_done)
        self.inspect_done_signal.connect(self._on_inspect_done)
        self.demo_done_signal.connect(self._on_demo_done)
        self.export_done_signal.connect(self._on_export_done)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        
        # 顶部扫描栏
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("额外扫描目录:"))
        self.search_dir_input = QLineEdit()
        self.search_dir_input.setPlaceholderText("C:\\Projects")
        top_bar.addWidget(self.search_dir_input, stretch=1)
        self.btn_scan = QPushButton("🔍 扫描环境")
        self.btn_scan.setStyleSheet("font-weight: bold; padding: 5px 15px;")
        self.btn_scan.clicked.connect(self._do_scan)
        top_bar.addWidget(self.btn_scan)
        root.addLayout(top_bar)

        # 主体分栏
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧环境列表
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("已检测到的环境:"))
        self.env_list = QListWidget()
        self.env_list.setStyleSheet("font-size: 11pt;")
        self.env_list.itemClicked.connect(self._on_env_selected)
        left_layout.addWidget(self.env_list)
        splitter.addWidget(left_panel)

        # 右侧详情区
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- 修改点 1：增加右侧顶部的刷新按钮 ---
        info_layout = QHBoxLayout()
        self.info_label = QLabel("请从左侧选择一个环境")
        self.info_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        
        self.btn_refresh_env = QPushButton("🔄 刷新当前详情")
        self.btn_refresh_env.setToolTip("重新探测当前选中环境的包信息")
        self.btn_refresh_env.setEnabled(False)
        self.btn_refresh_env.clicked.connect(self._refresh_current_env)
        
        info_layout.addWidget(self.info_label, stretch=1)
        info_layout.addWidget(self.btn_refresh_env)
        right_layout.addLayout(info_layout)

        # ================= 详情多标签页 =================
        self.detail_tabs = QTabWidget()

        # 1. 核心框架 Tab
        self.framework_table = QTableWidget(0, 4)
        self.framework_table.setHorizontalHeaderLabels(["框架", "版本", "后端", "附加信息"])
        header_fw = self.framework_table.horizontalHeader()
        header_fw.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_fw.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_fw.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_fw.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.framework_table.setColumnWidth(1, 120) 
        self.framework_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.detail_tabs.addTab(self.framework_table, "深度学习框架")

        # 2. 关键组件 Tab
        self.packages_table = QTableWidget(0, 2)
        self.packages_table.setHorizontalHeaderLabels(["组件/包名", "版本"])
        header_pkg = self.packages_table.horizontalHeader()
        header_pkg.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header_pkg.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.packages_table.setColumnWidth(0, 250) 
        self.packages_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.detail_tabs.addTab(self.packages_table, "关键依赖包")

        # 3. 硬件信息 Tab
        self.hardware_text = QTextEdit()
        self.hardware_text.setReadOnly(True)
        self.hardware_text.setStyleSheet("font-family: Consolas, 'Microsoft YaHei'; font-size: 11pt; padding: 10px;")
        self.detail_tabs.addTab(self.hardware_text, "硬件信息")

        right_layout.addWidget(self.detail_tabs, stretch=1)

        # 底部按钮
        btn_layout = QHBoxLayout()
        self.btn_demo = QPushButton("▶ 运行 Demo 验证")
        self.btn_demo.setEnabled(False)
        self.btn_demo.clicked.connect(self._do_demo)
        btn_layout.addWidget(self.btn_demo)

        self.btn_export = QPushButton("📦 导出环境")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._do_export)
        btn_layout.addWidget(self.btn_export)
        
        self.btn_recreate = QPushButton("⚙ 从文件复现环境")
        self.btn_recreate.clicked.connect(self._do_recreate)
        btn_layout.addWidget(self.btn_recreate)

        right_layout.addLayout(btn_layout)
        splitter.addWidget(right_panel)

        splitter.setSizes([250, 750])
        root.addWidget(splitter, stretch=1)

        # 底部日志
        root.addWidget(QLabel("控制台输出:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #1E1E1E; color: #00FF00; font-family: Consolas; font-size: 10pt;")
        self.log_text.setMaximumHeight(120)
        root.addWidget(self.log_text)

    def _log(self, msg):
        self.log_text.append(msg)

    # ================= 扫描与探察 =================

    def _do_scan(self):
        if self._is_scanning: return
        self._is_scanning = True
        self.btn_scan.setEnabled(False)
        
        extra_dir = self.search_dir_input.text().strip()
        dirs = [extra_dir] if extra_dir and os.path.isdir(extra_dir) else []
        self._log("正在扫描系统 Python/Conda 环境...")
        
        def run():
            envs = EnvDetectService.scan_environments(dirs)
            self.scan_done_signal.emit(envs)
            
        import threading
        threading.Thread(target=run, daemon=True).start()

    def _on_scan_done(self, envs):
        self._is_scanning = False
        self.btn_scan.setEnabled(True)
        self._environments = envs
        
        # --- 修改点 2：扫描完成后，尽可能保留之前的选中状态 ---
        prev_selected_path = self._current_env["path"] if self._current_env else None
        item_to_select = None
        
        self.env_list.clear()
        for env in envs:
            name = env["name"]
            etype = env["type"]
            py_exe = env["python_exe"]
            icon = "🐍" if etype == "base_python" else ("📦" if etype == "conda" else "📁")
            item = QListWidgetItem(f"{icon} {name}\n    {py_exe}")
            item.setData(Qt.ItemDataRole.UserRole, env)
            self.env_list.addItem(item)
            
            if prev_selected_path and env["path"] == prev_selected_path:
                item_to_select = item
                
        self._log(f"扫描完成，找到 {len(envs)} 个环境。")
        
        if item_to_select:
            self.env_list.setCurrentItem(item_to_select)
            self._on_env_selected(item_to_select)
        else:
            # 如果之前的环境不存在了，或者第一次扫描，清空右侧
            self._current_env = None
            self.info_label.setText("请从左侧选择一个环境")
            self.framework_table.setRowCount(0)
            self.packages_table.setRowCount(0)
            self.hardware_text.clear()
            self.btn_demo.setEnabled(False)
            self.btn_export.setEnabled(False)
            self.btn_refresh_env.setEnabled(False)

    def _on_env_selected(self, item):
        env = item.data(Qt.ItemDataRole.UserRole)
        if self._current_env and self._current_env["path"] == env["path"]: return
        self._current_env = env
        self._start_inspect(env)

    def _refresh_current_env(self):
        """刷新按钮触发的重新探测"""
        if not self._current_env: return
        self._start_inspect(self._current_env)

    def _start_inspect(self, env):
        """实际执行探测任务的方法（供选中和刷新共用）"""
        self._current_inspect_data = None
        self._inspect_task_id += 1
        current_task_id = self._inspect_task_id
        
        self.info_label.setText(f"正在检测环境: {env['name']} ...")
        self.framework_table.setRowCount(0)
        self.packages_table.setRowCount(0)
        self.hardware_text.clear()
        self.btn_demo.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.btn_refresh_env.setEnabled(False) # 探测中禁用刷新
        
        def run():
            result = EnvDetectService.inspect_env(env["python_exe"])
            if current_task_id == self._inspect_task_id:
                self.inspect_done_signal.emit(result)
            
        import threading
        threading.Thread(target=run, daemon=True).start()

    def _on_inspect_done(self, result):
        self._current_inspect_data = result
        self.btn_export.setEnabled(True)
        self.btn_refresh_env.setEnabled(True) # --- 修改点 3：探测完成，恢复刷新按钮 ---
        
        if "error" in result:
            self.info_label.setText(f"环境: {self._current_env['name']} (检测失败)")
            self._log(f"检测失败: {result['error']}")
            return
            
        py = result.get("python", {})
        self.info_label.setText(f"环境: {self._current_env['name']} | Python {py.get('version', '未知')} | 路径: {py.get('executable', '')}")
        
        # ----- 1. 填充核心框架表 -----
        self.framework_table.setRowCount(0)
        def add_fw_row(name, ver, backend="", info=""):
            row = self.framework_table.rowCount()
            self.framework_table.insertRow(row)
            self.framework_table.setItem(row, 0, QTableWidgetItem(name))
            self.framework_table.setItem(row, 1, QTableWidgetItem(ver))
            self.framework_table.setItem(row, 2, QTableWidgetItem(backend))
            self.framework_table.setItem(row, 3, QTableWidgetItem(info))
            
            if "cuda" in backend.lower() or "gpu" in backend.lower():
                for col in range(4):
                    itm = self.framework_table.item(row, col)
                    itm.setForeground(QColor("#2E7D32"))
                    f = itm.font(); f.setBold(True); itm.setFont(f)

        if result.get("pytorch"):
            pt = result["pytorch"]
            info = f"CUDA: {pt.get('cuda_version')} | cuDNN: {pt.get('cudnn_version')} | GPU: {pt.get('gpu_name')} | 算力: {pt.get('compute_capability')}"
            add_fw_row("PyTorch", pt["version"], pt["backend"].upper(), info)
        if result.get("tensorflow"):
            tf = result["tensorflow"]
            add_fw_row("TensorFlow", tf["version"], tf["backend"].upper(), f"检测到 {tf['gpu_count']} 个 GPU")
        if result.get("keras"):
            add_fw_row("Keras", result["keras"]["version"])
        if result.get("paddle"):
            pd = result["paddle"]
            add_fw_row("PaddlePaddle", pd["version"], pd["backend"].upper(), f"CUDA: {pd.get('cuda_version', '无')}")
        if result.get("onnxruntime"):
            ort = result["onnxruntime"]
            add_fw_row("ONNX Runtime", ort["version"], ", ".join(ort["providers"]))

        # ----- 2. 填充关键依赖包表 -----
        self.packages_table.setRowCount(0)
        pkgs = result.get("packages", {})
        for name, ver in pkgs.items():
            row = self.packages_table.rowCount()
            self.packages_table.insertRow(row)
            self.packages_table.setItem(row, 0, QTableWidgetItem(name))
            self.packages_table.setItem(row, 1, QTableWidgetItem(ver))

        # ----- 3. 填充硬件信息 -----
        hw = result.get("hardware", {})
        hw_lines = []
        if hw.get("ai_accelerator"):
            hw_lines.append("【🚀 专用 AI 加速器】")
            for acc in hw["ai_accelerator"]:
                hw_lines.append(f"● {acc['vendor']} {acc['name']}")
                if acc.get("vram_mib"): hw_lines.append(f"  - 显存: {acc['vram_mib']} MB")
                if acc.get("driver"): hw_lines.append(f"  - 驱动版本: {acc['driver']}")
                if acc.get("compute_capability"): hw_lines.append(f"  - 算力 (Compute Capability): {acc['compute_capability']}")
                hw_lines.append("")
        else:
            hw_lines.append("【⚠️ 未检测到专用 AI 加速器，将依赖 CPU/核显 推理】\n")
            cpu = hw.get("cpu")
            if cpu:
                hw_lines.append(f"💻 CPU: {cpu['name']}")
                hw_lines.append(f"  - 核心/线程: {cpu['cores']} 核 / {cpu['threads']} 线程")
                hw_lines.append(f"  - 最大主频: {cpu['max_clock_mhz']} MHz\n")
            
            if hw.get("integrated_gpu"):
                hw_lines.append("🖥️ 核显:")
                for ig in hw["integrated_gpu"]:
                    hw_lines.append(f"  - {ig['name']} (共享显存)")
        
        self.hardware_text.setPlainText("\n".join(hw_lines))
        self.btn_demo.setEnabled(True)
        self._log(f"检测完成: {self._current_env['name']}")

    # ================= 其他操作 =================
    def _do_demo(self):
        if not self._current_env: return
        self._log(f"开始在 {self._current_env['name']} 中运行 Demo 测试...")
        self.btn_demo.setEnabled(False)
        def run():
            out = EnvDetectService.run_demo(self._current_env["python_exe"])
            self.demo_done_signal.emit(out)
        import threading; threading.Thread(target=run, daemon=True).start()

    def _on_demo_done(self, output):
        self.btn_demo.setEnabled(True)
        self._log("---------- Demo 输出开始 ----------")
        self._log(output)
        self._log("---------- Demo 输出结束 ----------")

    def _do_export(self):
        if not self._current_env or not self._current_inspect_data: return
        dialog = QDialog(self); dialog.setWindowTitle("导出环境配置")
        layout = QFormLayout(dialog)
        combo = QComboBox(); combo.addItems(["requirements.txt", "environment.yml", "json"])
        layout.addRow("导出格式:", combo)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dialog.accept); btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            fmt = combo.currentText()
            save_path, _ = QFileDialog.getSaveFileName(self, "保存环境文件", f"{self._current_env['name']}_{fmt}", "All Files (*)")
            if not save_path: return
            self._log(f"正在导出为 {fmt}...")
            def run():
                full_info = self._current_env.copy()
                full_info["packages"] = self._current_inspect_data
                ok, msg = EnvDetectService.export_env(full_info, fmt, save_path)
                self.export_done_signal.emit(ok, msg)
            import threading; threading.Thread(target=run, daemon=True).start()

    def _on_export_done(self, ok, msg):
        if ok:
            self._log(f"✅ {msg}"); QMessageBox.information(self, "导出成功", msg)
        else:
            self._log(f"❌ {msg}"); QMessageBox.critical(self, "导出失败", msg)

    def _do_recreate(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择配置文件", "", "Environment Files (*.yml *.yaml *.txt)")
        if not file_path: return
        env_name, ok = QInputDialog.getText(self, "复现环境", "请输入新的环境名称:")
        if not ok or not env_name.strip(): return
        self._log(f"正在重建环境 {env_name} ...")
        def run():
            ok, msg = EnvDetectService.recreate_env(file_path, env_name.strip())
            self.export_done_signal.emit(ok, msg)
        import threading; threading.Thread(target=run, daemon=True).start()

    def shutdown(self): pass