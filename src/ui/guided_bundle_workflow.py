"""
Guided Bundle Review Workflow - Modern UI for reviewing AI bundle suggestions

Features:
- Wizard-style workflow through all bundle suggestions
- Three-panel layout: thumbnails (reorderable) | large preview | metadata
- Immediate PDF conversion on accept
- Previous/Next bundle navigation
- Progress tracking
- Drag-and-drop page reordering with up/down buttons
"""

from pathlib import Path

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QPainter,
    QPixmap,
    QTransform,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.bundle.bundle_colors import get_bundle_colors
from ui.bundle.bundle_colors import hex_to_rgb as _hex_to_rgb_fn
from ui.bundle.bundle_pdf_converter import BundlePdfConverter
from ui.bundle.bundle_stylesheet import build_bundle_stylesheet
from ui.bundle.bundle_thumbnail_panel import BundleThumbnailPanel
from ui.styles import (
    Colors,
)


class GuidedBundleWorkflow(QDialog):
    """
    Guided workflow for reviewing bundle suggestions and converting to PDF.

    Features:
    - Step through bundles with Previous/Next
    - Edit metadata, rotate, reorder pages
    - Accept → Immediate PDF conversion
    - Reject → Move to next
    - Skip → Mark for later review
    """

    workflow_completed = pyqtSignal(dict)  # stats
    bundle_accepted = pyqtSignal(dict)  # bundle data
    bundle_rejected = pyqtSignal(dict)  # bundle data

    def __init__(
        self,
        bundles=None,
        start_index=0,
        prototype_mode=True,
        analysis_db=None,
        metadata_db=None,
        config_manager=None,
        parent=None,
        embedded_mode=False,
    ):
        super().__init__(parent)

        # Services
        self.analysis_db = analysis_db
        self.metadata_db = metadata_db
        self.config_manager = config_manager
        self._pdf_converter: BundlePdfConverter = BundlePdfConverter(config_manager, analysis_db)

        # Embedded mode: run as child widget inside another layout (no dialog chrome/close)
        self.embedded_mode = embedded_mode

        # State
        self.prototype_mode = prototype_mode
        self.bundles = bundles or self._create_mock_bundles()
        self.current_bundle_index = start_index
        self.current_page_index = 0

        # Workflow tracking
        self.accepted_bundles = []
        self.rejected_bundles = []
        self.skipped_bundles = []

        # Current bundle state
        self.zoom_level = 100
        self.rotation_angle = 0
        self.pan_offset = QPoint(0, 0)
        self.is_panning = False
        self.pan_start_pos = QPoint(0, 0)
        self.original_pixmap = None  # Store original pixmap for fit calculations

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

        # Metadata inputs
        self.metadata_inputs = {}

        # Page reordering tracking
        self.page_order = []  # Will be initialized when loading bundle

        # Track first show
        self._first_show = True

        # Accordion sections
        self.accordion_sections = []

        # Theme state - read from config (same key as settings window)
        if config_manager:
            theme = config_manager.get_setting("Theme", "theme", "light")
            self.dark_mode = theme == "dark"
        else:
            self.dark_mode = False

        # Edit mode tracking
        self.edit_mode = False
        self.original_metadata = {}

        # Output filename tracking
        self.output_filename_manually_edited = False

        self._init_ui()

        self._load_current_bundle()

        # Apply initial theme based on dark_mode setting (after UI is fully built)
        if self.dark_mode:
            self._apply_dark_theme()
        else:
            self._apply_light_theme()

        # Force update of all component styles to ensure theme is fully applied
        self._update_all_component_styles()

    def _init_ui(self):
        """Initialize the guided workflow UI."""
        self.setWindowTitle("Verify Documents")
        if self.embedded_mode:
            # Don't constrain size — let the parent layout decide
            self.setMinimumSize(600, 400)
        else:
            self.setMinimumSize(1400, 900)
            self.resize(1400, 900)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header with progress
        header = self._create_header()
        main_layout.addWidget(header)

        # Three-panel layout (static widths, no splitter)
        content_container = QWidget()
        content_layout = QHBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Left panel - Thumbnails with reordering (fixed width)
        self.thumbnail_panel = BundleThumbnailPanel(dark_mode=self.dark_mode, parent=self)
        self.thumbnail_panel.setFixedWidth(150)
        self.thumbnail_panel.page_selected.connect(self._on_thumbnail_clicked)
        self.thumbnail_panel.page_reorder_requested.connect(self._on_drop_requested)
        self.thumbnail_panel.page_move_up_requested.connect(self._move_page_up)
        self.thumbnail_panel.page_move_down_requested.connect(self._move_page_down)
        self.thumbnail_panel.page_remove_requested.connect(self._on_remove_page)
        self.thumbnail_panel.reanalyze_requested.connect(self._on_reanalyze_page)
        self.thumbnail_panel.add_page_requested.connect(self._on_add_page)
        content_layout.addWidget(self.thumbnail_panel)

        # Center panel - Large preview (takes remaining space)
        preview_panel = self._create_preview_panel()
        content_layout.addWidget(preview_panel, stretch=1)

        # Right panel - Metadata (fixed width)
        self.metadata_panel = self._create_metadata_panel()
        self.metadata_panel.setFixedWidth(380)
        content_layout.addWidget(self.metadata_panel)

        main_layout.addWidget(content_container)

        # Bottom action bar
        self.action_bar = self._create_action_bar()
        main_layout.addWidget(self.action_bar)

    def _create_header(self) -> QWidget:
        """Create header with progress and navigation."""
        theme = self._get_theme_colors()

        self.header_widget = QWidget()
        self.header_widget.setStyleSheet(f"background: {theme['bg_secondary']};")
        self.header_widget.setFixedHeight(70)  # Reduced from 80
        header = self.header_widget

        layout = QVBoxLayout(header)
        layout.setContentsMargins(20, 8, 20, 8)  # Reduced top/bottom from 12 to 8
        layout.setSpacing(6)  # Reduced from 8 to 6

        # Top row - Title and stats
        top_row = QHBoxLayout()

        self.title_label = QLabel("📋 Verify Documents")
        self.title_label.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {theme['text_primary']}; "
            f"text-decoration: none; background: transparent;"
        )
        top_row.addWidget(self.title_label)

        top_row.addStretch()

        # Stats
        stats_text = f"✓ {len(self.accepted_bundles)} Accepted  •  ✗ {len(self.rejected_bundles)} Rejected  •  ⏭ {len(self.skipped_bundles)} Skipped"
        self.stats_label = QLabel(stats_text)
        self.stats_label.setStyleSheet(f"color: {theme['text_secondary']}; font-size: 13px;")
        top_row.addWidget(self.stats_label)

        layout.addLayout(top_row)

        # Bottom row - Progress and current bundle info
        bottom_row = QHBoxLayout()

        # Progress bar
        progress_container = QWidget()
        progress_container.setStyleSheet("background: transparent; border: none;")
        progress_layout = QHBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(12)

        self.progress_label = QLabel(
            f"Bundle {self.current_bundle_index + 1} of {len(self.bundles)}"
        )
        self.progress_label.setStyleSheet(
            f"color: {theme['text_primary']}; font-weight: 600; font-size: 13px; "
            f"text-decoration: none; background: transparent; border: none;"
        )
        progress_layout.addWidget(self.progress_label)
        bottom_row.addWidget(progress_container)
        bottom_row.addStretch()

        # Current bundle info
        bundle = self.bundles[self.current_bundle_index]
        doc_type = bundle.get("document_type", "Unknown").title()  # Title case
        company = bundle.get("company", "Unknown").title()  # Title case
        pages = len(bundle.get("file_paths", []))

        info_text = f"<b>{doc_type}</b> - {company} ({pages} pages)"
        self.bundle_info_label = QLabel(info_text)
        self.bundle_info_label.setStyleSheet(
            f"color: {theme['text_primary']}; font-size: 13px; background: transparent;"
        )
        bottom_row.addWidget(self.bundle_info_label)

        # Confidence badge
        confidence = bundle.get("confidence_score", 0.0)
        confidence_pct = int(confidence * 100)

        if confidence >= 0.8:
            badge_color = theme["success"]
        elif confidence >= 0.5:
            badge_color = theme["warning"]
        else:
            badge_color = theme["danger"]

        self.confidence_badge = QLabel(f"{confidence_pct}%")
        self.confidence_badge.setStyleSheet(
            f"""
            background: {badge_color};
            color: white;
            padding: 4px 10px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 12px;
        """
        )
        bottom_row.addWidget(self.confidence_badge)

        layout.addLayout(bottom_row)

        return header

    def _create_preview_panel(self) -> QWidget:
        """Create center panel with large image preview."""
        theme = self._get_theme_colors()

        panel = QWidget()
        panel.setStyleSheet(f"background: {theme['preview_bg']};")
        self.preview_container = panel  # Store reference for theme updates

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(0)

        # Preview area
        preview_area = QWidget()
        preview_area.setMinimumSize(600, 500)
        preview_area.setStyleSheet(f"background: {theme['preview_bg']};")
        preview_layout = QVBoxLayout(preview_area)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(8)

        # Page label - centered above image
        page_label = QLabel(f"Page {self.current_page_index + 1}")
        page_label.setStyleSheet(
            f"color: {theme['text_secondary']}; font-size: 13px; font-weight: 500;"
        )
        page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(page_label)
        self.page_label = page_label

        self.large_preview = QLabel()
        self.large_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.large_preview.setStyleSheet(f"background: {theme['preview_bg']};")
        preview_layout.addWidget(self.large_preview)

        layout.addWidget(preview_area)

        return panel

    def _create_overlay_controls(self) -> QWidget:
        """Create zoom/rotate overlay controls."""
        theme = self._get_theme_colors()

        controls = QWidget()
        # Semi-transparent background using theme colors
        bg_r, bg_g, bg_b = self._hex_to_rgb(theme["bg_secondary"])
        controls.setStyleSheet(f"""
            QWidget {{
                background: rgba({bg_r}, {bg_g}, {bg_b}, 0.95);
                border: 1px solid {theme["border"]};
                border-radius: 6px;
                padding: 4px;
            }}
        """)

        layout = QHBoxLayout(controls)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.setSizeConstraint(QHBoxLayout.SizeConstraint.SetFixedSize)

        btn_style = f"""
            QPushButton {{
                background: {theme["button_bg"]};
                color: {theme["button_text"]};
                border: 1px solid {theme["border"]};
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                min-width: 36px;
                max-width: 36px;
                min-height: 28px;
                max-height: 28px;
            }}
            QPushButton:hover {{
                background: {theme["button_hover"]};
                border-color: {theme["border"]};
                color: {theme["text_primary"]};
            }}
            QPushButton:pressed {{
                background: {theme["selected"]};
            }}
        """

        # Zoom controls
        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setStyleSheet(btn_style)
        zoom_out_btn.setToolTip("Zoom Out")
        zoom_out_btn.clicked.connect(self._on_zoom_out)
        layout.addWidget(zoom_out_btn)

        self.zoom_spinner = QSpinBox()
        self.zoom_spinner.setRange(25, 400)
        self.zoom_spinner.setValue(100)
        self.zoom_spinner.setSuffix("%")
        self.zoom_spinner.setFixedWidth(65)
        self.zoom_spinner.setFixedHeight(28)
        self.zoom_spinner.setStyleSheet(f"""
            QSpinBox {{
                background: {theme["button_bg"]};
                color: {theme["text_primary"]};
                border: 1px solid {theme["border"]};
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
                font-weight: 600;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background: {theme["button_hover"]};
                border: none;
                width: 14px;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background: {theme["selected"]};
            }}
        """)
        self.zoom_spinner.valueChanged.connect(self._on_zoom_changed)
        layout.addWidget(self.zoom_spinner)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setStyleSheet(btn_style)
        zoom_in_btn.setToolTip("Zoom In")
        zoom_in_btn.clicked.connect(self._on_zoom_in)
        layout.addWidget(zoom_in_btn)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"background: {theme['border']};")
        sep.setFixedWidth(1)
        sep.setFixedHeight(28)
        layout.addWidget(sep)

        # Fit buttons
        fit_width_btn = QPushButton("⬌")
        fit_width_btn.setStyleSheet(btn_style)
        fit_width_btn.setToolTip("Fit to Width")
        fit_width_btn.clicked.connect(self._on_fit_width)
        layout.addWidget(fit_width_btn)

        fit_height_btn = QPushButton("⬍")
        fit_height_btn.setStyleSheet(btn_style)
        fit_height_btn.setToolTip("Fit to Height")
        fit_height_btn.clicked.connect(self._on_fit_height)
        layout.addWidget(fit_height_btn)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet(f"background: {theme['border']};")
        sep2.setFixedWidth(1)
        sep2.setFixedHeight(28)
        layout.addWidget(sep2)

        # Rotation controls
        rotate_ccw_btn = QPushButton("↺")
        rotate_ccw_btn.setStyleSheet(btn_style)
        rotate_ccw_btn.setToolTip("Rotate Counter-Clockwise")
        rotate_ccw_btn.clicked.connect(self._on_rotate_ccw)
        layout.addWidget(rotate_ccw_btn)

        rotate_cw_btn = QPushButton("↻")
        rotate_cw_btn.setStyleSheet(btn_style)
        rotate_cw_btn.setToolTip("Rotate Clockwise")
        rotate_cw_btn.clicked.connect(self._on_rotate_cw)
        layout.addWidget(rotate_cw_btn)

        return controls

    def _create_metadata_panel(self) -> QWidget:
        """Create right panel with editable metadata in accordion sections."""
        theme = self._get_theme_colors()

        panel = QWidget()
        panel.setStyleSheet(f"background: {theme['metadata_bg']};")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {theme['metadata_bg']}; }}")

        container = QWidget()
        container.setStyleSheet(f"background: {theme['metadata_bg']};")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Store accordion sections
        self.accordion_sections = []

        # Extracted Metadata Section (expanded by default)
        metadata_section = self._create_accordion_section(
            "📋 Extracted Metadata", self._create_metadata_form(), initially_expanded=True
        )
        container_layout.addWidget(metadata_section)

        # File Information Section
        file_info_section = self._create_accordion_section(
            "📄 File Information", self._create_file_info_form(), initially_expanded=False
        )
        container_layout.addWidget(file_info_section)

        # Analysis Information Section
        analysis_section = self._create_accordion_section(
            "⚙️ Analysis Information", self._create_analysis_info_form(), initially_expanded=False
        )
        container_layout.addWidget(analysis_section)

        # Don't add stretch - let expanded accordion fill space
        scroll.setWidget(container)
        layout.addWidget(scroll)  # Takes all available space

        # Output filename section at bottom (fixed height)
        output_section = self._create_output_filename_section()
        layout.addWidget(output_section)

        return panel

    def _create_output_filename_section(self) -> QWidget:
        """Create output filename section with auto-updating field."""
        theme = self._get_theme_colors()

        # Use a highlighted background color to make it stand out
        highlight_bg = theme["info"] if self.dark_mode else "#e0f2fe"

        section = QWidget()
        section.setStyleSheet(f"background: {highlight_bg}; border-radius: 6px;")
        section.setMinimumHeight(90)
        section.setMaximumHeight(90)

        layout = QVBoxLayout(section)
        layout.setContentsMargins(10, 8, 10, 6)
        layout.setSpacing(6)

        # Label with icon and larger font - MUST be visible
        label = QLabel("📄 Output File Name")
        label_color = "white" if self.dark_mode else "#0c4a6e"
        label.setStyleSheet(
            f"color: {label_color}; font-weight: 700; font-size: 13px; background: transparent;"
        )
        label.setMinimumHeight(24)
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(label)

        # Textbox for filename (larger, more prominent)
        self.output_filename_input = QLineEdit()
        self.output_filename_input.setPlaceholderText("Company - Invoice - 2024-01-15")
        self.output_filename_input.setToolTip(
            "Output PDF filename (without extension).\n\n"
            "Extension will be automatically set to .PDF when saving.\n"
            "Any extension you type will be removed and replaced with .PDF"
        )

        input_bg = "#ffffff" if self.dark_mode else "#ffffff"
        input_text = "#111827" if self.dark_mode else "#111827"
        input_border = "#60a5fa" if self.dark_mode else "#3b82f6"

        self.output_filename_input.setStyleSheet(f"""
            QLineEdit {{
                background: {input_bg};
                color: {input_text};
                border: 2px solid {input_border};
                border-radius: 6px;
                padding: 10px 12px;
                font-size: 14px;
                font-weight: 600;
            }}
            QLineEdit:focus {{
                border: 2px solid {theme["selected"]};
                background: {input_bg};
            }}
        """)

        # Track manual edits
        self.output_filename_input.textChanged.connect(self._on_output_filename_manual_edit)

        layout.addWidget(self.output_filename_input)

        return section

    def _create_metadata_form(self) -> QWidget:
        """Create editable metadata form with all fields."""
        from services.logging_service import get_logger

        logger = get_logger()

        theme = self._get_theme_colors()

        form = QWidget()
        form.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(form)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        bundle = self.bundles[self.current_bundle_index]

        # Get current page analysis - use page_order to map visual index to actual index
        actual_index = (
            self.page_order[self.current_page_index]
            if self.current_page_index < len(self.page_order)
            else self.current_page_index
        )
        logger.info(
            f"[CREATE METADATA FORM] current_page_index={self.current_page_index}, actual_index={actual_index}"
        )

        if actual_index < len(bundle.get("analyses", [])):
            analysis = bundle["analyses"][actual_index]
            logger.info(
                f"[CREATE METADATA FORM] Found analysis: document_type={analysis.get('document_type')}, company={analysis.get('company')}"
            )
        else:
            analysis = {}
            logger.info(f"[CREATE METADATA FORM] No analysis found for actual_index {actual_index}")

        def add_field(label, field_name, value, widget_type="text", options=None, placeholder=""):
            field_container = QWidget()
            field_container.setStyleSheet("background: transparent;")
            field_layout = QVBoxLayout(field_container)
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(6)

            lbl = QLabel(label)
            # Use explicit white in dark mode, dark in light mode
            label_color = "#f1f5f9" if self.dark_mode else "#111827"
            lbl.setStyleSheet(
                f"color: {label_color}; font-weight: 600; font-size: 12px; background: transparent;"
            )
            field_layout.addWidget(lbl)

            if widget_type == "dropdown":
                widget = QComboBox()
                widget.setEditable(True)
                if options:
                    widget.addItems(options)
                if value:
                    widget.setCurrentText(str(value))
                # Create custom down arrow indicator using unicode character
                arrow_color = theme["text_primary"]
                widget.setStyleSheet(f"""
                    QComboBox {{
                        background: {theme["bg_input"]};
                        color: {theme["text_primary"]};
                        border: 1px solid {theme["border"]};
                        border-radius: 4px;
                        padding: 8px;
                        padding-right: 30px;
                        font-size: 13px;
                    }}
                    QComboBox:focus {{
                        border: 1px solid {theme["border_focus"]};
                    }}
                    QComboBox::drop-down {{
                        subcontrol-origin: padding;
                        subcontrol-position: center right;
                        width: 25px;
                        border: none;
                        background: transparent;
                    }}
                    QComboBox::down-arrow {{
                        image: none;
                        border: none;
                        width: 12px;
                        height: 12px;
                        margin-right: 5px;
                    }}
                    QComboBox QAbstractItemView {{
                        background: {theme["bg_input"]};
                        color: {theme["text_primary"]};
                        selection-background-color: {theme["selected"]};
                        border: 1px solid {theme["border"]};
                    }}
                """)

                # Add unicode down arrow as a visual indicator
                # Create a custom paint event to draw the arrow
                from PyQt6.QtCore import QPoint
                from PyQt6.QtGui import QColor, QPainter, QPen, QPolygon

                original_paint = widget.paintEvent

                def custom_paint(event):
                    original_paint(event)
                    painter = QPainter(widget)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                    # Draw down arrow triangle on the right side
                    arrow_x = widget.width() - 18
                    arrow_y = widget.height() // 2

                    # Create triangle points
                    points = [
                        QPoint(arrow_x - 4, arrow_y - 2),  # Top left
                        QPoint(arrow_x + 4, arrow_y - 2),  # Top right
                        QPoint(arrow_x, arrow_y + 3),  # Bottom center
                    ]

                    polygon = QPolygon(points)
                    painter.setPen(QPen(QColor(arrow_color), 1))
                    painter.setBrush(QColor(arrow_color))
                    painter.drawPolygon(polygon)
                    painter.end()

                widget.paintEvent = custom_paint
            elif widget_type == "checkbox":
                widget = QCheckBox()
                widget.setChecked(bool(value))
                widget.setStyleSheet(f"""
                    QCheckBox {{
                        color: {theme["text_primary"]};
                        font-size: 13px;
                    }}
                    QCheckBox::indicator {{
                        width: 18px;
                        height: 18px;
                        border: 2px solid {theme["border"]};
                        border-radius: 3px;
                    }}
                    QCheckBox::indicator:checked {{
                        background: {theme["selected"]};
                        border-color: {theme["selected"]};
                    }}
                """)
            else:
                widget = QLineEdit()
                widget.setText(str(value) if value else "")
                if placeholder:
                    widget.setPlaceholderText(placeholder)
                widget.setStyleSheet(f"""
                    QLineEdit {{
                        background: {theme["bg_input"]};
                        color: {theme["text_primary"]};
                        border: 1px solid {theme["border"]};
                        border-radius: 4px;
                        padding: 8px;
                        font-size: 13px;
                    }}
                    QLineEdit:focus {{
                        border: 1px solid {theme["border_focus"]};
                    }}
                """)

            field_layout.addWidget(widget)
            layout.addWidget(field_container)
            self.metadata_inputs[field_name] = widget

            # Connect field changes to update output filename
            # Only for key fields used in filename generation
            if field_name in ["company", "document_type", "document_date"]:
                if widget_type == "dropdown":
                    widget.currentTextChanged.connect(self._update_output_filename)
                elif widget_type == "text":
                    widget.textChanged.connect(self._update_output_filename)

        # Add all fields (matching bundle_review_window_v2.py)
        add_field(
            "Document Type",
            "document_type",
            bundle.get("document_type"),
            "dropdown",
            ["Invoice", "Receipt", "Statement", "Contract", "Purchase Order"],
            "e.g., invoice, receipt, contract",
        )

        add_field(
            "Company",
            "company",
            bundle.get("company"),
            "dropdown",
            ["Acme Corporation", "TechCorp", "Global Shipping", "ABC Manufacturing"],
            "Company or organization name",
        )

        add_field(
            "Document Date",
            "document_date",
            bundle.get("document_date"),
            "text",
            None,
            "YYYY-MM-DD format",
        )

        add_field(
            "Page Number",
            "page_number",
            analysis.get("page_number", ""),
            "text",
            None,
            "Current page number",
        )

        add_field(
            "Total Pages",
            "total_pages",
            analysis.get("total_pages", ""),
            "text",
            None,
            "Total number of pages",
        )

        add_field(
            "Rotation Needed",
            "rotation_needed",
            analysis.get("rotation_needed", "none"),
            "dropdown",
            ["none", "90_cw", "90_ccw", "180"],
        )

        add_field("Tax Related", "tax_related", analysis.get("tax_related", False), "checkbox")

        # Add Save/Cancel buttons (initially hidden)
        layout.addSpacing(15)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.metadata_save_btn = QPushButton("💾 Save Changes")
        self.metadata_save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.SUCCESS};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #059669;
            }}
        """)
        self.metadata_save_btn.clicked.connect(self._on_save_metadata_changes)
        self.metadata_save_btn.setVisible(False)
        button_layout.addWidget(self.metadata_save_btn)

        self.metadata_cancel_btn = QPushButton("✖ Cancel")
        _ct = self._get_theme_colors()
        self.metadata_cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_ct["button_bg"]};
                color: {_ct["button_text"]};
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {_ct["button_hover"]};
            }}
        """)
        self.metadata_cancel_btn.clicked.connect(self._on_cancel_metadata_changes)
        self.metadata_cancel_btn.setVisible(False)
        button_layout.addWidget(self.metadata_cancel_btn)

        layout.addLayout(button_layout)

        # Connect all inputs to enter edit mode on change
        for _field_name, input_widget in self.metadata_inputs.items():
            if isinstance(input_widget, QCheckBox):
                input_widget.stateChanged.connect(self._enter_edit_mode)
            elif isinstance(input_widget, QComboBox):
                input_widget.currentTextChanged.connect(self._enter_edit_mode)
            elif isinstance(input_widget, QLineEdit):
                input_widget.textChanged.connect(self._enter_edit_mode)

        return form

    def _generate_suggested_filename(self, bundle) -> str:
        """Generate suggested PDF filename."""
        company = bundle.get("company", "Unknown").replace(" ", "_")
        doc_type = bundle.get("document_type", "Document").replace(" ", "_")
        date = bundle.get("document_date", "").replace("-", "")
        return f"{company}_{doc_type}_{date}.pdf" if date else f"{company}_{doc_type}.pdf"

    def _create_accordion_section(
        self, title: str, content_widget, initially_expanded: bool = False
    ):
        """Create collapsible accordion section."""
        theme = self._get_theme_colors()

        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 1)  # Small bottom margin for spacing
        section_layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {theme["bg_tertiary"]};
                border: none;
                border-radius: 4px;
                padding: 6px 10px;
            }}
            QFrame:hover {{
                background-color: {theme["bg_hover"]};
            }}
        """)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Toggle indicator
        toggle_indicator = QLabel("▼" if initially_expanded else "▶")
        toggle_indicator.setStyleSheet(
            f"color: {theme['text_secondary']}; font-size: 9px; border: none;"
        )
        toggle_indicator.setObjectName("accordion_toggle")
        header_layout.addWidget(toggle_indicator)

        # Title
        title_label = QLabel(title)
        title_label.setObjectName("accordion_title")  # Set object name for easy lookup
        title_label.setStyleSheet(
            f"color: {theme['text_primary']}; font-weight: 600; font-size: 12px; border: none;"
        )
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        section_layout.addWidget(header)

        # Content (scrollable if needed)
        content_scroll = QScrollArea()
        content_scroll.setWidgetResizable(True)
        content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content_scroll.setObjectName("accordion_content")
        content_scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {theme["bg_secondary"]};
                border: none;
            }}
        """)

        content_container = QWidget()
        content_container.setStyleSheet(f"background: {theme['bg_secondary']};")
        content_container_layout = QVBoxLayout(content_container)
        content_container_layout.setContentsMargins(12, 12, 12, 12)
        content_container_layout.setSpacing(0)
        content_container_layout.addWidget(content_widget)
        content_container_layout.addStretch()

        content_scroll.setWidget(content_container)

        # Set viewport background explicitly
        viewport = content_scroll.viewport()
        if viewport is not None:
            viewport.setStyleSheet(f"background: {theme['bg_secondary']};")
        section_layout.addWidget(content_scroll)

        # Set size policy for expansion
        content_scroll.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding if initially_expanded else QSizePolicy.Policy.Ignored,
        )

        # Toggle function - auto-close others
        content_scroll.setVisible(initially_expanded)

        def toggle_section():
            is_currently_visible = content_scroll.isVisible()

            # Only allow opening, not closing
            # Clicking an already-open section does nothing
            if not is_currently_visible:
                # Close all other sections first
                for other_section in self.accordion_sections:
                    other_content = other_section.findChild(QScrollArea, "accordion_content")
                    other_toggle = other_section.findChild(QLabel, "accordion_toggle")
                    if other_content and other_content != content_scroll:
                        other_content.setVisible(False)
                        other_content.setSizePolicy(
                            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored
                        )
                        if other_toggle:
                            other_toggle.setText("▶")

                # Open this section
                content_scroll.setVisible(True)
                content_scroll.setSizePolicy(
                    QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
                )
                toggle_indicator.setText("▼")
            # If already visible, do nothing (can't close by clicking same section)

        header.mousePressEvent = lambda e: toggle_section()  # type: ignore[method-assign,assignment]

        # Store references
        section.accordion_header = header  # type: ignore[attr-defined]
        section.accordion_content = content_scroll  # type: ignore[attr-defined]
        section.accordion_toggle = toggle_indicator  # type: ignore[attr-defined]

        self.accordion_sections.append(section)

        return section

    def _create_file_info_form(self) -> QWidget:
        """Create file information form."""
        import os
        from datetime import datetime

        theme = self._get_theme_colors()

        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        bundle = self.bundles[self.current_bundle_index]

        # Use page_order to map visual index to actual index
        actual_index = (
            self.page_order[self.current_page_index]
            if self.current_page_index < len(self.page_order)
            else self.current_page_index
        )
        if actual_index < len(bundle.get("file_paths", [])):
            file_path = bundle["file_paths"][actual_index]
            filename = Path(file_path).name
            full_path = str(file_path)

            # Get file stats (mock or real)
            if self.prototype_mode:
                file_size_str = "1.2 MB"
                modified_str = "2024-03-15 10:30:00"
            else:
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    file_size_str = self._format_file_size(file_size)
                    modified_time = os.path.getmtime(file_path)
                    modified_str = datetime.fromtimestamp(modified_time).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                else:
                    file_size_str = "Unknown"
                    modified_str = "Unknown"

            def add_info_row(label, value, copyable=False):
                row = QWidget()
                row.setStyleSheet("background: transparent;")
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)

                lbl = QLabel(f"<b>{label}:</b>")
                lbl.setStyleSheet(
                    f"color: {theme['text_primary']}; font-size: 11px; font-weight: 600;"
                )
                lbl.setMinimumWidth(100)
                row_layout.addWidget(lbl)

                val = QLabel(value)
                if copyable:
                    # Make clickable for copy-to-clipboard
                    val.setCursor(Qt.CursorShape.PointingHandCursor)
                    val.setStyleSheet(
                        f"color: {theme['selected']}; font-size: 11px; background: transparent; "
                        f"text-decoration: underline;"
                    )
                    val.setToolTip("Click to copy to clipboard")

                    # Create click handler that copies value to clipboard
                    def make_copy_handler(text):
                        def copy_to_clipboard(event):
                            from PyQt6.QtWidgets import QApplication

                            QApplication.clipboard().setText(text)
                            # Show brief visual feedback
                            original_style = val.styleSheet()
                            val.setStyleSheet(
                                f"color: {theme['success']}; font-size: 11px; background: transparent; "
                                f"text-decoration: underline; font-weight: 700;"
                            )
                            from PyQt6.QtCore import QTimer

                            QTimer.singleShot(300, lambda: val.setStyleSheet(original_style))

                        return copy_to_clipboard

                    val.mousePressEvent = make_copy_handler(value)
                else:
                    val.setStyleSheet(
                        f"color: {theme['text_primary']}; font-size: 11px; background: transparent;"
                    )

                val.setWordWrap(True)
                row_layout.addWidget(val, stretch=1)

                layout.addWidget(row)

            add_info_row("Filename", filename, copyable=True)
            add_info_row("Full Path", full_path, copyable=True)
            add_info_row("File Size", file_size_str)
            add_info_row("Modified", modified_str)

        return widget

    def _create_analysis_info_form(self) -> QWidget:
        """Create analysis information form."""
        theme = self._get_theme_colors()

        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        bundle = self.bundles[self.current_bundle_index]

        # Use page_order to map visual index to actual index
        actual_index = (
            self.page_order[self.current_page_index]
            if self.current_page_index < len(self.page_order)
            else self.current_page_index
        )
        if actual_index < len(bundle.get("analyses", [])):
            analysis = bundle["analyses"][actual_index]
        else:
            analysis = {}

        def add_info_row(label, value, value_color=None):
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            lbl = QLabel(f"<b>{label}:</b>")
            lbl.setStyleSheet(
                f"color: {theme['text_primary']}; font-size: 11px; font-weight: 600; background: transparent;"
            )
            lbl.setMinimumWidth(100)
            row_layout.addWidget(lbl)

            val = QLabel(str(value))
            color = value_color if value_color else theme["text_primary"]
            val.setStyleSheet(f"color: {color}; font-size: 11px; background: transparent;")
            val.setWordWrap(True)
            row_layout.addWidget(val, stretch=1)

            layout.addWidget(row)

        add_info_row("Analysis ID", analysis.get("analysis_id", "N/A"))

        # Confidence score with color coding
        confidence = analysis.get("confidence_score", 0.0)
        if isinstance(confidence, int | float):
            confidence_pct = int(confidence * 100 if confidence <= 1.0 else confidence)

            # Color code based on confidence level
            if confidence_pct >= 80:
                conf_color = theme.get("success", "#10b981")
            elif confidence_pct >= 50:
                conf_color = theme.get("warning", "#f59e0b")
            else:
                conf_color = theme.get("danger", "#ef4444")

            add_info_row("Confidence Score", f"{confidence_pct:.1f}%", value_color=conf_color)
        else:
            add_info_row("Confidence Score", "N/A")

        add_info_row("Provider", analysis.get("provider", "N/A"))
        add_info_row("Model", analysis.get("model", "N/A"))
        add_info_row("Processing Time", analysis.get("processing_time", "N/A"))
        add_info_row("Analysis Date", analysis.get("analysis_date", "N/A"))

        return widget

    def _format_file_size(self, size_bytes: int | float) -> str:
        """Format file size in human-readable format."""
        return BundlePdfConverter.format_file_size(size_bytes)

    def _create_action_bar(self) -> QWidget:
        """Create bottom action bar."""
        theme = self._get_theme_colors()

        bar = QWidget()
        bar.setStyleSheet(f"background: {theme['bg_secondary']};")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)

        # Left side - Navigation
        prev_btn = QPushButton("← Previous Bundle")
        prev_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {theme["button_bg"]};
                color: {theme["button_text"]};
                border: 1px solid {theme["border"]};
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {theme["bg_hover"]};
                border-color: {theme["border_focus"]};
            }}
            QPushButton:disabled {{
                background: {theme["bg_secondary"]};
                color: {theme["text_disabled"]};
            }}
        """
        )
        prev_btn.clicked.connect(self._on_previous_bundle)
        prev_btn.setEnabled(self.current_bundle_index > 0)
        layout.addWidget(prev_btn)
        self.prev_btn = prev_btn

        next_btn = QPushButton("Next Bundle →")
        next_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {theme["button_bg"]};
                color: {theme["button_text"]};
                border: 1px solid {theme["border"]};
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {theme["bg_hover"]};
                border-color: {theme["border_focus"]};
            }}
            QPushButton:disabled {{
                background: {theme["bg_secondary"]};
                color: {theme["text_disabled"]};
            }}
        """
        )
        next_btn.clicked.connect(self._on_next_bundle)
        next_btn.setEnabled(self.current_bundle_index < len(self.bundles) - 1)
        layout.addWidget(next_btn)
        self.next_btn = next_btn

        layout.addStretch()

        # Zoom controls
        btn_style = f"""
            QPushButton {{
                background: {theme["button_bg"]};
                color: {theme["button_text"]};
                border: 1px solid {theme["border"]};
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {theme["button_hover"]};
                border-color: {theme["border"]};
                color: {theme["text_primary"]};
            }}
            QPushButton:pressed {{
                background: {theme["selected"]};
            }}
        """

        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setStyleSheet(btn_style)
        zoom_out_btn.setFixedSize(40, 32)  # Set AFTER stylesheet to ensure it takes effect
        zoom_out_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        zoom_out_btn.setToolTip("Zoom Out")
        zoom_out_btn.clicked.connect(self._on_zoom_out)
        layout.addWidget(zoom_out_btn)

        self.zoom_spinner = QSpinBox()
        self.zoom_spinner.setRange(25, 400)
        self.zoom_spinner.setValue(100)
        self.zoom_spinner.setSuffix("%")
        self.zoom_spinner.setFixedWidth(70)
        self.zoom_spinner.setFixedHeight(32)
        self.zoom_spinner.setStyleSheet(f"""
            QSpinBox {{
                background: {theme["button_bg"]};
                color: {theme["text_primary"]};
                border: 1px solid {theme["border"]};
                border-radius: 4px;
                padding: 2px 4px;
                font-size: 11px;
            }}
            QSpinBox:focus {{
                border-color: {theme["selected"]};
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 0px;
            }}
        """)
        self.zoom_spinner.valueChanged.connect(self._on_zoom_changed)
        layout.addWidget(self.zoom_spinner)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setStyleSheet(btn_style)
        zoom_in_btn.setFixedSize(40, 32)  # Set AFTER stylesheet to ensure it takes effect
        zoom_in_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        zoom_in_btn.setToolTip("Zoom In")
        zoom_in_btn.clicked.connect(self._on_zoom_in)
        layout.addWidget(zoom_in_btn)

        # Separator
        layout.addSpacing(12)

        # Fit buttons
        fit_width_btn = QPushButton("⬌")
        fit_width_btn.setStyleSheet(btn_style)
        fit_width_btn.setFixedSize(40, 32)
        fit_width_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        fit_width_btn.setToolTip("Fit to Width")
        fit_width_btn.clicked.connect(self._on_fit_width)
        layout.addWidget(fit_width_btn)

        fit_height_btn = QPushButton("⬍")
        fit_height_btn.setStyleSheet(btn_style)
        fit_height_btn.setFixedSize(40, 32)
        fit_height_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        fit_height_btn.setToolTip("Fit to Height")
        fit_height_btn.clicked.connect(self._on_fit_height)
        layout.addWidget(fit_height_btn)

        fit_window_btn = QPushButton("⛶")
        fit_window_btn.setStyleSheet(btn_style)
        fit_window_btn.setFixedSize(40, 32)
        fit_window_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        fit_window_btn.setToolTip("Fit to Window")
        fit_window_btn.clicked.connect(self._on_fit_window)
        layout.addWidget(fit_window_btn)

        # Separator
        layout.addSpacing(12)

        # Rotation controls
        rotate_left_btn = QPushButton("↺")
        rotate_left_btn.setStyleSheet(btn_style)
        rotate_left_btn.setFixedSize(40, 32)  # Set AFTER stylesheet to ensure it takes effect
        rotate_left_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        rotate_left_btn.setToolTip("Rotate Counter-Clockwise")
        rotate_left_btn.clicked.connect(self._on_rotate_ccw)
        layout.addWidget(rotate_left_btn)

        rotate_right_btn = QPushButton("↻")
        rotate_right_btn.setStyleSheet(btn_style)
        rotate_right_btn.setFixedSize(40, 32)  # Set AFTER stylesheet to ensure it takes effect
        rotate_right_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        rotate_right_btn.setToolTip("Rotate Clockwise")
        rotate_right_btn.clicked.connect(self._on_rotate_cw)
        layout.addWidget(rotate_right_btn)

        layout.addStretch()

        # Right side - Bundle decisions
        skip_btn = QPushButton("⏭ Skip for Later")
        skip_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {theme["warning"]};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {theme["warning_hover"]};
            }}
        """
        )
        skip_btn.clicked.connect(self._on_skip_bundle)
        layout.addWidget(skip_btn)
        self.skip_btn = skip_btn

        reject_btn = QPushButton("✗ Reject Bundle")
        reject_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {theme["danger"]};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {theme["danger_hover"]};
            }}
        """
        )
        reject_btn.clicked.connect(self._on_reject_bundle)
        layout.addWidget(reject_btn)
        self.reject_btn = reject_btn

        accept_btn = QPushButton("✓ Accept && Convert to PDF")
        accept_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {theme["success"]};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {theme["success_hover"]};
            }}
        """
        )
        accept_btn.setMinimumWidth(200)
        accept_btn.clicked.connect(self._on_accept_bundle)
        layout.addWidget(accept_btn)
        self.accept_btn = accept_btn

        return bar

    def _create_mock_bundles(self) -> list:
        """Create mock bundle data with complete metadata."""
        bundles = []
        companies = [
            "Acme Corporation",
            "TechCorp Industries",
            "Global Shipping LLC",
            "ABC Manufacturing",
        ]
        doc_types = ["Invoice", "Receipt", "Statement", "Contract"]

        for i in range(1, 8):
            # Make first bundle have 12 pages for demo
            num_pages = 12 if i == 1 else (i % 5) + 2

            company = companies[i % 4]
            doc_type = doc_types[i % 4]

            # Create analyses for each page
            analyses = []
            for p in range(num_pages):
                analyses.append(
                    {
                        "document_type": doc_type,
                        "company": company,
                        "page_number": str(p + 1),
                        "total_pages": str(num_pages),
                        "rotation_needed": "none",
                        "confidence_score": 0.85 + (p * 0.01),  # Slight variation per page
                        "tax_related": i % 3 == 0,  # Some are tax related
                        "analysis_id": f"analysis_{i:03d}_{p:03d}",
                        "provider": "Ollama",
                        "model": "qwen2.5-vl",
                        "processing_time": f"{1200 + (p * 100)}ms",
                        "analysis_date": f"2024-03-{15 + i:02d} 10:{30 + p:02d}:00",
                    }
                )

            bundles.append(
                {
                    "bundle_id": f"bundle_{i:03d}",
                    "company": company,
                    "document_type": doc_type,
                    "document_date": f"2024-0{(i % 9) + 1}-15",
                    "confidence_score": 0.95 - (i * 0.05),
                    "file_paths": [
                        f"mock_bundle_{i}_page_{p}.png" for p in range(1, num_pages + 1)
                    ],
                    "analyses": analyses,
                }
            )
        return bundles

    def _load_current_bundle(self):
        """Load the current bundle data."""
        bundle = self.bundles[self.current_bundle_index]
        self.page_order = list(range(len(bundle.get("file_paths", []))))
        self.current_page_index = 0
        self.rotation_angle = 0

        # Apply default zoom from config instead of hardcoded 100
        if self.default_zoom_mode == "custom_%":
            self.zoom_level = self.default_zoom_percent
        else:
            self.zoom_level = 100  # Will be recalculated by fit methods

        self._update_header()
        self._populate_thumbnails()
        self._update_metadata_form()
        self._display_current_page()

        # Reset output filename manual edit flag for new bundle
        self.output_filename_manually_edited = False

        # Update output filename based on bundle metadata
        if hasattr(self, "output_filename_input"):
            self._update_output_filename()

        if hasattr(self, "accordion_sections"):  # Only if accordions initialized
            self._refresh_accordion_content()

        # Apply configured zoom mode after UI is fully laid out
        # Use longer delay to ensure container dimensions are available
        QTimer.singleShot(300, self._apply_default_zoom)

    def _update_header(self):
        """Update header with current bundle info."""
        theme = self._get_theme_colors()
        bundle = self.bundles[self.current_bundle_index]

        # Progress
        self.progress_label.setText(
            f"Bundle {self.current_bundle_index + 1} of {len(self.bundles)}"
        )

        # Bundle info with title case
        doc_type = bundle.get("document_type", "Unknown").title()
        company = bundle.get("company", "Unknown").title()
        pages = len(bundle.get("file_paths", []))
        self.bundle_info_label.setText(f"<b>{doc_type}</b> - {company} ({pages} pages)")

        # Confidence with theme colors
        confidence = bundle.get("confidence_score", 0.0)
        confidence_pct = int(confidence * 100)
        if confidence >= 0.8:
            badge_color = theme["success"]
        elif confidence >= 0.5:
            badge_color = theme["warning"]
        else:
            badge_color = theme["danger"]

        self.confidence_badge.setText(f"{confidence_pct}%")
        self.confidence_badge.setStyleSheet(f"""
            background: {badge_color};
            color: white;
            padding: 4px 10px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 12px;
        """)

        # Stats
        stats_text = f"✓ {len(self.accepted_bundles)} Accepted  •  ✗ {len(self.rejected_bundles)} Rejected  •  ⏭ {len(self.skipped_bundles)} Skipped"
        self.stats_label.setText(stats_text)

        # Navigation buttons
        self.prev_btn.setEnabled(self.current_bundle_index > 0)
        self.next_btn.setEnabled(self.current_bundle_index < len(self.bundles) - 1)

    def _populate_thumbnails(self):
        """Delegate to BundleThumbnailPanel.populate()."""
        bundle = self.bundles[self.current_bundle_index]
        self.thumbnail_panel.populate(
            bundle.get("file_paths", []),
            self.page_order,
            self.current_page_index,
            self.prototype_mode,
        )

    def _update_metadata_form(self):
        """Update metadata form with current bundle data."""
        bundle = self.bundles[self.current_bundle_index]

        # Temporarily disconnect signals to prevent triggering edit mode during programmatic updates
        if "document_type" in self.metadata_inputs:
            widget = self.metadata_inputs["document_type"]
            if isinstance(widget, QComboBox):
                widget.currentTextChanged.disconnect(self._enter_edit_mode)
            widget.setCurrentText(bundle.get("document_type", ""))
            if isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self._enter_edit_mode)

        if "company" in self.metadata_inputs:
            widget = self.metadata_inputs["company"]
            if isinstance(widget, QComboBox):
                widget.currentTextChanged.disconnect(self._enter_edit_mode)
            widget.setCurrentText(bundle.get("company", ""))
            if isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self._enter_edit_mode)

        if "document_date" in self.metadata_inputs:
            widget = self.metadata_inputs["document_date"]
            if isinstance(widget, QLineEdit):
                widget.textChanged.disconnect(self._enter_edit_mode)
            widget.setText(bundle.get("document_date", ""))
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._enter_edit_mode)

    def _display_current_page(self):
        """Display the current page in large preview."""
        bundle = self.bundles[self.current_bundle_index]
        file_paths = bundle.get("file_paths", [])

        if not file_paths or self.current_page_index >= len(self.page_order):
            return

        actual_index = self.page_order[self.current_page_index]
        file_path = file_paths[actual_index]

        if self.prototype_mode:
            # Mock preview
            base_pixmap = QPixmap(600, 800)
            color_idx = actual_index
            base_color = QColor(220 + (color_idx * 10) % 30, 230, 245)
            base_pixmap.fill(base_color)

            painter = QPainter(base_pixmap)
            painter.drawText(
                base_pixmap.rect(),
                Qt.AlignmentFlag.AlignCenter,
                f"Page {actual_index + 1}\n\n(Mock Preview)",
            )
            painter.end()
        else:
            # Real mode - load actual image
            base_pixmap = QPixmap(file_path)
            if base_pixmap.isNull():
                # Fallback to placeholder if image fails to load
                base_pixmap = QPixmap(600, 800)
                base_pixmap.fill(QColor(240, 240, 240))
                painter = QPainter(base_pixmap)
                painter.drawText(
                    base_pixmap.rect(),
                    Qt.AlignmentFlag.AlignCenter,
                    f"Page {actual_index + 1}\n\nFailed to load image:\n{file_path}",
                )
                painter.end()

        # Store original pixmap for fit calculations
        self.original_pixmap = base_pixmap

        # Apply transforms
        transformed = self._apply_transform(base_pixmap)
        self.large_preview.setPixmap(transformed)

        # Update page label
        self.page_label.setText(f"Page {self.current_page_index + 1} of {len(self.page_order)}")

    def _apply_transform(self, pixmap: QPixmap) -> QPixmap:
        """Apply rotation and zoom to pixmap."""
        # Rotation
        if self.rotation_angle != 0:
            transform = QTransform()
            transform.rotate(self.rotation_angle)
            pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        # Zoom
        if self.zoom_level != 100:
            zoom_factor = self.zoom_level / 100.0
            new_width = int(pixmap.width() * zoom_factor)
            new_height = int(pixmap.height() * zoom_factor)
            pixmap = pixmap.scaled(
                new_width,
                new_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        return pixmap

    # Event handlers

    def _on_thumbnail_clicked(self, visual_index: int):
        """Handle thumbnail click."""
        from services.logging_service import get_logger

        logger = get_logger()

        logger.info(
            f"[THUMBNAIL CLICK] Clicked thumbnail {visual_index}, current_page_index was {self.current_page_index}"
        )
        try:
            self.current_page_index = visual_index
            logger.info(
                f"[THUMBNAIL CLICK] Updated current_page_index to {self.current_page_index}"
            )

            self._populate_thumbnails()
            logger.info("[THUMBNAIL CLICK] Thumbnails populated")

            self._display_current_page()
            logger.info("[THUMBNAIL CLICK] Current page displayed")

            logger.info("[THUMBNAIL CLICK] Calling _refresh_accordion_content()")
            self._refresh_accordion_content()  # Update metadata for new page
            logger.info("[THUMBNAIL CLICK] Finished _refresh_accordion_content()")
        except Exception as e:
            logger.error(f"[THUMBNAIL CLICK] Error handling thumbnail click: {e}", exc_info=True)

    def _move_page_up(self, visual_index: int):
        """Move page up in order."""
        if visual_index > 0:
            self.page_order[visual_index], self.page_order[visual_index - 1] = (
                self.page_order[visual_index - 1],
                self.page_order[visual_index],
            )
            self.current_page_index = visual_index - 1
            self._populate_thumbnails()
            self._display_current_page()
            self._refresh_accordion_content()

    def _move_page_down(self, visual_index: int):
        """Move page down in order."""
        if visual_index < len(self.page_order) - 1:
            self.page_order[visual_index], self.page_order[visual_index + 1] = (
                self.page_order[visual_index + 1],
                self.page_order[visual_index],
            )
            self.current_page_index = visual_index + 1
            self._populate_thumbnails()
            self._display_current_page()
            self._refresh_accordion_content()

    def _on_drop_requested(self, from_index: int, to_index: int):
        """Handle drop - reorder pages."""
        if from_index == to_index:
            return

        # Reorder
        page = self.page_order.pop(from_index)
        self.page_order.insert(to_index, page)

        self.current_page_index = to_index
        self._populate_thumbnails()
        self._display_current_page()
        self._refresh_accordion_content()

    def _on_zoom_in(self):
        """Zoom in."""
        new_zoom = min(400, self.zoom_level + 25)
        self.zoom_spinner.setValue(new_zoom)

    def _on_zoom_out(self):
        """Zoom out."""
        new_zoom = max(25, self.zoom_level - 25)
        self.zoom_spinner.setValue(new_zoom)

    def _on_zoom_changed(self, value: int):
        """Handle zoom change."""
        self.zoom_level = value
        self._display_current_page()

    def _on_fit_width(self):
        """Fit image to preview panel width."""
        if not hasattr(self, "original_pixmap") or self.original_pixmap is None:
            return

        # Get preview container width (subtract some padding for margins)
        container_width = self.preview_container.width() - 40

        # Get original image width (accounting for rotation)
        if self.rotation_angle in (90, 270):
            # Width and height are swapped when rotated 90 or 270 degrees
            image_width = self.original_pixmap.height()
        else:
            image_width = self.original_pixmap.width()

        if image_width > 0:
            # Calculate zoom percentage to fit width
            zoom = int((container_width / image_width) * 100)
            # Clamp to valid range
            zoom = max(25, min(400, zoom))
            self.zoom_spinner.setValue(zoom)

    def _on_fit_height(self):
        """Fit image to preview panel height."""
        if not hasattr(self, "original_pixmap") or self.original_pixmap is None:
            return

        # Get preview container height (subtract some padding for margins and controls)
        container_height = self.preview_container.height() - 100

        # Get original image height (accounting for rotation)
        if self.rotation_angle in (90, 270):
            # Width and height are swapped when rotated 90 or 270 degrees
            image_height = self.original_pixmap.width()
        else:
            image_height = self.original_pixmap.height()

        if image_height > 0:
            # Calculate zoom percentage to fit height
            zoom = int((container_height / image_height) * 100)
            # Clamp to valid range
            zoom = max(25, min(400, zoom))
            self.zoom_spinner.setValue(zoom)

    def _on_fit_window(self):
        """Fit image to preview panel (both width and height)."""
        if not hasattr(self, "original_pixmap") or self.original_pixmap is None:
            return

        # Get preview container dimensions (subtract padding)
        container_width = self.preview_container.width() - 40
        container_height = self.preview_container.height() - 100

        # Get original image dimensions (accounting for rotation)
        if self.rotation_angle in (90, 270):
            # Width and height are swapped when rotated 90 or 270 degrees
            image_width = self.original_pixmap.height()
            image_height = self.original_pixmap.width()
        else:
            image_width = self.original_pixmap.width()
            image_height = self.original_pixmap.height()

        if image_width > 0 and image_height > 0:
            # Calculate zoom to fit both dimensions (use the smaller zoom)
            zoom_width = int((container_width / image_width) * 100)
            zoom_height = int((container_height / image_height) * 100)
            zoom = min(zoom_width, zoom_height)

            # Clamp to valid range
            zoom = max(25, min(400, zoom))
            self.zoom_spinner.setValue(zoom)

    def _apply_default_zoom(self):
        """Apply the default zoom mode from config settings."""
        if self.default_zoom_mode == "fit_to_width":
            self._on_fit_width()
        elif self.default_zoom_mode == "fit_to_height":
            self._on_fit_height()
        elif self.default_zoom_mode == "fit_to_window":
            self._on_fit_window()
        elif self.default_zoom_mode == "custom_%":
            # Zoom level already set in _load_current_bundle
            self._display_current_page()

    def _on_rotate_ccw(self):
        """Rotate counter-clockwise."""
        self.rotation_angle = (self.rotation_angle - 90) % 360
        self._display_current_page()

    def _on_rotate_cw(self):
        """Rotate clockwise."""
        self.rotation_angle = (self.rotation_angle + 90) % 360
        self._display_current_page()

    def _on_output_filename_manual_edit(self):
        """Mark output filename as manually edited."""
        # Only set flag if the text was changed by user (not programmatically)
        if hasattr(self, "output_filename_input"):
            self.output_filename_manually_edited = True

    def _update_output_filename(self):
        """Update output filename based on current metadata (unless manually edited)."""
        if self.output_filename_manually_edited:
            return  # Don't auto-update if user manually edited

        # Get metadata values from inputs
        company = ""
        document_type = ""
        document_date = ""

        if "company" in self.metadata_inputs:
            widget = self.metadata_inputs["company"]
            if isinstance(widget, QComboBox):
                company = widget.currentText()
            elif isinstance(widget, QLineEdit):
                company = widget.text()

        if "document_type" in self.metadata_inputs:
            widget = self.metadata_inputs["document_type"]
            if isinstance(widget, QComboBox):
                document_type = widget.currentText()
            elif isinstance(widget, QLineEdit):
                document_type = widget.text()

        if "document_date" in self.metadata_inputs:
            widget = self.metadata_inputs["document_date"]
            if isinstance(widget, QLineEdit):
                document_date = widget.text()

        # Build filename with sanitization and title case
        filename_parts = []
        if company:
            filename_parts.append(company.title())
        if document_type:
            filename_parts.append(document_type.title())
        if document_date:
            filename_parts.append(document_date)  # Don't title case dates

        # Join with dashes, or use default if all empty
        filename = " - ".join(filename_parts) if filename_parts else "document"

        # Sanitize filename (remove invalid characters)
        filename = self._sanitize_filename(filename)

        # DON'T add .pdf extension to display - it will be added automatically when saving

        # Update textbox without triggering the manual edit flag
        if hasattr(self, "output_filename_input"):
            # Temporarily disconnect to avoid triggering manual edit
            self.output_filename_input.textChanged.disconnect(self._on_output_filename_manual_edit)
            self.output_filename_input.setText(filename)
            self.output_filename_input.textChanged.connect(self._on_output_filename_manual_edit)

    def _sanitize_filename(self, filename: str) -> str:
        """Remove invalid characters from filename."""
        # Remove invalid filename characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, "")
        # Remove leading/trailing spaces and dots
        filename = filename.strip(". ")
        return filename

    def _get_pdf_filename(self, filename: str) -> str:
        """
        Get final PDF filename with .PDF extension enforced.

        Strips any existing extension and adds .PDF
        As documented in the tooltip, any extension will be removed and replaced.

        Args:
            filename: Input filename (may or may not have extension)

        Returns:
            Filename with .PDF extension
        """
        import os

        # Remove any existing extension
        name_without_ext = os.path.splitext(filename)[0]

        # Sanitize
        name_without_ext = self._sanitize_filename(name_without_ext)

        # Force .PDF extension (uppercase for consistency)
        return f"{name_without_ext}.PDF"

    def _on_previous_bundle(self):
        """Navigate to previous bundle."""
        if self.current_bundle_index > 0:
            self.current_bundle_index -= 1
            self._load_current_bundle()

    def _on_next_bundle(self):
        """Navigate to next bundle."""
        if self.current_bundle_index < len(self.bundles) - 1:
            self.current_bundle_index += 1
            self._load_current_bundle()

    def _on_skip_bundle(self):
        """Skip bundle for later review."""
        bundle = self.bundles[self.current_bundle_index]
        self.skipped_bundles.append(bundle)

        # Move to next or close
        if self.current_bundle_index < len(self.bundles) - 1:
            self._on_next_bundle()
        else:
            self._show_completion_summary()

    def _on_reject_bundle(self):
        """Reject the current bundle."""
        bundle = self.bundles[self.current_bundle_index]

        reply = QMessageBox.question(
            self,
            "Reject Bundle",
            f"Reject this bundle?\n\n{bundle.get('document_type')} - {bundle.get('company')}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.rejected_bundles.append(bundle)
            self.bundle_rejected.emit(bundle)

            # Move to next or close
            if self.current_bundle_index < len(self.bundles) - 1:
                self._on_next_bundle()
            else:
                self._show_completion_summary()

    def _on_accept_bundle(self):
        """Accept bundle and convert to PDF."""
        bundle = self.bundles[self.current_bundle_index]

        # Get metadata edits
        metadata = {
            "document_type": self.metadata_inputs["document_type"].currentText(),
            "company": self.metadata_inputs["company"].currentText(),
            "document_date": self.metadata_inputs["document_date"].text(),
        }

        # Get output filename from textbox (user may have edited it)
        if hasattr(self, "output_filename_input"):
            raw_filename = self.output_filename_input.text().strip()
        else:
            # Fallback if textbox doesn't exist
            raw_filename = self._generate_suggested_filename(bundle)

        # Enforce .PDF extension (strips any existing extension user may have typed)
        metadata["output_filename"] = self._get_pdf_filename(raw_filename)

        # Show PDF conversion progress
        self._show_pdf_conversion(bundle, metadata)

    def _determine_output_directory(self, bundle: dict) -> str:
        """Determine output directory based on configuration strategy."""
        return self._pdf_converter.determine_output_directory(bundle)

    def _show_pdf_conversion(self, bundle, metadata):
        """Show PDF conversion progress dialog."""
        progress_dialog = QDialog(self)
        progress_dialog.setWindowTitle("Converting to PDF")
        progress_dialog.setMinimumWidth(400)
        progress_dialog.setModal(True)

        layout = QVBoxLayout(progress_dialog)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Icon and message
        icon_label = QLabel("📄")
        icon_label.setStyleSheet("font-size: 48px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        message = QLabel(f"Converting to PDF...\n\n{metadata['output_filename']}")
        message.setStyleSheet("color: white; font-size: 14px;")  # White text for dark mode
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setWordWrap(True)
        layout.addWidget(message)

        # Progress bar
        progress = QProgressBar()
        progress.setMinimum(0)
        progress.setMaximum(0)  # Indeterminate
        _ct = self._get_theme_colors()
        progress.setStyleSheet(f"""
            QProgressBar {{
                background: {_ct["bg_tertiary"]};
                border-radius: 4px;
                height: 8px;
            }}
            QProgressBar::chunk {{
                background: {Colors.PRIMARY};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(progress)

        progress_dialog.show()

        # Simulate PDF conversion (in real app, call bundling service)
        QTimer.singleShot(
            2000, lambda: self._complete_pdf_conversion(progress_dialog, bundle, metadata)
        )

    def _complete_pdf_conversion(self, progress_dialog, bundle, metadata):
        """Complete PDF conversion and show success."""
        progress_dialog.close()

        if self.prototype_mode:
            # Mock mode - just show success
            success_dialog = QMessageBox(self)
            success_dialog.setWindowTitle("PDF Created")
            success_dialog.setIcon(QMessageBox.Icon.Information)
            success_dialog.setText(f"✓ PDF created successfully!\n\n{metadata['output_filename']}")
            success_dialog.setStandardButtons(
                QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Ok
            )
            success_dialog.setDefaultButton(QMessageBox.StandardButton.Ok)

            result = success_dialog.exec()

            if result == QMessageBox.StandardButton.Open:
                QMessageBox.information(
                    self,
                    "Open PDF",
                    f"Would open: {metadata['output_filename']}\n\n(Mock implementation)",
                )

            # Track acceptance
            bundle_with_metadata = {**bundle, **metadata, "page_order": self.page_order}
            self.accepted_bundles.append(bundle_with_metadata)
            self.bundle_accepted.emit(bundle_with_metadata)

            # Move to next or complete
            if self.current_bundle_index < len(self.bundles) - 1:
                self._on_next_bundle()
            else:
                self._show_completion_summary()
            return

        # Real conversion
        try:
            ordered_paths = [bundle["file_paths"][i] for i in self.page_order]
            output_dir = self._pdf_converter.determine_output_directory(bundle)
            pdf_path = self._pdf_converter.convert(
                bundle, metadata, ordered_paths, self.rotation_angle
            )

            success_dialog = QMessageBox(self)
            success_dialog.setWindowTitle("PDF Created")
            success_dialog.setIcon(QMessageBox.Icon.Information)
            success_dialog.setText(
                f"✓ PDF created successfully!\n\n{metadata['output_filename']}\n\nLocation: {output_dir}"
            )
            success_dialog.setStandardButtons(
                QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Ok
            )
            success_dialog.setDefaultButton(QMessageBox.StandardButton.Ok)

            result = success_dialog.exec()

            if result == QMessageBox.StandardButton.Open:
                self._pdf_converter.open_pdf(pdf_path)

            bundle_with_metadata = {
                **bundle,
                **metadata,
                "page_order": self.page_order,
                "pdf_path": pdf_path,
            }
            self.accepted_bundles.append(bundle_with_metadata)
            self.bundle_accepted.emit(bundle_with_metadata)

            if self.current_bundle_index < len(self.bundles) - 1:
                self._on_next_bundle()
            else:
                self._show_completion_summary()

        except Exception as e:
            QMessageBox.critical(
                self, "PDF Conversion Failed", f"Failed to convert bundle to PDF:\n\n{str(e)}"
            )

    def _show_completion_summary(self):
        """Show workflow completion summary."""
        summary = QMessageBox(self)
        summary.setWindowTitle("Workflow Complete")
        summary.setIcon(QMessageBox.Icon.Information)

        summary_text = f"""
Bundle Review Complete!

✓ Accepted: {len(self.accepted_bundles)}
✗ Rejected: {len(self.rejected_bundles)}
⏭ Skipped: {len(self.skipped_bundles)}

Total Reviewed: {len(self.accepted_bundles) + len(self.rejected_bundles)} / {len(self.bundles)}
        """.strip()

        summary.setText(summary_text)
        summary.setStandardButtons(QMessageBox.StandardButton.Ok)
        summary.exec()

        # Emit completion
        self.workflow_completed.emit(
            {
                "accepted": len(self.accepted_bundles),
                "rejected": len(self.rejected_bundles),
                "skipped": len(self.skipped_bundles),
                "total": len(self.bundles),
            }
        )

        if not self.embedded_mode:
            self.accept()

    def _on_reanalyze_page(self):
        """Re-analyze the current page using LLM provider."""
        if self.prototype_mode:
            QMessageBox.information(
                self,
                "Re-analyze Page",
                "Re-analysis feature is not available in prototype mode.\n\n"
                "In production, this would:\n"
                "1. Call the configured LLM provider\n"
                "2. Extract metadata from the current page\n"
                "3. Update the analysis database\n"
                "4. Refresh the metadata fields",
            )
            return

        # Production implementation (reference from bundle_review_window_v2.py)
        from services.analysis_service import AnalysisService

        bundle = self.bundles[self.current_bundle_index]

        # Use page_order to map visual index to actual index
        actual_index = (
            self.page_order[self.current_page_index]
            if self.current_page_index < len(self.page_order)
            else self.current_page_index
        )
        if actual_index >= len(bundle.get("file_paths", [])):
            return

        file_path = bundle["file_paths"][actual_index]

        # Show progress
        progress = QProgressBar()
        progress.setMinimum(0)
        progress.setMaximum(0)
        progress.setWindowTitle("Re-analyzing Page")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        try:
            # Create progress callback to update progress bar title
            def update_progress(status_text: str):
                progress.setWindowTitle(status_text)
                QApplication.processEvents()  # Force UI update

            # Use centralized re-analysis method (resets status and forces fresh analysis)
            analysis_service = AnalysisService(
                self.config_manager, self.analysis_db, self.metadata_db
            )
            result = analysis_service.re_analyze_file(file_path, progress_callback=update_progress)

            if result["success"]:
                # Analysis already saved to database by re_analyze_file
                # Get the fresh analysis from the result
                fresh_analysis = result.get("analysis")
                if fresh_analysis:
                    # Update bundle data with the new analysis metadata
                    # Use actual_index (already calculated above) to update the correct analysis
                    bundle["analyses"][actual_index] = fresh_analysis

                    # Refresh UI
                    self._refresh_accordion_content()

                    QMessageBox.information(self, "Success", "Page re-analyzed successfully!")
                else:
                    QMessageBox.warning(self, "Error", "Re-analysis completed but no data returned")
            else:
                QMessageBox.warning(
                    self, "Error", f"Re-analysis failed:\n{result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Re-analysis error:\n{str(e)}")
        finally:
            progress.close()

    def _on_add_page(self):
        """Add a page from other bundles or loose pages."""
        if self.prototype_mode:
            QMessageBox.information(
                self,
                "Add Page",
                "Add page feature is not available in prototype mode.\n\n"
                "In production, this would:\n"
                "1. Show a dialog with all available pages\n"
                "2. Allow searching/filtering pages\n"
                "3. Add selected page to current bundle\n"
                "4. Update page order and refresh thumbnails",
            )
            return

        # Production implementation would show a page picker dialog
        # For now, placeholder
        QMessageBox.information(
            self,
            "Add Page",
            "This feature allows you to:\n\n"
            "• Browse pages from other bundles\n"
            "• Add loose/unassigned pages\n"
            "• Search pages by metadata\n\n"
            "Implementation: Create a PagePickerDialog that lists all available pages",
        )

    def _on_remove_page(self, visual_index: int):
        """Remove a page from the current bundle."""
        bundle = self.bundles[self.current_bundle_index]

        if len(bundle["file_paths"]) <= 1:
            QMessageBox.warning(
                self,
                "Cannot Remove",
                "Cannot remove the last page from a bundle.\n\n"
                "A bundle must have at least one page.",
            )
            return

        actual_index = self.page_order[visual_index]
        file_path = bundle["file_paths"][actual_index]
        filename = Path(file_path).name

        reply = QMessageBox.question(
            self,
            "Remove Page",
            f"Remove this page from the bundle?\n\n{filename}\n\n"
            "The page will be marked as a loose page.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Remove from file_paths and analyses
            bundle["file_paths"].pop(actual_index)
            if "analyses" in bundle and actual_index < len(bundle["analyses"]):
                bundle["analyses"].pop(actual_index)

            # Update page_order
            self.page_order = [
                idx if idx < actual_index else idx - 1
                for idx in self.page_order
                if idx != actual_index
            ]

            # Adjust current page index if needed
            if self.current_page_index >= len(self.page_order):
                self.current_page_index = max(0, len(self.page_order) - 1)

            # Refresh UI
            self._populate_thumbnails()
            self._display_current_page()
            self._update_header()

    def _refresh_accordion_content(self):
        """Refresh accordion sections when page changes."""
        from PyQt6.QtWidgets import QApplication

        from services.logging_service import get_logger

        logger = get_logger()

        try:
            logger.info(
                f"[REFRESH ACCORDION] Starting refresh, current_page_index={self.current_page_index}"
            )
            logger.info(
                f"[REFRESH ACCORDION] Number of accordion sections: {len(self.accordion_sections)}"
            )

            # Find and update each accordion section
            for idx, section in enumerate(self.accordion_sections):
                logger.info(f"[REFRESH ACCORDION] Processing section {idx}")

                if hasattr(section, "accordion_content"):
                    content_scroll = section.accordion_content  # This is a QScrollArea
                    logger.info(f"[REFRESH ACCORDION] Section {idx} has accordion_content")

                    # Get title from the section - use object name to find the correct label
                    title_label = section.findChild(QLabel, "accordion_title")
                    if title_label:
                        title = title_label.text()
                        logger.info(f"[REFRESH ACCORDION] Section {idx} title: '{title}'")

                        # Get the widget inside the scroll area (content_container)
                        content_container = content_scroll.widget()
                        if content_container:
                            layout = content_container.layout()
                            if layout:
                                items_before = layout.count()
                                logger.info(
                                    f"[REFRESH ACCORDION] Section {idx} has layout with {items_before} items BEFORE clearing"
                                )

                                # Remove old widgets immediately (not deleteLater)
                                widgets_to_delete = []
                                spacer_items = []
                                while layout.count() > 0:
                                    item = layout.takeAt(0)
                                    if item.widget():
                                        widget = item.widget()
                                        logger.info(
                                            f"[REFRESH ACCORDION] Removing widget: {widget.__class__.__name__}"
                                        )
                                        widget.setParent(None)  # Remove parent immediately
                                        widget.hide()  # Hide immediately
                                        widgets_to_delete.append(widget)
                                    elif item.spacerItem():
                                        logger.info("[REFRESH ACCORDION] Removing spacer item")
                                        spacer_items.append(item)

                                # Delete all old widgets
                                for widget in widgets_to_delete:
                                    widget.deleteLater()

                                # Force event processing to ensure widgets are deleted before adding new ones
                                QApplication.processEvents()

                                items_after_clear = layout.count()
                                logger.info(
                                    f"[REFRESH ACCORDION] Removed {len(widgets_to_delete)} widgets and {len(spacer_items)} spacers. Layout now has {items_after_clear} items"
                                )

                                # Add new widget based on section title
                                if "Extracted Metadata" in title:
                                    logger.info("[REFRESH ACCORDION] Creating new metadata form")
                                    new_widget = self._create_metadata_form()
                                elif "File Information" in title:
                                    logger.info("[REFRESH ACCORDION] Creating new file info form")
                                    new_widget = self._create_file_info_form()
                                elif "Analysis Information" in title:
                                    logger.info(
                                        "[REFRESH ACCORDION] Creating new analysis info form"
                                    )
                                    new_widget = self._create_analysis_info_form()
                                else:
                                    logger.warning(
                                        f"[REFRESH ACCORDION] Title '{title}' didn't match any section type"
                                    )
                                    continue

                                layout.addWidget(new_widget)
                                layout.addStretch()  # Add stretch like the initial creation does
                                items_after_add = layout.count()
                                logger.info(
                                    f"[REFRESH ACCORDION] Added new widget ({new_widget.__class__.__name__}) and stretch to section {idx}. Layout now has {items_after_add} items"
                                )
                            else:
                                logger.warning(
                                    f"[REFRESH ACCORDION] Section {idx} content_container has no layout"
                                )
                        else:
                            logger.warning(
                                f"[REFRESH ACCORDION] Section {idx} scroll area has no widget"
                            )
                    else:
                        logger.warning(f"[REFRESH ACCORDION] Section {idx} has no title label")
                else:
                    logger.warning(
                        f"[REFRESH ACCORDION] Section {idx} has no accordion_content attribute"
                    )

            logger.info("[REFRESH ACCORDION] Finished refresh")
        except Exception as e:
            logger.error(
                f"[REFRESH ACCORDION] Error refreshing accordion content: {e}", exc_info=True
            )

    def _toggle_theme(self):
        """Toggle between light and dark mode (not used - theme set from config)."""
        self.dark_mode = not self.dark_mode

        # Apply theme
        if self.dark_mode:
            self._apply_dark_theme()
        else:
            self._apply_light_theme()

        # Force UI refresh by updating all component styles
        self._update_all_component_styles()

    def _get_theme_colors(self):
        """Get current theme colors."""
        return get_bundle_colors(self.dark_mode)

    def _hex_to_rgb(self, hex_color: str) -> tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        return _hex_to_rgb_fn(hex_color)

    def _apply_dark_theme(self):
        """Apply dark theme colors."""
        self.setStyleSheet(build_bundle_stylesheet(True))

    def _apply_light_theme(self):
        """Apply light theme colors."""
        self.setStyleSheet(build_bundle_stylesheet(False))

    def _update_all_component_styles(self):
        """Update all component styles based on current theme."""
        theme = self._get_theme_colors()

        # Apply base theme first
        if self.dark_mode:
            self._apply_dark_theme()
        else:
            self._apply_light_theme()

        # Update header components
        if hasattr(self, "header_widget"):
            self.header_widget.setStyleSheet(f"background: {theme['bg_secondary']};")

        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(
                f"font-size: 18px; font-weight: bold; color: {theme['text_primary']}; "
                f"text-decoration: none; background: transparent;"
            )

        if hasattr(self, "progress_label"):
            self.progress_label.setStyleSheet(
                f"color: {theme['text_primary']}; font-weight: 600; font-size: 13px; "
                f"text-decoration: none; background: transparent; border: none;"
            )

        if hasattr(self, "stats_label"):
            self.stats_label.setStyleSheet(f"color: {theme['text_secondary']}; font-size: 13px;")

        if hasattr(self, "bundle_info_label"):
            self.bundle_info_label.setStyleSheet(
                f"color: {theme['text_primary']}; font-size: 13px; background: transparent;"
            )

        if hasattr(self, "confidence_badge"):
            # Badge color depends on confidence, but text should be white/dark accordingly
            confidence = self.bundles[self.current_bundle_index].get("confidence_score", 0.0)
            if confidence >= 0.8:
                bg_color = theme["success"]
            elif confidence >= 0.5:
                bg_color = theme["warning"]
            else:
                bg_color = theme["danger"]
            self.confidence_badge.setStyleSheet(
                f"background: {bg_color}; color: white; padding: 4px 12px; border-radius: 12px; "
                f"font-weight: 600; font-size: 11px;"
            )

        # Update thumbnail panel
        if hasattr(self, "thumbnail_panel"):
            self.thumbnail_panel.apply_theme(self.dark_mode)
        # Update preview panel
        if hasattr(self, "preview_container"):
            self.preview_container.setStyleSheet(
                f"background: {theme['preview_bg']}; border: none;"
            )

        if hasattr(self, "large_preview"):
            self.large_preview.setStyleSheet(f"background: {theme['preview_bg']};")

        if hasattr(self, "page_label"):
            self.page_label.setStyleSheet(
                f"color: {theme['text_secondary']}; font-weight: 500; font-size: 12px;"
            )

        # Update metadata panel
        if hasattr(self, "metadata_scroll"):
            self.metadata_scroll.setStyleSheet(f"background: {theme['metadata_bg']};")

        # Update action bar
        if hasattr(self, "action_bar"):
            self.action_bar.setStyleSheet(f"background: {theme['bg_secondary']};")

        # Update action buttons with theme-aware colors
        if hasattr(self, "prev_btn"):
            self.prev_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background: {theme["button_bg"]};
                    color: {theme["button_text"]};
                    border: 1px solid {theme["border"]};
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {theme["bg_hover"]};
                    border-color: {theme["border_focus"]};
                }}
                QPushButton:disabled {{
                    background: {theme["bg_secondary"]};
                    color: {theme["text_disabled"]};
                }}
                """
            )

        if hasattr(self, "next_btn"):
            self.next_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background: {theme["button_bg"]};
                    color: {theme["button_text"]};
                    border: 1px solid {theme["border"]};
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {theme["bg_hover"]};
                    border-color: {theme["border_focus"]};
                }}
                QPushButton:disabled {{
                    background: {theme["bg_secondary"]};
                    color: {theme["text_disabled"]};
                }}
                """
            )

        if hasattr(self, "skip_btn"):
            self.skip_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background: {theme["warning"]};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {theme["warning_hover"]};
                }}
                """
            )

        if hasattr(self, "reject_btn"):
            self.reject_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background: {theme["danger"]};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {theme["danger_hover"]};
                }}
                """
            )

        if hasattr(self, "accept_btn"):
            self.accept_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background: {theme["success"]};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {theme["success_hover"]};
                }}
                """
            )

        # Update metadata panel background
        if hasattr(self, "metadata_panel"):
            self.metadata_panel.setStyleSheet(f"background: {theme['metadata_bg']};")

        # Force widget update
        self.update()

        # Refresh visual components
        self._populate_thumbnails()
        self._display_current_page()

        # Update accordion sections styling
        if hasattr(self, "accordion_sections"):
            for section in self.accordion_sections:
                # Update accordion header
                header = section.findChild(QFrame)
                if header:
                    header.setStyleSheet(f"""
                        QFrame {{
                            background-color: {theme["bg_tertiary"]};
                            border: none;
                            border-radius: 4px;
                            padding: 6px 10px;
                        }}
                        QFrame:hover {{
                            background-color: {theme["bg_hover"]};
                        }}
                    """)

                # Update toggle indicator color
                toggle = section.findChild(QLabel, "accordion_toggle")
                if toggle:
                    toggle.setStyleSheet(
                        f"color: {theme['text_secondary']}; font-size: 9px; border: none;"
                    )

                # Update title label colors
                labels = section.findChildren(QLabel)
                for label in labels:
                    if label.objectName() != "accordion_toggle":
                        label.setStyleSheet(
                            f"color: {theme['text_primary']}; font-weight: 600; font-size: 12px; border: none;"
                        )
                        break

                # Update content scroll area
                scroll = section.findChild(QScrollArea, "accordion_content")
                if scroll:
                    scroll.setStyleSheet(f"""
                        QScrollArea {{
                            background-color: {theme["bg_secondary"]};
                            border: none;
                        }}
                    """)

                    # Update content container and viewport
                    container = scroll.widget()
                    if container:
                        container.setStyleSheet(f"background: {theme['bg_secondary']};")

                    # Update viewport explicitly
                    viewport = scroll.viewport()
                    if viewport:
                        viewport.setStyleSheet(f"background: {theme['bg_secondary']};")

            # Refresh accordion content forms
            self._refresh_accordion_content()

        # Update output filename section if it exists (with prominent styling)
        if hasattr(self, "output_filename_input"):
            # Find the parent section widget
            output_section = self.output_filename_input.parent()
            if output_section:
                # Use highlighted background to make it stand out
                highlight_bg = theme["info"] if self.dark_mode else "#e0f2fe"
                output_section.setStyleSheet(f"background: {highlight_bg}; border-radius: 6px;")
                output_section.setMinimumHeight(90)
                output_section.setMaximumHeight(90)

                # Update label colors (with prominent styling)
                label_color = "white" if self.dark_mode else "#0c4a6e"
                for label in output_section.findChildren(QLabel):
                    label.setStyleSheet(
                        f"color: {label_color}; font-weight: 700; font-size: 13px; background: transparent;"
                    )
                    label.setMinimumHeight(24)
                    label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

                # Update textbox styling (larger, more prominent)
                input_bg = "#ffffff"
                input_text = "#111827"
                input_border = "#60a5fa" if self.dark_mode else "#3b82f6"

                self.output_filename_input.setStyleSheet(f"""
                    QLineEdit {{
                        background: {input_bg};
                        color: {input_text};
                        border: 2px solid {input_border};
                        border-radius: 6px;
                        padding: 10px 12px;
                        font-size: 14px;
                        font-weight: 600;
                    }}
                    QLineEdit:focus {{
                        border: 2px solid {theme["selected"]};
                        background: {input_bg};
                    }}
                """)

    def _enter_edit_mode(self):
        """Enter edit mode when metadata is changed."""
        if self.edit_mode:
            return  # Already in edit mode

        # Store original metadata values
        self.original_metadata = {}
        for field_name, input_widget in self.metadata_inputs.items():
            if isinstance(input_widget, QCheckBox):
                self.original_metadata[field_name] = input_widget.isChecked()
            elif isinstance(input_widget, QComboBox):
                self.original_metadata[field_name] = input_widget.currentText()
            elif isinstance(input_widget, QLineEdit):
                self.original_metadata[field_name] = input_widget.text()

        self.edit_mode = True

        # Disable thumbnail panel
        self.thumbnail_panel.setEnabled(False)

        # Disable action bar
        self.action_bar.setEnabled(False)

        # Disable accordion headers (prevent page switching)
        for section in self.accordion_sections:
            if hasattr(section, "accordion_header"):
                header = section.accordion_header
                header.setEnabled(False)
                header.setCursor(Qt.CursorShape.ForbiddenCursor)

        # Show Save/Cancel buttons
        if hasattr(self, "metadata_save_btn"):
            self.metadata_save_btn.setVisible(True)
        if hasattr(self, "metadata_cancel_btn"):
            self.metadata_cancel_btn.setVisible(True)

    def _on_save_metadata_changes(self):
        """Save metadata changes and exit edit mode."""
        # Changes are already in the input widgets, just exit edit mode
        self._exit_edit_mode()

        # Show confirmation
        QMessageBox.information(
            self,
            "Changes Saved",
            "Metadata changes saved for this page.\n\n"
            "Changes will be applied when you accept or save the bundle.",
        )

    def _on_cancel_metadata_changes(self):
        """Cancel metadata changes and revert to original values."""
        # Revert all fields to original values
        for field_name, original_value in self.original_metadata.items():
            if field_name in self.metadata_inputs:
                input_widget = self.metadata_inputs[field_name]

                # Temporarily disconnect signals to avoid triggering edit mode again
                if isinstance(input_widget, QCheckBox):
                    input_widget.blockSignals(True)
                    input_widget.setChecked(original_value)
                    input_widget.blockSignals(False)
                elif isinstance(input_widget, QComboBox):
                    input_widget.blockSignals(True)
                    input_widget.setCurrentText(original_value)
                    input_widget.blockSignals(False)
                elif isinstance(input_widget, QLineEdit):
                    input_widget.blockSignals(True)
                    input_widget.setText(original_value)
                    input_widget.blockSignals(False)

        self._exit_edit_mode()

    def _exit_edit_mode(self):
        """Exit edit mode and re-enable panels."""
        self.edit_mode = False
        self.original_metadata = {}

        # Re-enable thumbnail panel
        self.thumbnail_panel.setEnabled(True)

        # Re-enable action bar
        self.action_bar.setEnabled(True)

        # Re-enable accordion headers
        for section in self.accordion_sections:
            if hasattr(section, "accordion_header"):
                header = section.accordion_header
                header.setEnabled(True)
                header.setCursor(Qt.CursorShape.PointingHandCursor)

        # Hide Save/Cancel buttons
        if hasattr(self, "metadata_save_btn"):
            self.metadata_save_btn.setVisible(False)
        if hasattr(self, "metadata_cancel_btn"):
            self.metadata_cancel_btn.setVisible(False)

    def showEvent(self, event):  # noqa: N802
        """Handle first show - apply configured default zoom."""
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            # Apply user's configured default zoom mode instead of hardcoded fit_to_width
            QTimer.singleShot(200, self._apply_default_zoom)
