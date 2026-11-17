from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from app.players.base_adapter import BasePlayerAdapter

class VideoSurface(QGraphicsView):
    """你之前写的完美支持拖拽的渲染画布"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_tab = parent
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        self.video_item = QGraphicsVideoItem()
        self.scene.addItem(self.video_item)
        
        self.setStyleSheet("background-color: black; border: none;")
        self.setAcceptDrops(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.video_item.setSize(self.viewport().size())
        self.scene.setSceneRect(0, 0, self.viewport().width(), self.viewport().height())

    def mouseDoubleClickEvent(self, event):
        if self.main_tab:
            self.main_tab._toggle_fullscreen()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls() and self.main_tab:
            self.main_tab._handle_video_drop(event)
            event.acceptProposedAction()


class QtPlayerAdapter(BasePlayerAdapter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        
        self.surface = VideoSurface(parent)
        self.player.setVideoOutput(self.surface.video_item)
        
        self._current_url = ""
        self._is_playing = False

        # 绑定原生信号到统一信号
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.positionChanged.connect(self.position_changed.emit)
        self.player.durationChanged.connect(self.duration_changed.emit)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._is_playing = True
            self.state_changed.emit("playing")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self._is_playing = False
            self.state_changed.emit("paused")
        else:
            self._is_playing = False
            self.state_changed.emit("stopped")

    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if hasattr(self.parent(), "_play_next"):
                self.parent()._play_next()

    def play(self, url: str):
        self._current_url = url
        self.player.setSource(QUrl.fromLocalFile(url) if not url.startswith(("http", "rtmp", "rtsp")) else QUrl(url))
        self.player.play()

    def pause(self):
        self.player.pause()

    def resume(self):
        self.player.play()

    def stop(self):
        self.player.stop()

    def seek(self, position_ms: int):
        self.player.setPosition(position_ms)

    def set_volume(self, volume: int):
        self.audio_output.setVolume(volume / 100.0)

    def get_widget(self):
        return self.surface

    def get_current_url(self) -> str:
        return self._current_url

    def is_playing(self) -> bool:
        return self._is_playing