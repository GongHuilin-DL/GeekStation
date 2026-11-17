from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

class BasePlayerAdapter(QObject):
    # 统一定义所有引擎都必须向外发出的信号
    state_changed = Signal(str)      # "playing", "paused", "stopped"
    position_changed = Signal(int)   # 当前播放进度 (毫秒)
    duration_changed = Signal(int)   # 视频总时长 (毫秒)

    def play(self, url: str):
        raise NotImplementedError

    def pause(self):
        raise NotImplementedError

    def resume(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def seek(self, position_ms: int):
        raise NotImplementedError

    def set_volume(self, volume: int):
        raise NotImplementedError

    def get_widget(self) -> QWidget:
        """获取用于在 UI 中显示的渲染控件"""
        raise NotImplementedError

    def get_current_url(self) -> str:
        raise NotImplementedError

    def is_playing(self) -> bool:
        raise NotImplementedError