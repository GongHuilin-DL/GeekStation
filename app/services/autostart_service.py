import os
import sys
import subprocess
from app.utils.storage import load_json, save_json, get_base_dir

# DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DATA_DIR = get_base_dir()
APP_CONFIG = os.path.join(DATA_DIR, "data", "app_config.json")

APP_NAME = "MyWorkbench"


def get_app_config() -> dict:
    default = {"dark_mode": False, "auto_start": False}
    return load_json(APP_CONFIG, default)


def save_app_config(cfg: dict):
    save_json(APP_CONFIG, cfg)


def _get_launch_info() -> tuple[str, str, str]:
    """获取 (目标路径, 参数, 工作目录)"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的 exe
        target = sys.executable
        args = ""
        work_dir = os.path.dirname(target)
    else:
        # 源码运行状态
        python_exe = sys.executable
        pythonw_exe = python_exe.replace("python.exe", "pythonw.exe")
        # 如果环境里没有 pythonw.exe，回退到 python.exe
        if not os.path.exists(pythonw_exe):
            pythonw_exe = python_exe
            
        main_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "main.py"))
        target = pythonw_exe
        args = f'"{main_path}"'
        work_dir = os.path.dirname(main_path)
        
    return target, args, work_dir


def _get_startup_lnk_path() -> str:
    """获取当前用户 Startup 文件夹中的快捷方式路径"""
    startup_dir = os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs\Startup")
    return os.path.join(startup_dir, f"{APP_NAME}.lnk")


def set_auto_start(enable: bool) -> bool:
    """开启或关闭开机自启（通过操作 Startup 文件夹中的快捷方式）"""
    lnk_path = _get_startup_lnk_path()
    
    if not enable:
        # 关闭：删除快捷方式
        if os.path.exists(lnk_path):
            try:
                os.remove(lnk_path)
            except Exception as e:
                print(f"删除快捷方式失败: {e}")
                return False
                
        cfg = get_app_config()
        cfg["auto_start"] = False
        save_app_config(cfg)
        return True

    # 开启：生成快捷方式
    target, args, work_dir = _get_launch_info()
    
    # 使用 PowerShell 生成 .lnk 快捷方式
    ps_script = f"""
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("{lnk_path}")
    $Shortcut.TargetPath = "{target}"
    $Shortcut.Arguments = '{args}'
    $Shortcut.WorkingDirectory = "{work_dir}"
    $Shortcut.Description = "个人日常工具集中台"
    $Shortcut.Save()
    """
    
    try:
        # 防止弹出黑框
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, startupinfo=startupinfo
        )
        
        if result.returncode == 0 and os.path.exists(lnk_path):
            cfg = get_app_config()
            cfg["auto_start"] = True
            save_app_config(cfg)
            return True
        else:
            print(f"生成快捷方式失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"执行 PowerShell 生成快捷方式异常: {e}")
        return False


def is_auto_start_enabled() -> bool:
    """检查快捷方式是否存在"""
    return os.path.exists(_get_startup_lnk_path())