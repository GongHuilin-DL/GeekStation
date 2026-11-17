import uuid
import os
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QToolTip,
)

from app.utils.storage import load_json, save_json

DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "snippets.json",
)


class SnippetTab(QWidget):
    """文本片段管理选项卡。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._snippets = []
        self._editing_id = None
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # ================= 1. 添加/编辑区域 =================
        self.add_group = QGroupBox("添加新文本片段")
        self.add_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        add_layout = QVBoxLayout(self.add_group)

        # 描述
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("描述:"))
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("例如: 常用邮箱地址 / 项目地址")
        row1.addWidget(self.desc_input)
        add_layout.addLayout(row1)

        # 文本内容（支持多行）
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("内容:"))
        self.content_input = QPlainTextEdit()
        self.content_input.setPlaceholderText("在此输入需要复制的文本，支持多行...")
        self.content_input.setFixedHeight(80)
        row2.addWidget(self.content_input)
        add_layout.addLayout(row2)

        # 按钮行
        row3 = QHBoxLayout()
        row3.addStretch()
        
        self.btn_cancel_edit = QPushButton("取消编辑")
        self.btn_cancel_edit.setStyleSheet("padding: 6px 15px;")
        self.btn_cancel_edit.clicked.connect(self._cancel_edit)
        self.btn_cancel_edit.hide()
        row3.addWidget(self.btn_cancel_edit)

        self.btn_save = QPushButton("添加保存")
        self.btn_save.setStyleSheet(
            "background-color: #1565C0; color: white; font-weight: bold; padding: 6px 20px;"
        )
        self.btn_save.clicked.connect(self._save_snippet)
        row3.addWidget(self.btn_save)
        
        add_layout.addLayout(row3)
        root.addWidget(self.add_group)

        # ================= 2. 列表与操作区域 =================
        list_group = QGroupBox("已保存的片段（单击选中，双击复制）")
        list_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        list_layout = QVBoxLayout(list_group)

        # 工具栏
        toolbar = QHBoxLayout()
        self.btn_copy_selected = QPushButton("复制选中项")
        self.btn_copy_selected.clicked.connect(self._copy_selected)
        
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.clicked.connect(self._select_all)
        
        self.btn_delete_selected = QPushButton("删除选中")
        self.btn_delete_selected.setStyleSheet("color: #D32F2F;")
        self.btn_delete_selected.clicked.connect(self._delete_selected)
        
        self.btn_clear_all = QPushButton("全部清空")
        self.btn_clear_all.setStyleSheet("color: #D32F2F;")
        self.btn_clear_all.clicked.connect(self._clear_all)

        toolbar.addWidget(self.btn_copy_selected)
        toolbar.addSpacing(20)
        toolbar.addWidget(self.btn_select_all)
        toolbar.addWidget(self.btn_delete_selected)
        toolbar.addWidget(self.btn_clear_all)
        toolbar.addStretch()
        list_layout.addLayout(toolbar)

        # 列表
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.itemDoubleClicked.connect(self._copy_item)
        
        # 右键菜单
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        
        self.list_widget.setStyleSheet("""
            QListWidget {
                font-size: 11pt;
                background-color: #FFFFFF;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #E0E0E0;
            }
            QListWidget::item:selected {
                background-color: #BBDEFB;
                color: #0D47A1;
            }
        """)
        list_layout.addWidget(self.list_widget)
        root.addWidget(list_group, stretch=1)

    # ---------- 数据存取 ----------

    def _load_data(self):
        data = load_json(DATA_FILE, {"snippets": []})
        self._snippets = data.get("snippets", [])
        self._refresh_list()

    def _save_data(self):
        save_json(DATA_FILE, {"snippets": self._snippets})

    def _refresh_list(self):
        self.list_widget.clear()
        for snip in self._snippets:
            desc = snip.get("desc", "无描述")
            content = snip.get("content", "")
            
            # 截取内容的第一行作为预览
            preview = content.replace("\n", " ").strip()
            if len(preview) > 40:
                preview = preview[:40] + "..."
                
            display_text = f"[{desc}]\n  > {preview}"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, snip)
            # 添加提示，鼠标悬停可看完整内容
            item.setToolTip(content)
            self.list_widget.addItem(item)

    # ---------- 增 / 改 逻辑 ----------

    def _save_snippet(self):
        desc = self.desc_input.text().strip()
        content = self.content_input.toPlainText().strip()

        if not content:
            QMessageBox.warning(self, "提示", "文本内容不能为空！")
            return
        if not desc:
            desc = "未命名片段"

        if self._editing_id:
            for snip in self._snippets:
                if snip["id"] == self._editing_id:
                    snip["desc"] = desc
                    snip["content"] = content
                    break
            self._cancel_edit()
        else:
            new_snip = {
                "id": str(uuid.uuid4()),
                "desc": desc,
                "content": content,
            }
            self._snippets.insert(0, new_snip)
            self.desc_input.clear()
            self.content_input.clear()

        self._save_data()
        self._refresh_list()

    def _start_edit(self, item: QListWidgetItem):
        snip = item.data(Qt.ItemDataRole.UserRole)
        self._editing_id = snip["id"]

        self.desc_input.setText(snip.get("desc", ""))
        self.content_input.setPlainText(snip.get("content", ""))

        self.add_group.setTitle(f"正在编辑片段: {snip.get('desc', '')}")
        self.btn_save.setText("保存修改")
        self.btn_save.setStyleSheet(
            "background-color: #F57C00; color: white; font-weight: bold; padding: 6px 20px;"
        )
        self.btn_cancel_edit.show()

    def _cancel_edit(self):
        self._editing_id = None
        self.desc_input.clear()
        self.content_input.clear()
        
        self.add_group.setTitle("添加新文本片段")
        self.btn_save.setText("添加保存")
        self.btn_save.setStyleSheet(
            "background-color: #1565C0; color: white; font-weight: bold; padding: 6px 20px;"
        )
        self.btn_cancel_edit.hide()

    # ---------- 复制逻辑 ----------

    def _copy_item(self, item: QListWidgetItem):
        snip = item.data(Qt.ItemDataRole.UserRole)
        content = snip.get("content", "")
        
        clipboard = QApplication.clipboard()
        clipboard.setText(content)
        
        # 视觉反馈：在鼠标位置显示一个气泡提示
        global_pos = self.list_widget.mapToGlobal(self.list_widget.visualItemRect(item).center())
        QToolTip.showText(global_pos, "✅ 已复制到剪贴板", self.list_widget, self.list_widget.visualItemRect(item), 1500)

    def _copy_selected(self):
        items = self.list_widget.selectedItems()
        if not items:
            QMessageBox.information(self, "提示", "请先选中要复制的项。")
            return
        
        # 如果选中了多项，按行拼接复制
        texts = [item.data(Qt.ItemDataRole.UserRole).get("content", "") for item in items]
        QApplication.clipboard().setText("\n\n".join(texts))
        
        # 提示
        QMessageBox.information(self, "复制成功", f"已复制 {len(items)} 条内容到剪贴板。")

    # ---------- 列表操作 ----------

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        
        menu = QMenu()
        act_copy = menu.addAction("复制内容")
        act_edit = menu.addAction("编辑此条")
        menu.addSeparator()
        act_delete = menu.addAction("删除此条")
        act_delete.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_TrashIcon))

        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == act_copy:
            self._copy_item(item)
        elif action == act_edit:
            self._start_edit(item)
        elif action == act_delete:
            snip_data = item.data(Qt.ItemDataRole.UserRole)
            self._snippets = [s for s in self._snippets if s["id"] != snip_data["id"]]
            self._save_data()
            self._refresh_list()
            if self._editing_id == snip_data["id"]:
                self._cancel_edit()

    def _select_all(self):
        self.list_widget.selectAll()

    def _delete_selected(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return
        
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除选中的 {len(selected_items)} 条片段吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            selected_ids = {item.data(Qt.ItemDataRole.UserRole)["id"] for item in selected_items}
            self._snippets = [s for s in self._snippets if s["id"] not in selected_ids]
            self._save_data()
            self._refresh_list()
            if self._editing_id in selected_ids:
                self._cancel_edit()

    def _clear_all(self):
        if not self._snippets:
            return
        reply = QMessageBox.question(
            self, "确认清空", "确定要删除所有文本片段吗？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._snippets.clear()
            self._save_data()
            self._refresh_list()
            self._cancel_edit()

    # ---------- 快捷键支持 ----------

    def keyPressEvent(self, event):
        # 支持 Ctrl+C 复制选中的单条或多条
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_C:
            self._copy_selected()
            event.accept()
        else:
            super().keyPressEvent(event)