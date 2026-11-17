import os
import uuid
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.navigation_service import (
    load_navigation,
    save_navigation,
    detect_browsers,
    open_url,
)


class NavigationTab(QWidget):
    """网址导航选项卡。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = load_navigation()
        self._current_category = ""
        self._build_ui()
        self._init_browsers()
        self._populate_tree()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # ================= 浏览器配置栏 =================
        browser_bar = QHBoxLayout()
        browser_bar.addWidget(QLabel("打开方式:"))
        self.browser_combo = QComboBox()
        self.browser_combo.setMinimumWidth(300)
        self.browser_combo.setStyleSheet("font-size: 10pt; padding: 2px 6px;")
        browser_bar.addWidget(self.browser_combo)

        self.btn_browse_browser = QPushButton("指定浏览器...")
        self.btn_browse_browser.clicked.connect(self._browse_browser)
        browser_bar.addWidget(self.btn_browse_browser)

        self.btn_save_browser = QPushButton("保存选择")
        self.btn_save_browser.clicked.connect(self._save_browser_choice)
        browser_bar.addWidget(self.btn_save_browser)
        browser_bar.addStretch()
        root.addLayout(browser_bar)

        # ================= 主体：左侧分类 + 右侧列表 =================
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---------------- 左侧分类区 ----------------
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("分类")
        self.tree.setMinimumWidth(180)
        self.tree.setStyleSheet("""
            QTreeWidget {
                font-size: 11pt;
                background-color: #FAFAFA;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
            }
            QTreeWidget::item {
                padding: 6px;
            }
        """)
        self.tree.itemClicked.connect(self._on_category_clicked)
        # 支持双击重命名
        self.tree.itemDoubleClicked.connect(self._rename_category)
        left_layout.addWidget(self.tree, stretch=1)

        # 左侧底部按钮栏
        tree_btns = QHBoxLayout()
        self.btn_add_cat = QPushButton("＋")
        self.btn_add_cat.setToolTip("添加新分类")
        self.btn_add_cat.setFixedWidth(35)
        self.btn_add_cat.clicked.connect(self._add_category)
        tree_btns.addWidget(self.btn_add_cat)

        self.btn_rename_cat = QPushButton("✎")
        self.btn_rename_cat.setToolTip("重命名选中分类")
        self.btn_rename_cat.setFixedWidth(35)
        self.btn_rename_cat.clicked.connect(lambda: self._rename_category(None, 0))
        tree_btns.addWidget(self.btn_rename_cat)

        self.btn_del_cat = QPushButton("✖")
        self.btn_del_cat.setToolTip("删除选中分类")
        self.btn_del_cat.setFixedWidth(35)
        self.btn_del_cat.setStyleSheet("color: #D32F2F;")
        self.btn_del_cat.clicked.connect(self._delete_category)
        tree_btns.addWidget(self.btn_del_cat)
        
        left_layout.addLayout(tree_btns)
        splitter.addWidget(left_widget)

        # ---------------- 右侧卡片区 ----------------
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 0, 0)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.itemDoubleClicked.connect(self._open_item)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        
        # 开启拖拽排序（仅限内部移动）
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_widget.model().rowsMoved.connect(self._on_rows_moved)
        
        self.list_widget.setStyleSheet("""
            QListWidget {
                font-size: 11pt;
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #EEEEEE;
            }
            QListWidget::item:selected {
                background-color: #BBDEFB;
                color: #0D47A1;
            }
        """)
        right_layout.addWidget(self.list_widget)

        # 右侧底部操作按钮栏
        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("＋ 添加网站")
        self.btn_add.clicked.connect(self._add_site)
        btn_row.addWidget(self.btn_add)

        self.btn_delete = QPushButton("删除选中")
        self.btn_delete.setStyleSheet("color: #D32F2F;")
        self.btn_delete.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.btn_delete)

        self.btn_open = QPushButton("打开选中项")
        self.btn_open.clicked.connect(self._open_selected)
        btn_row.addWidget(self.btn_open)

        btn_row.addSpacing(20)
        
        self.btn_move_up = QPushButton("↑ 上移")
        self.btn_move_up.clicked.connect(lambda: self._move_item_pos(-1))
        btn_row.addWidget(self.btn_move_up)

        self.btn_move_down = QPushButton("↓ 下移")
        self.btn_move_down.clicked.connect(lambda: self._move_item_pos(1))
        btn_row.addWidget(self.btn_move_down)
        
        btn_row.addStretch()
        right_layout.addLayout(btn_row)

        splitter.addWidget(right_widget)
        splitter.setSizes([200, 700])
        root.addWidget(splitter, stretch=1)

    # ================= 浏览器 =================

    def _init_browsers(self):
        self.browser_combo.clear()
        self._browsers = detect_browsers()
        if not self._browsers:
            self.browser_combo.addItem("未检测到浏览器（将使用系统默认）", "")
        else:
            for b in self._browsers:
                self.browser_combo.addItem(f"{b['name']}  —  {b['path']}", b["path"])

        saved = self._data.get("browser_path", "")
        if saved:
            idx = self.browser_combo.findData(saved)
            if idx >= 0:
                self.browser_combo.setCurrentIndex(idx)
            else:
                self.browser_combo.addItem(f"自定义  —  {saved}", saved)
                self.browser_combo.setCurrentIndex(self.browser_combo.count() - 1)

    def _browse_browser(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择浏览器可执行文件", "",
            "可执行文件 (*.exe);;所有文件 (*)",
        )
        if path:
            path = os.path.normpath(path)
            idx = self.browser_combo.findData(path)
            if idx < 0:
                self.browser_combo.addItem(f"自定义  —  {path}", path)
                idx = self.browser_combo.count() - 1
            self.browser_combo.setCurrentIndex(idx)

    def _save_browser_choice(self):
        self._data["browser_path"] = self.browser_combo.currentData() or ""
        if save_navigation(self._data):
            QMessageBox.information(self, "成功", "浏览器选择已保存。")

    def _get_browser_path(self) -> str:
        return self._data.get("browser_path", "")

    # ================= 分类管理 =================

    def _populate_tree(self, select_cat=None):
        self.tree.clear()
        categories = self._data.get("categories", {})
        target_item = None
        
        for cat_name in categories:
            item = QTreeWidgetItem([cat_name])
            item.setData(0, Qt.ItemDataRole.UserRole, cat_name)
            self.tree.addTopLevelItem(item)
            if select_cat and cat_name == select_cat:
                target_item = item

        if target_item:
            self.tree.setCurrentItem(target_item)
            self._on_category_clicked(target_item, 0)
        elif self.tree.topLevelItemCount() > 0:
            first = self.tree.topLevelItem(0)
            self.tree.setCurrentItem(first)
            self._on_category_clicked(first, 0)
        else:
            self._current_category = ""
            self._refresh_list()

    def _on_category_clicked(self, item: QTreeWidgetItem, _column: int):
        cat = item.data(0, Qt.ItemDataRole.UserRole)
        if cat:
            self._current_category = cat
            self._refresh_list()

    def _add_category(self):
        new_name, ok = QInputDialog.getText(self, "新建分类", "请输入新分类的名称:")
        if ok and new_name.strip():
            new_name = new_name.strip()
            if new_name in self._data["categories"]:
                QMessageBox.warning(self, "提示", "该分类名称已存在！")
                return
            self._data["categories"][new_name] = []
            save_navigation(self._data)
            self._populate_tree(select_cat=new_name)

    def _rename_category(self, item, _column=0):
        # 如果是从按钮点击调用，或者双击空白处，则取当前选中的
        if item is None:
            item = self.tree.currentItem()
        if not item:
            return
            
        old_name = item.data(0, Qt.ItemDataRole.UserRole)
        new_name, ok = QInputDialog.getText(self, "重命名分类", "请输入新的分类名称:", text=old_name)
        
        if ok and new_name.strip():
            new_name = new_name.strip()
            if new_name == old_name:
                return
            if new_name in self._data["categories"]:
                QMessageBox.warning(self, "提示", "该分类名称已存在！")
                return
                
            # 重建字典以保留分类排序
            new_cats = {}
            for k, v in self._data["categories"].items():
                if k == old_name:
                    new_cats[new_name] = v
                else:
                    new_cats[k] = v
            self._data["categories"] = new_cats
            save_navigation(self._data)
            self._populate_tree(select_cat=new_name)

    def _delete_category(self):
        item = self.tree.currentItem()
        if not item:
            return
        cat_name = item.data(0, Qt.ItemDataRole.UserRole)
        count = len(self._data["categories"].get(cat_name, []))
        
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除分类【{cat_name}】吗？\n该分类下的 {count} 个网址也将被彻底删除！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            del self._data["categories"][cat_name]
            save_navigation(self._data)
            self._populate_tree()

    # ================= 网址列表 =================

    def _refresh_list(self):
        self.list_widget.clear()
        cat = self._current_category
        if not cat:
            return
            
        sites = self._data.get("categories", {}).get(cat, [])
        for site in sites:
            display = f"{site['name']}\n  {site.get('desc', '')}\n  {site['url']}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, site)
            item.setToolTip(site["url"])
            self.list_widget.addItem(item)

    def _sync_list_to_data(self):
        """拖拽排序后，把列表里的当前顺序写回数据并保存。"""
        cat = self._current_category
        if not cat:
            return
        new_sites = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            new_sites.append(item.data(Qt.ItemDataRole.UserRole))
        self._data["categories"][cat] = new_sites
        save_navigation(self._data)

    def _on_rows_moved(self, parent, start, end, destination, row):
        """QListWidget 内部拖拽结束的槽函数"""
        # 使用 QTimer 稍微延迟一下，等 UI 刷新完毕再取数据
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, self._sync_list_to_data)

    def _move_item_pos(self, direction: int):
        """direction = -1 表示上移，1 表示下移"""
        items = self.list_widget.selectedItems()
        if len(items) != 1:
            return # 仅支持单行移动
            
        item = items[0]
        current_row = self.list_widget.row(item)
        new_row = current_row + direction
        
        if 0 <= new_row < self.list_widget.count():
            self.list_widget.takeItem(current_row)
            self.list_widget.insertItem(new_row, item)
            self.list_widget.setCurrentItem(item)
            self._sync_list_to_data()

    # ================= 网址增删改与移动 =================

    def _add_site(self):
        if not self._current_category:
            QMessageBox.warning(self, "提示", "请先在左侧选择一个分类。")
            return
        dlg = _SiteDialog(self)
        if dlg.exec():
            name, url, desc = dlg.get_values()
            if not name or not url:
                return
            site = {"id": str(uuid.uuid4()), "name": name, "url": url, "desc": desc}
            self._data["categories"][self._current_category].append(site)
            save_navigation(self._data)
            self._refresh_list()

    def _edit_site(self, item: QListWidgetItem):
        site = item.data(Qt.ItemDataRole.UserRole)
        dlg = _SiteDialog(self, site)
        if dlg.exec():
            name, url, desc = dlg.get_values()
            if not name or not url:
                return
            site["name"] = name
            site["url"] = url
            site["desc"] = desc
            save_navigation(self._data)
            self._refresh_list()

    def _delete_selected(self):
        items = self.list_widget.selectedItems()
        if not items:
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除选中的 {len(items)} 个网站吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        ids_to_remove = {it.data(Qt.ItemDataRole.UserRole)["id"] for it in items}
        cat_list = self._data["categories"][self._current_category]
        self._data["categories"][self._current_category] = [
            s for s in cat_list if s["id"] not in ids_to_remove
        ]
        save_navigation(self._data)
        self._refresh_list()

    def _move_sites_to_category(self, target_cat: str):
        items = self.list_widget.selectedItems()
        if not items:
            return
        source_cat = self._current_category
        if source_cat == target_cat:
            return

        moving_sites = [item.data(Qt.ItemDataRole.UserRole) for item in items]
        moving_ids = {s["id"] for s in moving_sites}

        # 从源分类移除
        self._data["categories"][source_cat] = [
            s for s in self._data["categories"][source_cat] if s["id"] not in moving_ids
        ]
        
        # 添加到目标分类
        self._data["categories"][target_cat].extend(moving_sites)
        save_navigation(self._data)
        self._refresh_list()

    # ================= 交互 =================

    def _open_item(self, item: QListWidgetItem):
        site = item.data(Qt.ItemDataRole.UserRole)
        open_url(site["url"], self._get_browser_path())

    def _open_selected(self):
        items = self.list_widget.selectedItems()
        for item in items:
            self._open_item(item)

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        menu = QMenu()
        act_open = menu.addAction("在浏览器中打开")
        act_edit = menu.addAction("编辑此网站")
        
        # 移动分类子菜单
        move_menu = menu.addMenu("移动到分类")
        categories = list(self._data["categories"].keys())
        for cat in categories:
            if cat == self._current_category:
                continue
            action = move_menu.addAction(cat)
            action.triggered.connect(lambda checked=False, c=cat: self._move_sites_to_category(c))
            
        if not move_menu.actions():
            move_menu.setEnabled(False)

        menu.addSeparator()
        act_delete = menu.addAction("删除此网站")
        act_delete.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_TrashIcon))

        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == act_open:
            self._open_item(item)
        elif action == act_edit:
            self._edit_site(item)
        elif action == act_delete:
            self.list_widget.setCurrentItem(item)
            self._delete_selected()


class _SiteDialog(QDialog):
    def __init__(self, parent=None, site: dict = None):
        super().__init__(parent)
        self.setWindowTitle("编辑网站" if site else "添加网站")
        self.resize(650, 220)
        self.setSizeGripEnabled(True)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(site["name"] if site else "")
        self.url_edit = QLineEdit(site["url"] if site else "")
        self.desc_edit = QLineEdit(site.get("desc", "") if site else "")
        
        form.addRow("名称:", self.name_edit)
        form.addRow("网址:", self.url_edit)
        form.addRow("简介:", self.desc_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self) -> tuple[str, str, str]:
        return (
            self.name_edit.text().strip(),
            self.url_edit.text().strip(),
            self.desc_edit.text().strip(),
        )