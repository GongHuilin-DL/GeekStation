import os
import sys
import shutil
import subprocess
from PySide6.QtCore import QObject, QProcess, Signal

from app.utils.storage import load_json, save_json, get_base_dir

# DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DATA_DIR = get_base_dir()
CONFIG_FILE = os.path.join(DATA_DIR, "data", "scrcpy_config.json")

DEFAULT_CONFIG = {
    "scrcpy_path": "",
    "adb_path": "",
    "last_usb_serial": "",
    "last_wifi_ip": "",
    "last_connect_port": 5555,
    "last_pair_port": 0,
    "args": {
        "video_codec": "h265",
        "max_size": 1920,
        "max_fps": 60,
        "turn_screen_off": True,
        "stay_awake": True,
        "keyboard_mode": "uhid",
        "no_audio": True,
    }
}

def load_config() -> dict:
    cfg = load_json(CONFIG_FILE, DEFAULT_CONFIG.copy())
    # 兜底合并
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    cfg.setdefault("args", {})
    for k, v in DEFAULT_CONFIG["args"].items():
        cfg["args"].setdefault(k, v)
    return cfg

def save_config(cfg: dict):
    save_json(CONFIG_FILE, cfg)

def find_scrcpy() -> str:
    return shutil.which("scrcpy") or ""

def find_adb() -> str:
    adb = shutil.which("adb")
    return adb or ""

def get_help_text(scrcpy_path: str) -> str:
    if not scrcpy_path or not os.path.isfile(scrcpy_path):
        return "scrcpy 路径无效。"
    try:
        result = subprocess.run(
            [scrcpy_path, "--help"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        return result.stdout or result.stderr or "(无输出)"
    except Exception as e:
        return f"获取帮助信息失败: {e}"

def get_devices(adb_path: str) -> list[dict]:
    """获取已连接设备（包括 USB 和 TCP/IP）。"""
    if not adb_path or not os.path.isfile(adb_path):
        return []
    try:
        result = subprocess.run(
            [adb_path, "devices", "-l"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        devices = []
        for line in result.stdout.splitlines()[1:]:
            line = line.strip()
            if not line or "offline" in line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                serial = parts[0]
                state = parts[1]
                model = ""
                for p in parts[2:]:
                    if p.startswith("model:"):
                        model = p.split(":", 1)[1].replace("_", " ")
                        break
                devices.append({"serial": serial, "state": state, "model": model or serial})
        return devices
    except Exception:
        return []

def adb_pair(adb_path: str, ip: str, port: int, code: str) -> tuple[bool, str]:
    """执行 adb pair 进行无线配对。"""
    try:
        result = subprocess.run(
            [adb_path, "pair", f"{ip}:{port}", code],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        out = (result.stdout or "") + (result.stderr or "")
        if "Successfully paired" in out or "successfully" in out.lower():
            return True, out.strip()
        return False, out.strip() or "配对失败"
    except Exception as e:
        return False, str(e)

def adb_connect(adb_path: str, ip: str, port: int) -> tuple[bool, str]:
    """执行 adb connect。"""
    try:
        result = subprocess.run(
            [adb_path, "connect", f"{ip}:{port}"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        out = (result.stdout or "") + (result.stderr or "")
        if "connected" in out.lower() and "cannot" not in out.lower():
            return True, out.strip()
        return False, out.strip() or "连接失败"
    except Exception as e:
        return False, str(e)

def adb_disconnect(adb_path: str, ip: str, port: int) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [adb_path, "disconnect", f"{ip}:{port}"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        return True, result.stdout.strip() or "已断开连接"
    except Exception as e:
        return False, str(e)

def collect_device_info(adb_path: str, serial: str = "") -> dict:
    """执行一组 adb 命令，返回原始输出字典。"""
    info = {}
    base = [adb_path]
    if serial:
        base += ["-s", serial]
    
    commands = {
        "model": ["shell", "getprop", "ro.product.model"],
        "brand": ["shell", "getprop", "ro.product.brand"],
        "android_version": ["shell", "getprop", "ro.build.version.release"],
        "api_level": ["shell", "getprop", "ro.build.version.sdk"],
        "cpu_abi": ["shell", "getprop", "ro.product.cpu.abi"],
        "cpu_info": ["shell", "cat", "/proc/cpuinfo"],
        "gles": ["shell", "dumpsys", "SurfaceFlinger"],
        "gpu_nodes": ["shell", "ls", "/dev"],
        "neural_service": ["shell", "service", "list"],
    }
    
    for key, cmd in commands.items():
        try:
            # 显式指定 utf-8 并忽略解码错误，防止 Windows 默认 GBK 解码 adb 输出时崩溃
            result = subprocess.run(
                base + cmd, 
                capture_output=True, 
                text=True, 
                encoding="utf-8", 
                errors="replace", 
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            info[key] = result.stdout.strip()
        except Exception as e:
            info[key] = f"(执行失败: {e})"
    return info

def build_scrcpy_args(cfg: dict, mode: str, serial: str = "") -> list[str]:
    """
    构建 scrcpy 参数。
    mode: "usb" 或 "wifi"
    """
    args = [cfg.get("scrcpy_path", "scrcpy")]
    a = cfg.get("args", {})

    # 选择设备
    if mode == "usb":
        args.append("-d")  # 强制选中 USB 设备
    else:
        args.append("-e")  # 强制选中 TCP/IP 设备

    # 编码与分辨率
    if a.get("video_codec"):
        args += ["--video-codec", a["video_codec"]]
    if a.get("max_size"):
        # max_size 为 0 时自动跳过，即使用手机原生分辨率
        args += ["--max-size", str(a["max_size"])]
    if a.get("max_fps"):
        args += ["--max-fps", str(a["max_fps"])]
    
    # 行为控制
    if a.get("turn_screen_off"):
        args.append("-S")
    if a.get("stay_awake"):
        args.append("-w")
    if a.get("keyboard_mode"):
        args += ["--keyboard", a["keyboard_mode"]]
    if a.get("no_audio"):
        args.append("--no-audio")

    # 如果有特定的 serial 且不是 -d / -e 强制，可添加 --serial
    if serial and mode == "usb" and not args.count("-d"):
        args += ["--serial", serial]

    return args

class ScrcpyProcess(QObject):
    """基于 QProcess 的 scrcpy 进程控制，支持实时日志和安全生命周期管理。"""
    log_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self):
        super().__init__()
        self.process = QProcess()
        # 将 stderr 合并到 stdout，方便统一读取（scrcpy 的进度和 adb 连接提示有些在 stderr）
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._on_finished)

    def start(self, args: list[str]):
        if self.running:
            self.stop()
        
        # QProcess 在 Windows 下如果路径带空格，直接传递可以完美处理，无需额外加引号
        self.process.start(args[0], args[1:])

    def _read_output(self):
        data = self.process.readAllStandardOutput().data()
        # 编码尝试：优先 utf-8，失败则用本地 gbk（Windows 下 adb 和 scrcpy 有时会输出 GBK）
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            text = data.decode('gbk', errors='replace')

        for line in text.splitlines():
            if line.strip():
                self.log_signal.emit(line)

    def _on_finished(self, exit_code, exit_status):
        # 通知 UI 进程已结束
        self.finished_signal.emit()

    @property
    def running(self) -> bool:
        return self.process.state() == QProcess.ProcessState.Running

    def stop(self):
        if self.running:
            self.process.terminate()
            if not self.process.waitForFinished(3000):
                self.process.kill()

