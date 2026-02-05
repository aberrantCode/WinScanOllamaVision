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

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QPainter, QPixmap, QTransform
from PyQt6.QtWidgets import (
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_pages = []
        self.page_checkboxes = []
        self._init_ui()
        self._create_mock_pages()

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

    def __init__(self, bundle_data=None, prototype_mode=True, parent=None):
        super().__init__(parent)

        # State
        self.prototype_mode = prototype_mode
        self.bundle_data = bundle_data or self._create_mock_bundle()
        self.current_page_index = 0
        self.zoom_level = 100
        self.rotation_angle = 0
        self.pan_offset = QPoint(0, 0)
        self.layout_mode = "flow"
        self.is_panning = False
        self.pan_start_pos = QPoint(0, 0)

        # Tracking
        self.confirmed_pages = set()
        self.removed_pages = set()

        # Metadata inputs (for editing)
        self.metadata_inputs = {}

        # Accordion sections
        self.accordion_sections = []

        self._init_ui()
        self._load_bundle()

    def _init_ui(self):
        """Initialize UI with three-panel layout."""
        self.setWindowTitle("Review Bundle")
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
        left_panel = self._create_thumbnail_panel()
        left_panel.setMinimumWidth(250)
        left_panel.setMaximumWidth(400)
        splitter.addWidget(left_panel)

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
        action_bar = self._create_action_bar()
        main_layout.addWidget(action_bar)

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

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: white; }")

        self.thumbnail_container = QWidget()
        self.thumbnail_container.setStyleSheet("background: white;")
        self.thumbnail_layout = QGridLayout(self.thumbnail_container)
        self.thumbnail_layout.setSpacing(8)
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

        # Preview label
        self.large_preview = QLabel()
        self.large_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
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

        header.mousePressEvent = lambda e: toggle()
        section_layout.addWidget(header)
        section_layout.addWidget(content_frame)

        self.accordion_sections.append(section)

        return section

    def _get_mock_distinct_values(self, field_name):
        """Get mock distinct values for prototype."""
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
        distinct_document_types = self._get_mock_distinct_values("document_type")
        distinct_companies = self._get_mock_distinct_values("company")

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
        add_editable_row(
            "Rotation Needed",
            "rotation_needed",
            analysis.get("rotation_needed", "none"),
            "none, 90_cw, 90_ccw, 180",
            widget_type="dropdown",
        )

        # Confidence score (as percentage)
        confidence = analysis.get("confidence_score", "")
        confidence_display = (
            f"{int(confidence * 100)}" if isinstance(confidence, float) else str(confidence)
        )
        add_editable_row(
            "Confidence Score", "confidence_score", confidence_display, "0-100 percentage"
        )

        # Tax related checkbox
        add_editable_row(
            "Tax Related", "tax_related", analysis.get("tax_related", False), widget_type="checkbox"
        )

        return widget

    def _create_file_info_content(self):
        """Create file information content (matching file_details_grid.py)."""
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
        else:
            filename = "N/A"
            full_path = "N/A"

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
        add_row("File Size", "N/A (mock)")  # Would use _format_size in real implementation
        add_row("Modified", "N/A (mock)")  # Would use _format_dt in real implementation
        add_row("File Hash", "N/A (mock)")  # Would be actual hash in real implementation

        return widget

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
        add_row("Analyzed", "N/A (mock)")  # Would show timestamp in real implementation
        add_row("Processing Time", "N/A (mock)")  # Would show duration in real implementation
        add_row("Provider", analysis.get("provider", "Ollama (mock)"))
        add_row("Model", analysis.get("model_used", "qwen2.5-vl (mock)"))
        add_row("Cached", "No" if self.current_page_index == 0 else "Yes")

        return widget

    def _create_action_bar(self) -> QWidget:
        """Create horizontal action bar at bottom."""
        bar = QWidget()
        bar.setStyleSheet(f"background: {Colors.GRAY_50}; border-top: 2px solid {Colors.GRAY_300};")

        # Buttons are 40px min-height + 12px padding (top/bottom) = need at least 64px
        # Add 15px padding top and bottom = 64 + 30 = 94px total
        bar.setMinimumHeight(94)
        bar.setMaximumHeight(94)

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
        pixmap = QPixmap(80, 100)
        base_color = QColor(220 + (index * 10) % 30, 230, 245)
        pixmap.fill(base_color)

        painter = QPainter(pixmap)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, f"Page\n{index + 1}")

        # Add checkmark if confirmed
        if index in self.confirmed_pages:
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
            tooltip = f"""
                <b>File:</b> {html.escape(Path(file_path).name)}<br>
                <b>Page:</b> {html.escape(str(analysis.get('page_number', '?')))} of {html.escape(str(analysis.get('total_pages', '?')))}<br>
                <b>Type:</b> {html.escape(str(analysis.get('document_type', 'Unknown')))}<br>
                <b>Confidence:</b> {int(analysis.get('confidence_score', 0) * 100)}%
            """
            thumbnail.setToolTip(tooltip)

        return thumbnail

    def _display_page(self, index: int):
        """Display page."""
        if index < 0 or index >= len(self.bundle_data.get("file_paths", [])):
            return

        self.current_page_index = index
        self.rotation_angle = 0
        self.pan_offset = QPoint(0, 0)

        self._update_large_preview()
        self._refresh_accordion_content()
        self._populate_thumbnails()

    def _update_large_preview(self):
        """Update preview with transforms and checkmark overlay."""
        if not self.bundle_data.get("file_paths"):
            return

        # Create base pixmap
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

        # Add checkmark overlay if confirmed
        if self.current_page_index in self.confirmed_pages:
            painter.setPen(QColor(Colors.SUCCESS))
            painter.setFont(QFont("Arial", 48, QFont.Weight.Bold))
            painter.drawText(20, 60, "✓")

        painter.end()

        # Apply transforms
        transformed = self._apply_transform(base_pixmap)

        self.large_preview.setPixmap(transformed)
        self._update_cursor()

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
        if self.zoom_level > 100 and not self.pan_offset.isNull():
            canvas = QPixmap(pixmap.size())
            canvas.fill(Qt.GlobalColor.white)
            painter = QPainter(canvas)
            painter.drawPixmap(self.pan_offset, pixmap)
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
                if content_frame:
                    # Get current content widget
                    old_widget = content_frame.layout().itemAt(0).widget()
                    new_widget = self._create_metadata_content()
                    content_frame.layout().replaceWidget(old_widget, new_widget)
                    old_widget.deleteLater()

            elif title_label and "File Information" in title_label.text():
                content_frame = section.findChild(QFrame, "accordion_content")
                if content_frame:
                    old_widget = content_frame.layout().itemAt(0).widget()
                    new_widget = self._create_file_info_content()
                    content_frame.layout().replaceWidget(old_widget, new_widget)
                    old_widget.deleteLater()

            elif title_label and "Analysis Information" in title_label.text():
                content_frame = section.findChild(QFrame, "accordion_content")
                if content_frame:
                    old_widget = content_frame.layout().itemAt(0).widget()
                    new_widget = self._create_analysis_content()
                    content_frame.layout().replaceWidget(old_widget, new_widget)
                    old_widget.deleteLater()

    def _update_cursor(self):
        """Update cursor."""
        if self.zoom_level > 100:
            self.large_preview.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        else:
            self.large_preview.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

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
        """Fit to width."""
        # Simplified for mock - set to reasonable zoom
        self.zoom_spinner.setValue(100)

    def _on_fit_height(self):
        """Fit to height."""
        # Simplified for mock - set to reasonable zoom
        self.zoom_spinner.setValue(75)

    def _on_fit_window(self):
        """Fit to window."""
        # Simplified for mock - set to fit both
        self.zoom_spinner.setValue(85)

    def mousePressEvent(self, event):
        """Start pan."""
        if self.zoom_level > 100 and event.button() == Qt.MouseButton.LeftButton:
            if self.large_preview.underMouse():
                self.is_panning = True
                self.pan_start_pos = event.pos()
                self.large_preview.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def mouseMoveEvent(self, event):
        """Update pan."""
        if self.is_panning:
            delta = event.pos() - self.pan_start_pos
            self.pan_offset += delta
            self.pan_start_pos = event.pos()
            self._update_large_preview()

    def mouseReleaseEvent(self, event):
        """End pan."""
        if self.is_panning:
            self.is_panning = False
            self._update_cursor()

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
        dialog = UnassignedPagesDialog(self)
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
        """Re-analyze."""
        QMessageBox.information(
            self, "Prototype Mode", "Re-analysis will be available when connected to backend."
        )

    def _on_save_bundle(self):
        """Save bundle."""
        # Save metadata edits (immutable pattern)
        if self.current_page_index < len(self.bundle_data.get("analyses", [])):
            # Collect all edits
            edits = {}
            for field_name, input_widget in self.metadata_inputs.items():
                # Get value based on widget type
                if isinstance(input_widget, QCheckBox):
                    value = input_widget.isChecked()
                elif isinstance(input_widget, QComboBox):
                    value = input_widget.currentText()
                else:  # QLineEdit or other text widgets
                    value = input_widget.text()
                edits[field_name] = value

            # Create new analyses list with updated analysis (immutable)
            new_analyses = []
            for i, analysis in enumerate(self.bundle_data["analyses"]):
                if i == self.current_page_index:
                    # Create new analysis dict with updates
                    new_analyses.append({**analysis, **edits})
                else:
                    new_analyses.append(analysis)

            # Update bundle_data immutably
            self.bundle_data = {
                **self.bundle_data,
                "analyses": new_analyses,
            }

        remaining_paths = [
            fp for i, fp in enumerate(self.bundle_data["file_paths"]) if i not in self.removed_pages
        ]

        result = {
            "bundle_id": self.bundle_data["bundle_id"],
            "file_paths": remaining_paths,
            "user_edits": {
                "removed_pages": list(self.removed_pages),
                "confirmed_pages": list(self.confirmed_pages),
            },
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
