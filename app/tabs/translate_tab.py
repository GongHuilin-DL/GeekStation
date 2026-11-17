from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QApplication,
)

from app.services.translation_service import (
    TranslationService,
    RECOMMENDED_ENGINES,
)


class TranslateTab(QWidget):
    """在线翻译选项卡。"""

    # 常用语言代码映射
    LANG_MAP = {
        "自动检测": "auto",
        "中文": "zh",
        "英文": "en",
        "日文": "ja",
        "韩文": "ko",
        "法文": "fr",
        "德文": "de",
        "西班牙文": "es",
        "俄文": "ru",
        "阿拉伯文": "ar",
        "葡萄牙文": "pt",
        "意大利文": "it",
        "泰文": "th",
        "越南文": "vi",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = TranslationService.load_config()
        self._build_ui()
        self._apply_config()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # ================= 1. 配置区 =================
        config_group = QGroupBox("翻译配置")
        config_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        config_layout = QHBoxLayout(config_group)
        config_layout.setSpacing(15)

        # 引擎选择
        config_layout.addWidget(QLabel("翻译引擎:"))
        self.engine_combo = QComboBox()
        self.engine_combo.setMinimumWidth(140)
        self.engine_combo.setStyleSheet("font-size: 11pt; padding: 2px 6px;")
        # 先填充推荐引擎，后面 _apply_config 中再根据情况补充全部
        for eng in RECOMMENDED_ENGINES:
            self.engine_combo.addItem(eng.upper(), eng)
        config_layout.addWidget(self.engine_combo)

        config_layout.addSpacing(10)

        # 源语言
        config_layout.addWidget(QLabel("源语言:"))
        self.from_combo = QComboBox()
        self.from_combo.setMinimumWidth(110)
        self.from_combo.setStyleSheet("font-size: 11pt; padding: 2px 6px;")
        for name, code in self.LANG_MAP.items():
            self.from_combo.addItem(name, code)
        config_layout.addWidget(self.from_combo)

        # 目标语言
        config_layout.addWidget(QLabel("目标语言:"))
        self.to_combo = QComboBox()
        self.to_combo.setMinimumWidth(110)
        self.to_combo.setStyleSheet("font-size: 11pt; padding: 2px 6px;")
        for name, code in self.LANG_MAP.items():
            self.to_combo.addItem(name, code)
        config_layout.addWidget(self.to_combo)

        config_layout.addStretch()

        # 保存配置按钮
        self.btn_save_config = QPushButton("保存配置")
        self.btn_save_config.setStyleSheet(
            "background-color: #546E7A; color: white; font-weight: bold; padding: 5px 15px; border-radius: 4px;"
        )
        self.btn_save_config.clicked.connect(self._save_config)
        config_layout.addWidget(self.btn_save_config)

        root.addWidget(config_group)

        # ================= 2. 翻译核心区 =================
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)

        # 左侧：原文
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("原文："))
        self.text_source = QPlainTextEdit()
        self.text_source.setPlaceholderText("在此输入或粘贴需要翻译的文本...")
        self.text_source.setFont(self._get_code_font())
        left_layout.addWidget(self.text_source)
        content_layout.addLayout(left_layout, stretch=1)

        # 中间：操作按钮
        btn_layout = QVBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        btn_layout.addSpacing(40)

        self.btn_translate = QPushButton("翻译 →")
        self.btn_translate.setStyleSheet(
            "background-color: #1565C0; color: white; font-weight: bold; font-size: 12pt; padding: 10px 20px; border-radius: 4px;"
        )
        self.btn_translate.clicked.connect(self._do_translate)
        btn_layout.addWidget(self.btn_translate)

        self.btn_copy_result = QPushButton("复制译文")
        self.btn_copy_result.setStyleSheet("padding: 8px;")
        self.btn_copy_result.clicked.connect(self._copy_result)
        btn_layout.addWidget(self.btn_copy_result)

        self.btn_clear = QPushButton("清空")
        self.btn_clear.setStyleSheet("padding: 8px;")
        self.btn_clear.clicked.connect(self._clear_all)
        btn_layout.addWidget(self.btn_clear)

        btn_layout.addStretch()
        content_layout.addLayout(btn_layout)

        # 右侧：译文
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("译文："))
        self.text_result = QPlainTextEdit()
        self.text_result.setPlaceholderText("翻译结果将显示在这里...")
        self.text_result.setFont(self._get_code_font())
        self.text_result.setReadOnly(True)
        self.text_result.setStyleSheet("background-color: #F5F7FA;")
        right_layout.addWidget(self.text_result)
        content_layout.addLayout(right_layout, stretch=1)

        root.addLayout(content_layout, stretch=1)

    def _get_code_font(self):
        from PySide6.QtGui import QFont
        font = QFont("Microsoft YaHei UI")
        font.setPointSize(11)
        return font

    # ================= 配置管理 =================

    def _apply_config(self):
        """将加载的配置应用到UI控件上。"""
        engine = self._config.get("default_engine", "bing")
        from_lang = self._config.get("default_from_lang", "auto")
        to_lang = self._config.get("default_to_lang", "zh")

        # 填充引擎下拉框（如果配置的引擎不在推荐列表中，也添加进去）
        current_engines = [self.engine_combo.itemData(i) for i in range(self.engine_combo.count())]
        if engine not in current_engines:
            self.engine_combo.addItem(engine.upper(), engine)
        
        idx = self.engine_combo.findData(engine)
        if idx >= 0:
            self.engine_combo.setCurrentIndex(idx)

        # 设置语言
        idx_from = self.from_combo.findData(from_lang)
        if idx_from >= 0:
            self.from_combo.setCurrentIndex(idx_from)

        idx_to = self.to_combo.findData(to_lang)
        if idx_to >= 0:
            self.to_combo.setCurrentIndex(idx_to)

    def _save_config(self):
        """保存当前选择到JSON文件。"""
        config = {
            "default_engine": self.engine_combo.currentData(),
            "default_from_lang": self.from_combo.currentData(),
            "default_to_lang": self.to_combo.currentData(),
        }
        if TranslationService.save_config(config):
            self._config = config
            QMessageBox.information(self, "成功", "翻译配置已保存！")
        else:
            QMessageBox.warning(self, "失败", "保存配置失败，请检查文件权限。")

    # ================= 翻译逻辑 =================

    def _do_translate(self):
        text = self.text_source.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请先输入需要翻译的文本。")
            return

        engine = self.engine_combo.currentData()
        from_lang = self.from_combo.currentData()
        to_lang = self.to_combo.currentData()

        # 切换按钮状态，防止重复点击
        self.btn_translate.setEnabled(False)
        self.btn_translate.setText("翻译中...")

        # 注意：这里为了界面不卡顿，理论上应该使用后台线程。
        # 但翻译请求通常很快（1-2秒），且本模块是独立功能，为了代码简洁暂不引入线程池。
        # 如果后续发现卡顿，可以参照 WeatherWorker 的方式改造。
        try:
            result, error = TranslationService.translate(
                text, from_lang, to_lang, engine
            )
            if error:
                self.text_result.setPlainText(f"翻译失败：{error}")
            else:
                self.text_result.setPlainText(result)
        finally:
            self.btn_translate.setEnabled(True)
            self.btn_translate.setText("翻译 →")

    def _copy_result(self):
        result = self.text_result.toPlainText()
        if result:
            QApplication.clipboard().setText(result)
            QMessageBox.information(self, "成功", "译文已复制到剪贴板！")

    def _clear_all(self):
        self.text_source.clear()
        self.text_result.clear()