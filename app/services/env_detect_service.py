import os
import sys
import json
import shutil
import subprocess
import tempfile
import winreg
from pathlib import Path
from app.utils.storage import get_base_dir

# DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DATA_DIR = get_base_dir()
HISTORY_FILE = os.path.join(DATA_DIR, "data", "env_detect_history.json")

# ================= 探测脚本（在目标环境内运行） =================
PROBE_SCRIPT = """
import sys, json
import importlib.metadata

result = {
    "python": {"version": sys.version.split()[0], "executable": sys.executable},
    "packages": {},
    "pytorch": None, "tensorflow": None, "keras": None, "paddle": None,
    "transformers": None, "onnxruntime": None, "openvino": None,
}

# 采集核心框架信息
try:
    import torch
    cuda_avail = torch.cuda.is_available()
    result["pytorch"] = {
        "version": torch.__version__,
        "backend": "cuda" if cuda_avail else "cpu",
        "cuda_version": torch.version.cuda,
        "cudnn_version": torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else None,
        "gpu_count": torch.cuda.device_count() if cuda_avail else 0,
        "gpu_name": torch.cuda.get_device_name(0) if cuda_avail else None,
        "compute_capability": f"{torch.cuda.get_device_capability(0)[0]}.{torch.cuda.get_device_capability(0)[1]}" if cuda_avail else None
    }
except Exception:
    pass

try:
    import tensorflow as tf
    gpus = tf.config.list_physical_devices('GPU')
    result["tensorflow"] = {
        "version": tf.__version__,
        "backend": "gpu" if gpus else "cpu",
        "gpu_count": len(gpus),
        "gpu_name": [g.name for g in gpus] if gpus else None
    }
except Exception:
    pass

try:
    import keras
    result["keras"] = {"version": keras.__version__}
except Exception:
    pass

try:
    import paddle
    result["paddle"] = {
        "version": paddle.__version__,
        "backend": "gpu" if paddle.device.is_compiled_with_cuda() else "cpu",
        "cuda_version": paddle.version.cuda() if paddle.device.is_compiled_with_cuda() else None
    }
except Exception:
    pass

try:
    import onnxruntime as ort
    result["onnxruntime"] = {
        "version": ort.__version__,
        "providers": ort.get_available_providers()
    }
except Exception:
    pass

# 采集关键依赖包 (安全、极快，不执行实际代码)
PACKAGES_TO_CHECK = [
    "numpy", "scipy", "pandas", "numba", 
    "transformers", "accelerate", "onnx", "tensorrt", "openvino", "triton",
    "gradio", "streamlit", "fastapi", "uvicorn",
    "opencv-python", "pillow", "decord",
    "deepspeed", "torchao", "xformers"
]
for pkg in PACKAGES_TO_CHECK:
    try:
        result["packages"][pkg] = importlib.metadata.version(pkg)
    except importlib.metadata.PackageNotFoundError:
        pass

print("---PROBE_START---")
print(json.dumps(result))
print("---PROBE_END---")
"""

# ================= Demo 测试脚本 =================
DEMO_SCRIPT = """
import sys
print(f"Python {sys.version.split()[0]}")
try:
    import torch
    backend = 'CUDA' if torch.cuda.is_available() else 'CPU'
    print(f"PyTorch {torch.__version__} Backend: {backend}")
    x = torch.randn(1000, 1000)
    if torch.cuda.is_available():
        x = x.cuda()
    y = x @ x
    print(f"[OK] PyTorch Matrix Multiplication Success (Device: {y.device})")
except ImportError:
    print("[WARN] PyTorch not installed")

try:
    import tensorflow as tf
    print(f"TensorFlow {tf.__version__}")
    a = tf.random.normal([100, 100])
    b = tf.matmul(a, a)
    devices = [d.device_type for d in tf.config.list_physical_devices()]
    print(f"[OK] TensorFlow Matrix Multiplication Success (Devices: {devices})")
except ImportError:
    print("[WARN] TensorFlow not installed")

print("=== Demo Test Completed ===")
"""


