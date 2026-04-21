"""
File Details Dialog Actions Mixin

Provides action handler methods for FileDetailsDialog (save, delete, re-analyze,
format helpers, metadata change tracking, etc.).
"""

from __future__ import annotations

import json
import os
from html import escape as html_escape
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QTransform
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from services.logging_service import get_logger
from ui.file_details.file_details_utils import find_actual_file_path, is_path_confined
from ui.theme.styles import show_critical, show_information, show_question, show_warning

if TYPE_CHECKING:
    from config.config_manager import ConfigManager
    from db.analysis_db import AnalysisDB
    from db.metadata_db import MetadataDB

logger = get_logger()


class _DialogActionsMixin:
    """
    Mixin providing action handler methods for FileDetailsDialog.

    All methods access self.* which resolves correctly via MRO since
    FileDetailsDialog inherits from this mixin alongside QDialog.
    """

    # Attributes declared by the orchestrator class (FileDetailsDialog)
    analysis_db: AnalysisDB
    metadata_db: MetadataDB
    config_manager: ConfigManager
    file_data: dict[str, Any]
    is_dark_mode: bool
    theme_colors: dict[str, str]
    metadata_inputs: dict[str, Any]
    original_metadata_values: dict[str, Any]
    # UI widgets declared by FileDetailsDialog._init_ui
    delete_btn: Any  # QPushButton
    open_doc_btn: Any  # QPushButton
    save_metadata_btn: Any  # QPushButton
    copy_json_btn: Any  # QPushButton
    re_analyze_btn: Any  # QPushButton
    close_btn: Any  # QPushButton
    image_preview: Any  # ImagePreviewWidget
    base_pixmap: Any  # QPixmap | None
    current_rotation: str

    def _format_summary(self) -> str:
        """Format summary information as HTML."""
        html = "<html><body style='font-family: Segoe UI; font-size: 10pt;'>"

        # File Information
        html += "<h3 style='color: #2563eb;'>File Information</h3>"
        html += "<table cellpadding='5'>"
        html += f"<tr><td><b>Filename:</b></td><td>{html_escape(str(self.file_data.get('filename', 'N/A')))}</td></tr>"
        html += f"<tr><td><b>Full Path:</b></td><td>{html_escape(str(self.file_data.get('full_path', 'N/A')))}</td></tr>"
        html += f"<tr><td><b>File Size:</b></td><td>{html_escape(self._format_size(self.file_data.get('file_size')))}</td></tr>"
        html += f"<tr><td><b>Modified:</b></td><td>{html_escape(self._format_dt(self.file_data.get('modified_time')))}</td></tr>"
        html += f"<tr><td><b>File Hash:</b></td><td>{html_escape(str(self.file_data.get('file_hash', 'N/A')))}</td></tr>"
        html += "</table>"

        # Analysis Information
        html += "<h3 style='color: #2563eb;'>Analysis Information</h3>"
        html += "<table cellpadding='5'>"
        html += f"<tr><td><b>Status:</b></td><td>{html_escape(str(self.file_data.get('status', 'N/A')))}</td></tr>"
        html += f"<tr><td><b>Analyzed:</b></td><td>{html_escape(self._format_dt(self.file_data.get('analysis_time')))}</td></tr>"
        html += f"<tr><td><b>Processing Time:</b></td><td>{html_escape(self._format_duration(self.file_data.get('processing_duration')))}</td></tr>"
        html += f"<tr><td><b>Provider:</b></td><td>{html_escape(str(self.file_data.get('provider', 'N/A')))}</td></tr>"
        html += f"<tr><td><b>Model:</b></td><td>{html_escape(str(self.file_data.get('model_used', 'N/A')))}</td></tr>"
        html += f"<tr><td><b>Cached:</b></td><td>{'Yes' if self.file_data.get('cache_hit') else 'No'}</td></tr>"

        if self.file_data.get("error_message"):
            html += f"<tr><td><b>Error:</b></td><td style='color: red;'>{html_escape(str(self.file_data.get('error_message')))}</td></tr>"

        html += "</table>"

        html += "</body></html>"
        return html

    def _format_metadata(self) -> str:
        """Format metadata information as HTML."""
        html = "<html><body style='font-family: Segoe UI; font-size: 10pt;'>"

        html += "<h3 style='color: #2563eb;'>Extracted Metadata</h3>"
        html += "<table cellpadding='5'>"

        confidence = self.file_data.get("confidence", 0)
        try:
            conf_float = float(confidence)
            conf_color = (
                "#16a34a" if conf_float >= 80 else "#ea580c" if conf_float >= 50 else "#dc2626"
            )
            html += f"<tr><td><b>Confidence:</b></td><td style='color: {conf_color}; font-weight: bold;'>{conf_float:.1f}%</td></tr>"
        except (ValueError, TypeError):
            html += f"<tr><td><b>Confidence:</b></td><td>{html_escape(str(confidence))}</td></tr>"

        html += f"<tr><td><b>Company:</b></td><td>{html_escape(str(self.file_data.get('company', 'N/A')))}</td></tr>"
        html += f"<tr><td><b>Document Type:</b></td><td>{html_escape(str(self.file_data.get('document_type', 'N/A')))}</td></tr>"
        html += f"<tr><td><b>Document Date:</b></td><td>{html_escape(str(self.file_data.get('document_date', 'N/A')))}</td></tr>"

        page_num = self.file_data.get("page_number")
        total_pages = self.file_data.get("total_pages")
        if page_num and total_pages:
            html += f"<tr><td><b>Pages:</b></td><td>{html_escape(str(page_num))} of {html_escape(str(total_pages))}</td></tr>"
        elif page_num:
            html += f"<tr><td><b>Page Number:</b></td><td>{html_escape(str(page_num))}</td></tr>"
        elif total_pages:
            html += f"<tr><td><b>Total Pages:</b></td><td>{html_escape(str(total_pages))}</td></tr>"

        html += "</table>"
        html += "</body></html>"
        return html

    def _format_size(self, size: Any) -> str:
        """Format file size."""
        try:
            size = int(size)
            for unit in ["B", "KB", "MB", "GB"]:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        except (ValueError, TypeError):
            return str(size) if size else "N/A"

    def _format_dt(self, dt: Any) -> str:
        """Format datetime (converts UTC to local timezone)."""
        if not dt:
            return "N/A"
        # Simple string conversion for now
        return str(dt)

    def _format_duration(self, duration: Any) -> str:
        """Format duration."""
        if not duration:
            return "N/A"
        try:
            seconds = float(duration)
            if seconds < 1:
                return f"{seconds * 1000:.0f}ms"
            elif seconds < 60:
                return f"{seconds:.1f}s"
            else:
                minutes = int(seconds // 60)
                secs = int(seconds % 60)
                return f"{minutes}m {secs}s"
        except (ValueError, TypeError):
            return str(duration)

    def _copy_json(self):
        """Copy JSON data to clipboard."""
        json_str = json.dumps(self.file_data, indent=2, default=str)
        QApplication.clipboard().setText(json_str)
        show_information(self, "Copied", "JSON data copied to clipboard")

    def _view_document(self):
        """Open the document with the default system viewer."""
        stored_path = self.file_data.get("full_path")
        filename = self.file_data.get("filename")

        if not filename:
            show_warning(
                self, "File Name Not Found", "Could not find the file name for this record."
            )
            return

        # Find actual file path (handles temp path issue)
        file_path = self._find_actual_file_path(stored_path, filename)

        if not file_path:
            show_warning(
                self,
                "File Not Found",
                f"Could not find the file:\n\n{filename}\n\nSearched in configured source directories.",
            )
            return

        # Validate path is confined to configured source directories (C-2)
        source_dirs: list[str] = []
        if self.config_manager:
            source_dirs = self.config_manager.get_directories()
        if not is_path_confined(file_path, source_dirs):
            logger.warning(
                "Blocked os.startfile: path not under configured source directories: %s",
                file_path,
            )
            show_warning(
                self,
                "Access Denied",
                "The file is not located within a configured source directory.",
            )
            return

        try:
            # Open file with default system viewer
            os.startfile(file_path)
        except Exception as e:
            show_critical(self, "Error Opening File", f"Failed to open file:\n\n{str(e)}")

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        """Coerce a value to int, returning None on non-numeric input.

        Used to defend metadata-save against stored strings like ``"N/A"`` or
        ``"unknown"`` that the LLM might return for page fields. A raw int()
        would raise ValueError and abort the entire save, taking rotation
        and legacy-analysis writes with it.
        """
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _save_metadata(self):
        """Save edited metadata back to the database."""
        # Collect values from all metadata input fields
        updated_metadata = {}
        for field_name, input_widget in self.metadata_inputs.items():
            if isinstance(input_widget, QLineEdit):
                value = input_widget.text().strip()
            elif isinstance(input_widget, QComboBox):
                value = input_widget.currentText()
            elif isinstance(input_widget, QCheckBox):
                value = input_widget.isChecked()
                # Always include checkbox values (even False)
                updated_metadata[field_name] = value
                continue
            else:
                continue

            # Only include non-empty values (for text fields)
            if value:
                updated_metadata[field_name] = value

        # NOTE: self.file_data was previously mutated here BEFORE the DB
        # write. If the write failed, the dialog's in-memory state then
        # diverged from the database — closing and reopening the dialog
        # showed values that were never persisted. Defer the merge until
        # after a successful write (see the fresh_updates section below).

        # Save to database - use both databases
        try:
            # Use the database instances passed to constructor
            analysis_db = self.analysis_db
            metadata_db = self.metadata_db

            if analysis_db and metadata_db:
                file_path = self.file_data.get("full_path")

                if file_path:
                    # Prepare metadata dict with standard field names
                    metadata = {
                        "document_type": updated_metadata.get("document_type", ""),
                        "company": updated_metadata.get("company", ""),
                        "document_date": updated_metadata.get("document_date", ""),
                        "page_number": updated_metadata.get("page_number", ""),
                        "total_pages": updated_metadata.get("total_pages", ""),
                        "rotation_needed": updated_metadata.get("rotation_needed", ""),
                        "tax_related": updated_metadata.get("tax_related", False),
                        "output_filename": updated_metadata.get("output_filename", ""),
                        "document_category": updated_metadata.get("document_category", ""),
                    }

                    logger.debug(
                        "[SAVE METADATA] Saving metadata to DB - rotation_needed: '%s'",
                        metadata.get("rotation_needed"),
                    )

                    # Update analysis database (legacy)
                    analysis_db.update_analysis_metadata(file_path, metadata)

                    # Save rotation to image_files table (via MetadataDB)
                    rotation_needed = metadata.get("rotation_needed", "none")
                    rotation_degrees = {
                        "none": 0,
                        "90_cw": 90,
                        "90_ccw": 270,
                        "180": 180,
                    }.get(rotation_needed, 0)
                    logger.debug(
                        "Converted rotation_needed to rotation_degrees: %d",
                        rotation_degrees,
                    )
                    metadata_db.save_rotation(file_path, rotation_degrees)

                    # Update normalized metadata table (user edit) via
                    # MetadataDB. This was previously wrapped in its own
                    # try/except-log-warning block, which caused a silent
                    # partial-save: the first two writes would succeed, this
                    # one would fail, the user would still see "Metadata saved
                    # successfully!" and the normalized table would be stale.
                    # Let the exception propagate to the outer handler so the
                    # user learns the save did not fully complete.
                    metadata_updates = {
                        "company": metadata.get("company"),
                        "document_type": metadata.get("document_type"),
                        "document_date": metadata.get("document_date"),
                        "page_number": self._safe_int(metadata.get("page_number")),
                        "total_pages": self._safe_int(metadata.get("total_pages")),
                        "rotation": rotation_degrees,
                        "tax_related": metadata.get("tax_related", False),
                        "output_filename": metadata.get("output_filename"),
                        "document_category": metadata.get("document_category"),
                    }
                    metadata_db.save_metadata(file_path, metadata_updates)
                    logger.debug("Updated normalized metadata table via MetadataDB (user edit)")

                    # All writes have succeeded — now it is safe to merge the
                    # user-entered values into the dialog's in-memory state.
                    self.file_data = {**self.file_data, **updated_metadata}

                    # Reload fresh data from database to ensure file_data is up-to-date
                    fresh_analysis = analysis_db.get_analysis(file_path)
                    if fresh_analysis:
                        logger.debug(
                            "Reloaded analysis from DB - rotation_needed: %s",
                            fresh_analysis.get("rotation_needed"),
                        )

                        # Rebuild file_data immutably with fresh values from database (H-5)
                        fresh_keys = [
                            "document_type",
                            "company",
                            "document_date",
                            "page_number",
                            "total_pages",
                            "rotation_needed",
                            "tax_related",
                            "confidence",
                            "output_filename",
                            "document_category",
                        ]
                        fresh_updates = {
                            key: fresh_analysis[key] for key in fresh_keys if key in fresh_analysis
                        }
                        self.file_data = {**self.file_data, **fresh_updates}

                        logger.debug(
                            "Updated file_data - rotation_needed: %s",
                            self.file_data.get("rotation_needed"),
                        )

                    # CRITICAL: Also reload rotation from metadata table (authoritative source via MetadataDB)
                    fresh_rotation = metadata_db.get_rotation(file_path)
                    self.file_data = {**self.file_data, "rotation": fresh_rotation}
                    logger.debug(
                        "Reloaded rotation from image_files: %d° (authoritative source)",
                        fresh_rotation,
                    )

                    # Emit signal so parent can refresh its data
                    self.metadata_saved.emit(file_path)

                    show_information(self, "Success", "Metadata saved successfully!")

                    # Update original values to current values (reset change tracking)
                    self._store_original_metadata_values()
                    self._update_save_button_state()
                else:
                    show_warning(
                        self, "Missing File Path", "Cannot save metadata: file path not found."
                    )
            else:
                # Determine which database is missing
                missing_dbs = []
                if not analysis_db:
                    missing_dbs.append("analysis_db")
                if not metadata_db:
                    missing_dbs.append("metadata_db")

                show_warning(
                    self,
                    "Database Not Available",
                    f"Cannot save metadata: {', '.join(missing_dbs)} not available.",
                )

        except Exception as e:
            logger.error("Save metadata failed", exc_info=True)
            show_critical(self, "Save Failed", f"Failed to save metadata:\n\n{str(e)}")

    def _find_actual_file_path(self, stored_path: str | None, filename: str) -> str | None:
        """Find the actual file path, searching source directories if needed."""
        # Resolve config_manager: prefer the one stored on self, then walk
        # parent chain. Cap the walk depth so a buggy parent() override that
        # returns self (or a cycle) cannot hang the UI thread.
        config_manager = getattr(self, "config_manager", None)
        if config_manager is None:
            parent_widget = self.parent()  # type: ignore[attr-defined]
            for _ in range(32):  # Qt widget hierarchies are nowhere near this deep
                if parent_widget is None:
                    break
                if hasattr(parent_widget, "config_manager"):
                    config_manager = parent_widget.config_manager
                    break
                parent_widget = parent_widget.parent() if hasattr(parent_widget, "parent") else None

        source_dirs: list[str] = config_manager.get_directories() if config_manager else []
        return find_actual_file_path(stored_path, filename, source_dirs)

    def _re_analyze(self):
        """Queue this file for re-analysis and close dialog."""
        file_path = self.file_data.get("full_path") or self.file_data.get("filename")
        if not file_path:
            show_warning(self, "No File Path", "Cannot re-analyze: file path not found.")
            return

        # Emit signal to parent (AnalysisStatusWindow will queue the job)
        self.re_analyze_requested.emit(file_path)

        # Close the dialog so user can see analysis progress in main window
        self.accept()

    def _delete_record(self):
        """Delete this record from the database (same as context menu delete)."""
        file_path = self.file_data.get("full_path") or self.file_data.get("filename")
        if not file_path:
            show_warning(self, "No File Path", "Cannot delete: file path not found.")
            return

        # Create custom dialog with checkbox for file deletion
        dialog = QDialog(self)
        dialog.setWindowTitle("Delete Record")
        dialog.setMinimumWidth(450)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)

        # Warning icon and message
        message_layout = QHBoxLayout()
        icon_label = QLabel("⚠️")
        icon_label.setStyleSheet("font-size: 32pt;")
        message_layout.addWidget(icon_label)

        message_text = QLabel(
            f"Delete this record from the database?\n\n"
            f"File: {os.path.basename(file_path)}\n"
            f"Path: {file_path}"
        )
        message_text.setWordWrap(True)
        message_layout.addWidget(message_text, 1)
        layout.addLayout(message_layout)

        # Checkbox for deleting physical file (unchecked by default — safe default, M-7)
        delete_file_checkbox = QCheckBox("Also delete the file from disk")
        delete_file_checkbox.setChecked(False)
        delete_file_checkbox.setStyleSheet("font-weight: 600; color: #DC2626;")
        layout.addWidget(delete_file_checkbox)

        # Warning label
        warning_label = QLabel("⚠️ Warning: Deleting the file from disk cannot be undone!")
        warning_label.setStyleSheet("color: #DC2626; font-size: 9pt;")
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #DC2626;
                color: white;
                font-weight: 600;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #B91C1C;
            }
        """)
        delete_btn.clicked.connect(dialog.accept)
        delete_btn.setDefault(True)
        button_layout.addWidget(delete_btn)

        layout.addLayout(button_layout)

        # Show dialog and get result
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # Get checkbox state
        delete_physical_file = delete_file_checkbox.isChecked()

        # Check if we have database access
        if not self.analysis_db:
            show_warning(
                self,
                "Database Not Available",
                "Cannot delete record: database connection not available.",
            )
            return

        try:
            # Delete using the same logic as context menu delete
            # 1. Mark image as deleted in image_files table (soft delete)
            self.analysis_db.mark_image_deleted(file_path)

            # 2. Delete from metadata table
            self.analysis_db.delete_metadata_by_path(file_path)

            # 3. Delete physical file if checkbox was checked
            if delete_physical_file and os.path.exists(file_path):
                # Path confinement check — mirrors the guard on os.startfile in
                # _view_document. Deletion is strictly more dangerous than
                # opening, so it must enforce the same invariant: the path
                # must lie under a configured source directory.
                source_dirs: list[str] = (
                    self.config_manager.get_directories() if self.config_manager else []
                )
                if not is_path_confined(file_path, source_dirs):
                    logger.warning(
                        "Blocked os.remove: path not under configured source directories: %s",
                        file_path,
                    )
                    show_warning(
                        self,
                        "Access Denied",
                        "The database record was removed, but the file on disk was NOT "
                        "deleted because it is not located within a configured source "
                        "directory.",
                    )
                else:
                    try:
                        os.remove(file_path)
                        logger.info("Deleted physical file: %s", file_path)
                    except Exception as file_error:
                        # Show warning but don't fail the whole operation
                        show_warning(
                            self,
                            "File Deletion Failed",
                            f"Database record deleted, but failed to delete the physical file:\n\n{str(file_error)}",
                        )

            # 4. Emit signal to notify parent to refresh
            self.record_deleted.emit(file_path)

            # 5. Close the dialog
            self.accept()

        except Exception as e:
            logger.error("Error deleting record: %s", e, exc_info=True)
            show_critical(self, "Delete Failed", f"Failed to delete record:\n\n{str(e)}")

    # Note: Analysis progress/completion handlers removed - now handled by queue system in AnalysisStatusWindow

    def _set_controls_enabled(self, enabled: bool):
        """Enable or disable all buttons and edit controls."""
        # Buttons
        self.delete_btn.setEnabled(enabled)
        self.open_doc_btn.setEnabled(enabled)
        self.save_metadata_btn.setEnabled(enabled)
        self.copy_json_btn.setEnabled(enabled)
        self.re_analyze_btn.setEnabled(enabled)
        self.close_btn.setEnabled(enabled)

        # Edit controls
        if hasattr(self, "metadata_inputs"):
            for input_widget in self.metadata_inputs.values():
                input_widget.setEnabled(enabled)

    def _update_metadata_fields(self):
        """Update metadata input fields with current file_data values."""
        if not hasattr(self, "metadata_inputs"):
            return

        for field_name, input_widget in self.metadata_inputs.items():
            value = self.file_data.get(field_name, "")

            if isinstance(input_widget, QLineEdit):
                input_widget.setText(str(value) if value else "")
            elif isinstance(input_widget, QComboBox):
                if value:
                    input_widget.setCurrentText(str(value))
            elif isinstance(input_widget, QCheckBox):
                input_widget.setChecked(bool(value))

    def _apply_rotation(self, rotation: str):
        """Apply metadata rotation to the base image (permanent rotation)."""
        if not hasattr(self, "base_pixmap") or self.base_pixmap is None:  # type: ignore[has-type]
            return

        # Update current rotation tracker
        self.current_rotation = rotation

        # Map rotation strings to angles
        rotation_map = {"90_cw": -90, "90_ccw": 90, "180": 180, "none": 0}

        angle = rotation_map.get(rotation, 0)

        # Load the original unrotated pixmap from file
        file_path = self.file_data.get("full_path")
        if file_path and os.path.exists(file_path):
            original = QPixmap(file_path)

            if angle == 0:
                # No rotation - use original directly
                self.base_pixmap = original
            else:
                # Apply metadata rotation to create new base pixmap
                transform = QTransform()
                transform.rotate(angle)
                self.base_pixmap = original.transformed(
                    transform, Qt.TransformationMode.SmoothTransformation
                )

            # Reset and update the image preview widget
            self.image_preview.set_pixmap(self.base_pixmap, apply_fit="window", file_path=file_path)
        else:
            # If file doesn't exist, just update with current pixmap
            self.image_preview.set_pixmap(self.base_pixmap, apply_fit="window")

    def _store_original_metadata_values(self):
        """Store the original values of all metadata fields for change tracking."""
        for field_name, widget in self.metadata_inputs.items():
            if isinstance(widget, QCheckBox):
                self.original_metadata_values[field_name] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                self.original_metadata_values[field_name] = widget.currentText()
            elif isinstance(widget, QLineEdit):
                self.original_metadata_values[field_name] = widget.text()

    def _connect_metadata_change_signals(self):
        """Connect change signals from all metadata input fields."""
        for _field_name, widget in self.metadata_inputs.items():
            if isinstance(widget, QCheckBox):
                widget.stateChanged.connect(self._on_metadata_changed)
            elif isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self._on_metadata_changed)
            elif isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._on_metadata_changed)

    def _on_metadata_changed(self):
        """Handle metadata field changes - update save button state."""
        self._update_save_button_state()

    @staticmethod
    def _normalized_eq(a: Any, b: Any) -> bool:
        """Treat None and '' (and other falsy equivalents) as equal.

        Used by _has_unsaved_changes to avoid flagging a field that went
        from stored NULL to empty string (or vice versa) as a user edit.
        """
        if not a and not b:
            return True
        return bool(a == b)

    def _has_unsaved_changes(self):
        """Check if current metadata values differ from original values."""
        for field_name, widget in self.metadata_inputs.items():
            original_value = self.original_metadata_values.get(field_name)

            if isinstance(widget, QCheckBox):
                current_value = widget.isChecked()
            elif isinstance(widget, QComboBox):
                current_value = widget.currentText()
            elif isinstance(widget, QLineEdit):
                current_value = widget.text()
            else:
                continue

            if not self._normalized_eq(original_value, current_value):
                return True

        return False

    def _update_save_button_state(self):
        """Enable or disable the save button based on whether there are unsaved changes."""
        if hasattr(self, "save_metadata_btn"):
            has_changes = self._has_unsaved_changes()
            self.save_metadata_btn.setEnabled(has_changes)

            # Update button style to show enabled/disabled state
            if has_changes:
                # Enabled state - use blue accent color to draw attention
                self.save_metadata_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {self.theme_colors["accent"]};
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 10px 20px;
                        font-weight: 600;
                        min-height: 36px;
                    }}
                    QPushButton:hover {{
                        background: {self.theme_colors["text_primary"]};
                        color: white;
                    }}
                """)
            else:
                # Disabled state with grayed out text
                disabled_text_color = "#808080" if self.is_dark_mode else "#A0A0A0"
                self.save_metadata_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {self.theme_colors["bg_secondary"]};
                        color: {disabled_text_color};
                        border: 1px solid {self.theme_colors["border"]};
                        border-radius: 6px;
                        padding: 10px 20px;
                        font-weight: 600;
                        min-height: 36px;
                        opacity: 0.6;
                    }}
                    QPushButton:disabled {{
                        color: {disabled_text_color};
                        opacity: 0.6;
                    }}
                """)

    def _check_unsaved_changes_before_close(self):
        """Check for unsaved changes and prompt user. Returns True if OK to close, False otherwise."""
        if self._has_unsaved_changes():
            reply = show_question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save them before closing?",
                buttons=QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                default_button=QMessageBox.StandardButton.Save,
            )

            if reply == QMessageBox.StandardButton.Save:
                # Save the metadata
                self._save_metadata()
                return True
            # Discard -> close without saving; Cancel -> don't close
            return reply == QMessageBox.StandardButton.Discard
        # No unsaved changes, OK to close
        return True
