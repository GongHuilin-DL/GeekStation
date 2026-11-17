import uuid
import os
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.utils.storage import load_json, save_json

DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "notes.json",
)


class NoteTab(QWidget):
    """便签选项卡：三列看板，按日期存盘。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_notes = {}  
        self._current_date_str = ""
        
        self._build_ui()
        self._load_data()
        
        self.date_edit.setDate(QDate.currentDate())
        self._load_notes_for_date()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # ================= 1. 顶部日期控制栏 =================
        top_bar = QHBoxLayout()
        
        top_bar.addWidget(QLabel("当前日期:"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setStyleSheet("font-size: 12pt; padding: 4px;")
        self.date_edit.dateChanged.connect(self._load_notes_for_date)
        top_bar.addWidget(self.date_edit)

        self.btn_today = QPushButton("回到今天")
        self.btn_today.clicked.connect(lambda: self.date_edit.setDate(QDate.currentDate()))
        top_bar.addWidget(self.btn_today)

        top_bar.addStretch()
        
        self.btn_clear_day = QPushButton("清空当日事项")
        self.btn_clear_day.setStyleSheet("color: #D32F2F;")
        self.btn_clear_day.clicked.connect(self._clear_current_day)
        top_bar.addWidget(self.btn_clear_day)
        
        root.addLayout(top_bar)

        # ================= 2. 三列看板 =================
        board_layout = QHBoxLayout()
        board_layout.setSpacing(10)

        self.col_todo_group, self.list_todo, self.lbl_todo_count = self._create_column("待办")
        
        self.input_new = QLineEdit()
        self.input_new.setPlaceholderText("输入新事项，按回车添加...")
        self.input_new.setStyleSheet("padding: 6px; font-size: 11pt;")
        self.input_new.returnPressed.connect(self._add_new_item)
        self.col_todo_group.layout().insertWidget(1, self.input_new)
        
        board_layout.addWidget(self.col_todo_group)

        self.col_doing_group, self.list_doing, self.lbl_doing_count = self._create_column("进行中")
        board_layout.addWidget(self.col_doing_group)

        self.col_done_group, self.list_done, self.lbl_done_count = self._create_column("已完成")
        board_layout.addWidget(self.col_done_group)

        root.addLayout(board_layout, stretch=1)

        for lst in (self.list_todo, self.list_doing, self.list_done):
            lst.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
            lst.itemDoubleClicked.connect(self._toggle_status)  
            lst.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            lst.customContextMenuRequested.connect(lambda pos, l=lst: self._show_context_menu(pos, l))

    def _create_column(self, title: str) -> tuple[QGroupBox, QListWidget, QLabel]:
        """创建一个看板列（去除写死背景，由全局主题接管）。"""
        group = QGroupBox()
        group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #CFD8DC;
                border-radius: 6px;
                margin-top: 10px;
            }
        """)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        header = QHBoxLayout()
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 13pt; font-weight: bold;")
        
        lbl_count = QLabel("0")
        lbl_count.setStyleSheet("""
            border-radius: 10px; 
            padding: 1px 8px; 
            font-weight: bold;
            border: 1px solid #B0BEC5;
        """)
        
        header.addWidget(lbl_title)
        header.addStretch()
        header.addWidget(lbl_count)
        layout.addLayout(header)

        lst = QListWidget()
        lst.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                font-size: 11pt;
            }
            QListWidget::item {
                border-radius: 4px;
                padding: 8px;
                margin-bottom: 4px;
                border: 1px solid #E0E0E0;
            }
        """)
        layout.addWidget(lst)

        return group, lst, lbl_count

    # ---------- 数据存取 ----------

    def _load_data(self):
        self._all_notes = load_json(DATA_FILE, {})

    def _save_data(self):
        save_json(DATA_FILE, self._all_notes)

    def _load_notes_for_date(self):
        self._current_date_str = self.date_edit.date().toString("yyyy-MM-dd")
        day_notes = self._all_notes.get(self._current_date_str, [])

        for lst in (self.list_todo, self.list_doing, self.list_done):
            lst.clear()

        for note in day_notes:
            status = note.get("status", "todo")
            lst = self._get_list_by_status(status)
            self._add_item_to_list(lst, note)

        self._update_counts()

    def _update_counts(self):
        self.lbl_todo_count.setText(str(self.list_todo.count()))
        self.lbl_doing_count.setText(str(self.list_doing.count()))
        self.lbl_done_count.setText(str(self.list_done.count()))

    def _get_list_by_status(self, status: str) -> QListWidget:
        if status == "doing":
            return self.list_doing
        elif status == "done":
            return self.list_done
        return self.list_todo

    def _get_status_by_list(self, lst: QListWidget) -> str:
        if lst == self.list_doing:
            return "doing"
        elif lst == self.list_done:
            return "done"
        return "todo"

    def _add_item_to_list(self, lst: QListWidget, note: dict):
        item = QListWidgetItem(note["text"])
        item.setData(Qt.ItemDataRole.UserRole, note["id"])
        if note.get("status") == "done":
            font = item.font()
            font.setStrikeOut(True)
            item.setFont(font)
            item.setForeground(Qt.GlobalColor.gray)
        lst.addItem(item)

    def _sync_ui_to_data(self):
        day_notes = []
        for lst in (self.list_todo, self.list_doing, self.list_done):
            status = self._get_status_by_list(lst)
            for i in range(lst.count()):
                item = lst.item(i)
                day_notes.append({
                    "id": item.data(Qt.ItemDataRole.UserRole),
                    "text": item.text(),
                    "status": status
                })
        
        if day_notes:
            self._all_notes[self._current_date_str] = day_notes
        elif self._current_date_str in self._all_notes:
            del self._all_notes[self._current_date_str]
            
        self._save_data()
        self._update_counts()

    # ---------- 增 / 删 / 改 / 切状态 ----------

    def _add_new_item(self):
        text = self.input_new.text().strip()
        if not text:
            return

        new_note = {
            "id": str(uuid.uuid4()),
            "text": text,
            "status": "todo"
        }
        
        self._add_item_to_list(self.list_todo, new_note)
        self.input_new.clear()
        self._sync_ui_to_data()

    def _toggle_status(self, item: QListWidgetItem):
        current_list = item.listWidget()
        note_id = item.data(Qt.ItemDataRole.UserRole)
        text = item.text()

        if current_list == self.list_todo:
            new_status, target_list = "doing", self.list_doing
        elif current_list == self.list_doing:
            new_status, target_list = "done", self.list_done
        else:
            new_status, target_list = "todo", self.list_todo

        row = current_list.row(item)
        current_list.takeItem(row)

        new_note = {"id": note_id, "text": text, "status": new_status}
        self._add_item_to_list(target_list, new_note)
        
        self._sync_ui_to_data()

    def _move_item_to(self, item: QListWidgetItem, target_list: QListWidget):
        if item.listWidget() == target_list:
            return
            
        current_list = item.listWidget()
        note_id = item.data(Qt.ItemDataRole.UserRole)
        text = item.text()

        row = current_list.row(item)
        current_list.takeItem(row)

        new_note = {"id": note_id, "text": text, "status": self._get_status_by_list(target_list)}
        self._add_item_to_list(target_list, new_note)
        self._sync_ui_to_data()

    def _edit_item(self, item: QListWidgetItem):
        from PySide6.QtWidgets import QInputDialog
        new_text, ok = QInputDialog.getText(
            self, "编辑事项", "修改内容:", QLineEdit.EchoMode.Normal, item.text()
        )
        if ok and new_text.strip():
            item.setText(new_text.strip())
            self._sync_ui_to_data()

    def _show_context_menu(self, pos, lst: QListWidget):
        item = lst.itemAt(pos)
        if not item:
            return

        menu = QMenu()
        if lst != self.list_todo:
            menu.addAction("移至 [待办]").triggered.connect(lambda: self._move_item_to(item, self.list_todo))
        if lst != self.list_doing:
            menu.addAction("移至 [进行中]").triggered.connect(lambda: self._move_item_to(item, self.list_doing))
        if lst != self.list_done:
            menu.addAction("移至 [已完成]").triggered.connect(lambda: self._move_item_to(item, self.list_done))

        menu.addSeparator()
        act_edit = menu.addAction("编辑内容")
        act_edit.triggered.connect(lambda: self._edit_item(item))
        
        act_delete = menu.addAction("删除事项")
        act_delete.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_TrashIcon))
        act_delete.triggered.connect(self._delete_selected_items)

        menu.exec(lst.mapToGlobal(pos))

    def _delete_selected_items(self):
        deleted_any = False
        for lst in (self.list_todo, self.list_doing, self.list_done):
            selected_items = lst.selectedItems()
            for item in selected_items:
                row = lst.row(item)
                lst.takeItem(row)
                deleted_any = True
        
        if deleted_any:
            self._sync_ui_to_data()

    def _clear_current_day(self):
        reply = QMessageBox.question(
            self, "确认清空", f"确定要清空 {self._current_date_str} 的所有事项吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.list_todo.clear()
            self.list_doing.clear()
            self.list_done.clear()
            self._sync_ui_to_data()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self._delete_selected_items()
            event.accept()
        else:
            super().keyPressEvent(event)