class EnvDetectService:
    # ================= 核心探察与硬件检测 =================

    @staticmethod
    def detect_hardware() -> dict:
        """硬件检测：优先找 NVIDIA，其次 Win32 接口找所有显卡，无 GPU 则查 CPU。"""
        hw = {"ai_accelerator": [], "cpu": None, "integrated_gpu": []}

        # 1. 查 NVIDIA (拥有完善的算力体系)
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,driver_version,compute_cap", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            if res.returncode == 0:
                for line in res.stdout.strip().splitlines():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 4:
                        hw["ai_accelerator"].append({
                            "vendor": "NVIDIA", "name": parts[0], "vram_mib": parts[1],
                            "driver": parts[2], "compute_capability": parts[3]
                        })
        except Exception:
            pass

        # 2. 查 AMD / Intel (如果没跑 nvidia-smi 或者有其他显卡)
        try:
            ps_cmd = "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion,PNPDeviceID | ConvertTo-Json"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                if isinstance(data, dict): data = [data]
                for gpu in data:
                    pnp = gpu.get("PNPDeviceID", "") or ""
                    name = gpu.get("Name", "")
                    vram = gpu.get("AdapterRAM", 0) or 0
                    entry = {"name": name, "vram_mib": round(vram / 1024 / 1024) if vram > 0 else None, "driver": gpu.get("DriverVersion", "")}
                    
                    if "VEN_1002" in pnp:
                        entry["vendor"] = "AMD"
                        hw["ai_accelerator"].append(entry)
                    elif "VEN_8086" in pnp:
                        entry["vendor"] = "Intel"
                        hw["integrated_gpu"].append(entry)
        except Exception:
            pass

        # 3. 如果没有 AI 加速器，获取 CPU 信息
        if not hw["ai_accelerator"]:
            try:
                res = subprocess.run(["wmic", "cpu", "get", "Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,Manufacturer", "/format:csv"], capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                lines = [l.strip() for l in res.stdout.splitlines() if l.strip() and not l.startswith("Node")]
                if lines:
                    parts = lines[0].split(",")
                    if len(parts) >= 6:
                        hw["cpu"] = {"manufacturer": parts[1], "name": parts[2], "cores": parts[3], "threads": parts[4], "max_clock_mhz": parts[5]}
            except Exception:
                pass

        return hw

    # @staticmethod
    # def scan_environments(search_dirs: list[str] = None) -> list[dict]:
    #     """强力扫描系统中的 Python/Anaconda 环境（支持打包后运行）。"""
    #     envs = []
    #     seen_paths = set()
    #     conda_roots = set()  # 记录找到的所有 conda 根目录

    #     def add_env(name, path, env_type, python_exe, parent=None):
    #         if not python_exe or not os.path.isfile(python_exe):
    #             return
    #         lower_exe = python_exe.lower()
    #         if not lower_exe.endswith(("python.exe", "pythonw.exe", "python", "python3")):
    #             return
    #         real_path = os.path.realpath(path)
    #         if real_path in seen_paths:
    #             return
    #         seen_paths.add(real_path)
    #         envs.append({
    #             "name": name,
    #             "path": real_path,
    #             "type": env_type,
    #             "python_exe": python_exe,
    #             "parent": parent
    #         })

    #     # 1. 获取当前运行环境（仅在源码运行时添加）
    #     if not getattr(sys, 'frozen', False):
    #         add_env("当前运行环境", sys.prefix, "base_python", sys.executable)

    #     # ==================== 强力寻找 Conda 根目录 ====================
    #     # (1) 从环境变量获取
    #     for var in ["CONDA_EXE", "CONDA_PREFIX", "CONDA_ROOT"]:
    #         val = os.environ.get(var)
    #         if val:
    #             if "conda.exe" in val.lower():
    #                 conda_roots.add(os.path.dirname(os.path.dirname(val)))
    #             elif "Scripts" in val:
    #                 conda_roots.add(os.path.dirname(val))
    #             else:
    #                 conda_roots.add(val)

    #     # (2) 从 Windows 注册表卸载列表获取 (应对自定义安装路径如 D:\Anaconda3)
    #     try:
    #         uninstall_keys = [
    #             r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
    #             r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
    #         ]
    #         for un_key in uninstall_keys:
    #             try:
    #                 with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, un_key) as key:
    #                     for i in range(winreg.QueryInfoKey(key)[0]):
    #                         subkey_name = winreg.EnumKey(key, i)
    #                         with winreg.OpenKey(key, subkey_name) as subkey:
    #                             try:
    #                                 name = winreg.QueryValueEx(subkey, "DisplayName")[0]
    #                                 if "Anaconda" in name or "Miniconda" in name:
    #                                     loc = winreg.QueryValueEx(subkey, "InstallLocation")[0]
    #                                     if os.path.isdir(loc): conda_roots.add(loc)
    #                             except OSError:
    #                                 pass
    #             except OSError:
    #                 pass
    #     except ImportError:
    #         pass # 兼容非 Windows 系统

    #     # (3) 智能探测常见盘符
    #     for drive in ["C:", "D:", "E:", "F:", "G:"]:
    #         if os.path.exists(drive + "\\"):
    #             for folder in ["Anaconda3", "Miniconda3", "anaconda3", "miniconda3", "ProgramData\\Anaconda3", "ProgramData\\Miniconda3"]:
    #                 p = os.path.join(drive + "\\", folder)
    #                 if os.path.isdir(p) and os.path.isfile(os.path.join(p, "Scripts", "conda.exe")):
    #                     conda_roots.add(p)

    #     # (4) 执行 conda info 获取 envs_dirs
    #     for root in conda_roots:
    #         conda_exe = os.path.join(root, "Scripts", "conda.exe")
    #         if not os.path.isfile(conda_exe):
    #             conda_exe = shutil.which("conda")
    #         if not conda_exe: continue

    #         try:
    #             # 清理 PyInstaller 注入的环境变量
    #             clean_env = os.environ.copy()
    #             for k in list(clean_env.keys()):
    #                 if k.startswith("_PYI_") or k == "_MEIPASS":
    #                     del clean_env[k]

    #             res = subprocess.run(
    #                 [conda_exe, "info", "--json"], capture_output=True, text=True, 
    #                 timeout=10, env=clean_env,
    #                 creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    #             )
    #             if res.returncode == 0 and res.stdout.strip():
    #                 info = json.loads(res.stdout)
    #                 for d in info.get("envs_dirs", []):
    #                     if os.path.isdir(d):
    #                         for item in os.listdir(d):
    #                             p = os.path.join(d, item)
    #                             if os.path.isdir(p) and os.path.isdir(os.path.join(p, "conda-meta")):
    #                                 py_exe = os.path.join(p, "python.exe") if os.name == "nt" else os.path.join(p, "bin", "python")
    #                                 add_env(item, p, "conda", py_exe)
    #                 # base 环境
    #                 base_p = info.get("root_prefix")
    #                 if base_p:
    #                     py_exe = os.path.join(base_p, "python.exe") if os.name == "nt" else os.path.join(base_p, "bin", "python")
    #                     add_env("base", base_p, "conda", py_exe)
    #         except Exception:
    #             pass

    #     # (5) 直读 ~/.conda/environments.txt 兜底
    #     conda_env_txt = os.path.expanduser("~/.conda/environments.txt")
    #     if os.path.isfile(conda_env_txt):
    #         try:
    #             with open(conda_env_txt, "r", encoding="utf-8") as f:
    #                 for line in f:
    #                     env_path = line.strip()
    #                     if env_path and os.path.isdir(env_path):
    #                         py_exe = os.path.join(env_path, "python.exe") if os.name == "nt" else os.path.join(env_path, "bin", "python")
    #                         name = os.path.basename(env_path) or "base"
    #                         add_env(name, env_path, "conda", py_exe)
    #         except Exception:
    #             pass

    #     # (6) 遍历找到的 conda 根目录下的 envs 文件夹
    #     for root in conda_roots:
    #         envs_dir = os.path.join(root, "envs")
    #         if os.path.isdir(envs_dir):
    #             for item in os.listdir(envs_dir):
    #                 p = os.path.join(envs_dir, item)
    #                 if os.path.isdir(p):
    #                     py_exe = os.path.join(p, "python.exe") if os.name == "nt" else os.path.join(p, "bin", "python")
    #                     add_env(item, p, "conda", py_exe)

    #     # 7. 扫描用户额外指定的目录
    #     if search_dirs:
    #         for base_dir in search_dirs:
    #             if not os.path.isdir(base_dir): continue
    #             for item in os.listdir(base_dir):
    #                 p = os.path.join(base_dir, item)
    #                 if not os.path.isdir(p): continue
    #                 if os.path.isfile(os.path.join(p, "pyvenv.cfg")):
    #                     py_exe = os.path.join(p, "Scripts", "python.exe") if os.name == "nt" else os.path.join(p, "bin", "python")
    #                     add_env(item, p, "venv", py_exe)
    #                 if os.path.isdir(os.path.join(p, "conda-meta")):
    #                     py_exe = os.path.join(p, "python.exe") if os.name == "nt" else os.path.join(p, "bin", "python")
    #                     add_env(item, p, "conda", py_exe)

    #     # 8. 扫描系统 PATH 中的 Python
    #     for path_dir in os.environ.get("PATH", "").split(os.pathsep):
    #         if not path_dir: continue
    #         py_exe = os.path.join(path_dir, "python.exe" if os.name == "nt" else "python")
    #         if os.path.isfile(py_exe):
    #             add_env("系统PATH中的 Python", os.path.dirname(py_exe), "base_python", py_exe)

    #     return envs

    @staticmethod
    def scan_environments(search_dirs: list[str] = None) -> list[dict]:
        """强力扫描系统中的 Python/Anaconda 环境（无死角覆盖）。"""
        envs = []
        seen_paths = set()
        conda_roots = set()
        envs_dirs = set()

        def add_env(name, path, env_type, python_exe, parent=None):
            if not python_exe or not os.path.isfile(python_exe):
                return
            lower_exe = python_exe.lower()
            if not lower_exe.endswith(("python.exe", "pythonw.exe", "python", "python3")):
                return
            real_path = os.path.realpath(path)
            if real_path in seen_paths:
                return
            seen_paths.add(real_path)
            envs.append({
                "name": name,
                "path": real_path,
                "type": env_type,
                "python_exe": python_exe,
                "parent": parent
            })

        # 1. 获取当前运行环境（仅在源码运行时添加）
        if not getattr(sys, 'frozen', False):
            add_env("当前运行环境", sys.prefix, "base_python", sys.executable)

        # ==================== 深度搜集 Conda 的相关目录 ====================
        
        # (1) 从环境变量获取
        for var in ["CONDA_EXE", "CONDA_PREFIX", "CONDA_ROOT"]:
            val = os.environ.get(var)
            if val:
                if "conda.exe" in val.lower() or "conda.bat" in val.lower():
                    conda_roots.add(os.path.dirname(os.path.dirname(val)))
                elif "Scripts" in val:
                    conda_roots.add(os.path.dirname(val))
                else:
                    conda_roots.add(val)

        # (2) 从 Windows 注册表获取
        try:
            uninstall_keys = [
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
            ]
            for un_key in uninstall_keys:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, un_key) as key:
                        for i in range(winreg.QueryInfoKey(key)[0]):
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                try:
                                    name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                    if "Anaconda" in name or "Miniconda" in name:
                                        loc = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                        if os.path.isdir(loc): conda_roots.add(loc)
                                except OSError:
                                    pass
                except OSError:
                    pass
        except ImportError:
            pass

        # (3) 智能探测：覆盖用户目录和常见盘符根目录
        home = os.path.expanduser("~")
        # 补全用户目录下的默认安装
        conda_roots.add(os.path.join(home, "anaconda3"))
        conda_roots.add(os.path.join(home, "miniconda3"))
        
        for drive in ["C:", "D:", "E:", "F:", "G:"]:
            if os.path.exists(drive + "\\"):
                for folder in ["Anaconda3", "Miniconda3", "anaconda3", "miniconda3", "ProgramData\\Anaconda3", "ProgramData\\Miniconda3"]:
                    p = os.path.join(drive + "\\", folder)
                    if os.path.isdir(p): conda_roots.add(p)

        # (4) 核心大招：直接解析 ~/.condarc 文件提取 envs_dirs
        condarc_path = os.path.join(home, ".condarc")
        if os.path.isfile(condarc_path):
            try:
                with open(condarc_path, "r", encoding="utf-8") as f:
                    in_envs_dirs = False
                    for line in f:
                        line = line.strip()
                        if line.startswith("envs_dirs:"):
                            in_envs_dirs = True
                            continue
                        if in_envs_dirs:
                            if line.startswith("- "):
                                p = line[2:].strip().replace('"', '').replace("'", "")
                                if os.path.isdir(p): envs_dirs.add(p)
                            elif not line.startswith("- ") and line:
                                in_envs_dirs = False
            except Exception:
                pass

        # (5) 尝试运行 conda info 补充 envs_dirs
        for root in conda_roots:
            conda_exe = os.path.join(root, "Scripts", "conda.exe")
            if not os.path.isfile(conda_exe):
                conda_exe = shutil.which("conda")
            if not conda_exe: continue

            try:
                clean_env = os.environ.copy()
                for k in list(clean_env.keys()):
                    if k.startswith("_PYI_") or k == "_MEIPASS": del clean_env[k]

                res = subprocess.run(
                    [conda_exe, "info", "--json"], capture_output=True, text=True, 
                    timeout=10, env=clean_env,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                if res.returncode == 0 and res.stdout.strip():
                    info = json.loads(res.stdout)
                    for d in info.get("envs_dirs", []):
                        if os.path.isdir(d): envs_dirs.add(d)
                    base_p = info.get("root_prefix")
                    if base_p and os.path.isdir(base_p):
                        py_exe = os.path.join(base_p, "python.exe")
                        add_env("base", base_p, "conda", py_exe)
            except Exception:
                pass

        # ==================== 执行全面扫描 ====================
        
        # 6. 遍历所有可能的 envs 根目录（包含 .condarc 提取的）
        for d in envs_dirs:
            if not os.path.isdir(d): continue
            for item in os.listdir(d):
                p = os.path.join(d, item)
                if os.path.isdir(p) and os.path.isdir(os.path.join(p, "conda-meta")):
                    py_exe = os.path.join(p, "python.exe") if os.name == "nt" else os.path.join(p, "bin", "python")
                    add_env(item, p, "conda", py_exe)

        # 7. 遍历 conda 根目录下的 envs 和 base 环境
        for root in conda_roots:
            if not os.path.isdir(root): continue
            
            # 添加 base 环境
            py_exe_base = os.path.join(root, "python.exe") if os.name == "nt" else os.path.join(root, "bin", "python")
            if os.path.isfile(py_exe_base):
                add_env(os.path.basename(root) or "base", root, "conda", py_exe_base)

            # 扫描 envs 目录
            envs_dir = os.path.join(root, "envs")
            if os.path.isdir(envs_dir):
                for item in os.listdir(envs_dir):
                    p = os.path.join(envs_dir, item)
                    if os.path.isdir(p) and os.path.isdir(os.path.join(p, "conda-meta")):
                        py_exe = os.path.join(p, "python.exe") if os.name == "nt" else os.path.join(p, "bin", "python")
                        add_env(item, p, "conda", py_exe)

        # 8. 读取 ~/.conda/environments.txt 兜底
        conda_env_txt = os.path.join(home, ".conda", "environments.txt")
        if os.path.isfile(conda_env_txt):
            try:
                with open(conda_env_txt, "r", encoding="utf-8") as f:
                    for line in f:
                        env_path = line.strip()
                        if env_path and os.path.isdir(env_path):
                            py_exe = os.path.join(env_path, "python.exe") if os.name == "nt" else os.path.join(env_path, "bin", "python")
                            name = os.path.basename(env_path) or "base"
                            add_env(name, env_path, "conda", py_exe)
            except Exception:
                pass

        # 9. 扫描用户额外指定的目录
        if search_dirs:
            for base_dir in search_dirs:
                if not os.path.isdir(base_dir): continue
                for item in os.listdir(base_dir):
                    p = os.path.join(base_dir, item)
                    if not os.path.isdir(p): continue
                    if os.path.isfile(os.path.join(p, "pyvenv.cfg")):
                        py_exe = os.path.join(p, "Scripts", "python.exe") if os.name == "nt" else os.path.join(p, "bin", "python")
                        add_env(item, p, "venv", py_exe)
                    if os.path.isdir(os.path.join(p, "conda-meta")):
                        py_exe = os.path.join(p, "python.exe") if os.name == "nt" else os.path.join(p, "bin", "python")
                        add_env(item, p, "conda", py_exe)

        # 10. 扫描系统 PATH 中的 Python
        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            if not path_dir: continue
            py_exe = os.path.join(path_dir, "python.exe" if os.name == "nt" else "python")
            if os.path.isfile(py_exe):
                add_env("系统PATH中的 Python", os.path.dirname(py_exe), "base_python", py_exe)

        return envs

    @staticmethod
    def inspect_env(python_exe: str) -> dict:
        """在目标环境中执行探测脚本，并合并硬件信息。"""
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            res = subprocess.run(
                [python_exe, "-I", "-c", PROBE_SCRIPT],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            out = res.stdout
            if "---PROBE_START---" in out and "---PROBE_END---" in out:
                json_str = out.split("---PROBE_START---")[1].split("---PROBE_END---")[0].strip()
                result = json.loads(json_str)
                # 合并硬件信息
                result["hardware"] = EnvDetectService.detect_hardware()
                return result
        except subprocess.TimeoutExpired:
            return {"error": "探测超时"}
        except Exception as e:
            return {"error": str(e)}
        return {"error": "未能正确解析探测结果"}

    # ================= Demo 运行、导出等 =================

    @staticmethod
    def run_demo(python_exe: str) -> str:
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            res = subprocess.run([python_exe, "-I", "-c", DEMO_SCRIPT], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, env=env, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            return res.stdout + "\n" + res.stderr
        except Exception as e:
            return f"运行失败: {e}"

    @staticmethod
    def export_env(env_info: dict, export_format: str, save_path: str) -> tuple[bool, str]:
        python_exe = env_info["python_exe"]
        env_path = env_info["path"]
        try:
            if export_format == "requirements.txt":
                res = subprocess.run([python_exe, "-m", "pip", "freeze"], capture_output=True, text=True, timeout=60)
                with open(save_path, "w", encoding="utf-8") as f: f.write(res.stdout)
                return True, f"已导出 requirements.txt"
            elif export_format == "environment.yml":
                conda = shutil.which("conda")
                if not conda: return False, "未找到 conda 命令"
                res = subprocess.run([conda, "env", "export", "-p", env_path, "--no-builds"], capture_output=True, text=True, timeout=60)
                with open(save_path, "w", encoding="utf-8") as f: f.write(res.stdout)
                return True, "已导出 environment.yml"
            elif export_format == "json":
                with open(save_path, "w", encoding="utf-8") as f: json.dump(env_info, f, indent=2, ensure_ascii=False)
                return True, "已导出 JSON 完整报告"
        except Exception as e:
            return False, str(e)
        return False, "未知格式"

    @staticmethod
    def recreate_env(file_path: str, env_name: str) -> tuple[bool, str]:
        try:
            if file_path.endswith((".yml", ".yaml")):
                conda = shutil.which("conda")
                if not conda: return False, "未找到 conda 命令"
                res = subprocess.run([conda, "env", "create", "-n", env_name, "-f", file_path], capture_output=True, text=True)
                return (True, f"环境 {env_name} 创建成功") if res.returncode == 0 else (False, res.stderr)
            elif file_path.endswith(".txt"):
                venv_path = os.path.join(os.getcwd(), env_name)
                subprocess.run([sys.executable, "-m", "venv", venv_path], check=True)
                pip_exe = os.path.join(venv_path, "Scripts", "pip.exe") if os.name == "nt" else os.path.join(venv_path, "bin", "pip")
                res = subprocess.run([pip_exe, "install", "-r", file_path], capture_output=True, text=True)
                return (True, f"虚拟环境 {env_name} 创建并安装依赖成功") if res.returncode == 0 else (False, res.stderr)
        except Exception as e:
            return False, str(e)
        return False, "不支持的文件格式"