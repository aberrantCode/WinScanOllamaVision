"""
File Details Table Model

Provides the QAbstractTableModel for displaying file analysis data in a table view.
"""

import os
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor


class FileDetailsTableModel(QAbstractTableModel):
    """
    Table model for file analysis details.

    Supports 19 columns with configurable visibility.
    """

    # Column definitions
    COLUMNS = [
        ("filename", "Filename", True),
        ("status", "Status", True),
        ("confidence", "Confidence", True),
        ("company", "Company", True),
        ("document_type", "Type", True),
        ("document_date", "Date", True),
        ("tax_related", "Tax Related", True),
        ("is_blank", "Is Blank", True),
        ("page_number", "Page", True),
        ("total_pages", "Total", True),
        ("rotation", "Rotation", True),
        ("file_size", "Size", True),
        ("modified_time", "Modified", True),
        ("analysis_time", "Analyzed", True),
        ("processing_duration", "Duration", False),
        ("model_used", "Model", False),
        ("provider", "Provider", False),
        ("cache_hit", "Cached", False),
        ("error_message", "Error", False),
        ("full_path", "Full Path", False),
        ("file_hash", "Hash", False),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._data: list[dict[str, Any]] = []
        self._visible_columns: list[int] = [
            i for i, (_, _, visible) in enumerate(self.COLUMNS) if visible
        ]

    def set_data(self, data: list[dict[str, Any]]):
        """Set the data for the model."""
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def set_visible_columns(self, visible_columns: list[int]):
        """Set which columns are visible."""
        self.beginResetModel()
        self._visible_columns = sorted(visible_columns)
        self.endResetModel()

    def get_visible_columns(self) -> list[int]:
        """Get list of visible column indices."""
        return self._visible_columns.copy()

    def get_row_data(self, row: int) -> dict[str, Any] | None:
        """Get the complete data for a specific row."""
        if 0 <= row < len(self._data):
            return self._data[row].copy()
        return None

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802, B008
        """Return the number of rows."""
        if parent.isValid():
            return 0
        return len(self._data)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802, B008
        """Return the number of visible columns."""
        if parent.isValid():
            return 0
        return len(self._visible_columns)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole) -> Any:
        """Return data for a specific cell."""
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if row >= len(self._data) or col >= len(self._visible_columns):
            return None

        actual_col = self._visible_columns[col]
        col_key, _, _ = self.COLUMNS[actual_col]
        row_data = self._data[row]
        value = row_data.get(col_key)

        if role == Qt.ItemDataRole.DisplayRole:
            return self._format_display_value(col_key, value, row_data)
        elif role == Qt.ItemDataRole.ToolTipRole:
            return self._format_tooltip(col_key, value, row_data)
        elif role == Qt.ItemDataRole.BackgroundRole:
            return self._get_background_color(col_key, value, row_data)
        elif role == Qt.ItemDataRole.ForegroundRole:
            return self._get_foreground_color(col_key, value, row_data)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return self._get_alignment(col_key)

        return None

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole
    ) -> Any:
        """Return header data."""
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole and section < len(self._visible_columns):
                actual_col = self._visible_columns[section]
                _, header, _ = self.COLUMNS[actual_col]
                return header
            elif role == Qt.ItemDataRole.ToolTipRole and section < len(self._visible_columns):
                actual_col = self._visible_columns[section]
                col_key, header, _ = self.COLUMNS[actual_col]
                return self._get_column_tooltip(col_key, header)

        elif orientation == Qt.Orientation.Vertical and role == Qt.ItemDataRole.DisplayRole:
            return str(section + 1)

        return None

    def _format_display_value(self, col_key: str, value: Any, row_data: dict) -> str:
        """Format value for display."""
        if value is None or value == "":
            return ""

        if col_key == "filename":
            return os.path.basename(str(value))
        elif col_key == "status":
            return str(value).title()
        elif col_key == "confidence":
            if isinstance(value, int | float):
                return f"{value:.1f}%"
            return str(value)
        elif col_key == "file_size":
            return self._format_file_size(value)
        elif col_key in ("modified_time", "analysis_time"):
            return self._format_datetime(value)
        elif col_key == "processing_duration":
            return self._format_duration(value)
        elif col_key in ("cache_hit", "tax_related", "is_blank"):
            return "Yes" if value else "No"
        elif col_key == "rotation":
            # Display rotation as degrees (0°, 90°, 180°, 270°)
            if isinstance(value, int | float):
                return f"{int(value)}°"
            return "0°"
        elif col_key == "error_message":
            # Truncate long error messages
            msg = str(value)
            return msg[:50] + "..." if len(msg) > 50 else msg
        elif col_key == "full_path":
            # Show truncated path
            path = str(value)
            if len(path) > 60:
                return "..." + path[-57:]
            return path
        elif col_key == "file_hash":
            # Show shortened hash
            hash_str = str(value)
            return hash_str[:8] if len(hash_str) > 8 else hash_str

        return str(value)

    def _format_tooltip(self, col_key: str, value: Any, row_data: dict) -> str:
        """Format tooltip for a cell."""
        if value is None or value == "":
            return f"{col_key}: (empty)"

        if col_key == "filename":
            full_path = row_data.get("full_path", value)
            return f"Full path: {full_path}"
        elif col_key == "error_message":
            return f"Error: {value}"
        elif col_key == "full_path":
            return str(value)
        elif col_key == "file_hash":
            return f"Full hash: {value}"
        elif col_key == "confidence":
            conf = float(value) if isinstance(value, int | float) else 0
            if conf >= 80:
                return f"High confidence: {conf:.1f}%"
            elif conf >= 50:
                return f"Medium confidence: {conf:.1f}%"
            else:
                return f"Low confidence: {conf:.1f}%"

        return f"{col_key}: {value}"

    def _get_background_color(self, col_key: str, value: Any, row_data: dict) -> QColor | None:
        """Get background color for a cell."""
        # Highlight rows with errors
        if row_data.get("error_message"):
            return QColor(255, 240, 240)  # Light red

        # Highlight low confidence
        if col_key == "confidence" and isinstance(value, int | float) and value < 50:
            return QColor(255, 245, 230)  # Light orange

        # Highlight cached items
        if col_key == "cache_hit" and value:
            return QColor(240, 255, 240)  # Light green

        return None

    def _get_foreground_color(self, col_key: str, value: Any, row_data: dict) -> QColor | None:
        """Get foreground color for a cell."""
        if row_data.get("error_message") and col_key == "status":
            return QColor(200, 0, 0)  # Red text

        return None

    def _get_alignment(self, col_key: str) -> Qt.AlignmentFlag:
        """Get text alignment for a column."""
        if col_key in (
            "confidence",
            "file_size",
            "page_number",
            "total_pages",
            "processing_duration",
            "rotation",
        ):
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        elif col_key in ("cache_hit", "tax_related", "is_blank"):
            return Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
        return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

    def _get_column_tooltip(self, col_key: str, header: str) -> str:
        """Get tooltip for column header."""
        tooltips = {
            "filename": "Name of the scanned file",
            "status": "Analysis status (Analyzed, Pending, Failed)",
            "confidence": "Confidence score from LLM analysis (0-100%)",
            "company": "Extracted company/organization name",
            "document_type": "Type of document (Invoice, Receipt, etc.)",
            "document_date": "Date extracted from document",
            "tax_related": "Whether document is related to taxes (W-2, 1099, tax returns, etc.)",
            "is_blank": "Whether the page appears to be blank or has no significant content",
            "page_number": "Page number (if detected)",
            "total_pages": "Total pages in document (if detected)",
            "rotation": "Suggested rotation in degrees (0, 90, 180, 270)",
            "file_size": "Size of file on disk",
            "modified_time": "Last modification time of file",
            "analysis_time": "When the file was analyzed",
            "processing_duration": "Time taken to analyze (seconds)",
            "model_used": "LLM model used for analysis",
            "provider": "LLM provider (Ollama, Claude, Gemini)",
            "cache_hit": "Whether result was loaded from cache",
            "error_message": "Error message (if analysis failed)",
            "full_path": "Complete file path",
            "file_hash": "MD5 hash of file content",
        }
        return tooltips.get(col_key, header)

    @staticmethod
    def _format_file_size(size: Any) -> str:
        """Format file size in human-readable format."""
        try:
            size = int(size)
            for unit in ["B", "KB", "MB", "GB"]:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        except (ValueError, TypeError):
            return str(size)

    @staticmethod
    def _format_datetime(dt: Any) -> str:
        """Format datetime for display (converts UTC to local timezone)."""
        if not dt:
            return "N/A"
        # Simple string conversion for now
        return str(dt)

    @staticmethod
    def _format_duration(duration: Any) -> str:
        """Format duration in seconds."""
        try:
            seconds = float(duration)
            if seconds < 1:
                return f"{seconds * 1000:.0f}ms"
            elif seconds < 60:
                return f"{seconds:.1f}s"
            else:
                minutes = int(seconds // 60)
                secs = int(seconds % 60)
                return f"{minutes}m {secs}s"
        except (ValueError, TypeError):
            return str(duration)
