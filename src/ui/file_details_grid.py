"""
File Analysis Grid Component

Provides a comprehensive grid view of all analyzed files with advanced filtering,
sorting, and data export capabilities.
"""

import csv
import json
import os
from datetime import datetime
from html import escape as html_escape
from typing import Any

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QAction, QColor, QFont, QPainter, QPixmap, QTransform
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.pannable_image_label import PannableImageLabel


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

    def __init__(self, parent=None):
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
        elif col_key in ("cache_hit", "tax_related"):
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
        elif col_key in ("cache_hit", "tax_related"):
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
        from ui.datetime_utils import format_datetime_for_display

        return format_datetime_for_display(dt, "%Y-%m-%d %I:%M %p")

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


class FileDetailsSortFilterProxyModel(QSortFilterProxyModel):
    """
    Proxy model for filtering and sorting file details.

    Supports:
    - Column-specific filters
    - Full-text search across all columns
    - Quick filter presets
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._column_filters: dict[str, Any] = {}
        self._search_text: str = ""
        self._quick_filter: str | None = None

    def set_filters(self, filters: dict[str, Any]):
        """Set column-specific filters."""
        self._column_filters = filters.copy()
        self.invalidateFilter()

    def set_search_text(self, text: str):
        """Set full-text search filter."""
        self._search_text = text.lower().strip()
        self.invalidateFilter()

    def set_quick_filter(self, filter_name: str | None):
        """Set quick filter preset."""
        self._quick_filter = filter_name
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        """Determine if a row should be visible."""
        model = self.sourceModel()
        if not isinstance(model, FileDetailsTableModel):
            return True

        row_data = model.get_row_data(source_row)
        if not row_data:
            return False

        # Apply quick filter
        if self._quick_filter and not self._apply_quick_filter(row_data):
            return False

        # Apply column filters
        for col_key, filter_value in self._column_filters.items():
            if not filter_value:
                continue

            row_value = row_data.get(col_key)

            # Handle different filter types
            if isinstance(filter_value, list | tuple | set):
                if row_value not in filter_value:
                    return False
            else:
                if str(row_value).lower() != str(filter_value).lower():
                    return False

        # Apply search text
        return not self._search_text or self._search_in_row(row_data)

    def _apply_quick_filter(self, row_data: dict[str, Any]) -> bool:
        """Apply quick filter logic."""
        if self._quick_filter == "high_confidence":
            confidence = row_data.get("confidence", 0)
            try:
                return float(confidence) >= 80
            except (ValueError, TypeError):
                return False

        elif self._quick_filter == "needs_review":
            confidence = row_data.get("confidence", 100)
            try:
                return float(confidence) < 80
            except (ValueError, TypeError):
                return True

        elif self._quick_filter == "multi_page":
            total_pages = row_data.get("total_pages")
            if total_pages is None:
                return False
            try:
                return int(total_pages) > 1
            except (ValueError, TypeError):
                return False

        elif self._quick_filter == "recent":
            analysis_time = row_data.get("analysis_time")
            if not analysis_time:
                return False
            try:
                if isinstance(analysis_time, str):
                    analysis_time = datetime.fromisoformat(analysis_time)
                if isinstance(analysis_time, datetime):
                    hours_ago = (datetime.now() - analysis_time).total_seconds() / 3600
                    return hours_ago < 24
            except (ValueError, TypeError):
                pass
            return False

        elif self._quick_filter == "has_errors":
            # Check if status is Failed or if there's an error message
            status = row_data.get("status", "")
            error_msg = row_data.get("error_message", "")
            return status == "Failed" or bool(error_msg)

        elif self._quick_filter == "missing_metadata":
            # Check if any key metadata field is missing or N/A
            company = row_data.get("company", "")
            document_type = row_data.get("document_type", "")
            document_date = row_data.get("document_date", "")

            # Missing if any field is empty, None, or 'N/A'
            company_missing = not company or company in ("N/A", "None", "")
            type_missing = not document_type or document_type in ("N/A", "None", "")
            date_missing = not document_date or document_date in ("N/A", "None", "")

            return company_missing or type_missing or date_missing

        elif self._quick_filter == "cached_only":
            return bool(row_data.get("cache_hit"))

        return True

    def _search_in_row(self, row_data: dict[str, Any]) -> bool:
        """Check if search text appears in any column."""
        search_text = self._search_text

        # Search in all string-like fields
        searchable_fields = [
            "filename",
            "company",
            "document_type",
            "document_date",
            "status",
            "error_message",
            "model_used",
            "provider",
            "full_path",
        ]

        for field in searchable_fields:
            value = row_data.get(field)
            if value and search_text in str(value).lower():
                return True

        return False


class FileDetailsDialog(QDialog):
    """
    Dialog showing detailed information for a single file.

    Displays:
    - File information
    - Analysis results
    - Extracted metadata
    - Raw LLM response
    """

    re_analyze_requested = pyqtSignal(str)  # Emits file path
    metadata_saved = pyqtSignal(str)  # Emits file path when metadata is saved

    def __init__(
        self,
        file_data: dict[str, Any],
        parent=None,
        analysis_db=None,
        metadata_db=None,
        config_manager=None,
    ):
        super().__init__(parent)
        self.file_data = file_data
        self.analysis_db = analysis_db  # Store database reference
        self.metadata_db = metadata_db  # Store metadata database reference
        self.setWindowTitle(
            f"File Details - {os.path.basename(file_data.get('filename', 'Unknown'))}"
        )
        self.setMinimumSize(1050, 800)  # Increased by 50% for better visibility

        # Debug logging for rotation persistence tracking
        from services.logging_service import get_logger

        logger = get_logger()
        logger.debug(
            f"[DIALOG INIT] FileDetailsDialog opened for {file_data.get('filename')} - "
            f"rotation (image_files): {file_data.get('rotation')}, "
            f"rotation_needed (analysis_results): {file_data.get('rotation_needed')}"
        )

        # Get theme from parent
        self.is_dark_mode = False
        if parent and hasattr(parent, "is_dark_mode"):
            self.is_dark_mode = parent.is_dark_mode
        self.theme_colors = self._get_theme_colors()

        self.accordion_sections: list[QWidget] = []  # Track accordion sections

        # Get config manager for zoom settings
        self.config_manager = config_manager
        if self.config_manager is None and parent and hasattr(parent, "config_manager"):
            self.config_manager = parent.config_manager

        # Read default zoom settings from config
        if self.config_manager:
            self.default_zoom_mode = (
                self.config_manager.get_setting("Theme", "default_zoom_mode_png", "fit_to_width")
                .lower()
                .replace(" ", "_")
            )
            self.default_zoom_percent = int(
                self.config_manager.get_setting("Theme", "default_zoom_percent_png", "100")
            )
        else:
            self.default_zoom_mode = "fit_to_width"
            self.default_zoom_percent = 100

        # Zoom and rotation controls
        self.zoom_level = 100  # Start at 100%
        self.rotation_angle = 0  # Rotation in degrees (0, 90, 180, 270)

        # Correct the file path if it's in a temp folder
        stored_path = self.file_data.get("full_path")
        filename = self.file_data.get("filename")
        if filename:
            basename = os.path.basename(filename)
            corrected_path = self._find_actual_file_path(stored_path, basename)
            if corrected_path and os.path.exists(corrected_path):
                # Update file_data with corrected path
                self.file_data["full_path"] = corrected_path

        self._init_ui()

    def _get_theme_colors(self):
        """Return color palette based on current theme"""
        if self.is_dark_mode:
            return {
                "bg_primary": "#1E1E1E",
                "bg_secondary": "#2D2D2D",
                "text_primary": "#E0E0E0",
                "text_secondary": "#B0B0B0",
                "border": "#4A4A4A",
                "accent": "#3B82F6",
            }
        else:
            return {
                "bg_primary": "#FFFFFF",
                "bg_secondary": "#F9FAFB",
                "text_primary": "#111827",
                "text_secondary": "#374151",
                "border": "#E5E7EB",
                "accent": "#3B82F6",
            }

    def _create_overlay_controls(self) -> QWidget:
        """Create compact overlaid zoom/rotate controls with tooltips."""
        # Color definitions
        gray_100 = "#F3F4F6"
        gray_300 = "#D1D5DB"
        gray_900 = "#111827"
        primary_pale = "#EFF6FF"
        primary = "#3B82F6"

        controls = QWidget()
        controls.setStyleSheet(f"""
            QWidget {{
                background: rgba(255, 255, 255, 0.95);
                border: 2px solid {gray_900};
                border-radius: 12px;
                padding: 4px;
            }}
        """)

        layout = QHBoxLayout(controls)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        layout.setSizeConstraint(QHBoxLayout.SizeConstraint.SetFixedSize)  # Shrink to fit content

        # Button style (doubled size)
        btn_style = f"""
            QPushButton {{
                background: {gray_100};
                color: {gray_900};
                border: 1px solid {gray_300};
                border-radius: 4px;
                font-size: 20px;
                font-weight: bold;
                min-width: 40px;
                max-width: 40px;
                min-height: 40px;
                max-height: 40px;
            }}
            QPushButton:hover {{
                background: {primary_pale};
                border-color: {primary};
            }}
        """

        # Zoom controls
        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setStyleSheet(btn_style)
        zoom_out_btn.setToolTip("Zoom Out (25%)")
        zoom_out_btn.clicked.connect(self._on_zoom_out)
        layout.addWidget(zoom_out_btn)

        self.zoom_spinner = QSpinBox()
        self.zoom_spinner.setRange(25, 400)
        self.zoom_spinner.setValue(100)
        self.zoom_spinner.setSuffix("%")
        self.zoom_spinner.setFixedWidth(110)
        self.zoom_spinner.setFixedHeight(40)
        self.zoom_spinner.setToolTip("Zoom Level (25-400%)")
        self.zoom_spinner.setStyleSheet(f"""
            QSpinBox {{
                background: white;
                color: {gray_900};
                border: 1px solid {gray_300};
                border-radius: 4px;
                padding: 2px;
                font-size: 20px;
            }}
        """)
        self.zoom_spinner.valueChanged.connect(self._on_zoom_percent_changed)
        layout.addWidget(self.zoom_spinner)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setStyleSheet(btn_style)
        zoom_in_btn.setToolTip("Zoom In (25%)")
        zoom_in_btn.clicked.connect(self._on_zoom_in)
        layout.addWidget(zoom_in_btn)

        # Fit buttons
        fit_width_btn = QPushButton("W")
        fit_width_btn.setStyleSheet(btn_style)
        fit_width_btn.setToolTip("Fit to Width")
        fit_width_btn.clicked.connect(self._on_fit_width)
        layout.addWidget(fit_width_btn)

        fit_height_btn = QPushButton("H")
        fit_height_btn.setStyleSheet(btn_style)
        fit_height_btn.setToolTip("Fit to Height")
        fit_height_btn.clicked.connect(self._on_fit_height)
        layout.addWidget(fit_height_btn)

        fit_btn = QPushButton("F")
        fit_btn.setStyleSheet(btn_style)
        fit_btn.setToolTip("Fit to Window")
        fit_btn.clicked.connect(self._on_fit_window)
        layout.addWidget(fit_btn)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"background: {gray_300};")
        sep.setFixedWidth(2)
        sep.setFixedHeight(40)
        layout.addWidget(sep)

        # Rotation controls (only CW and CCW)
        rotate_ccw_btn = QPushButton("↺")
        rotate_ccw_btn.setStyleSheet(btn_style)
        rotate_ccw_btn.setToolTip("Rotate Counter-Clockwise (90°)")
        rotate_ccw_btn.clicked.connect(self._on_rotate_ccw)
        layout.addWidget(rotate_ccw_btn)

        rotate_cw_btn = QPushButton("↻")
        rotate_cw_btn.setStyleSheet(btn_style)
        rotate_cw_btn.setToolTip("Rotate Clockwise (90°)")
        rotate_cw_btn.clicked.connect(self._on_rotate_cw)
        layout.addWidget(rotate_cw_btn)

        return controls

    def _position_overlay_controls(self):
        """Position overlay controls at bottom-center of image area."""
        if not hasattr(self, "overlay_controls") or not hasattr(self, "image_area"):
            return

        # Center horizontally, position at bottom
        x = (self.image_area.width() - self.overlay_controls.width()) // 2
        y = self.image_area.height() - self.overlay_controls.height() - 10
        self.overlay_controls.move(x, y)

    def _init_ui(self):
        """Initialize the user interface with image preview and accordion sections."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtWidgets import QScrollArea, QSplitter

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create horizontal splitter for left (image) and right (metadata) panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)  # Make handle wider and easier to grab
        splitter.setChildrenCollapsible(False)  # Prevent panels from collapsing completely

        # Style the splitter handle to make it visible and indicate it's draggable
        handle_color = "#4A4A4A" if self.is_dark_mode else "#D1D5DB"
        hover_color = "#6B7280" if self.is_dark_mode else "#9CA3AF"
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {handle_color};
                border-radius: 3px;
                margin: 2px 0px;
            }}
            QSplitter::handle:hover {{
                background-color: {hover_color};
            }}
            QSplitter::handle:horizontal {{
                width: 6px;
            }}
        """)

        # ===== LEFT PANEL: Image Preview =====
        left_panel = QWidget()
        left_panel.setStyleSheet(f"background-color: {self.theme_colors['bg_secondary']};")
        left_panel.setMinimumWidth(200)  # Minimum width to keep image visible
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(15, 15, 15, 15)

        # Image display area (with overlay controls)
        image_area = QWidget()
        image_area.setMinimumSize(400, 400)  # Ensure minimum size for absolute positioning
        image_layout = QVBoxLayout(image_area)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(0)

        # Image preview label with panning support
        self.image_label = PannableImageLabel()
        self.image_label.set_zoom_level(self.zoom_level)  # Initialize zoom level
        self.image_label.setStyleSheet(f"""
            QLabel {{
                background-color: {self.theme_colors["bg_primary"]};
                border: 2px solid {self.theme_colors["border"]};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        image_layout.addWidget(self.image_label)

        # Overlay controls (positioned absolutely at bottom-left)
        self.overlay_controls = self._create_overlay_controls()
        self.overlay_controls.setParent(image_area)
        self.overlay_controls.raise_()  # Bring controls to front
        # Position will be set in _apply_initial_zoom after layout is complete

        # Load and display image (path already corrected in __init__)
        file_path = self.file_data.get("full_path")

        if file_path and os.path.exists(file_path):
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                # Store base pixmap (never modified)
                self.base_pixmap = pixmap
                self.original_pixmap = pixmap
                self.current_rotation = "none"

                # Update preview with initial zoom
                self._update_image_preview()
            else:
                self.base_pixmap = None
                self.original_pixmap = None
                self.current_rotation = "none"
                self.image_label.setText("Failed to load image")
                self.image_label.setStyleSheet(f"color: {self.theme_colors['text_secondary']};")
        else:
            self.base_pixmap = None
            self.original_pixmap = None
            self.current_rotation = "none"
            self.image_label.setText(f"Image not found\n{file_path or 'No path'}")
            self.image_label.setStyleSheet(f"color: {self.theme_colors['text_secondary']};")

        left_layout.addWidget(image_area)

        # Store references for dynamic resizing
        self.image_area = image_area  # Store for overlay control repositioning
        self.left_panel = left_panel
        self.splitter = splitter

        splitter.addWidget(left_panel)

        # ===== RIGHT PANEL: Accordion Sections =====
        right_panel = QWidget()
        right_panel.setStyleSheet(f"background-color: {self.theme_colors['bg_secondary']};")
        right_panel.setMinimumWidth(400)  # Minimum width to keep accordion sections readable
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area for accordion sections
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setStyleSheet(f"background-color: {self.theme_colors['bg_secondary']};")

        accordion_container = QWidget()
        # No maximum width constraint - let splitter control the width
        accordion_layout = QVBoxLayout(accordion_container)
        accordion_layout.setContentsMargins(0, 0, 0, 0)  # No margins - flush with panel
        accordion_layout.setSpacing(0)  # No spacing between accordions

        # Extracted Metadata Section (moved to top, always first)
        metadata_section = self._create_accordion_section(
            "📋 Extracted Metadata", self._create_metadata_content(), initially_expanded=True
        )
        accordion_layout.addWidget(metadata_section)

        # File Information Section
        file_info_section = self._create_accordion_section(
            "📄 File Information", self._create_file_info_content()
        )
        accordion_layout.addWidget(file_info_section)

        # Analysis Information Section
        analysis_section = self._create_accordion_section(
            "⚙️ Analysis Information", self._create_analysis_content()
        )
        accordion_layout.addWidget(analysis_section)

        # LLM Prompt Section
        llm_prompt_section = self._create_accordion_section(
            "📝 LLM Prompt", self._create_llm_prompt_content()
        )
        accordion_layout.addWidget(llm_prompt_section)

        # Raw Response Section
        raw_response_section = self._create_accordion_section(
            "💬 LLM Response", self._create_raw_response_content()
        )
        accordion_layout.addWidget(raw_response_section)

        accordion_layout.addStretch()
        scroll_area.setWidget(accordion_container)
        right_layout.addWidget(scroll_area)

        splitter.addWidget(right_panel)

        # Set splitter proportions (50% image, 50% metadata)
        splitter.setSizes([525, 525])

        # Connect splitter moved signal to rescale image dynamically
        splitter.splitterMoved.connect(self._on_splitter_moved)

        main_layout.addWidget(splitter)

        # Bottom container with fixed height and centered buttons
        bottom_container = QWidget()
        bottom_container.setStyleSheet(f"background-color: {self.theme_colors['bg_secondary']};")
        bottom_container.setFixedHeight(80)  # Fixed height for consistent layout
        bottom_layout = QHBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(20, 15, 20, 15)  # Left, Top, Right, Bottom margins
        bottom_layout.setSpacing(10)

        # Status label on the left (hidden by default)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            f"color: {self.theme_colors['text_secondary']}; font-size: 9pt; background: transparent;"
        )
        self.status_label.setVisible(False)
        bottom_layout.addWidget(self.status_label)

        # Add stretch to push buttons to the right
        bottom_layout.addStretch()

        # Button styling matching guided bundle workflow
        button_style = f"""
            QPushButton {{
                background: {self.theme_colors['bg_primary']};
                color: {self.theme_colors['text_primary']};
                border: 1px solid {self.theme_colors['border']};
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                min-height: 36px;
            }}
            QPushButton:hover {{
                background: {self.theme_colors['bg_secondary']};
                border-color: {self.theme_colors['accent']};
            }}
            QPushButton:pressed {{
                background: {self.theme_colors['accent']};
                color: white;
            }}
        """

        # Action buttons with consistent styling
        self.open_doc_btn = QPushButton("📄 Open Document")
        self.open_doc_btn.setStyleSheet(button_style)
        self.open_doc_btn.clicked.connect(self._view_document)
        bottom_layout.addWidget(self.open_doc_btn)

        self.copy_json_btn = QPushButton("📋 Copy JSON")
        self.copy_json_btn.setStyleSheet(button_style)
        self.copy_json_btn.clicked.connect(self._copy_json)
        bottom_layout.addWidget(self.copy_json_btn)

        self.re_analyze_btn = QPushButton("🔄 Re-analyze")
        self.re_analyze_btn.setStyleSheet(button_style)
        self.re_analyze_btn.clicked.connect(self._re_analyze)
        bottom_layout.addWidget(self.re_analyze_btn)

        # Save button (positioned before close, will be blue when enabled)
        self.save_metadata_btn = QPushButton("💾 Save Metadata")
        self.save_metadata_btn.setStyleSheet(button_style)
        self.save_metadata_btn.clicked.connect(self._save_metadata)
        bottom_layout.addWidget(self.save_metadata_btn)

        # Initialize save button state (disabled initially if no changes)
        self._update_save_button_state()

        # Close button with gray styling (matching other buttons)
        self.close_btn = QPushButton("Close")
        self.close_btn.setStyleSheet(button_style)
        self.close_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(self.close_btn)

        main_layout.addWidget(bottom_container)

    def _format_summary(self) -> str:
        """Format summary information as HTML."""
        html = "<html><body style='font-family: Segoe UI; font-size: 10pt;'>"

        # File Information
        html += "<h3 style='color: #2563eb;'>File Information</h3>"
        html += "<table cellpadding='5'>"
        html += f"<tr><td><b>Filename:</b></td><td>{html_escape(str(self.file_data.get('filename', 'N/A')))}</td></tr>"
        html += f"<tr><td><b>Full Path:</b></td><td>{html_escape(str(self.file_data.get('full_path', 'N/A')))}</td></tr>"
        html += f"<tr><td><b>File Size:</b></td><td>{html_escape(self._format_size(self.file_data.get('file_size')))}</td></tr>"
        html += f"<tr><td><b>Modified:</b></td><td>{html_escape(self._format_dt(self.file_data.get('modified_time')))}</td></tr>"
        html += f"<tr><td><b>File Hash:</b></td><td>{html_escape(str(self.file_data.get('file_hash', 'N/A')))}</td></tr>"
        html += "</table>"

        # Analysis Information
        html += "<h3 style='color: #2563eb;'>Analysis Information</h3>"
        html += "<table cellpadding='5'>"
        html += f"<tr><td><b>Status:</b></td><td>{html_escape(str(self.file_data.get('status', 'N/A')))}</td></tr>"
        html += f"<tr><td><b>Analyzed:</b></td><td>{html_escape(self._format_dt(self.file_data.get('analysis_time')))}</td></tr>"
        html += f"<tr><td><b>Processing Time:</b></td><td>{html_escape(self._format_duration(self.file_data.get('processing_duration')))}</td></tr>"
        html += f"<tr><td><b>Provider:</b></td><td>{html_escape(str(self.file_data.get('provider', 'N/A')))}</td></tr>"
        html += f"<tr><td><b>Model:</b></td><td>{html_escape(str(self.file_data.get('model_used', 'N/A')))}</td></tr>"
        html += f"<tr><td><b>Cached:</b></td><td>{'Yes' if self.file_data.get('cache_hit') else 'No'}</td></tr>"

        if self.file_data.get("error_message"):
            html += f"<tr><td><b>Error:</b></td><td style='color: red;'>{html_escape(str(self.file_data.get('error_message')))}</td></tr>"

        html += "</table>"

        html += "</body></html>"
        return html

    def _format_metadata(self) -> str:
        """Format metadata information as HTML."""
        html = "<html><body style='font-family: Segoe UI; font-size: 10pt;'>"

        html += "<h3 style='color: #2563eb;'>Extracted Metadata</h3>"
        html += "<table cellpadding='5'>"

        confidence = self.file_data.get("confidence", 0)
        try:
            conf_float = float(confidence)
            conf_color = (
                "#16a34a" if conf_float >= 80 else "#ea580c" if conf_float >= 50 else "#dc2626"
            )
            html += f"<tr><td><b>Confidence:</b></td><td style='color: {conf_color}; font-weight: bold;'>{conf_float:.1f}%</td></tr>"
        except (ValueError, TypeError):
            html += f"<tr><td><b>Confidence:</b></td><td>{html_escape(str(confidence))}</td></tr>"

        html += f"<tr><td><b>Company:</b></td><td>{html_escape(str(self.file_data.get('company', 'N/A')))}</td></tr>"
        html += f"<tr><td><b>Document Type:</b></td><td>{html_escape(str(self.file_data.get('document_type', 'N/A')))}</td></tr>"
        html += f"<tr><td><b>Document Date:</b></td><td>{html_escape(str(self.file_data.get('document_date', 'N/A')))}</td></tr>"

        page_num = self.file_data.get("page_number")
        total_pages = self.file_data.get("total_pages")
        if page_num and total_pages:
            html += f"<tr><td><b>Pages:</b></td><td>{html_escape(str(page_num))} of {html_escape(str(total_pages))}</td></tr>"
        elif page_num:
            html += f"<tr><td><b>Page Number:</b></td><td>{html_escape(str(page_num))}</td></tr>"
        elif total_pages:
            html += f"<tr><td><b>Total Pages:</b></td><td>{html_escape(str(total_pages))}</td></tr>"

        html += "</table>"
        html += "</body></html>"
        return html

    def _format_size(self, size: Any) -> str:
        """Format file size."""
        try:
            size = int(size)
            for unit in ["B", "KB", "MB", "GB"]:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        except (ValueError, TypeError):
            return str(size) if size else "N/A"

    def _format_dt(self, dt: Any) -> str:
        """Format datetime (converts UTC to local timezone)."""
        from ui.datetime_utils import format_datetime_for_display

        return format_datetime_for_display(dt, "%Y-%m-%d %I:%M:%S %p")

    def _format_duration(self, duration: Any) -> str:
        """Format duration."""
        if not duration:
            return "N/A"
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

    def _create_accordion_section(
        self, title: str, content_widget, initially_expanded: bool = False
    ):
        """Create a collapsible accordion section."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QFrame

        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(0)

        header = QFrame()
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {self.theme_colors["bg_primary"]};
                border: 1px solid {self.theme_colors["border"]};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 12px;
            }}
            QFrame:hover {{
                background-color: {self.theme_colors["bg_secondary"]};
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        toggle_indicator = QLabel("▼" if initially_expanded else "▶")
        toggle_indicator.setObjectName("accordion_toggle")
        toggle_indicator.setStyleSheet(
            f"color: {self.theme_colors['text_secondary']}; font-size: 10pt; background: transparent; border: none;"
        )
        header_layout.addWidget(toggle_indicator)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {self.theme_colors['text_primary']}; font-weight: 600; font-size: 11pt; background: transparent; border: none;"
        )
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        content_frame = QFrame()
        content_frame.setObjectName("accordion_content")
        content_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {self.theme_colors["bg_secondary"]};
                border: 1px solid {self.theme_colors["border"]};
                border-top: none;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                padding: 12px;
            }}
        """)
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(content_widget)
        content_frame.setVisible(initially_expanded)

        def toggle():
            is_visible = content_frame.isVisible()

            # If already expanded, do nothing (don't close it)
            if is_visible:
                return

            # Expanding this section - collapse all others
            for other_section in getattr(self, "accordion_sections", []):
                if other_section != section:
                    # Find and collapse other sections
                    other_content = other_section.findChild(QFrame, "accordion_content")
                    other_toggle = other_section.findChild(QLabel, "accordion_toggle")
                    if other_content:
                        other_content.setVisible(False)
                    if other_toggle:
                        other_toggle.setText("▶")

            # Expand this section
            content_frame.setVisible(True)
            toggle_indicator.setText("▼")

        header.mousePressEvent = lambda e: toggle()  # type: ignore[method-assign,assignment]
        section_layout.addWidget(header)
        section_layout.addWidget(content_frame)

        # Add to tracked sections list
        if hasattr(self, "accordion_sections"):
            self.accordion_sections.append(section)

        return section

    def _create_file_info_content(self):
        """Create file information content widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        def add_row(label, value):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(f"<b>{label}:</b>")
            lbl.setStyleSheet(
                f"color: {self.theme_colors['text_secondary']}; background: transparent; border: none;"
            )
            lbl.setMinimumWidth(120)
            row_layout.addWidget(lbl)
            val = QLabel(value)
            val.setStyleSheet(
                f"color: {self.theme_colors['text_primary']}; background: transparent; border: none;"
            )
            val.setWordWrap(True)
            val.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            val.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )  # Allow text selection
            row_layout.addWidget(val, stretch=1)
            layout.addWidget(row)

        add_row("Filename", self.file_data.get("filename", "N/A"))
        add_row("Full Path", self.file_data.get("full_path", "N/A"))
        add_row("File Size", self._format_size(self.file_data.get("file_size")))
        add_row("Modified", self._format_dt(self.file_data.get("modified_time")))
        add_row("File Hash", self.file_data.get("file_hash", "N/A"))
        return widget

    # Strict whitelist of column names allowed in dynamic SQL queries.
    # These must match actual columns in the analysis_results table schema.
    ALLOWED_QUERY_COLUMNS = frozenset(
        {
            "file_path",
            "document_type",
            "company",
            "document_date",
            "page_number",
            "total_pages",
            "confidence_score",
            "provider_name",
            "model_name",
        }
    )

    def _get_distinct_values(self, field_name):
        """Get distinct values for a field from database.

        Args:
            field_name: Column name to query. Must be in ALLOWED_QUERY_COLUMNS.

        Returns:
            List of distinct non-empty values for the field.

        Raises:
            ValueError: If field_name is not in the allowed whitelist.
        """
        if not self.metadata_db:
            return []

        # Use MetadataDB methods for known fields
        try:
            if field_name == "company":
                return self.metadata_db.get_unique_companies()
            elif field_name == "document_type":
                return self.metadata_db.get_unique_titles()
            elif field_name == "document_category":
                return self.metadata_db.get_unique_categories()
        except Exception as e:
            from services.logging_service import get_logger

            get_logger().error(f"Error getting distinct values for {field_name}: {e}")
            return []

        # Fallback for other fields - route to correct table based on schema
        if not self.analysis_db:
            return []

        # Validate against strict whitelist to prevent SQL injection
        if field_name not in self.ALLOWED_QUERY_COLUMNS:
            from services.logging_service import get_logger

            get_logger().warning(f"Rejected disallowed column name in query: {field_name!r}")
            return []

        try:
            # Route field to correct table after Migration 16 schema refactoring
            if field_name in ("provider_name", "model_name"):
                # Analysis provenance fields - from analysis_results table
                table = "analysis_results"
            elif field_name in ("document_date", "page_number", "total_pages", "confidence_score"):
                # Document metadata fields - from metadata table
                table = "metadata"
            elif field_name == "file_path":
                # File system fields - from image_files table
                table = "image_files"
            else:
                # Unknown field - skip
                return []

            # Safe to interpolate now that field_name is validated and table is hardcoded
            query = f"SELECT DISTINCT {field_name} FROM {table} WHERE {field_name} IS NOT NULL AND {field_name} != '' ORDER BY {field_name}"
            result = self.analysis_db.connection.execute(query).fetchall()
            return [row[0] for row in result if row[0]]
        except Exception as e:
            from services.logging_service import get_logger

            get_logger().error(f"Error getting distinct values for {field_name}: {e}")
            return []

    def _get_distinct_categories(self):
        """Get distinct document categories from metadata table."""
        if not self.metadata_db:
            return []

        try:
            return self.metadata_db.get_unique_categories()
        except Exception as e:
            from services.logging_service import get_logger

            get_logger().error(f"Error getting distinct categories: {e}")
            return []

    def _create_metadata_content(self):
        """Create extracted metadata content widget with editable fields."""
        from PyQt6.QtWidgets import QComboBox, QLineEdit

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Store references to input fields for later saving
        self.metadata_inputs = {}
        self.original_metadata_values = {}  # Track original values for change detection

        def add_editable_row(
            label,
            field_name,
            current_value,
            placeholder="",
            widget_type="text",
            distinct_values=None,
        ):
            """Add a row with editable field."""
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            # Label (fixed width for perfect alignment)
            lbl = QLabel(f"<b>{label}:</b>")
            lbl.setStyleSheet(
                f"color: {self.theme_colors['text_secondary']}; background: transparent; border: none;"
            )
            lbl.setFixedWidth(
                160
            )  # Fixed width ensures perfect alignment (increased for "Document Category")
            row_layout.addWidget(lbl)

            # Input field (text, dropdown, or checkbox)
            if widget_type == "checkbox":
                input_widget = QCheckBox()
                # Handle boolean conversion
                if isinstance(current_value, bool):
                    input_widget.setChecked(current_value)
                elif isinstance(current_value, int | str):
                    input_widget.setChecked(
                        bool(int(current_value)) if str(current_value).isdigit() else False
                    )
                else:
                    input_widget.setChecked(False)
                input_widget.setStyleSheet(f"""
                    QCheckBox {{
                        background: transparent;
                        color: {self.theme_colors["text_primary"]};
                        spacing: 5px;
                    }}
                    QCheckBox::indicator {{
                        width: 18px;
                        height: 18px;
                        border: 1px solid {self.theme_colors["border"]};
                        border-radius: 3px;
                        background-color: {self.theme_colors["bg_primary"]};
                    }}
                    QCheckBox::indicator:checked {{
                        background-color: {self.theme_colors["accent"]};
                        border-color: {self.theme_colors["accent"]};
                    }}
                    QCheckBox::indicator:hover {{
                        border-color: {self.theme_colors["accent"]};
                    }}
                """)
            elif widget_type == "dropdown":
                input_widget = QComboBox()
                input_widget.setEditable(False)
                input_widget.addItems(["none", "90_cw", "90_ccw", "180"])
                # Set current value if it exists
                if current_value and current_value in ["none", "90_cw", "90_ccw", "180"]:
                    input_widget.setCurrentText(current_value)
                input_widget.setStyleSheet(f"""
                    QComboBox {{
                        background-color: {self.theme_colors["bg_primary"]};
                        color: {self.theme_colors["text_primary"]};
                        border: 1px solid {self.theme_colors["border"]};
                        border-radius: 4px;
                        padding: 4px 8px;
                    }}
                    QComboBox:focus {{
                        border: 1px solid {self.theme_colors["accent"]};
                    }}
                    QComboBox::drop-down {{
                        border: none;
                    }}
                    QComboBox QAbstractItemView {{
                        background-color: {self.theme_colors["bg_primary"]};
                        color: {self.theme_colors["text_primary"]};
                        selection-background-color: {self.theme_colors["accent"]};
                    }}
                """)
            elif widget_type == "editable_dropdown":
                input_widget = QComboBox()
                input_widget.setEditable(True)  # Allow typing new values

                # Add distinct values from database
                if distinct_values:
                    input_widget.addItems(sorted(distinct_values))

                # Set current value
                if current_value:
                    input_widget.setCurrentText(str(current_value))

                input_widget.setStyleSheet(f"""
                    QComboBox {{
                        background-color: {self.theme_colors["bg_primary"]};
                        color: {self.theme_colors["text_primary"]};
                        border: 1px solid {self.theme_colors["border"]};
                        border-radius: 4px;
                        padding: 4px 8px;
                    }}
                    QComboBox:focus {{
                        border: 1px solid {self.theme_colors["accent"]};
                    }}
                    QComboBox::drop-down {{
                        border: none;
                    }}
                    QComboBox QAbstractItemView {{
                        background-color: {self.theme_colors["bg_primary"]};
                        color: {self.theme_colors["text_primary"]};
                        selection-background-color: {self.theme_colors["accent"]};
                    }}
                """)
            else:
                input_widget = QLineEdit()
                input_widget.setText(
                    str(current_value) if current_value and current_value != "N/A" else ""
                )
                input_widget.setPlaceholderText(placeholder)
                input_widget.setStyleSheet(f"""
                    QLineEdit {{
                        background-color: {self.theme_colors["bg_primary"]};
                        color: {self.theme_colors["text_primary"]};
                        border: 1px solid {self.theme_colors["border"]};
                        border-radius: 4px;
                        padding: 4px 8px;
                    }}
                    QLineEdit:focus {{
                        border: 1px solid {self.theme_colors["accent"]};
                    }}
                """)

            row_layout.addWidget(input_widget, stretch=1)
            layout.addWidget(row)

            # Store reference for later access
            self.metadata_inputs[field_name] = input_widget

        # Extract rotation - prioritize user-saved rotation from image_files table
        from services.logging_service import get_logger

        logger = get_logger()

        # ALWAYS get rotation from image_files table (authoritative source via MetadataDB)
        # Never use analysis_results.rotation_needed as it's just for historical reference
        rotation_value = "none"  # Default
        if self.metadata_db:
            file_path = self.file_data.get("full_path")
            if file_path:
                rotation_degrees = self.metadata_db.get_image_rotation(file_path)
                # Convert degrees back to rotation_needed format
                rotation_value = {
                    0: "none",
                    90: "90_cw",
                    270: "90_ccw",
                    180: "180",
                }.get(rotation_degrees, "none")  # Default to "none" if unexpected value
                logger.debug(
                    f"[METADATA CONTENT] Loaded rotation from image_files: {rotation_degrees}° = '{rotation_value}'"
                )

        # Store initial rotation for later application
        self.initial_rotation = rotation_value
        logger.debug(
            f"[METADATA CONTENT] Set initial_rotation and rotation_value to: '{self.initial_rotation}'"
        )

        # Get distinct values from database
        distinct_document_types = self._get_distinct_values("document_type")
        distinct_companies = self._get_distinct_values("company")
        distinct_categories = self._get_distinct_categories()

        # Add all metadata fields (always show all fields, even if empty)
        # Document Category FIRST (user's top priority field)
        add_editable_row(
            "Document Category",
            "document_category",
            self.file_data.get("document_category"),
            "Category (optional)",
            widget_type="editable_dropdown",
            distinct_values=distinct_categories,
        )

        add_editable_row(
            "Document Type",
            "document_type",
            self.file_data.get("document_type"),
            "e.g., invoice, receipt, contract",
            widget_type="editable_dropdown",
            distinct_values=distinct_document_types,
        )

        add_editable_row(
            "Company",
            "company",
            self.file_data.get("company"),
            "Company or organization name",
            widget_type="editable_dropdown",
            distinct_values=distinct_companies,
        )

        add_editable_row(
            "Document Date",
            "document_date",
            self.file_data.get("document_date"),
            "YYYY-MM-DD format",
        )

        add_editable_row(
            "Page Number", "page_number", self.file_data.get("page_number"), "Current page number"
        )

        add_editable_row(
            "Total Pages", "total_pages", self.file_data.get("total_pages"), "Total number of pages"
        )

        add_editable_row(
            "Rotation Needed",
            "rotation_needed",
            rotation_value,
            "none, 90_cw, 90_ccw, 180",
            widget_type="dropdown",
        )

        # Connect rotation dropdown to apply rotation immediately
        if "rotation_needed" in self.metadata_inputs:
            rotation_dropdown = self.metadata_inputs["rotation_needed"]

            # Debug logging - verify dropdown was set correctly
            from services.logging_service import get_logger

            logger = get_logger()
            logger.debug(
                f"[METADATA CONTENT] Rotation dropdown created - "
                f"currentText: '{rotation_dropdown.currentText()}'"
            )

            rotation_dropdown.currentTextChanged.connect(self._apply_rotation)

            # Apply initial rotation if one exists
            if hasattr(self, "initial_rotation") and self.initial_rotation != "none":
                logger.debug(
                    f"[METADATA CONTENT] Applying initial rotation: '{self.initial_rotation}'"
                )
                self._apply_rotation(self.initial_rotation)

        # Tax related checkbox
        add_editable_row(
            "Tax Related",
            "tax_related",
            self.file_data.get("tax_related", False),
            widget_type="checkbox",
        )

        # Output filename field (user's desired PDF filename)
        add_editable_row(
            "Output Filename",
            "output_filename",
            self.file_data.get("output_filename"),
            "Desired PDF filename (optional)",
        )

        # Store original values and connect change tracking
        self._store_original_metadata_values()
        self._connect_metadata_change_signals()

        return widget

    def _create_analysis_content(self):
        """Create analysis information content widget."""
        from PyQt6.QtWidgets import QGridLayout

        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)
        layout.setColumnStretch(1, 1)  # Value column expands

        row = 0

        def add_row(label_text, value_text, value_color=None, value_bold=False):
            nonlocal row
            # Label (column 0)
            lbl = QLabel(f"<b>{label_text}:</b>")
            lbl.setStyleSheet(
                f"color: {self.theme_colors['text_secondary']}; background: transparent; border: none;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            layout.addWidget(lbl, row, 0)

            # Value (column 1)
            val = QLabel(value_text)
            style = f"color: {value_color or self.theme_colors['text_primary']}; background: transparent; border: none;"
            if value_bold:
                style += " font-weight: bold;"
            val.setStyleSheet(style)
            val.setWordWrap(True)
            val.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            val.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            layout.addWidget(val, row, 1)

            row += 1

        # Add all rows with proper alignment
        add_row("Status", self.file_data.get("status", "N/A"))

        # Confidence score with color coding
        confidence = self.file_data.get("confidence", 0)
        try:
            conf_float = float(confidence)
            conf_color = (
                "#16a34a" if conf_float >= 80 else "#ea580c" if conf_float >= 50 else "#dc2626"
            )
            add_row(
                "Confidence Score", f"{conf_float:.1f}%", value_color=conf_color, value_bold=True
            )
        except (ValueError, TypeError):
            add_row("Confidence Score", str(confidence) if confidence else "N/A")

        add_row("Analyzed", self._format_dt(self.file_data.get("analysis_time")))
        add_row("Processing Time", self._format_duration(self.file_data.get("processing_duration")))
        add_row("Provider", self.file_data.get("provider", "N/A"))
        add_row("Model", self.file_data.get("model_used", "N/A"))
        add_row("Cached", "Yes" if self.file_data.get("cache_hit") else "No")

        if self.file_data.get("error_message"):
            add_row("Error", self.file_data.get("error_message"))

        return widget

    def _create_llm_prompt_content(self):
        """Create LLM prompt content widget with copy button."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header with copy button
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        header_layout.addStretch()

        # Copy button (icon only)
        copy_btn = QPushButton("📋")
        copy_btn.setToolTip("Copy prompt to clipboard")
        copy_btn.setFixedSize(32, 32)
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme_colors["bg_secondary"]};
                color: {self.theme_colors["text_primary"]};
                border: 1px solid {self.theme_colors["border"]};
                border-radius: 4px;
                font-size: 16px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {self.theme_colors["accent"]};
                color: {self.theme_colors["bg_primary"]};
            }}
            QPushButton:pressed {{
                background-color: {self.theme_colors["border"]};
            }}
        """)
        copy_btn.clicked.connect(self._copy_prompt_to_clipboard)
        header_layout.addWidget(copy_btn)
        layout.addWidget(header)

        # Text edit for prompt
        prompt_text = self.file_data.get("prompt_text", "No prompt available")

        self.prompt_text_edit = QTextEdit()
        self.prompt_text_edit.setPlainText(str(prompt_text))
        self.prompt_text_edit.setReadOnly(True)
        self.prompt_text_edit.setFont(QFont("Consolas", 9))
        self.prompt_text_edit.setMinimumHeight(150)
        self.prompt_text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {self.theme_colors["bg_primary"]};
                color: {self.theme_colors["text_primary"]};
                border: 1px solid {self.theme_colors["border"]};
                border-radius: 4px;
                padding: 8px;
            }}
        """)
        layout.addWidget(self.prompt_text_edit)

        return container

    def _copy_prompt_to_clipboard(self):
        """Copy LLM prompt text to clipboard."""
        if hasattr(self, "prompt_text_edit"):
            prompt_text = self.prompt_text_edit.toPlainText()
            clipboard = QApplication.clipboard()
            clipboard.setText(prompt_text)
            # Show brief feedback
            if hasattr(self, "status_label"):
                self.status_label.setText("✓ Prompt copied to clipboard")
                self.status_label.show()
                QTimer.singleShot(2000, self.status_label.hide)

    def _create_raw_response_content(self):
        """Create raw LLM response content widget."""
        # Migration 16: raw_response renamed to response_text
        raw_response = self.file_data.get("response_text") or self.file_data.get(
            "raw_response", "No raw response available"
        )

        text_edit = QTextEdit()
        text_edit.setPlainText(str(raw_response))
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Consolas", 9))
        text_edit.setMinimumHeight(200)
        text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {self.theme_colors["bg_primary"]};
                color: {self.theme_colors["text_primary"]};
                border: 1px solid {self.theme_colors["border"]};
                border-radius: 4px;
                padding: 8px;
            }}
        """)
        return text_edit

    def _scale_image_to_mode(self, pixmap, available_width, available_height):
        """Scale image according to configured zoom mode."""
        if self.default_zoom_mode == "fit_to_width":
            return pixmap.scaledToWidth(available_width, Qt.TransformationMode.SmoothTransformation)
        elif self.default_zoom_mode == "fit_to_height":
            return pixmap.scaledToHeight(
                available_height, Qt.TransformationMode.SmoothTransformation
            )
        elif self.default_zoom_mode == "fit_to_window":
            # Scale to fit both dimensions (aspect ratio preserved)
            return pixmap.scaled(
                available_width,
                available_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        elif self.default_zoom_mode == "custom_%":
            # Scale by percentage
            scale_factor = self.default_zoom_percent / 100.0
            return pixmap.scaled(
                int(pixmap.width() * scale_factor),
                int(pixmap.height() * scale_factor),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            # Fallback to fit width
            return pixmap.scaledToWidth(available_width, Qt.TransformationMode.SmoothTransformation)

    def _update_image_preview(self):
        """Update preview with zoom, rotation, and pan transformations."""
        if not self.base_pixmap:
            return

        # Start with base pixmap
        pixmap = self.base_pixmap

        # Apply rotation
        if self.rotation_angle != 0:
            transform = QTransform()
            transform.rotate(self.rotation_angle)
            pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        # Apply zoom
        zoom_factor = self.zoom_level / 100.0
        if zoom_factor != 1.0:
            new_width = int(pixmap.width() * zoom_factor)
            new_height = int(pixmap.height() * zoom_factor)
            pixmap = pixmap.scaled(
                new_width,
                new_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        # Apply pan
        pan_offset = self.image_label.get_pan_offset()
        if self.zoom_level > 100 and not pan_offset.isNull():
            canvas = QPixmap(pixmap.size())
            canvas.fill(Qt.GlobalColor.white)
            painter = QPainter(canvas)
            painter.drawPixmap(pan_offset, pixmap)
            painter.end()
            pixmap = canvas

        self.image_label.setPixmap(pixmap)

    def _on_zoom_in(self):
        """Zoom in by 25%."""
        new_zoom = min(400, self.zoom_level + 25)
        self.zoom_spinner.setValue(new_zoom)

    def _on_zoom_out(self):
        """Zoom out by 25%."""
        new_zoom = max(25, self.zoom_level - 25)
        self.zoom_spinner.setValue(new_zoom)

    def _on_zoom_percent_changed(self, value: int):
        """Handle zoom percentage change."""
        self.zoom_level = value
        self.image_label.set_zoom_level(value)
        self._update_image_preview()

    def _on_rotate_ccw(self):
        """Rotate counter-clockwise by 90 degrees."""
        self.rotation_angle = (self.rotation_angle - 90) % 360
        self.image_label.reset_pan()  # Reset pan when rotating
        self._update_image_preview()

    def _on_rotate_cw(self):
        """Rotate clockwise by 90 degrees."""
        self.rotation_angle = (self.rotation_angle + 90) % 360
        self.image_label.reset_pan()  # Reset pan when rotating
        self._update_image_preview()

    def _on_fit_width(self):
        """Fit image to width of preview area."""
        if not self.base_pixmap or not hasattr(self, "image_area"):
            return

        # Start with base pixmap
        pixmap = self.base_pixmap

        # Apply rotation to get actual display dimensions
        if self.rotation_angle != 0:
            transform = QTransform()
            transform.rotate(self.rotation_angle)
            pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        # Get available width from image_area (subtract margins and padding)
        available_width = self.image_area.width() - 40

        # Ensure we have valid dimensions
        if available_width <= 0 or pixmap.width() <= 0:
            return

        # Calculate zoom to fit width
        zoom_percent = int((available_width / pixmap.width()) * 100)
        zoom_percent = max(25, min(400, zoom_percent))  # Clamp to valid range

        self.zoom_spinner.setValue(zoom_percent)

    def _on_fit_height(self):
        """Fit image to height of preview area."""
        if not self.base_pixmap or not hasattr(self, "image_area"):
            return

        # Start with base pixmap
        pixmap = self.base_pixmap

        # Apply rotation to get actual display dimensions
        if self.rotation_angle != 0:
            transform = QTransform()
            transform.rotate(self.rotation_angle)
            pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        # Get available height from image_area (subtract margins, padding, and overlay controls)
        available_height = self.image_area.height() - 80  # Extra space for overlay controls

        # Ensure we have valid dimensions
        if available_height <= 0 or pixmap.height() <= 0:
            return

        # Calculate zoom to fit height
        zoom_percent = int((available_height / pixmap.height()) * 100)
        zoom_percent = max(25, min(400, zoom_percent))  # Clamp to valid range

        self.zoom_spinner.setValue(zoom_percent)

    def _on_fit_window(self):
        """Fit image to window (both width and height)."""
        if not self.base_pixmap or not hasattr(self, "image_area"):
            return

        # Start with base pixmap
        pixmap = self.base_pixmap

        # Apply rotation to get actual display dimensions
        if self.rotation_angle != 0:
            transform = QTransform()
            transform.rotate(self.rotation_angle)
            pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        # Get available dimensions from image_area (subtract margins and overlay controls space)
        available_width = self.image_area.width() - 40
        available_height = self.image_area.height() - 80  # Extra space for overlay controls

        # Ensure we have valid dimensions
        if (
            available_width <= 0
            or available_height <= 0
            or pixmap.width() <= 0
            or pixmap.height() <= 0
        ):
            return

        # Calculate zoom to fit both dimensions (use smaller ratio)
        width_ratio = available_width / pixmap.width()
        height_ratio = available_height / pixmap.height()
        zoom_ratio = min(width_ratio, height_ratio)
        zoom_percent = int(zoom_ratio * 100)
        zoom_percent = max(25, min(400, zoom_percent))  # Clamp to valid range

        self.zoom_spinner.setValue(zoom_percent)

    def _on_splitter_moved(self, pos, index):
        """Handle splitter movement - no automatic rescaling with manual zoom controls."""
        # With manual zoom controls, we don't automatically rescale on splitter movement
        # Users can use fit buttons (W, H, F) if they want to adjust zoom
        pass

    def showEvent(self, event):  # noqa: N802
        """Handle first show to apply initial zoom setting."""
        super().showEvent(event)

        # Only apply on first show
        if not hasattr(self, "_first_show_done"):
            self._first_show_done = True

            # Apply initial zoom after window is shown and layout is calculated
            if hasattr(self, "base_pixmap") and self.base_pixmap is not None:
                # Use QTimer to ensure layout has been fully calculated
                from PyQt6.QtCore import QTimer

                QTimer.singleShot(100, self._apply_initial_zoom)

    def _apply_initial_zoom(self):
        """Apply the configured zoom setting after window is shown."""
        if not hasattr(self, "base_pixmap") or self.base_pixmap is None:
            return

        # Ensure overlay controls are visible and positioned at bottom-left
        if hasattr(self, "overlay_controls"):
            self._position_overlay_controls()
            self.overlay_controls.show()
            self.overlay_controls.raise_()

        # Apply zoom based on default mode
        if self.default_zoom_mode == "fit_to_width":
            self._on_fit_width()
        elif self.default_zoom_mode == "fit_to_height":
            self._on_fit_height()
        elif self.default_zoom_mode == "fit_to_window":
            self._on_fit_window()
        elif self.default_zoom_mode == "custom_%":
            # Use configured percentage
            self.zoom_spinner.setValue(self.default_zoom_percent)
        else:
            # Default to fit width
            self._on_fit_width()

    def resizeEvent(self, event):  # noqa: N802
        """Handle window resize - reposition overlay controls."""
        super().resizeEvent(event)
        # Reposition overlay controls at bottom-left when window is resized
        if hasattr(self, "overlay_controls") and hasattr(self, "image_area"):
            self._position_overlay_controls()

    def _copy_json(self):
        """Copy JSON data to clipboard."""
        json_str = json.dumps(self.file_data, indent=2, default=str)
        QApplication.clipboard().setText(json_str)
        QMessageBox.information(self, "Copied", "JSON data copied to clipboard")

    def _view_document(self):
        """Open the document with the default system viewer."""
        stored_path = self.file_data.get("full_path")
        filename = self.file_data.get("filename")

        if not filename:
            QMessageBox.warning(
                self, "File Name Not Found", "Could not find the file name for this record."
            )
            return

        # Find actual file path (handles temp path issue)
        file_path = self._find_actual_file_path(stored_path, filename)

        if not file_path:
            QMessageBox.warning(
                self,
                "File Not Found",
                f"Could not find the file:\n\n{filename}\n\nSearched in configured source directories.",
            )
            return

        try:
            # Open file with default system viewer
            os.startfile(file_path)
        except Exception as e:
            QMessageBox.critical(self, "Error Opening File", f"Failed to open file:\n\n{str(e)}")

    def _save_metadata(self):
        """Save edited metadata back to the database."""
        from PyQt6.QtWidgets import QComboBox, QLineEdit

        # Collect values from all metadata input fields
        updated_metadata = {}
        for field_name, input_widget in self.metadata_inputs.items():
            if isinstance(input_widget, QLineEdit):
                value = input_widget.text().strip()
            elif isinstance(input_widget, QComboBox):
                value = input_widget.currentText()
            elif isinstance(input_widget, QCheckBox):
                value = input_widget.isChecked()
                # Always include checkbox values (even False)
                updated_metadata[field_name] = value
                continue
            else:
                continue

            # Only include non-empty values (for text fields)
            if value:
                updated_metadata[field_name] = value

        # Update file_data dictionary
        self.file_data.update(updated_metadata)

        # Save to database - use both databases
        try:
            # Use the database instances passed to constructor
            analysis_db = self.analysis_db
            metadata_db = self.metadata_db

            if analysis_db and metadata_db:
                file_path = self.file_data.get("full_path")

                if file_path:
                    # Prepare metadata dict with standard field names
                    metadata = {
                        "document_type": updated_metadata.get("document_type", ""),
                        "company": updated_metadata.get("company", ""),
                        "document_date": updated_metadata.get("document_date", ""),
                        "page_number": updated_metadata.get("page_number", ""),
                        "total_pages": updated_metadata.get("total_pages", ""),
                        "rotation_needed": updated_metadata.get("rotation_needed", ""),
                        "tax_related": updated_metadata.get("tax_related", False),
                        "output_filename": updated_metadata.get("output_filename", ""),
                        "document_category": updated_metadata.get("document_category", ""),
                    }

                    # Debug logging before database save
                    from services.logging_service import get_logger

                    logger = get_logger()
                    logger.debug(
                        f"[SAVE METADATA] Saving metadata to DB - "
                        f"rotation_needed: '{metadata.get('rotation_needed')}'"
                    )

                    # Update analysis database (legacy)
                    analysis_db.update_analysis_metadata(file_path, metadata)

                    # Save rotation to image_files table (via MetadataDB)
                    rotation_needed = metadata.get("rotation_needed", "none")
                    rotation_degrees = {
                        "none": 0,
                        "90_cw": 90,
                        "90_ccw": 270,
                        "180": 180,
                    }.get(rotation_needed, 0)
                    from services.logging_service import get_logger

                    logger = get_logger()
                    logger.debug(
                        f"Converted rotation_needed to rotation_degrees: {rotation_degrees}"
                    )
                    metadata_db.update_image_rotation(file_path, rotation_degrees)

                    # Update normalized metadata table (user edit) via MetadataDB
                    try:
                        image_file = metadata_db.get_image_file(file_path)
                        if image_file:
                            metadata_updates = {
                                "company": metadata.get("company"),
                                "document_type": metadata.get("document_type"),
                                "document_date": metadata.get("document_date"),
                                "page_number": int(metadata["page_number"])
                                if metadata.get("page_number")
                                else None,
                                "total_pages": int(metadata["total_pages"])
                                if metadata.get("total_pages")
                                else None,
                                "rotation": rotation_degrees,
                                "tax_related": metadata.get("tax_related", False),
                                "output_filename": metadata.get("output_filename"),
                                "document_category": metadata.get("document_category"),
                            }
                            # Use metadata_db for normalized metadata operations
                            metadata_db.update_normalized_metadata(
                                image_file["id"], metadata_updates
                            )
                            logger.debug(
                                "Updated normalized metadata table via MetadataDB (user edit)"
                            )
                    except Exception as meta_error:
                        logger.warning(f"Failed to update normalized metadata: {meta_error}")

                    # Reload fresh data from database to ensure file_data is up-to-date
                    fresh_analysis = analysis_db.get_analysis(file_path)
                    if fresh_analysis:
                        logger.debug(
                            f"Reloaded analysis from DB - rotation_needed: {fresh_analysis.get('rotation_needed')}"
                        )

                        # Update file_data with fresh values from database
                        for key in [
                            "document_type",
                            "company",
                            "document_date",
                            "page_number",
                            "total_pages",
                            "rotation_needed",
                            "tax_related",
                            "confidence",
                            "output_filename",
                            "document_category",
                        ]:
                            if key in fresh_analysis:
                                self.file_data[key] = fresh_analysis[key]

                        logger.debug(
                            f"Updated file_data - rotation_needed: {self.file_data.get('rotation_needed')}"
                        )

                    # CRITICAL: Also reload rotation from image_files table (authoritative source via MetadataDB)
                    fresh_rotation = metadata_db.get_image_rotation(file_path)
                    self.file_data["rotation"] = fresh_rotation
                    logger.debug(
                        f"Reloaded rotation from image_files: {fresh_rotation}° (authoritative source)"
                    )

                    # Emit signal so parent can refresh its data
                    self.metadata_saved.emit(file_path)

                    QMessageBox.information(self, "Success", "Metadata saved successfully!")

                    # Update original values to current values (reset change tracking)
                    self._store_original_metadata_values()
                    self._update_save_button_state()
                else:
                    QMessageBox.warning(
                        self, "Missing File Path", "Cannot save metadata: file path not found."
                    )
            else:
                # Determine which database is missing
                missing_dbs = []
                if not analysis_db:
                    missing_dbs.append("analysis_db")
                if not metadata_db:
                    missing_dbs.append("metadata_db")

                QMessageBox.warning(
                    self,
                    "Database Not Available",
                    f"Cannot save metadata: {', '.join(missing_dbs)} not available.",
                )

        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Failed to save metadata:\n\n{str(e)}")

    def _find_actual_file_path(self, stored_path, filename):
        """Find the actual file path, searching source directories if needed."""
        # First, check if the stored path exists and is not in a temp folder
        if stored_path and os.path.exists(stored_path):
            # Check if it's in a temp folder
            temp_indicators = ["temp", "tmp", "AppData\\Local\\Temp"]
            if not any(indicator in stored_path for indicator in temp_indicators):
                return stored_path

        # If stored path doesn't exist or is in temp, search source directories
        # Traverse parent chain to find config_manager
        parent_widget = self.parent()
        config_manager = None

        while parent_widget:
            if hasattr(parent_widget, "config_manager"):
                config_manager = parent_widget.config_manager
                break
            parent_widget = parent_widget.parent() if hasattr(parent_widget, "parent") else None

        if config_manager:
            directories = config_manager.get_directories()

            # Search for the file by name in all source directories
            for directory in directories:
                if not os.path.exists(directory):
                    continue

                for root, _, files in os.walk(directory):
                    if filename in files:
                        found_path = os.path.join(root, filename)
                        if os.path.exists(found_path):
                            return found_path

        return None

    def _re_analyze(self):
        """Queue this file for re-analysis and close dialog."""
        file_path = self.file_data.get("full_path") or self.file_data.get("filename")
        if not file_path:
            QMessageBox.warning(self, "No File Path", "Cannot re-analyze: file path not found.")
            return

        # Emit signal to parent (AnalysisStatusWindow will queue the job)
        self.re_analyze_requested.emit(file_path)

        # Close the dialog so user can see analysis progress in main window
        self.accept()

    # Note: Analysis progress/completion handlers removed - now handled by queue system in AnalysisStatusWindow

    def _set_controls_enabled(self, enabled: bool):
        """Enable or disable all buttons and edit controls."""
        # Buttons
        self.open_doc_btn.setEnabled(enabled)
        self.save_metadata_btn.setEnabled(enabled)
        self.copy_json_btn.setEnabled(enabled)
        self.re_analyze_btn.setEnabled(enabled)
        self.close_btn.setEnabled(enabled)

        # Edit controls
        if hasattr(self, "metadata_inputs"):
            for input_widget in self.metadata_inputs.values():
                input_widget.setEnabled(enabled)

    def _update_metadata_fields(self):
        """Update metadata input fields with current file_data values."""
        from PyQt6.QtWidgets import QComboBox, QLineEdit

        if not hasattr(self, "metadata_inputs"):
            return

        for field_name, input_widget in self.metadata_inputs.items():
            value = self.file_data.get(field_name, "")

            if isinstance(input_widget, QLineEdit):
                input_widget.setText(str(value) if value else "")
            elif isinstance(input_widget, QComboBox):
                if value:
                    input_widget.setCurrentText(str(value))
            elif isinstance(input_widget, QCheckBox):
                input_widget.setChecked(bool(value))

    def _apply_rotation(self, rotation: str):
        """Apply metadata rotation to the base image (permanent rotation)."""
        if not hasattr(self, "base_pixmap") or self.base_pixmap is None:
            return

        from PyQt6.QtGui import QTransform

        # Update current rotation tracker
        self.current_rotation = rotation

        # Map rotation strings to angles
        rotation_map = {"90_cw": -90, "90_ccw": 90, "180": 180, "none": 0}

        angle = rotation_map.get(rotation, 0)

        # Load the original unrotated pixmap from file
        file_path = self.file_data.get("full_path")
        if file_path and os.path.exists(file_path):
            from PyQt6.QtGui import QPixmap

            original = QPixmap(file_path)

            if angle == 0:
                # No rotation - use original directly
                self.base_pixmap = original
            else:
                # Apply metadata rotation to create new base pixmap
                transform = QTransform()
                transform.rotate(angle)
                self.base_pixmap = original.transformed(
                    transform, Qt.TransformationMode.SmoothTransformation
                )

        # Reset overlay rotation controls when metadata rotation changes
        self.rotation_angle = 0
        self.image_label.reset_pan()

        # Update the preview with new base pixmap
        self._update_image_preview()

    def _store_original_metadata_values(self):
        """Store the original values of all metadata fields for change tracking."""
        from PyQt6.QtWidgets import QCheckBox, QComboBox, QLineEdit

        for field_name, widget in self.metadata_inputs.items():
            if isinstance(widget, QCheckBox):
                self.original_metadata_values[field_name] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                self.original_metadata_values[field_name] = widget.currentText()
            elif isinstance(widget, QLineEdit):
                self.original_metadata_values[field_name] = widget.text()

    def _connect_metadata_change_signals(self):
        """Connect change signals from all metadata input fields."""
        from PyQt6.QtWidgets import QCheckBox, QComboBox, QLineEdit

        for _field_name, widget in self.metadata_inputs.items():
            if isinstance(widget, QCheckBox):
                widget.stateChanged.connect(self._on_metadata_changed)
            elif isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self._on_metadata_changed)
            elif isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._on_metadata_changed)

    def _on_metadata_changed(self):
        """Handle metadata field changes - update save button state."""
        self._update_save_button_state()

    def _has_unsaved_changes(self):
        """Check if current metadata values differ from original values."""
        from PyQt6.QtWidgets import QCheckBox, QComboBox, QLineEdit

        for field_name, widget in self.metadata_inputs.items():
            original_value = self.original_metadata_values.get(field_name)

            if isinstance(widget, QCheckBox):
                current_value = widget.isChecked()
            elif isinstance(widget, QComboBox):
                current_value = widget.currentText()
            elif isinstance(widget, QLineEdit):
                current_value = widget.text()
            else:
                continue

            # Compare current to original (handle None and empty string as equivalent)
            if original_value != current_value and not (not original_value and not current_value):
                return True

        return False

    def _update_save_button_state(self):
        """Enable or disable the save button based on whether there are unsaved changes."""
        if hasattr(self, "save_metadata_btn"):
            has_changes = self._has_unsaved_changes()
            self.save_metadata_btn.setEnabled(has_changes)

            # Update button style to show enabled/disabled state
            if has_changes:
                # Enabled state - use blue accent color to draw attention
                self.save_metadata_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {self.theme_colors['accent']};
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 10px 20px;
                        font-weight: 600;
                        min-height: 36px;
                    }}
                    QPushButton:hover {{
                        background: {self.theme_colors['text_primary']};
                        color: white;
                    }}
                """)
            else:
                # Disabled state with grayed out text
                disabled_text_color = "#808080" if self.is_dark_mode else "#A0A0A0"
                self.save_metadata_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {self.theme_colors['bg_secondary']};
                        color: {disabled_text_color};
                        border: 1px solid {self.theme_colors['border']};
                        border-radius: 6px;
                        padding: 10px 20px;
                        font-weight: 600;
                        min-height: 36px;
                        opacity: 0.6;
                    }}
                    QPushButton:disabled {{
                        color: {disabled_text_color};
                        opacity: 0.6;
                    }}
                """)

    def _check_unsaved_changes_before_close(self):
        """Check for unsaved changes and prompt user. Returns True if OK to close, False otherwise."""
        if self._has_unsaved_changes():
            from PyQt6.QtWidgets import QMessageBox

            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save them before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )

            if reply == QMessageBox.StandardButton.Save:
                # Save the metadata
                self._save_metadata()
                return True
            # Discard -> close without saving; Cancel -> don't close
            return reply == QMessageBox.StandardButton.Discard
        # No unsaved changes, OK to close
        return True

    def accept(self):  # noqa: N802
        """Override accept to check for unsaved changes before closing."""
        if self._check_unsaved_changes_before_close():
            super().accept()

    def reject(self):  # noqa: N802
        """Override reject to check for unsaved changes before closing."""
        if self._check_unsaved_changes_before_close():
            super().reject()

    def closeEvent(self, event):  # noqa: N802
        """Handle dialog close - prompt if there are unsaved changes."""
        if self._check_unsaved_changes_before_close():
            event.accept()
        else:
            event.ignore()


class FileDetailsGrid(QWidget):
    """
    Main grid widget for displaying file analysis details.

    Features:
    - Advanced filtering (quick filters, column filters, search)
    - Multi-column sorting
    - Column visibility management
    - Context menu actions
    - Export to CSV
    """

    re_analyze_requested = pyqtSignal(list)  # Emits list of file paths

    def __init__(self, parent=None, analysis_db=None, metadata_db=None):
        super().__init__(parent)

        # Store database references
        self.analysis_db = analysis_db
        self.metadata_db = metadata_db

        # Get theme from parent
        self.is_dark_mode = False
        if parent and hasattr(parent, "is_dark_mode"):
            self.is_dark_mode = parent.is_dark_mode

        # Get theme colors
        self.theme_colors = self._get_theme_colors()

        # Get config manager from parent or create new one
        self.config_manager = None
        if parent and hasattr(parent, "config_manager"):
            self.config_manager = parent.config_manager
        else:
            from config.config_manager import ConfigManager

            self.config_manager = ConfigManager()

        self.model = FileDetailsTableModel()
        self.proxy_model = FileDetailsSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self._init_ui()

    def _get_theme_colors(self):
        """Return color palette based on current theme (matching analysis_status_window)"""
        if self.is_dark_mode:
            return {
                "bg_primary": "#1E1E1E",
                "bg_secondary": "#2D2D2D",
                "bg_tertiary": "#3A3A3A",
                "text_primary": "#E0E0E0",
                "text_secondary": "#B0B0B0",
                "text_tertiary": "#808080",
                "border": "#4A4A4A",
                "input_bg": "#2D2D2D",
                "button_bg": "#3A3A3A",
                "button_hover": "#4A4A4A",
                "accent": "#3B82F6",
                "tab_active_bg": "#2D2D2D",
                "tab_inactive_bg": "#1E1E1E",
                "tab_hover_bg": "#3A3A3A",
            }
        else:
            return {
                "bg_primary": "#F9FAFB",
                "bg_secondary": "#FFFFFF",
                "bg_tertiary": "#F3F4F6",
                "text_primary": "#111827",
                "text_secondary": "#374151",
                "text_tertiary": "#6B7280",
                "border": "#E5E7EB",
                "input_bg": "#FFFFFF",
                "button_bg": "#F3F4F6",
                "button_hover": "#E5E7EB",
                "accent": "#3B82F6",
                "tab_active_bg": "#FFFFFF",
                "tab_inactive_bg": "#F3F4F6",
                "tab_hover_bg": "#E5E7EB",
            }

    def _init_ui(self):
        """Initialize the user interface."""
        # Transparent background - parent container handles the background color
        self.setStyleSheet("background-color: transparent;")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Filter toolbar with better styling
        filter_frame = QWidget()
        filter_frame.setStyleSheet(f"""
            QWidget {{
                background-color: {self.theme_colors["bg_secondary"]};
                border: 1px solid {self.theme_colors["border"]};
                border-radius: 8px;
            }}
        """)
        filter_main_layout = QVBoxLayout(filter_frame)
        filter_main_layout.setContentsMargins(12, 12, 12, 12)
        filter_main_layout.setSpacing(10)

        # Quick filters row
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)

        # Quick filter buttons
        quick_filter_label = QLabel("Quick Filters:")
        quick_filter_label.setStyleSheet(
            f"font-weight: 600; color: {self.theme_colors['text_primary']}; background: transparent; border: none; font-size: 10pt;"
        )
        filter_layout.addWidget(quick_filter_label)

        self.quick_filters = {
            "high_confidence": QPushButton("✓ High Confidence"),
            "needs_review": QPushButton("⚠ Needs Review"),
            "multi_page": QPushButton("📄 Multi-Page"),
            "recent": QPushButton("🕐 Recent (24h)"),
            "has_errors": QPushButton("❌ Has Errors"),
            "missing_metadata": QPushButton("📋 Missing Metadata"),
            "cached_only": QPushButton("⚡ Cached Only"),
        }

        button_style = f"""
            QPushButton {{
                background-color: {self.theme_colors["button_bg"]};
                border: 1px solid {self.theme_colors["border"]};
                border-radius: 4px;
                padding: 4px 10px;
                color: {self.theme_colors["text_primary"]};
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background-color: {self.theme_colors["button_hover"]};
            }}
            QPushButton:checked {{
                background-color: {self.theme_colors["accent"]};
                border-color: {self.theme_colors["accent"]};
                color: white;
                font-weight: 600;
            }}
        """

        for name, btn in self.quick_filters.items():
            btn.setCheckable(True)
            btn.setStyleSheet(button_style)
            btn.clicked.connect(
                lambda checked, n=name: self._apply_quick_filter(n if checked else None)
            )
            filter_layout.addWidget(btn)

        filter_layout.addStretch()

        filter_main_layout.addLayout(filter_layout)

        # Dropdown filters row
        dropdown_layout = QHBoxLayout()
        dropdown_layout.setContentsMargins(0, 0, 0, 0)

        combo_style = f"""
            QComboBox {{
                background-color: {self.theme_colors["input_bg"]};
                border: 1px solid {self.theme_colors["border"]};
                border-radius: 4px;
                padding: 4px 8px;
                min-width: 120px;
                color: {self.theme_colors["text_primary"]};
                font-size: 9pt;
            }}
            QComboBox:hover {{
                background-color: {self.theme_colors["button_hover"]};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {self.theme_colors["text_secondary"]};
                margin-right: 5px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {self.theme_colors["bg_secondary"]};
                color: {self.theme_colors["text_primary"]};
                selection-background-color: {self.theme_colors["accent"]};
                border: 1px solid {self.theme_colors["border"]};
            }}
        """

        self.status_filter = QComboBox()
        self.status_filter.setStyleSheet(combo_style)
        self.status_filter.addItem("All Status", None)
        self.status_filter.addItem("Analyzed", "Analyzed")
        self.status_filter.addItem("Cached", "Cached")
        self.status_filter.addItem("Failed", "Failed")
        self.status_filter.currentIndexChanged.connect(self._apply_column_filters)

        status_label = QLabel("Status:")
        status_label.setStyleSheet(
            f"font-weight: 600; color: {self.theme_colors['text_primary']}; background: transparent; border: none; font-size: 9pt;"
        )
        dropdown_layout.addWidget(status_label)
        dropdown_layout.addWidget(self.status_filter)

        self.company_filter = QComboBox()
        self.company_filter.setStyleSheet(combo_style)
        self.company_filter.addItem("All Companies", None)
        self.company_filter.currentIndexChanged.connect(self._apply_column_filters)

        company_label = QLabel("Company:")
        company_label.setStyleSheet(
            f"font-weight: 600; color: {self.theme_colors['text_primary']}; background: transparent; border: none; margin-left: 12px; font-size: 9pt;"
        )
        dropdown_layout.addWidget(company_label)
        dropdown_layout.addWidget(self.company_filter)

        self.type_filter = QComboBox()
        self.type_filter.setStyleSheet(combo_style)
        self.type_filter.addItem("All Types", None)
        self.type_filter.currentIndexChanged.connect(self._apply_column_filters)

        type_label = QLabel("Type:")
        type_label.setStyleSheet(
            f"font-weight: 600; color: {self.theme_colors['text_primary']}; background: transparent; border: none; margin-left: 12px; font-size: 9pt;"
        )
        dropdown_layout.addWidget(type_label)
        dropdown_layout.addWidget(self.type_filter)

        self.tax_filter = QComboBox()
        self.tax_filter.setStyleSheet(combo_style)
        self.tax_filter.addItem("All Tax Status", None)
        self.tax_filter.addItem("Tax Related", True)
        self.tax_filter.addItem("Not Tax Related", False)
        self.tax_filter.currentIndexChanged.connect(self._apply_column_filters)

        tax_label = QLabel("Tax:")
        tax_label.setStyleSheet(
            f"font-weight: 600; color: {self.theme_colors['text_primary']}; background: transparent; border: none; margin-left: 12px; font-size: 9pt;"
        )
        dropdown_layout.addWidget(tax_label)
        dropdown_layout.addWidget(self.tax_filter)

        dropdown_layout.addStretch()

        filter_main_layout.addLayout(dropdown_layout)

        layout.addWidget(filter_frame)

        # Search bar with improved styling
        search_frame = QWidget()
        search_frame.setStyleSheet("background-color: transparent;")
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(0, 0, 0, 0)

        search_label = QLabel("🔍")
        search_label.setStyleSheet(
            f"font-size: 12pt; color: {self.theme_colors['text_secondary']}; background: transparent;"
        )
        search_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search filename, company, type, dates...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.theme_colors["input_bg"]};
                border: 1px solid {self.theme_colors["border"]};
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 10pt;
                color: {self.theme_colors["text_primary"]};
            }}
            QLineEdit:focus {{
                border-color: {self.theme_colors["accent"]};
            }}
        """)
        self.search_input.textChanged.connect(self._apply_search)
        search_layout.addWidget(self.search_input, stretch=1)

        action_button_style = f"""
            QPushButton {{
                background-color: {self.theme_colors["button_bg"]};
                border: 1px solid {self.theme_colors["border"]};
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 600;
                color: {self.theme_colors["text_primary"]};
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background-color: {self.theme_colors["button_hover"]};
            }}
        """

        clear_btn = QPushButton("Clear All")
        clear_btn.setStyleSheet(action_button_style)
        clear_btn.clicked.connect(self._clear_all_filters)
        search_layout.addWidget(clear_btn)

        export_btn = QPushButton("Export CSV")
        export_btn.setStyleSheet(action_button_style)
        export_btn.clicked.connect(self._export_csv)
        search_layout.addWidget(export_btn)

        layout.addWidget(search_frame)

        # Table view with professional styling
        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)
        self.table_view.doubleClicked.connect(self._show_details_dialog)
        self.table_view.setShowGrid(False)

        # Connect selection change to update status label
        self.table_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.table_view.setStyleSheet(f"""
            QTableView {{
                background-color: {self.theme_colors["bg_secondary"]};
                border: 1px solid {self.theme_colors["border"]};
                border-radius: 4px;
                gridline-color: {self.theme_colors["border"]};
                selection-background-color: {self.theme_colors["accent"]}40;
                selection-color: {self.theme_colors["text_primary"]};
                color: {self.theme_colors["text_primary"]};
            }}
            QTableView::item {{
                padding: 6px;
                border-bottom: 1px solid {self.theme_colors["border"]};
            }}
            QTableView::item:selected {{
                background-color: {self.theme_colors["accent"]}40;
            }}
            QTableView::item:hover {{
                background-color: {self.theme_colors["bg_tertiary"]};
            }}
            QHeaderView::section {{
                background-color: {self.theme_colors["bg_tertiary"]};
                color: {self.theme_colors["text_primary"]};
                font-weight: 600;
                padding: 8px;
                border: none;
                border-bottom: 2px solid {self.theme_colors["border"]};
                border-right: 1px solid {self.theme_colors["border"]};
                font-size: 9pt;
            }}
            QHeaderView::section:hover {{
                background-color: {self.theme_colors["button_hover"]};
            }}
        """)

        # Configure header
        header = self.table_view.horizontalHeader()
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_column_menu)
        header.setSectionsMovable(True)
        header.setStretchLastSection(True)
        header.setDefaultSectionSize(120)
        header.setMinimumSectionSize(60)

        # Set initial column widths
        for i in range(self.model.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)

        # Connect signals for persisting column state
        header.sectionResized.connect(self._save_column_state)
        header.sectionMoved.connect(self._save_column_state)

        # Set row height
        self.table_view.verticalHeader().setDefaultSectionSize(36)
        self.table_view.verticalHeader().setVisible(False)  # Hide row numbers

        layout.addWidget(self.table_view, stretch=1)

        # Load saved column state after UI is initialized
        self._load_column_state()

        # Status bar with better styling
        status_frame = QWidget()
        status_frame.setStyleSheet(f"""
            QWidget {{
                background-color: {self.theme_colors["bg_secondary"]};
                border: 1px solid {self.theme_colors["border"]};
                border-radius: 4px;
            }}
        """)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(10, 6, 10, 6)

        self.status_label = QLabel("No files loaded")
        self.status_label.setStyleSheet(
            f"font-weight: 600; color: {self.theme_colors['text_primary']}; font-size: 9pt; background: transparent; border: none;"
        )
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        refresh_hint = QLabel("💡 Double-click to view details | Right-click for actions")
        refresh_hint.setStyleSheet(
            f"color: {self.theme_colors['text_tertiary']}; font-size: 8pt; background: transparent; border: none;"
        )
        status_layout.addWidget(refresh_hint)

        layout.addWidget(status_frame)

    def refresh_data(self, data: list[dict[str, Any]]):
        """Refresh the grid with new data."""
        self.model.set_data(data)
        self._update_filter_dropdowns(data)
        self._update_status_label()

        # Auto-resize columns on first load
        if data:
            self.table_view.resizeColumnsToContents()

    def _save_column_state(self):
        """Save column widths, order, and visibility to config."""
        if not self.config_manager:
            return

        header = self.table_view.horizontalHeader()

        # Save column widths
        widths = []
        for i in range(self.model.columnCount()):
            widths.append(header.sectionSize(i))

        # Save visual index order (for moved columns)
        visual_order = []
        for i in range(self.model.columnCount()):
            visual_order.append(header.visualIndex(i))

        # Save visible columns
        visible_columns = self.model.get_visible_columns()

        # Store as JSON in config
        import json

        self.config_manager.set_setting("FileGridColumns", "widths", json.dumps(widths))
        self.config_manager.set_setting("FileGridColumns", "visual_order", json.dumps(visual_order))
        self.config_manager.set_setting(
            "FileGridColumns", "visible_columns", json.dumps(visible_columns)
        )

    def _load_column_state(self):
        """Load column widths, order, and visibility from config."""
        if not self.config_manager:
            return

        import json

        try:
            # Load column widths
            widths_json = self.config_manager.get_setting("FileGridColumns", "widths")
            if widths_json:
                widths = json.loads(widths_json)
                header = self.table_view.horizontalHeader()
                for i, width in enumerate(widths):
                    if i < self.model.columnCount():
                        header.resizeSection(i, width)

            # Load visual order (column positions)
            order_json = self.config_manager.get_setting("FileGridColumns", "visual_order")
            if order_json:
                visual_order = json.loads(order_json)
                header = self.table_view.horizontalHeader()
                for logical_index, visual_index in enumerate(visual_order):
                    if logical_index < self.model.columnCount():
                        header.moveSection(header.visualIndex(logical_index), visual_index)

            # Load visible columns
            visible_json = self.config_manager.get_setting("FileGridColumns", "visible_columns")
            if visible_json:
                visible_columns = json.loads(visible_json)
                self.model.set_visible_columns(visible_columns)
                # Update column visibility in view
                for i in range(len(self.model.COLUMNS)):
                    self.table_view.setColumnHidden(i, i not in visible_columns)
        except (json.JSONDecodeError, ValueError, TypeError):
            # If there's any error loading the config, just use defaults
            pass

    def apply_quick_filter(self, filter_name: str):
        """Apply a quick filter preset (for cross-tab navigation)."""
        # Uncheck all other quick filter buttons
        for name, btn in self.quick_filters.items():
            btn.setChecked(name == filter_name)

        self._apply_quick_filter(filter_name)

    def _apply_quick_filter(self, filter_name: str | None):
        """Apply quick filter to proxy model."""
        # Uncheck other quick filter buttons
        for name, btn in self.quick_filters.items():
            if name != filter_name:
                btn.setChecked(False)

        self.proxy_model.set_quick_filter(filter_name)
        self._update_status_label()

    def _apply_column_filters(self):
        """Apply column-specific filters."""
        filters = {}

        status = self.status_filter.currentData()
        if status:
            filters["status"] = status

        company = self.company_filter.currentData()
        if company:
            filters["company"] = company

        doc_type = self.type_filter.currentData()
        if doc_type:
            filters["document_type"] = doc_type

        tax_related = self.tax_filter.currentData()
        if tax_related is not None:
            filters["tax_related"] = tax_related

        self.proxy_model.set_filters(filters)
        self._update_status_label()

    def _apply_search(self, text: str):
        """Apply search filter."""
        self.proxy_model.set_search_text(text)
        self._update_status_label()

    def _clear_all_filters(self):
        """Clear all filters and search."""
        # Clear quick filters
        for btn in self.quick_filters.values():
            btn.setChecked(False)
        self.proxy_model.set_quick_filter(None)

        # Clear column filters
        self.status_filter.setCurrentIndex(0)
        self.company_filter.setCurrentIndex(0)
        self.type_filter.setCurrentIndex(0)
        self.tax_filter.setCurrentIndex(0)
        self.proxy_model.set_filters({})

        # Clear search
        self.search_input.clear()
        self.proxy_model.set_search_text("")

        self._update_status_label()

    def _update_filter_dropdowns(self, data: list[dict[str, Any]]):
        """Update filter dropdown options based on data."""
        # Update company filter
        companies = sorted({str(item.get("company")) for item in data if item.get("company")})
        current_company = self.company_filter.currentData()
        self.company_filter.clear()
        self.company_filter.addItem("All Companies", None)
        for company in companies:
            self.company_filter.addItem(company, company)
        if current_company:
            index = self.company_filter.findData(current_company)
            if index >= 0:
                self.company_filter.setCurrentIndex(index)

        # Update type filter
        types = sorted(
            {str(item.get("document_type")) for item in data if item.get("document_type")}
        )
        current_type = self.type_filter.currentData()
        self.type_filter.clear()
        self.type_filter.addItem("All Types", None)
        for doc_type in types:
            self.type_filter.addItem(doc_type, doc_type)
        if current_type:
            index = self.type_filter.findData(current_type)
            if index >= 0:
                self.type_filter.setCurrentIndex(index)

    def _update_status_label(self):
        """Update status label with current counts."""
        total_rows = self.model.rowCount()
        visible_rows = self.proxy_model.rowCount()

        # Check if there are selected rows
        selected_rows = len(self.table_view.selectionModel().selectedRows())

        if selected_rows > 0:
            # Show selection count
            self.status_label.setText(f"Selected {selected_rows} files")
        elif visible_rows == total_rows:
            self.status_label.setText(f"Showing {total_rows} files")
        else:
            self.status_label.setText(f"Showing {visible_rows} of {total_rows} files")

    def _on_selection_changed(self):
        """Handle selection changes in the table view."""
        self._update_status_label()

    def _show_column_menu(self, pos):
        """Show column visibility menu."""
        menu = QMenu(self)

        # Get theme colors
        bg_secondary = self.theme_colors.get(
            "bg_secondary", "#2D2D2D" if self.is_dark_mode else "#FFFFFF"
        )
        text_primary = self.theme_colors.get(
            "text_primary", "#E0E0E0" if self.is_dark_mode else "#111827"
        )
        border = self.theme_colors.get("border", "#4A4A4A" if self.is_dark_mode else "#E5E7EB")
        accent = self.theme_colors.get("accent", "#3B82F6")

        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {bg_secondary};
                color: {text_primary};
                border: 1px solid {border};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
                background-color: transparent;
            }}
            QMenu::item:selected {{
                background-color: {accent};
                color: white;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {border};
                margin: 4px 8px;
            }}
        """)

        for i, (_, col_name, _) in enumerate(FileDetailsTableModel.COLUMNS):
            action = QAction(col_name, menu)
            action.setCheckable(True)
            action.setChecked(i in self.model.get_visible_columns())
            action.triggered.connect(lambda checked, idx=i: self._toggle_column(idx, checked))
            menu.addAction(action)

        menu.exec(self.table_view.horizontalHeader().mapToGlobal(pos))

    def _toggle_column(self, col_index: int, visible: bool):
        """Toggle column visibility."""
        visible_columns = self.model.get_visible_columns()

        if visible and col_index not in visible_columns:
            visible_columns.append(col_index)
        elif not visible and col_index in visible_columns:
            visible_columns.remove(col_index)

        self.model.set_visible_columns(visible_columns)
        # Save column state when visibility changes
        self._save_column_state()

    def _show_context_menu(self, pos):
        """Show context menu for row actions."""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            return

        menu = QMenu(self)

        # Get theme colors with fallbacks
        bg_secondary = self.theme_colors.get(
            "bg_secondary", "#2D2D2D" if self.is_dark_mode else "#FFFFFF"
        )
        text_primary = self.theme_colors.get(
            "text_primary", "#E0E0E0" if self.is_dark_mode else "#111827"
        )
        border = self.theme_colors.get("border", "#4A4A4A" if self.is_dark_mode else "#E5E7EB")
        accent = self.theme_colors.get("accent", "#3B82F6")

        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {bg_secondary};
                color: {text_primary};
                border: 1px solid {border};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
                background-color: transparent;
            }}
            QMenu::item:selected {{
                background-color: {accent};
                color: white;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {border};
                margin: 4px 8px;
            }}
        """)

        # Open Document (only show if single selection)
        if len(selection) == 1:
            open_action = QAction("📄 Open Document", menu)
            open_action.triggered.connect(self._view_selected_document)
            menu.addAction(open_action)
            menu.addSeparator()

        re_analyze_action = QAction("Re-analyze Selected", menu)
        re_analyze_action.triggered.connect(self._re_analyze_selected)
        menu.addAction(re_analyze_action)

        # Check if any selected files have error status
        has_errors = False
        for index in selection:
            source_index = self.proxy_model.mapToSource(index)
            row_data = self.model.get_row_data(source_index.row())
            if row_data:
                status = row_data.get("status", "")
                error_msg = row_data.get("error_message", "")
                if status == "Failed" or error_msg:
                    has_errors = True
                    break

        # Add Clear Error option if any selected files have errors
        if has_errors:
            clear_error_action = QAction("Clear Error", menu)
            clear_error_action.triggered.connect(self._clear_error_for_selected)
            menu.addAction(clear_error_action)

        menu.addSeparator()

        export_action = QAction("Export Selected to CSV", menu)
        export_action.triggered.connect(lambda: self._export_csv(selected_only=True))
        menu.addAction(export_action)

        copy_action = QAction("Copy to Clipboard (TSV)", menu)
        copy_action.triggered.connect(self._copy_to_clipboard)
        menu.addAction(copy_action)

        copy_filename_action = QAction("Copy file name", menu)
        copy_filename_action.triggered.connect(self._copy_filename_to_clipboard)
        menu.addAction(copy_filename_action)

        copy_filepath_action = QAction("Copy file path", menu)
        copy_filepath_action.triggered.connect(self._copy_filepath_to_clipboard)
        menu.addAction(copy_filepath_action)

        menu.addSeparator()

        delete_action = QAction("Delete from Database", menu)
        delete_action.triggered.connect(self._delete_selected)
        menu.addAction(delete_action)

        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    def _find_actual_file_path(self, stored_path, filename):
        """Find the actual file path, searching source directories if needed."""
        # First, check if the stored path exists and is not in a temp folder
        if stored_path and os.path.exists(stored_path):
            # Check if it's in a temp folder
            temp_indicators = ["temp", "tmp", "AppData\\Local\\Temp"]
            if not any(indicator in stored_path for indicator in temp_indicators):
                return stored_path

        # If stored path doesn't exist or is in temp, search source directories
        if self.parent() and hasattr(self.parent(), "config_manager"):
            config_manager = self.parent().config_manager
            directories = config_manager.get_directories()

            # Search for the file by name in all source directories
            for directory in directories:
                if not os.path.exists(directory):
                    continue

                for root, _, files in os.walk(directory):
                    if filename in files:
                        found_path = os.path.join(root, filename)
                        if os.path.exists(found_path):
                            return found_path

        return None

    def _view_selected_document(self):
        """Open the selected document with the default system viewer."""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            return

        # Get the first (and should be only) selected row
        index = selection[0]
        source_index = self.proxy_model.mapToSource(index)
        row_data = self.model.get_row_data(source_index.row())

        if not row_data:
            return

        stored_path = row_data.get("full_path")
        filename = row_data.get("filename")

        if not filename:
            QMessageBox.warning(
                self, "File Name Not Found", "Could not find the file name for this record."
            )
            return

        # Find the actual file path
        file_path = self._find_actual_file_path(stored_path, filename)

        if not file_path:
            QMessageBox.warning(
                self,
                "File Not Found",
                f"Could not find the file:\n\n{filename}\n\nSearched in configured source directories.",
            )
            return

        try:
            # Open file with default system viewer
            os.startfile(file_path)
        except Exception as e:
            QMessageBox.critical(self, "Error Opening File", f"Failed to open file:\n\n{str(e)}")

    def _show_details_dialog(self, index: QModelIndex):
        """Show details dialog for double-clicked row."""
        source_index = self.proxy_model.mapToSource(index)
        row_data = self.model.get_row_data(source_index.row())

        if row_data:
            dialog = FileDetailsDialog(
                row_data,
                self,
                analysis_db=self.analysis_db,
                metadata_db=self.metadata_db,
                config_manager=self.config_manager,
            )
            dialog.re_analyze_requested.connect(lambda path: self.re_analyze_requested.emit([path]))
            dialog.metadata_saved.connect(self._on_metadata_saved)
            dialog.exec()

    def _on_metadata_saved(self, file_path: str):
        """Handle metadata saved signal - refresh the row data for the updated file."""
        from services.logging_service import get_logger

        logger = get_logger()

        if not self.analysis_db:
            return

        # Get fresh analysis from database
        fresh_analysis = self.analysis_db.get_analysis(file_path)
        if not fresh_analysis:
            return

        # Also get the rotation field from image_files table (not in analysis_results) via MetadataDB
        rotation_degrees = self.metadata_db.get_image_rotation(file_path)
        fresh_analysis["rotation"] = rotation_degrees
        logger.debug(
            f"[GRID UPDATE] Updating row for {file_path} with rotation={rotation_degrees}°"
        )

        # Find and update the row in the model
        for row in range(self.model.rowCount()):
            row_data = self.model.get_row_data(row)
            if row_data and row_data.get("full_path") == file_path:
                # Update the row data with fresh values
                old_rotation = row_data.get("rotation")
                for key, value in fresh_analysis.items():
                    row_data[key] = value
                logger.debug(
                    f"[GRID UPDATE] Row {row} updated: rotation changed from {old_rotation}° to {row_data.get('rotation')}°"
                )

                # Notify model that data changed
                self.model.dataChanged.emit(
                    self.model.index(row, 0), self.model.index(row, self.model.columnCount() - 1)
                )

                # Force proxy model to refresh - critical for view to update
                self.proxy_model.invalidate()

                # Force table view to update display
                self.table_view.viewport().update()

                logger.debug(
                    f"[GRID UPDATE] Emitted dataChanged signal for row {row}, invalidated proxy model"
                )
                break

    def _clear_error_for_selected(self):
        """Clear error status for selected files, resetting them to pending."""
        selection = self.table_view.selectionModel().selectedRows()
        files_to_clear = []

        for index in selection:
            source_index = self.proxy_model.mapToSource(index)
            row_data = self.model.get_row_data(source_index.row())
            if row_data:
                status = row_data.get("status", "")
                error_msg = row_data.get("error_message", "")
                if status == "Failed" or error_msg:
                    file_path = row_data.get("full_path") or row_data.get("filename")
                    if file_path:
                        files_to_clear.append((file_path, source_index.row()))

        if not files_to_clear:
            return

        reply = QMessageBox.question(
            self,
            "Clear Errors",
            f"Reset {len(files_to_clear)} file(s) to pending status?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if reply == QMessageBox.StandardButton.Yes and self.analysis_db:
            for file_path, row_idx in files_to_clear:
                try:
                    # Reset status to pending in database
                    self.analysis_db.update_analysis_status(file_path, "Pending")

                    # Update the row data in the model
                    row_data = self.model.get_row_data(row_idx)
                    if row_data:
                        row_data["status"] = "Pending"
                        row_data["error_message"] = None
                        # Notify model that data changed
                        self.model.dataChanged.emit(
                            self.model.index(row_idx, 0),
                            self.model.index(row_idx, self.model.columnCount() - 1),
                        )
                except Exception as e:
                    QMessageBox.warning(
                        self,
                        "Clear Error Failed",
                        f"Failed to clear error for {file_path}:\n\n{str(e)}",
                    )

    def _re_analyze_selected(self):
        """Request re-analysis of selected files."""
        selection = self.table_view.selectionModel().selectedRows()
        file_paths = []

        for index in selection:
            source_index = self.proxy_model.mapToSource(index)
            row_data = self.model.get_row_data(source_index.row())
            if row_data:
                file_path = row_data.get("full_path") or row_data.get("filename")
                if file_path:
                    file_paths.append(file_path)

        if file_paths:
            reply = QMessageBox.question(
                self,
                "Re-analyze Files",
                f"Re-analyze {len(file_paths)} selected file(s)?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.re_analyze_requested.emit(file_paths)

    def _export_csv(self, selected_only: bool = False):
        """Export data to CSV file."""
        from PyQt6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export to CSV", "file_analysis.csv", "CSV Files (*.csv);;All Files (*.*)"
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                # Write headers
                headers = []
                for col_idx in self.model.get_visible_columns():
                    _, col_name, _ = FileDetailsTableModel.COLUMNS[col_idx]
                    headers.append(col_name)
                writer.writerow(headers)

                # Write data
                if selected_only:
                    indices = self.table_view.selectionModel().selectedRows()
                else:
                    indices = [
                        self.proxy_model.index(row, 0) for row in range(self.proxy_model.rowCount())
                    ]

                for index in indices:
                    source_index = self.proxy_model.mapToSource(index)
                    row_data = self.model.get_row_data(source_index.row())

                    if row_data:
                        row = []
                        for col_idx in self.model.get_visible_columns():
                            col_key, _, _ = FileDetailsTableModel.COLUMNS[col_idx]
                            value = row_data.get(col_key, "")
                            row.append(str(value) if value is not None else "")
                        writer.writerow(row)

            QMessageBox.information(self, "Export Complete", f"Data exported to {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export data: {str(e)}")

    def _copy_to_clipboard(self):
        """Copy selected rows to clipboard as TSV."""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            return

        # Build TSV string
        lines = []

        # Headers
        headers = []
        for col_idx in self.model.get_visible_columns():
            _, col_name, _ = FileDetailsTableModel.COLUMNS[col_idx]
            headers.append(col_name)
        lines.append("\t".join(headers))

        # Data rows
        for index in selection:
            source_index = self.proxy_model.mapToSource(index)
            row_data = self.model.get_row_data(source_index.row())

            if row_data:
                row = []
                for col_idx in self.model.get_visible_columns():
                    col_key, _, _ = FileDetailsTableModel.COLUMNS[col_idx]
                    value = row_data.get(col_key, "")
                    row.append(str(value) if value is not None else "")
                lines.append("\t".join(row))

        tsv_string = "\n".join(lines)
        QApplication.clipboard().setText(tsv_string)

        QMessageBox.information(self, "Copied", f"{len(selection)} rows copied to clipboard")

    def _copy_filename_to_clipboard(self):
        """Copy selected filenames to clipboard."""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            return

        filenames = []
        for index in selection:
            source_index = self.proxy_model.mapToSource(index)
            row_data = self.model.get_row_data(source_index.row())

            if row_data:
                filename = row_data.get("filename", "")
                if filename:
                    filenames.append(os.path.basename(filename))

        if filenames:
            clipboard_text = ", ".join(filenames)
            QApplication.clipboard().setText(clipboard_text)

    def _copy_filepath_to_clipboard(self):
        """Copy selected file paths to clipboard."""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            return

        file_paths = []
        for index in selection:
            source_index = self.proxy_model.mapToSource(index)
            row_data = self.model.get_row_data(source_index.row())

            if row_data:
                file_path = row_data.get("full_path", "")
                if file_path:
                    file_paths.append(file_path)

        if file_paths:
            clipboard_text = ", ".join(file_paths)
            QApplication.clipboard().setText(clipboard_text)

    def _delete_selected(self):
        """Delete selected rows from database."""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            return

        reply = QMessageBox.warning(
            self,
            "Delete Records",
            f"Delete {len(selection)} record(s) from the database?\n\nThis will NOT delete the actual files.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Get database instances from parent chain
            parent_widget = self.parent()
            analysis_db = None

            while parent_widget:
                if hasattr(parent_widget, "analysis_db"):
                    analysis_db = parent_widget.analysis_db
                    break
                parent_widget = parent_widget.parent() if hasattr(parent_widget, "parent") else None

            if not analysis_db:
                QMessageBox.warning(
                    self,
                    "Database Not Available",
                    "Cannot delete records: database connection not available.",
                )
                return

            # Collect file paths from selected rows
            file_paths = []
            for index in selection:
                source_index = self.proxy_model.mapToSource(index)
                row_data = self.model.get_row_data(source_index.row())
                if row_data:
                    file_path = row_data.get("full_path")
                    if file_path:
                        file_paths.append(file_path)

            if not file_paths:
                QMessageBox.warning(self, "No Records", "No valid records found to delete.")
                return

            # Delete from all databases
            deleted_count = 0
            errors = []

            for file_path in file_paths:
                try:
                    # 1. Mark image as deleted in image_files table (soft delete)
                    # This will CASCADE to analysis_results via foreign key
                    analysis_db.mark_image_deleted(file_path)

                    # 2. Delete from metadata table (using AnalysisDB facade)
                    analysis_db.delete_metadata_by_path(file_path)

                    deleted_count += 1
                except Exception as e:
                    errors.append(f"{file_path}: {str(e)}")

            # Refresh the grid by reloading from database
            if hasattr(self.parent(), "_refresh_file_grid"):
                self.parent()._refresh_file_grid()
            else:
                # Fallback: reload current data excluding deleted files
                updated_data = [
                    row for row in self.model._data if row.get("full_path") not in file_paths
                ]
                self.refresh_data(updated_data)

            # Show result message
            if deleted_count > 0:
                message = f"Successfully deleted {deleted_count} record(s) from the database."
                if errors:
                    message += f"\n\nErrors ({len(errors)}):\n" + "\n".join(errors[:5])
                    if len(errors) > 5:
                        message += f"\n... and {len(errors) - 5} more errors"
                QMessageBox.information(self, "Deletion Complete", message)
            else:
                QMessageBox.warning(
                    self, "Deletion Failed", "No records were deleted.\n\n" + "\n".join(errors[:10])
                )
