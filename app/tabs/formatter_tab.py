from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QApplication,
    QCheckBox,
)

from app.services.text_formatter_service import TextFormatterService


class FormatterTab(QWidget):
    """文本格式化与命令转换选项卡。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # 顶部标题栏
        header = QHBoxLayout()
        title = QLabel("文本格式化与命令转换")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0D47A1;")
        header.addWidget(title)
        header.addStretch()
        
        # Shell 类型选择
        header.addWidget(QLabel("目标 Shell 类型:"))
        self.shell_combo = QComboBox()
        self.shell_combo.addItem("Windows CMD ( ^ )", "cmd")
        self.shell_combo.addItem("PowerShell ( ` )", "powershell")
        self.shell_combo.addItem("Linux / Bash ( ` )", "linux")
        self.shell_combo.setMinimumWidth(180)
        self.shell_combo.setStyleSheet("font-size: 11pt; padding: 2px 6px;")
        header.addWidget(self.shell_combo)
        
        root.addLayout(header)

        # 核心内容区：左右两个文本框
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)

        # 左侧：输入框
        input_layout = QVBoxLayout()
        input_layout.addWidget(QLabel("原始文本 / 命令："))
        self.text_input = QPlainTextEdit()
        self.text_input.setPlaceholderText("在此粘贴多行命令或文本...")
        self.text_input.setFont(self._get_code_font())
        input_layout.addWidget(self.text_input)
        content_layout.addLayout(input_layout, stretch=1)

        # 中间：操作按钮区
        btn_layout = QVBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # 转换操作分组
        convert_group = QGroupBox("命令格式转换")
        convert_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        convert_v = QVBoxLayout(convert_group)

        self.btn_multi_to_single = QPushButton("多行转单行")
        self.btn_multi_to_single.setToolTip("根据上方选择的 Shell 类型，去除续行符并合并")
        self.btn_multi_to_single.clicked.connect(self._do_multi_to_single)
        convert_v.addWidget(self.btn_multi_to_single)

        self.btn_single_to_multi = QPushButton("单行转多行")
        self.btn_single_to_multi.setToolTip("根据操作符 (&&, ||, |, ;) 智能断行")
        self.btn_single_to_multi.clicked.connect(self._do_single_to_multi)
        convert_v.addWidget(self.btn_single_to_multi)
        
        btn_layout.addWidget(convert_group)

        # 清洗操作分组
        clean_group = QGroupBox("文本清洗")
        clean_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        clean_v = QVBoxLayout(clean_group)

        self.btn_strip = QPushButton("去除首尾空格")
        self.btn_strip.clicked.connect(self._do_strip)
        clean_v.addWidget(self.btn_strip)

        self.btn_remove_spaces = QPushButton("去除所有空格")
        self.btn_remove_spaces.clicked.connect(self._do_remove_spaces)
        clean_v.addWidget(self.btn_remove_spaces)

        # 去除指定字符串
        # target_layout = QHBoxLayout()
        # target_layout = QVBoxLayout()
        # self.target_input = QLineEdit()
        # self.target_input.setPlaceholderText("输入要删除的字符...")
        # self.target_input.setMaximumWidth(120)
        # self.btn_remove_target = QPushButton("删除")
        # self.btn_remove_target.setFixedWidth(50)
        # self.btn_remove_target.clicked.connect(self._do_remove_target)
        # target_layout.addWidget(self.target_input)
        # target_layout.addWidget(self.btn_remove_target)
        # clean_v.addLayout(target_layout)

        # 去除指定字符串
        target_layout = QVBoxLayout()

        target_row = QHBoxLayout()
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("输入要删除的字符...")
        self.target_input.setMaximumWidth(120)
        self.btn_remove_target = QPushButton("删除")
        self.btn_remove_target.setFixedWidth(50)
        self.btn_remove_target.clicked.connect(self._do_remove_target)
        target_row.addWidget(self.target_input)
        target_row.addWidget(self.btn_remove_target)
        
        self.cb_case_sensitive = QCheckBox("区分大小写")
        self.cb_case_sensitive.setChecked(True)  # 默认区分大小写
        self.cb_case_sensitive.setStyleSheet("font-size: 9pt; color: #666;")
        
        target_layout.addLayout(target_row)
        target_layout.addWidget(self.cb_case_sensitive)
        clean_v.addLayout(target_layout)
        
        btn_layout.addWidget(clean_group)

        btn_layout.addSpacing(20)
        
        self.btn_copy = QPushButton("复制输出结果")
        self.btn_copy.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.btn_copy.clicked.connect(self._copy_output)
        btn_layout.addWidget(self.btn_copy)

        btn_layout.addStretch()
        content_layout.addLayout(btn_layout)

        # 右侧：输出框
        output_layout = QVBoxLayout()
        output_layout.addWidget(QLabel("处理结果："))
        self.text_output = QPlainTextEdit()
        self.text_output.setPlaceholderText("处理结果将显示在这里...")
        self.text_output.setFont(self._get_code_font())
        self.text_output.setReadOnly(True)
        self.text_output.setStyleSheet("background-color: #F5F7FA;")
        output_layout.addWidget(self.text_output)
        content_layout.addLayout(output_layout, stretch=1)

        root.addLayout(content_layout, stretch=1)

    def _get_code_font(self):
        from PySide6.QtGui import QFont
        font = QFont("Consolas")
        font.setPointSize(11)
        return font

    # ================= 逻辑调用 =================

    def _get_text(self) -> str:
        return self.text_input.toPlainText()

    def _set_result(self, result: str):
        self.text_output.setPlainText(result)

    def _do_multi_to_single(self):
        shell = self.shell_combo.currentData()
        text = self._get_text()
        if not text:
            return
        res = TextFormatterService.convert_to_single_line(text, shell)
        self._set_result(res)

    def _do_single_to_multi(self):
        shell = self.shell_combo.currentData()
        text = self._get_text()
        if not text:
            return
        res = TextFormatterService.convert_to_multi_line(text, shell)
        self._set_result(res)

    def _do_strip(self):
        text = self._get_text()
        res = TextFormatterService.strip_whitespace(text)
        self._set_result(res)

    def _do_remove_spaces(self):
        text = self._get_text()
        res = TextFormatterService.remove_all_spaces(text)
        self._set_result(res)

    # def _do_remove_target(self):
    #     text = self._get_text()
    #     target = self.target_input.text()
    #     if not target:
    #         QMessageBox.warning(self, "提示", "请先在按钮左侧的输入框内输入要删除的字符串。")
    #         return
    #     res = TextFormatterService.remove_substring(text, target)
    #     self._set_result(res)

    def _do_remove_target(self):
        text = self._get_text()
        target = self.target_input.text()
        if not target:
            QMessageBox.warning(self, "提示", "请先在按钮左侧的输入框内输入要删除的字符串。")
            return
        
        case_sensitive = self.cb_case_sensitive.isChecked()
        res = TextFormatterService.remove_substring(text, target, case_sensitive)
        self._set_result(res)

    def _copy_output(self):
        text = self.text_output.toPlainText()
        if not text:
            return
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "成功", "处理结果已复制到剪贴板！")