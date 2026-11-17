import os
import json
import ctypes
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.fernet import Fernet, InvalidToken

from app.utils.storage import get_base_dir

# 全局配置
# DATA_DIR = os.path.join(
#     os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
# )
DATA_DIR = get_base_dir()
CONFIG_FILE = os.path.join(DATA_DIR, "data", "security_config.json")
RECORDS_FILE = os.path.join(DATA_DIR, "data", "security_hidden_records.json")

MAGIC = b"MYCRYPT2"   # 8 bytes
VERSION = b"\x02"     # 1 byte

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
DK_LEN = 32

# Windows 属性常量
FILE_ATTRIBUTE_HIDDEN = 0x2
FILE_ATTRIBUTE_SYSTEM = 0x4
FILE_ATTRIBUTE_NORMAL = 0x80
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class SecurityService:
    """文件安全服务：密码管理、加密解密、隐藏恢复。"""

    # ---------- 密码与配置管理 ----------

    @staticmethod
    def is_password_set() -> bool:
        return os.path.exists(CONFIG_FILE)

    @staticmethod
    def save_password(password: str):
        os.makedirs(DATA_DIR, exist_ok=True)
        data = {"password_hash": hashlib.sha256(password.encode()).hexdigest()}
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)

    @staticmethod
    def verify_password(password: str) -> bool:
        if not os.path.exists(CONFIG_FILE):
            return False
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return hashlib.sha256(password.encode()).hexdigest() == data["password_hash"]
        except Exception:
            return False

    # ---------- 隐藏/恢复逻辑 ----------

    @staticmethod
    def _set_attr(path, attrs):
        if not kernel32.SetFileAttributesW(path, attrs):
            raise ctypes.WinError(ctypes.get_last_error())

    @classmethod
    def hide_path(cls, path):
        """递归隐藏文件夹及其内部内容。"""
        try:
            if os.path.isdir(path):
                for root, dirs, files in os.walk(path):
                    for name in files:
                        cls._set_attr(os.path.join(root, name), FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)
                    for name in dirs:
                        cls._set_attr(os.path.join(root, name), FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)
            cls._set_attr(path, FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)
        except Exception as e:
            raise Exception(f"隐藏失败: {e}")

    @classmethod
    def unhide_path(cls, path):
        """递归恢复文件夹及其内部内容。"""
        try:
            if os.path.isdir(path):
                for root, dirs, files in os.walk(path):
                    for name in files:
                        cls._set_attr(os.path.join(root, name), FILE_ATTRIBUTE_NORMAL)
                    for name in dirs:
                        cls._set_attr(os.path.join(root, name), FILE_ATTRIBUTE_NORMAL)
            cls._set_attr(path, FILE_ATTRIBUTE_NORMAL)
        except Exception as e:
            raise Exception(f"恢复失败: {e}")

    # ---------- 记录存取 ----------

    @staticmethod
    def load_records() -> list[str]:
        if not os.path.exists(RECORDS_FILE):
            return []
        try:
            with open(RECORDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    @staticmethod
    def save_records(records: list[str]):
        with open(RECORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    # ---------- 加密/解密逻辑 ----------

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        return hashlib.scrypt(
            password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=DK_LEN
        )

    @staticmethod
    def encrypt_file(password: str, src: str, dst: str):
        salt = os.urandom(16)
        nonce = os.urandom(12)
        key = SecurityService._derive_key(password, salt)
        aes = AESGCM(key)

        with open(src, "rb") as f:
            data = f.read()

        encrypted = aes.encrypt(nonce, data, None)
        blob = MAGIC + VERSION + salt + nonce + encrypted

        tmp_path = dst + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(blob)
        os.replace(tmp_path, dst)

    @staticmethod
    def decrypt_file(password: str, raw_key: str, src: str, dst: str):
        with open(src, "rb") as f:
            data = f.read()

        if data.startswith(MAGIC):
            version = data[8:9]
            if version != VERSION:
                raise Exception("不支持的加密版本")
            salt = data[9:25]
            nonce = data[25:37]
            encrypted = data[37:]
            key = SecurityService._derive_key(password, salt)
            aes = AESGCM(key)
            try:
                plain = aes.decrypt(nonce, encrypted, None)
            except Exception:
                raise Exception("密码错误或文件损坏")
        else:
            # 兼容旧版 Fernet 格式
            if not raw_key:
                raise Exception("旧文件需要提供 Key")
            try:
                fernet = Fernet(raw_key.encode())
                plain = fernet.decrypt(data)
            except InvalidToken:
                raise Exception("Key错误或文件损坏")

        tmp_path = dst + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(plain)
        os.replace(tmp_path, dst)