"""
Bundle Review Window - Version 2 (Refactored based on user feedback)

Major improvements:
1. Fixed dropdown white-on-white text
2. Metadata panel uses accordions from file details viewer (editable)
3. Page actions moved to horizontal bottom bar
4. Fixed control button styling and positioning
5. Improved splitter behavior
6. Zoom/rotate controls overlaid on image
7. Fixed Add Pages dialog theme
8. Removed Delete Page button
9. Checkmark appears on main image when confirmed
10. Fixed gap when removing pages
11. Metadata fields are editable
"""

import html
from pathlib import Path
from typing import cast

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap, QTransform
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ui.bundle_widgets import ClickableLabel
from ui.pannable_image_label import PannableImageLabel
from ui.styles import (
    Colors,
    get_danger_button_style,
    get_primary_button_style,
    get_secondary_button_style,
    get_success_button_style,
)


class UnassignedPagesDialog(QDialog):
    """Dialog for selecting unassigned pages to add to bundle."""

    pages_selected = pyqtSignal(list)

    def __init__(self, bundle_id=None, analysis_db=None, prototype_mode=True, parent=None):
        super().__init__(parent)
        self.bundle_id = bundle_id
        self.analysis_db = analysis_db
        self.prototype_mode = prototype_mode
        self.selected_pages = []
        self.page_checkboxes = []
        self._init_ui()

        # Load pages based on mode
        if prototype_mode:
            self._create_mock_pages()
        else:
            self._load_unassigned_pages()

    def _init_ui(self):
        """Initialize dialog UI with light theme."""
        self.setWindowTitle("Add Pages to Bundle")
        self.setMinimumSize(800, 600)

        # Apply light theme
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Header
        header = QLabel("Select pages to add to this bundle:")
        header.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {Colors.GRAY_900};")
        layout.addWidget(header)

        # Scroll area for thumbnails
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"background: white; border: 1px solid {Colors.GRAY_200};")

        # Container for grid
        container = QWidget()
        container.setStyleSheet("background: white;")
        self.grid_layout = QGridLayout(container)
        self.grid_layout.setSpacing(10)
        scroll.setWidget(container)

        layout.addWidget(scroll)

        # Button bar
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.add_button = QPushButton("Add Selected (0)")
        self.add_button.setStyleSheet(get_success_button_style())
        self.add_button.setMinimumWidth(150)
        self.add_button.clicked.connect(self._on_add_selected)
        button_layout.addWidget(self.add_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet(get_secondary_button_style())
        cancel_button.setMinimumWidth(100)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def _create_mock_pages(self):
        """Create mock unassigned pages for prototype."""
        mock_pages = []
        for i in range(1, 13):
            mock_pages.append(
                {
                    "file_path": f"mock_unassigned_page_{i}.png",
                    "company": f"Company {chr(65 + (i % 5))}",
                    "document_type": ["Invoice", "Receipt", "Statement", "Contract"][i % 4],
                    "page_number": i,
                }
            )

        # Create thumbnails in 4-column grid
        for idx, page in enumerate(mock_pages):
            row = idx // 4
            col = idx % 4

            # Create thumbnail container
            thumb_container = QWidget()
            thumb_container.setStyleSheet("background: white;")
            thumb_layout = QVBoxLayout(thumb_container)
            thumb_layout.setContentsMargins(5, 5, 5, 5)
            thumb_layout.setSpacing(5)

            # Checkbox
            checkbox = QCheckBox()
            checkbox.setProperty("file_path", page["file_path"])
            checkbox.stateChanged.connect(self._on_selection_changed)
            self.page_checkboxes.append(checkbox)
            thumb_layout.addWidget(checkbox, alignment=Qt.AlignmentFlag.AlignCenter)

            # Thumbnail (placeholder)
            pixmap = QPixmap(80, 100)
            pixmap.fill(QColor(200 + (idx * 5) % 50, 220, 240))
            painter = QPainter(pixmap)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, f"Page\n{i}")
            painter.end()

            thumb_label = QLabel()
            thumb_label.setPixmap(pixmap)
            thumb_label.setStyleSheet(f"border: 1px solid {Colors.GRAY_300}; background: white;")
            thumb_layout.addWidget(thumb_label)

            # Info label
            info_label = QLabel(f"{page['company']}\n{page['document_type']}")
            info_label.setStyleSheet(f"font-size: 10px; color: {Colors.GRAY_600};")
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb_layout.addWidget(info_label)

            self.grid_layout.addWidget(thumb_container, row, col)

    def _load_unassigned_pages(self):
        """Load real unassigned pages from database."""
        import json
        import os

        if not self.analysis_db:
            QMessageBox.warning(
                self, "Error", "Database not available. Cannot load unassigned pages."
            )
            self.reject()
            return

        # Get all analyzed pages
        all_pages = self.analysis_db.get_analyzed_pages()

        # Get all bundles to find which pages are assigned
        all_bundles = self.analysis_db.get_bundle_suggestions()

        # Collect assigned file paths
        assigned_paths = set()
        for bundle in all_bundles:
            if bundle["status"] in ["suggested", "accepted", "modified"]:
                # Parse file_paths from JSON if needed
                file_paths = bundle.get("file_paths", [])
                if isinstance(file_paths, str):
                    file_paths = json.loads(file_paths)
                assigned_paths.update(file_paths)

        # Filter to unassigned pages
        unassigned_pages = [page for page in all_pages if page["file_path"] not in assigned_paths]

        if not unassigned_pages:
            # Show message and close
            QMessageBox.information(
                self, "No Unassigned Pages", "All analyzed pages are already assigned to bundles."
            )
            self.reject()
            return

        # Create thumbnails in 4-column grid
        for idx, page in enumerate(unassigned_pages):
            row = idx // 4
            col = idx % 4

            # Create thumbnail container
            thumb_container = QWidget()
            thumb_container.setStyleSheet("background: white;")
            thumb_layout = QVBoxLayout(thumb_container)
            thumb_layout.setContentsMargins(5, 5, 5, 5)
            thumb_layout.setSpacing(5)

            # Checkbox
            checkbox = QCheckBox()
            checkbox.setProperty("file_path", page["file_path"])
            checkbox.stateChanged.connect(self._on_selection_changed)
            self.page_checkboxes.append(checkbox)
            thumb_layout.addWidget(checkbox, alignment=Qt.AlignmentFlag.AlignCenter)

            # Thumbnail (real image)
            file_path = page["file_path"]
            if os.path.exists(file_path):
                full_pixmap = QPixmap(file_path)
                if not full_pixmap.isNull():
                    pixmap = full_pixmap.scaled(
                        80,
                        100,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                else:
                    # Placeholder for invalid image
                    pixmap = QPixmap(80, 100)
                    pixmap.fill(QColor(240, 240, 240))
                    painter = QPainter(pixmap)
                    painter.setPen(QColor(150, 150, 150))
                    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Error")
                    painter.end()
            else:
                # Placeholder for missing file
                pixmap = QPixmap(80, 100)
                pixmap.fill(QColor(240, 240, 240))
                painter = QPainter(pixmap)
                painter.setPen(QColor(150, 150, 150))
                painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Missing")
                painter.end()

            thumb_label = QLabel()
            thumb_label.setPixmap(pixmap)
            thumb_label.setStyleSheet(f"border: 1px solid {Colors.GRAY_300}; background: white;")
            thumb_layout.addWidget(thumb_label)

            # Info label
            company = page.get("company", "Unknown")
            doc_type = page.get("document_type", "Unknown")
            info_label = QLabel(f"{company}\n{doc_type}")
            info_label.setStyleSheet(f"font-size: 10px; color: {Colors.GRAY_600};")
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb_layout.addWidget(info_label)

            self.grid_layout.addWidget(thumb_container, row, col)

    def _on_selection_changed(self):
        """Update button text when selection changes."""
        selected_count = sum(1 for cb in self.page_checkboxes if cb.isChecked())
        self.add_button.setText(f"Add Selected ({selected_count})")
        self.add_button.setEnabled(selected_count > 0)

    def _on_add_selected(self):
        """Emit selected pages and close."""
        self.selected_pages = [
            cb.property("file_path") for cb in self.page_checkboxes if cb.isChecked()
        ]
        self.pages_selected.emit(self.selected_pages)
        self.accept()


class BundleReviewWindow(QDialog):
    """
    Bundle Review Window - Version 2

    Improvements:
    - Accordion panels for metadata (editable, like file details viewer)
    - Horizontal page actions bar at bottom
    - Overlaid zoom/rotate controls on image
    - Fixed splitter behavior
    - Checkmark on main image when confirmed
    - No gaps when removing pages
    """

    bundle_confirmed = pyqtSignal(dict)
    bundle_rejected = pyqtSignal(dict)

    def __init__(
        self,
        bundle_data=None,
        prototype_mode=True,
        analysis_db=None,
        metadata_db=None,
        config_manager=None,
        parent=None,
    ):
        super().__init__(parent)

        # Services
        self.analysis_db = analysis_db
        self.metadata_db = metadata_db
        self.config_manager = config_manager

        # State
        self.prototype_mode = prototype_mode

        # Load bundle data
        if bundle_data:
            self.bundle_data = bundle_data
        elif prototype_mode:
            self.bundle_data = self._create_mock_bundle()
        else:
            # Production mode requires database
            if not analysis_db:
                raise ValueError("analysis_db required when prototype_mode=False")
            # Will be loaded via _load_bundle_from_database if bundle_id provided
            self.bundle_data = None

        self.current_page_index = 0
        self.zoom_level = 100
        self.rotation_angle = 0
        self.layout_mode = "flow"

        # Tracking
        self.confirmed_pages = set()
        self.removed_pages = set()

        # Metadata inputs (for editing)
        self.metadata_inputs = {}

        # Edit mode tracking
        self.edit_mode = False
        self.original_metadata = {}

        # Accordion sections
        self.accordion_sections = []

        # Track first show for default zoom
        self._first_show = True

        self._init_ui()
        self._load_bundle()

    def _init_ui(self):
        """Initialize UI with three-panel layout."""
        self.setWindowTitle("Modify Bundle")
        self.setMinimumSize(1400, 900)
        self.resize(1400, 900)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header = self._create_header_bar()
        main_layout.addWidget(header)

        # Splitter with three panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {Colors.GRAY_300};
            }}
            QSplitter::handle:hover {{
                background-color: {Colors.PRIMARY};
            }}
        """)

        # Left panel - Thumbnails (300px)
        self.thumbnail_panel = self._create_thumbnail_panel()
        self.thumbnail_panel.setMinimumWidth(250)
        self.thumbnail_panel.setMaximumWidth(400)
        splitter.addWidget(self.thumbnail_panel)

        # Center panel - Large preview (flexible)
        center_panel = self._create_large_preview()
        splitter.addWidget(center_panel)

        # Right panel - Accordion metadata (350px)
        right_panel = self._create_accordion_panel()
        right_panel.setMinimumWidth(300)
        right_panel.setMaximumWidth(450)
        splitter.addWidget(right_panel)

        # Set sizes
        splitter.setSizes([300, 750, 350])

        main_layout.addWidget(splitter)

        # Bottom action bar (horizontal)
        self.action_bar = self._create_action_bar()
        main_layout.addWidget(self.action_bar)

    def _create_header_bar(self) -> QWidget:
        """Create header bar."""
        header = QWidget()
        header.setStyleSheet(
            f"background: {Colors.GRAY_50}; border-bottom: 1px solid {Colors.GRAY_200};"
        )
        header.setFixedHeight(60)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(15, 10, 15, 10)

        # Title
        doc_type = self.bundle_data.get("document_type", "Unknown")
        company = self.bundle_data.get("company", "Unknown")
        title = QLabel(f"Review Bundle: {doc_type} - {company}")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {Colors.GRAY_900};")
        layout.addWidget(title)

        layout.addStretch()

        # Confidence badge
        confidence = self.bundle_data.get("confidence_score", 0.0)
        confidence_pct = int(confidence * 100)

        if confidence >= 0.8:
            badge_color = Colors.SUCCESS
        elif confidence >= 0.5:
            badge_color = "#F59E0B"
        else:
            badge_color = Colors.DANGER

        confidence_badge = QLabel(f"Confidence: {confidence_pct}%")
        confidence_badge.setStyleSheet(f"""
            background: {badge_color};
            color: white;
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 13px;
        """)
        layout.addWidget(confidence_badge)

        # Page count
        total_pages = len(
            [
                i
                for i in range(len(self.bundle_data.get("file_paths", [])))
                if i not in self.removed_pages
            ]
        )
        page_count = QLabel(f"{total_pages} pages")
        page_count.setStyleSheet(f"color: {Colors.GRAY_600}; font-size: 13px; margin-left: 10px;")
        layout.addWidget(page_count)

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {Colors.GRAY_600};
                font-size: 20px;
                padding: 5px 10px;
            }}
            QPushButton:hover {{
                background: {Colors.GRAY_200};
                border-radius: 4px;
            }}
        """)
        close_btn.setFixedSize(40, 40)
        close_btn.clicked.connect(self._on_reject_bundle)
        layout.addWidget(close_btn)

        return header

    def _create_thumbnail_panel(self) -> QWidget:
        """Create left panel with thumbnails."""
        panel = QWidget()
        panel.setStyleSheet(f"background: white; border-right: 1px solid {Colors.GRAY_200};")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Layout selector
        selector_label = QLabel("Layout:")
        selector_label.setStyleSheet(
            f"font-weight: 600; color: {Colors.GRAY_700}; font-size: 12px;"
        )
        layout.addWidget(selector_label)

        self.layout_selector = QComboBox()
        self.layout_selector.addItems(["Flow Layout", "4-Column Grid", "Vertical List"])
        self.layout_selector.setStyleSheet(f"""
            QComboBox {{
                padding: 6px;
                border: 1px solid {Colors.GRAY_300};
                border-radius: 4px;
                background: white;
                color: {Colors.GRAY_900};
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background: white;
                color: {Colors.GRAY_900};
                selection-background-color: {Colors.PRIMARY_PALE};
                selection-color: {Colors.GRAY_900};
            }}
        """)
        self.layout_selector.currentTextChanged.connect(self._on_layout_changed)
        layout.addWidget(self.layout_selector)

        # No additional widgets between layout selector and thumbnail scroll area
        # The center panel handles the large preview - nothing should be here

        # Scroll area for thumbnails
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: white; }")

        self.thumbnail_container = QWidget()
        self.thumbnail_container.setStyleSheet("background: white;")
        self.thumbnail_layout = QGridLayout(self.thumbnail_container)
        self.thumbnail_layout.setSpacing(8)
        self.thumbnail_layout.setContentsMargins(0, 0, 0, 0)  # Remove any default margins
        scroll.setWidget(self.thumbnail_container)

        layout.addWidget(scroll)

        return panel

    def _create_large_preview(self) -> QWidget:
        """Create center panel with image and overlaid controls."""
        panel = QWidget()
        panel.setStyleSheet("background: white;")

        # Use stacking layout
        stack_layout = QVBoxLayout(panel)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.setSpacing(0)

        # Preview container with overlay controls
        preview_container = QWidget()
        preview_container.setStyleSheet("background: white;")
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(15, 15, 15, 15)

        # Image display area (with overlay controls)
        image_area = QWidget()
        image_area.setMinimumSize(600, 500)
        image_layout = QVBoxLayout(image_area)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(0)

        # Preview label with panning support
        self.large_preview = PannableImageLabel()
        self.large_preview.set_zoom_level(self.zoom_level)  # Initialize zoom level
        self.large_preview.setStyleSheet(
            f"background: white; border: 2px solid {Colors.GRAY_200}; border-radius: 4px;"
        )
        image_layout.addWidget(self.large_preview)

        # Overlay controls (positioned absolutely)
        self.overlay_controls = self._create_overlay_controls()
        self.overlay_controls.setParent(image_area)
        self.overlay_controls.move(10, 10)  # Top-left corner

        preview_layout.addWidget(image_area)
        stack_layout.addWidget(preview_container)

        return panel

    def _create_overlay_controls(self) -> QWidget:
        """Create compact overlaid zoom/rotate controls with tooltips."""
        controls = QWidget()
        controls.setStyleSheet(f"""
            QWidget {{
                background: rgba(255, 255, 255, 240);
                border: 1px solid {Colors.GRAY_300};
                border-radius: 4px;
            }}
        """)

        layout = QHBoxLayout(controls)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        layout.setSizeConstraint(QHBoxLayout.SizeConstraint.SetFixedSize)  # Shrink to fit content

        # Ultra-compact button style
        btn_style = f"""
            QPushButton {{
                background: {Colors.GRAY_100};
                color: {Colors.GRAY_900};
                border: 1px solid {Colors.GRAY_300};
                border-radius: 2px;
                font-size: 10px;
                font-weight: bold;
                min-width: 20px;
                max-width: 20px;
                min-height: 20px;
                max-height: 20px;
            }}
            QPushButton:hover {{
                background: {Colors.PRIMARY_PALE};
                border-color: {Colors.PRIMARY};
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
        self.zoom_spinner.setFixedWidth(55)
        self.zoom_spinner.setFixedHeight(20)
        self.zoom_spinner.setToolTip("Zoom Level (25-400%)")
        self.zoom_spinner.setStyleSheet(f"""
            QSpinBox {{
                background: white;
                color: {Colors.GRAY_900};
                border: 1px solid {Colors.GRAY_300};
                border-radius: 2px;
                padding: 1px;
                font-size: 10px;
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
        sep.setStyleSheet(f"background: {Colors.GRAY_300};")
        sep.setFixedWidth(1)
        sep.setFixedHeight(20)
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

    def _create_accordion_panel(self) -> QWidget:
        """Create right panel with accordion sections (like file details viewer)."""
        panel = QWidget()
        panel.setStyleSheet(f"background: white; border-left: 1px solid {Colors.GRAY_200};")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: white; }")

        # Container
        container = QWidget()
        container.setStyleSheet("background: white;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(15, 15, 15, 15)
        container_layout.setSpacing(12)

        # Extracted Metadata (editable)
        metadata_section = self._create_accordion_section(
            "📋 Extracted Metadata", self._create_metadata_content(), initially_expanded=True
        )
        container_layout.addWidget(metadata_section)

        # File Information
        file_info_section = self._create_accordion_section(
            "📄 File Information", self._create_file_info_content()
        )
        container_layout.addWidget(file_info_section)

        # Analysis Information
        analysis_section = self._create_accordion_section(
            "⚙️ Analysis Information", self._create_analysis_content()
        )
        container_layout.addWidget(analysis_section)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        return panel

    def _create_accordion_section(
        self, title: str, content_widget, initially_expanded: bool = False
    ):
        """Create collapsible accordion section (matching file_details_grid.py)."""
        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(0)

        # Theme colors (light mode)
        theme_colors = {
            "bg_primary": "#FFFFFF",
            "bg_secondary": "#F9FAFB",
            "text_primary": "#111827",
            "text_secondary": "#374151",
            "border": "#E5E7EB",
        }

        # Header
        header = QFrame()
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {theme_colors["bg_primary"]};
                border: 1px solid {theme_colors["border"]};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 12px;
            }}
            QFrame:hover {{
                background-color: {theme_colors["bg_secondary"]};
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        toggle_indicator = QLabel("▼" if initially_expanded else "▶")
        toggle_indicator.setObjectName("accordion_toggle")
        toggle_indicator.setStyleSheet(
            f"color: {theme_colors['text_secondary']}; font-size: 10pt; background: transparent; border: none;"
        )
        header_layout.addWidget(toggle_indicator)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {theme_colors['text_primary']}; font-weight: 600; font-size: 11pt; background: transparent; border: none;"
        )
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        # Content
        content_frame = QFrame()
        content_frame.setObjectName("accordion_content")
        content_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {theme_colors["bg_secondary"]};
                border: 1px solid {theme_colors["border"]};
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
            # Prevent toggling when in edit mode
            if self.edit_mode:
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.information(
                    self,
                    "Unsaved Changes",
                    "Please save or cancel your metadata changes before switching pages.",
                    QMessageBox.StandardButton.Ok,
                )
                return

            is_visible = content_frame.isVisible()

            # Collapse others
            if not is_visible:
                for other_section in self.accordion_sections:
                    if other_section != section:
                        other_content = other_section.findChild(QFrame, "accordion_content")
                        other_toggle = other_section.findChild(QLabel, "accordion_toggle")
                        if other_content:
                            other_content.setVisible(False)
                        if other_toggle:
                            other_toggle.setText("▶")

            # Toggle this
            content_frame.setVisible(not is_visible)
            toggle_indicator.setText("▶" if is_visible else "▼")

        # Store header reference for disabling later
        section.accordion_header = header  # type: ignore[attr-defined]

        header.mousePressEvent = lambda e: toggle()  # type: ignore[method-assign,assignment]
        section_layout.addWidget(header)
        section_layout.addWidget(content_frame)

        self.accordion_sections.append(section)

        return section

    def _get_distinct_values(self, field_name: str) -> list[str]:
        """Get distinct values for dropdown suggestions."""
        # In prototype mode, use mocks
        if self.prototype_mode:
            if field_name == "document_type":
                return [
                    "Invoice",
                    "Receipt",
                    "Statement",
                    "Contract",
                    "Purchase Order",
                    "Bill of Lading",
                ]
            elif field_name == "company":
                return [
                    "Acme Corporation",
                    "TechCorp Industries",
                    "Global Shipping Co",
                    "ABC Manufacturing",
                    "XYZ Logistics",
                ]
            return []

        # Production mode: query database
        if not self.metadata_db:
            return []

        if field_name == "document_type":
            return cast(list[str], self.metadata_db.get_unique_titles(use_cache=True))
        elif field_name == "company":
            return cast(list[str], self.metadata_db.get_unique_companies(use_cache=True))

        return []

    def _create_metadata_content(self):
        """Create editable metadata content (matching file_details_grid.py)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Get current page analysis
        if self.current_page_index < len(self.bundle_data.get("analyses", [])):
            analysis = self.bundle_data["analyses"][self.current_page_index]
        else:
            analysis = {}

        # Theme colors (light mode)
        theme_colors = {
            "bg_primary": "#FFFFFF",
            "bg_secondary": "#F9FAFB",
            "text_primary": "#111827",
            "text_secondary": "#374151",
            "border": "#E5E7EB",
            "accent": "#3B82F6",
        }

        def add_editable_row(
            label,
            field_name,
            current_value,
            placeholder="",
            widget_type="text",
            distinct_values=None,
        ):
            """Add editable field row (matching file details viewer)."""
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            lbl = QLabel(f"<b>{label}:</b>")
            lbl.setStyleSheet(
                f"color: {theme_colors['text_secondary']}; background: transparent; border: none;"
            )
            lbl.setMinimumWidth(130)
            row_layout.addWidget(lbl)

            if widget_type == "checkbox":
                input_widget = QCheckBox()
                if isinstance(current_value, bool):
                    input_widget.setChecked(current_value)
                else:
                    input_widget.setChecked(False)
                input_widget.setStyleSheet(f"""
                    QCheckBox {{
                        background: transparent;
                        color: {theme_colors["text_primary"]};
                        spacing: 5px;
                    }}
                    QCheckBox::indicator {{
                        width: 18px;
                        height: 18px;
                        border: 1px solid {theme_colors["border"]};
                        border-radius: 3px;
                        background-color: {theme_colors["bg_primary"]};
                    }}
                    QCheckBox::indicator:checked {{
                        background-color: {theme_colors["accent"]};
                        border-color: {theme_colors["accent"]};
                    }}
                    QCheckBox::indicator:hover {{
                        border-color: {theme_colors["accent"]};
                    }}
                """)
            elif widget_type == "dropdown":
                input_widget = QComboBox()
                input_widget.setEditable(False)
                input_widget.addItems(["none", "90_cw", "90_ccw", "180"])
                if current_value and current_value in ["none", "90_cw", "90_ccw", "180"]:
                    input_widget.setCurrentText(current_value)
                input_widget.setStyleSheet(f"""
                    QComboBox {{
                        background-color: {theme_colors["bg_primary"]};
                        color: {theme_colors["text_primary"]};
                        border: 1px solid {theme_colors["border"]};
                        border-radius: 4px;
                        padding: 4px 8px;
                    }}
                    QComboBox:focus {{
                        border: 1px solid {theme_colors["accent"]};
                    }}
                    QComboBox::drop-down {{
                        border: none;
                    }}
                    QComboBox QAbstractItemView {{
                        background-color: {theme_colors["bg_primary"]};
                        color: {theme_colors["text_primary"]};
                        selection-background-color: {theme_colors["accent"]};
                    }}
                """)
            elif widget_type == "editable_dropdown":
                input_widget = QComboBox()
                input_widget.setEditable(True)  # Allow typing new values

                # Add distinct values
                if distinct_values:
                    input_widget.addItems(sorted(distinct_values))

                # Set current value
                if current_value:
                    input_widget.setCurrentText(str(current_value))

                input_widget.setStyleSheet(f"""
                    QComboBox {{
                        background-color: {theme_colors["bg_primary"]};
                        color: {theme_colors["text_primary"]};
                        border: 1px solid {theme_colors["border"]};
                        border-radius: 4px;
                        padding: 4px 8px;
                    }}
                    QComboBox:focus {{
                        border: 1px solid {theme_colors["accent"]};
                    }}
                    QComboBox::drop-down {{
                        border: none;
                    }}
                    QComboBox QAbstractItemView {{
                        background-color: {theme_colors["bg_primary"]};
                        color: {theme_colors["text_primary"]};
                        selection-background-color: {theme_colors["accent"]};
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
                        background-color: {theme_colors["bg_primary"]};
                        color: {theme_colors["text_primary"]};
                        border: 1px solid {theme_colors["border"]};
                        border-radius: 4px;
                        padding: 4px 8px;
                    }}
                    QLineEdit:focus {{
                        border: 1px solid {theme_colors["accent"]};
                    }}
                """)

            row_layout.addWidget(input_widget, stretch=1)
            layout.addWidget(row)
            self.metadata_inputs[field_name] = input_widget

        # Get mock distinct values
        distinct_document_types = self._get_distinct_values("document_type")
        distinct_companies = self._get_distinct_values("company")

        # Add fields in correct order (matching file_details_grid.py)
        add_editable_row(
            "Document Type",
            "document_type",
            analysis.get("document_type"),
            "e.g., invoice, receipt, contract",
            widget_type="editable_dropdown",
            distinct_values=distinct_document_types,
        )
        add_editable_row(
            "Company",
            "company",
            analysis.get("company"),
            "Company or organization name",
            widget_type="editable_dropdown",
            distinct_values=distinct_companies,
        )
        add_editable_row(
            "Document Date",
            "document_date",
            self.bundle_data.get("document_date"),
            "YYYY-MM-DD format",
        )
        add_editable_row(
            "Page Number", "page_number", analysis.get("page_number"), "Current page number"
        )
        add_editable_row(
            "Total Pages", "total_pages", analysis.get("total_pages"), "Total number of pages"
        )
        # Get rotation - prioritize user-saved rotation from image_files table
        rotation_value = "none"
        file_path = analysis.get("file_path")
        if file_path:
            rotation_degrees = self.analysis_db.get_image_rotation(file_path)
            # Convert degrees to rotation_needed format
            rotation_value = {
                0: "none",
                90: "90_cw",
                270: "90_ccw",
                180: "180",
            }.get(rotation_degrees, "none")
            # Fall back to analysis_results if not set in image_files
            if rotation_degrees == 0 and analysis.get("rotation_needed"):
                rotation_value = analysis.get("rotation_needed", "none")

        add_editable_row(
            "Rotation Needed",
            "rotation_needed",
            rotation_value,
            "none, 90_cw, 90_ccw, 180",
            widget_type="dropdown",
        )

        # Confidence score (as percentage)
        confidence = analysis.get("confidence_score", 0.0)
        # Handle both decimal (0.95) and percentage (95) formats
        if isinstance(confidence, int | float):
            if confidence <= 1.0:
                # Decimal format (0.95) - convert to percentage
                confidence_display = f"{confidence * 100:.2f}"
            else:
                # Already in percentage format (95.0)
                confidence_display = f"{confidence:.2f}"
        else:
            confidence_display = "0.00"
        add_editable_row(
            "Confidence Score", "confidence_score", confidence_display, "0-100 percentage"
        )

        # Tax related checkbox
        add_editable_row(
            "Tax Related", "tax_related", analysis.get("tax_related", False), widget_type="checkbox"
        )

        # Add Save/Cancel buttons (initially hidden)
        layout.addSpacing(15)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.metadata_save_btn = QPushButton("Save Changes")
        self.metadata_save_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        self.metadata_save_btn.clicked.connect(self._on_save_metadata_changes)
        self.metadata_save_btn.setVisible(False)
        button_layout.addWidget(self.metadata_save_btn)

        self.metadata_cancel_btn = QPushButton("Cancel")
        self.metadata_cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6B7280;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4B5563;
            }
        """)
        self.metadata_cancel_btn.clicked.connect(self._on_cancel_metadata_changes)
        self.metadata_cancel_btn.setVisible(False)
        button_layout.addWidget(self.metadata_cancel_btn)

        layout.addLayout(button_layout)

        # Connect all metadata inputs to enter edit mode on change
        for _field_name, input_widget in self.metadata_inputs.items():
            if isinstance(input_widget, QCheckBox):
                input_widget.stateChanged.connect(lambda: self._enter_edit_mode())
            elif isinstance(input_widget, QComboBox):
                input_widget.currentTextChanged.connect(lambda: self._enter_edit_mode())
            elif isinstance(input_widget, QLineEdit):
                input_widget.textChanged.connect(lambda: self._enter_edit_mode())

        return widget

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
        self.thumbnail_panel.setStyleSheet(
            "QWidget { background: #F3F4F6; border-right: 1px solid #E5E7EB; }"
        )

        # Disable action bar
        self.action_bar.setEnabled(False)
        self.action_bar.setStyleSheet(
            "QWidget { background: #F3F4F6; border-top: 2px solid #E5E7EB; }"
        )

        # Disable accordion headers (prevent page switching)
        for section in self.accordion_sections:
            if hasattr(section, "accordion_header"):
                header = section.accordion_header
                header.setEnabled(False)
                header.setCursor(Qt.CursorShape.ForbiddenCursor)
                # Update header style to show disabled state
                header.setStyleSheet("""
                    QFrame {
                        background-color: #F3F4F6;
                        border: 1px solid #E5E7EB;
                        border-top-left-radius: 8px;
                        border-top-right-radius: 8px;
                        padding: 10px 12px;
                        opacity: 0.6;
                    }
                """)

        # Show Save/Cancel buttons
        if hasattr(self, "metadata_save_btn"):
            self.metadata_save_btn.setVisible(True)
        if hasattr(self, "metadata_cancel_btn"):
            self.metadata_cancel_btn.setVisible(True)

    def _on_save_metadata_changes(self):
        """Save metadata changes and exit edit mode."""
        # Check if bundle-level fields (company, document_type, document_date, document_category) changed
        bundle_level_fields = ["company", "document_type", "document_date", "document_category"]
        changed_bundle_fields = {}

        for field_name in bundle_level_fields:
            if field_name in self.metadata_inputs and field_name in self.original_metadata:
                input_widget = self.metadata_inputs[field_name]
                original_value = self.original_metadata[field_name]

                # Get current value based on widget type
                if isinstance(input_widget, QCheckBox):
                    current_value = input_widget.isChecked()
                elif isinstance(input_widget, QComboBox):
                    current_value = input_widget.currentText()
                elif isinstance(input_widget, QLineEdit):
                    current_value = input_widget.text()
                else:
                    current_value = original_value

                # Check if changed
                if current_value != original_value:
                    changed_bundle_fields[field_name] = current_value

        # If bundle-level fields changed, prompt user to apply to all pages
        apply_to_all = False
        if changed_bundle_fields:
            changed_field_names = ", ".join(changed_bundle_fields.keys())
            reply = QMessageBox.question(
                self,
                "Apply Changes to All Pages?",
                f"The following fields have changed: {changed_field_names}\n\n"
                f"Would you like to apply these changes to all pages in this bundle?\n\n"
                f"Note: Other field changes will only apply to the current page.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            apply_to_all = reply == QMessageBox.StandardButton.Yes

        # Apply changes to all pages if user confirmed
        if apply_to_all and changed_bundle_fields:
            # Update bundle-level data
            for field_name, new_value in changed_bundle_fields.items():
                self.bundle_data[field_name] = new_value

            # Update all analyses in the bundle (immutable pattern)
            new_analyses = []
            for analysis in self.bundle_data.get("analyses", []):
                new_analysis = dict(analysis)  # Create a copy
                for field_name, new_value in changed_bundle_fields.items():
                    new_analysis[field_name] = new_value
                new_analyses.append(new_analysis)

            self.bundle_data["analyses"] = new_analyses

            # Show confirmation
            QMessageBox.information(
                self,
                "Changes Applied",
                f"The fields ({', '.join(changed_bundle_fields.keys())}) have been applied to all pages.\n\n"
                f"Click 'Save Bundle' at the bottom to persist all changes to the database.",
            )
        else:
            # Just save to current page (changes are already in the input widgets)
            QMessageBox.information(
                self,
                "Changes Saved",
                "Metadata changes saved for this page.\n\n"
                "Click 'Save Bundle' at the bottom to persist all changes to the database.",
            )

        # Exit edit mode
        self._exit_edit_mode()

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
        self.thumbnail_panel.setStyleSheet(
            f"QWidget {{ background: white; border-right: 1px solid {Colors.GRAY_200}; }}"
        )

        # Re-enable action bar
        self.action_bar.setEnabled(True)
        self.action_bar.setStyleSheet(
            f"QWidget {{ background: {Colors.GRAY_50}; border-top: 2px solid {Colors.GRAY_300}; }}"
        )

        # Re-enable accordion headers
        for section in self.accordion_sections:
            if hasattr(section, "accordion_header"):
                header = section.accordion_header
                header.setEnabled(True)
                header.setCursor(Qt.CursorShape.PointingHandCursor)
                # Restore original header style
                header.setStyleSheet("""
                    QFrame {
                        background-color: #FFFFFF;
                        border: 1px solid #E5E7EB;
                        border-top-left-radius: 8px;
                        border-top-right-radius: 8px;
                        padding: 10px 12px;
                    }
                    QFrame:hover {
                        background-color: #F9FAFB;
                    }
                """)

        # Hide Save/Cancel buttons
        if hasattr(self, "metadata_save_btn"):
            self.metadata_save_btn.setVisible(False)
        if hasattr(self, "metadata_cancel_btn"):
            self.metadata_cancel_btn.setVisible(False)

    def _create_file_info_content(self):
        """Create file information content (matching file_details_grid.py)."""
        import os
        from datetime import datetime

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Theme colors
        theme_colors = {
            "bg_primary": "#FFFFFF",
            "text_primary": "#111827",
            "text_secondary": "#374151",
            "border": "#E5E7EB",
        }

        if self.current_page_index < len(self.bundle_data.get("file_paths", [])):
            file_path = self.bundle_data["file_paths"][self.current_page_index]
            filename = Path(file_path).name
            full_path = str(file_path)

            # Get real file stats
            if not self.prototype_mode and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                file_size_str = self._format_file_size(file_size)

                modified_time = os.path.getmtime(file_path)
                modified_str = datetime.fromtimestamp(modified_time).strftime(
                    "%Y-%m-%d %I:%M:%S %p"
                )

                # Get file hash from analysis
                if self.analysis_db:
                    analysis = self.analysis_db.get_analysis(file_path)
                    file_hash = analysis.get("file_hash", "N/A") if analysis else "N/A"
                else:
                    file_hash = "N/A"
            else:
                file_size_str = "N/A (mock)" if self.prototype_mode else "File not found"
                modified_str = "N/A (mock)" if self.prototype_mode else "N/A"
                file_hash = "N/A (mock)" if self.prototype_mode else "N/A"
        else:
            filename = "N/A"
            full_path = "N/A"
            file_size_str = "N/A"
            modified_str = "N/A"
            file_hash = "N/A"

        def add_row(label, value):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            lbl = QLabel(f"<b>{label}:</b>")
            lbl.setStyleSheet(
                f"color: {theme_colors['text_secondary']}; background: transparent; border: none;"
            )
            lbl.setMinimumWidth(120)
            row_layout.addWidget(lbl)

            val = QLabel(value)
            val.setStyleSheet(
                f"color: {theme_colors['text_primary']}; background: transparent; border: none;"
            )
            val.setWordWrap(True)
            val.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row_layout.addWidget(val, stretch=1)

            layout.addWidget(row)

        add_row("Filename", filename)
        add_row("Full Path", full_path)
        add_row("File Size", file_size_str)
        add_row("Modified", modified_str)
        # Truncate hash for display
        hash_display = (
            file_hash[:16] + "..." if len(file_hash) > 16 and file_hash != "N/A" else file_hash
        )
        add_row("File Hash", hash_display)

        return widget

    def _format_file_size(self, size_bytes: int | float) -> str:
        """Format file size in human-readable format."""
        size: float = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def _create_analysis_content(self):
        """Create analysis information content (matching file_details_grid.py)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Theme colors
        theme_colors = {
            "text_primary": "#111827",
            "text_secondary": "#374151",
        }

        if self.current_page_index < len(self.bundle_data.get("analyses", [])):
            analysis = self.bundle_data["analyses"][self.current_page_index]
        else:
            analysis = {}

        def add_row(label, value):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            lbl = QLabel(f"<b>{label}:</b>")
            lbl.setStyleSheet(
                f"color: {theme_colors['text_secondary']}; background: transparent; border: none;"
            )
            lbl.setMinimumWidth(120)
            row_layout.addWidget(lbl)

            val = QLabel(value)
            val.setStyleSheet(
                f"color: {theme_colors['text_primary']}; background: transparent; border: none;"
            )
            val.setWordWrap(True)
            val.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row_layout.addWidget(val, stretch=1)

            layout.addWidget(row)

        # Match file_details_grid.py fields
        status = "Confirmed" if self.current_page_index in self.confirmed_pages else "Pending"
        add_row("Status", status)

        # Get timestamps from analysis
        if not self.prototype_mode and analysis:
            from ui.datetime_utils import format_db_timestamp

            analyzed_timestamp = analysis.get("analyzed_at", "N/A")
            analyzed_str = format_db_timestamp(
                analyzed_timestamp if analyzed_timestamp != "N/A" else None, "%Y-%m-%d %I:%M:%S %p"
            )

            processing_time = analysis.get("processing_time_ms", 0)
            processing_str = f"{processing_time}ms" if processing_time else "N/A"

            provider = analysis.get("provider_name") or analysis.get("provider", "Unknown")
            model = analysis.get("model_used", "Unknown")

            # Check if cached (no processing time or very fast)
            is_cached = "Yes" if processing_time == 0 or processing_time < 10 else "No"
        else:
            analyzed_str = "N/A (mock)"
            processing_str = "N/A (mock)"
            provider = analysis.get("provider", "Ollama (mock)")
            model = analysis.get("model_used", "qwen2.5-vl (mock)")
            is_cached = "No" if self.current_page_index == 0 else "Yes"

        add_row("Analyzed", analyzed_str)
        add_row("Processing Time", processing_str)
        add_row("Provider", provider)
        add_row("Model", model)
        add_row("Cached", is_cached)

        return widget

    def _create_action_bar(self) -> QWidget:
        """Create horizontal action bar at bottom."""
        bar = QWidget()
        bar.setStyleSheet(f"background: {Colors.GRAY_50}; border-top: 2px solid {Colors.GRAY_300};")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(15, 15, 15, 15)  # Equal padding all around
        layout.setSpacing(12)

        # Left side - Page actions
        confirm_btn = QPushButton("✓ Confirm Page")
        confirm_btn.setStyleSheet(get_success_button_style())
        confirm_btn.clicked.connect(self._on_confirm_page)
        layout.addWidget(confirm_btn)

        remove_btn = QPushButton("Remove from Bundle")
        remove_btn.setStyleSheet(get_danger_button_style())
        remove_btn.clicked.connect(self._on_remove_page)
        layout.addWidget(remove_btn)

        add_pages_btn = QPushButton("Add Pages...")
        add_pages_btn.setStyleSheet(get_primary_button_style())
        add_pages_btn.clicked.connect(self._on_add_pages)
        layout.addWidget(add_pages_btn)

        save_copy_btn = QPushButton("Save Copy")
        save_copy_btn.setStyleSheet(get_secondary_button_style())
        save_copy_btn.clicked.connect(self._on_save_copy)
        layout.addWidget(save_copy_btn)

        reanalyze_btn = QPushButton("Re-Analyze")
        reanalyze_btn.setStyleSheet(get_secondary_button_style())
        reanalyze_btn.clicked.connect(self._on_reanalyze_page)
        layout.addWidget(reanalyze_btn)

        layout.addStretch()

        # Right side - Bundle actions
        save_bundle_btn = QPushButton("Save Bundle")
        save_bundle_btn.setStyleSheet(get_success_button_style())
        save_bundle_btn.setMinimumWidth(120)
        save_bundle_btn.clicked.connect(self._on_save_bundle)
        layout.addWidget(save_bundle_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(get_secondary_button_style())
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self._on_reject_bundle)
        layout.addWidget(cancel_btn)

        return bar

    def _create_mock_bundle(self) -> dict:
        """Create mock bundle."""
        file_paths = [f"mock_bundle_page_{i}.png" for i in range(1, 8)]

        return {
            "bundle_id": "mock_bundle_001",
            "file_paths": file_paths,
            "company": "Acme Corporation",
            "document_type": "Invoice",
            "document_date": "2024-03-15",
            "confidence_score": 0.87,
            "total_pages": len(file_paths),
            "analyses": [
                {
                    "file_path": fp,
                    "company": "Acme Corporation",
                    "document_type": "Invoice",
                    "page_number": i,
                    "total_pages": len(file_paths),
                    "confidence_score": 0.85 + (i * 0.02),
                    "legibility": "clear",
                    "rotation_needed": False,
                }
                for i, fp in enumerate(file_paths, 1)
            ],
        }

    def _load_bundle_from_database(self, bundle_id: int) -> dict:
        """Load bundle data from database."""
        import json

        from services.logging_service import get_logger

        logger = get_logger()

        # Get bundle metadata
        bundle = self.analysis_db.get_bundle_by_id(bundle_id)
        if not bundle:
            raise ValueError(f"Bundle {bundle_id} not found in database")

        # Parse file_paths from JSON string
        file_paths_str = bundle.get("file_paths", "[]")
        if isinstance(file_paths_str, str):
            file_paths = json.loads(file_paths_str)
        else:
            file_paths = file_paths_str

        logger.info(f"Loading bundle {bundle_id} with {len(file_paths)} files")

        # Load analyses for each page
        analyses = []
        missing_files = []

        for file_path in file_paths:
            analysis = self.analysis_db.get_analysis(file_path)
            if analysis:
                analyses.append(analysis)
            else:
                # Create placeholder if analysis missing
                logger.warning(f"No analysis found for {file_path}")
                analyses.append(
                    {
                        "file_path": file_path,
                        "company": bundle.get("company"),
                        "document_type": bundle.get("document_type"),
                        "page_number": None,
                        "total_pages": None,
                        "confidence_score": 0.0,
                        "error": "Analysis not found",
                    }
                )

            # Check if file exists
            import os

            if not os.path.exists(file_path):
                missing_files.append(file_path)

        if missing_files:
            logger.warning(
                f"Bundle {bundle_id} has {len(missing_files)} missing files: {missing_files[:3]}"
            )

        return {
            "bundle_id": bundle["id"],
            "file_paths": file_paths,
            "company": bundle.get("company"),
            "document_type": bundle.get("document_type"),
            "document_date": bundle.get("document_date"),
            "confidence_score": bundle.get("confidence_score", 0.0),
            "total_pages": len(file_paths),
            "analyses": analyses,
        }

    def _load_bundle(self):
        """Load bundle data."""
        self._populate_thumbnails()
        if self.bundle_data.get("file_paths"):
            self._display_page(0)

    def _populate_thumbnails(self):
        """Populate thumbnails (no gaps for removed pages)."""
        # Clear existing
        while self.thumbnail_layout.count():
            item = self.thumbnail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        file_paths = self.bundle_data.get("file_paths", [])
        visible_idx = 0

        for idx, file_path in enumerate(file_paths):
            if idx in self.removed_pages:
                continue

            thumbnail = self._create_thumbnail(file_path, idx)

            # Layout based on mode
            if self.layout_mode == "flow":
                row = visible_idx // 3
                col = visible_idx % 3
            elif self.layout_mode == "grid":
                row = visible_idx // 4
                col = visible_idx % 4
            else:  # list
                row = visible_idx
                col = 0

            self.thumbnail_layout.addWidget(thumbnail, row, col)
            visible_idx += 1

    def _create_thumbnail(self, file_path: str, index: int) -> ClickableLabel:
        """Create thumbnail."""
        import os

        # Load real image or create placeholder
        if self.prototype_mode:
            # Mock thumbnail
            pixmap = QPixmap(80, 100)
            base_color = QColor(220 + (index * 10) % 30, 230, 245)
            pixmap.fill(base_color)
            painter = QPainter(pixmap)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, f"Page\n{index + 1}")
            painter.end()
        elif os.path.exists(file_path):
            # Load and scale real image
            full_pixmap = QPixmap(file_path)
            if not full_pixmap.isNull():
                pixmap = full_pixmap.scaled(
                    80,
                    100,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            else:
                # Invalid image
                pixmap = QPixmap(80, 100)
                pixmap.fill(QColor(240, 240, 240))
                painter = QPainter(pixmap)
                painter.setPen(QColor(150, 150, 150))
                painter.setFont(QFont("Arial", 10))
                painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Error")
                painter.end()
        else:
            # File not found
            pixmap = QPixmap(80, 100)
            pixmap.fill(QColor(240, 240, 240))
            painter = QPainter(pixmap)
            painter.setPen(QColor(150, 150, 150))
            painter.setFont(QFont("Arial", 10))
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Missing")
            painter.end()

        # Add checkmark overlay if confirmed
        if index in self.confirmed_pages:
            painter = QPainter(pixmap)
            painter.setPen(QColor(Colors.SUCCESS))
            painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            painter.drawText(5, 20, "✓")
            painter.end()

        thumbnail = ClickableLabel()
        thumbnail.setPixmap(pixmap)
        thumbnail.setFixedSize(82, 102)

        # Selection border
        if index == self.current_page_index:
            border_color = Colors.PRIMARY
            border_width = 2
        else:
            border_color = Colors.GRAY_300
            border_width = 1

        thumbnail.setStyleSheet(f"""
            ClickableLabel {{
                border: {border_width}px solid {border_color};
                background: white;
            }}
            ClickableLabel:hover {{
                background: {Colors.PRIMARY_PALE};
            }}
        """)

        thumbnail.clicked.connect(lambda idx=index: self._on_thumbnail_clicked(idx))

        # Tooltip
        if index < len(self.bundle_data.get("analyses", [])):
            analysis = self.bundle_data["analyses"][index]
            # Format confidence score correctly
            conf = analysis.get("confidence_score", 0)
            if isinstance(conf, int | float):
                conf_pct = int(conf * 100) if conf <= 1.0 else int(conf)
            else:
                conf_pct = 0

            tooltip = f"""
                <b>File:</b> {html.escape(Path(file_path).name)}<br>
                <b>Page:</b> {html.escape(str(analysis.get('page_number', '?')))} of {html.escape(str(analysis.get('total_pages', '?')))}<br>
                <b>Type:</b> {html.escape(str(analysis.get('document_type', 'Unknown')))}<br>
                <b>Confidence:</b> {conf_pct}%
            """
            thumbnail.setToolTip(tooltip)

        return thumbnail

    def _display_page(self, index: int):
        """Display page."""
        if index < 0 or index >= len(self.bundle_data.get("file_paths", [])):
            return

        self.current_page_index = index
        self.rotation_angle = 0
        self.large_preview.reset_pan()

        self._update_large_preview()
        self._refresh_accordion_content()
        self._populate_thumbnails()

    def _update_large_preview(self):
        """Update preview with transforms and checkmark overlay."""
        import os

        if not self.bundle_data.get("file_paths"):
            return

        file_path = self.bundle_data["file_paths"][self.current_page_index]

        # Load real image or create placeholder
        if self.prototype_mode:
            # Mock pixmap for prototype
            base_pixmap = QPixmap(600, 800)
            color_idx = self.current_page_index
            base_color = QColor(220 + (color_idx * 10) % 30, 230, 245)
            base_pixmap.fill(base_color)

            painter = QPainter(base_pixmap)
            painter.drawText(
                base_pixmap.rect(),
                Qt.AlignmentFlag.AlignCenter,
                f"Page {self.current_page_index + 1}\n\n(Mock Preview)",
            )
            painter.end()
        elif os.path.exists(file_path):
            # Load real image
            base_pixmap = QPixmap(file_path)
            if base_pixmap.isNull():
                # Invalid image file
                base_pixmap = self._create_placeholder_pixmap(
                    f"Cannot load image:\n{os.path.basename(file_path)}"
                )
        else:
            # File not found
            base_pixmap = self._create_placeholder_pixmap(
                f"File not found:\n{os.path.basename(file_path)}"
            )

        # Add checkmark overlay if confirmed
        if self.current_page_index in self.confirmed_pages:
            painter = QPainter(base_pixmap)
            painter.setPen(QColor(Colors.SUCCESS))
            painter.setFont(QFont("Arial", 48, QFont.Weight.Bold))
            painter.drawText(20, 60, "✓")
            painter.end()

        # Apply transforms
        transformed = self._apply_transform(base_pixmap)

        self.large_preview.setPixmap(transformed)

    def _create_placeholder_pixmap(self, text: str) -> QPixmap:
        """Create placeholder pixmap with error text."""
        pixmap = QPixmap(600, 800)
        pixmap.fill(QColor(240, 240, 240))
        painter = QPainter(pixmap)
        painter.setPen(QColor(100, 100, 100))
        painter.setFont(QFont("Arial", 14))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()
        return pixmap

    def _apply_transform(self, pixmap: QPixmap) -> QPixmap:
        """Apply zoom, rotation, pan."""
        # Rotation
        if self.rotation_angle != 0:
            transform = QTransform()
            transform.rotate(self.rotation_angle)
            pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        # Zoom
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

        # Pan
        pan_offset = self.large_preview.get_pan_offset()
        if self.zoom_level > 100 and not pan_offset.isNull():
            canvas = QPixmap(pixmap.size())
            canvas.fill(Qt.GlobalColor.white)
            painter = QPainter(canvas)
            painter.drawPixmap(pan_offset, pixmap)
            painter.end()
            pixmap = canvas

        return pixmap

    def _refresh_accordion_content(self):
        """Refresh accordion sections when page changes."""
        # Find and update metadata section
        for section in self.accordion_sections:
            title_label = section.findChild(QLabel)
            if title_label and "Extracted Metadata" in title_label.text():
                # Update metadata inputs
                content_frame = section.findChild(QFrame, "accordion_content")
                if content_frame and content_frame.layout():
                    # Get current content widget with null check
                    item = content_frame.layout().itemAt(0)
                    if item:
                        old_widget = item.widget()
                        if old_widget:
                            new_widget = self._create_metadata_content()
                            content_frame.layout().replaceWidget(old_widget, new_widget)
                            old_widget.deleteLater()

            elif title_label and "File Information" in title_label.text():
                content_frame = section.findChild(QFrame, "accordion_content")
                if content_frame and content_frame.layout():
                    item = content_frame.layout().itemAt(0)
                    if item:
                        old_widget = item.widget()
                        if old_widget:
                            new_widget = self._create_file_info_content()
                            content_frame.layout().replaceWidget(old_widget, new_widget)
                            old_widget.deleteLater()

            elif title_label and "Analysis Information" in title_label.text():
                content_frame = section.findChild(QFrame, "accordion_content")
                if content_frame and content_frame.layout():
                    item = content_frame.layout().itemAt(0)
                    if item:
                        old_widget = item.widget()
                        if old_widget:
                            new_widget = self._create_analysis_content()
                            content_frame.layout().replaceWidget(old_widget, new_widget)
                            old_widget.deleteLater()

    # Event handlers
    def _on_thumbnail_clicked(self, index: int):
        """Handle thumbnail click."""
        self._display_page(index)

    def _on_layout_changed(self, layout_name: str):
        """Handle layout change."""
        if layout_name == "Flow Layout":
            self.layout_mode = "flow"
        elif layout_name == "4-Column Grid":
            self.layout_mode = "grid"
        else:
            self.layout_mode = "list"

        self._populate_thumbnails()

    def _on_zoom_in(self):
        """Zoom in."""
        new_zoom = min(400, self.zoom_level + 25)
        self.zoom_spinner.setValue(new_zoom)

    def _on_zoom_out(self):
        """Zoom out."""
        new_zoom = max(25, self.zoom_level - 25)
        self.zoom_spinner.setValue(new_zoom)

    def _on_zoom_percent_changed(self, value: int):
        """Handle zoom change."""
        self.zoom_level = value
        self.large_preview.set_zoom_level(value)
        self._update_large_preview()

    def _on_rotate_ccw(self):
        """Rotate CCW."""
        self.rotation_angle = (self.rotation_angle - 90) % 360
        self._update_large_preview()

    def _on_rotate_cw(self):
        """Rotate CW."""
        self.rotation_angle = (self.rotation_angle + 90) % 360
        self._update_large_preview()

    def _on_fit_width(self):
        """Fit to width of preview area."""
        if not self.bundle_data.get("file_paths"):
            return

        file_path = self.bundle_data["file_paths"][self.current_page_index]

        # Get original image size
        import os

        if not self.prototype_mode and os.path.exists(file_path):
            pixmap = QPixmap(file_path)
        else:
            pixmap = QPixmap(600, 800)  # Mock size

        if pixmap.isNull():
            return

        # Apply rotation to get actual display dimensions
        if self.rotation_angle != 0:
            transform = QTransform()
            transform.rotate(self.rotation_angle)
            pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        # Get preview area width (subtract some margin)
        preview_width = self.large_preview.width() - 20

        # Calculate zoom to fit width
        zoom_percent = int((preview_width / pixmap.width()) * 100)
        zoom_percent = max(25, min(400, zoom_percent))  # Clamp to valid range

        self.zoom_spinner.setValue(zoom_percent)

    def _on_fit_height(self):
        """Fit to height of preview area."""
        if not self.bundle_data.get("file_paths"):
            return

        file_path = self.bundle_data["file_paths"][self.current_page_index]

        # Get original image size
        import os

        if not self.prototype_mode and os.path.exists(file_path):
            pixmap = QPixmap(file_path)
        else:
            pixmap = QPixmap(600, 800)  # Mock size

        if pixmap.isNull():
            return

        # Apply rotation to get actual display dimensions
        if self.rotation_angle != 0:
            transform = QTransform()
            transform.rotate(self.rotation_angle)
            pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        # Get preview area height (subtract some margin)
        preview_height = self.large_preview.height() - 20

        # Calculate zoom to fit height
        zoom_percent = int((preview_height / pixmap.height()) * 100)
        zoom_percent = max(25, min(400, zoom_percent))  # Clamp to valid range

        self.zoom_spinner.setValue(zoom_percent)

    def _on_fit_window(self):
        """Fit to window (both width and height)."""
        if not self.bundle_data.get("file_paths"):
            return

        file_path = self.bundle_data["file_paths"][self.current_page_index]

        # Get original image size
        import os

        if not self.prototype_mode and os.path.exists(file_path):
            pixmap = QPixmap(file_path)
        else:
            pixmap = QPixmap(600, 800)  # Mock size

        if pixmap.isNull():
            return

        # Apply rotation to get actual display dimensions
        if self.rotation_angle != 0:
            transform = QTransform()
            transform.rotate(self.rotation_angle)
            pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        # Get preview area dimensions (subtract margins)
        preview_width = self.large_preview.width() - 20
        preview_height = self.large_preview.height() - 20

        # Calculate zoom to fit both dimensions (use smaller ratio)
        width_ratio = preview_width / pixmap.width()
        height_ratio = preview_height / pixmap.height()
        zoom_ratio = min(width_ratio, height_ratio)
        zoom_percent = int(zoom_ratio * 100)
        zoom_percent = max(25, min(400, zoom_percent))  # Clamp to valid range

        self.zoom_spinner.setValue(zoom_percent)

    def showEvent(self, event):  # noqa: N802
        """Handle window show event - set default zoom to fit width on first show."""
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            # Use QTimer to ensure window geometry is finalized
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(100, self._on_fit_width)

    def _on_confirm_page(self):
        """Confirm page."""
        self.confirmed_pages.add(self.current_page_index)
        self._populate_thumbnails()
        self._update_large_preview()
        self._refresh_accordion_content()

        QMessageBox.information(
            self, "Page Confirmed", f"Page {self.current_page_index + 1} confirmed!"
        )

    def _on_remove_page(self):
        """Remove page."""
        reply = QMessageBox.question(
            self,
            "Remove Page",
            f"Remove page {self.current_page_index + 1} from this bundle?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.removed_pages.add(self.current_page_index)

            # Move to next visible page
            remaining = [
                i for i in range(len(self.bundle_data["file_paths"])) if i not in self.removed_pages
            ]
            if remaining:
                self._display_page(remaining[0])
            else:
                self.large_preview.clear()

            self._populate_thumbnails()

    def _on_add_pages(self):
        """Show add pages dialog."""
        dialog = UnassignedPagesDialog(
            bundle_id=self.bundle_data.get("bundle_id"),
            analysis_db=self.analysis_db,
            prototype_mode=self.prototype_mode,
            parent=self,
        )
        dialog.pages_selected.connect(self._on_pages_added)
        dialog.exec()

    def _on_pages_added(self, file_paths: list):
        """Handle pages added."""
        # Immutable update: create new lists instead of mutating
        current_paths = self.bundle_data["file_paths"]
        new_file_paths = current_paths + file_paths

        new_analyses = []
        for i, fp in enumerate(file_paths, len(current_paths) + 1):
            new_analyses.append(
                {
                    "file_path": fp,
                    "company": self.bundle_data["company"],
                    "document_type": self.bundle_data["document_type"],
                    "page_number": i,
                    "total_pages": len(new_file_paths),
                    "confidence_score": 0.75,
                    "legibility": "clear",
                    "rotation_needed": False,
                }
            )

        # Create new bundle_data dict with updated values
        self.bundle_data = {
            **self.bundle_data,
            "file_paths": new_file_paths,
            "analyses": self.bundle_data["analyses"] + new_analyses,
        }

        self._populate_thumbnails()

        QMessageBox.information(self, "Pages Added", f"Added {len(file_paths)} page(s) to bundle")

    def _on_save_copy(self):
        """Save copy."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Page Copy",
            f"page_{self.current_page_index + 1}.png",
            "PNG Images (*.png);;JPEG Images (*.jpg *.jpeg)",
        )

        if file_path:
            pixmap = self.large_preview.pixmap()
            if pixmap:
                pixmap.save(file_path)

                QMessageBox.information(self, "Page Saved", f"Page saved to:\n{file_path}")

    def _on_reanalyze_page(self):
        """Re-analyze current page using LLM provider."""
        from pathlib import Path

        if self.current_page_index >= len(self.bundle_data.get("file_paths", [])):
            return

        file_path = self.bundle_data["file_paths"][self.current_page_index]

        # In prototype mode, just show info
        if self.prototype_mode:
            QMessageBox.information(
                self, "Prototype Mode", "Re-analysis will be available when connected to backend."
            )
            return

        # Confirm action
        reply = QMessageBox.question(
            self,
            "Re-Analyze Page",
            f"Re-analyze this page using the current LLM provider?\n\n"
            f"File: {Path(file_path).name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Show progress dialog
        progress = QMessageBox(self)
        progress.setWindowTitle("Re-Analyzing")
        progress.setText("Analyzing page, please wait...")
        progress.setStandardButtons(QMessageBox.StandardButton.NoButton)
        progress.setModal(True)
        progress.show()
        QApplication.processEvents()

        try:
            # Get provider from config
            from llm_providers.provider_factory import ProviderFactory
            from services.analysis_service import AnalysisService

            provider = ProviderFactory.create_from_config_manager(self.config_manager)

            # Get prompt
            prompt = self.config_manager.get_setting(
                "Prompts", "document_metadata", AnalysisService.DEFAULT_ANALYSIS_PROMPT
            )

            # Analyze
            result = provider.analyze_images([file_path], prompt, model=None)

            if result["success"]:
                # Save to database
                file_hash = self.metadata_db.compute_file_hash(file_path)
                self.analysis_db.save_analysis(
                    file_path=file_path,
                    file_hash=file_hash,
                    provider_name=result["provider_name"],
                    model_name=result["model_used"],
                    analysis_data=result["metadata"],
                    raw_response=result["response"],
                    processing_time_ms=result["processing_time_ms"],
                    prompt_text=prompt,  # Save the prompt used for analysis
                )

                # Update bundle_data immutably
                new_analyses = list(self.bundle_data["analyses"])
                new_analyses[self.current_page_index] = {
                    **result["metadata"],
                    "file_path": file_path,
                    "provider_name": result["provider_name"],
                    "model_used": result["model_used"],
                    "processing_time_ms": result["processing_time_ms"],
                    "analyzed_at": result.get("analyzed_at"),
                }

                self.bundle_data = {
                    **self.bundle_data,
                    "analyses": new_analyses,
                }

                # Refresh UI
                self._refresh_accordion_content()

                progress.close()
                QMessageBox.information(
                    self, "Success", f"Page re-analyzed successfully using {result['model_used']}"
                )
            else:
                progress.close()
                QMessageBox.warning(
                    self,
                    "Analysis Failed",
                    f"Failed to re-analyze page:\n{result.get('error', 'Unknown error')}",
                )

        except Exception as e:
            progress.close()

            # Log error
            from services.logging_service import get_logger

            logger = get_logger()
            logger.error(f"Re-analysis failed for {file_path}", exc_info=True)

            # Save error to database
            self.analysis_db.save_analysis_error(
                file_path=file_path, error_message=str(e), error_type="re_analysis_failure"
            )

            QMessageBox.critical(
                self, "Error", f"Error during re-analysis:\n{str(e)}\n\nError has been logged."
            )

    def _on_save_bundle(self):
        """Save bundle changes to database."""
        # Collect metadata edits from current page
        if self.current_page_index < len(self.bundle_data.get("analyses", [])):
            edits = {}
            for field_name, input_widget in self.metadata_inputs.items():
                if isinstance(input_widget, QCheckBox):
                    value = input_widget.isChecked()
                elif isinstance(input_widget, QComboBox):
                    value = input_widget.currentText()
                else:
                    value = input_widget.text()
                edits[field_name] = value

            # Update all analyses with bundle-level fields (immutable pattern)
            bundle_level_fields = ["company", "document_type", "document_date", "document_category"]
            new_analyses = []
            for i, analysis in enumerate(self.bundle_data["analyses"]):
                new_analysis = {**analysis}
                if i == self.current_page_index:
                    # Apply all edits to current page
                    new_analysis.update(edits)
                else:
                    # Apply only bundle-level edits to other pages
                    for field in bundle_level_fields:
                        if field in edits:
                            new_analysis[field] = edits[field]
                new_analyses.append(new_analysis)

            # Update bundle_data immutably
            self.bundle_data = {
                **self.bundle_data,
                "analyses": new_analyses,
            }

        # Get final file paths (excluding removed)
        remaining_paths = [
            fp for i, fp in enumerate(self.bundle_data["file_paths"]) if i not in self.removed_pages
        ]

        if not remaining_paths:
            QMessageBox.warning(
                self,
                "No Pages",
                "Cannot save bundle with no pages. Please add pages or cancel.",
            )
            return

        # Save to database (only in production mode)
        if not self.prototype_mode:
            try:
                # Update each page's metadata in database
                for i, file_path in enumerate(self.bundle_data["file_paths"]):
                    if i in self.removed_pages:
                        continue

                    analysis = self.bundle_data["analyses"][i]
                    metadata_updates = {
                        "company": analysis.get("company"),
                        "document_type": analysis.get("document_type"),
                        "document_date": analysis.get("document_date"),
                        "page_number": analysis.get("page_number"),
                        "total_pages": len(remaining_paths),
                        "confidence_score": analysis.get("confidence_score"),
                        "tax_related": analysis.get("tax_related"),
                        "rotation_needed": analysis.get("rotation_needed"),
                    }

                    self.analysis_db.update_analysis_metadata(file_path, metadata_updates)

                    # Save rotation to image_files table
                    rotation_needed = metadata_updates.get("rotation_needed", "none")
                    rotation_degrees = {
                        "none": 0,
                        "90_cw": 90,
                        "90_ccw": 270,
                        "180": 180,
                    }.get(rotation_needed, 0)
                    self.analysis_db.update_image_rotation(file_path, rotation_degrees)

                # Update bundle status in database
                bundle_id = self.bundle_data["bundle_id"]

                # If file paths changed, update bundle
                if len(remaining_paths) != len(self.bundle_data["file_paths"]):
                    from services.bundling_service import BundlingService

                    bundling_service = BundlingService(self.analysis_db)
                    bundling_service.modify_bundle(bundle_id, remaining_paths)
                else:
                    # Just mark as accepted
                    from services.bundling_service import BundlingService

                    bundling_service = BundlingService(self.analysis_db)
                    bundling_service.accept_bundle(bundle_id)

            except Exception as e:
                QMessageBox.critical(
                    self, "Save Failed", f"Failed to save bundle changes:\n{str(e)}"
                )
                return

        # Emit success signal
        result = {
            "bundle_id": self.bundle_data["bundle_id"],
            "file_paths": remaining_paths,
            "user_edits": {
                "removed_pages": list(self.removed_pages),
                "confirmed_pages": list(self.confirmed_pages),
            },
            "status": "accepted",
        }

        self.bundle_confirmed.emit(result)
        self.accept()

    def _on_reject_bundle(self):
        """Reject bundle."""
        reply = QMessageBox.question(
            self,
            "Cancel Review",
            "Discard all changes to this bundle?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.bundle_rejected.emit(self.bundle_data)
            self.reject()
