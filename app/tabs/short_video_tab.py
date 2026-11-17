import os
import re
import time
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QProgressBar, QFileDialog,
    QMessageBox, QHeaderView, QAbstractItemView, QComboBox
)
from PySide6.QtGui import QColor

from app.services.short_video_service import (
    VideoParser, DownloadTask, VideoDownloadWorker
)


class ShortVideoTab(QWidget):
    """短视频下载选项卡（支持多任务并发）。"""
    
    # 定义信号，用于从后台线程安全地将解析结果传回主线程
    parse_finished_signal = Signal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks: dict[int, DownloadTask] = {}
        self.workers: dict[int, VideoDownloadWorker] = {}
        self.task_id_counter = 0
        self._thread_pool = QThreadPool.globalInstance()
        self._thread_pool.setMaxThreadCount(8)
        
        self.save_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "videos")
        os.makedirs(self.save_dir, exist_ok=True)
        
        self._build_ui()
        
        # 连接信号到槽函数
        self.parse_finished_signal.connect(self._on_parse_done)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        title = QLabel("短视频下载器")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #0D47A1;")
        root.addWidget(title)
        
        subtitle = QLabel("支持抖音、快手等平台 | 粘贴分享链接即可解析 | 多任务并发下载")
        subtitle.setStyleSheet("color: gray; font-size: 11pt;")
        root.addWidget(subtitle)

        input_group = QWidget()
        input_layout = QVBoxLayout(input_group)
        input_layout.setContentsMargins(0, 0, 0, 0)
        
        self.link_input = QTextEdit()
        self.link_input.setPlaceholderText("在此粘贴分享链接或分享文案（每行一个）...")
        self.link_input.setMaximumHeight(80)
        self.link_input.setStyleSheet("font-size: 11pt;")
        input_layout.addWidget(self.link_input)

        btn_layout = QHBoxLayout()
        self.btn_parse = QPushButton("解析链接")
        self.btn_parse.setStyleSheet("background-color: #1565C0; color: white; font-weight: bold; padding: 6px 15px;")
        self.btn_parse.clicked.connect(self._parse_links)
        btn_layout.addWidget(self.btn_parse)
        
        self.btn_clear = QPushButton("清空输入")
        self.btn_clear.clicked.connect(lambda: self.link_input.clear())
        btn_layout.addWidget(self.btn_clear)
        
        btn_layout.addStretch()
        
        self.btn_browse_dir = QPushButton("修改保存目录")
        self.btn_browse_dir.clicked.connect(self._select_save_dir)
        btn_layout.addWidget(self.btn_browse_dir)
        
        self.dir_label = QLabel(f"保存至: {self.save_dir}")
        self.dir_label.setStyleSheet("color: #546E7A; font-size: 10pt;")
        btn_layout.addWidget(self.dir_label)
        
        input_layout.addLayout(btn_layout)
        root.addWidget(input_group)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["平台", "标题", "进度", "状态", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(2, 180)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(4, 120)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        root.addWidget(self.table, stretch=1)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        self.log_text.setStyleSheet("background-color: #1E1E1E; color: #00FF00; font-family: Consolas; font-size: 9pt;")
        root.addWidget(QLabel("运行日志:"))
        root.addWidget(self.log_text)

    def _select_save_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择视频保存目录", self.save_dir)
        if path:
            self.save_dir = path
            self.dir_label.setText(f"保存至: {path}")

    def _parse_links(self):
        text = self.link_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请先粘贴分享链接。")
            return
        
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        urls = []
        for line in lines:
            url = VideoParser.extract_url(line)
            if url:
                urls.append(url)
        
        if not urls:
            QMessageBox.warning(self, "提示", "未能从输入中识别到有效链接。")
            return

        self._log(f"开始解析 {len(urls)} 个链接...")
        self.btn_parse.setEnabled(False)
        
        # 后台线程解析，完成后通过信号通知主线程
        def do_parse():
            results = []
            for url in urls:
                info = VideoParser.parse(url)
                results.append(info)
                time.sleep(0.1)
            
            # 发射信号，将结果传回主线程
            self.parse_finished_signal.emit(results)
        
        threading.Thread(target=do_parse, daemon=True).start()

    def _on_parse_done(self, results: list):
        self.btn_parse.setEnabled(True)
        success_count = 0
        
        for info in results:
            if info.get("error"):
                self._log(f"❌ 解析失败: {info['error']}")
                continue
            
            success_count += 1
            self.task_id_counter += 1
            task_id = self.task_id_counter
            
            safe_title = re.sub(r'[\\/*?:"<>|]', "_", info["title"])[:50]
            filename = f"{safe_title}_{task_id}.mp4"
            save_path = os.path.join(self.save_dir, filename)
            
            task = DownloadTask(task_id, info["title"], info["video_url"], save_path, info["platform"])
            task.row = self.table.rowCount()  # 记录行号
            self.tasks[task_id] = task
            
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            self.table.setItem(row, 0, QTableWidgetItem(info["platform"]))
            self.table.setItem(row, 1, QTableWidgetItem(info["title"]))
            
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            self.table.setCellWidget(row, 2, progress_bar)
            
            self.table.setItem(row, 3, QTableWidgetItem("等待下载"))
            
            btn_download = QPushButton("开始下载")
            btn_download.setStyleSheet("background-color: #2E7D32; color: white; padding: 4px;")
            btn_download.clicked.connect(lambda checked=False, tid=task_id: self._start_download(tid))
            
            btn_cancel = QPushButton("取消")
            btn_cancel.setStyleSheet("color: #D32F2F; padding: 4px;")
            btn_cancel.setEnabled(False)
            btn_cancel.clicked.connect(lambda checked=False, tid=task_id: self._cancel_task(tid))
            
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 2, 2, 2)
            action_layout.addWidget(btn_download)
            action_layout.addWidget(btn_cancel)
            self.table.setCellWidget(row, 4, action_widget)
            
            task.btn_download = btn_download
            task.btn_cancel = btn_cancel
            
            self._log(f"✅ 解析成功: {info['title']} ({info['platform']})")
        
        self._log(f"解析完成: 成功 {success_count}/{len(results)}")
        if success_count > 0:
            self.link_input.clear()

    def _start_download(self, task_id: int):
        task = self.tasks.get(task_id)
        if not task or task.status == "下载中":
            return
        
        task.status = "下载中"
        task.cancelled = False
        task.btn_download.setEnabled(False)
        task.btn_cancel.setEnabled(True)
        self._update_status(task_id, "下载中", "#1565C0")
        
        worker = VideoDownloadWorker(task)
        worker.signals.log.connect(self._log)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.finished.connect(self._on_download_finished)
        
        self.workers[task_id] = worker
        self._thread_pool.start(worker)
        self._log(f"加入下载队列: {task.title}")

    def _cancel_task(self, task_id: int):
        task = self.tasks.get(task_id)
        if task:
            task.cancelled = True
            self._log(f"正在取消: {task.title}")
            task.btn_cancel.setEnabled(False)

    def _on_progress(self, task_id: int, percent: int):
        task = self.tasks.get(task_id)
        if task and hasattr(task, 'row'):
            bar = self.table.cellWidget(task.row, 2)
            if bar:
                bar.setValue(percent)

    def _on_download_finished(self, task_id: int, success: bool, message: str):
        task = self.tasks.get(task_id)
        if not task:
            return
        
        if success:
            task.status = "已完成"
            self._update_status(task_id, "已完成", "#2E7D32")
            self._log(f"✅ 下载完成: {task.title}")
            bar = self.table.cellWidget(task.row, 2)
            if bar: bar.setValue(100)
            task.btn_download.setText("已完成")
            task.btn_download.setEnabled(False)
        elif message == "已取消":
            task.status = "已取消"
            self._update_status(task_id, "已取消", "#757575")
            self._log(f"⏹ 已取消: {task.title}")
            task.btn_download.setEnabled(True)
            task.btn_download.setText("重新下载")
        else:
            task.status = "失败"
            self._update_status(task_id, "失败", "#D32F2F")
            self._log(f"❌ 下载失败: {task.title} - {message}")
            task.btn_download.setEnabled(True)
            task.btn_download.setText("重试")
        
        task.btn_cancel.setEnabled(False)
        self.workers.pop(task_id, None)

    def _update_status(self, task_id: int, text: str, color: str):
        task = self.tasks.get(task_id)
        if task and hasattr(task, 'row'):
            item = self.table.item(task.row, 3)
            if item:
                item.setText(text)
                item.setForeground(QColor(color))

    def _log(self, msg: str):
        if hasattr(self, 'log_text'):
            self.log_text.append(msg)