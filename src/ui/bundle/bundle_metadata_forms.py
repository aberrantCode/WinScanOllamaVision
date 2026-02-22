"""Standalone form-builder functions for BundleMetadataPanel accordion sections.

Extracted from BundleMetadataPanel to keep that class under 800 lines.
Each function is called from _build_ui() and _refresh_forms() with the current
panel state passed as parameters instead of via self.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygon
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.bundle.bundle_colors import get_bundle_colors
from ui.bundle.bundle_pdf_converter import BundlePdfConverter
from ui.styles import Colors


def create_metadata_form(
    dark_mode: bool,
    bundle: dict,
    page_order: list[int],
    current_page_index: int,
    on_field_change: Callable,
    on_update_filename: Callable,
    on_save: Callable,
    on_cancel: Callable,
) -> tuple[QWidget, dict[str, QWidget], QPushButton, QPushButton]:
    """Build the editable metadata form.

    Returns
    -------
    (form_widget, metadata_inputs, save_btn, cancel_btn)
    """
    theme = get_bundle_colors(dark_mode)

    form = QWidget()
    form.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(form)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)

    actual_index = (
        page_order[current_page_index]
        if current_page_index < len(page_order)
        else current_page_index
    )
    analysis = (
        bundle["analyses"][actual_index] if actual_index < len(bundle.get("analyses", [])) else {}
    )

    metadata_inputs: dict[str, QWidget] = {}

    def add_field(
        label: str,
        field_name: str,
        value: object,
        widget_type: str = "text",
        options: list[str] | None = None,
        placeholder: str = "",
    ) -> None:
        field_container = QWidget()
        field_container.setStyleSheet("background: transparent;")
        field_layout = QVBoxLayout(field_container)
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(6)

        lbl = QLabel(label)
        label_color = "#f1f5f9" if dark_mode else "#111827"
        lbl.setStyleSheet(
            f"color: {label_color}; font-weight: 600; font-size: 12px; background: transparent;"
        )
        field_layout.addWidget(lbl)

        widget: QWidget
        if widget_type == "dropdown":
            arrow_color = theme["text_primary"]
            combo = QComboBox()
            combo.setEditable(True)
            if options:
                combo.addItems(options)
            if value:
                combo.setCurrentText(str(value))
            combo.setStyleSheet(
                f"""
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
                """
            )

            # Monkey-patch: draw custom down-arrow triangle
            original_paint = combo.paintEvent

            def custom_paint(event, _widget=combo, _arrow_color=arrow_color):  # noqa: ANN001
                original_paint(event)
                painter = QPainter(_widget)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                ax = _widget.width() - 18
                ay = _widget.height() // 2
                points = [
                    QPoint(ax - 4, ay - 2),
                    QPoint(ax + 4, ay - 2),
                    QPoint(ax, ay + 3),
                ]
                polygon = QPolygon(points)
                painter.setPen(QPen(QColor(_arrow_color), 1))
                painter.setBrush(QColor(_arrow_color))
                painter.drawPolygon(polygon)
                painter.end()

            combo.paintEvent = custom_paint  # type: ignore[method-assign]
            widget = combo

        elif widget_type == "checkbox":
            chk = QCheckBox()
            chk.setChecked(bool(value))
            chk.setStyleSheet(
                f"""
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
                """
            )
            widget = chk

        else:
            line = QLineEdit()
            line.setText(str(value) if value else "")
            if placeholder:
                line.setPlaceholderText(placeholder)
            line.setStyleSheet(
                f"""
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
                """
            )
            widget = line

        field_layout.addWidget(widget)
        layout.addWidget(field_container)
        metadata_inputs[field_name] = widget

        if field_name in ("company", "document_type", "document_date"):
            if widget_type == "dropdown" and isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(on_update_filename)
            elif widget_type == "text" and isinstance(widget, QLineEdit):
                widget.textChanged.connect(on_update_filename)

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

    layout.addSpacing(15)
    button_layout = QHBoxLayout()
    button_layout.addStretch()

    save_btn = QPushButton("💾 Save Changes")
    save_btn.setStyleSheet(
        f"""
        QPushButton {{
            background-color: {Colors.SUCCESS};
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: 600;
            font-size: 12px;
        }}
        QPushButton:hover {{ background-color: #059669; }}
        """
    )
    save_btn.clicked.connect(on_save)
    save_btn.setVisible(False)
    button_layout.addWidget(save_btn)

    _ct = get_bundle_colors(dark_mode)
    cancel_btn = QPushButton("✖ Cancel")
    cancel_btn.setStyleSheet(
        f"""
        QPushButton {{
            background-color: {_ct["button_bg"]};
            color: {_ct["button_text"]};
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: 600;
            font-size: 12px;
        }}
        QPushButton:hover {{ background-color: {_ct["button_hover"]}; }}
        """
    )
    cancel_btn.clicked.connect(on_cancel)
    cancel_btn.setVisible(False)
    button_layout.addWidget(cancel_btn)

    layout.addLayout(button_layout)

    for _field_name, input_widget in metadata_inputs.items():
        if isinstance(input_widget, QCheckBox):
            input_widget.stateChanged.connect(on_field_change)
        elif isinstance(input_widget, QComboBox):
            input_widget.currentTextChanged.connect(on_field_change)
        elif isinstance(input_widget, QLineEdit):
            input_widget.textChanged.connect(on_field_change)

    return form, metadata_inputs, save_btn, cancel_btn


def create_file_info_form(
    dark_mode: bool,
    bundle: dict,
    page_order: list[int],
    current_page_index: int,
    prototype_mode: bool,
) -> QWidget:
    """Build the read-only file information accordion section."""
    theme = get_bundle_colors(dark_mode)

    widget = QWidget()
    widget.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    actual_index = (
        page_order[current_page_index]
        if current_page_index < len(page_order)
        else current_page_index
    )
    if actual_index < len(bundle.get("file_paths", [])):
        file_path = bundle["file_paths"][actual_index]
        filename = Path(file_path).name
        full_path = str(file_path)

        if prototype_mode:
            file_size_str = "1.2 MB"
            modified_str = "2024-03-15 10:30:00"
        else:
            if os.path.exists(file_path):
                file_size_str = BundlePdfConverter.format_file_size(os.path.getsize(file_path))
                modified_str = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            else:
                file_size_str = "Unknown"
                modified_str = "Unknown"

        def add_info_row(label: str, value: str, copyable: bool = False) -> None:
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            lbl = QLabel(f"<b>{label}:</b>")
            lbl.setStyleSheet(f"color: {theme['text_primary']}; font-size: 11px; font-weight: 600;")
            lbl.setMinimumWidth(100)
            row_layout.addWidget(lbl)

            val = QLabel(value)
            if copyable:
                val.setCursor(Qt.CursorShape.PointingHandCursor)
                val.setStyleSheet(
                    f"color: {theme['selected']}; font-size: 11px; background: transparent; "
                    f"text-decoration: underline;"
                )
                val.setToolTip("Click to copy to clipboard")

                def make_copy_handler(text: str):  # noqa: ANN202
                    def copy_to_clipboard(event):  # noqa: ANN001
                        from PyQt6.QtWidgets import QApplication as _QApp

                        _QApp.clipboard().setText(text)
                        original_style = val.styleSheet()
                        val.setStyleSheet(
                            f"color: {theme['success']}; font-size: 11px; background: transparent; "
                            f"text-decoration: underline; font-weight: 700;"
                        )
                        QTimer.singleShot(300, lambda: val.setStyleSheet(original_style))

                    return copy_to_clipboard

                val.mousePressEvent = make_copy_handler(value)  # type: ignore[method-assign]
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


def create_analysis_info_form(
    dark_mode: bool,
    bundle: dict,
    page_order: list[int],
    current_page_index: int,
) -> QWidget:
    """Build the read-only analysis information accordion section."""
    theme = get_bundle_colors(dark_mode)

    widget = QWidget()
    widget.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    actual_index = (
        page_order[current_page_index]
        if current_page_index < len(page_order)
        else current_page_index
    )
    analysis = (
        bundle["analyses"][actual_index] if actual_index < len(bundle.get("analyses", [])) else {}
    )

    def add_info_row(label: str, value: object, value_color: str | None = None) -> None:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel(f"<b>{label}:</b>")
        lbl.setStyleSheet(
            f"color: {theme['text_primary']}; font-size: 11px; font-weight: 600; "
            f"background: transparent;"
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

    confidence = analysis.get("confidence_score", 0.0)
    if isinstance(confidence, int | float):
        confidence_pct = int(confidence * 100 if confidence <= 1.0 else confidence)
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
