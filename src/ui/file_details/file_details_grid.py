"""
File Analysis Grid Component

Provides a comprehensive grid view of all analyzed files with advanced filtering,
sorting, and data export capabilities.
"""

import json
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ui.file_details.file_details_filter_model import FileDetailsSortFilterProxyModel
from ui.file_details.file_details_grid_actions import _GridActionsMixin
from ui.file_details.file_details_table_model import FileDetailsTableModel
from ui.file_details.file_details_utils import get_file_details_theme_colors


class FileDetailsGrid(_GridActionsMixin, QWidget):
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
    bundle_created = pyqtSignal(int)  # Emits the id of a manually-created/extended bundle

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
        self.theme_colors = get_file_details_theme_colors(self.is_dark_mode)

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

    def _init_ui(self):
        """Initialize the user interface."""
        # Transparent background - parent container handles the background color
        self.setStyleSheet("background-color: transparent;")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Collapsible filter/search toggle button
        self._filter_toggle_btn = QPushButton("▶  Filters & Search")
        self._filter_toggle_btn.setCheckable(True)
        self._filter_toggle_btn.setChecked(False)
        self._filter_toggle_btn.setFixedHeight(26)
        self._filter_toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme_colors["bg_tertiary"]};
                border: 1px solid {self.theme_colors["border"]};
                border-radius: 4px;
                padding: 3px 8px;
                color: {self.theme_colors["text_secondary"]};
                font-size: 9pt;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {self.theme_colors["button_hover"]};
                color: {self.theme_colors["text_primary"]};
            }}
            QPushButton:checked {{
                color: {self.theme_colors["text_primary"]};
            }}
        """)
        layout.addWidget(self._filter_toggle_btn)

        # Collapsible body — starts hidden
        self._filter_body = QWidget()
        self._filter_body.setVisible(False)
        filter_body_layout = QVBoxLayout(self._filter_body)
        filter_body_layout.setContentsMargins(0, 0, 0, 0)
        filter_body_layout.setSpacing(12)

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
            "blank_pages": QPushButton("⬜ Blank Pages"),
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

        # Populate with all ImageStatus enum values
        from db.image_status import ImageStatus

        for status in ImageStatus:
            # Format status name for display (e.g., ANALYZED -> Analyzed)
            display_name = status.name.capitalize()
            self.status_filter.addItem(display_name, status.value)

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

        filter_body_layout.addWidget(filter_frame)

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

        filter_body_layout.addWidget(search_frame)

        layout.addWidget(self._filter_body)
        self._filter_toggle_btn.toggled.connect(self._filter_body.setVisible)
        self._filter_toggle_btn.toggled.connect(
            lambda checked: self._filter_toggle_btn.setText(
                "▼  Filters & Search" if checked else "▶  Filters & Search"
            )
        )

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
        self.config_manager.set_setting("FileGridColumns", "widths", json.dumps(widths))
        self.config_manager.set_setting("FileGridColumns", "visual_order", json.dumps(visual_order))
        self.config_manager.set_setting(
            "FileGridColumns", "visible_columns", json.dumps(visible_columns)
        )

    def _load_column_state(self):
        """Load column widths, order, and visibility from config."""
        if not self.config_manager:
            return

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
