import os
import re
import time
import json
import shutil
import asyncio
import threading
import subprocess
from collections import deque
from urllib.parse import urljoin

import requests
import aiohttp
from Crypto.Cipher import AES

from app.utils.storage import get_base_dir

# DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DATA_DIR = get_base_dir()
CONFIG_PATH = os.path.join(DATA_DIR, "data", "m3u8_config.json")

DEFAULT_CONFIG = {
    "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
    "download_path": os.path.join(DATA_DIR, "downloads"),
    "max_threads": 32,
    "per_task_threads": 8,
    "retry_count": 5,
    "retry_backoff": 0.5,
    "use_proxy": False,
    "proxy_host": "127.0.0.1",
    "proxy_port": 7890
}

class M3U8Config:
    def __init__(self):
        self.data = self._load()
        
    def _load(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            return DEFAULT_CONFIG.copy()
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return DEFAULT_CONFIG.copy()

    def save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2)

    def get_proxy_url(self):
        if not self.data.get("use_proxy", False):
            return None
        host = self.data.get("proxy_host", "127.0.0.1")
        port = self.data.get("proxy_port", 7890)
        return f"http://{host}:{port}"

config_manager = M3U8Config()

class M3U8Logger:
    def __init__(self):
        self.logs = deque(maxlen=1000)
        self.lock = threading.Lock()

    def log(self, msg):
        with self.lock:
            t = time.strftime("%H:%M:%S")
            self.logs.append(f"[{t}] {msg}")

    def get(self):
        with self.lock:
            return list(self.logs)

logger = M3U8Logger()

class AsyncScheduler:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.global_sem = None
        
        def start_loop():
            asyncio.set_event_loop(self.loop)
            # 在事件循环所在线程中安全地创建信号量
            self.global_sem = asyncio.Semaphore(config_manager.data.get("max_threads", 32))
            self.loop.run_forever()
            
        self._thread = threading.Thread(target=start_loop, daemon=True)
        self._thread.start()

    def submit(self, coro):
        asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop(self):
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
            self._thread.join(timeout=2)

scheduler = AsyncScheduler()

def parse_m3u8(url, headers):
    """返回 (ts_url列表, 密钥二进制数据)"""
    try:
        proxy = config_manager.get_proxy_url()
        proxies = {"http": proxy, "https": proxy} if proxy else None
        try:
            r = requests.get(url, headers=headers, timeout=10, proxies=proxies)
        except:
            r = requests.get(url, headers=headers, timeout=10, proxies={})
        r.raise_for_status()
    except Exception as e:
        logger.log(f"解析 m3u8 失败: {e}")
        return [], None

    lines = r.text.splitlines()
    ts_list = []
    key = None

    for line in lines:
        line = line.strip()
        if line.startswith("#EXT-X-KEY"):
            uri = re.search(r'URI="(.*?)"', line)
            if uri:
                key_url = urljoin(url, uri.group(1))
                try:
                    proxy = config_manager.get_proxy_url()
                    proxies = {"http": proxy, "https": proxy} if proxy else None
                    try:
                        key = requests.get(key_url, headers=headers, timeout=10, proxies=proxies).content
                    except:
                        key = requests.get(key_url, headers=headers, timeout=10, proxies={}).content
                    logger.log(f"获取 AES 密钥成功")
                except Exception as e:
                    logger.log(f"密钥下载失败: {e}")
        elif line and not line.startswith("#"):
            ts_list.append(urljoin(url, line))
    return ts_list, key


