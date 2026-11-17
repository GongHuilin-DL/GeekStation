import os
import re
import sys
import uuid
import shutil
import tempfile
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, unquote

from PySide6.QtCore import QObject, QRunnable, Signal

class M3U8Parser:
    """M3U8 媒体播放列表解析器。"""
    def __init__(self, playlist_path):
        self.playlist_path = Path(playlist_path).resolve()
        self.base_dir = self.playlist_path.parent
        self.segments = []
        self.missing = []
        self.empty = []
        self.all_segments = []
        self.total_duration = 0.0
        self.valid_duration = 0.0
        self.total_count = 0
        self.global_lines = []
        self.trailing_lines = []
        self.has_aes128_default_iv = False

    def parse(self):
        self.segments.clear()
        self.missing.clear()
        self.empty.clear()
        self.all_segments.clear()
        self.total_duration = 0.0
        self.valid_duration = 0.0
        self.total_count = 0
        self.global_lines.clear()
        self.trailing_lines.clear()
        self.has_aes128_default_iv = False

        if not self.playlist_path.is_file():
            raise FileNotFoundError(f"找不到 M3U8 文件：{self.playlist_path}")

        content = self.playlist_path.read_text(encoding="utf-8-sig")
        lines = [line.strip() for line in content.splitlines() if line.strip()]

        if not lines or lines[0] != "#EXTM3U":
            raise ValueError("无效的 M3U8 文件。")

        for line in lines:
            if line.startswith("#EXT-X-STREAM-INF") or line.startswith("#EXT-X-I-FRAME-STREAM-INF"):
                raise ValueError("检测到 M3U8 主播放列表，请选择具体媒体播放列表。")
            if line.startswith("#EXT-X-MAP:"):
                raise ValueError("检测到 EXT-X-MAP，当前版本暂不支持 fMP4 HLS。")

        self._check_encryption(lines)

        pending_lines = []
        has_extinf = False
        pending_duration = 0.0

        for line in lines[1:]:
            if line.startswith("#EXTINF:"):
                if has_extinf:
                    raise ValueError("M3U8 格式错误：前一个 EXTINF 缺少 URI。")
                has_extinf = True
                pending_lines.append(line)
                match = re.match(r"#EXTINF:([0-9]+(?:\.[0-9]+)?)", line)
                pending_duration = float(match.group(1)) if match else 0.0
                continue

            if line.startswith("#"):
                if self.total_count == 0 and not has_extinf:
                    self.global_lines.append(line)
                else:
                    pending_lines.append(line)
                continue

            if not has_extinf:
                raise ValueError(f"发现没有对应 EXTINF 的 URI：{line}")

            item = {
                "sequence": self.total_count,
                "uri": line,
                "path": self._resolve_uri(line),
                "duration": pending_duration,
                "block": list(pending_lines),
                "status": None
            }
            self.total_count += 1
            self.total_duration += pending_duration

            is_gap = "#EXT-X-GAP" in pending_lines
            if is_gap:
                item["status"] = "missing"
                self.missing.append(item)
            elif not item["path"].is_file():
                item["status"] = "missing"
                self.missing.append(item)
            elif item["path"].stat().st_size == 0:
                item["status"] = "empty"
                self.empty.append(item)
            else:
                item["status"] = "valid"
                self.segments.append(item)
                self.valid_duration += pending_duration

            self.all_segments.append(item)
            pending_lines = []
            has_extinf = False
            pending_duration = 0.0

        if has_extinf:
            raise ValueError("M3U8 格式错误：最后一个 EXTINF 缺少 URI。")

        self.trailing_lines = pending_lines
        if not self.segments:
            raise ValueError("没有找到可用的 TS 分片。")
        return True

    def _resolve_uri(self, uri):
        parsed = urlsplit(uri)
        if parsed.scheme or parsed.netloc:
            raise ValueError(f"不支持远程 TS 地址：{uri}")
        relative_path = unquote(parsed.path)
        if not relative_path:
            raise ValueError(f"无效的 TS URI：{uri}")
        path = Path(relative_path)
        if not path.is_absolute():
            path = self.base_dir / path
        return path.resolve()

    def _check_encryption(self, lines):
        for line in lines:
            if not line.startswith("#EXT-X-KEY:"):
                continue
            method_match = re.search(r'(?:^|,)METHOD=([^,]+)', line)
            if not method_match:
                continue
            method = method_match.group(1).strip()
            if method == "NONE":
                continue
            if method != "AES-128":
                raise ValueError(f"不支持的加密方式：{method}")
            keyformat_match = re.search(r'(?:^|,)KEYFORMAT="([^"]+)"', line)
            if keyformat_match and keyformat_match.group(1) != "identity":
                raise ValueError("不支持非 identity 类型的 AES-128 密钥。")
            if not re.search(r'(?:^|,)IV=', line):
                self.has_aes128_default_iv = True
            uri_match = re.search(r'URI="([^"]+)"', line)
            if not uri_match:
                raise ValueError("AES-128 密钥标签缺少 URI。")
            key_uri = uri_match.group(1)
            parsed = urlsplit(key_uri)
            if parsed.scheme in ("http", "https"):
                raise ValueError("当前版本不支持远程 AES-128 密钥。")
            if parsed.scheme:
                raise ValueError(f"不支持的密钥协议：{parsed.scheme}")
            key_path = Path(unquote(parsed.path))
            if not key_path.is_absolute():
                key_path = self.base_dir / key_path
            if not key_path.is_file():
                raise FileNotFoundError(f"本地密钥文件不存在：{key_path}")

    def create_repaired_playlist(self):
        if self.has_aes128_default_iv and (self.missing or self.empty):
            raise ValueError(
                "检测到 AES-128 默认 IV 模式，同时存在缺失分片。\n\n"
                "由于 AES 默认 IV 与媒体序列号有关，删除中间分片后可能导致后续分片解密错误。\n"
                "为避免生成错误视频，本程序拒绝自动修复这种情况。"
            )

        output_lines = ["#EXTM3U"] + self.global_lines
        for item in self.all_segments:
            if item["status"] == "valid":
                output_lines.extend(item["block"])
                output_lines.append(item["uri"])
            else:
                for tag in item["block"]:
                    if tag.startswith("#EXTINF:") or tag.startswith("#EXT-X-BYTERANGE:") or tag == "#EXT-X-GAP" or tag.startswith("#EXT-X-PROGRAM-DATE-TIME:"):
                        continue
                    output_lines.append(tag)

        output_lines.extend(self.trailing_lines)
        if not any(line == "#EXT-X-ENDLIST" for line in output_lines):
            output_lines.append("#EXT-X-ENDLIST")

        fd, temp_path = tempfile.mkstemp(prefix=".m3u8_repaired_", suffix=".m3u8", dir=str(self.base_dir))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("\n".join(output_lines) + "\n")
        except Exception:
            try: os.unlink(temp_path)
            except OSError: pass
            raise
        return Path(temp_path)

    def get_all_source_paths(self):
        paths = {self.playlist_path.resolve()}
        for item in self.all_segments:
            paths.add(item["path"].resolve())
        return paths


