"""
Multi-Source Reconciliation Dialog for Musicat.

Presents side-by-side metadata comparisons from Beatport, Traxsource, Discogs,
MusicBrainz, Social/Remix web sources, and Apple Music HD covers.
Provides field-by-field selective resolution to resolve metadata discrepancies.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..scrapers.reconciler import MetadataReconciler, DiscrepancyReport
from ..scrapers.beatport import BeatportScraper
from ..scrapers.traxsource import TraxsourceScraper
from ..scrapers.discogs import DiscogsClient
from ..scrapers.musicbrainz import MusicBrainzClient
from ..scrapers.social_remix import SocialRemixScraper
from ..scrapers.artwork_hd import HDArtworkFinder
from ..tags.editor import AudioTagEditor
from ..core.logger import MusicatLogger


class ReconcilerDialog(QDialog):
    """Interactive multi-source discrepancy resolution and HD cover injector."""

    metadata_reconciled = Signal(dict)

    def __init__(self, track: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.track = track
        self.current_report: Optional[DiscrepancyReport] = None
        self.selected_image_bytes: Optional[bytes] = None

        self.setWindowTitle(f"Musicat Multi-Source Reconciler - {self.track.get('filename')}")
        self.resize(1020, 720)

        self._init_ui()
        self._start_search()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Header Search Query Bar
        q_bar = QHBoxLayout()
        q_bar.addWidget(QLabel("<b>Track Query:</b>"))
        self.txt_query = QLineEdit()
        art = self.track.get("artist") or ""
        tit = self.track.get("title") or Path(self.track.get("filepath", "")).stem
        self.txt_query.setText(f"{art} {tit}".strip())

        self.btn_search = QPushButton("🔎 Run Multi-Source Scraping")
        self.btn_search.setObjectName("PrimaryButton")
        self.btn_search.clicked.connect(self._start_search)

        q_bar.addWidget(self.txt_query, 3)
        q_bar.addWidget(self.btn_search, 1)
        main_layout.addLayout(q_bar)

        # Sources Checkboxes
        src_box = QHBoxLayout()
        src_box.addWidget(QLabel("Active Sources:"))
        self.chk_bp = QCheckBox("Beatport")
        self.chk_bp.setChecked(True)
        self.chk_tx = QCheckBox("Traxsource")
        self.chk_tx.setChecked(True)
        self.chk_disc = QCheckBox("Discogs")
        self.chk_disc.setChecked(True)
        self.chk_mb = QCheckBox("MusicBrainz")
        self.chk_mb.setChecked(True)
        self.chk_soc = QCheckBox("Social/Remixes")
        self.chk_soc.setChecked(True)
        self.chk_hd = QCheckBox("Apple Music HD Covers")
        self.chk_hd.setChecked(True)

        for c in (self.chk_bp, self.chk_tx, self.chk_disc, self.chk_mb, self.chk_soc, self.chk_hd):
            src_box.addWidget(c)
        src_box.addStretch()
        main_layout.addLayout(src_box)

        # Content: Discrepancy Table + HD Cover Preview
        content_layout = QHBoxLayout()

        # Discrepancy Table
        table_group = QGroupBox("Field Discrepancy Reconciliation")
        table_layout = QVBoxLayout(table_group)

        self.table_discrepancies = QTableWidget()
        self.table_discrepancies.setColumnCount(4)
        self.table_discrepancies.setHorizontalHeaderLabels(["Field", "Status", "Available Values from Sources", "Chosen Value"])
        self.table_discrepancies.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_discrepancies.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_discrepancies.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_discrepancies.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        table_layout.addWidget(self.table_discrepancies)
        content_layout.addWidget(table_group, 3)

        # Artwork Panel
        art_group = QGroupBox("HD Album Artwork")
        art_layout = QVBoxLayout(art_group)

        self.lbl_cover_preview = QLabel("Searching...")
        self.lbl_cover_preview.setFixedSize(220, 220)
        self.lbl_cover_preview.setStyleSheet("border: 1px dashed #3a3f52; background-color: #14161f;")
        self.lbl_cover_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_art_info = QLabel("No cover selected")
        self.lbl_art_info.setStyleSheet("color: #8c92a4; font-size: 11px;")

        self.cmb_art_options = QComboBox()
        self.cmb_art_options.currentIndexChanged.connect(self._on_artwork_selected)

        self.chk_save_folder_copy = QCheckBox("Save copy as cover.jpg in track folder")
        self.chk_save_folder_copy.setChecked(True)

        art_layout.addWidget(self.lbl_cover_preview, alignment=Qt.AlignmentFlag.AlignCenter)
        art_layout.addWidget(self.lbl_art_info)
        art_layout.addWidget(self.cmb_art_options)
        art_layout.addWidget(self.chk_save_folder_copy)
        art_layout.addStretch()

        content_layout.addWidget(art_group, 1)
        main_layout.addLayout(content_layout)

        # Bottom Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        bottom_bar = QHBoxLayout()
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("color: #8c92a4;")

        self.btn_cancel = QPushButton("Cancel")
        self.btn_apply = QPushButton("Apply Reconciled Metadata to Track")
        self.btn_apply.setObjectName("PrimaryButton")
        self.btn_apply.setEnabled(False)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply.clicked.connect(self._apply_reconciliation)

        bottom_bar.addWidget(self.lbl_status)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self.btn_cancel)
        bottom_bar.addWidget(self.btn_apply)
        main_layout.addLayout(bottom_bar)

        self.combos_by_field: Dict[str, QComboBox] = {}
        self.hd_candidates = []

    def _start_search(self) -> None:
        q = self.txt_query.text().strip()
        if not q:
            return

        self.btn_search.setEnabled(False)
        self.lbl_status.setText("Querying online sources...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        # Aggregate results across selected providers
        all_results: List[Dict[str, Any]] = []

        try:
            if self.chk_bp.isChecked():
                bp_tracks = BeatportScraper.search_tracks(q, limit=3)
                all_results.extend([t.to_dict() for t in bp_tracks])

            if self.chk_tx.isChecked():
                tx_tracks = TraxsourceScraper.search_tracks(q, limit=3)
                all_results.extend([t.to_dict() for t in tx_tracks])

            if self.chk_disc.isChecked():
                disc_tracks = DiscogsClient().search_releases(q, limit=3)
                all_results.extend(disc_tracks)

            if self.chk_mb.isChecked():
                mb_tracks = MusicBrainzClient.search_track(q, limit=3)
                all_results.extend(mb_tracks)

            if self.chk_soc.isChecked():
                soc_tracks = SocialRemixScraper.search_all(q, limit_per_source=2)
                all_results.extend(soc_tracks)

            if self.chk_hd.isChecked():
                self.hd_candidates = HDArtworkFinder.search_all_hd_sources(
                    artist=self.track.get("artist") or "",
                    title=self.track.get("title") or q,
                )
        except Exception as e:
            MusicatLogger.get_logger().error(f"[RECONCILER] Search error: {e}")

        self.progress_bar.setVisible(False)
        self.btn_search.setEnabled(True)

        # Analyze discrepancies
        self.current_report = MetadataReconciler.analyze_discrepancies(
            track_query=q,
            results_from_sources=all_results,
            current_file_tags=self.track,
        )

        self._render_discrepancies(self.current_report)
        self._populate_artwork_candidates(self.hd_candidates)
        self.btn_apply.setEnabled(len(all_results) > 0 or len(self.hd_candidates) > 0)
        self.lbl_status.setText(f"Done. Retrieved metadata from {len(all_results)} results across {len(self.current_report.sources_participated)} sources.")

    def _render_discrepancies(self, report: DiscrepancyReport) -> None:
        self.table_discrepancies.setRowCount(0)
        self.combos_by_field.clear()

        rows = list(report.fields.items())
        self.table_discrepancies.setRowCount(len(rows))

        for idx, (fld_name, disc) in enumerate(rows):
            # Field name item
            item_fld = QTableWidgetItem(fld_name.replace("_", " ").title())
            item_fld.setFlags(item_fld.flags() & ~Qt.ItemFlag.ItemIsEditable)

            # Conflict Status
            if disc.has_conflict:
                item_status = QTableWidgetItem("⚠️ Conflict")
                item_status.setForeground(Qt.GlobalColor.yellow)
            elif disc.values_by_source:
                item_status = QTableWidgetItem("✓ Match")
                item_status.setForeground(Qt.GlobalColor.green)
            else:
                item_status = QTableWidgetItem("- Empty")
                item_status.setForeground(Qt.GlobalColor.gray)
            item_status.setFlags(item_status.flags() & ~Qt.ItemFlag.ItemIsEditable)

            # Available Values summary
            summary_parts = [f"[{src}]: {val}" for src, val in disc.values_by_source.items()]
            item_summary = QTableWidgetItem("; ".join(summary_parts))
            item_summary.setFlags(item_summary.flags() & ~Qt.ItemFlag.ItemIsEditable)

            # Combo to choose which source/value wins
            cmb_choice = QComboBox()
            cmb_choice.addItem("<None / Leave empty>", "")

            default_idx = 0
            for opt_idx, (src_name, src_val) in enumerate(disc.values_by_source.items(), start=1):
                cmb_choice.addItem(f"{src_name}: {src_val}", src_val)
                if disc.recommended_value is not None and str(src_val).strip() == str(disc.recommended_value).strip():
                    default_idx = opt_idx

            cmb_choice.setCurrentIndex(default_idx)
            self.combos_by_field[fld_name] = cmb_choice

            self.table_discrepancies.setItem(idx, 0, item_fld)
            self.table_discrepancies.setItem(idx, 1, item_status)
            self.table_discrepancies.setItem(idx, 2, item_summary)
            self.table_discrepancies.setCellWidget(idx, 3, cmb_choice)

    def _populate_artwork_candidates(self, candidates: List) -> None:
        self.cmb_art_options.clear()
        self.cmb_art_options.addItem("Keep existing cover", None)

        for idx, c in enumerate(candidates):
            self.cmb_art_options.addItem(f"{c.source} ({c.dimension_label})", c.image_url)

        if candidates:
            self.cmb_art_options.setCurrentIndex(1)
        else:
            self.lbl_cover_preview.setText("No Artwork Discovered")

    def _on_artwork_selected(self, index: int) -> None:
        url = self.cmb_art_options.currentData()
        if not url:
            self.lbl_cover_preview.setText("Existing Cover")
            self.selected_image_bytes = None
            return

        self.lbl_cover_preview.setText("Downloading...")
        data = HDArtworkFinder.download_image(url)
        if data:
            self.selected_image_bytes = data
            img = QImage.fromData(data)
            pix = QPixmap.fromImage(img).scaled(
                210, 210, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_cover_preview.setPixmap(pix)
            self.lbl_art_info.setText(f"Size: {len(data) // 1024} KB | Res: {img.width()}x{img.height()} px")
        else:
            self.lbl_cover_preview.setText("Download Failed")

    def _apply_reconciliation(self) -> None:
        if not self.current_report:
            return

        # Read user selections
        selections: Dict[str, Any] = {}
        for fld, cmb in self.combos_by_field.items():
            val = cmb.currentData()
            if val is not None and val != "":
                selections[fld] = val

        merged_tags = MetadataReconciler.merge_selected_metadata(self.current_report, selections)
        filepath = self.track.get("filepath", "")

        try:
            # 1. Write merged metadata to physical audio tags
            AudioTagEditor.write_metadata(filepath, merged_tags)

            # 2. Inject HD Artwork if selected
            if self.selected_image_bytes:
                save_local = self.chk_save_folder_copy.isChecked()
                HDArtworkFinder.apply_artwork_to_file(filepath, self.selected_image_bytes, save_folder_copy=save_local)
                merged_tags["has_cover"] = 1

            # 3. Synchronize with updated record
            updated_record = dict(self.track)
            updated_record.update(merged_tags)

            QMessageBox.information(
                self,
                "Reconciliation Complete",
                f"Successfully reconciled and saved {len(merged_tags)} metadata fields to:\n{Path(filepath).name}",
            )
            self.metadata_reconciled.emit(updated_record)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not commit tags: {e}")
