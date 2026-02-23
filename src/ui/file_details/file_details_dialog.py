"""
File Details Dialog

Dialog showing detailed information for a single file, including image preview,
extracted metadata, analysis results, and raw LLM response.
"""

import os
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ui.file_details.file_details_dialog_actions import _DialogActionsMixin
from ui.file_details.file_details_dialog_sections import _DialogSectionsMixin
from ui.image_preview import ImagePreviewWidget, ToolbarPosition, ToolbarSize


class FileDetailsDialog(_DialogSectionsMixin, _DialogActionsMixin, QDialog):
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
    record_deleted = pyqtSignal(str)  # Emits file path when record is deleted

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
        self.config_manager = config_manager  # Store config manager reference
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
                "bg_primary": "#0B1120",
                "bg_secondary": "#151D2F",
                "text_primary": "#E0E0E0",
                "text_secondary": "#B0B0B0",
                "border": "#2A3550",
                "accent": "#3B82F6",
                "button_bg": "#1F2A40",
                "button_hover": "#2A3550",
            }
        else:
            return {
                "bg_primary": "#FFFFFF",
                "bg_secondary": "#F9FAFB",
                "text_primary": "#111827",
                "text_secondary": "#374151",
                "border": "#E5E7EB",
                "accent": "#3B82F6",
                "button_bg": "#F3F4F6",
                "button_hover": "#EFF6FF",
            }

    def _init_ui(self):
        """Initialize the user interface with image preview and accordion sections."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create horizontal splitter for left (image) and right (metadata) panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)  # Make handle wider and easier to grab
        splitter.setChildrenCollapsible(False)  # Prevent panels from collapsing completely

        # Style the splitter handle to make it visible and indicate it's draggable
        handle_color = "#2A3550" if self.is_dark_mode else "#D1D5DB"
        hover_color = "#3A4560" if self.is_dark_mode else "#9CA3AF"
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
        # Create unified image preview widget
        self.image_preview = ImagePreviewWidget(
            toolbar_size=ToolbarSize.COMPACT,
            toolbar_position=ToolbarPosition.BOTTOM_CENTER,
            theme_colors=self.theme_colors,
            config_manager=self.config_manager,
            analysis_db=self.analysis_db,
        )
        self.image_preview.setMinimumSize(400, 400)

        # Load and display image (path already corrected in __init__)
        file_path = self.file_data.get("full_path")

        if file_path and os.path.exists(file_path):
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                # Store base pixmap (never modified)
                self.base_pixmap = pixmap
                self.original_pixmap = pixmap
                self.current_rotation = "none"

                # Load into preview widget with fit to window
                self.image_preview.set_pixmap(pixmap, apply_fit="window", file_path=file_path)
            else:
                self.base_pixmap = None
                self.original_pixmap = None
                self.current_rotation = "none"
                self.image_preview.image_label.setText("Failed to load image")
                self.image_preview.image_label.setStyleSheet(
                    f"color: {self.theme_colors['text_secondary']};"
                )
        else:
            self.base_pixmap = None
            self.original_pixmap = None
            self.current_rotation = "none"
            self.image_preview.image_label.setText(f"Image not found\n{file_path or 'No path'}")
            self.image_preview.image_label.setStyleSheet(
                f"color: {self.theme_colors['text_secondary']};"
            )

        image_area = self.image_preview  # For compatibility with existing splitter code
        left_layout.addWidget(image_area)

        # Store references for dynamic resizing
        self.image_area = image_area  # Store for compatibility
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
                background: {self.theme_colors["bg_primary"]};
                color: {self.theme_colors["text_primary"]};
                border: 1px solid {self.theme_colors["border"]};
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                min-height: 36px;
            }}
            QPushButton:hover {{
                background: {self.theme_colors["bg_secondary"]};
                border-color: {self.theme_colors["accent"]};
            }}
            QPushButton:pressed {{
                background: {self.theme_colors["accent"]};
                color: white;
            }}
        """

        # Action buttons with consistent styling
        # Delete Record button (with red styling for destructive action)
        delete_button_style = """
            QPushButton {
                background: #991B1B;
                color: #E0E0E0;
                border: 1px solid #7F1D1D;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                min-height: 36px;
            }
            QPushButton:hover {
                background: #7F1D1D;
                border-color: #991B1B;
            }
            QPushButton:pressed {
                background: #450A0A;
                color: white;
            }
        """
        self.delete_btn = QPushButton("🗑️ Delete Record")
        self.delete_btn.setStyleSheet(delete_button_style)
        self.delete_btn.setToolTip(
            "Delete this record from the database (file will NOT be deleted)"
        )
        self.delete_btn.clicked.connect(self._delete_record)
        bottom_layout.addWidget(self.delete_btn)

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
