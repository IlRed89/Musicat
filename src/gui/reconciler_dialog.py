"""
Multi-Source Reconciliation Dialog for Musicat.

Presents side-by-side metadata comparisons from Beatport, Traxsource, Discogs,
MusicBrainz, Social/Remix web sources, and Apple Music HD covers.
Provides field-by-field selective resolution to resolve metadata discrepancies.
Non-blocking asynchronous background execution ensures zero GUI freezing.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal, QThread
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
from ..core.i18n import _t


FIELD_TRANSLATIONS = {
    "title": "Titolo",
    "artist": "Artista",
    "remixer": "Remixer",
    "album": "Album",
    "label": "Etichetta",
    "genre": "Genere",
    "year": "Anno",
    "bpm": "BPM",
    "musical_key": "Chiave Musicale",
    "camelot_key": "Chiave Camelot",
    "catalog_number": "Num. Catalogo",
    "format": "Formato",
    "artwork_url": "Copertina HD",
}


class ReconcilerSearchWorker(QThread):
    """Asynchronous worker for multi-source scraping queries without freezing the GUI."""

    results_ready = Signal(list, list)  # all_results, hd_candidates
    error_occurred = Signal(str)

    def __init__(
        self,
        query: str,
        artist: str,
        title: str,
        chk_bp: bool,
        chk_tx: bool,
        chk_disc: bool,
        chk_mb: bool,
        chk_soc: bool,
        chk_hd: bool,
    ) -> None:
        super().__init__()
        self.query = query
        self.artist = artist
        self.title = title
        self.chk_bp = chk_bp
        self.chk_tx = chk_tx
        self.chk_disc = chk_disc
        self.chk_mb = chk_mb
        self.chk_soc = chk_soc
        self.chk_hd = chk_hd

    def run(self) -> None:
        all_results: List[Dict[str, Any]] = []
        hd_candidates: List[Any] = []
        q = self.query

        try:
            if self.chk_bp:
                try:
                    bp_tracks = BeatportScraper.search_tracks(q, limit=3)
                    all_results.extend([t.to_dict() for t in bp_tracks])
                except Exception as exc:
                    MusicatLogger.debug("RECONCILER:BP", f"Beatport query error: {exc}")

            if self.chk_tx:
                try:
                    tx_tracks = TraxsourceScraper.search_tracks(q, limit=3)
                    all_results.extend([t.to_dict() for t in tx_tracks])
                except Exception as exc:
                    MusicatLogger.debug("RECONCILER:TX", f"Traxsource query error: {exc}")

            if self.chk_disc:
                try:
                    disc_tracks = DiscogsClient().search_releases(q, limit=3)
                    all_results.extend(disc_tracks)
                except Exception as exc:
                    MusicatLogger.debug("RECONCILER:DISC", f"Discogs query error: {exc}")

            if self.chk_mb:
                try:
                    mb_tracks = MusicBrainzClient.search_track(q, limit=3)
                    all_results.extend(mb_tracks)
                except Exception as exc:
                    MusicatLogger.debug("RECONCILER:MB", f"MusicBrainz query error: {exc}")

            if self.chk_soc:
                try:
                    soc_tracks = SocialRemixScraper.search_all(q, limit_per_source=2)
                    all_results.extend(soc_tracks)
                except Exception as exc:
                    MusicatLogger.debug("RECONCILER:SOC", f"SocialRemix query error: {exc}")

            if self.chk_hd:
                try:
                    hd_candidates = HDArtworkFinder.search_all_hd_sources(
                        artist=self.artist or "",
                        title=self.title or q,
                    )
                except Exception as exc:
                    MusicatLogger.debug("RECONCILER:HD", f"HD Artwork query error: {exc}")

            # Fallback to Web/YouTube search if primary results lack genre or year
            has_genre_or_year = any(r.get("genre") or r.get("year") for r in all_results)
            if not has_genre_or_year:
                try:
                    from ..scrapers.web_enricher import WebEnricher
                    web_res = WebEnricher.search_genre_and_year(self.artist, self.title or q)
                    if web_res:
                        all_results.append(web_res)
                except Exception as exc:
                    MusicatLogger.debug("RECONCILER:WEB", f"WebEnricher query error: {exc}")

        except Exception as e:
            self.error_occurred.emit(str(e))
            return

        self.results_ready.emit(all_results, hd_candidates)


class ReconcilerDialog(QDialog):
    """Interactive multi-source discrepancy resolution and HD cover injector."""

    metadata_reconciled = Signal(dict)

    def __init__(self, track: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.track = track
        self.current_report: Optional[DiscrepancyReport] = None
        self.selected_image_bytes: Optional[bytes] = None
        self.search_worker: Optional[ReconcilerSearchWorker] = None

        filename = self.track.get("filename") or Path(self.track.get("filepath", "")).name
        self.setWindowTitle(_t("reconciler_dialog_title", "Revisione e Conferma Metadati — {filename}", filename=filename))
        self.setMinimumSize(920, 620)
        self.resize(1040, 720)
        self.setSizeGripEnabled(True)

        self._init_ui()
        self._start_search()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(14, 14, 14, 14)

        # Header Search Query Bar
        q_bar = QHBoxLayout()
        lbl_q = QLabel(_t("reconciler_lbl_query", "<b>Query di Ricerca:</b>"))
        q_bar.addWidget(lbl_q)

        self.txt_query = QLineEdit()
        art = self.track.get("artist") or ""
        tit = self.track.get("title") or Path(self.track.get("filepath", "")).stem
        self.txt_query.setText(f"{art} {tit}".strip())
        self.txt_query.setClearButtonEnabled(True)

        self.btn_search = QPushButton(_t("reconciler_btn_search", "🔎 Avvia Ricerca Online"))
        self.btn_search.setObjectName("PrimaryButton")
        self.btn_search.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        self.btn_search.clicked.connect(self._start_search)

        q_bar.addWidget(self.txt_query, 3)
        q_bar.addWidget(self.btn_search, 1)
        main_layout.addLayout(q_bar)

        # Sources Checkboxes
        src_box = QHBoxLayout()
        src_box.addWidget(QLabel(_t("reconciler_lbl_sources", "Fonti Attive:")))
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
        content_layout.setSpacing(12)

        # Discrepancy Table
        table_group = QGroupBox(_t("reconciler_group_table", "Riconciliazione Metadati e Conflitti"))
        table_layout = QVBoxLayout(table_group)

        self.table_discrepancies = QTableWidget()
        self.table_discrepancies.setColumnCount(4)
        self.table_discrepancies.setHorizontalHeaderLabels([
            _t("reconciler_col_field", "Campo"),
            _t("reconciler_col_current", "Valore Attuale"),
            _t("reconciler_col_found", "Valore Rilevato (Online)"),
            _t("reconciler_col_chosen", "Valore da Applicare"),
        ])
        self.table_discrepancies.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_discrepancies.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_discrepancies.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_discrepancies.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_discrepancies.verticalHeader().setDefaultSectionSize(36)
        self.table_discrepancies.setStyleSheet("""
            QTableWidget {
                gridline-color: #2b3040;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 4px 6px;
            }
            QComboBox {
                padding: 3px 6px;
                min-height: 24px;
                font-size: 11px;
            }
        """)

        table_layout.addWidget(self.table_discrepancies)
        content_layout.addWidget(table_group, 3)

        # Artwork Panel
        art_group = QGroupBox(_t("reconciler_group_artwork", "Copertina HD Album"))
        art_layout = QVBoxLayout(art_group)

        self.lbl_cover_preview = QLabel(_t("reconciler_status_querying", "Ricerca in corso..."))
        self.lbl_cover_preview.setFixedSize(220, 220)
        self.lbl_cover_preview.setStyleSheet("border: 1px dashed #3a3f52; background-color: #14161f; border-radius: 6px;")
        self.lbl_cover_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_art_info = QLabel(_t("reconciler_art_none", "Nessuna copertina selezionata"))
        self.lbl_art_info.setStyleSheet("color: #8c92a4; font-size: 11px;")

        self.cmb_art_options = QComboBox()
        self.cmb_art_options.currentIndexChanged.connect(self._on_artwork_selected)

        self.chk_save_folder_copy = QCheckBox(_t("reconciler_chk_save_local", "Salva copia come cover.jpg nella cartella"))
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
        self.progress_bar.setMaximumHeight(8)
        main_layout.addWidget(self.progress_bar)

        bottom_bar = QHBoxLayout()
        self.lbl_status = QLabel(_t("reconciler_status_ready", "Pronto"))
        self.lbl_status.setStyleSheet("color: #8c92a4; font-size: 12px;")

        self.btn_cancel = QPushButton(_t("reconciler_btn_cancel", "Annulla"))
        self.btn_apply = QPushButton(_t("reconciler_btn_apply", "Salva Modifiche nei File"))
        self.btn_apply.setObjectName("PrimaryButton")
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #16a34a;
                color: #ffffff;
                font-weight: bold;
                padding: 7px 18px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #15803d;
            }
            QPushButton:disabled {
                background-color: #4b5563;
                color: #9ca3af;
            }
        """)
        self.btn_apply.setEnabled(False)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply.clicked.connect(self._apply_reconciliation)

        bottom_bar.addWidget(self.lbl_status)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self.btn_cancel)
        bottom_bar.addWidget(self.btn_apply)
        main_layout.addLayout(bottom_bar)

        self.combos_by_field: Dict[str, QComboBox] = {}
        self.hd_candidates: List[Any] = []

    def _start_search(self) -> None:
        q = self.txt_query.text().strip()
        if not q:
            return

        self.btn_search.setEnabled(False)
        self.lbl_status.setText(_t("reconciler_status_querying", "Interrogazione fonti online in corso..."))
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.lbl_cover_preview.setText("Ricerca in corso...")

        # Start non-blocking QThread
        self.search_worker = ReconcilerSearchWorker(
            query=q,
            artist=self.track.get("artist") or "",
            title=self.track.get("title") or q,
            chk_bp=self.chk_bp.isChecked(),
            chk_tx=self.chk_tx.isChecked(),
            chk_disc=self.chk_disc.isChecked(),
            chk_mb=self.chk_mb.isChecked(),
            chk_soc=self.chk_soc.isChecked(),
            chk_hd=self.chk_hd.isChecked(),
        )
        self.search_worker.results_ready.connect(self._on_search_completed)
        self.search_worker.error_occurred.connect(self._on_search_error)
        self.search_worker.start()

    def _on_search_error(self, err_msg: str) -> None:
        self.progress_bar.setVisible(False)
        self.btn_search.setEnabled(True)
        self.lbl_status.setText(f"Errore durante la ricerca: {err_msg}")

    def _on_search_completed(self, all_results: List[Dict[str, Any]], hd_candidates: List[Any]) -> None:
        self.progress_bar.setVisible(False)
        self.btn_search.setEnabled(True)
        self.hd_candidates = hd_candidates

        q = self.txt_query.text().strip()
        # Analyze discrepancies
        self.current_report = MetadataReconciler.analyze_discrepancies(
            track_query=q,
            results_from_sources=all_results,
            current_file_tags=self.track,
        )

        self._render_discrepancies(self.current_report)
        self._populate_artwork_candidates(self.hd_candidates)
        self.btn_apply.setEnabled(len(all_results) > 0 or len(self.hd_candidates) > 0 or bool(self.track))
        sources_count = len(self.current_report.sources_participated)
        self.lbl_status.setText(
            _t(
                "reconciler_status_done",
                "Completato. Metadati recuperati da {count} risultati across {sources} fonti.",
                count=len(all_results),
                sources=sources_count,
            )
        )

    def _render_discrepancies(self, report: DiscrepancyReport) -> None:
        self.table_discrepancies.setRowCount(0)
        self.combos_by_field.clear()

        rows = list(report.fields.items())
        self.table_discrepancies.setRowCount(len(rows))

        for idx, (fld_name, disc) in enumerate(rows):
            # Column 0: Friendly Localized Field name
            friendly_name = FIELD_TRANSLATIONS.get(fld_name, fld_name.replace("_", " ").title())
            item_fld = QTableWidgetItem(friendly_name)
            item_fld.setFlags(item_fld.flags() & ~Qt.ItemFlag.ItemIsEditable)

            # Column 1: Current Local Value
            cur_local = str(self.track.get(fld_name) or "").strip()
            item_cur = QTableWidgetItem(cur_local if cur_local else "-")
            item_cur.setFlags(item_cur.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if not cur_local:
                item_cur.setForeground(Qt.GlobalColor.gray)

            # Column 2: Available Values summary from online sources (excluding Current File)
            online_sources = {s: v for s, v in disc.values_by_source.items() if s != "Current File"}
            summary_parts = [f"[{src}]: {val}" for src, val in online_sources.items()]
            summary_text = "; ".join(summary_parts) if summary_parts else "-"
            item_summary = QTableWidgetItem(summary_text)
            item_summary.setFlags(item_summary.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if disc.has_conflict:
                item_summary.setForeground(Qt.GlobalColor.yellow)

            # Column 3: Combo to choose which value to apply
            cmb_choice = QComboBox()
            cmb_choice.addItem("<Nessuno / Lascia vuoto>", "")

            default_idx = 0
            opt_idx = 1

            # Option for current value
            if cur_local:
                cmb_choice.addItem(f"Attuale: {cur_local}", cur_local)
                default_idx = opt_idx
                opt_idx += 1

            # Options for online sources
            for src_name, src_val in online_sources.items():
                if str(src_val).strip():
                    cmb_choice.addItem(f"{src_name}: {src_val}", src_val)
                    if disc.recommended_value is not None and str(src_val).strip() == str(disc.recommended_value).strip():
                        default_idx = opt_idx
                    opt_idx += 1

            cmb_choice.setCurrentIndex(default_idx)
            self.combos_by_field[fld_name] = cmb_choice

            self.table_discrepancies.setItem(idx, 0, item_fld)
            self.table_discrepancies.setItem(idx, 1, item_cur)
            self.table_discrepancies.setItem(idx, 2, item_summary)
            self.table_discrepancies.setCellWidget(idx, 3, cmb_choice)

    def _populate_artwork_candidates(self, candidates: List) -> None:
        self.cmb_art_options.clear()
        self.cmb_art_options.addItem(_t("reconciler_art_keep", "Mantieni copertina esistente"), None)

        for c in candidates:
            self.cmb_art_options.addItem(f"{c.source} ({c.dimension_label})", c.image_url)

        if candidates:
            self.cmb_art_options.setCurrentIndex(1)
        else:
            self.lbl_cover_preview.setText(_t("reconciler_art_none", "Nessuna copertina trovata"))

    def _on_artwork_selected(self, index: int) -> None:
        url = self.cmb_art_options.currentData()
        if not url:
            self.lbl_cover_preview.setText("Copertina Esistente")
            self.selected_image_bytes = None
            return

        self.lbl_cover_preview.setText("Download copertina...")
        data = HDArtworkFinder.download_image(url)
        if data:
            self.selected_image_bytes = data
            img = QImage.fromData(data)
            pix = QPixmap.fromImage(img).scaled(
                210, 210, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_cover_preview.setPixmap(pix)
            self.lbl_art_info.setText(f"Dimensione: {len(data) // 1024} KB | Ris: {img.width()}x{img.height()} px")
        else:
            self.lbl_cover_preview.setText("Download Fallito")

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

        # Clean separation: If title contains " - " and artist is empty, separate cleanly
        t_val = str(merged_tags.get("title") or self.track.get("title") or "").strip()
        a_val = str(merged_tags.get("artist") or self.track.get("artist") or "").strip()
        if " - " in t_val and (not a_val or a_val.lower() in ("various", "unknown")):
            parts = t_val.split(" - ", 1)
            merged_tags["artist"] = parts[0].strip()
            merged_tags["title"] = parts[1].strip()

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
                "Salvataggio Completato",
                f"Metadati riconciliati e salvati fisicamente con successo nel file:\n{Path(filepath).name}",
            )
            self.metadata_reconciled.emit(updated_record)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Errore di Scrittura", f"Impossibile scrivere i tag nel file: {e}")
