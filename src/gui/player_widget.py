"""
DJ Mini-Player with Waveform Preview and libVLC Engine for Musicat.

Features:
- Universal codec playback powered by libVLC (with automatic QtMultimedia fallback).
- Interactive waveform scrubbing canvas.
- DJ Pitch / Playback Rate slider (+/- 8% tempo bend).
- Continuous looping and volume attenuation.
- Camelot key badge, BPM badge, and precise millisecond positioning.
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
from ..core.memory_cache import WaveformMemoryCache
from ..player.vlc_engine import VLCAudioPlayer
from .views import LoudnessMeterBar, QualityDiagnosisDialog


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
        """Sets downsampled audio peak envelope points."""
        self._peaks = peaks
        self.update()

    def set_position_ratio(self, ratio: float) -> None:
        """Updates playback cursor position [0.0 - 1.0]."""
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
    """Compact DJ bottom bar player with VLC audio backend and pitch bending."""

    position_tick = Signal(int, int)
    track_normalized = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("MiniPlayer")
        self.setStyleSheet("QFrame#MiniPlayer { background-color: #171821; border-top: 1px solid #282b3a; }")

        # 1. Primary VLC Audio Engine
        self.vlc_player = VLCAudioPlayer()

        # 2. Fallback QtMultimedia Player
        self.qt_player = QMediaPlayer(self)
        self.qt_audio = QAudioOutput(self)
        self.qt_player.setAudioOutput(self.qt_audio)
        self.qt_audio.setVolume(0.8)

        self.current_track: Optional[Dict] = None
        self._is_using_vlc = self.vlc_player.is_available()

        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(14, 8, 14, 8)
        main_layout.setSpacing(14)

        # Left: Track Info Panel
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

        self.engine_badge = QLabel("VLC Engine" if self._is_using_vlc else "Qt Audio")
        self.engine_badge.setStyleSheet("color: #00d2ff; font-size: 10px; border: 1px solid #005a73; border-radius: 3px; padding: 1px 4px;")

        badges_layout.addWidget(self.bpm_badge)
        badges_layout.addWidget(self.camelot_badge)
        badges_layout.addWidget(self.engine_badge)
        badges_layout.addStretch()

        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.artist_label)
        info_layout.addLayout(badges_layout)
        info_layout.addStretch()

        # Center Left: Playback Controls
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(6)

        self.btn_play = QPushButton("▶")
        self.btn_play.setObjectName("PrimaryButton")
        self.btn_play.setFixedSize(38, 38)
        self.btn_play.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))

        self.btn_stop = QPushButton("⏹")
        self.btn_stop.setFixedSize(32, 32)

        self.btn_loop = QPushButton("🔁")
        self.btn_loop.setCheckable(True)
        self.btn_loop.setFixedSize(32, 32)
        self.btn_loop.setToolTip("Toggle Continuous Looping")

        ctrl_layout.addWidget(self.btn_play)
        ctrl_layout.addWidget(self.btn_stop)
        ctrl_layout.addWidget(self.btn_loop)

        # Center: Waveform, VU Meter & Time Label
        waveform_container = QVBoxLayout()
        waveform_container.setSpacing(3)

        self.waveform_canvas = WaveformCanvas(self)

        meter_layout = QHBoxLayout()
        meter_layout.setSpacing(6)

        self.meter_bar = LoudnessMeterBar(self)
        self.meter_bar.setFixedHeight(16)
        self.meter_bar.setMinimumWidth(160)
        self.meter_bar.setToolTip("Livello Sonoro Integrato (LUFS) e True Peak (dBTP)")

        self.btn_normalize = QPushButton("⚡ Correggi")
        self.btn_normalize.setToolTip("Diagnosi e Normalizzazione Qualità Audio (LUFS / Clipping)")
        self.btn_normalize.setStyleSheet("""
            QPushButton {
                background-color: #1a2234;
                border: 1px solid #0284c7;
                color: #38bdf8;
                font-weight: bold;
                font-size: 10px;
                padding: 1px 7px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)
        self.btn_normalize.clicked.connect(self._on_open_quality_dialog)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #8c92a4; font-size: 11px; font-family: monospace;")

        meter_layout.addWidget(self.meter_bar, 1)
        meter_layout.addWidget(self.btn_normalize)
        meter_layout.addStretch()
        meter_layout.addWidget(self.time_label)

        waveform_container.addWidget(self.waveform_canvas)
        waveform_container.addLayout(meter_layout)

        # Right: DJ Pitch / Rate Control Slider (+/- 8%)
        pitch_box = QVBoxLayout()
        pitch_box.setSpacing(2)

        pitch_header = QHBoxLayout()
        self.lbl_pitch = QLabel("Pitch: 0.0%")
        self.lbl_pitch.setStyleSheet("color: #c77dff; font-size: 10px; font-weight: bold;")
        self.btn_reset_pitch = QPushButton("0")
        self.btn_reset_pitch.setFixedSize(16, 16)
        self.btn_reset_pitch.setToolTip("Reset Pitch to 0.0%")
        self.btn_reset_pitch.clicked.connect(self._reset_pitch)

        pitch_header.addWidget(self.lbl_pitch)
        pitch_header.addWidget(self.btn_reset_pitch)

        self.slider_pitch = QSlider(Qt.Orientation.Horizontal)
        self.slider_pitch.setRange(-80, 80)  # -8.0% to +8.0%
        self.slider_pitch.setValue(0)
        self.slider_pitch.setFixedWidth(85)
        self.slider_pitch.setToolTip("DJ Tempo / Pitch Adjustment (+/- 8%)")

        pitch_box.addLayout(pitch_header)
        pitch_box.addWidget(self.slider_pitch)

        # Far Right: Volume Control
        vol_layout = QHBoxLayout()
        vol_layout.setSpacing(6)
        vol_icon = QLabel("🔊")
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(70)

        vol_layout.addWidget(vol_icon)
        vol_layout.addWidget(self.vol_slider)

        # Assemble main layout
        main_layout.addLayout(info_layout, 2)
        main_layout.addLayout(ctrl_layout, 1)
        main_layout.addLayout(waveform_container, 4)
        main_layout.addLayout(pitch_box, 1)
        main_layout.addLayout(vol_layout, 1)

    def _connect_signals(self) -> None:
        self.btn_play.clicked.connect(self.toggle_play_pause)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_loop.toggled.connect(self._on_loop_toggled)
        self.waveform_canvas.seek_requested.connect(self._on_seek)
        self.vol_slider.valueChanged.connect(self._on_volume_changed)
        self.slider_pitch.valueChanged.connect(self._on_pitch_changed)

        # Connect VLC callbacks
        self.position_tick.connect(self._on_vlc_position_update)
        if self._is_using_vlc:
            self.vlc_player.set_callbacks(
                time_cb=lambda c, t: self.position_tick.emit(c, t),
                state_cb=self._on_vlc_state_changed,
            )
        else:
            self.qt_player.positionChanged.connect(self._on_qt_position_changed)
            self.qt_player.durationChanged.connect(self._on_qt_duration_changed)

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

        # Update Audio Quality & Loudness Meter
        lufs = track.get("lufs")
        tp = track.get("true_peak")
        status = track.get("audio_status") or "OK"
        if lufs is not None and tp is not None:
            self.meter_bar.set_metrics(float(lufs), float(tp), str(status))
        else:
            self.meter_bar.set_metrics(-70.0, -100.0, "OK")

        # Retrieve or generate waveform peak envelope
        waveform_cache = WaveformMemoryCache.get_instance()
        peaks = waveform_cache.get_waveform(filepath)
        if not peaks:
            raw_peaks = track.get("waveform_peaks")
            if isinstance(raw_peaks, str) and raw_peaks:
                peaks = WaveformGenerator.deserialize_peaks(raw_peaks)
            elif isinstance(raw_peaks, list) and raw_peaks:
                peaks = raw_peaks

        if not peaks:
            peaks = WaveformGenerator.generate_peaks(filepath, num_points=250)

        if peaks:
            waveform_cache.put_waveform(filepath, peaks)

        self.waveform_canvas.set_peaks(peaks or [])
        self.waveform_canvas.set_position_ratio(0.0)

        # Load media into active audio engine
        if self._is_using_vlc:
            self.vlc_player.load(filepath)
        else:
            self.qt_player.setSource(QUrl.fromLocalFile(filepath))

        self.btn_play.setText("▶")

    def play(self) -> None:
        if self._is_using_vlc:
            self.vlc_player.play()
        else:
            self.qt_player.play()
        self.btn_play.setText("⏸")

    def pause(self) -> None:
        if self._is_using_vlc:
            self.vlc_player.pause()
        else:
            self.qt_player.pause()
        self.btn_play.setText("▶")

    def stop(self) -> None:
        if self._is_using_vlc:
            self.vlc_player.stop()
        else:
            self.qt_player.stop()
        self.waveform_canvas.set_position_ratio(0.0)
        self.btn_play.setText("▶")

    def toggle_play_pause(self) -> None:
        if self._is_using_vlc:
            if self.vlc_player.is_playing():
                self.pause()
            else:
                self.play()
        else:
            if self.qt_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.pause()
            else:
                self.play()

    def _on_seek(self, ratio: float) -> None:
        if self._is_using_vlc:
            self.vlc_player.seek_fraction(ratio)
        else:
            dur = self.qt_player.duration()
            if dur > 0:
                self.qt_player.setPosition(int(ratio * dur))

    def _on_loop_toggled(self, checked: bool) -> None:
        if self._is_using_vlc:
            self.vlc_player.set_loop(checked)

    def _on_volume_changed(self, val: int) -> None:
        if self._is_using_vlc:
            self.vlc_player.set_volume(val)
        else:
            self.qt_audio.setVolume(val / 100.0)

    def _on_pitch_changed(self, val: int) -> None:
        percent = val / 10.0  # e.g. +2.4%
        self.lbl_pitch.setText(f"Pitch: {percent:+.1f}%")
        multiplier = 1.0 + (percent / 100.0)
        if self._is_using_vlc:
            self.vlc_player.set_pitch_rate(multiplier)

    def _reset_pitch(self) -> None:
        self.slider_pitch.setValue(0)

    def _on_vlc_position_update(self, cur_ms: int, tot_ms: int) -> None:
        if tot_ms > 0:
            ratio = cur_ms / tot_ms
            self.waveform_canvas.set_position_ratio(ratio)
        self._update_time_label(cur_ms, tot_ms)

    def _on_vlc_state_changed(self, state: str) -> None:
        if state == "playing":
            self.btn_play.setText("⏸")
        else:
            self.btn_play.setText("▶")

    def _on_qt_position_changed(self, pos_ms: int) -> None:
        dur = self.qt_player.duration()
        if dur > 0:
            self.waveform_canvas.set_position_ratio(pos_ms / dur)
        self._update_time_label(pos_ms, dur)

    def _on_qt_duration_changed(self, dur_ms: int) -> None:
        self._update_time_label(self.qt_player.position(), dur_ms)

    def _update_time_label(self, pos_ms: int, dur_ms: int) -> None:
        c_m, c_s = divmod(int(pos_ms / 1000), 60)
        t_m, t_s = divmod(int(dur_ms / 1000), 60)
        self.time_label.setText(f"{c_m:02d}:{c_s:02d} / {t_m:02d}:{t_s:02d}")

    def _on_open_quality_dialog(self) -> None:
        """Opens audio quality and loudness normalization modal for current track."""
        if not self.current_track:
            return
        fp = self.current_track.get("filepath", "")
        if not fp or not Path(fp).exists():
            return

        parent_db = getattr(self.parent(), "db", None) if self.parent() else None
        dlg = QualityDiagnosisDialog(fp, db=parent_db, parent=self)
        dlg.normalization_applied.connect(self._on_track_normalized)
        dlg.exec()

    def _on_track_normalized(self, normalized_path: str) -> None:
        """Handles post-normalization refresh and notification."""
        self.track_normalized.emit(normalized_path)
        if self.parent() and hasattr(self.parent(), "_refresh_library"):
            self.parent()._refresh_library()
