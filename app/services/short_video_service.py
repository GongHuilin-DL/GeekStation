import os
import re
import time
import requests
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal


class VideoParser:
    """短视频分享链接解析器（优先聚合API，备用抖音直链）。"""
    
    @staticmethod
    def extract_url(text: str) -> str | None:
        """从分享文案中提取 URL。"""
        match = re.search(r'https?://[^\s"\']+', text)
        return match.group(0) if match else None

    @staticmethod
    def parse(url: str) -> dict:
        """
        解析视频信息。
        返回 dict: {"title", "video_url", "platform", "error"}
        """
        # 1. 优先使用聚合解析 API（兼容抖音/快手等）
        try:
            resp = requests.post(
                "https://video.zacao.top/api/parse",
                json={"text": url},
                headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
                timeout=15,
            )
            data = resp.json()
            if data.get("code") == 200 and data.get("succ"):
                info = data.get("data", {})
                video_url = info.get("source_video_url") or info.get("video_url")
                if video_url:
                    return {
                        "title": info.get("title", "未命名视频")[:80],
                        "video_url": video_url,
                        "platform": info.get("platform", "未知"),
                        "error": "",
                    }
        except Exception:
            pass

        # 2. 备用：抖音免登录直链解析
        if "douyin.com" in url:
            return VideoParser._parse_douyin_fallback(url)

        return {"title": "", "video_url": "", "platform": "", "error": "解析失败，链接可能失效或平台不支持。"}

    @staticmethod
    def _parse_douyin_fallback(url: str) -> dict:
        """抖音备用解析：提取 video_id 构造直链。"""
        headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"}
        try:
            resp = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
            match = re.search(r'"video_id":"(v[0-9a-zA-Z]+)"', resp.text)
            if match:
                video_id = match.group(1)
                play_api = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={video_id}&ratio=1080p&line=0"
                return {
                    "title": f"douyin_{video_id[:8]}",
                    "video_url": play_api,
                    "platform": "抖音",
                    "error": "",
                }
        except Exception:
            pass
        return {"title": "", "video_url": "", "platform": "抖音", "error": "抖音直链解析失败。"}


class DownloadTask:
    """单个视频下载任务的数据模型。"""
    def __init__(self, task_id: int, title: str, url: str, save_path: str, platform: str):
        self.id = task_id
        self.title = title
        self.url = url
        self.save_path = save_path
        self.platform = platform
        
        self.downloaded = 0
        self.total = 0
        self.progress = 0
        self.status = "等待下载"
        self.cancelled = False


class VideoDownloadSignals(QObject):
    log = Signal(str)
    progress = Signal(int, int)      # (task_id, percent)
    finished = Signal(int, bool, str)  # (task_id, success, message)


class VideoDownloadWorker(QRunnable):
    """流式下载视频（支持取消）。"""
    def __init__(self, task: DownloadTask):
        super().__init__()
        self.task = task
        self.signals = VideoDownloadSignals()

    def run(self):
        try:
            self.signals.log.emit(f"开始下载: {self.task.title}")
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            
            with requests.get(self.task.url, headers=headers, stream=True, timeout=60, allow_redirects=True) as r:
                r.raise_for_status()
                self.task.total = int(r.headers.get('content-length', 0))
                
                os.makedirs(os.path.dirname(self.task.save_path) or ".", exist_ok=True)
                tmp_path = self.task.save_path + ".tmp"
                
                with open(tmp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if self.task.cancelled:
                            f.close()
                            if os.path.exists(tmp_path):
                                os.remove(tmp_path)
                            self.signals.finished.emit(self.task.id, False, "已取消")
                            return
                        
                        if chunk:
                            f.write(chunk)
                            self.task.downloaded += len(chunk)
                            if self.task.total > 0:
                                percent = int(self.task.downloaded / self.task.total * 100)
                                if percent != self.task.progress:
                                    self.task.progress = percent
                                    self.signals.progress.emit(self.task.id, percent)
                
                # 原子重命名
                os.replace(tmp_path, self.task.save_path)
                self.signals.finished.emit(self.task.id, True, self.task.save_path)
                
        except Exception as e:
            # 清理临时文件
            tmp_path = self.task.save_path + ".tmp"
            if os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except: pass
            self.signals.finished.emit(self.task.id, False, str(e))