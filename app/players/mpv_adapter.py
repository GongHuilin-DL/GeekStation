import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout
from app.players.base_adapter import BasePlayerAdapter

try:
    import mpv
    HAS_MPV = True
except ImportError:
    HAS_MPV = False

class MpvPlayerAdapter(BasePlayerAdapter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_url = ""
        self._is_playing = False
        
        # 创建用于承载 mpv 渲染的原生窗口
        self._container = QWidget(parent)
        self._container.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors)
        self._container.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self._container.setStyleSheet("background-color: black;")
        
        if not HAS_MPV:
            self._mpv = None
            return

        # 初始化 mpv，关键参数 wid 指向容器窗口句柄
        self._mpv = mpv.MPV(
            wid=str(int(self._container.winId())),
            vo='gpu',
            ytdl=False,
            input_default_bindings=False,
            input_vo_keyboard=False
        )
        
        # 监听 mpv 属性变化，并转为 Qt 信号
        self._mpv.observe_property('pause', self._on_pause_changed)
        self._mpv.observe_property('time-pos', self._on_pos_changed)
        self._mpv.observe_property('duration', self._on_dur_changed)
        self._mpv.observe_property('eof-reached', self._on_eof_reached)

    def _on_pause_changed(self, name, value):
        if value is None: return
        self._is_playing = not value
        self.state_changed.emit("paused" if value else "playing")

    def _on_pos_changed(self, name, value):
        if value is not None:
            self.position_changed.emit(int(value * 1000))

    def _on_dur_changed(self, name, value):
        if value is not None:
            self.duration_changed.emit(int(value * 1000))

    def _on_eof_reached(self, name, value):
        if value is True: # 播放结束，自动连播
            if hasattr(self.parent(), "_play_next"):
                self.parent()._play_next()

    def play(self, url: str):
        if not self._mpv: return
        self._current_url = url
        self._mpv.play(url)

    def pause(self):
        if self._mpv: self._mpv.pause = True

    def resume(self):
        if self._mpv: self._mpv.pause = False

    def stop(self):
        if self._mpv: self._mpv.stop()

    def seek(self, position_ms: int):
        if self._mpv:
            try:
                # 确保 seek 的位置不小于 0，且转换为浮点秒数
                self._mpv.command("seek", max(0, position_ms) / 1000.0, "absolute")
            except SystemError as e:
                # 对于直播流（如 RTMP），强行 seek 会触发底层 FFmpeg 报错，在这里安全忽略
                print(f"[mpv_adapter] 当前流不支持 Seek（可能是直播流）: {e}")
            except Exception as e:
                print(f"[mpv_adapter] Seek 异常: {e}")

    def set_volume(self, volume: int):
        if self._mpv: self._mpv.volume = volume

    def get_widget(self) -> QWidget:
        return self._container

    def get_current_url(self) -> str:
        return self._current_url

    def is_playing(self) -> bool:
        return self._is_playing