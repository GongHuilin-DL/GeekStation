import json
import os
import sys
import tempfile


def get_base_dir():
    # 如果是打包后的 exe
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), "data")
    # 如果是源码运行
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_json(filepath: str, default_data: any = None) -> any:
    """读取 JSON，如果不存在或损坏则返回默认值。"""
    if default_data is None:
        default_data = {}
    if not os.path.exists(filepath):
        return default_data
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_data


def save_json(filepath: str, data: any) -> bool:
    """安全保存 JSON（先写临时文件，再原子替换）。"""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(filepath), suffix=".tmp"
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, filepath)
        return True
    except Exception as e:
        print(f"保存文件失败: {e}")
        return False