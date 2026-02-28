"""Right-panel: accordion metadata form + output filename.

Emits signals; the orchestrator (GuidedBundleWorkflow / BundleReviewWidget)
handles cross-panel interactions (disabling thumbnail/action-bar in edit mode).
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.bundle.bundle_colors import get_bundle_colors
from ui.bundle.bundle_metadata_forms import (
    create_analysis_info_form,
    create_file_info_form,
    create_metadata_form,
)


class BundleMetadataPanel(QWidget):
    """Accordion metadata form + output-filename field.

    Signals
    -------
    metadata_changed
        Emitted once when the user first modifies a field (entering edit mode).
    save_requested(dict)
        Emitted when the user confirms edits.  Payload is ``get_metadata()``.
    cancel_requested
        Emitted when the user cancels edits.
    """

    metadata_changed = pyqtSignal()
    save_requested = pyqtSignal(dict)
    cancel_requested = pyqtSignal()

    def __init__(
        self,
        dark_mode: bool,
        parent: QWidget | None = None,
        analysis_db: Any | None = None,
    ) -> None:
        super().__init__(parent)
        self._dark_mode = dark_mode
        self._analysis_db = analysis_db

        # Bundle state (populated by load_bundle())
        self._bundle: dict = {}
        self._page_order: list[int] = []
        self._current_page_index: int = 0
        self._prototype_mode: bool = False

        # UI state
        self._metadata_inputs: dict[str, QWidget] = {}
        self._accordion_sections: list[QWidget] = []
        self._in_edit_mode: bool = False
        self._original_metadata: dict = {}
        self._output_filename_manually_edited: bool = False

        # Built in _build_ui — referenced in several methods
        self._output_filename_input: QLineEdit
        self._save_btn: QPushButton
        self._cancel_btn: QPushButton

        self._build_ui()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        theme = get_bundle_colors(self._dark_mode)

        self.setStyleSheet(f"background: {theme['metadata_bg']};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area for accordion sections
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {theme['metadata_bg']}; }}")

        container = QWidget()
        container.setStyleSheet(f"background: {theme['metadata_bg']};")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self._accordion_sections = []

        form_w, inputs, save_btn, cancel_btn = create_metadata_form(
            dark_mode=self._dark_mode,
            bundle=self._bundle,
            page_order=self._page_order,
            current_page_index=self._current_page_index,
            on_field_change=self._enter_edit_mode,
            on_update_filename=self._update_output_filename,
            on_save=self._on_save_btn_clicked,
            on_cancel=self._on_cancel_btn_clicked,
            analysis_db=self._analysis_db,
        )
        self._metadata_inputs = inputs
        self._save_btn = save_btn
        self._cancel_btn = cancel_btn
        metadata_section = self._create_accordion_section(
            "📋 Extracted Metadata", form_w, initially_expanded=True, section_type="metadata"
        )
        container_layout.addWidget(metadata_section)

        file_info_w = create_file_info_form(
            dark_mode=self._dark_mode,
            bundle=self._bundle,
            page_order=self._page_order,
            current_page_index=self._current_page_index,
            prototype_mode=self._prototype_mode,
        )
        file_info_section = self._create_accordion_section(
            "📄 File Information", file_info_w, initially_expanded=False, section_type="file_info"
        )
        container_layout.addWidget(file_info_section)

        analysis_w = create_analysis_info_form(
            dark_mode=self._dark_mode,
            bundle=self._bundle,
            page_order=self._page_order,
            current_page_index=self._current_page_index,
        )
        analysis_section = self._create_accordion_section(
            "⚙️ Analysis Information",
            analysis_w,
            initially_expanded=False,
            section_type="analysis_info",
        )
        container_layout.addWidget(analysis_section)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Output filename at the bottom (fixed height)
        output_section = self._create_output_filename_section()
        layout.addWidget(output_section)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_bundle(
        self,
        bundle: dict,
        page_order: list[int],
        current_page_index: int,
        prototype_mode: bool,
    ) -> None:
        """Replace displayed bundle data and rebuild all accordion forms."""
        self._bundle = bundle
        self._page_order = page_order
        self._current_page_index = current_page_index
        self._prototype_mode = prototype_mode
        self._output_filename_manually_edited = False
        self._refresh_forms()
        self._update_output_filename()

    def get_metadata(self) -> dict:
        """Collect current field values and return as a dict."""
        result: dict = {}
        for field_name, widget in self._metadata_inputs.items():
            if isinstance(widget, QCheckBox):
                result[field_name] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                result[field_name] = widget.currentText()
            elif isinstance(widget, QLineEdit):
                result[field_name] = widget.text()
        return result

    def get_output_filename(self) -> str:
        """Return the current output filename (without extension)."""
        return str(self._output_filename_input.text())

    def set_output_filename(self, name: str) -> None:
        """Set output filename without triggering the manual-edit flag."""
        self._output_filename_input.blockSignals(True)
        self._output_filename_input.setText(name)
        self._output_filename_input.blockSignals(False)

    def apply_theme(self, dark_mode: bool) -> None:
        """Re-apply colour styles and rebuild accordion forms for the new theme."""
        self._dark_mode = dark_mode
        theme = get_bundle_colors(dark_mode)

        self.setStyleSheet(f"background: {theme['metadata_bg']};")

        for section in self._accordion_sections:
            header = section.findChild(QFrame)
            if header:
                header.setStyleSheet(
                    f"""
                    QFrame {{
                        background-color: {theme["bg_tertiary"]};
                        border: none;
                        border-radius: 4px;
                        padding: 6px 10px;
                    }}
                    QFrame:hover {{
                        background-color: {theme["bg_hover"]};
                    }}
                    """
                )

            toggle = section.findChild(QLabel, "accordion_toggle")
            if toggle:
                toggle.setStyleSheet(
                    f"color: {theme['text_secondary']}; font-size: 9px; border: none;"
                )

            title_label = section.findChild(QLabel, "accordion_title")
            if title_label:
                title_label.setStyleSheet(
                    f"color: {theme['text_primary']}; font-weight: 600; font-size: 12px; border: none;"
                )

            content_scroll = section.findChild(QScrollArea, "accordion_content")
            if content_scroll:
                content_scroll.setStyleSheet(
                    f"QScrollArea {{ background-color: {theme['bg_secondary']}; border: none; }}"
                )
                container = content_scroll.widget()
                if container:
                    container.setStyleSheet(f"background: {theme['bg_secondary']};")
                viewport = content_scroll.viewport()
                if viewport:
                    viewport.setStyleSheet(f"background: {theme['bg_secondary']};")

        # Re-style output filename section
        highlight_bg = theme["info"] if dark_mode else "#e0f2fe"
        output_section = self._output_filename_input.parent()
        if isinstance(output_section, QWidget):
            output_section.setStyleSheet(f"background: {highlight_bg}; border-radius: 6px;")
            output_section.setMinimumHeight(90)
            output_section.setMaximumHeight(90)
            label_color = "white" if dark_mode else "#0c4a6e"
            for lbl in output_section.findChildren(QLabel):
                lbl.setStyleSheet(
                    f"color: {label_color}; font-weight: 700; font-size: 13px; background: transparent;"
                )
                lbl.setMinimumHeight(24)
                lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

            input_border = "#60a5fa" if dark_mode else "#3b82f6"
            self._output_filename_input.setStyleSheet(
                f"""
                QLineEdit {{
                    background: #ffffff;
                    color: #111827;
                    border: 2px solid {input_border};
                    border-radius: 6px;
                    padding: 10px 12px;
                    font-size: 14px;
                    font-weight: 600;
                }}
                QLineEdit:focus {{
                    border: 2px solid {theme["selected"]};
                    background: #ffffff;
                }}
                """
            )

        # Rebuild all accordion forms with the new theme
        self._refresh_forms()

    # ------------------------------------------------------------------
    # Private: accordion management
    # ------------------------------------------------------------------

    def _create_accordion_section(
        self,
        title: str,
        content_widget: QWidget,
        initially_expanded: bool = False,
        section_type: str = "",
    ) -> QWidget:
        """Create a collapsible accordion section."""
        theme = get_bundle_colors(self._dark_mode)

        section = QWidget()
        section.section_type = section_type  # type: ignore[attr-defined]
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 1)
        section_layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.setStyleSheet(
            f"""
            QFrame {{
                background-color: {theme["bg_tertiary"]};
                border: none;
                border-radius: 4px;
                padding: 6px 10px;
            }}
            QFrame:hover {{
                background-color: {theme["bg_hover"]};
            }}
            """
        )

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        toggle_indicator = QLabel("▼" if initially_expanded else "▶")
        toggle_indicator.setStyleSheet(
            f"color: {theme['text_secondary']}; font-size: 9px; border: none;"
        )
        toggle_indicator.setObjectName("accordion_toggle")
        header_layout.addWidget(toggle_indicator)

        title_label = QLabel(title)
        title_label.setObjectName("accordion_title")
        title_label.setStyleSheet(
            f"color: {theme['text_primary']}; font-weight: 600; font-size: 12px; border: none;"
        )
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        section_layout.addWidget(header)

        # Content scroll area
        content_scroll = QScrollArea()
        content_scroll.setWidgetResizable(True)
        content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content_scroll.setObjectName("accordion_content")
        content_scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {theme['bg_secondary']}; border: none; }}"
        )

        content_container = QWidget()
        content_container.setStyleSheet(f"background: {theme['bg_secondary']};")
        content_container_layout = QVBoxLayout(content_container)
        content_container_layout.setContentsMargins(12, 12, 12, 12)
        content_container_layout.setSpacing(0)
        content_container_layout.addWidget(content_widget)
        content_container_layout.addStretch()

        content_scroll.setWidget(content_container)

        viewport = content_scroll.viewport()
        if viewport is not None:
            viewport.setStyleSheet(f"background: {theme['bg_secondary']};")

        section_layout.addWidget(content_scroll)

        content_scroll.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding if initially_expanded else QSizePolicy.Policy.Ignored,
        )
        content_scroll.setVisible(initially_expanded)

        def toggle_section() -> None:
            if not content_scroll.isVisible():
                for other_section in self._accordion_sections:
                    other_content = other_section.findChild(QScrollArea, "accordion_content")
                    other_toggle = other_section.findChild(QLabel, "accordion_toggle")
                    if other_content and other_content is not content_scroll:
                        other_content.setVisible(False)
                        other_content.setSizePolicy(
                            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored
                        )
                        if other_toggle:
                            other_toggle.setText("▶")
                content_scroll.setVisible(True)
                content_scroll.setSizePolicy(
                    QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
                )
                toggle_indicator.setText("▼")

        header.mousePressEvent = lambda e: toggle_section()  # type: ignore[method-assign,assignment]

        section.accordion_header = header  # type: ignore[attr-defined]
        section.accordion_content = content_scroll  # type: ignore[attr-defined]
        section.accordion_toggle = toggle_indicator  # type: ignore[attr-defined]

        self._accordion_sections.append(section)

        return section

    def _refresh_forms(self) -> None:
        """Rebuild all accordion form content for the current bundle/page state."""
        for section in self._accordion_sections:
            if not hasattr(section, "accordion_content"):
                continue
            content_scroll = section.accordion_content
            content_container = content_scroll.widget()
            if content_container is None:
                continue
            layout = content_container.layout()
            if layout is None:
                continue

            widgets_to_delete = []
            while layout.count() > 0:
                item = layout.takeAt(0)
                if item is not None:
                    widget = item.widget()
                    if widget is not None:
                        widget.setParent(None)
                        widget.hide()
                        widgets_to_delete.append(widget)
            for widget in widgets_to_delete:
                widget.deleteLater()
            QApplication.processEvents()

            section_type = getattr(section, "section_type", "")
            if section_type == "metadata":
                form_w, inputs, save_btn, cancel_btn = create_metadata_form(
                    dark_mode=self._dark_mode,
                    bundle=self._bundle,
                    page_order=self._page_order,
                    current_page_index=self._current_page_index,
                    on_field_change=self._enter_edit_mode,
                    on_update_filename=self._update_output_filename,
                    on_save=self._on_save_btn_clicked,
                    on_cancel=self._on_cancel_btn_clicked,
                    analysis_db=self._analysis_db,
                )
                self._metadata_inputs = inputs
                self._save_btn = save_btn
                self._cancel_btn = cancel_btn
                new_widget = form_w
            elif section_type == "file_info":
                new_widget = create_file_info_form(
                    dark_mode=self._dark_mode,
                    bundle=self._bundle,
                    page_order=self._page_order,
                    current_page_index=self._current_page_index,
                    prototype_mode=self._prototype_mode,
                )
            elif section_type == "analysis_info":
                new_widget = create_analysis_info_form(
                    dark_mode=self._dark_mode,
                    bundle=self._bundle,
                    page_order=self._page_order,
                    current_page_index=self._current_page_index,
                )
            else:
                continue

            layout.addWidget(new_widget)
            layout.addStretch()

    def _create_output_filename_section(self) -> QWidget:
        """Create output-filename section with auto-updating field."""
        theme = get_bundle_colors(self._dark_mode)
        highlight_bg = theme["info"] if self._dark_mode else "#e0f2fe"

        section = QWidget()
        section.setStyleSheet(f"background: {highlight_bg}; border-radius: 6px;")
        section.setMinimumHeight(90)
        section.setMaximumHeight(90)

        layout = QVBoxLayout(section)
        layout.setContentsMargins(10, 8, 10, 6)
        layout.setSpacing(6)

        label = QLabel("📄 Output File Name")
        label_color = "white" if self._dark_mode else "#0c4a6e"
        label.setStyleSheet(
            f"color: {label_color}; font-weight: 700; font-size: 13px; background: transparent;"
        )
        label.setMinimumHeight(24)
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(label)

        input_border = "#60a5fa" if self._dark_mode else "#3b82f6"
        self._output_filename_input = QLineEdit()
        self._output_filename_input.setPlaceholderText("Company - Invoice - 2024-01-15")
        self._output_filename_input.setToolTip(
            "Output PDF filename (without extension).\n\n"
            "Extension will be automatically set to .PDF when saving.\n"
            "Any extension you type will be removed and replaced with .PDF"
        )
        self._output_filename_input.setStyleSheet(
            f"""
            QLineEdit {{
                background: #ffffff;
                color: #111827;
                border: 2px solid {input_border};
                border-radius: 6px;
                padding: 10px 12px;
                font-size: 14px;
                font-weight: 600;
            }}
            QLineEdit:focus {{
                border: 2px solid {theme["selected"]};
                background: #ffffff;
            }}
            """
        )
        self._output_filename_input.textChanged.connect(self._on_output_filename_manual_edit)
        layout.addWidget(self._output_filename_input)

        return section

    # ------------------------------------------------------------------
    # Private: edit-mode management
    # ------------------------------------------------------------------

    def _enter_edit_mode(self) -> None:
        """Enter edit mode on first field change."""
        if self._in_edit_mode:
            return

        self._original_metadata = {}
        for field_name, input_widget in self._metadata_inputs.items():
            if isinstance(input_widget, QCheckBox):
                self._original_metadata[field_name] = input_widget.isChecked()
            elif isinstance(input_widget, QComboBox):
                self._original_metadata[field_name] = input_widget.currentText()
            elif isinstance(input_widget, QLineEdit):
                self._original_metadata[field_name] = input_widget.text()

        self._in_edit_mode = True

        for section in self._accordion_sections:
            if hasattr(section, "accordion_header"):
                header = section.accordion_header
                header.setEnabled(False)
                header.setCursor(Qt.CursorShape.ForbiddenCursor)

        if hasattr(self, "_save_btn"):
            self._save_btn.setVisible(True)
        if hasattr(self, "_cancel_btn"):
            self._cancel_btn.setVisible(True)

        self.metadata_changed.emit()

    def _exit_edit_mode(self) -> None:
        """Exit edit mode and hide save/cancel buttons."""
        self._in_edit_mode = False
        self._original_metadata = {}

        for section in self._accordion_sections:
            if hasattr(section, "accordion_header"):
                header = section.accordion_header
                header.setEnabled(True)
                header.setCursor(Qt.CursorShape.PointingHandCursor)

        if hasattr(self, "_save_btn"):
            self._save_btn.setVisible(False)
        if hasattr(self, "_cancel_btn"):
            self._cancel_btn.setVisible(False)

    def _on_save_btn_clicked(self) -> None:
        """Confirm edits and notify orchestrator."""
        metadata = self.get_metadata()
        self._exit_edit_mode()
        self.save_requested.emit(metadata)

    def _on_cancel_btn_clicked(self) -> None:
        """Revert fields and notify orchestrator."""
        for field_name, original_value in self._original_metadata.items():
            if field_name in self._metadata_inputs:
                w = self._metadata_inputs[field_name]
                if isinstance(w, QCheckBox):
                    w.blockSignals(True)
                    w.setChecked(original_value)
                    w.blockSignals(False)
                elif isinstance(w, QComboBox):
                    w.blockSignals(True)
                    w.setCurrentText(original_value)
                    w.blockSignals(False)
                elif isinstance(w, QLineEdit):
                    w.blockSignals(True)
                    w.setText(original_value)
                    w.blockSignals(False)

        self._exit_edit_mode()
        self.cancel_requested.emit()

    # ------------------------------------------------------------------
    # Private: output filename
    # ------------------------------------------------------------------

    def _on_output_filename_manual_edit(self) -> None:
        self._output_filename_manually_edited = True

    def _update_output_filename(self) -> None:
        """Auto-update output filename from key metadata fields (unless manually edited)."""
        if self._output_filename_manually_edited:
            return

        company = ""
        document_type = ""
        document_date = ""

        if "company" in self._metadata_inputs:
            w = self._metadata_inputs["company"]
            company = (
                w.currentText()
                if isinstance(w, QComboBox)
                else (w.text() if isinstance(w, QLineEdit) else "")
            )

        if "document_type" in self._metadata_inputs:
            w = self._metadata_inputs["document_type"]
            document_type = (
                w.currentText()
                if isinstance(w, QComboBox)
                else (w.text() if isinstance(w, QLineEdit) else "")
            )

        if "document_date" in self._metadata_inputs:
            w = self._metadata_inputs["document_date"]
            document_date = w.text() if isinstance(w, QLineEdit) else ""

        parts = []
        if company:
            parts.append(company.title())
        if document_type:
            parts.append(document_type.title())
        if document_date:
            parts.append(document_date)

        filename = self._sanitize_filename(" - ".join(parts) if parts else "document")

        self._output_filename_input.textChanged.disconnect(self._on_output_filename_manual_edit)
        self._output_filename_input.setText(filename)
        self._output_filename_input.textChanged.connect(self._on_output_filename_manual_edit)

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        for char in '<>:"/\\|?*':
            filename = filename.replace(char, "")
        return filename.strip(". ")
