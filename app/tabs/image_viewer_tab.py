import os
from collections import deque

from PySide6.QtCore import (
    Qt, QThread, Signal, QSize, QRectF, QRect, QTimer, QMutex, QMutexLocker, QWaitCondition
)
from PySide6.QtGui import (
    QPixmap, QImageReader, QMouseEvent, QWheelEvent, QPainter, QCursor, QColor
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSpinBox,
    QScrollArea, QGridLayout, QFileDialog, QMessageBox, QToolTip, QDialog,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QFrame, QSizePolicy,
    QApplication
)


# ------------------------------ 缩略图生成线程 ------------------------------
class ThumbnailWorker(QThread):
    thumbnail_ready = Signal(str, QPixmap)

    def __init__(self, base_size=300):
        super().__init__()
        self.base_size = QSize(base_size, base_size)
        self._running = True
        self._queue = deque()
        self._mutex = QMutex()
        self._cond = QWaitCondition()

    def add_tasks(self, paths):
        with QMutexLocker(self._mutex):
            for p in paths:
                if p not in self._queue:
                    self._queue.append(p)
            self._cond.wakeOne()

    def clear_tasks(self):
        """切换文件夹时清空任务队列"""
        with QMutexLocker(self._mutex):
            self._queue.clear()

    def stop(self):
        with QMutexLocker(self._mutex):
            self._running = False
            self._cond.wakeOne()

    def run(self):
        while self._running:
            self._mutex.lock()
            if not self._queue:
                self._cond.wait(self._mutex, 100)
                self._mutex.unlock()
                continue
            path = self._queue.popleft()
            self._mutex.unlock()

            if not self._running:
                break

            reader = QImageReader(path)
            reader.setAutoTransform(True)
            reader.setScaledSize(self.base_size)
            image = reader.read()
            if not image.isNull() and self._running:
                pixmap = QPixmap.fromImage(image)
                pixmap = pixmap.scaled(
                    self.base_size.width(), self.base_size.height(),
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                self.thumbnail_ready.emit(path, pixmap)


# ------------------------------ 自定义图片控件 ------------------------------
class ImageWidget(QFrame):
    clicked = Signal(str)
    double_clicked = Signal(str)
    right_clicked = Signal(str)
    right_double_clicked = Signal(str)

    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.thumbnail = None
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("""
            ImageWidget {
                background-color: #F8F9FA;
                border-radius: 6px;
                border: 1px solid #E0E0E0;
            }
            ImageWidget:hover {
                border: 1px solid #1565C0;
                background-color: #E3F2FD;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(False)
        layout.addWidget(self.image_label)

        self.click_timer = QTimer()
        self.click_timer.setSingleShot(True)
        self.click_timer.timeout.connect(self._on_click_timeout)
        self.pending_click = False

        self.right_click_timer = QTimer()
        self.right_click_timer.setSingleShot(True)
        self.right_click_timer.timeout.connect(self._on_right_click_timeout)
        self.pending_right_click = False

    def set_thumbnail(self, pixmap):
        self.thumbnail = pixmap
        self._update_display()

    def _update_display(self):
        if self.thumbnail and not self.thumbnail.isNull():
            label_size = self.image_label.size()
            if label_size.width() > 0 and label_size.height() > 0:
                scaled = self.thumbnail.scaled(
                    label_size, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(scaled)

    def resizeEvent(self, event):
        self._update_display()
        super().resizeEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pending_click = True
            self.click_timer.start(QApplication.doubleClickInterval())
        elif event.button() == Qt.MouseButton.RightButton:
            self.pending_right_click = True
            self.right_click_timer.start(QApplication.doubleClickInterval())
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.pending_click:
                self.click_timer.stop()
                self.pending_click = False
            self.double_clicked.emit(self.image_path)
        elif event.button() == Qt.MouseButton.RightButton:
            if self.pending_right_click:
                self.right_click_timer.stop()
                self.pending_right_click = False
            self.right_double_clicked.emit(self.image_path)
        super().mouseDoubleClickEvent(event)

    def _on_click_timeout(self):
        if self.pending_click:
            self.pending_click = False
            self.clicked.emit(self.image_path)

    def _on_right_click_timeout(self):
        if self.pending_right_click:
            self.pending_right_click = False
            self.right_clicked.emit(self.image_path)


# ------------------------------ 全屏预览窗口 ------------------------------
class FullscreenPreview(QDialog):
    def __init__(self, page_paths, current_index, parent=None):
        super().__init__(parent)
        self.page_paths = page_paths
        self.current_index = current_index
        self._view_mode = 'fit'
        
        self.setWindowTitle("图片预览")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.showFullScreen()

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setBackgroundBrush(QColor("black"))

        self.info_label = QLabel(self)
        self.info_label.setStyleSheet("color: white; background-color: rgba(0,0,0,150); padding: 8px 15px; border-radius: 8px; font-size: 14px;")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.setLayout(layout)

        self.info_timer = QTimer(self)
        self.info_timer.setSingleShot(True)
        self.info_timer.timeout.connect(self.info_label.hide)

        self.pixmap_item = None
        self.load_current_image()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def load_current_image(self):
        if self.current_index < 0 or self.current_index >= len(self.page_paths):
            return
        image_path = self.page_paths[self.current_index]
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return

        self.scene.clear()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)
        self.scene.setSceneRect(QRectF(pixmap.rect()))
        self.reset_view()

        file_name = os.path.basename(image_path)
        total = len(self.page_paths)
        self.info_label.setText(f"{file_name}  ({self.current_index+1}/{total})  |  ←/A 上一张  →/D 下一张  ESC 关闭")
        self.info_label.adjustSize()
        self.update_info_label_position()
        self.info_label.show()
        self.info_timer.start(3000)

    def update_info_label_position(self):
        if hasattr(self, 'info_label') and self.info_label:
            self.info_label.move(
                self.width() - self.info_label.width() - 20,
                self.height() - self.info_label.height() - 20
            )

    def reset_view(self):
        if self.pixmap_item:
            self.view.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            self._view_mode = 'fit'

    def zoom_in(self):
        self.view.scale(1.2, 1.2)
        self._view_mode = 'custom'

    def zoom_out(self):
        self.view.scale(1 / 1.2, 1 / 1.2)
        self._view_mode = 'custom'

    def original_size(self):
        self.view.resetTransform()
        if self.pixmap_item:
            self.view.centerOn(self.pixmap_item)
            self._view_mode = 'original'

    def toggle_fit_original(self):
        if self._view_mode == 'fit':
            self.original_size()
        else:
            self.reset_view()

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        self.view.scale(factor, factor)
        self._view_mode = 'custom'

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_fit_original()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_A, Qt.Key.Key_W):
            total = len(self.page_paths)
            if total > 0:
                self.current_index = (self.current_index - 1) % total
                self.load_current_image()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_D, Qt.Key.Key_S):
            total = len(self.page_paths)
            if total > 0:
                self.current_index = (self.current_index + 1) % total
                self.load_current_image()
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_in()
        elif key == Qt.Key.Key_Minus:
            self.zoom_out()
        elif key == Qt.Key.Key_0:
            self.original_size()
        elif key in (Qt.Key.Key_F, Qt.Key.Key_Space):
            self.reset_view()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'info_label') and self.info_label and self.info_label.isVisible():
            self.update_info_label_position()


# ------------------------------ 图片查看器主面板 ------------------------------
# ------------------------------ 图片查看器主面板 ------------------------------
class ImageViewerTab(QWidget):
    """本地图片查看器选项卡。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.folder_path = ""
        self.image_paths = []
        self.thumbnails = {}
        self.current_widgets = {}
        
        self.rows = 3
        self.cols = 4
        self.row_spacing = 10
        self.col_spacing = 10
        self.current_page = 0
        self.total_pages = 0
        self.pending_thumb_paths = set()
        
        # 防重入锁 & 防抖计时器
        self._is_rendering = False
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self._safe_render_page)

        # 初始化后台工作线程
        self.thumbnail_worker = ThumbnailWorker(base_size=300)
        self.thumbnail_worker.thumbnail_ready.connect(self.on_thumbnail_ready)
        self.thumbnail_worker.start()
        
        QApplication.instance().aboutToQuit.connect(self.shutdown)

        self.setup_ui()
        self.set_controls_enabled(False)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 控制栏
        control_bar = QHBoxLayout()
        self.folder_btn = QPushButton("选择文件夹")
        self.folder_btn.clicked.connect(self.select_folder)
        self.folder_label = QLabel("未选择文件夹")
        self.folder_label.setStyleSheet("color: #546E7A;")
        control_bar.addWidget(self.folder_btn)
        control_bar.addWidget(self.folder_label)
        control_bar.addSpacing(20)

        control_bar.addWidget(QLabel("行数:"))
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 10)
        self.rows_spin.setValue(self.rows)
        self.rows_spin.valueChanged.connect(self.on_layout_param_changed)
        control_bar.addWidget(self.rows_spin)

        control_bar.addWidget(QLabel("列数:"))
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 10)
        self.cols_spin.setValue(self.cols)
        self.cols_spin.valueChanged.connect(self.on_layout_param_changed)
        control_bar.addWidget(self.cols_spin)

        control_bar.addWidget(QLabel("间距:"))
        self.row_spacing_spin = QSpinBox()
        self.row_spacing_spin.setRange(0, 50)
        self.row_spacing_spin.setValue(self.row_spacing)
        self.row_spacing_spin.valueChanged.connect(self.on_layout_param_changed)
        control_bar.addWidget(self.row_spacing_spin)

        control_bar.addStretch()

        self.prev_btn = QPushButton("上一页")
        self.prev_btn.clicked.connect(self.prev_page)
        self.page_label = QLabel("第 0 / 0 页")
        self.next_btn = QPushButton("下一页")
        self.next_btn.clicked.connect(self.next_page)
        
        control_bar.addWidget(self.prev_btn)
        control_bar.addWidget(self.page_label)
        control_bar.addWidget(self.next_btn)

        main_layout.addLayout(control_bar)

        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        self.image_container = QWidget()
        self.image_layout = QGridLayout(self.image_container)
        self.image_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.image_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_area.setWidget(self.image_container)
        main_layout.addWidget(self.scroll_area, stretch=1)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #757575;")
        main_layout.addWidget(self.status_label)

    def set_controls_enabled(self, enabled):
        self.prev_btn.setEnabled(enabled)
        self.next_btn.setEnabled(enabled)
        self.rows_spin.setEnabled(enabled)
        self.cols_spin.setEnabled(enabled)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹", "")
        if not folder:
            return
        self.folder_path = folder
        self.folder_label.setText(folder)
        self.load_images_from_folder()

    def load_images_from_folder(self):
        self.refresh_timer.stop()
        self.thumbnail_worker.clear_tasks()
        self.pending_thumb_paths.clear()
        self.thumbnails.clear()

        self.image_paths = []
        extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
        try:
            for file in os.listdir(self.folder_path):
                ext = os.path.splitext(file)[1].lower()
                if ext in extensions:
                    full_path = os.path.join(self.folder_path, file)
                    self.image_paths.append(full_path)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"读取文件夹失败: {e}")
            return

        self.image_paths.sort(key=lambda x: os.path.basename(x).lower())

        if not self.image_paths:
            QMessageBox.information(self, "提示", "该文件夹中没有支持的图片文件。")
            self.current_page = 0
            self.total_pages = 0
            self.update_page_display()
            self.clear_image_grid()
            self.set_controls_enabled(False)
            return

        self.current_page = 0
        self.update_page_params()
        self._safe_render_page()
        self.set_controls_enabled(True)
        self.status_label.setText(f"共加载 {len(self.image_paths)} 张图片")

    def update_page_params(self):
        page_size = self.rows * self.cols
        if page_size <= 0:
            return
        total = len(self.image_paths)
        self.total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        if self.current_page >= self.total_pages:
            self.current_page = max(0, self.total_pages - 1)
        if self.total_pages == 0:
            self.current_page = 0
        self.update_page_display()

    def update_page_display(self):
        self.page_label.setText(f"第 {self.current_page + 1} / {self.total_pages} 页")

    def generate_thumbnails_for_paths(self, paths):
        if not paths:
            return
        new_paths = [p for p in paths if p not in self.thumbnails and p not in self.pending_thumb_paths]
        if not new_paths:
            return

        for p in new_paths:
            self.pending_thumb_paths.add(p)

        self.thumbnail_worker.add_tasks(new_paths)

    def on_thumbnail_ready(self, image_path, pixmap):
        if not self.isVisible():
            return
        self.thumbnails[image_path] = pixmap
        if image_path in self.pending_thumb_paths:
            self.pending_thumb_paths.remove(image_path)
            
        # 如果当前正在重建 UI，忽略这个信号，防止给旧控件赋值引发崩溃
        if self._is_rendering:
            return
            
        if image_path in self.current_widgets:
            widget = self.current_widgets[image_path]
            widget.set_thumbnail(pixmap)

    def clear_image_grid(self):
        """彻底清理布局和控件，断开信号"""
        self.current_widgets.clear()
        while self.image_layout.count():
            item = self.image_layout.takeAt(0)
            widget = item.widget()
            if widget:
                # 强行断开所有可能引发事件的信号
                try:
                    widget.clicked.disconnect()
                    widget.double_clicked.disconnect()
                    widget.right_clicked.disconnect()
                except RuntimeError:
                    pass
                widget.setParent(None)
                widget.deleteLater()

    def calculate_cell_size(self):
        viewport = self.scroll_area.viewport()
        if not viewport:
            return QSize(100, 100)
        available_width = viewport.width() - 20 # 预留滚动条空间
        available_height = viewport.height() - 20
        
        cell_width = (available_width - (self.cols - 1) * self.col_spacing) // self.cols if self.cols > 0 else 100
        cell_height = (available_height - (self.rows - 1) * self.row_spacing) // self.rows if self.rows > 0 else 100
        
        return QSize(max(cell_width, 40), max(cell_height, 40))

    def on_layout_param_changed(self):
        self.rows = self.rows_spin.value()
        self.cols = self.cols_spin.value()
        self.row_spacing = self.row_spacing_spin.value()
        self.col_spacing = self.row_spacing_spin.value()

        self.update_page_params()
        self.refresh_timer.start(200) # 延迟防抖

    def get_current_page_paths(self):
        if not self.image_paths:
            return []
        page_size = self.rows * self.cols
        start_idx = self.current_page * page_size
        end_idx = min(start_idx + page_size, len(self.image_paths))
        return self.image_paths[start_idx:end_idx]

    def _safe_render_page(self):
        """防重入的安全渲染函数"""
        if self._is_rendering:
            return
        self._is_rendering = True
        self.set_controls_enabled(False) # 渲染期间暂时禁用按钮，防止连点

        try:
            self.display_current_page()
        finally:
            self._is_rendering = False
            self.set_controls_enabled(True)

    def display_current_page(self):
        if not self.image_paths:
            return

        page_size = self.rows * self.cols
        start_idx = self.current_page * page_size
        end_idx = min(start_idx + page_size, len(self.image_paths))

        self.clear_image_grid()

        self.image_layout.setHorizontalSpacing(self.col_spacing)
        self.image_layout.setVerticalSpacing(self.row_spacing)

        cell_size = self.calculate_cell_size()
        current_page_paths = self.image_paths[start_idx:end_idx]

        row, col = 0, 0
        for img_path in current_page_paths:
            widget = ImageWidget(img_path)
            widget.setFixedSize(cell_size)
            widget.clicked.connect(self.on_image_clicked)
            widget.double_clicked.connect(self.on_left_double_click)
            widget.right_clicked.connect(self.on_right_click)
            
            if img_path in self.thumbnails:
                widget.set_thumbnail(self.thumbnails[img_path])
                
            self.image_layout.addWidget(widget, row, col)
            self.current_widgets[img_path] = widget
            
            col += 1
            if col >= self.cols:
                col = 0
                row += 1

        self.update_page_display()
        
        # 预加载下一页图片
        missing_paths = [p for p in current_page_paths if p not in self.thumbnails]
        if missing_paths:
            self.generate_thumbnails_for_paths(missing_paths)

        if self.total_pages > 0:
            next_page = (self.current_page + 1) % self.total_pages
            if next_page != self.current_page:
                next_start = next_page * page_size
                next_end = min(next_start + page_size, len(self.image_paths))
                next_paths = self.image_paths[next_start:next_end]
                missing_next = [p for p in next_paths if p not in self.thumbnails]
                if missing_next:
                    self.generate_thumbnails_for_paths(missing_next)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 拉伸窗口时，只调整已有控件的大小，绝不触发重新生成，防止死循环
        if self.image_paths and not self._is_rendering:
            cell_size = self.calculate_cell_size()
            for widget in self.current_widgets.values():
                widget.setFixedSize(cell_size)

    def prev_page(self):
        if self.total_pages <= 0 or self._is_rendering:
            return
        self.current_page = (self.current_page - 1) % self.total_pages
        self.update_page_display()
        self.refresh_timer.start(50)

    def next_page(self):
        if self.total_pages <= 0 or self._is_rendering:
            return
        self.current_page = (self.current_page + 1) % self.total_pages
        self.update_page_display()
        self.refresh_timer.start(50)

    def on_image_clicked(self, image_path):
        current_page_paths = self.get_current_page_paths()
        if image_path in current_page_paths:
            current_idx = current_page_paths.index(image_path)
            preview = FullscreenPreview(current_page_paths, current_idx, self)
            preview.exec()

    def on_left_double_click(self, image_path):
        base_name = os.path.basename(image_path)
        QApplication.clipboard().setText(base_name)
        self.status_label.setText(f"✅ 已复制文件名: {base_name}")
        QTimer.singleShot(2000, lambda: self.status_label.setText("就绪"))

    def on_right_click(self, image_path):
        file_name = os.path.basename(image_path)
        cursor_pos = QCursor.pos()
        QToolTip.showText(cursor_pos, file_name, self, QRect(), 3000)

    def shutdown(self):
        if hasattr(self, 'thumbnail_worker') and self.thumbnail_worker is not None:
            if self.thumbnail_worker.isRunning():
                self.thumbnail_worker.stop()
                self.thumbnail_worker.wait(1000)
            self.thumbnail_worker = None

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)