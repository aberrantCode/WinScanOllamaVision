"""
File Analysis Grid Component

Provides a comprehensive grid view of all analyzed files with advanced filtering,
sorting, and data export capabilities.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QPushButton,
    QLineEdit, QComboBox, QLabel, QMenu, QDialog, QTextEdit,
    QDialogButtonBox, QHeaderView, QMessageBox, QApplication
)
from PyQt6.QtCore import (
    Qt, QAbstractTableModel, QSortFilterProxyModel, QModelIndex,
    pyqtSignal, QDateTime
)
from PyQt6.QtGui import QAction, QColor, QFont
from datetime import datetime
from typing import List, Dict, Optional, Any, Set
import csv
import json
import os


class FileDetailsTableModel(QAbstractTableModel):
    """
    Table model for file analysis details.

    Supports 18 columns with configurable visibility.
    """

    # Column definitions
    COLUMNS = [
        ('filename', 'Filename', True),
        ('status', 'Status', True),
        ('confidence', 'Confidence', True),
        ('company', 'Company', True),
        ('document_type', 'Type', True),
        ('document_date', 'Date', True),
        ('page_number', 'Page', True),
        ('total_pages', 'Total', True),
        ('file_size', 'Size', True),
        ('modified_time', 'Modified', True),
        ('analysis_time', 'Analyzed', False),
        ('processing_duration', 'Duration', False),
        ('model_used', 'Model', False),
        ('provider', 'Provider', False),
        ('cache_hit', 'Cached', False),
        ('error_message', 'Error', False),
        ('full_path', 'Full Path', False),
        ('file_hash', 'Hash', False),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[Dict[str, Any]] = []
        self._visible_columns: List[int] = [i for i, (_, _, visible) in enumerate(self.COLUMNS) if visible]

    def set_data(self, data: List[Dict[str, Any]]):
        """Set the data for the model."""
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def set_visible_columns(self, visible_columns: List[int]):
        """Set which columns are visible."""
        self.beginResetModel()
        self._visible_columns = sorted(visible_columns)
        self.endResetModel()

    def get_visible_columns(self) -> List[int]:
        """Get list of visible column indices."""
        return self._visible_columns.copy()

    def get_row_data(self, row: int) -> Optional[Dict[str, Any]]:
        """Get the complete data for a specific row."""
        if 0 <= row < len(self._data):
            return self._data[row].copy()
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        """Return the number of rows."""
        if parent.isValid():
            return 0
        return len(self._data)

    def columnCount(self, parent=QModelIndex()) -> int:
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

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole) -> Any:
        """Return header data."""
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                if section < len(self._visible_columns):
                    actual_col = self._visible_columns[section]
                    _, header, _ = self.COLUMNS[actual_col]
                    return header
            elif role == Qt.ItemDataRole.ToolTipRole:
                if section < len(self._visible_columns):
                    actual_col = self._visible_columns[section]
                    col_key, header, _ = self.COLUMNS[actual_col]
                    return self._get_column_tooltip(col_key, header)

        elif orientation == Qt.Orientation.Vertical:
            if role == Qt.ItemDataRole.DisplayRole:
                return str(section + 1)

        return None

    def _format_display_value(self, col_key: str, value: Any, row_data: Dict) -> str:
        """Format value for display."""
        if value is None or value == '':
            return ''

        if col_key == 'filename':
            return os.path.basename(str(value))
        elif col_key == 'status':
            return str(value).title()
        elif col_key == 'confidence':
            if isinstance(value, (int, float)):
                return f"{value:.1f}%"
            return str(value)
        elif col_key == 'file_size':
            return self._format_file_size(value)
        elif col_key in ('modified_time', 'analysis_time'):
            return self._format_datetime(value)
        elif col_key == 'processing_duration':
            return self._format_duration(value)
        elif col_key == 'cache_hit':
            return 'Yes' if value else 'No'
        elif col_key == 'error_message':
            # Truncate long error messages
            msg = str(value)
            return msg[:50] + '...' if len(msg) > 50 else msg
        elif col_key == 'full_path':
            # Show truncated path
            path = str(value)
            if len(path) > 60:
                return '...' + path[-57:]
            return path
        elif col_key == 'file_hash':
            # Show shortened hash
            hash_str = str(value)
            return hash_str[:8] if len(hash_str) > 8 else hash_str

        return str(value)

    def _format_tooltip(self, col_key: str, value: Any, row_data: Dict) -> str:
        """Format tooltip for a cell."""
        if value is None or value == '':
            return f"{col_key}: (empty)"

        if col_key == 'filename':
            full_path = row_data.get('full_path', value)
            return f"Full path: {full_path}"
        elif col_key == 'error_message':
            return f"Error: {value}"
        elif col_key == 'full_path':
            return str(value)
        elif col_key == 'file_hash':
            return f"Full hash: {value}"
        elif col_key == 'confidence':
            conf = float(value) if isinstance(value, (int, float)) else 0
            if conf >= 80:
                return f"High confidence: {conf:.1f}%"
            elif conf >= 50:
                return f"Medium confidence: {conf:.1f}%"
            else:
                return f"Low confidence: {conf:.1f}%"

        return f"{col_key}: {value}"

    def _get_background_color(self, col_key: str, value: Any, row_data: Dict) -> Optional[QColor]:
        """Get background color for a cell."""
        # Highlight rows with errors
        if row_data.get('error_message'):
            return QColor(255, 240, 240)  # Light red

        # Highlight low confidence
        if col_key == 'confidence':
            if isinstance(value, (int, float)):
                if value < 50:
                    return QColor(255, 245, 230)  # Light orange

        # Highlight cached items
        if col_key == 'cache_hit' and value:
            return QColor(240, 255, 240)  # Light green

        return None

    def _get_foreground_color(self, col_key: str, value: Any, row_data: Dict) -> Optional[QColor]:
        """Get foreground color for a cell."""
        if row_data.get('error_message') and col_key == 'status':
            return QColor(200, 0, 0)  # Red text

        return None

    def _get_alignment(self, col_key: str) -> Qt.AlignmentFlag:
        """Get text alignment for a column."""
        if col_key in ('confidence', 'file_size', 'page_number', 'total_pages', 'processing_duration'):
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

    def _get_column_tooltip(self, col_key: str, header: str) -> str:
        """Get tooltip for column header."""
        tooltips = {
            'filename': 'Name of the scanned file',
            'status': 'Analysis status (Analyzed, Pending, Failed)',
            'confidence': 'Confidence score from LLM analysis (0-100%)',
            'company': 'Extracted company/organization name',
            'document_type': 'Type of document (Invoice, Receipt, etc.)',
            'document_date': 'Date extracted from document',
            'page_number': 'Page number (if detected)',
            'total_pages': 'Total pages in document (if detected)',
            'file_size': 'Size of file on disk',
            'modified_time': 'Last modification time of file',
            'analysis_time': 'When the file was analyzed',
            'processing_duration': 'Time taken to analyze (seconds)',
            'model_used': 'LLM model used for analysis',
            'provider': 'LLM provider (Ollama, Claude, Gemini)',
            'cache_hit': 'Whether result was loaded from cache',
            'error_message': 'Error message (if analysis failed)',
            'full_path': 'Complete file path',
            'file_hash': 'MD5 hash of file content',
        }
        return tooltips.get(col_key, header)

    @staticmethod
    def _format_file_size(size: Any) -> str:
        """Format file size in human-readable format."""
        try:
            size = int(size)
            for unit in ['B', 'KB', 'MB', 'GB']:
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
            return dt.strftime('%Y-%m-%d %H:%M')

        return str(dt)

    @staticmethod
    def _format_duration(duration: Any) -> str:
        """Format duration in seconds."""
        try:
            seconds = float(duration)
            if seconds < 1:
                return f"{seconds*1000:.0f}ms"
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
        self._column_filters: Dict[str, Any] = {}
        self._search_text: str = ''
        self._quick_filter: Optional[str] = None

    def set_filters(self, filters: Dict[str, Any]):
        """Set column-specific filters."""
        self._column_filters = filters.copy()
        self.invalidateFilter()

    def set_search_text(self, text: str):
        """Set full-text search filter."""
        self._search_text = text.lower().strip()
        self.invalidateFilter()

    def set_quick_filter(self, filter_name: Optional[str]):
        """Set quick filter preset."""
        self._quick_filter = filter_name
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Determine if a row should be visible."""
        model = self.sourceModel()
        if not isinstance(model, FileDetailsTableModel):
            return True

        row_data = model.get_row_data(source_row)
        if not row_data:
            return False

        # Apply quick filter
        if self._quick_filter:
            if not self._apply_quick_filter(row_data):
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
        if self._search_text:
            if not self._search_in_row(row_data):
                return False

        return True

    def _apply_quick_filter(self, row_data: Dict[str, Any]) -> bool:
        """Apply quick filter logic."""
        if self._quick_filter == 'high_confidence':
            confidence = row_data.get('confidence', 0)
            try:
                return float(confidence) >= 80
            except (ValueError, TypeError):
                return False

        elif self._quick_filter == 'needs_review':
            confidence = row_data.get('confidence', 100)
            try:
                return float(confidence) < 80
            except (ValueError, TypeError):
                return True

        elif self._quick_filter == 'multi_page':
            total_pages = row_data.get('total_pages')
            try:
                return int(total_pages) > 1
            except (ValueError, TypeError):
                return False

        elif self._quick_filter == 'recent':
            analysis_time = row_data.get('analysis_time')
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

        elif self._quick_filter == 'has_errors':
            return bool(row_data.get('error_message'))

        elif self._quick_filter == 'cached_only':
            return bool(row_data.get('cache_hit'))

        return True

    def _search_in_row(self, row_data: Dict[str, Any]) -> bool:
        """Check if search text appears in any column."""
        search_text = self._search_text

        # Search in all string-like fields
        searchable_fields = [
            'filename', 'company', 'document_type', 'document_date',
            'status', 'error_message', 'model_used', 'provider', 'full_path'
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

    def __init__(self, file_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.file_data = file_data
        self.setWindowTitle(f"File Details - {os.path.basename(file_data.get('filename', 'Unknown'))}")
        self.setMinimumSize(700, 600)
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Create tabbed text display
        from PyQt6.QtWidgets import QTabWidget, QTextBrowser
        tab_widget = QTabWidget()

        # Summary tab
        summary_text = self._format_summary()
        summary_browser = QTextBrowser()
        summary_browser.setHtml(summary_text)
        summary_browser.setOpenExternalLinks(False)
        tab_widget.addTab(summary_browser, "Summary")

        # Metadata tab
        metadata_text = self._format_metadata()
        metadata_browser = QTextBrowser()
        metadata_browser.setHtml(metadata_text)
        tab_widget.addTab(metadata_browser, "Metadata")

        # Raw Response tab
        raw_response = self.file_data.get('raw_response', 'No raw response available')
        raw_text = QTextEdit()
        raw_text.setPlainText(str(raw_response))
        raw_text.setReadOnly(True)
        raw_text.setFont(QFont('Consolas', 9))
        tab_widget.addTab(raw_text, "Raw Response")

        # Full Data tab (JSON)
        json_text = QTextEdit()
        json_text.setPlainText(json.dumps(self.file_data, indent=2, default=str))
        json_text.setReadOnly(True)
        json_text.setFont(QFont('Consolas', 9))
        tab_widget.addTab(json_text, "Full Data (JSON)")

        layout.addWidget(tab_widget)

        # Button box
        button_box = QDialogButtonBox()

        copy_json_btn = QPushButton("Copy JSON")
        copy_json_btn.clicked.connect(self._copy_json)
        button_box.addButton(copy_json_btn, QDialogButtonBox.ButtonRole.ActionRole)

        re_analyze_btn = QPushButton("Re-analyze")
        re_analyze_btn.clicked.connect(self._re_analyze)
        button_box.addButton(re_analyze_btn, QDialogButtonBox.ButtonRole.ActionRole)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_box.addButton(close_btn, QDialogButtonBox.ButtonRole.RejectRole)

        layout.addWidget(button_box)

    def _format_summary(self) -> str:
        """Format summary information as HTML."""
        html = "<html><body style='font-family: Segoe UI; font-size: 10pt;'>"

        # File Information
        html += "<h3 style='color: #2563eb;'>File Information</h3>"
        html += "<table cellpadding='5'>"
        html += f"<tr><td><b>Filename:</b></td><td>{self.file_data.get('filename', 'N/A')}</td></tr>"
        html += f"<tr><td><b>Full Path:</b></td><td>{self.file_data.get('full_path', 'N/A')}</td></tr>"
        html += f"<tr><td><b>File Size:</b></td><td>{self._format_size(self.file_data.get('file_size'))}</td></tr>"
        html += f"<tr><td><b>Modified:</b></td><td>{self._format_dt(self.file_data.get('modified_time'))}</td></tr>"
        html += f"<tr><td><b>File Hash:</b></td><td>{self.file_data.get('file_hash', 'N/A')}</td></tr>"
        html += "</table>"

        # Analysis Information
        html += "<h3 style='color: #2563eb;'>Analysis Information</h3>"
        html += "<table cellpadding='5'>"
        html += f"<tr><td><b>Status:</b></td><td>{self.file_data.get('status', 'N/A')}</td></tr>"
        html += f"<tr><td><b>Analyzed:</b></td><td>{self._format_dt(self.file_data.get('analysis_time'))}</td></tr>"
        html += f"<tr><td><b>Processing Time:</b></td><td>{self._format_duration(self.file_data.get('processing_duration'))}</td></tr>"
        html += f"<tr><td><b>Provider:</b></td><td>{self.file_data.get('provider', 'N/A')}</td></tr>"
        html += f"<tr><td><b>Model:</b></td><td>{self.file_data.get('model_used', 'N/A')}</td></tr>"
        html += f"<tr><td><b>Cached:</b></td><td>{'Yes' if self.file_data.get('cache_hit') else 'No'}</td></tr>"

        if self.file_data.get('error_message'):
            html += f"<tr><td><b>Error:</b></td><td style='color: red;'>{self.file_data.get('error_message')}</td></tr>"

        html += "</table>"

        html += "</body></html>"
        return html

    def _format_metadata(self) -> str:
        """Format metadata information as HTML."""
        html = "<html><body style='font-family: Segoe UI; font-size: 10pt;'>"

        html += "<h3 style='color: #2563eb;'>Extracted Metadata</h3>"
        html += "<table cellpadding='5'>"

        confidence = self.file_data.get('confidence', 0)
        try:
            conf_float = float(confidence)
            conf_color = '#16a34a' if conf_float >= 80 else '#ea580c' if conf_float >= 50 else '#dc2626'
            html += f"<tr><td><b>Confidence:</b></td><td style='color: {conf_color}; font-weight: bold;'>{conf_float:.1f}%</td></tr>"
        except (ValueError, TypeError):
            html += f"<tr><td><b>Confidence:</b></td><td>{confidence}</td></tr>"

        html += f"<tr><td><b>Company:</b></td><td>{self.file_data.get('company', 'N/A')}</td></tr>"
        html += f"<tr><td><b>Document Type:</b></td><td>{self.file_data.get('document_type', 'N/A')}</td></tr>"
        html += f"<tr><td><b>Document Date:</b></td><td>{self.file_data.get('document_date', 'N/A')}</td></tr>"

        page_num = self.file_data.get('page_number')
        total_pages = self.file_data.get('total_pages')
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
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        except (ValueError, TypeError):
            return str(size) if size else 'N/A'

    def _format_dt(self, dt: Any) -> str:
        """Format datetime."""
        if not dt:
            return 'N/A'
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt)
            except (ValueError, TypeError):
                return str(dt)
        if isinstance(dt, datetime):
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        return str(dt)

    def _format_duration(self, duration: Any) -> str:
        """Format duration."""
        if not duration:
            return 'N/A'
        try:
            seconds = float(duration)
            if seconds < 1:
                return f"{seconds*1000:.0f}ms"
            elif seconds < 60:
                return f"{seconds:.1f}s"
            else:
                minutes = int(seconds // 60)
                secs = int(seconds % 60)
                return f"{minutes}m {secs}s"
        except (ValueError, TypeError):
            return str(duration)

    def _copy_json(self):
        """Copy JSON data to clipboard."""
        json_str = json.dumps(self.file_data, indent=2, default=str)
        QApplication.clipboard().setText(json_str)
        QMessageBox.information(self, "Copied", "JSON data copied to clipboard")

    def _re_analyze(self):
        """Request re-analysis of this file."""
        file_path = self.file_data.get('full_path') or self.file_data.get('filename')
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = FileDetailsTableModel()
        self.proxy_model = FileDetailsSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Filter toolbar
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(5, 5, 5, 5)

        # Quick filter buttons
        quick_filter_label = QLabel("Quick Filters:")
        filter_layout.addWidget(quick_filter_label)

        self.quick_filters = {
            'high_confidence': QPushButton("High Confidence"),
            'needs_review': QPushButton("Needs Review"),
            'multi_page': QPushButton("Multi-Page"),
            'recent': QPushButton("Recent (24h)"),
            'has_errors': QPushButton("Has Errors"),
            'cached_only': QPushButton("Cached Only"),
        }

        for name, btn in self.quick_filters.items():
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, n=name: self._apply_quick_filter(n if checked else None))
            filter_layout.addWidget(btn)

        filter_layout.addStretch()

        # Dropdown filters
        self.status_filter = QComboBox()
        self.status_filter.addItem("All Status", None)
        self.status_filter.addItem("Analyzed", "analyzed")
        self.status_filter.addItem("Pending", "pending")
        self.status_filter.addItem("Failed", "failed")
        self.status_filter.currentIndexChanged.connect(self._apply_column_filters)
        filter_layout.addWidget(QLabel("Status:"))
        filter_layout.addWidget(self.status_filter)

        self.company_filter = QComboBox()
        self.company_filter.addItem("All Companies", None)
        self.company_filter.currentIndexChanged.connect(self._apply_column_filters)
        filter_layout.addWidget(QLabel("Company:"))
        filter_layout.addWidget(self.company_filter)

        self.type_filter = QComboBox()
        self.type_filter.addItem("All Types", None)
        self.type_filter.currentIndexChanged.connect(self._apply_column_filters)
        filter_layout.addWidget(QLabel("Type:"))
        filter_layout.addWidget(self.type_filter)

        layout.addLayout(filter_layout)

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(5, 0, 5, 5)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search all columns...")
        self.search_input.textChanged.connect(self._apply_search)
        search_layout.addWidget(QLabel("Search:"))
        search_layout.addWidget(self.search_input)

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_all_filters)
        search_layout.addWidget(clear_btn)

        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(self._export_csv)
        search_layout.addWidget(export_btn)

        layout.addLayout(search_layout)

        # Table view
        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)
        self.table_view.doubleClicked.connect(self._show_details_dialog)

        # Configure header
        header = self.table_view.horizontalHeader()
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_column_menu)
        header.setSectionsMovable(True)
        header.setStretchLastSection(True)

        # Set initial column widths
        for i in range(self.model.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)

        layout.addWidget(self.table_view)

        # Status bar
        self.status_label = QLabel("No files loaded")
        layout.addWidget(self.status_label)

    def refresh_data(self, data: List[Dict[str, Any]]):
        """Refresh the grid with new data."""
        self.model.set_data(data)
        self._update_filter_dropdowns(data)
        self._update_status_label()

        # Auto-resize columns on first load
        if data:
            self.table_view.resizeColumnsToContents()

    def apply_quick_filter(self, filter_name: str):
        """Apply a quick filter preset (for cross-tab navigation)."""
        # Uncheck all other quick filter buttons
        for name, btn in self.quick_filters.items():
            btn.setChecked(name == filter_name)

        self._apply_quick_filter(filter_name)

    def _apply_quick_filter(self, filter_name: Optional[str]):
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
            filters['status'] = status

        company = self.company_filter.currentData()
        if company:
            filters['company'] = company

        doc_type = self.type_filter.currentData()
        if doc_type:
            filters['document_type'] = doc_type

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
        self.proxy_model.set_filters({})

        # Clear search
        self.search_input.clear()
        self.proxy_model.set_search_text('')

        self._update_status_label()

    def _update_filter_dropdowns(self, data: List[Dict[str, Any]]):
        """Update filter dropdown options based on data."""
        # Update company filter
        companies = sorted(set(item.get('company') for item in data if item.get('company')))
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
        types = sorted(set(item.get('document_type') for item in data if item.get('document_type')))
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

        for i, (col_key, col_name, default_visible) in enumerate(FileDetailsTableModel.COLUMNS):
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

    def _show_context_menu(self, pos):
        """Show context menu for row actions."""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            return

        menu = QMenu(self)

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

    def _show_details_dialog(self, index: QModelIndex):
        """Show details dialog for double-clicked row."""
        source_index = self.proxy_model.mapToSource(index)
        row_data = self.model.get_row_data(source_index.row())

        if row_data:
            dialog = FileDetailsDialog(row_data, self)
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
                file_path = row_data.get('full_path') or row_data.get('filename')
                if file_path:
                    file_paths.append(file_path)

        if file_paths:
            reply = QMessageBox.question(
                self,
                "Re-analyze Files",
                f"Re-analyze {len(file_paths)} selected file(s)?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.re_analyze_requested.emit(file_paths)

    def _export_csv(self, selected_only: bool = False):
        """Export data to CSV file."""
        from PyQt6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export to CSV",
            "file_analysis.csv",
            "CSV Files (*.csv);;All Files (*.*)"
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
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
                    indices = [self.proxy_model.index(row, 0) for row in range(self.proxy_model.rowCount())]

                for index in indices:
                    source_index = self.proxy_model.mapToSource(index)
                    row_data = self.model.get_row_data(source_index.row())

                    if row_data:
                        row = []
                        for col_idx in self.model.get_visible_columns():
                            col_key, _, _ = FileDetailsTableModel.COLUMNS[col_idx]
                            value = row_data.get(col_key, '')
                            row.append(str(value) if value is not None else '')
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
        lines.append('\t'.join(headers))

        # Data rows
        for index in selection:
            source_index = self.proxy_model.mapToSource(index)
            row_data = self.model.get_row_data(source_index.row())

            if row_data:
                row = []
                for col_idx in self.model.get_visible_columns():
                    col_key, _, _ = FileDetailsTableModel.COLUMNS[col_idx]
                    value = row_data.get(col_key, '')
                    row.append(str(value) if value is not None else '')
                lines.append('\t'.join(row))

        tsv_string = '\n'.join(lines)
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
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # TODO: Implement database deletion
            # This would require access to AnalysisDB
            QMessageBox.information(
                self,
                "Not Implemented",
                "Database deletion not yet implemented.\n\nPlease use the Analysis Status window to manage records."
            )
