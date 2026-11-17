import os
import uuid
import winreg
import webbrowser
from app.utils.storage import load_json, save_json

DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "navigation.json",
)

# 默认内置导航数据（首次运行时写入）
DEFAULT_DATA = {
    "browser_path": "",
    "categories": {
        "在线AI服务": [
            {"id": str(uuid.uuid4()), "name": "DeepSeek", "url": "https://chat.deepseek.com/", "desc": "深度求索，强推理与代码能力"},
            {"id": str(uuid.uuid4()), "name": "豆包", "url": "https://www.doubao.com/chat/", "desc": "字节跳动，免费对话助手"},
            {"id": str(uuid.uuid4()), "name": "腾讯元宝", "url": "https://yuanbao.tencent.com/", "desc": "腾讯综合型AI"},
            {"id": str(uuid.uuid4()), "name": "Kimi", "url": "https://www.kimi.com/", "desc": "月之暗面，长文本处理"},
            {"id": str(uuid.uuid4()), "name": "通义千问", "url": "https://www.qianwen.com/", "desc": "阿里云，综合对话与多模态"},
            {"id": str(uuid.uuid4()), "name": "文心一言", "url": "https://yiyan.baidu.com/", "desc": "百度，中文对话"},
            {"id": str(uuid.uuid4()), "name": "讯飞星火", "url": "https://xinghuo.xfyun.cn/", "desc": "科大讯飞，语音与对话"},
            {"id": str(uuid.uuid4()), "name": "智谱清言", "url": "https://chatglm.cn/", "desc": "智谱AI，GLM系列"},
            {"id": str(uuid.uuid4()), "name": "秘塔AI搜索", "url": "https://metaso.cn/", "desc": "AI搜索引擎"},
            {"id": str(uuid.uuid4()), "name": "Perplexity", "url": "https://www.perplexity.ai/", "desc": "AI搜索，带引用来源"},
            {"id": str(uuid.uuid4()), "name": "Gemini", "url": "https://gemini.google.com/app", "desc": "Google 多模态AI"},
            {"id": str(uuid.uuid4()), "name": "扣子", "url": "https://www.coze.cn/", "desc": "字节跳动 AI Bot 平台"},
        ],
        "计算机视觉": [
            {"id": str(uuid.uuid4()), "name": "Ultralytics YOLO", "url": "https://github.com/ultralytics/ultralytics", "desc": "YOLOv8/YOLO11 官方实现，检测/分割/分类"},
            {"id": str(uuid.uuid4()), "name": "YOLOv5", "url": "https://github.com/ultralytics/yolov5", "desc": "经典 YOLOv5 PyTorch 实现"},
            {"id": str(uuid.uuid4()), "name": "MMDetection", "url": "https://github.com/open-mmlab/mmdetection", "desc": "OpenMMLab 模块化检测工具箱"},
            {"id": str(uuid.uuid4()), "name": "Segment Anything (SAM)", "url": "https://github.com/facebookresearch/segment-anything", "desc": "Meta 通用分割模型"},
            {"id": str(uuid.uuid4()), "name": "SAM 2", "url": "https://github.com/facebookresearch/sam2", "desc": "支持视频分割的 SAM 升级版"},
            {"id": str(uuid.uuid4()), "name": "SegFormer", "url": "https://github.com/NVlabs/SegFormer", "desc": "轻量 Transformer 语义分割"},
            {"id": str(uuid.uuid4()), "name": "Mask2Former", "url": "https://github.com/facebookresearch/Mask2Former", "desc": "通用分割强 baseline"},
            {"id": str(uuid.uuid4()), "name": "ByteTrack", "url": "https://github.com/ifzhang/ByteTrack", "desc": "多目标跟踪，关联所有检测框"},
            {"id": str(uuid.uuid4()), "name": "OC-SORT", "url": "https://github.com/noahcao/OC_SORT", "desc": "观测中心化 SORT 改进"},
            {"id": str(uuid.uuid4()), "name": "Yolov7-tracker", "url": "https://github.com/JackWoo0831/Yolov7-tracker", "desc": "YOLO + 多种跟踪器统一工具箱"},
            {"id": str(uuid.uuid4()), "name": "PySlowFast", "url": "https://github.com/facebookresearch/SlowFast", "desc": "视频理解，SlowFast/MViT 行为识别"},
        ],
        "本地AI部署框架": [
            {"id": str(uuid.uuid4()), "name": "Ollama", "url": "https://github.com/ollama/ollama", "desc": "本地运行时+模型管理，开箱即用"},
            {"id": str(uuid.uuid4()), "name": "llama.cpp", "url": "https://github.com/ggml-org/llama.cpp", "desc": "跨平台推理引擎，GGUF 格式起源"},
            {"id": str(uuid.uuid4()), "name": "vLLM", "url": "https://github.com/vllm-project/vllm", "desc": "高吞吐生产级推理，PagedAttention"},
            {"id": str(uuid.uuid4()), "name": "SGLang", "url": "https://github.com/sgl-project/sglang", "desc": "高性能推理框架"},
            {"id": str(uuid.uuid4()), "name": "TGI (HuggingFace)", "url": "https://github.com/huggingface/text-generation-inference", "desc": "HuggingFace 官方推理引擎"},
            {"id": str(uuid.uuid4()), "name": "LiteLLM", "url": "https://github.com/BerriAI/litellm", "desc": "多提供商统一 API 层"},
            {"id": str(uuid.uuid4()), "name": "LocalAI", "url": "https://github.com/mudler/LocalAI", "desc": "OpenAI API 本地替代，无需 GPU"},
            {"id": str(uuid.uuid4()), "name": "LMDeploy", "url": "https://github.com/InternLM/lmdeploy", "desc": "上海AI实验室，高效推理与量化"},
        ],
        "AI前端WebUI": [
            {"id": str(uuid.uuid4()), "name": "Open WebUI", "url": "https://github.com/open-webui/open-webui", "desc": "功能最全的前端，支持 Ollama/OpenAI"},
            {"id": str(uuid.uuid4()), "name": "Lobe Chat", "url": "https://github.com/lobehub/lobe-chat", "desc": "现代化设计，多模型/知识库/插件"},
            {"id": str(uuid.uuid4()), "name": "LibreChat", "url": "https://github.com/danny-avila/LibreChat", "desc": "多模型聚合，自托管聊天界面"},
            {"id": str(uuid.uuid4()), "name": "AnythingLLM", "url": "https://github.com/Mintplex-Labs/anything-llm", "desc": "文档 RAG + 统一界面"},
            {"id": str(uuid.uuid4()), "name": "Gradio", "url": "https://github.com/gradio-app/gradio", "desc": "快速构建 ML 演示界面的 Python 库"},
            {"id": str(uuid.uuid4()), "name": "Streamlit", "url": "https://github.com/streamlit/streamlit", "desc": "数据/ML 应用快速原型"},
            {"id": str(uuid.uuid4()), "name": "ChatGPT-Next-Web", "url": "https://github.com/ChatGPTNextWeb/ChatGPT-Next-Web", "desc": "轻量跨平台 ChatGPT 客户端"},
            {"id": str(uuid.uuid4()), "name": "Serge", "url": "https://github.com/serge-chat/serge", "desc": "llama.cpp 的 Web 对话界面"},
        ],
        "多模态与LLM开源": [
            {"id": str(uuid.uuid4()), "name": "Awesome-Chinese-LLM", "url": "https://github.com/Das-rebel/Awesome-Chinese-LLM", "desc": "中文LLM精选列表"},
            {"id": str(uuid.uuid4()), "name": "CogVLM", "url": "https://github.com/THUDM/CogVLM", "desc": "智谱，强视觉语言模型"},
            {"id": str(uuid.uuid4()), "name": "Qwen-VL", "url": "https://github.com/QwenLM/Qwen-VL", "desc": "阿里，视觉语言模型"},
            {"id": str(uuid.uuid4()), "name": "InternVL", "url": "https://github.com/OpenGVLab/InternVL", "desc": "上海AI实验室多模态系列"},
            {"id": str(uuid.uuid4()), "name": "MiniCPM-V", "url": "https://github.com/OpenBMB/MiniCPM-V", "desc": "端侧多模态大模型"},
            {"id": str(uuid.uuid4()), "name": "VisCPM", "url": "https://github.com/OpenBMB/VisCPM", "desc": "中英双语多模态对话与图像生成"},
            {"id": str(uuid.uuid4()), "name": "LLaSM", "url": "https://github.com/LinkSoul-AI/LLaSM", "desc": "中英文语音-文本多模态对话"},
            {"id": str(uuid.uuid4()), "name": "Valen", "url": "https://github.com/Liuziyu77/Valen", "desc": "多模态视觉语言模型"},
        ],
    }
}


