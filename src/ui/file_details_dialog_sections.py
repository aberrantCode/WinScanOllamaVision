"""
File Details Dialog Sections Mixin

Provides UI-building methods for accordion sections within FileDetailsDialog.
These methods are separated for organizational clarity; they access self.* via
Python's MRO when mixed into FileDetailsDialog.
"""
# mypy: disable-error-code=attr-defined

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    pass


class _DialogSectionsMixin:
    """
    Mixin providing accordion section creation methods for FileDetailsDialog.

    All methods access self.* which resolves correctly via MRO since
    FileDetailsDialog inherits from this mixin alongside QDialog.
    """

    def _create_accordion_section(
        self, title: str, content_widget, initially_expanded: bool = False
    ):
        """Create a collapsible accordion section."""
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
        if self.analysis_db:
            file_path = self.file_data.get("full_path")
            if file_path:
                # Get rotation from metadata table using RotationRepository
                from db.repositories.rotation_repo import RotationRepository

                rotation_repo = RotationRepository(self.analysis_db.connection)
                rotation_degrees = rotation_repo.get(file_path)
                # Convert degrees back to rotation_needed format
                rotation_value = {
                    0: "none",
                    90: "90_cw",
                    270: "90_ccw",
                    180: "180",
                }.get(rotation_degrees, "none")  # Default to "none" if unexpected value
                logger.debug(
                    f"[METADATA CONTENT] Loaded rotation from metadata table: {rotation_degrees}° = '{rotation_value}'"
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

    def _on_splitter_moved(self, pos, index):
        """Handle splitter movement - no automatic rescaling with manual zoom controls."""
        # With manual zoom controls, we don't automatically rescale on splitter movement
        # Users can use fit buttons (W, H, F) if they want to adjust zoom
        pass

    def resizeEvent(self, event):  # noqa: N802
        """Handle window resize - reposition overlay controls."""
        super().resizeEvent(event)
        # Reposition overlay controls at bottom-left when window is resized
        if hasattr(self, "overlay_controls") and hasattr(self, "image_area"):
            self._position_overlay_controls()
