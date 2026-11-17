import sys
import os
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from app.main_window import MainWindow
from app.utils.theme_manager import ThemeManager
from app.services.autostart_service import get_app_config

# 适配 PyInstaller 打包后的资源路径
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ==================== 单实例控制逻辑 ====================
SERVER_NAME = "PersonalWorkbench_SingleInstance_Server"

def check_single_instance(window) -> bool:
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    
    if socket.waitForConnected(500):
        # 连接成功，说明已经有程序在运行了
        print("检测到已有实例在运行，正在激活已有窗口并退出当前程序...")
        socket.write(b"activate")
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        return False

    # 如果没有连上，说明是第一个实例，建立服务端监听
    # 针对 Windows 平台的清理机制：移除可能残留的旧管道
    QLocalServer.removeServer(SERVER_NAME)
    server = QLocalServer()
    
    if not server.listen(SERVER_NAME):
        QMessageBox.critical(None, "错误", "本地服务启动失败。\n请检查任务管理器中是否有卡死的残留进程。")
        return True

    def on_new_connection():
        new_socket = server.nextPendingConnection()
        if new_socket:
            new_socket.readyRead.connect(lambda: on_ready_read(new_socket))

    def on_ready_read(sock):
        data = sock.readAll().data()
        if data == b"activate" and window:
            # 将已存在的窗口带到前台
            window.showNormal() # 如果最小化了，先恢复
            window.raise_()     # 置顶
            window.activateWindow() # 获取焦点
        sock.disconnectFromServer()

    server.newConnection.connect(on_new_connection)
    window._local_server = server
    return True
# =========================================================

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("WeatherCenter")

    font = QFont()
    font.setFamilies(["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"])
    font.setPointSize(10)
    app.setFont(font)

    icon_path = resource_path("app.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    cfg = get_app_config()
    ThemeManager.apply_theme(cfg.get("dark_mode", False))

    window = MainWindow()

    if not check_single_instance(window):
        # 核心修复：使用 os._exit(0) 立即强制结束，避免后台线程阻塞退出
        os._exit(0)

    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()