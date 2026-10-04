"""
Smart Organizer & Sorter Dialog for Musicat.
Configures dynamic directory hierarchy rules, generates Dry Run previews,
and dispatches audio files across physical storage.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.i18n import _t, I18n
from ..organizer.sorter import SmartOrganizer, SortPlanItem


class SorterDialog(QDialog):
    """Smart File Dispatcher dialog with interactive Dry Run preview."""

    operation_completed = Signal(dict)

    def __init__(self, selected_tracks: Optional[List[Dict[str, Any]]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.selected_tracks = selected_tracks or []
        self.current_plan: List[SortPlanItem] = []

        self.setWindowTitle(_t("sorter_title", "Musicat — Organizzatore Smart & Smistatore File"))
        self.resize(920, 700)

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Title / Description
        title_lbl = QLabel(f"<b>{_t('sorter_heading', 'Organizzatore Smart & Smistamento Fisico dei File')}</b>")
        title_lbl.setStyleSheet("color: #0d6efd; font-size: 15px; font-weight: bold;")
        desc_lbl = QLabel(
            _t(
                "sorter_desc",
                "Organizza i file in alberi di cartelle dinamici basati su Anno, Genere, Intervalli BPM o Chiavi Camelot. "
                "Ispeziona sempre l'anteprima di Simulazione (Dry Run) prima di applicare modifiche fisiche.",
            )
        )
        desc_lbl.setStyleSheet("color: #6c757d;")
        desc_lbl.setWordWrap(True)
        main_layout.addWidget(title_lbl)
        main_layout.addWidget(desc_lbl)

        # Config Panel
        config_group = QGroupBox(_t("sorter_group_rules", "Regole di Smistamento & Destinazioni"))
        cfg_layout = QVBoxLayout(config_group)

        # Source Selection
        src_row = QHBoxLayout()
        self.radio_selected = QRadioButton(
            _t("sorter_src_selected", "Tracce selezionate nella libreria ({count} tracce)", count=len(self.selected_tracks))
        )
        self.radio_folder = QRadioButton(_t("sorter_src_folder", "Cartella sorgente su disco:"))
        self.radio_selected.setChecked(len(self.selected_tracks) > 0)
        self.radio_folder.setChecked(len(self.selected_tracks) == 0)

        self.txt_src_folder = QLineEdit()
        self.btn_browse_src = QPushButton(_t("sorter_browse", "Sfoglia..."))
        self.btn_browse_src.clicked.connect(self._browse_src)

        src_row.addWidget(self.radio_selected)
        src_row.addWidget(self.radio_folder)
        src_row.addWidget(self.txt_src_folder)
        src_row.addWidget(self.btn_browse_src)
        cfg_layout.addLayout(src_row)

        # Destination Folder
        dst_row = QHBoxLayout()
        dst_lbl = QLabel(_t("sorter_dest_dir", "Cartella di Destinazione:"))
        self.txt_dst_folder = QLineEdit()
        self.btn_browse_dst = QPushButton(_t("sorter_browse", "Sfoglia..."))
        self.btn_browse_dst.clicked.connect(self._browse_dst)

        dst_row.addWidget(dst_lbl)
        dst_row.addWidget(self.txt_dst_folder)
        dst_row.addWidget(self.btn_browse_dst)
        cfg_layout.addLayout(dst_row)

        # Rule Preset & Template
        rule_row = QHBoxLayout()
        rule_lbl = QLabel(_t("sorter_rule_label", "Regola di Organizzazione:"))
        self.cmb_presets = QComboBox()
        self.cmb_presets.addItem(_t("sorter_rule_genre", "Per Genere: {genre}/{artist} - {title}{ext}"), "{genre}/{artist} - {title}{ext}")
        self.cmb_presets.addItem(_t("sorter_rule_year", "Per Anno: {year}/{artist} - {title}{ext}"), "{year}/{artist} - {title}{ext}")
        self.cmb_presets.addItem(_t("sorter_rule_bpm", "Per Intervallo BPM: BPM {bpm_range}/{artist} - {title}{ext}"), "BPM {bpm_range}/{artist} - {title}{ext}")
        self.cmb_presets.addItem(_t("sorter_rule_camelot", "Per Chiave Camelot: Key {camelot_key}/{artist} - {title}{ext}"), "Key {camelot_key}/{artist} - {title}{ext}")
        self.cmb_presets.addItem(_t("sorter_rule_genre_bpm", "Genere + Intervallo BPM: {genre}/BPM {bpm_range}/{artist} - {title}{ext}"), "{genre}/BPM {bpm_range}/{artist} - {title}{ext}")
        self.cmb_presets.addItem(_t("sorter_rule_genre_year_bpm", "Genere + Anno + BPM: {genre}/{year}/BPM {bpm_range}/{artist} - {title}{ext}"), "{genre}/{year}/BPM {bpm_range}/{artist} - {title}{ext}")
        self.cmb_presets.addItem(_t("sorter_rule_custom", "Modello di Gerarchia Personalizzato"), "")

        self.txt_pattern = QLineEdit("{genre}/BPM {bpm_range}/{artist} - {title}{ext}")
        self.cmb_presets.currentIndexChanged.connect(self._on_preset_changed)

        rule_row.addWidget(rule_lbl)
        rule_row.addWidget(self.cmb_presets, 2)
        rule_row.addWidget(self.txt_pattern, 3)
        cfg_layout.addLayout(rule_row)

        # Options: BPM Step, Action (Copy/Move), Collision
        opt_row = QHBoxLayout()
        opt_row.addWidget(QLabel(_t("sorter_bpm_step", "Passo Intervallo BPM:")))
        self.spin_bpm_step = QSpinBox()
        self.spin_bpm_step.setRange(1, 20)
        self.spin_bpm_step.setValue(5)
        self.spin_bpm_step.setSuffix(" BPM")
        opt_row.addWidget(self.spin_bpm_step)

        opt_row.addWidget(QLabel(_t("sorter_operation", "Operazione:")))
        self.cmb_action = QComboBox()
        self.cmb_action.addItem(_t("sorter_op_copy", "Copia File (Sicuro)"), "copy")
        self.cmb_action.addItem(_t("sorter_op_move", "Sposta File (Smistamento Fisico)"), "move")
        opt_row.addWidget(self.cmb_action)

        opt_row.addWidget(QLabel(_t("sorter_collision", "Gestione Collisioni:")))
        self.cmb_collision = QComboBox()
        self.cmb_collision.addItem(_t("sorter_coll_rename", "Rinomina Automaticamente: Brano (1).mp3"), "rename")
        self.cmb_collision.addItem(_t("sorter_coll_overwrite", "Sovrascrivi File di Destinazione"), "overwrite")
        self.cmb_collision.addItem(_t("sorter_coll_skip", "Salta File Esistente"), "skip")
        opt_row.addWidget(self.cmb_collision)

        opt_row.addStretch()

        self.btn_dry_run = QPushButton(_t("sorter_btn_dry_run", "🔍 Genera Anteprima Simulazione (Dry Run)"))
        self.btn_dry_run.setObjectName("AccentButton")
        self.btn_dry_run.setStyleSheet("""
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
        self.btn_dry_run.clicked.connect(self._generate_dry_run)
        opt_row.addWidget(self.btn_dry_run)

        cfg_layout.addLayout(opt_row)
        main_layout.addWidget(config_group)

        # Preview Table
        preview_group = QGroupBox(_t("sorter_preview_group", "Piano di Anteprima Simulazione (Dry Run)"))
        prev_layout = QVBoxLayout(preview_group)

        self.table_preview = QTableWidget()
        self.table_preview.setColumnCount(5)
        self.table_preview.setHorizontalHeaderLabels([
            _t("sorter_col_status", "Stato"),
            _t("sorter_col_source", "File Sorgente"),
            _t("sorter_col_target", "Percorso Relativo Destinazione"),
            _t("sorter_col_action", "Azione"),
            _t("sorter_col_details", "Dettagli"),
        ])
        self.table_preview.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_preview.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_preview.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_preview.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_preview.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        prev_layout.addWidget(self.table_preview)
        main_layout.addWidget(preview_group)

        # Execution Progress & Controls
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        bottom_row = QHBoxLayout()
        self.lbl_summary = QLabel(_t("sorter_preview_empty", "Anteprima non ancora generata."))
        self.lbl_summary.setStyleSheet("color: #6c757d; font-size: 12px;")

        self.btn_close = QPushButton(_t("sorter_btn_close", "Chiudi"))
        self.btn_execute = QPushButton(_t("sorter_btn_execute", "⚡ Esegui Smistamento Fisico"))
        self.btn_execute.setObjectName("PrimaryButton")
        self.btn_execute.setStyleSheet("""
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
        self.btn_execute.setEnabled(False)

        self.btn_close.clicked.connect(self.reject)
        self.btn_execute.clicked.connect(self._execute_dispatch)

        bottom_row.addWidget(self.lbl_summary)
        bottom_row.addStretch()
        bottom_row.addWidget(self.btn_close)
        bottom_row.addWidget(self.btn_execute)

        main_layout.addLayout(bottom_row)

    def _browse_src(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, _t("sorter_dialog_src_title", "Seleziona Cartella Sorgente"))
        if folder:
            self.txt_src_folder.setText(folder)
            self.radio_folder.setChecked(True)

    def _browse_dst(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, _t("sorter_dialog_dst_title", "Seleziona Cartella di Destinazione"))
        if folder:
            self.txt_dst_folder.setText(folder)

    def _on_preset_changed(self, idx: int) -> None:
        pattern = self.cmb_presets.currentData()
        if pattern:
            self.txt_pattern.setText(pattern)

    def _generate_dry_run(self) -> None:
        dest_dir = self.txt_dst_folder.text().strip()
        if not dest_dir:
            QMessageBox.warning(
                self,
                _t("sorter_err_no_dest_title", "Destinazione Mancante"),
                _t("sorter_err_no_dest_msg", "Specifica una cartella di destinazione valida."),
            )
            return

        rule_pattern = self.txt_pattern.text().strip()
        if not rule_pattern:
            QMessageBox.warning(
                self,
                _t("sorter_err_no_pattern_title", "Pattern Mancante"),
                _t("sorter_err_no_pattern_msg", "Inserisci un pattern di cartella valido."),
            )
            return

        # Determine source items
        items_to_sort: List[Any] = []
        if self.radio_selected.isChecked() and self.selected_tracks:
            items_to_sort = self.selected_tracks
        elif self.txt_src_folder.text().strip():
            src_dir = Path(self.txt_src_folder.text().strip())
            if not src_dir.exists():
                QMessageBox.warning(
                    self,
                    _t("sorter_err_invalid_src_title", "Sorgente Non Valida"),
                    _t("sorter_err_invalid_src_msg", "La cartella sorgente selezionata non esiste."),
                )
                return
            from ..tags.editor import SUPPORTED_EXTENSIONS
            import os
            for root, _, files in os.walk(str(src_dir)):
                for f in files:
                    if Path(f).suffix.lower() in SUPPORTED_EXTENSIONS:
                        items_to_sort.append(os.path.join(root, f))
        else:
            QMessageBox.warning(
                self,
                _t("sorter_err_no_items_title", "Nessun Elemento"),
                _t("sorter_err_no_items_msg", "Nessuna traccia selezionata e nessuna cartella sorgente specificata."),
            )
            return

        if not items_to_sort:
            QMessageBox.information(
                self,
                _t("sorter_err_empty_title", "Nessun File Trovato"),
                _t("sorter_err_empty_msg", "Nessun file audio trovato da organizzare."),
            )
            return

        action = self.cmb_action.currentData()
        bpm_step = self.spin_bpm_step.value()
        collision = self.cmb_collision.currentData()

        self.current_plan = SmartOrganizer.build_plan(
            source_items=items_to_sort,
            dest_dir=dest_dir,
            rule_pattern=rule_pattern,
            action=action,
            bpm_step=bpm_step,
            collision_mode=collision,
        )

        # Populate Preview Table
        self.table_preview.setRowCount(len(self.current_plan))
        ok_count = 0
        collision_count = 0
        missing_count = 0

        for r, item in enumerate(self.current_plan):
            status_item = QTableWidgetItem(item.status)
            if item.status == "OK":
                status_item.setForeground(Qt.GlobalColor.green)
                ok_count += 1
            elif item.status == "COLLISION":
                status_item.setForeground(Qt.GlobalColor.yellow)
                collision_count += 1
            elif item.status == "MISSING_TAG":
                status_item.setForeground(Qt.GlobalColor.cyan)
                missing_count += 1
            else:
                status_item.setForeground(Qt.GlobalColor.red)

            src_item = QTableWidgetItem(Path(item.source_path).name)
            src_item.setToolTip(item.source_path)

            dst_item = QTableWidgetItem(item.relative_target)
            dst_item.setToolTip(item.target_path)

            act_item = QTableWidgetItem(item.action.upper())
            msg_item = QTableWidgetItem(item.message)

            self.table_preview.setItem(r, 0, status_item)
            self.table_preview.setItem(r, 1, src_item)
            self.table_preview.setItem(r, 2, dst_item)
            self.table_preview.setItem(r, 3, act_item)
            self.table_preview.setItem(r, 4, msg_item)

        self.lbl_summary.setText(
            _t(
                "sorter_summary",
                "<b>Riepilogo Piano:</b> Totale: {total} | Conforme: {ok} | Collisioni: {collision} | Tag Mancanti: {missing}",
                total=len(self.current_plan),
                ok=ok_count,
                collision=collision_count,
                missing=missing_count,
            )
        )
        self.btn_execute.setEnabled(len(self.current_plan) > 0)

    def _execute_dispatch(self) -> None:
        if not self.current_plan:
            return

        confirm = QMessageBox.question(
            self,
            _t("sorter_confirm_title", "Conferma Smistamento"),
            _t(
                "sorter_confirm_msg",
                "Sei sicuro di voler procedere con l'operazione '{action}' su {count} tracce nella destinazione?\n"
                "Questa operazione creerà fisicamente le cartelle e sposterà/copierà i file.",
                action=self.cmb_action.currentText(),
                count=len(self.current_plan),
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(self.current_plan))
        self.progress_bar.setValue(0)

        def progress_cb(current, total, item):
            self.progress_bar.setValue(current)

        result = SmartOrganizer.execute_plan(self.current_plan, progress_callback=progress_cb)
        self.progress_bar.setVisible(False)

        QMessageBox.information(
            self,
            _t("sorter_done_title", "Smistamento Completato"),
            _t(
                "sorter_done_msg",
                "Operazione completata con successo!\nCopiati/Spostati: {success}\nSaltati: {skipped}\nFalliti: {failed}",
                success=result["success"],
                skipped=result["skipped"],
                failed=result["failed"],
            ),
        )
        self.operation_completed.emit(result)
        self.accept()
