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
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.bundle.bundle_colors import get_bundle_colors
from ui.bundle.bundle_colors import hex_to_rgb as _hex_to_rgb_fn
from ui.bundle.bundle_metadata_panel import BundleMetadataPanel
from ui.bundle.bundle_pdf_converter import BundlePdfConverter
from ui.bundle.bundle_preview_panel import BundlePreviewPanel
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
        self.pan_offset = QPoint(0, 0)
        self.is_panning = False
        self.pan_start_pos = QPoint(0, 0)

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

        # Page reordering tracking
        self.page_order = []  # Will be initialized when loading bundle

        # Track first show
        self._first_show = True

        # Theme state - read from config (same key as settings window)
        if config_manager:
            theme = config_manager.get_setting("Theme", "theme", "light")
            self.dark_mode = theme == "dark"
        else:
            self.dark_mode = False

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
        self.preview_panel = BundlePreviewPanel(dark_mode=self.dark_mode, parent=self)
        content_layout.addWidget(self.preview_panel, stretch=1)

        # Right panel - Metadata (fixed width)
        self.metadata_panel = BundleMetadataPanel(dark_mode=self.dark_mode, parent=self)
        self.metadata_panel.setFixedWidth(380)
        self.metadata_panel.metadata_changed.connect(self._on_metadata_changed)
        self.metadata_panel.save_requested.connect(self._on_metadata_save)
        self.metadata_panel.cancel_requested.connect(self._on_metadata_cancel)
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
        self.preview_panel.reset_rotation()

        # Apply default zoom from config instead of hardcoded 100
        if self.default_zoom_mode == "custom_%":
            self.preview_panel.set_zoom(self.default_zoom_percent)
        else:
            self.preview_panel.set_zoom(100)  # Will be recalculated by fit methods

        self._update_header()
        self._populate_thumbnails()
        self._display_current_page()
        self.metadata_panel.load_bundle(bundle, self.page_order, 0, self.prototype_mode)

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

    def _display_current_page(self):
        """Create a pixmap for the current page and hand it to preview_panel."""
        bundle = self.bundles[self.current_bundle_index]
        file_paths = bundle.get("file_paths", [])

        if not file_paths or self.current_page_index >= len(self.page_order):
            return

        actual_index = self.page_order[self.current_page_index]
        file_path = file_paths[actual_index]

        if self.prototype_mode:
            pixmap = QPixmap(600, 800)
            base_color = QColor(220 + (actual_index * 10) % 30, 230, 245)
            pixmap.fill(base_color)
            painter = QPainter(pixmap)
            painter.drawText(
                pixmap.rect(),
                Qt.AlignmentFlag.AlignCenter,
                f"Page {actual_index + 1}\n\n(Mock Preview)",
            )
            painter.end()
        else:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                pixmap = QPixmap(600, 800)
                pixmap.fill(QColor(240, 240, 240))
                painter = QPainter(pixmap)
                painter.drawText(
                    pixmap.rect(),
                    Qt.AlignmentFlag.AlignCenter,
                    f"Page {actual_index + 1}\n\nFailed to load image:\n{file_path}",
                )
                painter.end()

        self.preview_panel.display_page(pixmap, self.current_page_index + 1, len(self.page_order))

    def _on_zoom_in(self):
        """Zoom in."""
        new_zoom = min(400, self.preview_panel.zoom_level + 25)
        self.zoom_spinner.setValue(new_zoom)

    def _on_zoom_out(self):
        """Zoom out."""
        new_zoom = max(25, self.preview_panel.zoom_level - 25)
        self.zoom_spinner.setValue(new_zoom)

    def _on_zoom_changed(self, value: int):
        """Propagate zoom change to the preview panel."""
        self.preview_panel.set_zoom(value)

    def _on_fit_width(self):
        """Fit image to preview panel width."""
        size = self.preview_panel.get_original_pixel_size(rotation_adjusted=True)
        if size is None:
            return
        image_width = size[0]
        container_width = self.preview_panel.get_container_size()[0] - 40
        if image_width > 0:
            zoom = max(25, min(400, int(container_width / image_width * 100)))
            self.zoom_spinner.setValue(zoom)

    def _on_fit_height(self):
        """Fit image to preview panel height."""
        size = self.preview_panel.get_original_pixel_size(rotation_adjusted=True)
        if size is None:
            return
        image_height = size[1]
        container_height = self.preview_panel.get_container_size()[1] - 100
        if image_height > 0:
            zoom = max(25, min(400, int(container_height / image_height * 100)))
            self.zoom_spinner.setValue(zoom)

    def _on_fit_window(self):
        """Fit image to preview panel (both width and height)."""
        size = self.preview_panel.get_original_pixel_size(rotation_adjusted=True)
        if size is None:
            return
        image_width, image_height = size
        container_width = self.preview_panel.get_container_size()[0] - 40
        container_height = self.preview_panel.get_container_size()[1] - 100
        if image_width > 0 and image_height > 0:
            zoom_w = int(container_width / image_width * 100)
            zoom_h = int(container_height / image_height * 100)
            zoom = max(25, min(400, min(zoom_w, zoom_h)))
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
            self.preview_panel.set_zoom(self.default_zoom_percent)

    def _on_rotate_ccw(self):
        """Rotate counter-clockwise."""
        self.preview_panel.rotate_ccw()

    def _on_rotate_cw(self):
        """Rotate clockwise."""
        self.preview_panel.rotate_cw()

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

        # Sanitize (preserve characters safe for filenames)
        name_without_ext = BundleMetadataPanel._sanitize_filename(name_without_ext)

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

        # Get metadata and output filename from panel
        metadata = self.metadata_panel.get_metadata()
        raw_filename = self.metadata_panel.get_output_filename().strip()
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
                bundle, metadata, ordered_paths, self.preview_panel.rotation_angle
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
                    self.metadata_panel.load_bundle(
                        bundle, self.page_order, self.current_page_index, self.prototype_mode
                    )

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
        if hasattr(self, "preview_panel"):
            self.preview_panel.apply_theme(self.dark_mode)
        # Update metadata panel
        if hasattr(self, "metadata_panel"):
            self.metadata_panel.apply_theme(self.dark_mode)

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

        # Force widget update
        self.update()

        # Refresh visual components
        self._populate_thumbnails()
        self._display_current_page()

    def _on_metadata_changed(self) -> None:
        """Disable cross-panel interaction while user is editing metadata."""
        self.thumbnail_panel.setEnabled(False)
        self.action_bar.setEnabled(False)

    def _on_metadata_save(self, metadata: dict) -> None:
        """Re-enable panels after metadata save."""
        self.thumbnail_panel.setEnabled(True)
        self.action_bar.setEnabled(True)
        QMessageBox.information(
            self,
            "Changes Saved",
            "Metadata changes saved for this page.\n\n"
            "Changes will be applied when you accept or save the bundle.",
        )

    def _on_metadata_cancel(self) -> None:
        """Re-enable panels after metadata cancel."""
        self.thumbnail_panel.setEnabled(True)
        self.action_bar.setEnabled(True)

    def showEvent(self, event):  # noqa: N802
        """Handle first show - apply configured default zoom."""
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            # Apply user's configured default zoom mode instead of hardcoded fit_to_width
            QTimer.singleShot(200, self._apply_default_zoom)
