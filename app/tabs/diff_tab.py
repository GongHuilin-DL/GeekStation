from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.services.diff_service import generate_diff_html


class DiffTab(QWidget):
    """文本内容比较工具。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # ================= 1. 顶部控制栏 =================
        header_layout = QHBoxLayout()
        
        title = QLabel("代码与文本对比工具")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0D47A1;")
        header_layout.addWidget(title)
        header_layout.addSpacing(20)

        header_layout.addWidget(QLabel("语言类型:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("纯文本 (不解析)", "text")
        self.lang_combo.addItem("C / C++", "c_cpp")
        self.lang_combo.addItem("C#", "csharp")
        self.lang_combo.addItem("Java", "java")
        self.lang_combo.addItem("Python", "python")
        self.lang_combo.addItem("JavaScript / TypeScript", "javascript")
        self.lang_combo.setMinimumWidth(160)
        self.lang_combo.setStyleSheet("font-size: 11pt; padding: 2px;")
        header_layout.addWidget(self.lang_combo)

        self.cb_ignore_comments = QCheckBox("忽略代码注释")
        self.cb_ignore_comments.setStyleSheet("font-size: 11pt;")
        self.cb_ignore_comments.setChecked(True) # 默认开启
        header_layout.addWidget(self.cb_ignore_comments)

        header_layout.addStretch()

        self.btn_compare = QPushButton("开始对比")
        self.btn_compare.setStyleSheet(
            "background-color: #1565C0; color: white; font-weight: bold; font-size: 12pt; padding: 6px 20px; border-radius: 4px;"
        )
        self.btn_compare.clicked.connect(self._do_compare)
        header_layout.addWidget(self.btn_compare)

        root.addLayout(header_layout)

        # ================= 2. 核心对比区 (上下分割) =================
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 上半部分：左右输入区
        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        
        # 代码字体
        code_font = QFont("Consolas")
        code_font.setPointSize(11)

        # 左侧输入
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("文本 A (原版本):"))
        self.text_a = QPlainTextEdit()
        self.text_a.setPlaceholderText("在此粘贴原版本代码或文本...")
        self.text_a.setFont(code_font)
        left_layout.addWidget(self.text_a)
        input_layout.addLayout(left_layout)

        # 右侧输入
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("文本 B (新版本):"))
        self.text_b = QPlainTextEdit()
        self.text_b.setPlaceholderText("在此粘贴新版本代码或文本...")
        self.text_b.setFont(code_font)
        right_layout.addWidget(self.text_b)
        input_layout.addLayout(right_layout)

        splitter.addWidget(input_widget)

        # 下半部分：差异结果显示区
        result_widget = QWidget()
        result_layout = QVBoxLayout(result_widget)
        result_layout.setContentsMargins(0, 5, 0, 0)
        
        result_layout.addWidget(QLabel("差异高亮结果 (仅显示有差异的部分及上下文):"))
        self.result_browser = QTextBrowser()
        self.result_browser.setOpenExternalLinks(False)
        self.result_browser.setStyleSheet("background-color: #FFFFFF; border: 1px solid #CFD8DC; border-radius: 4px;")
        result_layout.addWidget(self.result_browser)

        splitter.addWidget(result_widget)

        # 设置上下比例 1:1
        splitter.setSizes([300, 300])
        root.addWidget(splitter, stretch=1)

    # ================= 逻辑处理 =================

    def _do_compare(self):
        text_a = self.text_a.toPlainText()
        text_b = self.text_b.toPlainText()

        if not text_a and not text_b:
            QMessageBox.information(self, "提示", "请输入需要对比的文本内容。")
            return

        language = self.lang_combo.currentData()
        ignore_comments = self.cb_ignore_comments.isChecked()

        try:
            html = generate_diff_html(
                text_a, text_b, 
                ignore_comments=ignore_comments, 
                language=language
            )
            self.result_browser.setHtml(html)
        except Exception as e:
            QMessageBox.critical(self, "对比失败", f"生成差异时出错: {e}")