class M3U8Task:
    def __init__(self, url, headers, path):
        self.url = url
        self.headers = headers if headers else config_manager.data["headers"]
        self.path = path
        self.filename = os.path.basename(path)
        self.temp = path + "_tmp"

        self.ts = []
        self.key = None
        self.total = 0
        self.downloaded = 0
        self.paused = False
        self.error = False
        self.status = "等待中"
        self._lock = threading.Lock()

    def prepare(self):
        logger.log(f"解析 m3u8: {self.url}")
        self.ts, self.key = parse_m3u8(self.url, self.headers)
        self.total = len(self.ts)
        if self.total == 0:
            raise ValueError("未找到任何 ts 分片")
        os.makedirs(self.temp, exist_ok=True)

    def decrypt(self, data, idx):
        if not self.key:
            return data
        iv = idx.to_bytes(16, 'big')
        return AES.new(self.key, AES.MODE_CBC, iv).decrypt(data)

    async def _run_async(self):
        connector = aiohttp.TCPConnector(limit=config_manager.data["max_threads"], ssl=False)
        timeout = aiohttp.ClientTimeout(total=60)
        
        async with aiohttp.ClientSession(
            connector=connector, timeout=timeout, trust_env=False
        ) as session:
            sem = asyncio.Semaphore(config_manager.data["per_task_threads"])
            proxy = config_manager.get_proxy_url()

            async def worker(idx, url):
                async with sem:
                    async with scheduler.global_sem:
                        await self.download_segment_async(session, proxy, idx, url)

            tasks = []
            for i, u in enumerate(self.ts):
                if i < self.downloaded:
                    continue
                tasks.append(worker(i, u))

            await asyncio.gather(*tasks)

        if self.error:
            self.status = "错误"
        elif self.paused:
            self.status = "已暂停"
        else:
            self.merge()

    async def download_segment_async(self, session, proxy, idx, url):
        if self.paused or self.error:
            return

        for attempt in range(config_manager.data["retry_count"]):
            try:
                async with session.get(url, headers=self.headers, timeout=15, proxy=proxy) as r:
                    r.raise_for_status()
                    data = await r.read()
                    data = self.decrypt(data, idx)

                    seg_path = os.path.join(self.temp, f"{idx}.ts")
                    with open(seg_path, 'wb') as f:
                        f.write(data)

                    with self._lock:
                        self.downloaded += 1
                    return
            except Exception as e:
                if attempt < config_manager.data["retry_count"] - 1:
                    await asyncio.sleep(config_manager.data["retry_backoff"] * (attempt + 1))
                else:
                    logger.log(f"分片 {idx} 失败: {e}")
                    self.error = True
                    self.status = "错误"

    def start(self):
        if self.status in ["已完成", "合并中", "下载中"]:
            return

        if self.status == "等待中":
            self.status = "准备中"
            def prepare_and_start():
                try:
                    self.prepare()
                    self._start_download()
                except Exception as e:
                    self.status = "错误"
                    self.error = True
                    logger.log(f"任务准备失败: {e}")
            
            threading.Thread(target=prepare_and_start, daemon=True).start()
        else:
            self._start_download()

    def _start_download(self):
        self.paused = False
        self.error = False
        self.status = "下载中"
        scheduler.submit(self._run_async())

    def pause(self):
        self.paused = True
        self.status = "已暂停"

    def resume(self):
        if self.status == "已暂停":
            self.start()

    def merge(self):
        self.status = "合并中"
        logger.log(f"开始合并: {self.filename}")
        
        # 使用绝对路径防止 ffmpeg 找不到文件
        abs_temp = os.path.abspath(self.temp)
        abs_path = os.path.abspath(self.path)
        lst_path = os.path.join(abs_temp, "list.txt")
        
        with open(lst_path, 'w', encoding='utf-8') as f:
            for i in range(self.total):
                seg_path = os.path.join(abs_temp, f"{i}.ts").replace("\\", "/")
                f.write(f"file '{seg_path}'\n")
                
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst_path, "-c", "copy", abs_path],
                check=True, capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW  # 防止弹出黑框
            )
            self.status = "已完成"
            logger.log(f"完成: {self.filename}")
            # 清理临时文件
            try:
                shutil.rmtree(abs_temp)
            except:
                pass
        except Exception as e:
            self.status = "合并失败"
            self.error = True
            logger.log(f"合并错误: {e}")