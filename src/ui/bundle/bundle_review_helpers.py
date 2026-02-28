"""Module-level helpers for PDF conversion and workflow-completion dialogs.

These functions contain the bodies of three ``BundleReviewWidget`` methods
that were extracted to keep the orchestrator under the 800-line limit.
Each original method is now a one-line delegation wrapper.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from ui.bundle.bundle_colors import get_bundle_colors
from ui.bundle.bundle_pdf_converter import BundlePdfConverter
from ui.theme.styles import Colors, show_critical, show_information, show_question


def show_pdf_conversion(
    parent: QWidget,
    dark_mode: bool,
    bundle: dict,
    metadata: dict,
    on_complete: Callable[[QDialog, dict, dict], None],
) -> None:
    """Show an indeterminate progress dialog then schedule ``on_complete``."""
    progress_dialog = QDialog(parent)
    progress_dialog.setWindowTitle("Converting to PDF")
    progress_dialog.setMinimumWidth(400)
    progress_dialog.setModal(True)

    layout = QVBoxLayout(progress_dialog)
    layout.setContentsMargins(30, 30, 30, 30)
    layout.setSpacing(20)

    icon_label = QLabel("📄")
    icon_label.setStyleSheet("font-size: 48px;")
    icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(icon_label)

    message = QLabel(f"Converting to PDF...\n\n{metadata['output_filename']}")
    message.setStyleSheet("color: white; font-size: 14px;")
    message.setAlignment(Qt.AlignmentFlag.AlignCenter)
    message.setWordWrap(True)
    layout.addWidget(message)

    progress = QProgressBar()
    progress.setMinimum(0)
    progress.setMaximum(0)  # Indeterminate
    _ct = get_bundle_colors(dark_mode)
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
    QTimer.singleShot(2000, lambda: on_complete(progress_dialog, bundle, metadata))


def complete_pdf_conversion(
    parent: QWidget,
    progress_dialog: QDialog,
    bundle: dict,
    metadata: dict,
    prototype_mode: bool,
    page_order: list[int],
    rotation_angle: int,
    pdf_converter: BundlePdfConverter,
    on_accepted: Callable[[dict], None],
    on_next_or_complete: Callable[[], None],
) -> None:
    """Close the progress dialog, show the result, then advance the workflow."""
    progress_dialog.close()

    if prototype_mode:
        result = show_question(
            parent,
            "PDF Created",
            f"✓ PDF created successfully!\n\n{metadata['output_filename']}",
            buttons=QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Ok,
            default_button=QMessageBox.StandardButton.Ok,
        )

        if result == QMessageBox.StandardButton.Open:
            show_information(
                parent,
                "Open PDF",
                f"Would open: {metadata['output_filename']}\n\n(Mock implementation)",
            )

        bundle_with_metadata = {**bundle, **metadata, "page_order": page_order}
        on_accepted(bundle_with_metadata)
        on_next_or_complete()
        return

    # Real conversion
    try:
        ordered_paths = [bundle["file_paths"][i] for i in page_order]
        output_dir = pdf_converter.determine_output_directory(bundle)
        pdf_path = pdf_converter.convert(bundle, metadata, ordered_paths, rotation_angle)

        result = show_question(
            parent,
            "PDF Created",
            f"✓ PDF created successfully!\n\n{metadata['output_filename']}\n\n"
            f"Location: {output_dir}",
            buttons=QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Ok,
            default_button=QMessageBox.StandardButton.Ok,
        )

        if result == QMessageBox.StandardButton.Open:
            pdf_converter.open_pdf(pdf_path)

        bundle_with_metadata = {
            **bundle,
            **metadata,
            "page_order": page_order,
            "pdf_path": pdf_path,
        }
        on_accepted(bundle_with_metadata)
        on_next_or_complete()

    except Exception as e:
        show_critical(
            parent, "PDF Conversion Failed", f"Failed to convert bundle to PDF:\n\n{str(e)}"
        )


def show_completion_summary(
    parent: QWidget,
    accepted: int,
    rejected: int,
    skipped: int,
    total: int,
    on_completed: Callable[[dict], None],
) -> None:
    """Show the workflow-complete summary dialog and call ``on_completed``."""
    summary_text = f"""
Bundle Review Complete!

✓ Accepted: {accepted}
✗ Rejected: {rejected}
⏭ Skipped: {skipped}

Total Reviewed: {accepted + rejected} / {total}
    """.strip()

    show_information(parent, "Workflow Complete", summary_text)

    on_completed(
        {
            "accepted": accepted,
            "rejected": rejected,
            "skipped": skipped,
            "total": total,
        }
    )
