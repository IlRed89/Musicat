"""
DJ Mini-Player with Waveform Preview for Musicat.
Provides instant audio auditioning, waveform seeking, volume control, and key/BPM display.
"""

from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import QPoint, QRectF, QTime, QUrl, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..audio.waveform import WaveformGenerator


class WaveformCanvas(QWidget):
    """Custom painted waveform seekbar with interactive scrubbing."""

    seek_requested = Signal(float)  # Position fraction 0.0 -> 1.0

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._peaks: List[float] = []
        self._position_ratio: float = 0.0  # 0.0 to 1.0

    def set_peaks(self, peaks: List[float]) -> None:
        self._peaks = peaks
        self.update()

    def set_position_ratio(self, ratio: float) -> None:
        self._position_ratio = max(0.0, min(1.0, ratio))
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            ratio = max(0.0, min(1.0, event.position().x() / self.width()))
            self._position_ratio = ratio
            self.seek_requested.emit(ratio)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            ratio = max(0.0, min(1.0, event.position().x() / self.width()))
            self._position_ratio = ratio
            self.seek_requested.emit(ratio)
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        half_h = h / 2.0

        # Background
        painter.fillRect(0, 0, w, h, QColor("#14161d"))

        # Centerline
        painter.setPen(QPen(QColor("#252834"), 1))
        painter.drawLine(0, int(half_h), w, int(half_h))

        if not self._peaks:
            # Subtle placeholder bars
            painter.setPen(QColor("#2d3243"))
            for x in range(0, w, 6):
                bar_h = 10
                painter.drawLine(x, int(half_h - bar_h), x, int(half_h + bar_h))
            return

        num_peaks = len(self._peaks)
        bar_width = max(1.0, w / num_peaks)

        played_x = self._position_ratio * w

        for i, peak in enumerate(self._peaks):
            x = i * bar_width
            bar_height = max(2.0, peak * (half_h - 4))

            # Color: Cyan for played portion, Muted Slate for unplayed
            if x <= played_x:
                painter.setPen(QColor("#00d2ff"))
            else:
                painter.setPen(QColor("#43495d"))

            painter.drawLine(int(x), int(half_h - bar_height), int(x), int(half_h + bar_height))

        # Playhead cursor
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawLine(int(played_x), 0, int(played_x), h)


