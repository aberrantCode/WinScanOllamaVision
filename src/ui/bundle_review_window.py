"""
Bundle Review Window - Prototype Implementation

A dedicated window for reviewing and editing document bundles with:
- Thumbnail grid with multiple layout modes
- Large preview with zoom, rotation, and pan
- Page and bundle management actions
- Prototype mode with mock data for rapid iteration
"""

import html
from pathlib import Path

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QPainter, QPixmap, QTransform
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
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

    pages_selected = pyqtSignal(list)  # Emits list of selected file paths

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_pages = []
        self.page_checkboxes = []
        self._init_ui()
        self._create_mock_pages()

    def _init_ui(self):
        """Initialize dialog UI."""
        self.setWindowTitle("Add Pages to Bundle")
        self.setMinimumSize(800, 600)

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

        # Container for grid
        container = QWidget()
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
        for i in range(1, 13):  # 12 mock unassigned pages
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


class BundleReviewWindowV1(QDialog):
    """
    Window for reviewing and editing document bundles.

    Features:
    - Thumbnail grid with multiple layout modes
    - Large preview with zoom, rotation, and pan
    - Page management (add, remove, delete, re-analyze)
    - Bundle actions (save, cancel)
    - Prototype mode with mock data
    """

    # Signals
    bundle_confirmed = pyqtSignal(dict)
    bundle_rejected = pyqtSignal(dict)

    def __init__(self, bundle_data=None, prototype_mode=True, parent=None):
        super().__init__(parent)

        # State
        self.prototype_mode = prototype_mode
        self.bundle_data = bundle_data or self._create_mock_bundle()
        self.current_page_index = 0
        self.zoom_level = 100  # Percentage
        self.rotation_angle = 0
        self.pan_offset = QPoint(0, 0)
        self.layout_mode = "flow"  # flow/grid/list
        self.is_panning = False
        self.pan_start_pos = QPoint(0, 0)

        # Confirmed/removed tracking (prototype)
        self.confirmed_pages = set()
        self.removed_pages = set()

        self._init_ui()
        self._load_bundle()

    def _init_ui(self):
        """Initialize main UI with three-panel layout."""
        self.setWindowTitle("Review Bundle")
        self.setMinimumSize(1400, 900)
        self.resize(1400, 900)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header bar
        header = self._create_header_bar()
        main_layout.addWidget(header)

        # Three-panel splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left panel - Thumbnails (300px)
        left_panel = self._create_thumbnail_panel()
        left_panel.setMinimumWidth(300)
        left_panel.setMaximumWidth(300)
        splitter.addWidget(left_panel)

        # Center panel - Large preview (flexible)
        center_panel = self._create_large_preview()
        splitter.addWidget(center_panel)

        # Right panel - Actions (280px)
        right_panel = self._create_action_panel()
        right_panel.setMinimumWidth(280)
        right_panel.setMaximumWidth(280)
        splitter.addWidget(right_panel)

        # Set initial sizes
        splitter.setSizes([300, 820, 280])

        main_layout.addWidget(splitter)

    def _create_header_bar(self) -> QWidget:
        """Create header bar with title, badges, and close button."""
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
            badge_color = "#F59E0B"  # Amber
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
        total_pages = len(self.bundle_data.get("file_paths", []))
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
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

        return header

    def _create_thumbnail_panel(self) -> QWidget:
        """Create left panel with layout selector and thumbnail grid."""
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

        # Scroll area for thumbnails
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        # Container for thumbnails
        self.thumbnail_container = QWidget()
        self.thumbnail_layout = QGridLayout(self.thumbnail_container)
        self.thumbnail_layout.setSpacing(8)
        scroll.setWidget(self.thumbnail_container)

        layout.addWidget(scroll)

        return panel

    def _create_large_preview(self) -> QWidget:
        """Create center panel with large preview and controls."""
        panel = QWidget()
        panel.setStyleSheet("background: white;")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Preview container
        preview_container = QWidget()
        preview_container.setStyleSheet(f"""
            background: white;
            border: 2px solid {Colors.GRAY_200};
            border-radius: 4px;
        """)
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(12, 12, 12, 12)

        # Large preview label
        self.large_preview = QLabel()
        self.large_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.large_preview.setMinimumSize(600, 500)
        self.large_preview.setStyleSheet("background: white;")
        preview_layout.addWidget(self.large_preview)

        layout.addWidget(preview_container)

        # Control panel
        controls = self._create_control_panel()
        layout.addWidget(controls)

        return panel

    def _create_control_panel(self) -> QWidget:
        """Create control panel with zoom, rotation, and save buttons."""
        panel = QWidget()
        panel.setStyleSheet(
            f"background: {Colors.GRAY_50}; border: 1px solid {Colors.GRAY_200}; border-radius: 4px;"
        )

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(15)

        # Zoom controls
        zoom_label = QLabel("Zoom:")
        zoom_label.setStyleSheet(f"font-weight: 600; color: {Colors.GRAY_700};")
        layout.addWidget(zoom_label)

        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setFixedSize(32, 32)
        zoom_out_btn.setStyleSheet(get_secondary_button_style())
        zoom_out_btn.clicked.connect(self._on_zoom_out)
        layout.addWidget(zoom_out_btn)

        self.zoom_spinner = QSpinBox()
        self.zoom_spinner.setRange(25, 400)
        self.zoom_spinner.setValue(100)
        self.zoom_spinner.setSuffix("%")
        self.zoom_spinner.setFixedWidth(80)
        self.zoom_spinner.valueChanged.connect(self._on_zoom_percent_changed)
        layout.addWidget(self.zoom_spinner)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedSize(32, 32)
        zoom_in_btn.setStyleSheet(get_secondary_button_style())
        zoom_in_btn.clicked.connect(self._on_zoom_in)
        layout.addWidget(zoom_in_btn)

        fit_width_btn = QPushButton("Fit Width")
        fit_width_btn.setStyleSheet(get_secondary_button_style())
        fit_width_btn.clicked.connect(self._on_fit_width)
        layout.addWidget(fit_width_btn)

        fit_height_btn = QPushButton("Fit Height")
        fit_height_btn.setStyleSheet(get_secondary_button_style())
        fit_height_btn.clicked.connect(self._on_fit_height)
        layout.addWidget(fit_height_btn)

        # Separator
        separator = QWidget()
        separator.setFixedWidth(2)
        separator.setStyleSheet(f"background: {Colors.GRAY_300};")
        layout.addWidget(separator)

        # Rotation controls
        rotation_label = QLabel("Rotate:")
        rotation_label.setStyleSheet(f"font-weight: 600; color: {Colors.GRAY_700};")
        layout.addWidget(rotation_label)

        rotate_ccw_btn = QPushButton("↺ 90°")
        rotate_ccw_btn.setStyleSheet(get_secondary_button_style())
        rotate_ccw_btn.clicked.connect(self._on_rotate_ccw)
        layout.addWidget(rotate_ccw_btn)

        rotate_cw_btn = QPushButton("↻ 90°")
        rotate_cw_btn.setStyleSheet(get_secondary_button_style())
        rotate_cw_btn.clicked.connect(self._on_rotate_cw)
        layout.addWidget(rotate_cw_btn)

        rotate_180_btn = QPushButton("180°")
        rotate_180_btn.setStyleSheet(get_secondary_button_style())
        rotate_180_btn.clicked.connect(self._on_rotate_180)
        layout.addWidget(rotate_180_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.setStyleSheet(get_secondary_button_style())
        reset_btn.clicked.connect(self._on_reset_rotation)
        layout.addWidget(reset_btn)

        # Separator
        separator2 = QWidget()
        separator2.setFixedWidth(2)
        separator2.setStyleSheet(f"background: {Colors.GRAY_300};")
        layout.addWidget(separator2)

        # Save copy button
        save_copy_btn = QPushButton("Save Copy")
        save_copy_btn.setStyleSheet(get_primary_button_style())
        save_copy_btn.clicked.connect(self._on_save_copy)
        layout.addWidget(save_copy_btn)

        layout.addStretch()

        return panel

    def _create_action_panel(self) -> QWidget:
        """Create right panel with page info and actions."""
        panel = QWidget()
        panel.setStyleSheet(f"background: white; border-left: 1px solid {Colors.GRAY_200};")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Page info card
        info_card = QWidget()
        info_card.setStyleSheet(f"""
            background: {Colors.GRAY_50};
            border: 1px solid {Colors.GRAY_200};
            border-radius: 6px;
            padding: 12px;
        """)
        info_layout = QVBoxLayout(info_card)
        info_layout.setSpacing(8)

        self.page_filename = QLabel()
        self.page_filename.setStyleSheet(
            f"font-weight: 600; color: {Colors.GRAY_900}; font-size: 13px;"
        )
        self.page_filename.setWordWrap(True)
        info_layout.addWidget(self.page_filename)

        self.page_position = QLabel()
        self.page_position.setStyleSheet(f"color: {Colors.GRAY_600}; font-size: 12px;")
        info_layout.addWidget(self.page_position)

        self.page_metadata = QLabel()
        self.page_metadata.setStyleSheet(f"color: {Colors.GRAY_700}; font-size: 12px;")
        self.page_metadata.setWordWrap(True)
        info_layout.addWidget(self.page_metadata)

        self.page_confidence = QLabel()
        self.page_confidence.setStyleSheet("font-weight: 600; font-size: 12px;")
        info_layout.addWidget(self.page_confidence)

        layout.addWidget(info_card)

        # Page actions section
        actions_label = QLabel("Page Actions")
        actions_label.setStyleSheet(
            f"font-weight: 700; color: {Colors.GRAY_900}; font-size: 13px; margin-top: 5px;"
        )
        layout.addWidget(actions_label)

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

        reanalyze_btn = QPushButton("Re-Analyze Page")
        reanalyze_btn.setStyleSheet(get_secondary_button_style())
        reanalyze_btn.clicked.connect(self._on_reanalyze_page)
        layout.addWidget(reanalyze_btn)

        delete_btn = QPushButton("Delete Page")
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background: white;
                color: {Colors.DANGER};
                border: 2px solid {Colors.DANGER};
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Colors.DANGER};
                color: white;
            }}
        """)
        delete_btn.clicked.connect(self._on_delete_page)
        layout.addWidget(delete_btn)

        layout.addStretch()

        # Divider
        divider = QWidget()
        divider.setFixedHeight(2)
        divider.setStyleSheet(f"background: {Colors.GRAY_300};")
        layout.addWidget(divider)

        # Bundle actions
        bundle_label = QLabel("Bundle Actions")
        bundle_label.setStyleSheet(
            f"font-weight: 700; color: {Colors.GRAY_900}; font-size: 13px; margin-top: 5px;"
        )
        layout.addWidget(bundle_label)

        save_bundle_btn = QPushButton("Save Bundle")
        save_bundle_btn.setStyleSheet(get_success_button_style())
        save_bundle_btn.clicked.connect(self._on_save_bundle)
        layout.addWidget(save_bundle_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(get_secondary_button_style())
        cancel_btn.clicked.connect(self._on_reject_bundle)
        layout.addWidget(cancel_btn)

        return panel

    def _create_mock_bundle(self) -> dict:
        """Create mock bundle data for prototype."""
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
        """Load bundle data and populate thumbnails."""
        self._populate_thumbnails()
        if self.bundle_data.get("file_paths"):
            self._display_page(0)

    def _populate_thumbnails(self):
        """Create and display thumbnails based on current layout mode."""
        # Clear existing thumbnails
        while self.thumbnail_layout.count():
            item = self.thumbnail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        file_paths = self.bundle_data.get("file_paths", [])

        for idx, file_path in enumerate(file_paths):
            if idx in self.removed_pages:
                continue

            thumbnail = self._create_thumbnail(file_path, idx)

            # Layout based on mode
            if self.layout_mode == "flow":
                row = idx // 3
                col = idx % 3
            elif self.layout_mode == "grid":
                row = idx // 4
                col = idx % 4
            else:  # list
                row = idx
                col = 0

            self.thumbnail_layout.addWidget(thumbnail, row, col)

    def _create_thumbnail(self, file_path: str, index: int) -> ClickableLabel:
        """Create thumbnail with selection border and hover effects."""
        # Create placeholder pixmap
        pixmap = QPixmap(80, 100)
        base_color = QColor(220 + (index * 10) % 30, 230, 245)
        pixmap.fill(base_color)

        painter = QPainter(pixmap)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, f"Page\n{index + 1}")

        # Add confirmed indicator
        if index in self.confirmed_pages:
            painter.setPen(QColor(Colors.SUCCESS))
            painter.drawText(5, 15, "✓")

        painter.end()

        # Create clickable label
        thumbnail = ClickableLabel()
        thumbnail.setPixmap(pixmap)
        thumbnail.setFixedSize(82, 102)

        # Set border based on selection
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

        # Connect click
        thumbnail.clicked.connect(lambda idx=index: self._on_thumbnail_clicked(idx))

        # Tooltip with metadata
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
        """Display page in large preview."""
        if index < 0 or index >= len(self.bundle_data.get("file_paths", [])):
            return

        self.current_page_index = index

        # Reset transform state
        self.rotation_angle = 0
        self.pan_offset = QPoint(0, 0)

        # Update preview
        self._update_large_preview()

        # Update page info
        self._update_page_info(index)

        # Refresh thumbnails to update selection
        self._populate_thumbnails()

    def _update_large_preview(self):
        """Update large preview with current transform state."""
        if not self.bundle_data.get("file_paths"):
            return

        # Create placeholder pixmap
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

        # Apply transforms
        transformed = self._apply_transform(base_pixmap)

        self.large_preview.setPixmap(transformed)
        self._update_cursor()

    def _apply_transform(self, pixmap: QPixmap) -> QPixmap:
        """Apply zoom, rotation, and pan to pixmap."""
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

        # Apply pan (if zoomed)
        if self.zoom_level > 100 and not self.pan_offset.isNull():
            # Create canvas for panned image
            canvas = QPixmap(pixmap.size())
            canvas.fill(Qt.GlobalColor.white)
            painter = QPainter(canvas)
            painter.drawPixmap(self.pan_offset, pixmap)
            painter.end()
            pixmap = canvas

        return pixmap

    def _update_page_info(self, index: int):
        """Update page info card."""
        if index >= len(self.bundle_data.get("file_paths", [])):
            return

        file_path = self.bundle_data["file_paths"][index]
        filename = Path(file_path).name

        self.page_filename.setText(filename)
        self.page_position.setText(f"Page {index + 1} of {len(self.bundle_data['file_paths'])}")

        if index < len(self.bundle_data.get("analyses", [])):
            analysis = self.bundle_data["analyses"][index]

            company = analysis.get("company", "Unknown")
            doc_type = analysis.get("document_type", "Unknown")
            doc_date = self.bundle_data.get("document_date", "Unknown")

            self.page_metadata.setText(f"Company: {company}\nType: {doc_type}\nDate: {doc_date}")

            confidence = analysis.get("confidence_score", 0.0)
            confidence_pct = int(confidence * 100)

            if confidence >= 0.8:
                color = Colors.SUCCESS
            elif confidence >= 0.5:
                color = "#F59E0B"
            else:
                color = Colors.DANGER

            self.page_confidence.setText(f"Confidence: {confidence_pct}%")
            self.page_confidence.setStyleSheet(
                f"font-weight: 600; font-size: 12px; color: {color};"
            )

    def _update_cursor(self):
        """Update cursor based on zoom level."""
        if self.zoom_level > 100:
            self.large_preview.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        else:
            self.large_preview.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    # Event handlers - Thumbnails
    def _on_thumbnail_clicked(self, index: int):
        """Handle thumbnail click."""
        self._display_page(index)

    def _on_layout_changed(self, layout_name: str):
        """Handle layout mode change."""
        if layout_name == "Flow Layout":
            self.layout_mode = "flow"
        elif layout_name == "4-Column Grid":
            self.layout_mode = "grid"
        else:
            self.layout_mode = "list"

        self._populate_thumbnails()

    # Event handlers - Zoom
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
        self._update_large_preview()

    def _on_fit_width(self):
        """Fit image to preview width."""
        # Simplified calculation for mock
        self.zoom_spinner.setValue(100)

    def _on_fit_height(self):
        """Fit image to preview height."""
        # Simplified calculation for mock
        self.zoom_spinner.setValue(75)

    # Event handlers - Rotation
    def _on_rotate_ccw(self):
        """Rotate counter-clockwise 90°."""
        self.rotation_angle = (self.rotation_angle - 90) % 360
        self._update_large_preview()

    def _on_rotate_cw(self):
        """Rotate clockwise 90°."""
        self.rotation_angle = (self.rotation_angle + 90) % 360
        self._update_large_preview()

    def _on_rotate_180(self):
        """Rotate 180°."""
        self.rotation_angle = (self.rotation_angle + 180) % 360
        self._update_large_preview()

    def _on_reset_rotation(self):
        """Reset rotation to 0°."""
        self.rotation_angle = 0
        self.pan_offset = QPoint(0, 0)
        self.zoom_spinner.setValue(100)
        self._update_large_preview()

    # Event handlers - Pan (mouse events)
    def mousePressEvent(self, event):
        """Start pan drag."""
        if self.zoom_level > 100 and event.button() == Qt.MouseButton.LeftButton:
            if self.large_preview.underMouse():
                self.is_panning = True
                self.pan_start_pos = event.pos()
                self.large_preview.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def mouseMoveEvent(self, event):
        """Update pan offset during drag."""
        if self.is_panning:
            delta = event.pos() - self.pan_start_pos
            self.pan_offset += delta
            self.pan_start_pos = event.pos()
            self._update_large_preview()

    def mouseReleaseEvent(self, event):
        """End pan drag."""
        if self.is_panning:
            self.is_panning = False
            self._update_cursor()

    # Event handlers - Page actions
    def _on_confirm_page(self):
        """Mark current page as confirmed."""
        self.confirmed_pages.add(self.current_page_index)
        self._populate_thumbnails()  # Refresh to show checkmark

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(f"Page {self.current_page_index + 1} confirmed!")
        msg.setWindowTitle("Page Confirmed")
        msg.exec()

    def _on_remove_page(self):
        """Remove page from bundle."""
        reply = QMessageBox.question(
            self,
            "Remove Page",
            f"Remove page {self.current_page_index + 1} from this bundle?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.removed_pages.add(self.current_page_index)

            # Move to next page or previous
            remaining = [
                i for i in range(len(self.bundle_data["file_paths"])) if i not in self.removed_pages
            ]
            if remaining:
                self._display_page(remaining[0])
            else:
                self.large_preview.clear()

            self._populate_thumbnails()

    def _on_add_pages(self):
        """Show dialog to add unassigned pages."""
        dialog = UnassignedPagesDialog(self)
        dialog.pages_selected.connect(self._on_pages_added)
        dialog.exec()

    def _on_pages_added(self, file_paths: list):
        """Handle pages added from dialog."""
        # Add to bundle data
        current_paths = self.bundle_data["file_paths"]
        self.bundle_data["file_paths"].extend(file_paths)

        # Create mock analyses for new pages
        for i, fp in enumerate(file_paths, len(current_paths) + 1):
            self.bundle_data["analyses"].append(
                {
                    "file_path": fp,
                    "company": self.bundle_data["company"],
                    "document_type": self.bundle_data["document_type"],
                    "page_number": i,
                    "total_pages": len(self.bundle_data["file_paths"]),
                    "confidence_score": 0.75,
                    "legibility": "clear",
                    "rotation_needed": False,
                }
            )

        self._populate_thumbnails()

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(f"Added {len(file_paths)} page(s) to bundle")
        msg.setWindowTitle("Pages Added")
        msg.exec()

    def _on_reanalyze_page(self):
        """Re-analyze current page (prototype mode message)."""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText("Re-analysis feature will be available when connected to backend services.")
        msg.setWindowTitle("Prototype Mode")
        msg.exec()

    def _on_delete_page(self):
        """Delete page permanently."""
        reply = QMessageBox.question(
            self,
            "Delete Page",
            f"Permanently delete page {self.current_page_index + 1}?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Same as remove for prototype
            self._on_remove_page()

    # Event handlers - Other
    def _on_save_copy(self):
        """Save copy of current page with transforms."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Page Copy",
            f"page_{self.current_page_index + 1}.png",
            "PNG Images (*.png);;JPEG Images (*.jpg *.jpeg)",
        )

        if file_path:
            # Get current pixmap
            pixmap = self.large_preview.pixmap()
            if pixmap:
                pixmap.save(file_path)

                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Icon.Information)
                msg.setText(f"Page saved to:\n{file_path}")
                msg.setWindowTitle("Page Saved")
                msg.exec()

    def _on_save_bundle(self):
        """Save bundle and emit confirmation signal."""
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
        """Reject bundle and emit rejection signal."""
        reply = QMessageBox.question(
            self,
            "Cancel Review",
            "Discard all changes to this bundle?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.bundle_rejected.emit(self.bundle_data)
            self.reject()
