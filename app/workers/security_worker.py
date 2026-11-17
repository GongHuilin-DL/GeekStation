import os
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject, QRunnable, Signal
from app.services.security_service import SecurityService


class SecurityWorkerSignals(QObject):
    progress = Signal(int, int)  # (当前完成数, 总数)
    log = Signal(str)
    finished = Signal()


class SecurityWorker(QRunnable):
    """处理批量文件加密/解密的后台任务。"""

    def __init__(self, password: str, raw_key: str, src_dir: str, dst_dir: str, mode: str, threads: int):
        super().__init__()
        self.password = password
        self.raw_key = raw_key
        self.src_dir = src_dir
        self.dst_dir = dst_dir
        self.mode = mode
        self.threads = threads
        self.signals = SecurityWorkerSignals()

    def run(self):
        try:
            # 简单过滤一下，避免把输出目录也抓进去
            files = [f for f in os.listdir(self.src_dir) if os.path.isfile(os.path.join(self.src_dir, f))]
            if not files:
                self.signals.log.emit("没有找到可处理的文件。")
                return

            os.makedirs(self.dst_dir, exist_ok=True)
            total = len(files)
            done = 0

            def task(f):
                nonlocal done
                src = os.path.join(self.src_dir, f)
                dst = os.path.join(self.dst_dir, f)
                try:
                    if self.mode == "encrypt":
                        SecurityService.encrypt_file(self.password, src, dst)
                    else:
                        SecurityService.decrypt_file(self.password, self.raw_key, src, dst)
                    self.signals.log.emit(f"✅ 完成: {f}")
                except Exception as e:
                    self.signals.log.emit(f"❌ 失败: {f} -> {e}")
                
                done += 1
                self.signals.progress.emit(done, total)

            with ThreadPoolExecutor(max_workers=self.threads) as executor:
                executor.map(task, files)

        finally:
            self.signals.finished.emit()