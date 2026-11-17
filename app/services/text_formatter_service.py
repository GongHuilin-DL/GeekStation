import re


class TextFormatterService:
    """文本格式化与命令转换服务。"""

    @staticmethod
    def strip_whitespace(text: str) -> str:
        """1. 去除文本首尾空格。"""
        return text.strip()

    @staticmethod
    def remove_all_spaces(text: str) -> str:
        """2. 去除文本所有空格（包括全角/半角空格及制表符）。"""
        return re.sub(r"[ \t\u3000]+", "", text)

    @staticmethod
    def remove_substring(text: str, target: str, case_sensitive: bool = True) -> str:
        """3. 去除指定的字符串（支持区分/忽略大小写）。"""
        if not target:
            return text
        if case_sensitive:
            return text.replace(target, "")
        else:
            pattern = re.compile(re.escape(target), re.IGNORECASE)
            return pattern.sub("", text)

    @staticmethod
    def convert_to_single_line(text: str, shell_type: str) -> str:
        """
        4. 多行命令转单行。
        CMD 使用 ^ 续行，PowerShell 使用 ` 续行，Linux 使用 \ 续行。
        """
        if shell_type.lower() == "cmd":
            pattern = r"\s*\^\s*\r?\n"
        elif shell_type.lower() == "powershell":
            pattern = r"\s*`\s*\r?\n"
        else: # linux
            pattern = r"\s*\\\s*\r?\n"

        # 去掉续行符及换行，替换为空格
        single_line = re.sub(pattern, " ", text)
        
        # 处理那些没有写续行符直接换行的普通多行文本，把换行也换成空格
        single_line = single_line.replace('\r\n', ' ').replace('\n', ' ')
        
        # 压缩多余空格
        return re.sub(r"\s+", " ", single_line).strip()

    @staticmethod
    def convert_to_multi_line(text: str, shell_type: str) -> str:
        """
        5. 单行命令转多行（智能断行）。
        根据操作符 (&&, ||, |, ;) 进行断行，并加上对应的续行符。
        """
        if shell_type.lower() == "cmd":
            cont_char = " ^"
        elif shell_type.lower() == "powershell":
            cont_char = " `"
        else: # linux
            cont_char = " \\"

        # 将 " && ", " || ", " | ", " ; " 等替换为 " [续行符]\n操作符 "
        # 注意：这里只是一种启发式转换，不处理引号内的操作符
        formatted_text = re.sub(r"\s*(\&\&|\|\||\||\;)\s*", rf"{cont_char}\n\1 ", text)
        
        # 首行如果有多余的续行符，清理掉（比如字符串刚好以 && 开头）
        formatted_text = formatted_text.strip()
        if formatted_text.startswith(cont_char.strip()):
            formatted_text = formatted_text[len(cont_char.strip()):].strip()

        return formatted_text