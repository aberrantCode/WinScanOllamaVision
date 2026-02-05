"""
File Analysis Grid Component

Provides a comprehensive grid view of all analyzed files with advanced filtering,
sorting, and data export capabilities.
"""

import csv
import json
import os
from datetime import datetime
from typing import Any

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QAction, QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


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
        ("file_size", "Size", True),
        ("modified_time", "Modified", True),
        ("analysis_time", "Analyzed", False),
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
            if isinstance(value, (int, float)):
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
            conf = float(value) if isinstance(value, (int, float)) else 0
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
        if col_key == "confidence" and isinstance(value, (int, float)) and value < 50:
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
        """Format datetime for display."""
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt)
            except (ValueError, TypeError):
                return str(dt)

        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d %H:%M")

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
            if isinstance(filter_value, (list, tuple, set)):
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
            return bool(row_data.get("error_message"))

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

    def __init__(self, file_data: dict[str, Any], parent=None, analysis_db=None):
        super().__init__(parent)
        self.file_data = file_data
        self.analysis_db = analysis_db  # Store database reference
        self.setWindowTitle(
            f"File Details - {os.path.basename(file_data.get('filename', 'Unknown'))}"
        )
        self.setMinimumSize(1050, 800)  # Increased by 50% for better visibility

        # Get theme from parent
        self.is_dark_mode = False
        if parent and hasattr(parent, "is_dark_mode"):
            self.is_dark_mode = parent.is_dark_mode
        self.theme_colors = self._get_theme_colors()

        self.accordion_sections = []  # Track accordion sections

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

        # Image preview label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(f"""
            QLabel {{
                background-color: {self.theme_colors["bg_primary"]};
                border: 2px solid {self.theme_colors["border"]};
                border-radius: 8px;
                padding: 10px;
            }}
        """)

        # Load and display image (path already corrected in __init__)
        file_path = self.file_data.get("full_path")

        if file_path and os.path.exists(file_path):
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                # Store original pixmap for potential rescaling
                self.original_pixmap = pixmap

                # Calculate available width (50% of dialog width minus margins/padding/border)
                # Dialog width: 1050, 50% = 525, minus margins (15*2) and border/padding (~20) = ~480
                available_width = 480

                # Scale to fit width while maintaining aspect ratio
                scaled_pixmap = pixmap.scaledToWidth(
                    available_width, Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
            else:
                self.original_pixmap = None
                self.image_label.setText("Failed to load image")
                self.image_label.setStyleSheet(f"color: {self.theme_colors['text_secondary']};")
        else:
            self.original_pixmap = None
            self.image_label.setText(f"Image not found\n{file_path or 'No path'}")
            self.image_label.setStyleSheet(f"color: {self.theme_colors['text_secondary']};")

        left_layout.addWidget(self.image_label)

        # Store references for dynamic resizing
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
        accordion_layout.setContentsMargins(15, 15, 15, 15)
        accordion_layout.setSpacing(12)

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

        # Raw Response Section
        raw_response_section = self._create_accordion_section(
            "💬 Raw LLM Response", self._create_raw_response_content()
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

        # Button box at bottom
        button_box = QDialogButtonBox()
        button_box.setStyleSheet(
            f"background-color: {self.theme_colors['bg_secondary']}; padding: 10px;"
        )

        open_doc_btn = QPushButton("📄 Open Document")
        open_doc_btn.clicked.connect(self._view_document)
        button_box.addButton(open_doc_btn, QDialogButtonBox.ButtonRole.ActionRole)

        save_metadata_btn = QPushButton("💾 Save Metadata")
        save_metadata_btn.clicked.connect(self._save_metadata)
        button_box.addButton(save_metadata_btn, QDialogButtonBox.ButtonRole.ActionRole)

        copy_json_btn = QPushButton("Copy JSON")
        copy_json_btn.clicked.connect(self._copy_json)
        button_box.addButton(copy_json_btn, QDialogButtonBox.ButtonRole.ActionRole)

        re_analyze_btn = QPushButton("Re-analyze")
        re_analyze_btn.clicked.connect(self._re_analyze)
        button_box.addButton(re_analyze_btn, QDialogButtonBox.ButtonRole.ActionRole)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_box.addButton(close_btn, QDialogButtonBox.ButtonRole.RejectRole)

        main_layout.addWidget(button_box)

    def _format_summary(self) -> str:
        """Format summary information as HTML."""
        html = "<html><body style='font-family: Segoe UI; font-size: 10pt;'>"

        # File Information
        html += "<h3 style='color: #2563eb;'>File Information</h3>"
        html += "<table cellpadding='5'>"
        html += (
            f"<tr><td><b>Filename:</b></td><td>{self.file_data.get('filename', 'N/A')}</td></tr>"
        )
        html += (
            f"<tr><td><b>Full Path:</b></td><td>{self.file_data.get('full_path', 'N/A')}</td></tr>"
        )
        html += f"<tr><td><b>File Size:</b></td><td>{self._format_size(self.file_data.get('file_size'))}</td></tr>"
        html += f"<tr><td><b>Modified:</b></td><td>{self._format_dt(self.file_data.get('modified_time'))}</td></tr>"
        html += (
            f"<tr><td><b>File Hash:</b></td><td>{self.file_data.get('file_hash', 'N/A')}</td></tr>"
        )
        html += "</table>"

        # Analysis Information
        html += "<h3 style='color: #2563eb;'>Analysis Information</h3>"
        html += "<table cellpadding='5'>"
        html += f"<tr><td><b>Status:</b></td><td>{self.file_data.get('status', 'N/A')}</td></tr>"
        html += f"<tr><td><b>Analyzed:</b></td><td>{self._format_dt(self.file_data.get('analysis_time'))}</td></tr>"
        html += f"<tr><td><b>Processing Time:</b></td><td>{self._format_duration(self.file_data.get('processing_duration'))}</td></tr>"
        html += (
            f"<tr><td><b>Provider:</b></td><td>{self.file_data.get('provider', 'N/A')}</td></tr>"
        )
        html += f"<tr><td><b>Model:</b></td><td>{self.file_data.get('model_used', 'N/A')}</td></tr>"
        html += f"<tr><td><b>Cached:</b></td><td>{'Yes' if self.file_data.get('cache_hit') else 'No'}</td></tr>"

        if self.file_data.get("error_message"):
            html += f"<tr><td><b>Error:</b></td><td style='color: red;'>{self.file_data.get('error_message')}</td></tr>"

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
            html += f"<tr><td><b>Confidence:</b></td><td>{confidence}</td></tr>"

        html += f"<tr><td><b>Company:</b></td><td>{self.file_data.get('company', 'N/A')}</td></tr>"
        html += f"<tr><td><b>Document Type:</b></td><td>{self.file_data.get('document_type', 'N/A')}</td></tr>"
        html += f"<tr><td><b>Document Date:</b></td><td>{self.file_data.get('document_date', 'N/A')}</td></tr>"

        page_num = self.file_data.get("page_number")
        total_pages = self.file_data.get("total_pages")
        if page_num and total_pages:
            html += f"<tr><td><b>Pages:</b></td><td>{page_num} of {total_pages}</td></tr>"
        elif page_num:
            html += f"<tr><td><b>Page Number:</b></td><td>{page_num}</td></tr>"
        elif total_pages:
            html += f"<tr><td><b>Total Pages:</b></td><td>{total_pages}</td></tr>"

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
        """Format datetime."""
        if not dt:
            return "N/A"
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt)
            except (ValueError, TypeError):
                return str(dt)
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return str(dt)

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

            # If expanding this section, collapse all others
            if not is_visible:
                for other_section in getattr(self, "accordion_sections", []):
                    if other_section != section:
                        # Find and collapse other sections
                        other_content = other_section.findChild(QFrame, "accordion_content")
                        other_toggle = other_section.findChild(QLabel, "accordion_toggle")
                        if other_content:
                            other_content.setVisible(False)
                        if other_toggle:
                            other_toggle.setText("▶")

            # Toggle this section
            content_frame.setVisible(not is_visible)
            toggle_indicator.setText("▶" if is_visible else "▼")

        header.mousePressEvent = lambda e: toggle()
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

    def _get_distinct_values(self, field_name):
        """Get distinct values for a field from database."""
        if not self.analysis_db:
            return []

        try:
            # Get distinct values from analysis_db
            query = f"SELECT DISTINCT {field_name} FROM analyses WHERE {field_name} IS NOT NULL AND {field_name} != '' ORDER BY {field_name}"
            result = self.analysis_db.conn.execute(query).fetchall()
            return [row[0] for row in result if row[0]]
        except Exception as e:
            print(f"Error getting distinct values for {field_name}: {e}")
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

            # Label
            lbl = QLabel(f"<b>{label}:</b>")
            lbl.setStyleSheet(
                f"color: {self.theme_colors['text_secondary']}; background: transparent; border: none;"
            )
            lbl.setMinimumWidth(130)
            row_layout.addWidget(lbl)

            # Input field (text, dropdown, or checkbox)
            if widget_type == "checkbox":
                input_widget = QCheckBox()
                # Handle boolean conversion
                if isinstance(current_value, bool):
                    input_widget.setChecked(current_value)
                elif isinstance(current_value, (int, str)):
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

        # Extract rotation from raw response if available
        rotation_value = ""
        raw_response = str(self.file_data.get("raw_response", ""))
        if "rotation" in raw_response.lower() or "rotate" in raw_response.lower():
            import re

            rotation_match = re.search(
                r'"rotation[^"]*":\s*"?([^",}]+)"?', raw_response, re.IGNORECASE
            )
            if rotation_match:
                rotation_value = rotation_match.group(1).strip()

        # Get distinct values from database
        distinct_document_types = self._get_distinct_values("document_type")
        distinct_companies = self._get_distinct_values("company")

        # Add all metadata fields (always show all fields, even if empty)
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

        # Confidence score (editable as percentage)
        confidence = self.file_data.get("confidence", "")
        try:
            if confidence:
                conf_float = float(confidence)
                confidence_display = (
                    f"{conf_float:.1f}" if conf_float > 1 else f"{conf_float * 100:.1f}"
                )
            else:
                confidence_display = ""
        except (ValueError, TypeError):
            confidence_display = str(confidence) if confidence else ""

        add_editable_row(
            "Confidence Score", "confidence_score", confidence_display, "0-100 percentage"
        )

        # Tax related checkbox
        add_editable_row(
            "Tax Related",
            "tax_related",
            self.file_data.get("tax_related", False),
            widget_type="checkbox",
        )

        return widget

    def _create_analysis_content(self):
        """Create analysis information content widget."""
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

        add_row("Status", self.file_data.get("status", "N/A"))
        add_row("Analyzed", self._format_dt(self.file_data.get("analysis_time")))
        add_row("Processing Time", self._format_duration(self.file_data.get("processing_duration")))
        add_row("Provider", self.file_data.get("provider", "N/A"))
        add_row("Model", self.file_data.get("model_used", "N/A"))
        add_row("Cached", "Yes" if self.file_data.get("cache_hit") else "No")

        if self.file_data.get("error_message"):
            add_row("Error", self.file_data.get("error_message"))

        return widget

    def _create_raw_response_content(self):
        """Create raw LLM response content widget."""
        raw_response = self.file_data.get("raw_response", "No raw response available")
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

    def _on_splitter_moved(self, pos, index):
        """Rescale image when splitter is moved."""
        if not hasattr(self, "original_pixmap") or self.original_pixmap is None:
            return

        # Get current width of left panel
        left_width = self.left_panel.width()

        # Calculate available width for image (subtract margins and padding)
        # Margins: 15*2, border/padding: ~20
        available_width = left_width - 50

        # Don't scale if width is too small
        if available_width < 100:
            return

        # Rescale image to fit new width
        scaled_pixmap = self.original_pixmap.scaledToWidth(
            available_width, Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)

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

        # Save to database - traverse parent chain to find database instances
        try:
            # Find parent widget with database instances
            parent_widget = self.parent()
            analysis_db = None
            metadata_db = None

            while parent_widget:
                if hasattr(parent_widget, "analysis_db") and hasattr(parent_widget, "metadata_db"):
                    analysis_db = parent_widget.analysis_db
                    metadata_db = parent_widget.metadata_db
                    break
                parent_widget = parent_widget.parent() if hasattr(parent_widget, "parent") else None

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
                        "confidence_score": updated_metadata.get("confidence_score", ""),
                        "tax_related": updated_metadata.get("tax_related", False),
                    }

                    # Update analysis database
                    analysis_db.update_analysis_metadata(file_path, metadata)

                    # Also update metadata database for backward compatibility
                    metadata_db.save_metadata(
                        file_path=file_path,
                        metadata=metadata,
                        model_used=self.file_data.get("model_used", "manual_edit"),
                        processing_time_ms=0,
                    )

                    QMessageBox.information(self, "Success", "Metadata saved successfully!")
                else:
                    QMessageBox.warning(
                        self, "Missing File Path", "Cannot save metadata: file path not found."
                    )
            else:
                QMessageBox.warning(
                    self,
                    "Database Not Available",
                    "Cannot save metadata: database connection not available.",
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
        """Request re-analysis of this file."""
        file_path = self.file_data.get("full_path") or self.file_data.get("filename")
        if file_path:
            self.re_analyze_requested.emit(file_path)
            self.accept()


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

    def __init__(self, parent=None, analysis_db=None):
        super().__init__(parent)

        # Store database reference
        self.analysis_db = analysis_db

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
        companies = sorted({item.get("company") for item in data if item.get("company")})
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
        types = sorted({item.get("document_type") for item in data if item.get("document_type")})
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

        if visible_rows == total_rows:
            self.status_label.setText(f"Showing {total_rows} files")
        else:
            self.status_label.setText(f"Showing {visible_rows} of {total_rows} files")

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

        menu.addSeparator()

        export_action = QAction("Export Selected to CSV", menu)
        export_action.triggered.connect(lambda: self._export_csv(selected_only=True))
        menu.addAction(export_action)

        copy_action = QAction("Copy to Clipboard (TSV)", menu)
        copy_action.triggered.connect(self._copy_to_clipboard)
        menu.addAction(copy_action)

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
            dialog = FileDetailsDialog(row_data, self, analysis_db=self.analysis_db)
            dialog.re_analyze_requested.connect(lambda path: self.re_analyze_requested.emit([path]))
            dialog.exec()

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
            metadata_db = None

            while parent_widget:
                if hasattr(parent_widget, "analysis_db") and hasattr(parent_widget, "metadata_db"):
                    analysis_db = parent_widget.analysis_db
                    metadata_db = parent_widget.metadata_db
                    break
                parent_widget = parent_widget.parent() if hasattr(parent_widget, "parent") else None

            if not analysis_db or not metadata_db:
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

            # Delete from both databases
            deleted_count = 0
            errors = []

            for file_path in file_paths:
                try:
                    # Delete from analysis_db
                    if hasattr(analysis_db, "delete_analysis"):
                        analysis_db.delete_analysis(file_path)
                    else:
                        # Fallback: direct SQL deletion
                        cursor = analysis_db.connection.connection.cursor()
                        cursor.execute(
                            "DELETE FROM analysis_results WHERE file_path = ?", (file_path,)
                        )
                        analysis_db.connection.commit()

                    # Delete from metadata_db
                    if hasattr(metadata_db, "delete_metadata"):
                        metadata_db.delete_metadata(file_path)
                    else:
                        # Fallback: direct SQL deletion
                        cursor = metadata_db.connection.cursor()
                        cursor.execute("DELETE FROM metadata WHERE file_path = ?", (file_path,))
                        metadata_db.connection.commit()

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
