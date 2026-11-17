import os
import subprocess
import ctypes
import winreg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

try:
    from pycaw.pycaw import AudioUtilities
    HAS_PYCAW = True
except ImportError:
    HAS_PYCAW = False

from app.utils.theme_manager import ThemeManager
from app.services.autostart_service import set_auto_start, is_auto_start_enabled, get_app_config


class SystemTab(QWidget):
    """系统工具选项卡：集成了高频系统管理与实用小工具。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        # 缩减边距，使界面更紧凑，避免撑爆窗口高度
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # ================= 1. 快捷控制中心 =================
        quick_group = QGroupBox("快捷控制中心")
        quick_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11pt; }")
        quick_layout = QGridLayout(quick_group)
        quick_layout.setSpacing(8)
        quick_layout.setContentsMargins(10, 15, 10, 10)

        # 获取当前配置，动态设置初始按钮文字
        is_dark = get_app_config().get("dark_mode", False)
        is_autostart = is_auto_start_enabled()

        self.btn_theme_toggle = QPushButton("切换亮色模式" if is_dark else "切换暗黑模式")
        self.btn_theme_toggle.setMinimumHeight(32)
        self.btn_theme_toggle.setStyleSheet("background-color: #607D8B; color: white; font-weight: bold;")
        self.btn_theme_toggle.clicked.connect(self._toggle_dark_mode)
        quick_layout.addWidget(self.btn_theme_toggle, 0, 0)
        
        self.btn_autostart = QPushButton("关闭开机自启" if is_autostart else "开启开机自启")
        self.btn_autostart.setMinimumHeight(32)
        self.btn_autostart.setStyleSheet("background-color: #455A64; color: white; font-weight: bold;")
        self.btn_autostart.clicked.connect(self._toggle_autostart)
        quick_layout.addWidget(self.btn_autostart, 0, 1)

        quick_btns = [
            ("切换为亮色系统主题", lambda: self._set_theme(False), ""),
            ("切换为暗色系统主题", lambda: self._set_theme(True), ""),
            ("音量 -", lambda: self._adjust_volume(-0.05), ""),
            ("音量 +", lambda: self._adjust_volume(0.05), ""),
            ("打开 Wi-Fi 面板", lambda: os.startfile("ms-settings:network-wifi"), ""),
            ("断开 Wi-Fi 连接", self._disconnect_wifi, "#D32F2F"),
            ("开启蓝牙", lambda: self._set_bluetooth_state(True), ""),
            ("关闭蓝牙", lambda: self._set_bluetooth_state(False), "#D32F2F"),
        ]

        for i, (text, func, color) in enumerate(quick_btns):
            btn = QPushButton(text)
            btn.setMinimumHeight(32)
            if color:
                btn.setStyleSheet(f"font-size: 11pt; color: {color};")
            else:
                btn.setStyleSheet("font-size: 11pt;")
            btn.clicked.connect(func)
            
            row = (i + 2) // 5
            col = (i + 2) % 5
            quick_layout.addWidget(btn, row, col)

        root.addWidget(quick_group)

        # ================= 2. 网络连通性测试 =================
        net_group = QGroupBox("网络连通性测试")
        net_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11pt; }")
        net_layout = QHBoxLayout(net_group)
        net_layout.setContentsMargins(10, 15, 10, 10)
        net_layout.setSpacing(8)

        net_layout.addWidget(QLabel("目标地址:"))
        self.ping_input = QLineEdit()
        self.ping_input.setPlaceholderText("输入 IP 或域名，例如: 8.8.8.8")
        self.ping_input.setText("baidu.com")
        self.ping_input.setStyleSheet("font-size: 11pt; padding: 4px;")
        net_layout.addWidget(self.ping_input, stretch=1)

        self.btn_ping = QPushButton("持续 Ping")
        self.btn_ping.setStyleSheet("background-color: #1565C0; color: white; font-weight: bold; font-size: 11pt;")
        self.btn_ping.setMinimumHeight(30)
        self.btn_ping.clicked.connect(self._run_ping)
        net_layout.addWidget(self.btn_ping)

        self.btn_ipconfig = QPushButton("查看本机 IP")
        self.btn_ipconfig.setStyleSheet("font-size: 11pt;")
        self.btn_ipconfig.setMinimumHeight(30)
        self.btn_ipconfig.clicked.connect(lambda: self._run_cmd_terminal("ipconfig"))
        net_layout.addWidget(self.btn_ipconfig)

        self.btn_flush_dns = QPushButton("刷新 DNS 缓存")
        self.btn_flush_dns.setStyleSheet("font-size: 11pt;")
        self.btn_flush_dns.setMinimumHeight(30)
        self.btn_flush_dns.clicked.connect(lambda: self._run_cmd_terminal("ipconfig /flushdns"))
        net_layout.addWidget(self.btn_flush_dns)

        root.addWidget(net_group)

        # ================= 3. 系统管理与电源选项 =================
        sys_group = QGroupBox("系统管理与电源选项")
        sys_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11pt; }")
        sys_layout = QGridLayout(sys_group)
        sys_layout.setSpacing(8)
        sys_layout.setContentsMargins(10, 15, 10, 10)

        sys_btns = [
            ("设备管理器", lambda: self._safe_open("devmgmt.msc")),
            ("磁盘管理", lambda: self._safe_open("diskmgmt.msc")),
            ("系统服务", lambda: self._safe_open("services.msc")),
            ("任务管理器", lambda: self._safe_open("taskmgr.exe")),
            ("环境变量", lambda: self._safe_open("rundll32.exe", "sysdm.cpl,EditEnvironmentVariables")),
            ("控制面板", lambda: self._safe_open("control.exe")),
            ("电源与睡眠设置", lambda: self._safe_open("ms-settings:powersleep")),
            ("高级电源选项", lambda: self._safe_open("powercfg.cpl")),
            ("系统设置主页", lambda: self._safe_open("ms-settings:")),
        ]

        for i, (text, func) in enumerate(sys_btns):
            btn = QPushButton(text)
            btn.setMinimumHeight(34)
            btn.setStyleSheet("font-size: 11pt;")
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(func)
            sys_layout.addWidget(btn, i // 3, i % 3)

        root.addWidget(sys_group)

        # ================= 4. 日常小工具 =================
        tool_group = QGroupBox("日常小工具")
        tool_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11pt; }")
        tool_layout = QGridLayout(tool_group)
        tool_layout.setSpacing(8)
        tool_layout.setContentsMargins(10, 15, 10, 10)

        tool_btns = [
            ("打开摄像头", self._open_camera, ""),
            ("关闭摄像头", self._close_camera, "#D32F2F"),
            ("立即锁屏", self._lock_screen, ""),
            ("计算器", lambda: subprocess.Popen("calc.exe"), ""),
            ("记事本", lambda: subprocess.Popen("notepad.exe"), ""),
            ("虚拟键盘", self._open_virtual_keyboard, ""),
        ]

        for i, (text, func, color) in enumerate(tool_btns):
            btn = QPushButton(text)
            btn.setMinimumHeight(34)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            if color:
                btn.setStyleSheet(f"font-size: 11pt; color: {color};")
            else:
                btn.setStyleSheet("font-size: 11pt;")
            btn.clicked.connect(func)
            tool_layout.addWidget(btn, i // 3, i % 3)

        root.addWidget(tool_group)

                # ================= 5. 开发者调试与排查工具 =================
        dev_group = QGroupBox("开发者调试与排查工具")
        dev_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11pt; }")
        dev_layout = QGridLayout(dev_group)
        dev_layout.setSpacing(8)
        dev_layout.setContentsMargins(10, 15, 10, 10)

        # 分为 3x4 的网格布局
        dev_btns = [
            ("网络端口占用 (netstat)", lambda: self._run_dev_cmd("netstat -ano")),
            ("路由追踪 (tracert)", lambda: self._run_dev_cmd("tracert -d baidu.com")),
            ("链路丢包分析 (pathping)", lambda: self._run_dev_cmd("pathping baidu.com")),
            ("当前用户自启动项", lambda: self._safe_open("shell:startup")),
            ("全局自启动项", lambda: self._safe_open("shell:common startup")),
            ("实时性能监视器", lambda: self._safe_open("perfmon.exe")),
            ("系统事件查看器", lambda: self._safe_open("eventvwr.exe")),
            ("本地 Hosts 文件", lambda: self._safe_open("notepad.exe", "C:\\Windows\\System32\\drivers\\etc\\hosts")),
            ("远程桌面连接", lambda: self._safe_open("mstsc.exe")),
            ("启用/关闭 Windows 功能", lambda: self._safe_open("optionalfeatures")),
            ("注册表编辑器", lambda: self._safe_open("regedit.exe")),
            ("系统资源概览 (msinfo32)", lambda: self._safe_open("msinfo32.exe")),
        ]

        for i, (text, func) in enumerate(dev_btns):
            btn = QPushButton(text)
            btn.setMinimumHeight(34)
            btn.setStyleSheet("font-size: 11pt;")
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(func)
            dev_layout.addWidget(btn, i // 4, i % 4) # 每行 4 个按钮

        root.addWidget(dev_group)
        root.addStretch()

    # ================= 软件偏好控制逻辑 =================

    def _toggle_dark_mode(self):
        """切换软件自身的暗黑/亮色模式"""
        current_cfg = get_app_config()
        new_mode = not current_cfg.get("dark_mode", False)
        
        # 应用主题
        ThemeManager.apply_theme(new_mode)
        
        # 动态更新按钮文字
        self.btn_theme_toggle.setText("切换亮色模式" if new_mode else "切换暗黑模式")

    def _toggle_autostart(self):
        """切换开机自启状态"""
        current_state = is_auto_start_enabled()
        new_state = not current_state
        
        if set_auto_start(new_state):
            # 动态更新按钮文字
            self.btn_autostart.setText("关闭开机自启" if new_state else "开启开机自启")
            status_str = "已开启" if new_state else "已关闭"
            QMessageBox.information(self, "开机自启", f"程序已{status_str}开机自启。")
        else:
            QMessageBox.warning(self, "错误", "设置开机自启失败，请检查权限。")

    # ================= 系统硬件控制逻辑 =================

    def _set_theme(self, is_dark: bool):
        val = 0 if is_dark else 1
        try:
            key_sys = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key_sys, "SystemUsesLightTheme", 0, winreg.REG_DWORD, val)
            winreg.CloseKey(key_sys)
            
            key_app = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key_app, "AppsUseLightTheme", 0, winreg.REG_DWORD, val)
            winreg.CloseKey(key_app)
            
            ctypes.windll.user32.SendMessageW(0xffff, 0x001A, 0, ctypes.c_wchar_p("ImmersiveColorSet"))
        except Exception as e:
            QMessageBox.warning(self, "切换失败", f"修改主题失败: {e}")

    def _adjust_volume(self, delta: float):
        if not HAS_PYCAW:
            QMessageBox.warning(self, "缺少依赖", "请先执行 pip install pycaw comtypes")
            return
        try:
            devices = AudioUtilities.GetSpeakers()
            volume = devices.EndpointVolume
            current_vol = volume.GetMasterVolumeLevelScalar()
            new_vol = max(0.0, min(1.0, current_vol + delta))
            volume.SetMasterVolumeLevelScalar(new_vol, None)
        except Exception as e:
            QMessageBox.warning(self, "音量调整失败", str(e))

    def _disconnect_wifi(self):
        try:
            subprocess.run("netsh wlan disconnect", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            QMessageBox.information(self, "提示", "已发送断开 Wi-Fi 指令。")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"执行失败: {e}")

    def _set_bluetooth_state(self, turn_on: bool):
        state = "On" if turn_on else "Off"
        action_name = "开启" if turn_on else "关闭"
        ps_script = f"""
        $ErrorActionPreference = 'Stop'
        try {{
            [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
            $radios = [Windows.Devices.Radios.Radio]::GetRadiosAsync().GetResults()
            $bt = $radios | Where-Object {{ $_.Kind -eq [Windows.Devices.Radios.RadioKind]::Bluetooth }}
            if ($bt) {{
                $bt.SetStateAsync([Windows.Devices.Radios.RadioState]::{state}).GetResults()
            }}
        }} catch {{
            Write-Error $_
        }}
        """
        try:
            result = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, check=True)
            if result.stderr.strip():
                raise Exception(result.stderr.strip())
            QMessageBox.information(self, "提示", f"已{action_name}蓝牙无线电。")
        except Exception:
            QMessageBox.warning(self, "操作受限", "开启/关闭蓝牙需要在 Windows 设置中允许应用控制无线电。")

    # ================= 网络功能 =================
    
    def _run_ping(self):
        host = self.ping_input.text().strip()
        if not host:
            return
        title = f"Ping - {host}"
        subprocess.Popen(f'wt.exe -w 0 new-tab --title "{title}" cmd /K "ping {host} -t"', shell=True)

    def _run_cmd_terminal(self, command: str):
        title = command.split()[0]
        subprocess.Popen(f'wt.exe -w 0 new-tab --title "{title}" cmd /K "{command}"', shell=True)

    # ================= 系统管理功能 =================

    def _open_devmgmt(self):
        os.startfile("devmgmt.msc")

    def _open_diskmgmt(self):
        os.startfile("diskmgmt.msc")

    def _open_services(self):
        os.startfile("services.msc")

    def _open_taskmgr(self):
        subprocess.Popen("taskmgr.exe")

    def _open_env_vars(self):
        subprocess.Popen("rundll32 sysdm.cpl,EditEnvironmentVariables")

    def _open_control_panel(self):
        subprocess.Popen("control.exe")

    # ================= 日常小工具 =================

    def _open_camera(self):
        os.startfile("microsoft.windows.camera:")

    def _close_camera(self):
        try:
            subprocess.run("taskkill /F /IM WindowsCamera.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            QMessageBox.information(self, "提示", "已发送关闭摄像头指令。")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"执行失败: {e}")

    def _lock_screen(self):
        ctypes.windll.user32.LockWorkStation()

    def _open_virtual_keyboard(self):
        """打开 Windows 自带虚拟键盘 (osk.exe 或 tabtip.exe)"""
        try:
            os.startfile("osk.exe")
        except Exception:
            try:
                tabtip_path = os.path.join(
                    os.environ.get("CommonProgramFiles", r"C:\Program Files\Common Files"),
                    "microsoft shared", "ink", "TabTip.exe"
                )
                if os.path.exists(tabtip_path):
                    subprocess.Popen([tabtip_path])
                else:
                    ctypes.windll.shell32.ShellExecuteW(None, "runas", "osk.exe", None, None, 1)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法启动虚拟键盘: {e}")

        # ================= 开发者调试工具支持 =================

    def _run_dev_cmd(self, command: str):
        """在新终端窗口中打开开发者调试命令"""
        if not command:
            return
        title = command.split()[0]
        try:
            # 优先尝试 Windows Terminal
            subprocess.Popen(f'wt.exe -w 0 new-tab --title "{title}" cmd /K "{command}"', shell=True)
        except FileNotFoundError:
            # 如果没有安装 Windows Terminal，降级为弹出一个独立 CMD 窗口
            subprocess.Popen(f'start "{title}" cmd /K "{command}"', shell=True)


    def _safe_open(self, target, *args):
        """安全地启动系统组件，防止系统缺少组件导致程序崩溃"""
        try:
            if args:
                # 如果传了额外参数（如 notepad.exe "C:\..."），必须使用 subprocess.Popen
                subprocess.Popen([target] + list(args))
            else:
                # 如果不带参数，统统交给 os.startfile，它能完美处理：
                # 1. shell:startup 等 URI 协议
                # 2. ms-settings: 等 Win10/11 协议
                # 3. 普通的 exe / msc / cpl
                os.startfile(target)
        except FileNotFoundError:
            # 如果 startfile 找不到，再尝试用 subprocess 兜底一次（针对环境变量缺失等情况）
            try:
                subprocess.Popen(target, shell=True)
            except Exception:
                QMessageBox.warning(
                    self, "组件不存在", 
                    f"未能在系统中找到该组件 ({target})。\n"
                    "您的 Windows 版本（如家庭版或精简版）可能未内置此功能。"
                )
        except Exception as e:
            QMessageBox.warning(self, "启动失败", f"启动 {target} 失败: {e}")