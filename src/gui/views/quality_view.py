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
        self.resize(720, 620)
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
                margin-top: 12px;
                font-weight: bold;
                color: #0d6efd;
                background-color: #ffffff;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                background-color: #ffffff;
            }
            QRadioButton, QCheckBox {
                color: #212529;
                font-size: 12px;
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
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # Header Info
        header = QLabel(f"<b>File:</b> {Path(self.filepath).name}")
        header.setStyleSheet("font-size: 13px; color: #212529;")
        layout.addWidget(header)

        # Meter Bar
        self.meter_bar = LoudnessMeterBar(self)
        layout.addWidget(self.meter_bar)

        # 1. Diagnostics Group
        grp_diag = QGroupBox("📊 Metriche di Conformità EBU R128 / ITU-R BS.1770-4")
        diag_layout = QVBoxLayout(grp_diag)
        diag_layout.setSpacing(6)

        self.lbl_lufs = QLabel("Integrated Loudness: Calcolo in corso...")
        self.lbl_tp = QLabel("True Peak: Calcolo in corso...")
        self.lbl_lra = QLabel("Loudness Range (LRA): Calcolo in corso...")
        self.lbl_status = QLabel("Stato Qualità: Calcolo in corso...")
        self.lbl_gain_needed = QLabel("Guadagno Necessario: ...")

        diag_layout.addWidget(self.lbl_lufs)
        diag_layout.addWidget(self.lbl_tp)
        diag_layout.addWidget(self.lbl_lra)
        diag_layout.addWidget(self.lbl_status)
        diag_layout.addWidget(self.lbl_gain_needed)
        layout.addWidget(grp_diag)

        # 2. Strategy Selector Group
        grp_action = QGroupBox("⚡ Strategia di Correzione & Normalizzazione")
        act_layout = QVBoxLayout(grp_action)
        act_layout.setSpacing(10)

        # Target LUFS row & slider
        lufs_tooltip = (
            "Target Loudness (LUFS):\n"
            "• -9 / -10 LUFS: Club & DJ set ad alto impatto sonoro;\n"
            "• -14 LUFS: Standard streaming (Spotify, YouTube, Tidal, Apple Music);\n"
            "• -16 / -23 LUFS: Podcast ed EBU R128 broadcast."
        )

        target_row = QHBoxLayout()
        lbl_target_title = QLabel("Target Loudness:")
        lbl_target_title.setToolTip(lufs_tooltip)
        target_row.addWidget(lbl_target_title)

        self.cmb_target = QComboBox()
        self.cmb_target.addItem("-10.0 LUFS (DJ Club Standard)", -10.0)
        self.cmb_target.addItem("-14.0 LUFS (Spotify / Streaming)", -14.0)
        self.cmb_target.addItem("-16.0 LUFS (Apple Music / Podcast)", -16.0)
        self.cmb_target.addItem("-23.0 LUFS (EBU R128 Broadcast)", -23.0)
        self.cmb_target.setToolTip(lufs_tooltip)
        self.cmb_target.currentIndexChanged.connect(self._on_combo_target_changed)
        target_row.addWidget(self.cmb_target)

        self.slider_lufs = QSlider(Qt.Orientation.Horizontal)
        self.slider_lufs.setRange(-24, -6)
        self.slider_lufs.setValue(-10)
        self.slider_lufs.setToolTip(lufs_tooltip)
        self.slider_lufs.valueChanged.connect(self._on_slider_lufs_changed)
        target_row.addWidget(self.slider_lufs, 1)

        self.lbl_lufs_val = QLabel("-10.0 LUFS")
        self.lbl_lufs_val.setStyleSheet("font-weight: bold; min-width: 65px; color: #0d6efd;")
        target_row.addWidget(self.lbl_lufs_val)
        act_layout.addLayout(target_row)

        # Target True Peak ceiling row & slider
        tp_tooltip = (
            "Margine True Peak (headroom):\n"
            "• -1.0 dBTP: Margine di sicurezza raccomandato per eliminare distorsioni inter-sample "
            "e clipping digitale durante la conversione D/A e compressione MP3/AAC."
        )
        tp_row = QHBoxLayout()
        lbl_tp_title = QLabel("True Peak Headroom:")
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
        self.rad_replaygain = QRadioButton("🏷️ ReplayGain Non Distruttivo (Scrive tag Sound Check / Gain Offset nei metadati)")
        self.rad_replaygain.setChecked(True)
        self.rad_replaygain.setToolTip("Conserva il PCM originale senza toccare lo stream audio. Il player applica il guadagno al volo.")

        self.rad_loudnorm = QRadioButton("🛠️ Normalizzazione Fisica (De-Clipping & Re-encoding Two-Pass FFmpeg loudnorm)")
        self.rad_loudnorm.setToolTip("Ricalcola l'audio applicando True Peak Limiter a -1.0 dBTP e target LUFS.")

        act_layout.addWidget(self.rad_replaygain)
        act_layout.addWidget(self.rad_loudnorm)

        # Sub-options for Physical Normalization
        self.frame_loudnorm_opts = QFrame()
        loud_opts_layout = QVBoxLayout(self.frame_loudnorm_opts)
        loud_opts_layout.setContentsMargins(20, 0, 0, 0)
        loud_opts_layout.setSpacing(4)

        self.chk_save_fixed = QCheckBox("Salva con suffisso '_fixed.ext' (lascia intatto il file originale)")
        self.chk_save_fixed.setChecked(True)
        self.chk_backup_original = QCheckBox("Crea copia di sicurezza in cartella '_original/'")
        self.chk_backup_original.setChecked(True)

        loud_opts_layout.addWidget(self.chk_save_fixed)
        loud_opts_layout.addWidget(self.chk_backup_original)
        act_layout.addWidget(self.frame_loudnorm_opts)

        self.rad_replaygain.toggled.connect(lambda checked: self.frame_loudnorm_opts.setEnabled(not checked))
        self.frame_loudnorm_opts.setEnabled(False)

        layout.addWidget(grp_action)

        # Callout Box: Tips & Spiegazioni Operative
        callout_box = QFrame()
        callout_box.setStyleSheet("""
            QFrame {
                background-color: #f0f7ff;
                border: 1px solid #b6d4fe;
                border-radius: 6px;
            }
            QLabel {
                color: #084298;
                font-size: 11px;
            }
        """)
        callout_layout = QVBoxLayout(callout_box)
        callout_layout.setContentsMargins(12, 8, 12, 8)
        callout_layout.setSpacing(4)

        lbl_callout_title = QLabel("💡 <b>Tips & Spiegazioni Operative</b>")
        lbl_callout_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #084298;")

        lbl_callout_desc = QLabel(
            "• <b>ReplayGain (Non distruttivo):</b> Scrive il volume raccomandato nei metadati/tag del file "
            "senza alterare la qualità audio originale. I software DJ (Traktor, Serato, Rekordbox) e i lettori compatibili "
            "applicano la correzione al volo in tempo reale.<br>"
            "• <b>FFmpeg loudnorm (Normalizzazione fisica):</b> Ricalcola e riscrive fisicamente l'onda audio al True Peak impostato (-1.0 dBTP) "
            "eliminando distorsioni e clipping digitale permanente. Ideale per brani esportati su USB per CDJ standalone."
        )
        lbl_callout_desc.setWordWrap(True)
        lbl_callout_desc.setStyleSheet("color: #084298; font-size: 11px; line-height: 140%;")
        callout_layout.addWidget(lbl_callout_title)
        callout_layout.addWidget(lbl_callout_desc)
        layout.addWidget(callout_box)

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

    def _on_combo_target_changed(self) -> None:
        target_val = self.cmb_target.currentData()
        if target_val is not None:
            self.slider_lufs.blockSignals(True)
            self.slider_lufs.setValue(int(target_val))
            self.slider_lufs.blockSignals(False)
            self.lbl_lufs_val.setText(f"{target_val:.1f} LUFS")
            self._update_gain_needed()

    def _on_slider_lufs_changed(self, val: int) -> None:
        self.lbl_lufs_val.setText(f"{val:.1f} LUFS")
        self.cmb_target.blockSignals(True)
        # Update combo if matching preset exists
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

    def _on_slider_tp_changed(self, val: int) -> None:
        tp_val = val / 10.0
        self.lbl_tp_val.setText(f"{tp_val:+.1f} dBTP")

    def _update_gain_needed(self) -> None:
        if self.report:
            target_lufs = float(self.slider_lufs.value())
            diff = target_lufs - self.report.integrated_lufs
            sign = "+" if diff > 0 else ""
            self.lbl_gain_needed.setText(f"<b>Guadagno Raccomandato:</b> {sign}{diff:.2f} dB (per raggiungere {target_lufs:.1f} LUFS)")

    def _run_analysis(self) -> None:
        """Executes EBU R128 acoustic quality analysis."""
        try:
            target_lufs = float(self.slider_lufs.value())
            self.report = AcousticQualityAnalyzer.analyze_file(self.filepath, target_lufs=target_lufs)

            # Update UI labels
            self.lbl_lufs.setText(f"<b>Integrated Loudness:</b> {self.report.integrated_lufs:.2f} LUFS")
            tp_color = "#dc3545" if self.report.true_peak_dbtp > 0.0 else "#198754"
            self.lbl_tp.setText(f"<b>True Peak:</b> <span style='color: {tp_color};'>{self.report.true_peak_dbtp:+.2f} dBTP</span> (Sample Peak: {self.report.sample_peak_dbfs:+.2f} dBFS)")
            self.lbl_lra.setText(f"<b>Loudness Range (LRA):</b> {self.report.loudness_range_lra:.2f} LU")

            status_html = ""
            if self.report.status == "CLIPPING":
                status_html = "<span style='color: #dc3545; font-weight: bold;'>🔴 DISTORSIONE / CLIPPING RILEVATO (True Peak > 0 dBTP)</span>"
            elif self.report.status == "LOW_VOLUME":
                status_html = "<span style='color: #fd7e14; font-weight: bold;'>🟡 LIVELLO BASSO (< -18 LUFS)</span>"
            elif self.report.status == "BRICKWALL":
                status_html = "<span style='color: #d63384; font-weight: bold;'>🟠 IPERCOMPRESSIONE BRICKWALL (LRA < 3 LU)</span>"
            else:
                status_html = "<span style='color: #198754; font-weight: bold;'>🟢 CONFORME (Ottima Dinamica & Nessun Clipping)</span>"

            self.lbl_status.setText(f"<b>Stato Qualità:</b> {status_html}")
            self._update_gain_needed()
            self.meter_bar.set_metrics(self.report.integrated_lufs, self.report.true_peak_dbtp, self.report.status)

        except Exception as exc:
            self.lbl_status.setText(f"<span style='color: #dc3545;'>Errore durante l'analisi: {exc}</span>")

    def _on_target_changed(self) -> None:
        self._update_gain_needed()

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
                msg = f"Normalizzazione fisica completata!\nFile salvato: {res.output_filepath}"
                if res.backup_path:
                    msg += f"\nBackup originale creato in: {res.backup_path}"
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
