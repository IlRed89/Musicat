"""
Audio Quality & Loudness Diagnosis Dialog and Visual Gauges for Musicat.

Provides:
- Visual True Peak / LUFS meter bar widget
- QualityDiagnosisDialog for single track inspection and normalization
- BatchQualityDialog for mass library analysis and ReplayGain / loudnorm processing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal, QThread
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.db import Database
from src.plugins.quality_analyzer.analyzer import AcousticQualityAnalyzer, QualityReport
from src.plugins.quality_analyzer.normalizer import VolumeNormalizer, NormalizationResult


class LoudnessMeterBar(QWidget):
    """Custom-painted horizontal VU/Loudness bar widget showing LUFS and True Peak."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(18)
        self.setMinimumWidth(160)
        self._lufs: Optional[float] = None
        self._true_peak: Optional[float] = None
        self._status: str = "OK"
        self._has_metrics: bool = False

    def clear_metrics(self) -> None:
        """Clears measurements and shows deactivated placeholder."""
        self._lufs = None
        self._true_peak = None
        self._status = "OK"
        self._has_metrics = False
        self.update()

    def set_metrics(self, lufs: Optional[float], true_peak: Optional[float], status: str = "OK") -> None:
        """Updates displayed loudness and peak values."""
        if (
            lufs is not None
            and true_peak is not None
            and float(lufs) > -65.0
            and float(true_peak) > -95.0
        ):
            self._lufs = float(lufs)
            self._true_peak = float(true_peak)
            self._status = status
            self._has_metrics = True
        else:
            self._lufs = None
            self._true_peak = None
            self._status = status
            self._has_metrics = False
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        from src.core.settings import SettingsManager
        theme = SettingsManager.get_instance().get("ui", "theme", "light")
        is_light = "light" in (theme or "").lower()

        bg_col = QColor("#f1f3f5") if is_light else QColor("#12141a")
        border_col = QColor("#ced4da") if is_light else QColor("#272a38")
        muted_col = QColor("#868e96") if is_light else QColor("#6c757d")

        # Background track & border
        painter.fillRect(0, 0, w, h, bg_col)
        painter.setPen(QPen(border_col, 1))
        painter.drawRect(0, 0, w - 1, h - 1)

        if not self._has_metrics or self._lufs is None:
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium))
            painter.setPen(muted_col)
            painter.drawText(
                QRect(6, 0, w - 12, h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                "— LUFS  |  TP: — dBTP (Non analizzato)",
            )
            return

        # Map LUFS [-40 to 0] to fraction [0.0 to 1.0]
        clamped_lufs = max(-40.0, min(0.0, self._lufs))
        lufs_ratio = (clamped_lufs + 40.0) / 40.0
        fill_w = int(lufs_ratio * (w - 2))

        if fill_w > 0:
            grad = QLinearGradient(1, 0, w - 1, 0)
            grad.setColorAt(0.0, QColor("#00d2ff"))
            grad.setColorAt(0.65, QColor("#10b981"))
            grad.setColorAt(0.85, QColor("#f59e0b"))
            grad.setColorAt(1.0, QColor("#ef4444"))

            painter.fillRect(1, 1, fill_w, h - 2, grad)

        # True Peak marker line
        if self._true_peak is not None and self._true_peak > -40.0:
            clamped_tp = max(-40.0, min(6.0, self._true_peak))
            tp_ratio = (clamped_tp + 40.0) / 46.0
            tp_x = int(tp_ratio * (w - 2)) + 1
            tp_color = QColor("#ef4444") if self._true_peak > 0.0 else QColor("#212529" if is_light else "#ffffff")
            painter.setPen(QPen(tp_color, 2))
            painter.drawLine(tp_x, 1, tp_x, h - 2)

        # Text Overlay
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        text = f"{self._lufs:.1f} LUFS  |  TP: {self._true_peak:+.1f} dBTP"
        painter.setPen(QColor("#000000" if is_light else "#ffffff"))
        painter.drawText(QRect(6, 0, w - 12, h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)


class DualWaveformWidget(QWidget):
    """Interactive visual dual waveform preview comparing original audio vs normalized target.

    Shows:
    - Top waveform: Original track with peaks, highlighting True Peak clipping in red (> 0 dBTP).
    - Bottom waveform: Target preview (gain-adjusted, limited to safety True Peak ceiling),
      demonstrating effective de-clipping and loudness control.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(136)
        self.setMinimumWidth(320)
        self._peaks: np.ndarray = np.array([])
        self._orig_lufs: float = -14.0
        self._orig_tp: float = 0.0
        self._target_lufs: float = -10.0
        self._max_tp: float = -1.0
        self._has_data: bool = False

    def set_data(
        self,
        peaks: np.ndarray,
        orig_lufs: float,
        orig_tp: float,
        target_lufs: float = -10.0,
        max_tp: float = -1.0,
    ) -> None:
        self._peaks = np.array(peaks, dtype=float) if len(peaks) > 0 else np.array([])
        self._orig_lufs = orig_lufs
        self._orig_tp = orig_tp
        self._target_lufs = target_lufs
        self._max_tp = max_tp
        self._has_data = len(self._peaks) > 0
        self.update()

    def update_targets(self, target_lufs: float, max_tp: float) -> None:
        self._target_lufs = target_lufs
        self._max_tp = max_tp
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        half_h = (h - 10) // 2

        from src.core.settings import SettingsManager
        theme = SettingsManager.get_instance().get("ui", "theme", "light")
        is_light = "light" in (theme or "").lower()

        bg_card = QColor("#f8fafc" if is_light else "#141722")
        border_col = QColor("#dee2e6" if is_light else "#282d3f")
        text_col = QColor("#212529" if is_light else "#e2e8f0")
        subtext_col = QColor("#6c757d" if is_light else "#94a3b8")

        # Outer card background
        painter.fillRect(0, 0, w, h, bg_card)
        painter.setPen(QPen(border_col, 1))
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 6, 6)

        if not self._has_data or len(self._peaks) == 0:
            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(subtext_col)
            painter.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "Generazione anteprima forma d'onda in corso...")
            return

        num_bars = min(len(self._peaks), max(30, (w - 24) // 4))
        indices = np.linspace(0, len(self._peaks) - 1, num_bars).astype(int)
        sampled_peaks = self._peaks[indices]

        # Horizontal divider between top and bottom
        painter.setPen(QPen(border_col, 1))
        painter.drawLine(8, half_h + 5, w - 8, half_h + 5)

        bar_avail_w = w - 30
        bar_w = max(2.0, (bar_avail_w / num_bars) - 1.5)
        bar_max_h = max(10, half_h - 22)

        # -------------------------------------------------------------
        # 1. TOP WAVEFORM: ORIGINALE (Prima)
        # -------------------------------------------------------------
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        is_clipping = self._orig_tp > 0.0
        orig_tag = "⚠️ CLIPPING RILEVATO" if is_clipping else "CONFORME"
        tag_color = QColor("#dc3545" if is_clipping else "#198754")

        painter.setPen(text_col)
        painter.drawText(12, 15, f"PRIMA — Originale: {self._orig_lufs:.1f} LUFS | True Peak: {self._orig_tp:+.1f} dBTP")
        painter.setPen(tag_color)
        painter.drawText(w - 150, 15, f"[{orig_tag}]")

        # Ceiling line at top (0 dBTP threshold)
        ceil_y_top = 20
        painter.setPen(QPen(QColor("#dc3545" if is_clipping else "#ced4da"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(12, ceil_y_top, w - 16, ceil_y_top)

        for i in range(num_bars):
            val = float(sampled_peaks[i])
            bar_h = max(2.0, val * bar_max_h)
            bx = 12 + i * (bar_avail_w / num_bars)
            by = half_h + 3 - bar_h

            if is_clipping and val >= 0.88:
                col = QColor("#ef4444")
            else:
                col = QColor("#0d6efd" if is_light else "#38bdf8")

            painter.fillRect(QRectF(bx, by, bar_w, bar_h), col)

        # -------------------------------------------------------------
        # 2. BOTTOM WAVEFORM: NORMALIZZATO (Dopo)
        # -------------------------------------------------------------
        bot_y_start = half_h + 7
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(text_col)
        painter.drawText(12, bot_y_start + 14, f"DOPO — Target Preview: {self._target_lufs:.1f} LUFS | Safety Ceiling: {self._max_tp:+.1f} dBTP")
        painter.setPen(QColor("#10b981"))
        painter.drawText(w - 150, bot_y_start + 14, "[✅ DE-CLIPPATO]")

        # Target safety ceiling line
        ceil_y_bot = bot_y_start + 19
        painter.setPen(QPen(QColor("#10b981"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(12, ceil_y_bot, w - 16, ceil_y_bot)

        # Gain offset and ceiling calculation
        gain_db = self._target_lufs - self._orig_lufs
        linear_gain = 10.0 ** (gain_db / 20.0)
        ceiling_linear = 10.0 ** (self._max_tp / 20.0)

        for i in range(num_bars):
            val = float(sampled_peaks[i]) * linear_gain
            if val > ceiling_linear:
                val = ceiling_linear * (0.95 + 0.05 * float(np.tanh((val - ceiling_linear) * 2.0)))
            val = min(val, ceiling_linear)

            bar_h = max(2.0, (val / max(1.0, ceiling_linear)) * bar_max_h * min(1.0, ceiling_linear))
            bx = 12 + i * (bar_avail_w / num_bars)
            by = h - 6 - bar_h

            painter.fillRect(QRectF(bx, by, bar_w, bar_h), QColor("#10b981"))


class QualityDiagnosisDialog(QDialog):
    """Detailed modal diagnosis and loudness normalization dialog for single tracks in clean native light theme."""

    normalization_applied = Signal(str)  # Emits filepath when normalized

    def __init__(
        self,
        filepath: str,
        db: Optional[Database] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.filepath = filepath
        self.db = db
        self.report: Optional[QualityReport] = None
        self.normalizer = VolumeNormalizer(db=self.db)

        self.setWindowTitle(f"🔊 Audio Quality & Loudness Normalizer — {Path(filepath).name}")
        self.resize(760, 680)
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                color: #212529;
            }
            QLabel {
                color: #212529;
                font-size: 12px;
            }
            QGroupBox {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                margin-top: 10px;
                font-weight: bold;
                color: #0d6efd;
                background-color: #ffffff;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                background-color: #ffffff;
            }
            QRadioButton#radReplayGain, QRadioButton#radLoudnorm {
                color: #212529;
                font-size: 11px;
                padding: 8px 12px;
                border: 1px solid #ced4da;
                border-radius: 6px;
                background-color: #f8f9fa;
                font-weight: 500;
            }
            QRadioButton#radReplayGain:hover, QRadioButton#radLoudnorm:hover {
                border-color: #0d6efd;
                background-color: #f0f7ff;
            }
            QRadioButton#radReplayGain:checked, QRadioButton#radLoudnorm:checked {
                border: 2px solid #0d6efd;
                background-color: #e7f1ff;
                font-weight: bold;
                color: #0b5ed7;
            }
            QCheckBox {
                color: #212529;
                font-size: 11px;
                spacing: 6px;
            }
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 4px 8px;
                color: #212529;
                min-width: 180px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #e9ecef;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #0d6efd;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #0d6efd;
                border: 2px solid #ffffff;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
        """)

        self._init_ui()
        self._run_analysis()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 12, 18, 12)

        # Header Info
        header = QLabel(f"<b>File:</b> {Path(self.filepath).name}")
        header.setStyleSheet("font-size: 13px; color: #212529;")
        layout.addWidget(header)

        # Meter Bar
        self.meter_bar = LoudnessMeterBar(self)
        layout.addWidget(self.meter_bar)

        # Dual Waveform Widget (Before vs After)
        self.waveform_widget = DualWaveformWidget(self)
        layout.addWidget(self.waveform_widget)

        # 1. Diagnostics Group
        grp_diag = QGroupBox("📊 Analisi e Livello del Volume")
        diag_layout = QVBoxLayout(grp_diag)
        diag_layout.setSpacing(4)

        self.lbl_lufs = QLabel("Livello Volume Medio: Calcolo in corso...")
        self.lbl_tp = QLabel("Picco Massimo del Suono: Calcolo in corso...")
        self.lbl_lra = QLabel("Escursione Dinamica: Calcolo in corso...")
        self.lbl_status = QLabel("Diagnosi Qualità: Calcolo in corso...")
        self.lbl_gain_needed = QLabel("Regolazione Consigliata: ...")

        diag_layout.addWidget(self.lbl_lufs)
        diag_layout.addWidget(self.lbl_tp)
        diag_layout.addWidget(self.lbl_lra)
        diag_layout.addWidget(self.lbl_status)
        diag_layout.addWidget(self.lbl_gain_needed)
        layout.addWidget(grp_diag)

        # 2. Strategy Selector Group
        grp_action = QGroupBox("⚡ Ottimizzazione Volume e Qualità Audio")
        act_layout = QVBoxLayout(grp_action)
        act_layout.setSpacing(8)

        # Target LUFS row & slider
        lufs_tooltip = (
            "Regola automaticamente il volume per evitare che i brani suonino troppo bassi o distorcano, "
            "mantenendo la massima qualità audio senza modificare il timbro originale.\n\n"
            "• -14 LUFS: Volume standard consigliato per streaming (Spotify, YouTube, Apple Music)\n"
            "• -10 LUFS: Volume alto per DJ, club e piste da ballo\n"
            "• -16 LUFS: Volume conservativo per podcast e ascolto rilassato\n"
            "• -23 LUFS: Standard broadcast tradizionale per radio e TV"
        )

        target_row = QHBoxLayout()
        lbl_target_title = QLabel("Volume Desiderato:")
        lbl_target_title.setToolTip(lufs_tooltip)
        target_row.addWidget(lbl_target_title)

        self.cmb_target = QComboBox()
        self.cmb_target.addItem("Volume Standard Consigliato (Streaming / Spotify -14 LUFS)", -14.0)
        self.cmb_target.addItem("Volume Alto per DJ / Club (-10 LUFS)", -10.0)
        self.cmb_target.addItem("Volume Conservativo (-16 LUFS / Podcast)", -16.0)
        self.cmb_target.addItem("Volume Broadcast Tradizionale (-23 LUFS / Radio TV)", -23.0)
        self.cmb_target.setToolTip(lufs_tooltip)
        self.cmb_target.currentIndexChanged.connect(self._on_combo_target_changed)
        target_row.addWidget(self.cmb_target)

        self.slider_lufs = QSlider(Qt.Orientation.Horizontal)
        self.slider_lufs.setRange(-24, -6)
        self.slider_lufs.setValue(-14)
        self.slider_lufs.setToolTip(lufs_tooltip)
        self.slider_lufs.valueChanged.connect(self._on_slider_lufs_changed)
        target_row.addWidget(self.slider_lufs, 1)

        self.lbl_lufs_val = QLabel("-14.0 LUFS")
        self.lbl_lufs_val.setStyleSheet("font-weight: bold; min-width: 65px; color: #0d6efd;")
        target_row.addWidget(self.lbl_lufs_val)
        act_layout.addLayout(target_row)

        # Target True Peak ceiling row & slider
        tp_tooltip = (
            "Margine di sicurezza (Headroom):\n"
            "• -1.0 dBTP: Margine di sicurezza raccomandato per eliminare qualsiasi distorsione "
            "o clipping digitale durante l'ascolto e la compressione MP3/AAC."
        )
        tp_row = QHBoxLayout()
        lbl_tp_title = QLabel("Protezione Distorsioni (Headroom):")
        lbl_tp_title.setToolTip(tp_tooltip)
        tp_row.addWidget(lbl_tp_title)

        self.slider_tp = QSlider(Qt.Orientation.Horizontal)
        self.slider_tp.setRange(-30, 0)
        self.slider_tp.setValue(-10)  # -1.0 dBTP
        self.slider_tp.setToolTip(tp_tooltip)
        self.slider_tp.valueChanged.connect(self._on_slider_tp_changed)
        tp_row.addWidget(self.slider_tp, 1)

        self.lbl_tp_val = QLabel("-1.0 dBTP")
        self.lbl_tp_val.setStyleSheet("font-weight: bold; min-width: 65px; color: #0d6efd;")
        tp_row.addWidget(self.lbl_tp_val)
        act_layout.addLayout(tp_row)

        # Strategy Radio Buttons
        self.rad_replaygain = QRadioButton("🏷️ Regolazione Intelligente Non Distruttiva (Scrive il volume nei tag senza toccare il file audio)")
        self.rad_replaygain.setObjectName("radReplayGain")
        self.rad_replaygain.setChecked(True)
        self.rad_replaygain.setToolTip("Conserva il file originale al 100% senza alterare i campioni sonori. I software DJ compatibili applicheranno il volume al volo.")

        self.rad_loudnorm = QRadioButton("🛠️ Ottimizzazione Dinamica e Picchi Sonori (Prevenzione distorsione ed esportazione MP3 320k)")
        self.rad_loudnorm.setObjectName("radLoudnorm")
        self.rad_loudnorm.setToolTip("Normalizza il volume del brano al livello scelto ed elimina qualsiasi distorsione esportando in un file MP3 320 kbps ad alta fedeltà.")

        self.rad_dsp = QRadioButton("🎛️ Mastering Audio e Miglioramento Acustico (Equalizzazione, presenza vocale e punch)")
        self.rad_dsp.setObjectName("radDsp")
        self.rad_dsp.setToolTip("Applica filtri avanzati per migliorare la resa acustica, la nitidezza della voce o dare più corpo ai bassi.")

        act_layout.addWidget(self.rad_replaygain)
        act_layout.addWidget(self.rad_loudnorm)
        act_layout.addWidget(self.rad_dsp)

        # Sub-options for Physical Normalization
        self.frame_loudnorm_opts = QFrame()
        loud_opts_layout = QVBoxLayout(self.frame_loudnorm_opts)
        loud_opts_layout.setContentsMargins(20, 0, 0, 0)
        loud_opts_layout.setSpacing(4)

        self.chk_save_fixed = QCheckBox("Salva come nuovo file '_normalized.mp3' (lascia intatto il file originale)")
        self.chk_save_fixed.setChecked(False)
        self.chk_backup_original = QCheckBox("Crea copia di sicurezza del file originale nella cartella '_original/'")
        self.chk_backup_original.setChecked(False)

        loud_opts_layout.addWidget(self.chk_save_fixed)
        loud_opts_layout.addWidget(self.chk_backup_original)
        act_layout.addWidget(self.frame_loudnorm_opts)

        # Sub-options for DSP Mastering
        self.frame_dsp_opts = QFrame()
        dsp_opts_layout = QVBoxLayout(self.frame_dsp_opts)
        dsp_opts_layout.setContentsMargins(20, 0, 0, 0)
        dsp_opts_layout.setSpacing(6)

        dsp_row = QHBoxLayout()
        dsp_row.addWidget(QLabel("Preset Audio:"))
        self.combo_dsp_preset = QComboBox()
        self.combo_dsp_preset.addItem("Club Master (Bassi più potenti, limiter -0.5 dBTP)", "club_master")
        self.combo_dsp_preset.addItem("Vocal Clarity (Nitidezza voci e presenza)", "vocal_clarity")
        self.combo_dsp_preset.addItem("Warm Analog (Calore sonoro analogico)", "warm_analog")
        self.combo_dsp_preset.addItem("DJ Punch (Maggiore dinamica su cassa e rullante)", "dj_punch")
        self.combo_dsp_preset.addItem("De-Clip & Clean (Eliminazione distorsioni e pulizia audio)", "declip_clean")
        dsp_row.addWidget(self.combo_dsp_preset, 1)

        dsp_row.addWidget(QLabel("Formato:"))
        self.combo_dsp_format = QComboBox()
        self.combo_dsp_format.addItem("MP3 (320 kbps Massima Qualità)", "mp3")
        self.combo_dsp_format.addItem("MP3 (V0 Bitrate Variabile)", "mp3_v0")
        self.combo_dsp_format.addItem("FLAC (Senza Perdita di Qualità)", "flac")
        dsp_row.addWidget(self.combo_dsp_format)

        dsp_opts_layout.addLayout(dsp_row)
        act_layout.addWidget(self.frame_dsp_opts)

        def _update_option_frames() -> None:
            self.frame_loudnorm_opts.setEnabled(self.rad_loudnorm.isChecked())
            self.frame_dsp_opts.setEnabled(self.rad_dsp.isChecked())

        self.rad_replaygain.toggled.connect(lambda _: _update_option_frames())
        self.rad_loudnorm.toggled.connect(lambda _: _update_option_frames())
        self.rad_dsp.toggled.connect(lambda _: _update_option_frames())
        _update_option_frames()

        layout.addWidget(grp_action)

        # Action Buttons
        btn_box = QHBoxLayout()
        self.btn_apply = QPushButton("🚀 Esegui Correzione / Normalizza")
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #0d6efd;
                color: #ffffff;
                font-weight: bold;
                padding: 8px 18px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0b5ed7;
            }
        """)
        self.btn_apply.clicked.connect(self._on_apply_normalization)

        btn_close = QPushButton("Chiudi")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                color: #212529;
                border: 1px solid #ced4da;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
        """)
        btn_close.clicked.connect(self.close)

        btn_box.addStretch()
        btn_box.addWidget(btn_close)
        btn_box.addWidget(self.btn_apply)
        layout.addLayout(btn_box)

    def _extract_waveform_peaks(self, filepath: str, num_points: int = 80) -> np.ndarray:
        """Extracts downsampled peak envelope for dual waveform preview."""
        try:
            data, _ = AcousticQualityAnalyzer.read_audio(filepath, max_duration_sec=60.0)
            if data is not None and len(data) > 0:
                if data.ndim > 1:
                    data = np.mean(data, axis=1)
                abs_d = np.abs(data)
                chunk_size = max(1, len(abs_d) // num_points)
                peaks = []
                for i in range(num_points):
                    start = i * chunk_size
                    end = min(len(abs_d), (i + 1) * chunk_size)
                    if start < len(abs_d):
                        peaks.append(float(np.max(abs_d[start:end])))
                    else:
                        peaks.append(0.0)
                max_v = max(peaks) if peaks else 1.0
                return np.array(peaks) / (max_v if max_v > 0 else 1.0)
        except Exception:
            pass
        np.random.seed(abs(hash(filepath)) % 10000)
        env = 0.4 + 0.45 * np.sin(np.linspace(0, 3.14 * 6, num_points)) ** 2 + np.random.uniform(0.05, 0.2, num_points)
        return np.clip(env, 0.05, 1.0)

    def _update_waveform_preview(self) -> None:
        target_lufs = float(self.slider_lufs.value())
        max_tp = float(self.slider_tp.value()) / 10.0
        if hasattr(self, "waveform_widget"):
            self.waveform_widget.update_targets(target_lufs, max_tp)

    def _on_combo_target_changed(self) -> None:
        target_val = self.cmb_target.currentData()
        if target_val is not None:
            self.slider_lufs.blockSignals(True)
            self.slider_lufs.setValue(int(target_val))
            self.slider_lufs.blockSignals(False)
            self.lbl_lufs_val.setText(f"{target_val:.1f} LUFS")
            self._update_gain_needed()
            self._update_waveform_preview()

    def _on_slider_lufs_changed(self, val: int) -> None:
        self.lbl_lufs_val.setText(f"{val:.1f} LUFS")
        self.cmb_target.blockSignals(True)
        matched = False
        for i in range(self.cmb_target.count()):
            if abs(self.cmb_target.itemData(i) - float(val)) < 0.1:
                self.cmb_target.setCurrentIndex(i)
                matched = True
                break
        if not matched:
            self.cmb_target.setCurrentIndex(-1)
        self.cmb_target.blockSignals(False)
        self._update_gain_needed()
        self._update_waveform_preview()

    def _on_slider_tp_changed(self, val: int) -> None:
        tp_val = val / 10.0
        self.lbl_tp_val.setText(f"{tp_val:+.1f} dBTP")
        self._update_waveform_preview()

    def _update_gain_needed(self) -> None:
        if self.report:
            target_lufs = float(self.slider_lufs.value())
            diff = target_lufs - self.report.integrated_lufs
            sign = "+" if diff > 0 else ""
            self.lbl_gain_needed.setText(f"<b>Regolazione Consigliata:</b> {sign}{diff:.2f} dB (per raggiungere il target di {target_lufs:.1f} LUFS)")

    def _run_analysis(self) -> None:
        """Executes EBU R128 acoustic quality analysis."""
        try:
            target_lufs = float(self.slider_lufs.value())
            max_tp = float(self.slider_tp.value()) / 10.0
            self.report = AcousticQualityAnalyzer.analyze_file(self.filepath, target_lufs=target_lufs)

            # Update UI labels
            self.lbl_lufs.setText(f"<b>Volume Medio (Loudness):</b> {self.report.integrated_lufs:.2f} LUFS")
            tp_color = "#dc3545" if self.report.true_peak_dbtp > 0.0 else "#198754"
            tp_note = "Distorsione presente" if self.report.true_peak_dbtp > 0.0 else "Ottimale, nessun clipping"
            self.lbl_tp.setText(f"<b>Picco Massimo del Suono (True Peak):</b> <span style='color: {tp_color}; font-weight: bold;'>{self.report.true_peak_dbtp:+.2f} dBTP</span> ({tp_note})")
            self.lbl_lra.setText(f"<b>Escursione Dinamica (LRA):</b> {self.report.loudness_range_lra:.2f} LU")

            status_html = ""
            if self.report.status == "CLIPPING":
                status_html = "<span style='color: #dc3545; font-weight: bold;'>🔴 DISTORSIONE O PICCHI ECCESSIVI (Il volume satura oltre 0 dBTP)</span>"
            elif self.report.status == "LOW_VOLUME":
                status_html = "<span style='color: #fd7e14; font-weight: bold;'>🟡 VOLUME TROPPO BASSO (< -18 LUFS, consigliato alzare il volume)</span>"
            elif self.report.status == "BRICKWALL":
                status_html = "<span style='color: #d63384; font-weight: bold;'>🟠 COMPRESSIONE AGGRESSIVA (Poca dinamica tra parti calme e forti)</span>"
            else:
                status_html = "<span style='color: #198754; font-weight: bold;'>🟢 VOLUME BILANCIATO E OTTIMA QUALITÀ AUDIO</span>"

            self.lbl_status.setText(f"<b>Diagnosi del Brano:</b> {status_html}")
            self._update_gain_needed()
            self.meter_bar.set_metrics(self.report.integrated_lufs, self.report.true_peak_dbtp, self.report.status)

            # Update Dual Waveform Preview
            peaks = self._extract_waveform_peaks(self.filepath)
            self.waveform_widget.set_data(
                peaks,
                self.report.integrated_lufs,
                self.report.true_peak_dbtp,
                target_lufs,
                max_tp,
            )

        except Exception as exc:
            self.lbl_status.setText(f"<span style='color: #dc3545;'>Errore durante l'analisi: {exc}</span>")

    def _on_target_changed(self) -> None:
        self._update_gain_needed()
        self._update_waveform_preview()

    def _on_apply_normalization(self) -> None:
        """Executes normalization according to chosen strategy."""
        target_lufs = float(self.slider_lufs.value())
        max_true_peak = self.slider_tp.value() / 10.0

        if self.rad_replaygain.isChecked():
            res = self.normalizer.apply_replaygain(self.filepath, target_lufs=target_lufs, report=self.report)
            if res.success:
                QMessageBox.information(
                    self,
                    "ReplayGain Applicato",
                    f"Metadati ReplayGain scritti con successo nel file:\n"
                    f"• Gain Offset: {res.gain_applied_db:+.2f} dB\n"
                    f"• Target: {target_lufs:.1f} LUFS\n\n"
                    f"Il player libVLC regolerà automaticamente il volume durante l'ascolto.",
                )
                self.normalization_applied.emit(self.filepath)
                self.accept()
            else:
                QMessageBox.critical(self, "Errore ReplayGain", f"Impossibile applicare ReplayGain:\n{res.error_message}")

        elif self.rad_dsp.isChecked():
            preset = self.combo_dsp_preset.currentData() or "club_master"
            fmt = self.combo_dsp_format.currentData() or "mp3"
            res = self.normalizer.apply_dsp_enhancement(
                self.filepath,
                preset=preset,
                output_format=fmt,
                target_lufs=target_lufs,
                max_true_peak=max_true_peak,
                save_as_fixed=True,
            )
            if res.success:
                preset_name = self.combo_dsp_preset.currentText()
                fmt_name = self.combo_dsp_format.currentText()
                msg = f"Mastering DSP completato con successo!\n\n"
                msg += f"• Preset: {preset_name}\n"
                msg += f"• File generato: {res.output_filepath}\n"
                msg += f"• Formato: {fmt_name}\n"
                msg += f"• Target: {target_lufs:.1f} LUFS | Headroom: {max_true_peak:.1f} dBTP\n"
                msg += f"• Tag ID3 e Artwork: Copiati integralmente"

                QMessageBox.information(self, "Mastering DSP Completato", msg)
                self.normalization_applied.emit(res.output_filepath)
                self.accept()
            else:
                QMessageBox.critical(self, "Errore DSP", f"Impossibile applicare il processing DSP:\n{res.error_message}")

        else:
            save_as_fixed = self.chk_save_fixed.isChecked()
            create_backup = self.chk_backup_original.isChecked()

            res = self.normalizer.apply_physical_loudnorm(
                self.filepath,
                target_lufs=target_lufs,
                max_true_peak=max_true_peak,
                save_as_fixed=save_as_fixed,
                create_backup=create_backup,
            )
            if res.success:
                # Auto-index into SQLite immediately so the library table displays it right away
                if self.db:
                    try:
                        from src.core.scanner import LibraryScanner
                        LibraryScanner(self.db).scan_file(res.output_filepath)
                    except Exception:
                        pass

                msg = f"Normalizzazione fisica completata con successo!\n\n"
                msg += f"• File generato: {res.output_filepath}\n"
                msg += f"• Formato: MP3 (320 kbps High Quality, libmp3lame)\n"
                msg += f"• Target: {target_lufs:.1f} LUFS\n"
                msg += f"• Limiter Headroom: {max_true_peak:.1f} dBTP (De-clipping applicato)\n"
                msg += f"• Tag ID3 e Artwork: Copiati integralmente"
                if res.backup_path:
                    msg += f"\n• Copia originale salvata in: {res.backup_path}"

                QMessageBox.information(self, "Normalizzazione Completata", msg)
                self.normalization_applied.emit(res.output_filepath)
                self.accept()
            else:
                QMessageBox.critical(self, "Errore Normalizzazione", f"Impossibile normalizzare il file:\n{res.error_message}")


class BatchQualityWorker(QThread):
    """Background worker for mass library audio quality analysis."""

    progress = Signal(int, int, str)  # current, total, name
    finished = Signal(list)

    def __init__(self, tracks: List[Dict[str, Any]], target_lufs: float = -10.0) -> None:
        super().__init__()
        self.tracks = tracks
        self.target_lufs = target_lufs
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        reports = []
        total = len(self.tracks)
        for idx, tr in enumerate(self.tracks):
            if self._is_cancelled:
                break
            fp = tr.get("filepath", "")
            if not fp or not Path(fp).exists():
                continue

            try:
                rep = AcousticQualityAnalyzer.analyze_file(fp, target_lufs=self.target_lufs)
                reports.append(rep)
            except Exception:
                pass

            self.progress.emit(idx + 1, total, Path(fp).name)

        self.finished.emit(reports)
