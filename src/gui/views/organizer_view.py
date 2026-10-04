"""
Dedicated File Organizer & Sorter View for Musicat.
Provides interactive physical library organization, dynamic pattern dispatching,
and dry-run preview simulation.
"""

from typing import Any, Dict, List, Optional
from PySide6.QtWidgets import QWidget

from ..sorter_dialog import SorterDialog


class OrganizerView(SorterDialog):
    """File Organizer view and dispatcher."""

    def __init__(self, selected_tracks: Optional[List[Dict[str, Any]]] = None, parent: Optional[QWidget] = None, **kwargs: Any):
        tracks = selected_tracks if selected_tracks is not None else kwargs.get("tracks")
        super().__init__(selected_tracks=tracks, parent=parent)


__all__ = ["OrganizerView", "SorterDialog"]
