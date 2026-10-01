"""
Tag Editor Dialog for Musicat.
Provides Mp3tag-style single and multi-selection batch tag editing,
embedded artwork management, and Camelot/BPM synchronization.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..tags.editor import AudioTagEditor
from ..audio.analyzer import KEY_TO_CAMELOT, CAMELOT_TO_KEY, key_to_camelot, camelot_to_key, AcousticAnalyzer


class TagEditorDialog(QDialog):
    """Batch and Single track tag editor dialog."""

    tags_saved = Signal(list)  # List of updated track records

    KEEP_EXISTING_PLACEHOLDER = "<keep existing>"

    def __init__(self, tracks: List[Dict[str, Any]], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tracks = tracks
        self.is_batch = len(tracks) > 1
        self.pending_cover_bytes: Optional[bytes] = None
        self.pending_remove_cover: bool = False

        self.setWindowTitle(f"Musicat Tag Editor - {len(tracks)} track(s) selected")
        self.resize(720, 640)

        self._init_ui()
        self._populate_fields()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        header_lbl = QLabel(
            f"<b>Batch Editing {len(self.tracks)} Tracks</b> (fields left as '{self.KEEP_EXISTING_PLACEHOLDER}' will not be changed)"
            if self.is_batch
            else f"<b>Editing Track:</b> {self.tracks[0].get('filename')}"
        )
        header_lbl.setStyleSheet("color: #00d2ff; font-size: 14px;")
        main_layout.addWidget(header_lbl)

        content_layout = QHBoxLayout()

        # Left Column: Metadata Fields
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setSpacing(8)

        self.txt_title = QLineEdit()
        self.txt_artist = QLineEdit()
        self.txt_album = QLineEdit()
        self.txt_album_artist = QLineEdit()
        self.txt_genre = QLineEdit()
        self.txt_remixer = QLineEdit()
        self.txt_label = QLineEdit()
        self.txt_year = QLineEdit()
        self.txt_track_num = QLineEdit()
        self.txt_bpm = QLineEdit()

        # Camelot & Key dropdowns
        key_box = QHBoxLayout()
        self.cmb_camelot = QComboBox()
        self.cmb_camelot.addItem("")
        for num in range(1, 13):
            self.cmb_camelot.addItem(f"{num}A")
            self.cmb_camelot.addItem(f"{num}B")

        self.txt_musical_key = QLineEdit()
        key_box.addWidget(self.cmb_camelot)
        key_box.addWidget(QLabel("Key:"))
        key_box.addWidget(self.txt_musical_key)

        self.spin_energy = QSpinBox()
        self.spin_energy.setRange(0, 10)
        self.spin_energy.setSpecialValueText("Not set")

        self.txt_comment = QLineEdit()

        form_layout.addRow("Title:", self.txt_title)
        form_layout.addRow("Artist:", self.txt_artist)
        form_layout.addRow("Remixer:", self.txt_remixer)
        form_layout.addRow("Album:", self.txt_album)
        form_layout.addRow("Album Artist:", self.txt_album_artist)
        form_layout.addRow("Genre:", self.txt_genre)
        form_layout.addRow("Label:", self.txt_label)
        form_layout.addRow("Year:", self.txt_year)
        form_layout.addRow("Track #:", self.txt_track_num)
        form_layout.addRow("BPM:", self.txt_bpm)
        form_layout.addRow("Camelot / Key:", key_box)
        form_layout.addRow("Energy Level:", self.spin_energy)
        form_layout.addRow("Comment:", self.txt_comment)

        content_layout.addWidget(form_widget, 3)

        # Right Column: Artwork & Acoustic Helpers
        right_panel = QVBoxLayout()

        art_group = QGroupBox("Album Artwork")
        art_layout = QVBoxLayout(art_group)

        self.art_preview = QLabel("No Artwork")
        self.art_preview.setFixedSize(180, 180)
        self.art_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.art_preview.setStyleSheet("border: 1px dashed #3a3f52; background-color: #161821;")

        btn_load_art = QPushButton("Load Cover Image...")
        btn_export_art = QPushButton("Export cover.jpg...")
        btn_remove_art = QPushButton("Remove Cover")

        btn_load_art.clicked.connect(self._on_load_artwork)
        btn_export_art.clicked.connect(self._on_export_artwork)
        btn_remove_art.clicked.connect(self._on_remove_artwork)

        art_layout.addWidget(self.art_preview, alignment=Qt.AlignmentFlag.AlignCenter)
        art_layout.addWidget(btn_load_art)
        art_layout.addWidget(btn_export_art)
        art_layout.addWidget(btn_remove_art)

        right_panel.addWidget(art_group)

        # Acoustic Action Group
        acoustic_group = QGroupBox("Acoustic Tools")
        acoustic_layout = QVBoxLayout(acoustic_group)

        btn_calc_bpm_key = QPushButton("🎵 Auto-Detect BPM & Key")
        btn_calc_bpm_key.setObjectName("AccentButton")
        btn_calc_bpm_key.clicked.connect(self._on_detect_acoustic)

        acoustic_layout.addWidget(btn_calc_bpm_key)
        right_panel.addWidget(acoustic_group)
        right_panel.addStretch()

        content_layout.addLayout(right_panel, 2)
        main_layout.addLayout(content_layout)

        # Bottom Action Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_save = QPushButton("Save Tags to File(s)")
        self.btn_save.setObjectName("PrimaryButton")

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self._on_save)

        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_save)

        main_layout.addLayout(btn_box)

        # Connect camelot dropdown sync
        self.cmb_camelot.currentTextChanged.connect(self._on_camelot_changed)

    def _populate_fields(self) -> None:
        if not self.tracks:
            return

        if not self.is_batch:
            t = self.tracks[0]
            self.txt_title.setText(str(t.get("title") or ""))
            self.txt_artist.setText(str(t.get("artist") or ""))
            self.txt_remixer.setText(str(t.get("remixer") or ""))
            self.txt_album.setText(str(t.get("album") or ""))
            self.txt_album_artist.setText(str(t.get("album_artist") or ""))
            self.txt_genre.setText(str(t.get("genre") or ""))
            self.txt_label.setText(str(t.get("label") or ""))
            self.txt_year.setText(str(t.get("year") or ""))
            self.txt_track_num.setText(str(t.get("track_num") or ""))
            self.txt_bpm.setText(str(t.get("bpm") or ""))
            self.txt_musical_key.setText(str(t.get("musical_key") or ""))
            self.cmb_camelot.setCurrentText(str(t.get("camelot_key") or ""))
            self.spin_energy.setValue(int(t.get("energy_level") or 0))
            self.txt_comment.setText(str(t.get("comment") or ""))

            # Load artwork
            self._load_current_artwork(t.get("filepath", ""))
        else:
            # Batch mode: show placeholder if values differ
            def uniform_val(key: str) -> str:
                vals = {str(tr.get(key) or "") for tr in self.tracks}
                return vals.pop() if len(vals) == 1 else self.KEEP_EXISTING_PLACEHOLDER

            self.txt_title.setText(uniform_val("title"))
            self.txt_artist.setText(uniform_val("artist"))
            self.txt_remixer.setText(uniform_val("remixer"))
            self.txt_album.setText(uniform_val("album"))
            self.txt_album_artist.setText(uniform_val("album_artist"))
            self.txt_genre.setText(uniform_val("genre"))
            self.txt_label.setText(uniform_val("label"))
            self.txt_year.setText(uniform_val("year"))
            self.txt_track_num.setText(uniform_val("track_num"))
            self.txt_bpm.setText(uniform_val("bpm"))
            self.txt_comment.setText(uniform_val("comment"))

            # Display artwork if identical across tracks
            self._load_current_artwork(self.tracks[0].get("filepath", ""))

    def _load_current_artwork(self, filepath: str) -> None:
        if not filepath or not Path(filepath).exists():
            return
        cover = AudioTagEditor.get_artwork(filepath)
        if cover:
            img = QImage.fromData(cover.data)
            if not img.isNull():
                pixmap = QPixmap.fromImage(img).scaled(
                    170, 170, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                self.art_preview.setPixmap(pixmap)
                return
        self.art_preview.setText("No Artwork")

    def _on_camelot_changed(self, camelot: str) -> None:
        if camelot:
            key_name = camelot_to_key(camelot)
            if key_name and not self.txt_musical_key.text():
                self.txt_musical_key.setText(key_name)

    def _on_load_artwork(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Cover Image", "", "Images (*.jpg *.jpeg *.png *.webp)"
        )
        if path:
            data = Path(path).read_bytes()
            self.pending_cover_bytes = data
            self.pending_remove_cover = False
            img = QImage.fromData(data)
            if not img.isNull():
                pix = QPixmap.fromImage(img).scaled(
                    170, 170, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                self.art_preview.setPixmap(pix)

    def _on_export_artwork(self) -> None:
        if not self.tracks:
            return
        cover = AudioTagEditor.get_artwork(self.tracks[0].get("filepath", ""))
        if not cover:
            QMessageBox.information(self, "Export", "No embedded artwork found to export.")
            return

        out_path, _ = QFileDialog.getSaveFileName(self, "Save Artwork", "cover.jpg", "JPEG Image (*.jpg);;PNG Image (*.png)")
        if out_path:
            Path(out_path).write_bytes(cover.data)
            QMessageBox.information(self, "Export", f"Artwork exported to {out_path}")

    def _on_remove_artwork(self) -> None:
        self.pending_cover_bytes = None
        self.pending_remove_cover = True
        self.art_preview.setText("Artwork Removed")
        self.art_preview.setPixmap(QPixmap())

    def _on_detect_acoustic(self) -> None:
        """Runs acoustic analysis on current or first track."""
        if not self.tracks:
            return
        try:
            profile = AcousticAnalyzer.analyze_file(self.tracks[0].get("filepath", ""))
            self.txt_bpm.setText(f"{profile.bpm:.1f}")
            self.txt_musical_key.setText(profile.musical_key)
            self.cmb_camelot.setCurrentText(profile.camelot_key)
            QMessageBox.information(
                self,
                "Acoustic Detection",
                f"Detected BPM: {profile.bpm:.1f}\nKey: {profile.musical_key} (Camelot {profile.camelot_key})\nPeak: {profile.peak_db} dBFS",
            )
        except Exception as e:
            QMessageBox.warning(self, "Detection Failed", f"Acoustic analysis failed: {e}")

    def _on_save(self) -> None:
        """Saves tags to physical files and commits updates."""
        updates: Dict[str, Any] = {}

        def check_field(field_key: str, widget_text: str, is_numeric: bool = False, is_float: bool = False):
            val = widget_text.strip()
            if val == self.KEEP_EXISTING_PLACEHOLDER:
                return  # Do not touch this field
            if not val:
                updates[field_key] = None if is_numeric or is_float else ""
            elif is_numeric:
                updates[field_key] = int(val) if val.isdigit() else None
            elif is_float:
                try:
                    updates[field_key] = float(val)
                except ValueError:
                    pass
            else:
                updates[field_key] = val

        check_field("title", self.txt_title.text())
        check_field("artist", self.txt_artist.text())
        check_field("remixer", self.txt_remixer.text())
        check_field("album", self.txt_album.text())
        check_field("album_artist", self.txt_album_artist.text())
        check_field("genre", self.txt_genre.text())
        check_field("label", self.txt_label.text())
        check_field("year", self.txt_year.text(), is_numeric=True)
        check_field("track_num", self.txt_track_num.text(), is_numeric=True)
        check_field("bpm", self.txt_bpm.text(), is_float=True)
        check_field("musical_key", self.txt_musical_key.text())
        check_field("comment", self.txt_comment.text())

        if self.cmb_camelot.currentText():
            updates["camelot_key"] = self.cmb_camelot.currentText()
        if self.spin_energy.value() > 0:
            updates["energy_level"] = self.spin_energy.value()

        # Apply to each selected track
        updated_tracks = []
        for tr in self.tracks:
            fp = tr.get("filepath", "")
            try:
                # 1. Physical tag write
                AudioTagEditor.write_metadata(fp, updates)

                # 2. Artwork update
                if self.pending_cover_bytes:
                    AudioTagEditor.set_artwork(fp, self.pending_cover_bytes)
                    updates["has_cover"] = 1
                elif self.pending_remove_cover:
                    AudioTagEditor.remove_artwork(fp)
                    updates["has_cover"] = 0

                # 3. Update dictionary
                merged = dict(tr)
                merged.update({k: v for k, v in updates.items() if v is not None})
                updated_tracks.append(merged)
            except Exception as e:
                pass

        self.tags_saved.emit(updated_tracks)
        self.accept()
