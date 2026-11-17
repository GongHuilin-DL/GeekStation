import os
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget, QFileDialog, QInputDialog, QMessageBox,
    QProgressBar, QPlainTextEdit, QListWidget, QListWidgetItem,
    QSpinBox
)

from app.services.security_service import SecurityService
from app.workers.security_worker import SecurityWorker


class SecurityTab(QWidget):
    """文件安全选项卡：包含加密/解密与隐藏/恢复功能。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread_pool = QThreadPool.globalInstance()
        self._encrypt_path = ""
        self._records = SecurityService.load_records()
        self._build_ui()
        self._check_password()
        self._refresh_records()

    def _check_password(self):
        """首次进入检查密码"""
        if not SecurityService.is_password_set():
            pwd, ok = QInputDialog.getText(self, "初次设置密码", "请设置安全模块密码:", QLineEdit.EchoMode.Password)
            if ok and pwd:
                SecurityService.save_password(pwd)
                QMessageBox.information(self, "成功", "密码设置成功，请牢记！")
            else:
                QMessageBox.warning(self, "提示", "未设置密码，部分功能将受限。")

    def _ask_password(self) -> str:
        """验证密码"""
        pwd, ok = QInputDialog.getText(self, "密码验证", "请输入安全模块密码:", QLineEdit.EchoMode.Password)
        if ok and pwd:
            if SecurityService.verify_password(pwd):
                return pwd
            else:
                QMessageBox.critical(self, "错误", "密码错误！")
        return ""

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(15, 15, 15, 15)
        root.setSpacing(20)

        # ================= 左侧：加密解密面板 =================
        crypto_group = QGroupBox("文件加密 / 解密")
        crypto_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 12pt; }")
        crypto_layout = QVBoxLayout(crypto_group)
        crypto_layout.setSpacing(10)

        # 路径选择
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("选择要处理的文件或文件夹...")
        path_layout.addWidget(self.path_input)
        btn_file = QPushButton("选择文件")
        btn_file.clicked.connect(self._select_file)
        path_layout.addWidget(btn_file)
        btn_dir = QPushButton("选择文件夹")
        btn_dir.clicked.connect(self._select_dir)
        path_layout.addWidget(btn_dir)
        crypto_layout.addLayout(path_layout)

        # 兼容旧 Key 与线程数
        opts_layout = QHBoxLayout()
        self.raw_key_input = QLineEdit()
        self.raw_key_input.setPlaceholderText("旧版兼容 Key (可选)")
        opts_layout.addWidget(self.raw_key_input)
        
        opts_layout.addWidget(QLabel("线程数:"))
        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 32)
        self.thread_spin.setValue(4)
        opts_layout.addWidget(self.thread_spin)
        crypto_layout.addLayout(opts_layout)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_encrypt = QPushButton("开始加密")
        btn_encrypt.setStyleSheet("background-color: #1565C0; color: white; font-weight: bold; padding: 6px;")
        btn_encrypt.clicked.connect(lambda: self._run_crypto("encrypt"))
        btn_layout.addWidget(btn_encrypt)

        btn_decrypt = QPushButton("开始解密")
        btn_decrypt.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold; padding: 6px;")
        btn_decrypt.clicked.connect(lambda: self._run_crypto("decrypt"))
        btn_layout.addWidget(btn_decrypt)
        crypto_layout.addLayout(btn_layout)

        # 进度条与日志
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        crypto_layout.addWidget(self.progress_bar)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background-color: #F5F5F5; font-family: Consolas; font-size: 10pt;")
        crypto_layout.addWidget(self.log_output)

        root.addWidget(crypto_group, stretch=1)

        # ================= 右侧：隐藏恢复面板 =================
        hide_group = QGroupBox("文件隐藏 / 恢复")
        hide_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 12pt; }")
        hide_layout = QVBoxLayout(hide_group)
        hide_layout.setSpacing(10)

        hide_layout.addWidget(QLabel("已隐藏的记录："))
        self.records_list = QListWidget()
        self.records_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        hide_layout.addWidget(self.records_list)

        # 操作按钮
        hide_btn_layout = QHBoxLayout()
        btn_hide = QPushButton("➕ 隐藏新路径")
        btn_hide.setStyleSheet("background-color: #D32F2F; color: white; padding: 6px;")
        btn_hide.clicked.connect(self._hide_new)
        hide_btn_layout.addWidget(btn_hide)

        btn_unhide = QPushButton("🔓 恢复选中项")
        btn_unhide.setStyleSheet("background-color: #1976D2; color: white; padding: 6px;")
        btn_unhide.clicked.connect(self._unhide_selected)
        hide_btn_layout.addWidget(btn_unhide)
        hide_layout.addLayout(hide_btn_layout)

        root.addWidget(hide_group, stretch=1)

    # ================= 加密/解密逻辑 =================

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if path:
            self.path_input.setText(path)

    def _select_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if path:
            self.path_input.setText(path)

    def _log(self, msg: str):
        self.log_output.appendPlainText(msg)

    def _run_crypto(self, mode: str):
        path = self.path_input.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "提示", "请选择有效的文件或文件夹。")
            return

        pwd = self._ask_password()
        if not pwd:
            return

        raw_key = self.raw_key_input.text().strip()

        if os.path.isfile(path):
            # 单文件处理
            dst = path + (".enc" if mode == "encrypt" else ".dec")
            self._log(f"开始处理单文件: {path}")
            try:
                if mode == "encrypt":
                    SecurityService.encrypt_file(pwd, path, dst)
                else:
                    SecurityService.decrypt_file(pwd, raw_key, path, dst)
                self._log(f"✅ 完成: {dst}")
            except Exception as e:
                self._log(f"❌ 失败: {e}")
        else:
            # 文件夹多线程处理
            dst_dir = path + ("_enc" if mode == "encrypt" else "_dec")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            worker = SecurityWorker(
                pwd, raw_key, path, dst_dir, mode, self.thread_spin.value()
            )
            worker.signals.progress.connect(self._update_progress)
            worker.signals.log.connect(self._log)
            worker.signals.finished.connect(lambda: self.progress_bar.setVisible(False))
            self._thread_pool.start(worker)

    def _update_progress(self, done, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(done)

    # ================= 隐藏/恢复逻辑 =================

    def _refresh_records(self):
        self.records_list.clear()
        for path in self._records:
            item = QListWidgetItem(path)
            # 检查路径是否还存在
            if not os.path.exists(path):
                item.setForeground(Qt.GlobalColor.gray)
                item.setText(path + " (路径不存在)")
            self.records_list.addItem(item)

    def _hide_new(self):
        pwd = self._ask_password()
        if not pwd:
            return

        path = QFileDialog.getExistingDirectory(self, "选择要隐藏的文件夹 (也可通过右键复制路径)")
        if not path:
            return

        if path in self._records:
            QMessageBox.information(self, "提示", "该路径已在记录中。")
            return

        try:
            SecurityService.hide_path(path)
            self._records.append(path)
            SecurityService.save_records(self._records)
            self._refresh_records()
            QMessageBox.information(self, "成功", "已成功隐藏该路径及其内部所有文件。")
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

    def _unhide_selected(self):
        items = self.records_list.selectedItems()
        if not items:
            return
            
        pwd = self._ask_password()
        if not pwd:
            return

        for item in items:
            path = item.text().replace(" (路径不存在)", "")
            if not os.path.exists(path):
                # 如果路径没了，直接删记录
                if path in self._records:
                    self._records.remove(path)
                continue
                
            try:
                SecurityService.unhide_path(path)
                if path in self._records:
                    self._records.remove(path)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"{path}\n{e}")

        SecurityService.save_records(self._records)
        self._refresh_records()
        QMessageBox.information(self, "完成", "恢复操作执行完毕。")