class MiniPlayerWidget(QFrame):
    """Compact DJ bottom bar player."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("MiniPlayer")
        self.setStyleSheet("QFrame#MiniPlayer { background-color: #171821; border-top: 1px solid #282b3a; }")

        # Multimedia Player
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.8)

        self.current_track: Optional[Dict] = None

        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(14, 8, 14, 8)
        main_layout.setSpacing(16)

        # Track Info Panel
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        self.title_label = QLabel("No track playing")
        self.title_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #ffffff;")

        self.artist_label = QLabel("Select a track to audition")
        self.artist_label.setStyleSheet("color: #8c92a4; font-size: 11px;")

        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(6)

        self.bpm_badge = QLabel("-- BPM")
        self.bpm_badge.setObjectName("BpmBadge")

        self.camelot_badge = QLabel("--")
        self.camelot_badge.setObjectName("CamelotBadge")

        badges_layout.addWidget(self.bpm_badge)
        badges_layout.addWidget(self.camelot_badge)
        badges_layout.addStretch()

        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.artist_label)
        info_layout.addLayout(badges_layout)
        info_layout.addStretch()

        # Playback Controls
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(8)

        self.btn_prev = QPushButton("⏮")
        self.btn_prev.setFixedSize(32, 32)

        self.btn_play = QPushButton("▶")
        self.btn_play.setObjectName("PrimaryButton")
        self.btn_play.setFixedSize(40, 40)
        self.btn_play.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))

        self.btn_stop = QPushButton("⏹")
        self.btn_stop.setFixedSize(32, 32)

        self.btn_next = QPushButton("⏭")
        self.btn_next.setFixedSize(32, 32)

        ctrl_layout.addWidget(self.btn_prev)
        ctrl_layout.addWidget(self.btn_play)
        ctrl_layout.addWidget(self.btn_stop)
        ctrl_layout.addWidget(self.btn_next)

        # Center: Waveform & Time Label
        waveform_container = QVBoxLayout()
        waveform_container.setSpacing(4)

        self.waveform_canvas = WaveformCanvas(self)

        time_layout = QHBoxLayout()
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #8c92a4; font-size: 11px; font-family: monospace;")
        time_layout.addStretch()
        time_layout.addWidget(self.time_label)

        waveform_container.addWidget(self.waveform_canvas)
        waveform_container.addLayout(time_layout)

        # Right: Volume Control
        vol_layout = QHBoxLayout()
        vol_layout.setSpacing(8)
        vol_icon = QLabel("🔊")
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(80)

        vol_layout.addWidget(vol_icon)
        vol_layout.addWidget(self.vol_slider)

        # Add everything to main layout
        main_layout.addLayout(info_layout, 2)
        main_layout.addLayout(ctrl_layout, 1)
        main_layout.addLayout(waveform_container, 5)
        main_layout.addLayout(vol_layout, 1)

    def _connect_signals(self) -> None:
        self.btn_play.clicked.connect(self.toggle_play_pause)
        self.btn_stop.clicked.connect(self.stop)
        self.waveform_canvas.seek_requested.connect(self._on_seek)
        self.vol_slider.valueChanged.connect(self._on_volume_changed)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)

    def load_track(self, track: Dict) -> None:
        """Loads and prepares track for playback."""
        self.current_track = track
        filepath = track.get("filepath", "")

        self.title_label.setText(track.get("title") or Path(filepath).stem)
        self.artist_label.setText(track.get("artist") or "Unknown Artist")

        bpm = track.get("bpm")
        self.bpm_badge.setText(f"{bpm:.1f} BPM" if bpm else "-- BPM")

        camelot = track.get("camelot_key") or track.get("musical_key") or "--"
        self.camelot_badge.setText(camelot)

        # Generate waveform peaks asynchronously or directly
        peaks = WaveformGenerator.generate_peaks(filepath, num_points=250)
        self.waveform_canvas.set_peaks(peaks)
        self.waveform_canvas.set_position_ratio(0.0)

        # Set media source
        self.player.setSource(QUrl.fromLocalFile(filepath))
        self.btn_play.setText("▶")

    def play(self) -> None:
        self.player.play()

    def pause(self) -> None:
        self.player.pause()

    def stop(self) -> None:
        self.player.stop()
        self.waveform_canvas.set_position_ratio(0.0)
        self._update_time_label(0, self.player.duration())

    def toggle_play_pause(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.pause()
        else:
            self.play()

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play.setText("⏸")
        else:
            self.btn_play.setText("▶")

    def _on_seek(self, ratio: float) -> None:
        duration = self.player.duration()
        if duration > 0:
            target_ms = int(ratio * duration)
            self.player.setPosition(target_ms)

    def _on_position_changed(self, position_ms: int) -> None:
        duration = self.player.duration()
        if duration > 0:
            ratio = position_ms / duration
            self.waveform_canvas.set_position_ratio(ratio)
        self._update_time_label(position_ms, duration)

    def _on_duration_changed(self, duration_ms: int) -> None:
        self._update_time_label(self.player.position(), duration_ms)

    def _update_time_label(self, pos_ms: int, dur_ms: int) -> None:
        cur_sec = int(pos_ms / 1000)
        tot_sec = int(dur_ms / 1000)
        c_m, c_s = divmod(cur_sec, 60)
        t_m, t_s = divmod(tot_sec, 60)
        self.time_label.setText(f"{c_m:02d}:{c_s:02d} / {t_m:02d}:{t_s:02d}")

    def _on_volume_changed(self, val: int) -> None:
        self.audio_output.setVolume(val / 100.0)
