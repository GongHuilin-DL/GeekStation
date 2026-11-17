import os
os.environ["translators_default_region"] = "CN"

import translators as ts
from app.utils.storage import load_json, save_json

CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "translation_config.json",
)

# 推荐的主流引擎列表（从 translators_pool 中筛选常用项）
RECOMMENDED_ENGINES = [
    "bing",      # 微软必应，稳定，支持语言多
    "google",    # 谷歌，质量高
    "baidu",     # 百度，中文优化好
    "alibaba",   # 阿里，电商/专业领域
    "youdao",    # 有道，中文友好
    "tencent",   # 腾讯
    "sogou",     # 搜狗
    "deepl",     # DeepL，质量极高但可能较慢
]


class TranslationService:
    """在线翻译服务封装。"""

    @staticmethod
    def get_available_engines() -> list[str]:
        """获取所有可用的引擎列表。"""
        try:
            return list(ts.translators_pool)
        except Exception:
            return RECOMMENDED_ENGINES

    @staticmethod
    def load_config() -> dict:
        """加载用户配置（默认使用 bing 引擎，中文→英文）。"""
        default = {
            "default_engine": "bing",
            "default_from_lang": "auto",
            "default_to_lang": "zh",
        }
        return load_json(CONFIG_FILE, default)

    @staticmethod
    def save_config(config: dict) -> bool:
        """保存用户配置。"""
        return save_json(CONFIG_FILE, config)

    @staticmethod
    def translate(text: str, from_lang: str = "auto", to_lang: str = "zh", 
                  engine: str = "bing") -> tuple[str, str]:
        """
        执行翻译。
        返回 (翻译结果, 错误信息)。如果成功，错误信息为空字符串。
        如果指定引擎失败，自动尝试降级到其他引擎。
        """
        if not text.strip():
            return "", "翻译内容不能为空"

        engines_to_try = [engine] + [
            e for e in ["bing", "google", "baidu", "alibaba", "youdao"] 
            if e != engine
        ]

        last_error = ""
        for eng in engines_to_try:
            try:
                result = ts.translate_text(
                    text,
                    translator=eng,
                    from_language=from_lang,
                    to_language=to_lang,
                )
                if result:
                    return result, ""
            except Exception as e:
                last_error = str(e)
                continue

        return "", f"所有翻译引擎均失败，最后一次错误: {last_error}"