class FFmpegWorkerSignals(QObject):
    log = Signal(str)
    progress = Signal(int)
    finished = Signal(bool, str)  # (success, message_or_output_path)


class FFmpegWorker(QRunnable):
    """使用 FFmpeg HLS 解复用器和 -c copy 进行无损流复制的后台任务。"""
    def __init__(self, ffmpeg_path, playlist_path, output_path, total_duration):
        super().__init__()
        self.ffmpeg_path = ffmpeg_path
        self.playlist_path = Path(playlist_path)
        self.output_path = Path(output_path)
        self.total_duration = total_duration
        self.signals = FFmpegWorkerSignals()
        self.process = None
        self.cancel_event = False

    def run(self):
        command = [
            self.ffmpeg_path, "-y", "-hide_banner", "-loglevel", "warning",
            "-stats_period", "0.5", "-protocol_whitelist", "file,crypto,data",
            "-allowed_extensions", "ALL", "-i", str(self.playlist_path),
            "-map", "0", "-c", "copy", "-progress", "pipe:1", "-nostats",
            "-f", "mpegts", str(self.output_path)
        ]
        
        self.signals.log.emit("正在启动 FFmpeg...")
        self.signals.log.emit("FFmpeg 命令：\n" + subprocess.list2cmdline(command))

        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        
        try:
            self.process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                creationflags=creation_flags
            )
        except Exception as e:
            self.signals.finished.emit(False, f"启动 FFmpeg 失败: {e}")
            return

        last_percent = -1
        try:
            for line in self.process.stdout:
                if self.cancel_event:
                    break
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith("out_time_us="):
                    try:
                        current_time = int(line.split("=", 1)[1]) / 1_000_000
                        if self.total_duration > 0:
                            percent = min(99, int(current_time / self.total_duration * 100))
                            if percent != last_percent:
                                last_percent = percent
                                self.signals.progress.emit(percent)
                    except (ValueError, ZeroDivisionError):
                        pass
                elif line.startswith("progress="):
                    if line.endswith("end"):
                        self.signals.progress.emit(100)
                else:
                    self.signals.log.emit(line)

            return_code = self.process.wait()
            if self.cancel_event:
                self.signals.finished.emit(False, "用户取消了合并任务。")
                return
            if return_code != 0:
                self.signals.finished.emit(False, f"FFmpeg 执行失败，退出代码：{return_code}")
                return
            if not self.output_path.is_file() or self.output_path.stat().st_size == 0:
                self.signals.finished.emit(False, "FFmpeg 执行结束，但输出文件不存在或为空。")
                return
                
            self.signals.progress.emit(100)
            self.signals.finished.emit(True, str(self.output_path))
            
        except Exception as e:
            if self.process and self.process.poll() is None:
                self.process.kill()
                self.process.wait()
            self.signals.finished.emit(False, str(e))

    def cancel(self):
        self.cancel_event = True
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()