def load_navigation() -> dict:
    """加载导航数据；文件不存在或数据为空时，初始化并写入默认数据。"""
    # 1. 如果文件根本不存在，直接写入默认数据
    if not os.path.exists(DATA_FILE):
        save_json(DATA_FILE, DEFAULT_DATA)
        return DEFAULT_DATA
    
    # 2. 如果文件存在，读取内容
    data = load_json(DATA_FILE, {})
    
    # 3. 如果读取到的数据为空（比如文件损坏或之前生成的空字典），也重置为默认数据
    if not data or "categories" not in data:
        save_json(DATA_FILE, DEFAULT_DATA)
        return DEFAULT_DATA
        
    # 兼容性处理
    data.setdefault("browser_path", "")
    return data


def save_navigation(data: dict) -> bool:
    return save_json(DATA_FILE, data)


def detect_browsers() -> list[dict]:
    """
    检测系统中已安装的浏览器。
    采用“注册表全量扫描 + 默认浏览器识别 + 常见路径兜底”的三重策略，并加入黑名单过滤。
    """
    found = []
    seen_paths = set()
    import shlex

    # 黑名单：过滤掉容易注册网页协议的客户端、套壳软件、聊天工具等
    blacklist = [
        "doubao", "豆包", "wechat", "微信", "dingtalk", "钉钉",
        "wemeet", "腾讯会议", "qq.exe", "tim.exe", "feishu", "飞书",
        "thunder", "迅雷", "baidunetdisk", "百度网盘", "aliyundrive", "阿里云盘",
        "wps", "office", "steam", "epicgames"
    ]

    def is_blacklisted(name, path):
        name_lower = name.lower()
        path_lower = path.lower()
        for word in blacklist:
            if word in name_lower or word in path_lower:
                return True
        return False

    def add_browser(name, path):
        if not path or not os.path.isfile(path):
            return
        if is_blacklisted(name, path):
            return
        if path.lower() not in seen_paths:
            found.append({"name": name, "path": path})
            seen_paths.add(path.lower())

    # 1. 扫描注册表 StartMenuInternet (获取所有已注册的浏览器)
    reg_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Clients\StartMenuInternet"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Clients\StartMenuInternet"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Clients\StartMenuInternet"),
    ]
    
    for hkey, reg_path in reg_keys:
        try:
            with winreg.OpenKey(hkey, reg_path) as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        i += 1
                        # 获取显示名称
                        try:
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                display_name, _ = winreg.QueryValueEx(subkey, "")
                        except Exception:
                            display_name = subkey_name
                            
                        # 获取执行路径
                        try:
                            cmd_path = rf"{subkey_name}\shell\open\command"
                            with winreg.OpenKey(key, cmd_path) as cmd_key:
                                cmd, _ = winreg.QueryValueEx(cmd_key, "")
                                parts = shlex.split(cmd)
                                if parts:
                                    add_browser(display_name, parts[0])
                        except Exception:
                            pass
                    except OSError:
                        break
        except OSError:
            pass

    # 2. 获取系统默认浏览器，并插到列表最前面
    default_path = ""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice",
        ) as key:
            prog_id, _ = winreg.QueryValueEx(key, "ProgId")
        with winreg.OpenKey(
            winreg.HKEY_CLASSES_ROOT,
            rf"{prog_id}\shell\open\command",
        ) as key:
            cmd, _ = winreg.QueryValueEx(key, "")
            parts = shlex.split(cmd)
            if parts and os.path.isfile(parts[0]):
                default_path = parts[0]
    except Exception:
        pass

    if default_path and not is_blacklisted("", default_path):
        if default_path.lower() not in seen_paths:
            found.insert(0, {"name": "系统默认浏览器", "path": default_path})
            seen_paths.add(default_path.lower())
        else:
            for i, b in enumerate(found):
                if b["path"].lower() == default_path.lower():
                    found.insert(0, found.pop(i))
                    found[0]["name"] = f"默认 - {found[0]['name']}"
                    break

    # 3. 常见路径兜底
    candidates = [
        ("Google Chrome", [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]),
        ("Microsoft Edge", [
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        ]),
        ("Mozilla Firefox", [
            os.path.expandvars(r"%ProgramFiles%\Mozilla Firefox\firefox.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe"),
        ]),
        ("Brave", [
            os.path.expandvars(r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ]),
        ("QQ 浏览器", [
            os.path.expandvars(r"%ProgramFiles(x86)%\Tencent\QQBrowser\QQBrowser.exe"),
            os.path.expandvars(r"%ProgramFiles%\Tencent\QQBrowser\QQBrowser.exe"),
        ]),
        ("搜狗浏览器", [
            os.path.expandvars(r"%ProgramFiles(x86)%\SogouExplorer\SogouExplorer.exe"),
            os.path.expandvars(r"%ProgramFiles%\SogouExplorer\SogouExplorer.exe"),
        ])
    ]
    
    for name, paths in candidates:
        for p in paths:
            add_browser(name, p)

    return found


def open_url(url: str, browser_path: str = ""):
    """
    在指定浏览器中打开 URL。
    browser_path 为空时回退到系统默认行为。
    """
    if browser_path and os.path.isfile(browser_path):
        try:
            import subprocess
            # 使用双引号包裹路径，防止路径中有空格或特殊字符导致失败
            subprocess.Popen(f'"{browser_path}" "{url}"', shell=True)
            return
        except Exception as e:
            print(f"指定浏览器打开失败: {e}，回退到系统默认。")
    
    # 回退到系统默认方式
    os.startfile(url)