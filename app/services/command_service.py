import json
import subprocess
import os
import sys 
import shutil


def get_conda_envs() -> list[str]:
    """获取所有的 conda 虚拟环境名称，多重兜底策略保证抓全。"""
    envs = set()

    # 1. 尝试执行 conda env list --json
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        result = subprocess.run(
            ["conda", "env", "list", "--json"],
            capture_output=True, text=True, timeout=5,
            startupinfo=startupinfo, check=True,
            shell=(os.name == 'nt')  # Windows 下开启 shell 才能正确找到 .bat 脚本
        )
        # 有时候输出里带有警告信息，提取 JSON 部分
        output = result.stdout.strip()
        start_idx = output.find('{')
        end_idx = output.rfind('}')
        if start_idx != -1 and end_idx != -1:
            data = json.loads(output[start_idx:end_idx+1])
            for env_path in data.get("envs", []):
                env_path = env_path.rstrip("/\\")
                name = os.path.basename(env_path)
                if not name:
                    name = "base"
                envs.add(name)
    except Exception:
        pass

    # 2. 通过当前 Python 解释器路径反推 Conda 根目录，扫描 envs
    try:
        # sys.base_prefix 指向 base 环境，例如 C:\Users\xxx\anaconda3
        conda_root = sys.base_prefix
        conda_envs_dir = os.path.join(conda_root, "envs")
        if os.path.isdir(conda_envs_dir):
            for d in os.listdir(conda_envs_dir):
                if os.path.isdir(os.path.join(conda_envs_dir, d)):
                    envs.add(d)
    except Exception:
        pass

    # 3. 扫描用户目录下的 .conda/envs
    try:
        user_envs_dir = os.path.expanduser("~/.conda/envs")
        if os.path.isdir(user_envs_dir):
            for d in os.listdir(user_envs_dir):
                if os.path.isdir(os.path.join(user_envs_dir, d)):
                    envs.add(d)
    except Exception:
        pass

    # 4. 把当前运行环境也加进去
    current_env = os.environ.get("CONDA_DEFAULT_ENV")
    if current_env:
        envs.add(current_env)

    # 确保 base 在最前面
    envs_list = list(envs)
    if "base" in envs_list:
        envs_list.remove("base")
    envs_list.insert(0, "base")

    return envs_list
    

def execute_command(cmd_type: str, content: str, conda_env: str = "", desc: str = "") -> tuple[bool, str]:
    """
    在外部终端执行命令。
    优先使用 Windows Terminal (wt.exe) 以选项卡方式打开，无则回退到普通窗口。
    """
    try:
        # 检查是否安装了 Windows Terminal（Win11 默认自带）
        has_wt = shutil.which("wt") is not None
        title = desc if desc else "Command"
        
        # 1. 针对 Windows Terminal 的指令拼接
        if has_wt:
            # -w 0 表示强制在现有的窗口（ID 0）新建选项卡；如果没有窗口则新建
            base_wt = f'wt.exe -w 0 new-tab --title "{title}" '
            
            if cmd_type == "cmd":
                subprocess.Popen(f'{base_wt} cmd /K "{content}"', shell=True)
                
            elif cmd_type == "powershell":
                subprocess.Popen(f'{base_wt} powershell -NoExit -Command "{content}"', shell=True)
                
            elif cmd_type == "conda":
                full_cmd = f'call conda activate {conda_env} && {content}' if conda_env else content
                subprocess.Popen(f'{base_wt} cmd /K "{full_cmd}"', shell=True)
            else:
                return False, "未知的命令类型"
                
        # 2. 回退到传统的 start 命令（没有安装 WT 的系统，如 Win10）
        else:
            if cmd_type == "cmd":
                subprocess.Popen(f'start "{title}" cmd /K "{content}"', shell=True)
            elif cmd_type == "powershell":
                subprocess.Popen(f'start "{title}" powershell -NoExit -Command "{content}"', shell=True)
            elif cmd_type == "conda":
                full_cmd = f'call conda activate {conda_env} && {content}' if conda_env else content
                subprocess.Popen(f'start "{title}" cmd /K "{full_cmd}"', shell=True)
            else:
                return False, "未知的命令类型"

        return True, ""
    except Exception as e:
        return False, str(e)