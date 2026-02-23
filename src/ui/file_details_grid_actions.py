"""
File Details Grid Actions Mixin

Provides action handler methods for FileDetailsGrid (context menu actions,
metadata handling, export, clipboard, delete operations, etc.).
"""
# mypy: disable-error-code=attr-defined

import csv
import os

from PyQt6.QtCore import QModelIndex
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QMenu,
)

from ui.file_details_table_model import FileDetailsTableModel
from ui.styles import show_confirm, show_critical, show_information, show_warning


class _GridActionsMixin:
    """
    Mixin providing action handler methods for FileDetailsGrid.

    All methods access self.* which resolves correctly via MRO since
    FileDetailsGrid inherits from this mixin alongside QWidget.
    """

    def _find_actual_file_path(self, stored_path, filename):
        """Find the actual file path, searching source directories if needed."""
        # First, check if the stored path exists and is not in a temp folder
        if stored_path and os.path.exists(stored_path):
            # Check if it's in a temp folder
            temp_indicators = ["temp", "tmp", "AppData\\Local\\Temp"]
            if not any(indicator in stored_path for indicator in temp_indicators):
                return stored_path

        # If stored path doesn't exist or is in temp, search source directories
        if self.parent() and hasattr(self.parent(), "config_manager"):
            config_manager = self.parent().config_manager
            directories = config_manager.get_directories()

            # Search for the file by name in all source directories
            for directory in directories:
                if not os.path.exists(directory):
                    continue

                for root, _, files in os.walk(directory):
                    if filename in files:
                        found_path = os.path.join(root, filename)
                        if os.path.exists(found_path):
                            return found_path

        return None

    def _view_selected_document(self):
        """Open the selected document with the default system viewer."""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            return

        # Get the first (and should be only) selected row
        index = selection[0]
        source_index = self.proxy_model.mapToSource(index)
        row_data = self.model.get_row_data(source_index.row())

        if not row_data:
            return

        stored_path = row_data.get("full_path")
        filename = row_data.get("filename")

        if not filename:
            show_warning(
                self, "File Name Not Found", "Could not find the file name for this record."
            )
            return

        # Find the actual file path
        file_path = self._find_actual_file_path(stored_path, filename)

        if not file_path:
            show_warning(
                self,
                "File Not Found",
                f"Could not find the file:\n\n{filename}\n\nSearched in configured source directories.",
            )
            return

        try:
            # Open file with default system viewer
            os.startfile(file_path)
        except Exception as e:
            show_critical(self, "Error Opening File", f"Failed to open file:\n\n{str(e)}")

    def _show_details_dialog(self, index: QModelIndex):
        """Show details dialog for double-clicked row."""
        from ui.file_details_dialog import FileDetailsDialog

        source_index = self.proxy_model.mapToSource(index)
        row_data = self.model.get_row_data(source_index.row())

        if row_data:
            dialog = FileDetailsDialog(
                row_data,
                self,
                analysis_db=self.analysis_db,
                metadata_db=self.metadata_db,
                config_manager=self.config_manager,
            )
            dialog.re_analyze_requested.connect(lambda path: self.re_analyze_requested.emit([path]))
            dialog.metadata_saved.connect(self._on_metadata_saved)
            dialog.record_deleted.connect(self._on_record_deleted)
            dialog.exec()

    def _show_column_menu(self, pos):
        """Show column visibility menu."""
        menu = QMenu(self)

        # Get theme colors
        bg_secondary = self.theme_colors.get(
            "bg_secondary", "#151D2F" if self.is_dark_mode else "#FFFFFF"
        )
        text_primary = self.theme_colors.get(
            "text_primary", "#E0E0E0" if self.is_dark_mode else "#111827"
        )
        border = self.theme_colors.get("border", "#2A3550" if self.is_dark_mode else "#E5E7EB")
        accent = self.theme_colors.get("accent", "#3B82F6")

        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {bg_secondary};
                color: {text_primary};
                border: 1px solid {border};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
                background-color: transparent;
            }}
            QMenu::item:selected {{
                background-color: {accent};
                color: white;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {border};
                margin: 4px 8px;
            }}
        """)

        for i, (_, col_name, _) in enumerate(FileDetailsTableModel.COLUMNS):
            action = QAction(col_name, menu)
            action.setCheckable(True)
            action.setChecked(i in self.model.get_visible_columns())
            action.triggered.connect(lambda checked, idx=i: self._toggle_column(idx, checked))
            menu.addAction(action)

        menu.exec(self.table_view.horizontalHeader().mapToGlobal(pos))

    def _toggle_column(self, col_index: int, visible: bool):
        """Toggle column visibility."""
        visible_columns = self.model.get_visible_columns()

        if visible and col_index not in visible_columns:
            visible_columns.append(col_index)
        elif not visible and col_index in visible_columns:
            visible_columns.remove(col_index)

        self.model.set_visible_columns(visible_columns)
        # Save column state when visibility changes
        self._save_column_state()

    def _show_context_menu(self, pos):
        """Show context menu for row actions."""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            return

        menu = QMenu(self)

        # Get theme colors with fallbacks
        bg_secondary = self.theme_colors.get(
            "bg_secondary", "#151D2F" if self.is_dark_mode else "#FFFFFF"
        )
        text_primary = self.theme_colors.get(
            "text_primary", "#E0E0E0" if self.is_dark_mode else "#111827"
        )
        border = self.theme_colors.get("border", "#2A3550" if self.is_dark_mode else "#E5E7EB")
        accent = self.theme_colors.get("accent", "#3B82F6")

        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {bg_secondary};
                color: {text_primary};
                border: 1px solid {border};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
                background-color: transparent;
            }}
            QMenu::item:selected {{
                background-color: {accent};
                color: white;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {border};
                margin: 4px 8px;
            }}
        """)

        # Open Document (only show if single selection)
        if len(selection) == 1:
            open_action = QAction("📄 Open Document", menu)
            open_action.triggered.connect(self._view_selected_document)
            menu.addAction(open_action)
            menu.addSeparator()

        re_analyze_action = QAction("Re-analyze Selected", menu)
        re_analyze_action.triggered.connect(self._re_analyze_selected)
        menu.addAction(re_analyze_action)

        # Check if any selected files have error status
        has_errors = False
        for index in selection:
            source_index = self.proxy_model.mapToSource(index)
            row_data = self.model.get_row_data(source_index.row())
            if row_data:
                status = row_data.get("status", "")
                error_msg = row_data.get("error_message", "")
                if status == "Failed" or error_msg:
                    has_errors = True
                    break

        # Add Clear Error option if any selected files have errors
        if has_errors:
            clear_error_action = QAction("Clear Error", menu)
            clear_error_action.triggered.connect(self._clear_error_for_selected)
            menu.addAction(clear_error_action)

        menu.addSeparator()

        # Status change options
        if len(selection) == 1:
            # Single selection: "Mark Reviewed"
            mark_reviewed_action = QAction("✓ Mark Reviewed", menu)
            mark_reviewed_action.triggered.connect(
                lambda: self._change_status_for_selected("reviewed")
            )
            menu.addAction(mark_reviewed_action)
        else:
            # Multiple selection: "Change Status" submenu
            from db.image_status import ImageStatus

            change_status_menu = QMenu("Change Status", menu)
            change_status_menu.setStyleSheet(menu.styleSheet())  # Apply same theme

            for status in ImageStatus:
                # Format status name for display (e.g., ANALYZED -> Analyzed)
                display_name = status.name.capitalize()
                status_action = QAction(display_name, change_status_menu)
                status_action.triggered.connect(
                    lambda checked=False, s=status.value: self._change_status_for_selected(s)
                )
                change_status_menu.addAction(status_action)

            menu.addMenu(change_status_menu)

        menu.addSeparator()

        export_action = QAction("Export Selected to CSV", menu)
        export_action.triggered.connect(lambda: self._export_csv(selected_only=True))
        menu.addAction(export_action)

        copy_action = QAction("Copy to Clipboard (TSV)", menu)
        copy_action.triggered.connect(self._copy_to_clipboard)
        menu.addAction(copy_action)

        copy_filename_action = QAction("Copy file name", menu)
        copy_filename_action.triggered.connect(self._copy_filename_to_clipboard)
        menu.addAction(copy_filename_action)

        copy_filepath_action = QAction("Copy file path", menu)
        copy_filepath_action.triggered.connect(self._copy_filepath_to_clipboard)
        menu.addAction(copy_filepath_action)

        menu.addSeparator()

        delete_action = QAction("Delete from Database", menu)
        delete_action.triggered.connect(self._delete_selected)
        menu.addAction(delete_action)

        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    def _on_metadata_saved(self, file_path: str):
        """Handle metadata saved signal - refresh the row data for the updated file."""
        from services.logging_service import get_logger

        logger = get_logger()

        if not self.analysis_db:
            return

        # Get fresh analysis from database
        fresh_analysis = self.analysis_db.get_analysis(file_path)
        if not fresh_analysis:
            return

        # Also get the rotation field from metadata table via MetadataDB
        rotation_degrees = self.metadata_db.get_rotation(file_path)
        fresh_analysis["rotation"] = rotation_degrees
        logger.debug(
            f"[GRID UPDATE] Updating row for {file_path} with rotation={rotation_degrees}°"
        )

        # Find and update the row in the model
        for row in range(self.model.rowCount()):
            row_data = self.model.get_row_data(row)
            if row_data and row_data.get("full_path") == file_path:
                # Update the row data with fresh values
                old_rotation = row_data.get("rotation")
                for key, value in fresh_analysis.items():
                    row_data[key] = value
                logger.debug(
                    f"[GRID UPDATE] Row {row} updated: rotation changed from {old_rotation}° to {row_data.get('rotation')}°"
                )

                # Notify model that data changed
                self.model.dataChanged.emit(
                    self.model.index(row, 0), self.model.index(row, self.model.columnCount() - 1)
                )

                # Force proxy model to refresh - critical for view to update
                self.proxy_model.invalidate()

                # Force table view to update display
                self.table_view.viewport().update()

                logger.debug(
                    f"[GRID UPDATE] Emitted dataChanged signal for row {row}, invalidated proxy model"
                )
                break

    def _on_record_deleted(self, file_path: str):
        """Handle record deleted signal - remove the specific row from grid."""
        from services.logging_service import get_logger

        logger = get_logger()

        # Find and remove the row from the model data
        for i, row_data in enumerate(self.model._data):
            if row_data.get("full_path") == file_path:
                # Remove the row from model data
                self.model.beginRemoveRows(self.model.index(i, 0).parent(), i, i)
                self.model._data.pop(i)
                self.model.endRemoveRows()

                logger.debug(f"Removed row for deleted record: {file_path}")
                break

    def _clear_error_for_selected(self):
        """Clear error status for selected files, resetting them to pending."""
        selection = self.table_view.selectionModel().selectedRows()
        files_to_clear = []

        for index in selection:
            source_index = self.proxy_model.mapToSource(index)
            row_data = self.model.get_row_data(source_index.row())
            if row_data:
                status = row_data.get("status", "")
                error_msg = row_data.get("error_message", "")
                if status == "Failed" or error_msg:
                    file_path = row_data.get("full_path") or row_data.get("filename")
                    if file_path:
                        files_to_clear.append((file_path, source_index.row()))

        if not files_to_clear:
            return

        if (
            show_confirm(
                self,
                "Clear Errors",
                f"Reset {len(files_to_clear)} file(s) to pending status?",
                default_cancel=False,
            )
            and self.analysis_db
        ):
            for file_path, row_idx in files_to_clear:
                try:
                    # Reset status to pending in database
                    self.analysis_db.update_analysis_status(file_path, "Pending")

                    # Update the row data in the model
                    row_data = self.model.get_row_data(row_idx)
                    if row_data:
                        row_data["status"] = "Pending"
                        row_data["error_message"] = None
                        # Notify model that data changed
                        self.model.dataChanged.emit(
                            self.model.index(row_idx, 0),
                            self.model.index(row_idx, self.model.columnCount() - 1),
                        )
                except Exception as e:
                    show_warning(
                        self,
                        "Clear Error Failed",
                        f"Failed to clear error for {file_path}:\n\n{str(e)}",
                    )

    def _re_analyze_selected(self):
        """Request re-analysis of selected files."""
        selection = self.table_view.selectionModel().selectedRows()
        file_paths = []

        for index in selection:
            source_index = self.proxy_model.mapToSource(index)
            row_data = self.model.get_row_data(source_index.row())
            if row_data:
                file_path = row_data.get("full_path") or row_data.get("filename")
                if file_path:
                    file_paths.append(file_path)

        if file_paths and show_confirm(
            self,
            "Re-analyze Files",
            f"Re-analyze {len(file_paths)} selected file(s)?",
        ):
            self.re_analyze_requested.emit(file_paths)

    def _export_csv(self, selected_only: bool = False):
        """Export data to CSV file."""
        from PyQt6.QtWidgets import QFileDialog, QWidget

        parent_widget: QWidget | None = self if isinstance(self, QWidget) else None
        file_path, _ = QFileDialog.getSaveFileName(
            parent_widget,
            "Export to CSV",
            "file_analysis.csv",
            "CSV Files (*.csv);;All Files (*.*)",
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                # Write headers
                headers = []
                for col_idx in self.model.get_visible_columns():
                    _, col_name, _ = FileDetailsTableModel.COLUMNS[col_idx]
                    headers.append(col_name)
                writer.writerow(headers)

                # Write data
                if selected_only:
                    indices = self.table_view.selectionModel().selectedRows()
                else:
                    indices = [
                        self.proxy_model.index(row, 0) for row in range(self.proxy_model.rowCount())
                    ]

                for index in indices:
                    source_index = self.proxy_model.mapToSource(index)
                    row_data = self.model.get_row_data(source_index.row())

                    if row_data:
                        row = []
                        for col_idx in self.model.get_visible_columns():
                            col_key, _, _ = FileDetailsTableModel.COLUMNS[col_idx]
                            value = row_data.get(col_key, "")
                            row.append(str(value) if value is not None else "")
                        writer.writerow(row)

            show_information(self, "Export Complete", f"Data exported to {file_path}")

        except Exception as e:
            show_critical(self, "Export Failed", f"Failed to export data: {str(e)}")

    def _copy_to_clipboard(self):
        """Copy selected rows to clipboard as TSV."""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            return

        # Build TSV string
        lines = []

        # Headers
        headers = []
        for col_idx in self.model.get_visible_columns():
            _, col_name, _ = FileDetailsTableModel.COLUMNS[col_idx]
            headers.append(col_name)
        lines.append("\t".join(headers))

        # Data rows
        for index in selection:
            source_index = self.proxy_model.mapToSource(index)
            row_data = self.model.get_row_data(source_index.row())

            if row_data:
                row = []
                for col_idx in self.model.get_visible_columns():
                    col_key, _, _ = FileDetailsTableModel.COLUMNS[col_idx]
                    value = row_data.get(col_key, "")
                    row.append(str(value) if value is not None else "")
                lines.append("\t".join(row))

        tsv_string = "\n".join(lines)
        QApplication.clipboard().setText(tsv_string)

        show_information(self, "Copied", f"{len(selection)} rows copied to clipboard")

    def _copy_filename_to_clipboard(self):
        """Copy selected filenames to clipboard."""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            return

        filenames = []
        for index in selection:
            source_index = self.proxy_model.mapToSource(index)
            row_data = self.model.get_row_data(source_index.row())

            if row_data:
                filename = row_data.get("filename", "")
                if filename:
                    filenames.append(os.path.basename(filename))

        if filenames:
            clipboard_text = ", ".join(filenames)
            QApplication.clipboard().setText(clipboard_text)

    def _copy_filepath_to_clipboard(self):
        """Copy selected file paths to clipboard."""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            return

        file_paths = []
        for index in selection:
            source_index = self.proxy_model.mapToSource(index)
            row_data = self.model.get_row_data(source_index.row())

            if row_data:
                file_path = row_data.get("full_path", "")
                if file_path:
                    file_paths.append(file_path)

        if file_paths:
            clipboard_text = ", ".join(file_paths)
            QApplication.clipboard().setText(clipboard_text)

    def _change_status_for_selected(self, new_status: str):
        """Change status for selected images."""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            return

        # Get database instance from parent chain
        parent_widget = self.parent()
        analysis_db = None

        while parent_widget:
            if hasattr(parent_widget, "analysis_db"):
                analysis_db = parent_widget.analysis_db
                break
            parent_widget = parent_widget.parent() if hasattr(parent_widget, "parent") else None

        if not analysis_db:
            show_warning(
                self,
                "Database Not Available",
                "Cannot update status: database connection not available.",
            )
            return

        # Collect file paths from selected rows
        file_paths = []
        for index in selection:
            source_index = self.proxy_model.mapToSource(index)
            row_data = self.model.get_row_data(source_index.row())
            if row_data and row_data.get("full_path"):
                file_paths.append(row_data["full_path"])

        if not file_paths:
            show_warning(self, "No Records", "No valid records found to update.")
            return

        # Update status in database
        updated_count = 0
        errors = []

        for file_path in file_paths:
            try:
                analysis_db.update_image_status(file_path, new_status)
                updated_count += 1
                # Update just this row in the grid (efficient per-row refresh)
                self._on_metadata_saved(file_path)
            except Exception as e:
                errors.append(f"{file_path}: {str(e)}")

        # Show result message
        if updated_count > 0:
            from db.image_status import ImageStatus

            display_status = ImageStatus(new_status).value
            message = f"Successfully updated {updated_count} image(s) to status '{display_status}'."
            if errors:
                message += f"\n\nErrors ({len(errors)}):\n" + "\n".join(errors[:5])
                if len(errors) > 5:
                    message += f"\n... and {len(errors) - 5} more errors"
            show_information(self, "Status Update Complete", message)
        elif errors:
            show_warning(
                self, "Update Failed", "No records were updated.\n\n" + "\n".join(errors[:10])
            )

    def _delete_selected(self):
        """Delete selected rows from database."""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            return

        if show_confirm(
            self,
            "Delete Records",
            f"Delete {len(selection)} record(s) from the database?\n\nThis will NOT delete the actual files.",
            default_cancel=True,
        ):
            # Get database instances from parent chain
            parent_widget = self.parent()
            analysis_db = None

            while parent_widget:
                if hasattr(parent_widget, "analysis_db"):
                    analysis_db = parent_widget.analysis_db
                    break
                parent_widget = parent_widget.parent() if hasattr(parent_widget, "parent") else None

            if not analysis_db:
                show_warning(
                    self,
                    "Database Not Available",
                    "Cannot delete records: database connection not available.",
                )
                return

            # Collect file paths from selected rows
            file_paths = []
            for index in selection:
                source_index = self.proxy_model.mapToSource(index)
                row_data = self.model.get_row_data(source_index.row())
                if row_data:
                    file_path = row_data.get("full_path")
                    if file_path:
                        file_paths.append(file_path)

            if not file_paths:
                show_warning(self, "No Records", "No valid records found to delete.")
                return

            # Delete from all databases
            deleted_count = 0
            errors = []

            for file_path in file_paths:
                try:
                    # 1. Mark image as deleted in image_files table (soft delete)
                    # This will CASCADE to analysis_results via foreign key
                    analysis_db.mark_image_deleted(file_path)

                    # 2. Delete from metadata table (using AnalysisDB facade)
                    analysis_db.delete_metadata_by_path(file_path)

                    deleted_count += 1
                except Exception as e:
                    errors.append(f"{file_path}: {str(e)}")

            # Refresh the grid by reloading from database
            if hasattr(self.parent(), "_refresh_file_grid"):
                self.parent()._refresh_file_grid()
            else:
                # Fallback: reload current data excluding deleted files
                updated_data = [
                    row for row in self.model._data if row.get("full_path") not in file_paths
                ]
                self.refresh_data(updated_data)

            # Show result message
            if deleted_count > 0:
                message = f"Successfully deleted {deleted_count} record(s) from the database."
                if errors:
                    message += f"\n\nErrors ({len(errors)}):\n" + "\n".join(errors[:5])
                    if len(errors) > 5:
                        message += f"\n... and {len(errors) - 5} more errors"
                show_information(self, "Deletion Complete", message)
            else:
                show_warning(
                    self, "Deletion Failed", "No records were deleted.\n\n" + "\n".join(errors[:10])
                )
