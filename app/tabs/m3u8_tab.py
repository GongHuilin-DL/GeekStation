import os
import sys
import re
import json
import socket
import threading
import shutil

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QComboBox, QTableWidget, QTableWidgetItem, QProgressBar,
    QTextEdit, QFileDialog, QMessageBox, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from app.services.m3u8_service import (
    M3U8Task, logger, config_manager
)

class SnifferServer(threading.Thread):
    def __init__(self, tab):
        super().__init__(daemon=True)
        self.tab = tab
        self.running = True
        self.sock = None

    def run(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("127.0.0.1", 8765))
            self.sock.listen(5)
            self.sock.settimeout(1.0)
            logger.log("嗅探服务器启动，监听 127.0.0.1:8765")
            
            while self.running:
                try:
                    conn, _ = self.sock.accept()
                    data = conn.recv(4096).decode(errors='ignore')
                    try:
                        obj = json.loads(data)
                        url = obj.get("url")
                        headers = obj.get("headers", {})
                        if url and ".m3u8" in url:
                            logger.log(f"嗅探到 m3u8 (JSON): {url}")
                            # 使用信号/定时器机制在主线程处理
                            QTimer.singleShot(0, lambda u=url, h=headers: self.tab.add_sniffed(u, h))
                    except json.JSONDecodeError:
                        urls = re.findall(r"https?://[^\s\"']+\.m3u8[^\s\"']*", data)
                        if urls:
                            url = urls[0]
                            logger.log(f"嗅探到 m3u8 (plain): {url}")
                            QTimer.singleShot(0, lambda u=url: self.tab.add_sniffed(u, None))
                    conn.close()
                except socket.timeout:
                    continue
                except Exception:
                    break
        except Exception as e:
            logger.log(f"嗅探服务器异常: {e}")
            
    def stop(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass


class M3U8Tab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks = []
        self.links = []
        self.headers_map = {}
        
        # 检查 ffmpeg
        if not shutil.which("ffmpeg"):
            QMessageBox.warning(self, "环境提示", "未检测到 ffmpeg！\n视频合并功能将无法使用，请配置环境变量。")

        self._build_ui()
        
        # 启动嗅探
        self.sniffer = SnifferServer(self)
        self.sniffer.start()

        # 定时刷新 UI
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_ui)
        self.timer.start(500)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 代理与 URL 设置
        top = QHBoxLayout()
        self.proxy_checkbox = QCheckBox("使用代理")
        self.proxy_checkbox.setChecked(config_manager.data.get("use_proxy", False))
        
        self.proxy_ip = QLineEdit(config_manager.data.get("proxy_host", "127.0.0.1"))
        self.proxy_port = QLineEdit(str(config_manager.data.get("proxy_port", 7890)))
        self.proxy_ip.setFixedWidth(120)
        self.proxy_port.setFixedWidth(60)

        self.proxy_checkbox.stateChanged.connect(self.save_proxy_config)
        self.proxy_ip.editingFinished.connect(self.save_proxy_config)
        self.proxy_port.editingFinished.connect(self.save_proxy_config)

        top.addWidget(self.proxy_checkbox)
        top.addWidget(QLabel("IP:"))
        top.addWidget(self.proxy_ip)
        top.addWidget(QLabel("端口:"))
        top.addWidget(self.proxy_port)
        top.addSpacing(20)
        
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("输入网页URL或m3u8地址...")
        btn_parse = QPushButton("解析")
        btn_parse.clicked.connect(self.parse_url)
        
        self.combo = QComboBox()
        self.combo.setMinimumWidth(300)
        btn_add = QPushButton("添加下载任务")
        btn_add.setStyleSheet("background-color: #1565C0; color: white; font-weight: bold;")
        btn_add.clicked.connect(self.add_task)

        top.addWidget(self.url_edit, stretch=1)
        top.addWidget(btn_parse)
        top.addWidget(self.combo, stretch=1)
        top.addWidget(btn_add)
        layout.addLayout(top)

        # 表格
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["文件名", "进度", "状态", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 200)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 220)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # 日志
        layout.addWidget(QLabel("日志输出:"))
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("background-color: #1E1E1E; color: #00FF00; font-family: Consolas;")
        self.log_box.setMaximumHeight(150)
        layout.addWidget(self.log_box)

    def save_proxy_config(self):
        config_manager.data["use_proxy"] = self.proxy_checkbox.isChecked()
        config_manager.data["proxy_host"] = self.proxy_ip.text().strip()
        try:
            config_manager.data["proxy_port"] = int(self.proxy_port.text().strip() or 7890)
        except ValueError:
            config_manager.data["proxy_port"] = 7890
        config_manager.save()

    def add_sniffed(self, url, headers):
        if url not in self.links:
            self.links.append(url)
            self.headers_map[url] = headers
            self.combo.addItem(url)
            logger.log(f"嗅探添加: {url}")

    def parse_url(self):
        url = self.url_edit.text().strip()
        if not url: return
        
        try:
            if ".m3u8" in url:
                self.links = [url]
                self.headers_map[url] = config_manager.data["headers"]
            else:
                proxy = config_manager.get_proxy_url()
                proxies = {"http": proxy, "https": proxy} if proxy else None
                try:
                    import requests
                    resp = requests.get(url, headers=config_manager.data["headers"], timeout=10, proxies=proxies)
                except:
                    import requests
                    resp = requests.get(url, headers=config_manager.data["headers"], timeout=10, proxies={})
                resp.raise_for_status()
                
                self.links = re.findall(r"https?://[^\"']+\.m3u8[^\"']*", resp.text)
                if not self.links:
                    logger.log("未找到 m3u8 链接")
                    return
                for link in self.links:
                    self.headers_map[link] = config_manager.data["headers"]
                    
            self.combo.clear()
            for l in self.links:
                self.combo.addItem(l)
            logger.log(f"解析到 {len(self.links)} 个 m3u8 链接")
        except Exception as e:
            logger.log(f"解析失败: {e}")

    def add_task(self):
        idx = self.combo.currentIndex()
        if idx < 0 or idx >= len(self.links):
            QMessageBox.warning(self, "提示", "请先解析并选择一个链接")
            return

        default_dir = config_manager.data.get("download_path", "downloads")
        os.makedirs(default_dir, exist_ok=True)
        
        path, _ = QFileDialog.getSaveFileName(
            self, "保存为", os.path.join(default_dir, "video.mp4"), "MP4文件 (*.mp4)"
        )
        if not path: return

        url = self.links[idx]
        headers = self.headers_map.get(url, config_manager.data["headers"])
        task = M3U8Task(url, headers, path)
        self.tasks.append(task)

        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, 0, QTableWidgetItem(task.filename))

        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        self.table.setCellWidget(row, 1, progress_bar)

        self.table.setItem(row, 2, QTableWidgetItem(task.status))

        # 按钮组
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(2, 2, 2, 2)
        btn_start = QPushButton("开始")
        btn_pause = QPushButton("暂停")
        btn_resume = QPushButton("继续")
        btn_layout.addWidget(btn_start)
        btn_layout.addWidget(btn_pause)
        btn_layout.addWidget(btn_resume)
        self.table.setCellWidget(row, 3, btn_widget)

        btn_start.clicked.connect(lambda checked=False, t=task: t.start())
        btn_pause.clicked.connect(lambda checked=False, t=task: t.pause())
        btn_resume.clicked.connect(lambda checked=False, t=task: t.resume())

    def refresh_ui(self):
        for i, task in enumerate(self.tasks):
            if i >= self.table.rowCount(): break
            
            # 进度
            progress = int((task.downloaded / task.total) * 100) if task.total > 0 else 0
            bar = self.table.cellWidget(i, 1)
            if bar: bar.setValue(progress)
            
            # 状态
            status_item = QTableWidgetItem(task.status)
            if task.error or "失败" in task.status or "错误" in task.status:
                status_item.setForeground(QColor("#D32F2F"))
            elif task.status == "已完成":
                status_item.setForeground(QColor("#2E7D32"))
            elif task.status == "下载中":
                status_item.setForeground(QColor("#1565C0"))
            self.table.setItem(i, 2, status_item)

        # 日志
        logs = logger.get()
        if logs:
            self.log_box.setPlainText("\n".join(logs))
            scrollbar = self.log_box.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def shutdown(self):
        """释放资源"""
        self.timer.stop()
        if hasattr(self, 'sniffer') and self.sniffer:
            self.sniffer.stop()
        
        from app.services.m3u8_service import scheduler
        scheduler.stop()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)