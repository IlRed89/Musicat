"""
Dedicated File Organizer & Sorter View for Musicat.
Provides interactive physical library organization, dynamic pattern dispatching,
and dry-run preview simulation.
"""

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from ...core.i18n import _t
from ..sorter_dialog import SorterDialog


class OrganizerView(SorterDialog):
    """Dedicated File Organizer workspace view and physical file dispatcher."""

    back_requested = Signal()

    def __init__(self, selected_tracks: Optional[List[Dict[str, Any]]] = None, parent: Optional[QWidget] = None, **kwargs: Any):
        tracks = selected_tracks if selected_tracks is not None else kwargs.get("tracks")
        super().__init__(selected_tracks=tracks, parent=parent)

        if hasattr(self, "btn_close"):
            self.btn_close.setText(_t("sorter_btn_back", "◀ Torna alla Libreria"))
            try:
                self.btn_close.clicked.disconnect()
            except Exception:
                pass
            self.btn_close.clicked.connect(self._on_back_clicked)

    def _on_back_clicked(self) -> None:
        self.back_requested.emit()
        if self.isWindow():
            self.reject()

    def set_selected_tracks(self, tracks: Optional[List[Dict[str, Any]]] = None) -> None:
        """Dynamically pre-populates organizer with tracks selected in the library."""
        self.selected_tracks = list(tracks or [])
        count = len(self.selected_tracks)
        if hasattr(self, "radio_selected"):
            self.radio_selected.setText(
                _t("sorter_src_selected", "Tracce selezionate nella libreria ({count} tracce)", count=count)
            )
            self.radio_selected.setChecked(count > 0)
        if hasattr(self, "radio_folder"):
            self.radio_folder.setChecked(count == 0)


__all__ = ["OrganizerView", "SorterDialog"]
