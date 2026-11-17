import re
import difflib

# 语言规则配置：方便后续扩展新语言
# 格式： "语言键": (单行注释正则, 多行注释正则, 字符串匹配正则列表)
LANGUAGE_RULES = {
    "text": (None, None, None),  # 纯文本不处理
    "c_cpp": (r"//.*", r"/\*[\s\S]*?\*/", [r'"(?:\\.|[^"\\])*"', r"'(?:\\.|[^'\\])*'"]),
    "csharp": (r"//.*", r"/\*[\s\S]*?\*/", [r'"(?:\\.|[^"\\])*"', r"'(?:\\.|[^'\\])*'", r'@"[^"]*"']),
    "java": (r"//.*", r"/\*[\s\S]*?\*/", [r'"(?:\\.|[^"\\])*"', r"'(?:\\.|[^'\\])*'"]),
    "python": (r"#.*", r'(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')', [r'"(?:\\.|[^"\\])*"', r"'(?:\\.|[^'\\])*'"]),
    "javascript": (r"//.*", r"/\*[\s\S]*?\*/", [r'"(?:\\.|[^"\\])*"', r"'(?:\\.|[^'\\])*'", r"`(?:\\.|[^`\\])*`"]),
}


def strip_comments(code: str, language: str) -> str:
    """
    剥离代码注释。
    采用“提取字符串占位 -> 剥离注释 -> 还原字符串”的策略，防止误删字符串内的 // 或 #。
    """
    if language not in LANGUAGE_RULES or language == "text":
        return code

    single_line, multi_line, string_patterns = LANGUAGE_RULES[language]
    if not single_line and not multi_line:
        return code

    # 1. 保护字符串
    strings = []
    def save_string(match):
        strings.append(match.group(0))
        return f"__STR_PLACEHOLDER_{len(strings)-1}__"

    temp_code = code
    if string_patterns:
        for pattern in string_patterns:
            temp_code = re.sub(pattern, save_string, temp_code)

    # 2. 剥离注释
    if multi_line:
        temp_code = re.sub(multi_line, "", temp_code)
    if single_line:
        temp_code = re.sub(single_line, "", temp_code)

    # 3. 还原字符串
    for i, s in enumerate(strings):
        temp_code = temp_code.replace(f"__STR_PLACEHOLDER_{i}__", s)

    # 清理因为删除注释产生的空行
    temp_code = re.sub(r'\n\s*\n', '\n\n', temp_code)
    return temp_code.strip()


def generate_diff_html(text1: str, text2: str, ignore_comments: bool = False, language: str = "text") -> str:
    """
    生成差异对比的 HTML。
    """
    if ignore_comments:
        text1 = strip_comments(text1, language)
        text2 = strip_comments(text2, language)

    lines1 = text1.splitlines()
    lines2 = text2.splitlines()

    # 使用 HtmlDiff 生成对比表格
    # context=True 表示只显示有差异的上下文，numlines 是上下文的行数
    html_diff = difflib.HtmlDiff(wrapcolumn=80).make_file(
        lines1, lines2, 
        fromdesc="版本 A (左侧)", 
        todesc="版本 B (右侧)", 
        context=True, 
        numlines=3
    )
    
    # 注入自定义 CSS，让表格更符合现代审美
    custom_css = """
    <style>
        table.diff { font-family: 'Consolas', 'Courier New', monospace; border: 1px solid #ccc; width: 100%; border-collapse: collapse; font-size: 13px; }
        .diff_header { background-color: #f0f0f0; text-align: right; padding-right: 5px; color: #888; }
        td.diff_header { width: 30px; }
        .diff_next { background-color: #f0f0f0; }
        .diff_add { background-color: #d4edda; color: #155724; }
        .diff_chg { background-color: #fff3cd; color: #856404; }
        .diff_sub { background-color: #f8d7da; color: #721c24; }
        .diff { background-color: #fff; }
        th { background-color: #e2e8f0; padding: 8px; text-align: center; font-family: sans-serif; font-size: 14px; }
    </style>
    """
    # 替换 HtmlDiff 默认的 CSS
    html_diff = html_diff.replace("<style type=\"text/css\">", custom_css + "<style type=\"text/css\">")
    return html_diff