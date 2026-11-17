import os
import uuid
import shutil
from pathlib import Path
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QMessageBox, QProgressBar, QTextEdit, QGroupBox,
    QGridLayout, QSplitter
)

from app.services.merge_service import M3U8Parser, FFmpegWorker


class MergeTab(QWidget):
    """本地 M3U8 / TS 视频合并工具。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parser = None
        self.ffmpeg_worker = None
        self.repaired_playlist = None
        self.temp_output = None
        self.working = False
        
        self._thread_pool = QThreadPool.globalInstance()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        title = QLabel("M3U8 TS 视频合并工具")
        title.setStyleSheet("font-size: 18px; font-weight: bold;") # 去除硬编码颜色
        root.addWidget(title)
        
        subtitle = QLabel("HLS 分片检测 | 缺失文件处理 | FFmpeg 无损流复制")
        subtitle.setStyleSheet("font-size: 11pt;") # 去除 hardcode 灰色
        root.addWidget(subtitle)

        # ================= 1. 输入与配置区 =================
        config_group = QGroupBox("路径与配置")
        config_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        grid = QGridLayout(config_group)
        grid.setSpacing(10)

        grid.addWidget(QLabel("视频源目录:"), 0, 0)
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("选择包含 index.m3u8 的视频目录...")
        grid.addWidget(self.source_input, 0, 1)
        btn_browse_src = QPushButton("浏览...")
        btn_browse_src.clicked.connect(self._select_source)
        grid.addWidget(btn_browse_src, 0, 2)

        grid.addWidget(QLabel("输出文件:"), 1, 0)
        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText("选择合并后的 TS 输出路径...")
        grid.addWidget(self.output_input, 1, 1)
        btn_browse_out = QPushButton("选择...")
        btn_browse_out.clicked.connect(self._select_output)
        grid.addWidget(btn_browse_out, 1, 2)

        grid.addWidget(QLabel("FFmpeg 路径:"), 2, 0)
        self.ffmpeg_input = QLineEdit()
        self.ffmpeg_input.setText(shutil.which("ffmpeg") or "")
        self.ffmpeg_input.setPlaceholderText("自动检测或手动指定 ffmpeg.exe 路径...")
        grid.addWidget(self.ffmpeg_input, 2, 1)
        btn_browse_ff = QPushButton("浏览...")
        btn_browse_ff.clicked.connect(self._select_ffmpeg)
        grid.addWidget(btn_browse_ff, 2, 2)

        root.addWidget(config_group)

        # ================= 2. 操作与控制区 =================
        ctrl_layout = QHBoxLayout()
        self.btn_scan = QPushButton("① 检测 TS 分片")
        self.btn_scan.setStyleSheet("font-weight: bold; padding: 6px 15px;") # 去除背景色写死
        self.btn_scan.clicked.connect(self._scan)
        ctrl_layout.addWidget(self.btn_scan)

        self.btn_merge = QPushButton("② 开始合并")
        self.btn_merge.setStyleSheet("font-weight: bold; padding: 6px 15px;")
        self.btn_merge.setEnabled(False)
        self.btn_merge.clicked.connect(self._start_merge)
        ctrl_layout.addWidget(self.btn_merge)

        self.btn_cancel = QPushButton("取消任务")
        self.btn_cancel.setStyleSheet("color: #D32F2F; padding: 6px 15px;")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel)
        ctrl_layout.addWidget(self.btn_cancel)
        
        ctrl_layout.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(300)
        ctrl_layout.addWidget(self.progress_bar)

        root.addLayout(ctrl_layout)

        # ================= 3. 结果与日志区 =================
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setStyleSheet("font-family: Consolas; font-size: 10pt;") # 去除背景色写死
        self.result_text.setPlaceholderText("分片检测结果将显示在这里...")
        splitter.addWidget(self.result_text)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #1E1E1E; color: #00FF00; font-family: Consolas; font-size: 10pt;")
        self.log_text.setPlaceholderText("FFmpeg 运行日志...")
        splitter.addWidget(self.log_text)
        
        splitter.setSizes([200, 200])
        root.addWidget(splitter, stretch=1)

    # ================= 选择与配置 =================

    def _select_source(self):
        if self.working: return
        path = QFileDialog.getExistingDirectory(self, "选择包含 index.m3u8 的视频目录")
        if path:
            self.source_input.setText(path)
            self.output_input.setText(os.path.join(path, "merged.ts"))
            self.parser = None
            self.btn_merge.setEnabled(False)
            self.result_text.setText("等待执行分片检测...")
            self._log(f"已选择源目录：{path}")

    def _select_output(self):
        if self.working: return
        path, _ = QFileDialog.getSaveFileName(
            self, "选择输出文件", "", "MPEG Transport Stream (*.ts);;所有文件 (*)"
        )
        if path:
            self.output_input.setText(path)

    def _select_ffmpeg(self):
        if self.working: return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 FFmpeg 可执行文件", "", "FFmpeg (ffmpeg.exe);;所有文件 (*)"
        )
        if path:
            self.ffmpeg_input.setText(path)

    # ================= 核心流程 =================

    def _scan(self):
        if self.working: return
        source = Path(self.source_input.text().strip())
        if not source.is_dir():
            QMessageBox.warning(self, "错误", "请先选择有效的视频源目录。")
            return
        
        playlist = source / "index.m3u8"
        if not playlist.is_file():
            QMessageBox.warning(self, "错误", "源目录中不存在 index.m3u8。")
            return

        self.parser = None
        self.btn_merge.setEnabled(False)
        self._log("开始解析 M3U8 播放列表...")
        
        try:
            parser = M3U8Parser(playlist)
            parser.parse()
            self.parser = parser
            
            total = len(parser.segments) + len(parser.missing) + len(parser.empty)
            report = [
                f"播放列表：{playlist.name}",
                f"TS 分片总数：{total}",
                f"有效分片：{len(parser.segments)}",
                f"缺失分片：{len(parser.missing)}",
                f"空文件分片：{len(parser.empty)}",
                f"原始分片时长合计：{parser.total_duration:.2f} 秒",
                f"有效分片时长合计：{parser.valid_duration:.2f} 秒"
            ]
            
            if parser.missing:
                report.append("\n缺失分片：")
                for item in parser.missing[:30]:
                    report.append(f"  #{item['sequence']} {item['path'].name}")
                if len(parser.missing) > 30:
                    report.append(f"  ... 还有 {len(parser.missing) - 30} 个")
                    
            if parser.empty:
                report.append("\n空文件：")
                for item in parser.empty[:30]:
                    report.append(f"  #{item['sequence']} {item['path'].name}")
                if len(parser.empty) > 30:
                    report.append(f"  ... 还有 {len(parser.empty) - 30} 个")

            self.result_text.setText("\n".join(report))
            self._log(f"检测完成：有效 {len(parser.segments)}，缺失 {len(parser.missing)}，空文件 {len(parser.empty)}。")
            
            if parser.missing or parser.empty:
                self._log("警告：检测到缺失或空文件，这些分片的原始内容无法通过合并恢复。")

            self.btn_merge.setEnabled(True)
            
        except Exception as e:
            self.parser = None
            self.result_text.setText(f"检测失败：\n{e}")
            self._log(f"检测失败：{e}")
            QMessageBox.critical(self, "检测失败", str(e))

    def _start_merge(self):
        if self.working or not self.parser: return
        
        output_text = self.output_input.text().strip()
        if not output_text:
            QMessageBox.warning(self, "错误", "请指定输出文件路径。")
            return
        output = Path(output_text).expanduser().resolve()
        if output.suffix.lower() != ".ts":
            output = output.with_suffix(".ts")
            self.output_input.setText(str(output))

        ffmpeg_text = self.ffmpeg_input.text().strip()
        if not ffmpeg_text:
            QMessageBox.warning(self, "错误", "请配置 FFmpeg 路径。")
            return
        ffmpeg = Path(ffmpeg_text).expanduser().resolve()
        if not ffmpeg.is_file():
            QMessageBox.warning(self, "错误", f"找不到 FFmpeg 可执行文件：\n{ffmpeg}")
            return

        if output in self.parser.get_all_source_paths():
            QMessageBox.warning(self, "错误", "输出文件不能覆盖原始 M3U8 或 TS 分片。")
            return

        if output.exists():
            reply = QMessageBox.question(self, "确认覆盖", f"输出文件已经存在：\n{output}\n\n是否覆盖？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return

        output.parent.mkdir(parents=True, exist_ok=True)

        if self.parser.missing or self.parser.empty:
            warning = (
                f"检测结果：\n\n缺失分片：{len(self.parser.missing)} 个\n空文件：{len(self.parser.empty)} 个\n\n"
                "程序将跳过这些分片。\n缺失内容无法恢复，输出视频可能出现画面或音频跳跃。\n\n是否继续？"
            )
            reply = QMessageBox.warning(self, "分片完整性警告", warning, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return

        try:
            self.repaired_playlist = self.parser.create_repaired_playlist()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"生成临时 M3U8 失败：\n{e}")
            return

        temp_name = f".m3u8_merger_{uuid.uuid4().hex}.ts"
        self.temp_output = output.parent / temp_name

        self.working = True
        self.btn_scan.setEnabled(False)
        self.btn_merge.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        self.log_text.clear()
        
        self._log("开始合并 TS 分片...")
        self._log(f"有效分片数量：{len(self.parser.segments)}")
        self._log(f"预计有效内容时长：{self.parser.valid_duration:.2f} 秒")
        self._log(f"输出路径：{output}")

        self.ffmpeg_worker = FFmpegWorker(
            str(ffmpeg), str(self.repaired_playlist), str(self.temp_output), self.parser.valid_duration
        )
        self.ffmpeg_worker.signals.log.connect(self._log)
        self.ffmpeg_worker.signals.progress.connect(self.progress_bar.setValue)
        self.ffmpeg_worker.signals.finished.connect(lambda success, msg: self._on_merge_finished(success, msg, output))
        
        self._thread_pool.start(self.ffmpeg_worker)

    def _cancel(self):
        if not self.working or not self.ffmpeg_worker: return
        reply = QMessageBox.question(self, "确认取消", "确定要终止当前合并任务吗？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.btn_cancel.setEnabled(False)
            self._log("正在终止 FFmpeg...")
            self.ffmpeg_worker.cancel()

    def _on_merge_finished(self, success: bool, msg: str, final_output: Path):
        self._finish_cleanup()
        
        if success:
            try:
                os.replace(self.temp_output, final_output)
                size_mb = final_output.stat().st_size / 1024 / 1024
                self._log(f"合并成功：{final_output}")
                self._log(f"文件大小：{size_mb:.2f} MB")
                QMessageBox.information(self, "合并成功", f"视频合并完成！\n\n输出文件：\n{final_output}\n\n文件大小：{size_mb:.2f} MB")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"重命名输出文件失败：{e}")
        else:
            self._log(f"任务结束/失败：{msg}")
            if "取消" not in msg:
                QMessageBox.critical(self, "合并失败", str(msg))

    def _finish_cleanup(self):
        self.working = False
        self.ffmpeg_worker = None
        self.btn_scan.setEnabled(True)
        self.btn_merge.setEnabled(True if self.parser else False)
        self.btn_cancel.setEnabled(False)

        if self.repaired_playlist:
            try: self.repaired_playlist.unlink(missing_ok=True)
            except OSError: pass
            self.repaired_playlist = None

        if self.temp_output and self.temp_output.exists():
            try: self.temp_output.unlink(missing_ok=True)
            except OSError: pass
        self.temp_output = None

    def _log(self, message):
        self.log_text.append(message)

    def shutdown(self):
        if self.working and self.ffmpeg_worker:
            self.ffmpeg_worker.cancel()