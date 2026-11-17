import uuid
import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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

from app.services.command_service import execute_command, get_conda_envs
from app.utils.storage import load_json, save_json

DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "commands.json",
)


class CommandTab(QWidget):
    """命令管理选项卡。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._commands = []  # 内存中的命令列表
        self._editing_id = None  # 当前正在编辑的命令 ID
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # ================= 1. 添加/编辑区域 =================
        self.add_group = QGroupBox("添加新命令")
        self.add_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        add_layout = QVBoxLayout(self.add_group)

        # 第一行：类型、Conda环境、描述
        row1 = QHBoxLayout()
        
        row1.addWidget(QLabel("类型:"))
        self.type_combo = QComboBox()
        self.type_combo.addItem("CMD", "cmd")
        self.type_combo.addItem("PowerShell", "powershell")
        self.type_combo.addItem("Anaconda", "conda")
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        row1.addWidget(self.type_combo)

        # Conda 环境选择区（可编辑的下拉框 + 刷新按钮）
        self.conda_label = QLabel("环境名:")
        self.conda_env_combo = QComboBox()
        self.conda_env_combo.setEditable(True)
        self.conda_env_combo.setFixedWidth(120)
        self.btn_refresh_conda = QPushButton("↻")
        self.btn_refresh_conda.setToolTip("刷新 Conda 环境列表")
        self.btn_refresh_conda.setFixedWidth(30)
        self.btn_refresh_conda.clicked.connect(self._load_conda_envs)
        
        self.conda_label.hide()
        self.conda_env_combo.hide()
        self.btn_refresh_conda.hide()
        
        row1.addWidget(self.conda_label)
        row1.addWidget(self.conda_env_combo)
        row1.addWidget(self.btn_refresh_conda)

        row1.addSpacing(20)
        row1.addWidget(QLabel("描述:"))
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("例如: 查看网络连通性")
        row1.addWidget(self.desc_input)
        add_layout.addLayout(row1)

        # 第二行：具体命令 + 操作按钮
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("指令:"))
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText('例如: ping 127.0.0.1')
        row2.addWidget(self.cmd_input)

        self.btn_save = QPushButton("添加保存")
        self.btn_save.setStyleSheet(
            "background-color: #1565C0; color: white; font-weight: bold; padding: 6px 15px;"
        )
        self.btn_save.clicked.connect(self._save_command)
        row2.addWidget(self.btn_save)

        self.btn_cancel_edit = QPushButton("取消编辑")
        self.btn_cancel_edit.setStyleSheet("padding: 6px 15px;")
        self.btn_cancel_edit.clicked.connect(self._cancel_edit)
        self.btn_cancel_edit.hide()
        row2.addWidget(self.btn_cancel_edit)

        add_layout.addLayout(row2)
        root.addWidget(self.add_group)

        # ================= 2. 列表与操作区域 =================
        list_group = QGroupBox("已保存的命令（双击执行 / 右键编辑）")
        list_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        list_layout = QVBoxLayout(list_group)

        toolbar = QHBoxLayout()
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.clicked.connect(self._select_all)
        
        self.btn_delete_selected = QPushButton("删除选中")
        self.btn_delete_selected.setStyleSheet("color: #D32F2F;")
        self.btn_delete_selected.clicked.connect(self._delete_selected)
        
        self.btn_clear_all = QPushButton("全部清空")
        self.btn_clear_all.setStyleSheet("color: #D32F2F;")
        self.btn_clear_all.clicked.connect(self._clear_all)

        toolbar.addWidget(self.btn_select_all)
        toolbar.addWidget(self.btn_delete_selected)
        toolbar.addWidget(self.btn_clear_all)
        toolbar.addStretch()
        list_layout.addLayout(toolbar)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.itemDoubleClicked.connect(self._execute_item)
        
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

    # ---------- 类型与环境交互 ----------

    def _on_type_changed(self):
        is_conda = self.type_combo.currentData() == "conda"
        self.conda_label.setVisible(is_conda)
        self.conda_env_combo.setVisible(is_conda)
        self.btn_refresh_conda.setVisible(is_conda)
        
        if is_conda and self.conda_env_combo.count() == 0:
            self._load_conda_envs()

    # def _load_conda_envs(self):
    #     """从系统拉取 conda 环境并填充下拉框。"""
    #     self.btn_refresh_conda.setEnabled(False)
    #     self.btn_refresh_conda.setText("...")
        
    #     envs = get_conda_envs()
        
    #     self.conda_env_combo.clear()
    #     self.conda_env_combo.addItems(envs)
        
    #     self.btn_refresh_conda.setEnabled(True)
    #     self.btn_refresh_conda.setText("↻")

    def _load_conda_envs(self):
        """从系统拉取 conda 环境并填充下拉框。"""
        self.btn_refresh_conda.setEnabled(False)
        self.btn_refresh_conda.setText("...")
        
        current_text = self.conda_env_combo.currentText()  # 记录当前选中的
        
        envs = get_conda_envs()
        
        self.conda_env_combo.clear()
        self.conda_env_combo.addItems(envs)
        
        if current_text:  # 恢复之前选中的
            self.conda_env_combo.setCurrentText(current_text)
            
        self.btn_refresh_conda.setEnabled(True)
        self.btn_refresh_conda.setText("↻")

    # ---------- 数据存取 ----------

    def _load_data(self):
        data = load_json(DATA_FILE, {"commands": []})
        self._commands = data.get("commands", [])
        self._refresh_list()

    def _save_data(self):
        save_json(DATA_FILE, {"commands": self._commands})

    def _refresh_list(self):
        self.list_widget.clear()
        for cmd in self._commands:
            ctype = cmd["type"].upper()
            desc = cmd.get("desc", "无描述")
            env_str = f"[{cmd['conda_env']}] " if ctype == "CONDA" and cmd.get("conda_env") else ""
            
            display_text = f"[{ctype}] {env_str}{desc}\n  > {cmd['content']}"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, cmd)
            self.list_widget.addItem(item)

    # ---------- 增 / 改 逻辑 ----------

    def _save_command(self):
        ctype = self.type_combo.currentData()
        content = self.cmd_input.text().strip()
        desc = self.desc_input.text().strip()
        conda_env = self.conda_env_combo.currentText().strip() if ctype == "conda" else ""

        if not content:
            QMessageBox.warning(self, "提示", "指令内容不能为空！")
            return
        if not desc:
            desc = "未命名指令"

        if self._editing_id:
            # 处于编辑模式，更新原数据
            for cmd in self._commands:
                if cmd["id"] == self._editing_id:
                    cmd["type"] = ctype
                    cmd["content"] = content
                    cmd["desc"] = desc
                    cmd["conda_env"] = conda_env
                    break
            self._cancel_edit()  # 更新后重置状态
        else:
            # 新增模式
            new_cmd = {
                "id": str(uuid.uuid4()),
                "type": ctype,
                "content": content,
                "desc": desc,
                "conda_env": conda_env,
            }
            self._commands.insert(0, new_cmd)
            self.cmd_input.clear()
            self.desc_input.clear()

        self._save_data()
        self._refresh_list()

    def _start_edit(self, item: QListWidgetItem):
        cmd = item.data(Qt.ItemDataRole.UserRole)
        self._editing_id = cmd["id"]

        # 回填数据
        idx = self.type_combo.findData(cmd["type"])
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        
        # 如果之前没加载过 conda 环境，这里触发一下加载
        if cmd["type"] == "conda" and self.conda_env_combo.count() == 0:
            self._load_conda_envs()
        self.conda_env_combo.setCurrentText(cmd.get("conda_env", ""))
        
        self.cmd_input.setText(cmd["content"])
        self.desc_input.setText(cmd.get("desc", ""))

        # 切换 UI 状态
        self.add_group.setTitle(f"正在编辑命令: {cmd.get('desc', '')}")
        self.btn_save.setText("保存修改")
        self.btn_save.setStyleSheet(
            "background-color: #F57C00; color: white; font-weight: bold; padding: 6px 15px;"
        )
        self.btn_cancel_edit.show()

    def _cancel_edit(self):
        self._editing_id = None
        self.cmd_input.clear()
        self.desc_input.clear()
        self.conda_env_combo.setCurrentIndex(0)
        
        self.add_group.setTitle("添加新命令")
        self.btn_save.setText("添加保存")
        self.btn_save.setStyleSheet(
            "background-color: #1565C0; color: white; font-weight: bold; padding: 6px 15px;"
        )
        self.btn_cancel_edit.hide()

    # ---------- 列表操作 ----------

    def _execute_item(self, item: QListWidgetItem):
        cmd = item.data(Qt.ItemDataRole.UserRole)
        success, err = execute_command(
            cmd["type"], cmd["content"], cmd.get("conda_env", ""), cmd.get("desc", "")
        )
        if not success:
            QMessageBox.critical(self, "执行失败", f"无法启动终端: {err}")

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        
        menu = QMenu()
        act_run = menu.addAction("立即执行")
        act_edit = menu.addAction("编辑此条")
        menu.addSeparator()
        act_delete = menu.addAction("删除此条")
        act_delete.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_TrashIcon))

        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == act_run:
            self._execute_item(item)
        elif action == act_edit:
            self._start_edit(item)
        elif action == act_delete:
            cmd_data = item.data(Qt.ItemDataRole.UserRole)
            self._commands = [c for c in self._commands if c["id"] != cmd_data["id"]]
            self._save_data()
            self._refresh_list()
            # 如果刚好删掉了正在编辑的那一条，重置状态
            if self._editing_id == cmd_data["id"]:
                self._cancel_edit()

    def _select_all(self):
        self.list_widget.selectAll()

    def _delete_selected(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return
        
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除选中的 {len(selected_items)} 条命令吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            selected_ids = {item.data(Qt.ItemDataRole.UserRole)["id"] for item in selected_items}
            self._commands = [c for c in self._commands if c["id"] not in selected_ids]
            self._save_data()
            self._refresh_list()
            # 同理，如果删掉了正在编辑的项
            if self._editing_id in selected_ids:
                self._cancel_edit()

    def _clear_all(self):
        if not self._commands:
            return
        reply = QMessageBox.question(
            self, "确认清空", "确定要删除所有命令吗？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._commands.clear()
            self._save_data()
            self._refresh_list()
            self._cancel_edit()