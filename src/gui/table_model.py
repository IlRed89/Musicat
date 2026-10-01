"""
High-Performance Virtual Table Model for Musicat.
Subclasses QAbstractTableModel to render 50,000+ tracks effortlessly with instantaneous sorting.
"""

from typing import Any, Dict, List, Optional
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor


class TrackTableModel(QAbstractTableModel):
    """Virtual Table Model optimized for large DJ libraries."""

    COLUMNS = [
        ("#", "id"),
        ("Cover", "has_cover"),
        ("Title", "title"),
        ("Artist", "artist"),
        ("Remixer", "remixer"),
        ("BPM", "bpm"),
        ("Camelot", "camelot_key"),
        ("Key", "musical_key"),
        ("Genre", "genre"),
        ("Year", "year"),
        ("Album", "album"),
        ("Label", "label"),
        ("Time", "duration"),
        ("Bitrate", "bitrate"),
        ("Energy", "energy_level"),
        ("Path", "filepath"),
    ]

    def __init__(self, tracks: Optional[List[Dict[str, Any]]] = None):
        super().__init__()
        self._tracks: List[Dict[str, Any]] = tracks or []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._tracks)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section][0]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._tracks)):
            return None

        track = self._tracks[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            val = track.get(col_key)
            if col_key == "id":
                return str(index.row() + 1)
            elif col_key == "has_cover":
                return "🖼️" if val else ""
            elif col_key == "bpm":
                return f"{val:.1f}" if (val is not None and val > 0) else ""
            elif col_key == "duration":
                if val:
                    mins = int(val // 60)
                    secs = int(val % 60)
                    return f"{mins}:{secs:02d}"
                return ""
            elif col_key == "bitrate":
                return f"{val}k" if val else ""
            elif col_key == "year":
                return str(val) if val else ""
            elif col_key == "energy_level":
                return f"⚡ {val}" if val else ""
            return str(val) if val is not None else ""

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col_key in ("id", "has_cover", "bpm", "camelot_key", "musical_key", "year", "duration", "bitrate", "energy_level"):
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        elif role == Qt.ItemDataRole.ForegroundRole:
            if col_key == "camelot_key":
                val = str(track.get("camelot_key", ""))
                if val.endswith("A"):  # Minor
                    return QColor("#c77dff")
                elif val.endswith("B"):  # Major
                    return QColor("#00d2ff")
            elif col_key == "bpm":
                return QColor("#38bdf8")

        return None

    def set_tracks(self, tracks: List[Dict[str, Any]]) -> None:
        """Replaces current dataset."""
        self.beginResetModel()
        self._tracks = tracks
        self.endResetModel()

    def get_track(self, row: int) -> Optional[Dict[str, Any]]:
        """Retrieves track dictionary for given row."""
        if 0 <= row < len(self._tracks):
            return self._tracks[row]
        return None

    def get_tracks_by_rows(self, rows: List[int]) -> List[Dict[str, Any]]:
        """Retrieves tracks for a list of row indices."""
        return [self._tracks[r] for r in rows if 0 <= r < len(self._tracks)]

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        """Sorts table data based on column."""
        if not self._tracks:
            return

        col_key = self.COLUMNS[column][1]
        reverse = (order == Qt.SortOrder.DescendingOrder)

        def sort_key(item: Dict[str, Any]):
            val = item.get(col_key)
            if val is None:
                return (0, "")
            if isinstance(val, (int, float)):
                return (1, val)
            return (2, str(val).lower())

        self.beginResetModel()
        self._tracks.sort(key=sort_key, reverse=reverse)
        self.endResetModel()
