from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication
from app.services.autostart_service import get_app_config, save_app_config


class ThemeManager:
    @staticmethod
    def apply_theme(is_dark: bool):
        app = QApplication.instance()
        app.setStyle("Fusion")
        
        # 关键：每次切换前，先清空所有的全局 QSS，防止旧样式残留
        app.setStyleSheet("")
        
        palette = QPalette()
        if is_dark:
            palette.setColor(QPalette.ColorRole.Window, QColor("#2b2b2b"))
            palette.setColor(QPalette.ColorRole.WindowText, QColor("#e0e0e0"))
            palette.setColor(QPalette.ColorRole.Base, QColor("#1e1e1e"))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#353535"))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2b2b2b"))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#e0e0e0"))
            palette.setColor(QPalette.ColorRole.Text, QColor("#e0e0e0"))
            palette.setColor(QPalette.ColorRole.Button, QColor("#3c3f41"))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e0e0e0"))
            palette.setColor(QPalette.ColorRole.BrightText, QColor("#ff5555"))
            palette.setColor(QPalette.ColorRole.Link, QColor("#589df6"))
            palette.setColor(QPalette.ColorRole.Highlight, QColor("#2a82da"))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))
            
            app.setStyleSheet("""
                QToolTip { color: #e0e0e0; background-color: #2b2b2b; border: 1px solid #555; }
                
                /* 强覆盖所有的文本/输入框，清除局部 QSS 的残留 */
                QTextEdit, QPlainTextEdit, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { 
                    background-color: #1e1e1e !important; 
                    color: #e0e0e0 !important; 
                    border: 1px solid #555; 
                }
                QListWidget, QTableWidget, QTreeWidget { 
                    background-color: #1e1e1e !important; 
                    color: #e0e0e0 !important; 
                    alternate-background-color: #2b2b2b !important; 
                }
                
                QHeaderView::section { background-color: #3c3f41; color: #e0e0e0; border: 1px solid #555; }
                QGroupBox { border: 1px solid #555; border-radius: 4px; margin-top: 10px; }
                QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; }
                QTabWidget::pane { border: 1px solid #555; }
                QTabBar::tab { background: #3c3f41; color: #e0e0e0; padding: 8px 16px; border: 1px solid #555; border-bottom: none; }
                QTabBar::tab:selected { background: #2b2b2b; border-bottom: 1px solid #2b2b2b; }
                QPushButton { background-color: #3c3f41; color: #e0e0e0; border: 1px solid #555; border-radius: 4px; padding: 4px 10px; }
                QPushButton:hover { background-color: #4a4d4f; }
                QLabel { background: transparent; }
            """)
        else:
            # 亮色模式
            palette.setColor(QPalette.ColorRole.Window, QColor("#F5F7FA"))
            palette.setColor(QPalette.ColorRole.WindowText, QColor("#212121"))
            palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F0F0F0"))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#FFFFFF"))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#212121"))
            palette.setColor(QPalette.ColorRole.Text, QColor("#212121"))
            palette.setColor(QPalette.ColorRole.Button, QColor("#EAEAEA"))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor("#212121"))
            palette.setColor(QPalette.ColorRole.BrightText, QColor("#D32F2F"))
            palette.setColor(QPalette.ColorRole.Link, QColor("#1565C0"))
            palette.setColor(QPalette.ColorRole.Highlight, QColor("#1565C0"))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
            
            app.setStyleSheet("""
                /* 强覆盖所有的文本/输入框，清除局部 QSS 的残留 */
                QTextEdit, QPlainTextEdit, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { 
                    background-color: #FFFFFF !important; 
                    color: #212121 !important; 
                }
                QListWidget, QTableWidget, QTreeWidget { 
                    background-color: #FFFFFF !important; 
                    color: #212121 !important; 
                }
                
                QTabBar::tab { padding: 8px 16px; }
                QPushButton { padding: 4px 10px; }
                QLabel { background: transparent; }
            """)
            
        app.setPalette(palette)
        
        cfg = get_app_config()
        cfg["dark_mode"] = is_dark
        save_app_config(cfg)