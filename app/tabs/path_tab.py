import uuid
import os
import time
import subprocess
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
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
    "paths.json",
)


class PathTab(QWidget):
    """路径快捷管理选项卡。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths = []
        self._editing_id = None
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # ================= 1. 添加/编辑区域 =================
        self.add_group = QGroupBox("添加新快捷路径")
        self.add_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        add_layout = QVBoxLayout(self.add_group)

        # 描述与选择按钮
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("描述:"))
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("例如: 工作项目目录 / 常用配置文件")
        row1.addWidget(self.desc_input)
        add_layout.addLayout(row1)

        # 路径输入与浏览
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("路径:"))
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("请输入或选择文件 / 文件夹路径")
        row2.addWidget(self.path_input)

        self.btn_browse_dir = QPushButton("选文件夹")
        self.btn_browse_dir.clicked.connect(self._browse_dir)
        row2.addWidget(self.btn_browse_dir)

        self.btn_browse_file = QPushButton("选文件")
        self.btn_browse_file.clicked.connect(self._browse_file)
        row2.addWidget(self.btn_browse_file)
        add_layout.addLayout(row2)

        # 操作按钮
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
        self.btn_save.clicked.connect(self._save_path)
        row3.addWidget(self.btn_save)
        
        add_layout.addLayout(row3)
        root.addWidget(self.add_group)

        # ================= 2. 列表与操作区域 =================
        list_group = QGroupBox("已保存的快捷路径（双击直接打开）")
        list_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        list_layout = QVBoxLayout(list_group)

        # 工具栏
        toolbar = QHBoxLayout()
        self.btn_open_selected = QPushButton("打开选中项")
        self.btn_open_selected.clicked.connect(self._open_selected)
        
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.clicked.connect(self._select_all)
        
        self.btn_delete_selected = QPushButton("删除选中")
        self.btn_delete_selected.setStyleSheet("color: #D32F2F;")
        self.btn_delete_selected.clicked.connect(self._delete_selected)
        
        self.btn_clear_all = QPushButton("全部清空")
        self.btn_clear_all.setStyleSheet("color: #D32F2F;")
        self.btn_clear_all.clicked.connect(self._clear_all)

        toolbar.addWidget(self.btn_open_selected)
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
        self.list_widget.itemDoubleClicked.connect(self._open_item)
        
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

    # ---------- 路径选择与打开 ----------

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if path:
            self.path_input.setText(os.path.normpath(path))

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if path:
            self.path_input.setText(os.path.normpath(path))

    def _open_item(self, item: QListWidgetItem):
        path_data = item.data(Qt.ItemDataRole.UserRole)
        target = path_data.get("path", "")
        
        if not target or not os.path.exists(target):
            QMessageBox.warning(self, "路径不存在", f"该路径已失效：\n{target}")
            return

        try:
            if os.path.isdir(target):
                # 如果是文件夹，直接打开
                os.startfile(target)
            else:
                # 如果是文件，打开父目录并选中该文件
                subprocess.Popen(f'explorer /select,"{target}"')
        except Exception as e:
            QMessageBox.critical(self, "打开失败", str(e))

    # def _open_selected(self):
    #     items = self.list_widget.selectedItems()
    #     if not items:
    #         return
    #     # 如果有多个选中的，依次打开
    #     for i, item in enumerate(items):
    #         self._open_item(item)
    #         if len(items) > 1 and i < len(items) - 1:
    #             time.sleep(0.15)
    #             # time.sleep(0.3)

    def _open_selected(self):
        items = self.list_widget.selectedItems()
        if not items:
            return
            
        # 如果只选了一个，直接打开
        if len(items) == 1:
            self._open_item(items[0])
            return

        # 如果选了多个：将同一个父目录下的文件合并打开，避免重复弹窗口
        opened_dirs = set()
        for item in items:
            p_data = item.data(Qt.ItemDataRole.UserRole)
            target = p_data.get("path", "")
            if not target or not os.path.exists(target):
                continue
                
            if os.path.isdir(target):
                # 如果是文件夹，直接记录并打开
                if target not in opened_dirs:
                    opened_dirs.add(target)
                    try:
                        os.startfile(target)
                    except Exception:
                        pass
            else:
                # 如果是文件，记录它的父目录
                parent = os.path.dirname(target)
                if parent not in opened_dirs:
                    opened_dirs.add(parent)
                    try:
                        # 打开父目录并选中该文件
                        subprocess.Popen(f'explorer /select,"{target}"')
                    except Exception:
                        pass

    # ---------- 数据存取 ----------

    def _load_data(self):
        data = load_json(DATA_FILE, {"paths": []})
        self._paths = data.get("paths", [])
        self._refresh_list()

    def _save_data(self):
        save_json(DATA_FILE, {"paths": self._paths})

    def _refresh_list(self):
        self.list_widget.clear()
        for p in self._paths:
            desc = p.get("desc", "无描述")
            path = p.get("path", "")
            
            # 显示格式
            display_text = f"[{desc}]\n  📂 {path}"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, p)
            item.setToolTip(f"点击打开: {path}")
            self.list_widget.addItem(item)

    # ---------- 增 / 改 逻辑 ----------

    def _save_path(self):
        desc = self.desc_input.text().strip()
        path = self.path_input.text().strip()

        if not path:
            QMessageBox.warning(self, "提示", "路径不能为空！")
            return
        if not desc:
            desc = "未命名路径"

        # 简单的路径格式规范化
        path = os.path.normpath(path)

        if self._editing_id:
            for p in self._paths:
                if p["id"] == self._editing_id:
                    p["desc"] = desc
                    p["path"] = path
                    break
            self._cancel_edit()
        else:
            new_path = {
                "id": str(uuid.uuid4()),
                "desc": desc,
                "path": path,
            }
            self._paths.insert(0, new_path)
            self.desc_input.clear()
            self.path_input.clear()

        self._save_data()
        self._refresh_list()

    def _start_edit(self, item: QListWidgetItem):
        p = item.data(Qt.ItemDataRole.UserRole)
        self._editing_id = p["id"]

        self.desc_input.setText(p.get("desc", ""))
        self.path_input.setText(p.get("path", ""))

        self.add_group.setTitle(f"正在编辑路径: {p.get('desc', '')}")
        self.btn_save.setText("保存修改")
        self.btn_save.setStyleSheet(
            "background-color: #F57C00; color: white; font-weight: bold; padding: 6px 20px;"
        )
        self.btn_cancel_edit.show()

    def _cancel_edit(self):
        self._editing_id = None
        self.desc_input.clear()
        self.path_input.clear()
        
        self.add_group.setTitle("添加新快捷路径")
        self.btn_save.setText("添加保存")
        self.btn_save.setStyleSheet(
            "background-color: #1565C0; color: white; font-weight: bold; padding: 6px 20px;"
        )
        self.btn_cancel_edit.hide()

    # ---------- 列表操作 ----------

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        
        menu = QMenu()
        act_open = menu.addAction("打开所在目录")
        act_edit = menu.addAction("编辑此条")
        menu.addSeparator()
        act_delete = menu.addAction("删除此条")
        act_delete.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_TrashIcon))

        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == act_open:
            self._open_item(item)
        elif action == act_edit:
            self._start_edit(item)
        elif action == act_delete:
            p_data = item.data(Qt.ItemDataRole.UserRole)
            self._paths = [p for p in self._paths if p["id"] != p_data["id"]]
            self._save_data()
            self._refresh_list()
            if self._editing_id == p_data["id"]:
                self._cancel_edit()

    def _select_all(self):
        self.list_widget.selectAll()

    def _delete_selected(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return
        
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除选中的 {len(selected_items)} 条快捷路径吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            selected_ids = {item.data(Qt.ItemDataRole.UserRole)["id"] for item in selected_items}
            self._paths = [p for p in self._paths if p["id"] not in selected_ids]
            self._save_data()
            self._refresh_list()
            if self._editing_id in selected_ids:
                self._cancel_edit()

    def _clear_all(self):
        if not self._paths:
            return
        reply = QMessageBox.question(
            self, "确认清空", "确定要删除所有快捷路径吗？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._paths.clear()
            self._save_data()
            self._refresh_list()
            self._cancel_edit()