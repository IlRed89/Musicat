"""
Multi-Source Reconciliation Dialog for Musicat.

Detects and resolves metadata discrepancies across Beatport, Traxsource, Discogs,
MusicBrainz, Tunebat, Rate Your Music, Web/YouTube, and HD Cover Art providers.
Presents a dedicated Conflict Card per conflicting field (Titolo, Artista, Genere, Anno, BPM, Key)
with radio buttons per source and a custom input option, writing verified tags physically into the file.
Non-blocking asynchronous background execution ensures zero GUI freezing.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
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
from ..scrapers.providers.acoustic_discovery import TunebatSongBpmProvider
from ..scrapers.providers.discography import RateYourMusicProvider
from ..tags.editor import AudioTagEditor
from ..core.logger import MusicatLogger
from ..core.i18n import _t


FIELD_METADATA = {
    "title": ("Titolo", "🎵"),
    "artist": ("Artista", "🎤"),
    "genre": ("Genere", "🏷️"),
    "year": ("Anno", "📅"),
    "bpm": ("BPM", "⚡"),
    "musical_key": ("Chiave Musicale", "🔑"),
    "camelot_key": ("Chiave Camelot", "🎯"),
    "key": ("Chiave Musicale (Key)", "🔑"),
    "label": ("Etichetta", "🏢"),
    "remixer": ("Remixer", "🎧"),
    "album": ("Album", "💿"),
    "catalog_number": ("Num. Catalogo", "🔢"),
    "format": ("Formato", "📦"),
    "artwork_url": ("Copertina HD", "🖼️"),
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

            # Specialized Tunebat / SongBPM check for acoustic BPM and Key
            try:
                tb_res = TunebatSongBpmProvider().search_track(self.title or q, self.artist)
                if tb_res:
                    all_results.append(tb_res.to_dict())
            except Exception as exc:
                MusicatLogger.debug("RECONCILER:TUNEBAT", f"Tunebat query error: {exc}")

            # Specialized Rate Your Music check for micro-genres
            try:
                rym_res = RateYourMusicProvider().search_track(self.title or q, self.artist)
                if rym_res:
                    all_results.append(rym_res.to_dict())
            except Exception as exc:
                MusicatLogger.debug("RECONCILER:RYM", f"RYM query error: {exc}")

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


class ConflictFieldCard(QFrame):
    """Visual card widget for a single conflicting metadata field.

    Renders a group of radio buttons corresponding to each source,
    plus an editable custom value radio button.
    """

    def __init__(
        self,
        field_name: str,
        source_values: Dict[str, Any],
        recommended_val: Any = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.field_name = field_name
        self.source_values = source_values
        self.btn_group = QButtonGroup(self)
        self.radio_options: Dict[QRadioButton, Any] = {}

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            ConflictFieldCard {
                background-color: #1a1d29;
                border: 1px solid #2d3348;
                border-radius: 8px;
                padding: 10px;
                margin-bottom: 6px;
            }
            ConflictFieldCard:hover {
                border-color: #3b82f6;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Header with icon and field name
        friendly_label, icon = FIELD_METADATA.get(field_name, (field_name.replace("_", " ").title(), "📝"))
        lbl_header = QLabel(f"{icon}  <b>{friendly_label}</b>")
        lbl_header.setStyleSheet("font-size: 13px; font-weight: bold; color: #38bdf8;")
        layout.addWidget(lbl_header)

        # Radio options per source
        first_rb: Optional[QRadioButton] = None
        checked_set = False

        for src_name, val in source_values.items():
            if val is None or str(val).strip() == "":
                continue
            rb = QRadioButton(f"[{src_name}]: {val}")
            rb.setStyleSheet("""
                QRadioButton {
                    font-size: 12px;
                    color: #e2e8f0;
                    padding: 3px 0;
                }
                QRadioButton:checked {
                    font-weight: bold;
                    color: #60a5fa;
                }
            """)
            self.btn_group.addButton(rb)
            self.radio_options[rb] = val
            layout.addWidget(rb)

            if first_rb is None:
                first_rb = rb

            # Pre-select recommended consensus value
            if recommended_val is not None and str(val).strip().lower() == str(recommended_val).strip().lower():
                rb.setChecked(True)
                checked_set = True

        # Custom value row
        custom_layout = QHBoxLayout()
        custom_layout.setSpacing(8)

        self.rb_custom = QRadioButton(_t("reconciler_custom_radio", "Personalizzato:"))
        self.rb_custom.setStyleSheet("""
            QRadioButton {
                font-size: 12px;
                color: #e2e8f0;
            }
            QRadioButton:checked {
                font-weight: bold;
                color: #34d399;
            }
        """)
        self.btn_group.addButton(self.rb_custom)

        self.txt_custom = QLineEdit()
        self.txt_custom.setPlaceholderText(_t("reconciler_custom_hint", "Digita valore personalizzato manuale..."))
        self.txt_custom.setStyleSheet("""
            QLineEdit {
                background-color: #11131a;
                border: 1px solid #334155;
                border-radius: 4px;
                color: #ffffff;
                padding: 4px 8px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #34d399;
            }
        """)

        # Auto-check custom radio when typing in line edit
        self.txt_custom.textChanged.connect(self._on_custom_text_changed)
        self.rb_custom.toggled.connect(self._on_custom_radio_toggled)

        custom_layout.addWidget(self.rb_custom)
        custom_layout.addWidget(self.txt_custom, 1)
        layout.addLayout(custom_layout)

        # Fallback selection if no recommended value matched
        if not checked_set and first_rb is not None:
            first_rb.setChecked(True)

    def _on_custom_text_changed(self, text: str) -> None:
        if text.strip():
            self.rb_custom.setChecked(True)

    def _on_custom_radio_toggled(self, checked: bool) -> None:
        if checked:
            self.txt_custom.setFocus()

    def get_selected_value(self) -> Any:
        """Returns the chosen value for this field."""
        if self.rb_custom.isChecked():
            val = self.txt_custom.text().strip()
            return val if val else None

        for rb, val in self.radio_options.items():
            if rb.isChecked():
                return val

        return None


class ReconciliationDialog(QDialog):
    """Modal Conflict Reconciliation & Metadata Resolution Dialog.

    Displays conflicting metadata across sources (Titolo, Artista, Genere, Anno, BPM, Key)
    with radio buttons and custom input, saving confirmed tags directly to the audio file.
    """

    metadata_reconciled = Signal(dict)

    def __init__(
        self,
        track: Dict[str, Any],
        conflicts: Optional[Dict[str, Dict[str, Any]]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.track = dict(track)
        self.predefined_conflicts = conflicts or {}
        self.current_report: Optional[DiscrepancyReport] = None
        self.selected_image_bytes: Optional[bytes] = None
        self.search_worker: Optional[ReconcilerSearchWorker] = None
        self.field_cards: Dict[str, ConflictFieldCard] = {}
        self.hd_candidates: List[Any] = []

        filename = self.track.get("filename") or Path(self.track.get("filepath", "")).name
        self.setWindowTitle(_t("reconciler_conflict_title", "Riconciliazione Conflitti — {filename}", filename=filename))
        self.setModal(True)
        self.setMinimumSize(940, 640)
        self.resize(1060, 720)
        self.setSizeGripEnabled(True)

        self._init_ui()

        # If conflicts were already provided, render them immediately;
        # otherwise, trigger online multi-source query.
        if self.predefined_conflicts:
            self._render_from_dict_conflicts(self.predefined_conflicts)
            # Also search for HD artwork in the background
            self._start_artwork_search()
        else:
            self._start_search()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # Header Banner
        header_banner = QFrame()
        header_banner.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        h_box = QVBoxLayout(header_banner)
        h_box.setContentsMargins(8, 6, 8, 6)

        lbl_instruct = QLabel(
            _t(
                "reconciler_conflict_banner",
                "⚠️ <b>Risoluzione Discrepanze Metadati:</b> Le fonti di analisi hanno restituito valori discordanti.<br>"
                "Seleziona il valore da considerare valido tramite il pulsante radio corrispondente, oppure digita un valore manuale personalizzato prima del salvataggio.",
            )
        )
        lbl_instruct.setStyleSheet("font-size: 12px; color: #94a3b8; line-height: 1.4;")
        lbl_instruct.setWordWrap(True)
        h_box.addWidget(lbl_instruct)
        main_layout.addWidget(header_banner)

        # Search Query Bar
        q_bar = QHBoxLayout()
        lbl_q = QLabel(_t("reconciler_lbl_query", "<b>Query:</b>"))
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
        src_box.addWidget(QLabel(_t("reconciler_lbl_sources", "Fonti:")))
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

        # Content Split Layout: Scrollable Conflict Cards on Left + HD Cover on Right
        content_layout = QHBoxLayout()
        content_layout.setSpacing(14)

        # Left: Scroll area with conflict cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #27272a;
                background-color: #12141c;
                border-radius: 6px;
            }
        """)

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(10, 10, 10, 10)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch()
        self.scroll_area.setWidget(self.cards_container)

        content_layout.addWidget(self.scroll_area, 3)

        # Right: Artwork Panel
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

        self.chk_save_folder_copy = QCheckBox(_t("reconciler_chk_save_local", "Salva copia come cover.jpg"))
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
        self.btn_apply = QPushButton(_t("reconciler_btn_apply", "💾 Salva Modifiche nei File"))
        self.btn_apply.setObjectName("PrimaryButton")
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #16a34a;
                color: #ffffff;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #15803d;
            }
            QPushButton:disabled {
                background-color: #4b5563;
                color: #9ca3af;
            }
        """)
        self.btn_apply.clicked.connect(self._apply_reconciliation)
        self.btn_cancel.clicked.connect(self.reject)

        bottom_bar.addWidget(self.lbl_status)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self.btn_cancel)
        bottom_bar.addWidget(self.btn_apply)
        main_layout.addLayout(bottom_bar)

    def _clear_cards(self) -> None:
        """Clears all existing conflict cards from the layout."""
        self.field_cards.clear()
        while self.cards_layout.count() > 0:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _render_from_dict_conflicts(self, conflicts: Dict[str, Dict[str, Any]]) -> None:
        """Builds conflict cards directly from a dictionary of conflicting fields."""
        self._clear_cards()

        # Priority order of fields to render
        priority_order = ["title", "artist", "genre", "year", "bpm", "musical_key", "camelot_key", "key"]
        rendered_keys = set()

        for fld in priority_order:
            if fld in conflicts:
                source_vals = dict(conflicts[fld])
                # Ensure current file value is available
                if fld in self.track and "Attuale" not in source_vals and "File Attuale" not in source_vals:
                    cur_v = self.track.get(fld)
                    if cur_v:
                        source_vals["File Attuale"] = cur_v
                card = ConflictFieldCard(fld, source_vals, parent=self.cards_container)
                self.cards_layout.addWidget(card)
                self.field_cards[fld] = card
                rendered_keys.add(fld)

        # Any remaining fields
        for fld, source_vals in conflicts.items():
            if fld not in rendered_keys:
                card = ConflictFieldCard(fld, dict(source_vals), parent=self.cards_container)
                self.cards_layout.addWidget(card)
                self.field_cards[fld] = card

        self.cards_layout.addStretch()
        self.btn_apply.setEnabled(len(self.field_cards) > 0)
        self.lbl_status.setText(f"Rilevati {len(self.field_cards)} campi con discrepanze.")

    def _start_artwork_search(self) -> None:
        """Searches specifically for HD artwork."""
        q = self.txt_query.text().strip()
        art = self.track.get("artist") or ""
        tit = self.track.get("title") or q
        try:
            candidates = HDArtworkFinder.search_all_hd_sources(artist=art, title=tit)
            self._populate_artwork_candidates(candidates)
        except Exception as exc:
            MusicatLogger.debug("RECONCILER:ARTWORK", f"Artwork search error: {exc}")

    def _start_search(self) -> None:
        """Starts asynchronous online search across providers."""
        q = self.txt_query.text().strip()
        if not q:
            return

        self.btn_search.setEnabled(False)
        self.btn_apply.setEnabled(False)
        self.lbl_status.setText(_t("reconciler_status_querying", "Interrogazione fonti online in corso..."))
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.lbl_cover_preview.setText("Ricerca in corso...")

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
        self.current_report = MetadataReconciler.analyze_discrepancies(
            track_query=q,
            results_from_sources=all_results,
            current_file_tags=self.track,
        )

        self._render_from_report(self.current_report)
        self._populate_artwork_candidates(self.hd_candidates)
        self.btn_apply.setEnabled(len(self.field_cards) > 0 or len(all_results) > 0)
        self.lbl_status.setText(
            _t(
                "reconciler_status_done",
                "Completato. Trovate informazioni da {count} risultati.",
                count=len(all_results),
            )
        )

    def _render_from_report(self, report: DiscrepancyReport) -> None:
        """Renders conflict cards from DiscrepancyReport."""
        self._clear_cards()

        # Key fields to check for conflicts: Title, Artist, Genre, Year, BPM, Key
        target_fields = ["title", "artist", "genre", "year", "bpm", "musical_key", "camelot_key", "label", "album"]

        # First add fields that have conflicts
        conflicting_fields = [f for f in target_fields if f in report.fields and report.fields[f].has_conflict]
        # Then add fields that have at least one online value discovered
        other_fields = [
            f for f in target_fields
            if f in report.fields and not report.fields[f].has_conflict and len(report.fields[f].values_by_source) > 0
        ]

        fields_to_render = conflicting_fields if conflicting_fields else (conflicting_fields + other_fields)

        for fld in fields_to_render:
            disc = report.fields[fld]
            card = ConflictFieldCard(
                field_name=fld,
                source_values=disc.values_by_source,
                recommended_val=disc.recommended_value,
                parent=self.cards_container,
            )
            self.cards_layout.addWidget(card)
            self.field_cards[fld] = card

        if not fields_to_render:
            lbl_empty = QLabel("Nessuna discrepanza rilevata tra le fonti online e i tag locali.")
            lbl_empty.setStyleSheet("color: #94a3b8; font-size: 13px; padding: 20px;")
            self.cards_layout.addWidget(lbl_empty)

        self.cards_layout.addStretch()

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
        """Gathers selected values from conflict cards, writes physical audio tags, and closes."""
        resolved_tags: Dict[str, Any] = {}

        for fld, card in self.field_cards.items():
            val = card.get_selected_value()
            if val is not None and str(val).strip() != "":
                # Type sanitization
                if fld == "year":
                    if str(val).isdigit():
                        resolved_tags[fld] = int(val)
                elif fld == "bpm":
                    try:
                        resolved_tags[fld] = float(val)
                    except ValueError:
                        pass
                else:
                    resolved_tags[fld] = str(val).strip()

        filepath = self.track.get("filepath", "")
        if not filepath:
            QMessageBox.warning(self, "Attenzione", "Percorso del file audio non valido.")
            return

        # Clean separation: If title contains " - " and artist is empty, split cleanly
        t_val = str(resolved_tags.get("title") or self.track.get("title") or "").strip()
        a_val = str(resolved_tags.get("artist") or self.track.get("artist") or "").strip()
        if " - " in t_val and (not a_val or a_val.lower() in ("various", "unknown")):
            parts = t_val.split(" - ", 1)
            resolved_tags["artist"] = parts[0].strip()
            resolved_tags["title"] = parts[1].strip()

        try:
            # 1. Write merged metadata to physical audio tags
            AudioTagEditor.write_metadata(filepath, resolved_tags)

            # 2. Inject HD Artwork if selected
            if self.selected_image_bytes:
                save_local = self.chk_save_folder_copy.isChecked()
                HDArtworkFinder.apply_artwork_to_file(filepath, self.selected_image_bytes, save_folder_copy=save_local)
                resolved_tags["has_cover"] = 1

            # 3. Synchronize with updated record
            updated_record = dict(self.track)
            updated_record.update(resolved_tags)
            if "_conflicts" in updated_record:
                del updated_record["_conflicts"]

            QMessageBox.information(
                self,
                "Salvataggio Completato",
                f"Metadati riconciliati e salvati fisicamente con successo nel file:\n{Path(filepath).name}",
            )
            self.metadata_reconciled.emit(updated_record)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Errore di Scrittura", f"Impossibile scrivere i tag nel file: {e}")


# Alias ReconcilerDialog to ReconciliationDialog for backward compatibility
ReconcilerDialog = ReconciliationDialog

__all__ = ["ReconciliationDialog", "ReconcilerDialog", "ConflictFieldCard", "ReconcilerSearchWorker"]
