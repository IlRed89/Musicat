"""
Online Scraping & Comparison Dialog for Musicat.
Provides side-by-side 'Before / After' diff view for Beatport, AcoustID,
MusicBrainz, and Discogs metadata before committing tags to disk.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..scrapers.beatport import BeatportScraper, ScrapedTrack
from ..scrapers.musicbrainz import MusicBrainzClient
from ..scrapers.discogs import DiscogsClient
from ..core.i18n import _t, I18n
from ..scrapers.acoustid import AcoustIDMatcher
from ..tags.editor import AudioTagEditor


class ScraperDialog(QDialog):
    """Search online metadata sources and preview Before/After changes."""

    metadata_applied = Signal(dict)

    FIELDS_TO_COMPARE = [
        ("Title", "title"),
        ("Artist", "artist"),
        ("Remixer", "remixer"),
        ("Label", "label"),
        ("Genre", "genre"),
        ("BPM", "bpm"),
        ("Camelot Key", "camelot_key"),
        ("Musical Key", "musical_key"),
        ("Year", "year"),
        ("Catalog #", "catalog_number"),
    ]

    def __init__(self, current_track: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.track = current_track
        self.current_scraped: Optional[Dict[str, Any]] = None
        self.downloaded_art_bytes: Optional[bytes] = None

        self.setWindowTitle(_t("scraper_title", "Musicat — Ricerca Metadati Online - {filename}", filename=self.track.get("filename")))
        self.resize(860, 650)

        self._init_ui()
        self._initial_search()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Provider & Query Bar
        query_bar = QHBoxLayout()
        query_bar.addWidget(QLabel(_t("scraper_provider", "Provider:")))

        self.cmb_provider = QComboBox()
        self.cmb_provider.addItem("💽 Discogs (Fonte Primaria: Label, Anno, Cat#, Formati)", "discogs")
        self.cmb_provider.addItem("🎧 Beatport (Priorità Club & Electronic BPM/Key)", "beatport")
        self.cmb_provider.addItem("🎼 MusicBrainz", "musicbrainz")
        self.cmb_provider.addItem("🔍 AcoustID (Impronta Acustica)", "acoustid")

        self.txt_query = QLineEdit()
        # Pre-fill query with artist and title or filename
        artist = self.track.get("artist") or ""
        title = self.track.get("title") or Path(self.track.get("filepath", "")).stem
        self.txt_query.setText(f"{artist} {title}".strip())

        self.btn_search = QPushButton(_t("scraper_btn_search", "🔎 Cerca"))
        self.btn_search.setObjectName("PrimaryButton")
        self.btn_search.setStyleSheet("""
            QPushButton {
                background-color: #0d6efd;
                color: #ffffff;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0b5ed7;
            }
        """)
        self.btn_search.clicked.connect(self._do_search)

        query_bar.addWidget(self.cmb_provider)
        query_bar.addWidget(self.txt_query, 2)
        query_bar.addWidget(self.btn_search)
        main_layout.addLayout(query_bar)

        # Candidates Table
        candidates_group = QGroupBox(_t("scraper_candidates", "Candidati Trovati"))
        cand_layout = QVBoxLayout(candidates_group)

        self.table_candidates = QTableWidget()
        self.table_candidates.setColumnCount(6)
        self.table_candidates.setHorizontalHeaderLabels([
            _t("col_title", "Titolo"),
            _t("col_artist", "Artista"),
            _t("scraper_col_mix", "Versione/Mix"),
            _t("col_label", "Etichetta"),
            _t("col_bpm", "BPM"),
            _t("col_musical_key", "Key"),
        ])
        self.table_candidates.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_candidates.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_candidates.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_candidates.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_candidates.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table_candidates.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table_candidates.itemSelectionChanged.connect(self._on_candidate_selected)

        cand_layout.addWidget(self.table_candidates)
        main_layout.addWidget(candidates_group, 2)

        # Side-by-Side Before / After Diff
        diff_group = QGroupBox(_t("scraper_diff_group", "Confronto Metadati Prima / Dopo"))
        diff_layout = QHBoxLayout(diff_group)

        self.table_diff = QTableWidget()
        self.table_diff.setColumnCount(3)
        self.table_diff.setHorizontalHeaderLabels([
            _t("scraper_col_field", "Campo"),
            _t("scraper_col_before", "Attuale (Prima)"),
            _t("scraper_col_after", "Trovato Online (Dopo)"),
        ])
        self.table_diff.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_diff.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_diff.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        diff_layout.addWidget(self.table_diff, 3)

        # Artwork Diff Panel
        art_panel = QVBoxLayout()
        art_panel.addWidget(QLabel(_t("scraper_art_label", "Cover Proposta:")))
        self.lbl_art = QLabel(_t("scraper_no_art", "Nessuna Immagine"))
        self.lbl_art.setFixedSize(140, 140)
        self.lbl_art.setStyleSheet("border: 1px dashed #ced4da; background-color: #f8f9fa; border-radius: 6px;")
        self.lbl_art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        art_panel.addWidget(self.lbl_art)
        art_panel.addStretch()

        diff_layout.addLayout(art_panel, 1)
        main_layout.addWidget(diff_group, 3)

        # Bottom Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.btn_cancel = QPushButton(_t("settings_btn_cancel", "Annulla"))
        self.btn_apply = QPushButton(_t("scraper_btn_apply", "⚡ Applica Metadati al File"))
        self.btn_apply.setObjectName("PrimaryButton")
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #198754;
                color: #ffffff;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #157347;
            }
            QPushButton:disabled {
                background-color: #e9ecef;
                color: #adb5bd;
            }
        """)
        self.btn_apply.setEnabled(False)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply.clicked.connect(self._apply_scraped)

        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_apply)
        main_layout.addLayout(btn_box)

        self.candidates_data: List[Dict[str, Any]] = []

    def _initial_search(self) -> None:
        if self.txt_query.text().strip():
            self._do_search()

    def _do_search(self) -> None:
        provider = self.cmb_provider.currentData()
        q = self.txt_query.text().strip()

        self.table_candidates.setRowCount(0)
        self.candidates_data.clear()
        self.btn_apply.setEnabled(False)

        if provider == "beatport":
            tracks = BeatportScraper.search_tracks(q)
            self.candidates_data = [t.to_dict() for t in tracks]
        elif provider == "musicbrainz":
            self.candidates_data = MusicBrainzClient.search_track(q)
        elif provider == "discogs":
            self.candidates_data = DiscogsClient().search_releases(q)
        elif provider == "acoustid":
            matches = AcoustIDMatcher().identify_track(self.track.get("filepath", ""))
            self.candidates_data = [
                {"title": m.title, "artist": m.artist, "mix_name": "", "label": "", "bpm": None, "camelot_key": ""}
                for m in matches
            ]

        self.table_candidates.setRowCount(len(self.candidates_data))
        for r, c in enumerate(self.candidates_data):
            self.table_candidates.setItem(r, 0, QTableWidgetItem(str(c.get("title") or "")))
            self.table_candidates.setItem(r, 1, QTableWidgetItem(str(c.get("artist") or "")))
            self.table_candidates.setItem(r, 2, QTableWidgetItem(str(c.get("mix_name") or "")))
            self.table_candidates.setItem(r, 3, QTableWidgetItem(str(c.get("label") or "")))
            self.table_candidates.setItem(r, 4, QTableWidgetItem(f"{c['bpm']:.1f}" if c.get("bpm") else ""))
            self.table_candidates.setItem(r, 5, QTableWidgetItem(str(c.get("camelot_key") or c.get("musical_key") or "")))

        if self.candidates_data:
            self.table_candidates.selectRow(0)

    def _on_candidate_selected(self) -> None:
        sel = self.table_candidates.selectedIndexes()
        if not sel:
            return

        row = sel[0].row()
        if 0 <= row < len(self.candidates_data):
            cand = self.candidates_data[row]
            self.current_scraped = cand
            self._render_diff(cand)
            self.btn_apply.setEnabled(True)

    def _render_diff(self, scraped: Dict[str, Any]) -> None:
        self.table_diff.setRowCount(len(self.FIELDS_TO_COMPARE))

        for idx, (label, key) in enumerate(self.FIELDS_TO_COMPARE):
            cur_val = str(self.track.get(key) or "")
            new_val = str(scraped.get(key) or "")

            item_lbl = QTableWidgetItem(label)
            item_cur = QTableWidgetItem(cur_val)
            item_new = QTableWidgetItem(new_val)

            # Highlight diff
            if new_val and (new_val.lower() != cur_val.lower()):
                item_new.setForeground(Qt.GlobalColor.cyan)

            self.table_diff.setItem(idx, 0, item_lbl)
            self.table_diff.setItem(idx, 1, item_cur)
            self.table_diff.setItem(idx, 2, item_new)

        # Artwork preview
        art_url = scraped.get("artwork_url")
        if art_url:
            data = BeatportScraper.download_artwork(art_url)
            if data:
                self.downloaded_art_bytes = data
                img = QImage.fromData(data)
                pix = QPixmap.fromImage(img).scaled(130, 130, Qt.AspectRatioMode.KeepAspectRatio)
                self.lbl_art.setPixmap(pix)
                return
        self.lbl_art.setText(_t("scraper_no_art", "Nessuna Immagine"))

    def _apply_scraped(self) -> None:
        if not self.current_scraped:
            return

        fp = self.track.get("filepath", "")
        updates = {k: v for k, v in self.current_scraped.items() if v is not None and v != ""}

        # Clean non-tag keys
        for k in ("source", "url", "artwork_url", "mix_name", "catalog_number"):
            updates.pop(k, None)

        try:
            AudioTagEditor.write_metadata(fp, updates)
            if self.downloaded_art_bytes:
                AudioTagEditor.set_artwork(fp, self.downloaded_art_bytes)
                updates["has_cover"] = 1

            merged = dict(self.track)
            merged.update(updates)

            QMessageBox.information(
                self,
                _t("scraper_success_title", "Metadati Applicati"),
                _t("scraper_success_msg", "Metadati online salvati con successo nel file audio!"),
            )
            self.metadata_applied.emit(merged)
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self,
                _t("scraper_err_title", "Errore"),
                _t("scraper_err_msg", "Impossibile scrivere i metadati: {error}", error=str(e)),
            )
