# mypy: disable-error-code=attr-defined
"""Mixin class providing change-tracking for EnhancedSettingsWindow."""

SAVE_BUTTON_ENABLED_STYLE = """
    QPushButton {
        background-color: #2563EB;
        color: #FFFFFF;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 10pt;
        font-weight: 600;
    }
    QPushButton:hover {
        background-color: #1D4ED8;
    }
    QPushButton:pressed {
        background-color: #1E40AF;
    }
"""


class _ChangeTrackerMixin:
    """Mixin that provides change-tracking for settings widgets.

    Expects the host class to have all the widgets set up by _init_ui / the
    create_*_tab factory functions, plus:
        self._original_values  – dict (set up in _init_ui)
        self._tracking_enabled – bool
        self.save_button       – QPushButton | None
        self.config_manager    – ConfigManager
        self._get_logger()     – returns logging.Logger
        self._current_export_strategy() – str helper
    """

    def _capture_original_values(self):
        """Capture the original values of all input widgets for change tracking."""
        try:
            # General tab
            self._original_values["audit_trail"] = self.audit_trail_checkbox.isChecked()
            self._original_values["auto_start_analysis"] = (
                self.auto_start_analysis_checkbox.isChecked()
            )
            self._original_values["confirm_exit"] = self.confirm_exit_checkbox.isChecked()
            self._original_values["persist_rotation"] = self.persist_rotation_checkbox.isChecked()
            self._original_values["log_sql"] = self.log_sql_checkbox.isChecked()
            self._original_values["check_updates_on_startup"] = (
                self.check_updates_on_startup_checkbox.isChecked()
            )

            # LLM Provider tab
            self._original_values["active_provider"] = self.provider_combo.currentData()
            self._original_values["ollama_model"] = (
                self.ollama_model_combo.currentData() or self.ollama_model_combo.currentText()
            )
            self._original_values["ollama_url"] = self.ollama_url_edit.text()
            self._original_values["ollama_timeout"] = self.ollama_timeout_spin.value()
            self._original_values["claude_model"] = self.claude_model_combo.currentText()
            self._original_values["claude_command"] = self.claude_command_edit.toPlainText()
            self._original_values["claude_timeout"] = self.claude_timeout_spin.value()
            self._original_values["gemini_model"] = self.gemini_model_combo.currentText()
            self._original_values["gemini_command"] = self.gemini_command_edit.toPlainText()
            self._original_values["gemini_timeout"] = self.gemini_timeout_spin.value()

            # Prompts tab
            self._original_values["pages_prompt"] = self.pages_prompt_edit.toPlainText()
            self._original_values["metadata_prompt"] = self.metadata_prompt_edit.toPlainText()

            # Directories tab
            directories = []
            for i in range(self.directories_list.count()):
                item = self.directories_list.item(i)
                if item:  # Safety check
                    directories.append(item.text())
            self._original_values["directories"] = directories
            self._original_values["scan_on_startup"] = self.scan_on_startup_checkbox.isChecked()
            self._original_values["auto_advance_on_empty_discovery"] = (
                self.auto_advance_on_empty_checkbox.isChecked()
            )
            self._original_values["export_strategy"] = self._current_export_strategy()
            self._original_values["export_static_path"] = self.export_static_path_edit.text()
            self._original_values["export_subfolder_name"] = self.export_subfolder_name_edit.text()

            # Appearance tab
            self._original_values["theme"] = self.theme_combo.currentData()
            self._original_values["png_zoom_mode"] = self.png_zoom_combo.currentText()
            self._original_values["pdf_zoom_mode"] = self.pdf_zoom_combo.currentText()
            self._original_values["png_zoom_percent"] = self.png_zoom_percent.value()
            self._original_values["pdf_zoom_percent"] = self.pdf_zoom_percent.value()
            self._original_values["minimize_to_tray"] = self.minimize_to_tray_checkbox.isChecked()
            self._original_values["close_to_tray"] = self.close_to_tray_checkbox.isChecked()
        except Exception as e:
            self._get_logger().error(f"Error capturing original values: {e}", exc_info=True)
            # Keep any partially captured values — partial state is better than none

    def _connect_change_signals(self):
        """Connect all input widgets to the change detection method."""
        # General tab
        self.audit_trail_checkbox.stateChanged.connect(self._check_for_changes)
        self.auto_start_analysis_checkbox.stateChanged.connect(self._check_for_changes)
        self.confirm_exit_checkbox.stateChanged.connect(self._check_for_changes)
        self.persist_rotation_checkbox.stateChanged.connect(self._check_for_changes)
        self.log_sql_checkbox.stateChanged.connect(self._check_for_changes)
        self.check_updates_on_startup_checkbox.stateChanged.connect(self._check_for_changes)

        # LLM Provider tab
        self.provider_combo.currentIndexChanged.connect(self._check_for_changes)
        self.ollama_model_combo.currentIndexChanged.connect(self._check_for_changes)
        self.ollama_url_edit.textChanged.connect(self._check_for_changes)
        self.ollama_timeout_spin.valueChanged.connect(self._check_for_changes)
        self.claude_model_combo.currentIndexChanged.connect(self._check_for_changes)
        self.claude_command_edit.textChanged.connect(self._check_for_changes)
        self.claude_timeout_spin.valueChanged.connect(self._check_for_changes)
        self.gemini_model_combo.currentIndexChanged.connect(self._check_for_changes)
        self.gemini_command_edit.textChanged.connect(self._check_for_changes)
        self.gemini_timeout_spin.valueChanged.connect(self._check_for_changes)

        # Prompts tab
        self.pages_prompt_edit.textChanged.connect(self._check_for_changes)
        self.metadata_prompt_edit.textChanged.connect(self._check_for_changes)

        # Directories tab
        self.directories_list.itemChanged.connect(self._check_for_changes)
        # Also need to check when items are added/removed
        self.directories_list.model().rowsInserted.connect(self._check_for_changes)
        self.directories_list.model().rowsRemoved.connect(self._check_for_changes)
        self.scan_on_startup_checkbox.stateChanged.connect(self._check_for_changes)
        self.auto_advance_on_empty_checkbox.stateChanged.connect(self._check_for_changes)
        self.export_static_radio.clicked.connect(self._check_for_changes)
        self.export_subfolder_radio.clicked.connect(self._check_for_changes)
        self.export_beside_radio.clicked.connect(self._check_for_changes)
        self.export_static_path_edit.textChanged.connect(self._check_for_changes)
        self.export_subfolder_name_edit.textChanged.connect(self._check_for_changes)

        # Discovery & Scheduler tab
        self.discovery_enabled_checkbox.stateChanged.connect(self._check_for_changes)
        self.discovery_interval_spinbox.valueChanged.connect(self._check_for_changes)
        self.auto_analyze_checkbox.stateChanged.connect(self._check_for_changes)

        # Appearance tab
        self.theme_combo.currentIndexChanged.connect(self._check_for_changes)
        self.png_zoom_combo.currentIndexChanged.connect(self._check_for_changes)
        self.pdf_zoom_combo.currentIndexChanged.connect(self._check_for_changes)
        self.png_zoom_percent.valueChanged.connect(self._check_for_changes)
        self.pdf_zoom_percent.valueChanged.connect(self._check_for_changes)
        self.minimize_to_tray_checkbox.stateChanged.connect(self._check_for_changes)
        self.close_to_tray_checkbox.stateChanged.connect(self._check_for_changes)

    def _update_save_button_style(self, enabled: bool) -> None:
        """Update the save button's visual style based on enabled state."""
        try:
            if not hasattr(self, "save_button") or not self.save_button:
                return

            self._get_logger().debug(f"_update_save_button_style called with enabled={enabled}")

            current_theme = self.config_manager.get_setting("Theme", "theme", "light")

            if enabled:
                # Enabled style is identical for both themes
                style = SAVE_BUTTON_ENABLED_STYLE
            else:
                # Disabled style (grayed out)
                if current_theme == "dark":
                    style = """
                        QPushButton {
                            background-color: #151D2F;
                            color: #555555;
                            border: 1px solid #3D3D3D;
                            border-radius: 6px;
                            padding: 8px 16px;
                            font-size: 10pt;
                            font-weight: 600;
                        }
                    """
                else:
                    style = """
                        QPushButton {
                            background-color: #E5E7EB;
                            color: #9CA3AF;
                            border: 1px solid #D1D5DB;
                            border-radius: 6px;
                            padding: 8px 16px;
                            font-size: 10pt;
                            font-weight: 600;
                        }
                    """

            self.save_button.setStyleSheet(style)
            self.save_button.setEnabled(enabled)

        except Exception as e:
            self._get_logger().error(f"Error updating save button style: {e}", exc_info=True)

    def _check_for_changes(self):
        """Check if any values have changed from original and enable/disable Save button."""
        try:
            # Don't check during initialization
            if not hasattr(self, "_tracking_enabled") or not self._tracking_enabled:
                return

            # Safety check: ensure original values are captured
            if not self._original_values:
                return

            has_changes = False
            changed_fields = []

            # General tab
            if self.audit_trail_checkbox.isChecked() != self._original_values.get(
                "audit_trail", False
            ):
                has_changes = True
            if self.auto_start_analysis_checkbox.isChecked() != self._original_values.get(
                "auto_start_analysis", False
            ):
                has_changes = True
            if self.confirm_exit_checkbox.isChecked() != self._original_values.get(
                "confirm_exit", False
            ):
                has_changes = True
            if self.persist_rotation_checkbox.isChecked() != self._original_values.get(
                "persist_rotation", True
            ):
                has_changes = True
            if self.log_sql_checkbox.isChecked() != self._original_values.get("log_sql", False):
                has_changes = True
            if self.check_updates_on_startup_checkbox.isChecked() != self._original_values.get(
                "check_updates_on_startup", True
            ):
                has_changes = True

            # LLM Provider tab
            if self.provider_combo.currentData() != self._original_values.get(
                "active_provider", ""
            ):
                has_changes = True

            # Fix: Use currentData() if available, otherwise use currentText(), and compare correctly
            ollama_model_current = (
                self.ollama_model_combo.currentData()
                if self.ollama_model_combo.currentData() is not None
                else self.ollama_model_combo.currentText()
            )
            if ollama_model_current != self._original_values.get("ollama_model", ""):
                has_changes = True
                changed_fields.append(
                    f"ollama_model: '{ollama_model_current}' != '{self._original_values.get('ollama_model', '')}'"
                )
            if self.ollama_url_edit.text() != self._original_values.get("ollama_url", ""):
                has_changes = True
            if self.ollama_timeout_spin.value() != self._original_values.get("ollama_timeout", 0):
                has_changes = True
            if self.claude_model_combo.currentText() != self._original_values.get(
                "claude_model", ""
            ):
                has_changes = True
            if self.claude_command_edit.toPlainText() != self._original_values.get(
                "claude_command", ""
            ):
                has_changes = True
            if self.claude_timeout_spin.value() != self._original_values.get("claude_timeout", 0):
                has_changes = True
            if self.gemini_model_combo.currentText() != self._original_values.get(
                "gemini_model", ""
            ):
                has_changes = True
            if self.gemini_command_edit.toPlainText() != self._original_values.get(
                "gemini_command", ""
            ):
                has_changes = True
            if self.gemini_timeout_spin.value() != self._original_values.get("gemini_timeout", 0):
                has_changes = True

            # Prompts tab
            if self.pages_prompt_edit.toPlainText() != self._original_values.get(
                "pages_prompt", ""
            ):
                has_changes = True
            if self.metadata_prompt_edit.toPlainText() != self._original_values.get(
                "metadata_prompt", ""
            ):
                has_changes = True

            # Directories tab
            current_directories = []
            for i in range(self.directories_list.count()):
                item = self.directories_list.item(i)
                if item:
                    current_directories.append(item.text())
            if current_directories != self._original_values.get("directories", []):
                has_changes = True
                self._get_logger().debug(
                    f"Directories changed: {current_directories} != {self._original_values.get('directories', [])}"
                )
            if self.scan_on_startup_checkbox.isChecked() != self._original_values.get(
                "scan_on_startup", False
            ):
                has_changes = True
            if self.auto_advance_on_empty_checkbox.isChecked() != self._original_values.get(
                "auto_advance_on_empty_discovery", False
            ):
                has_changes = True
            if self._current_export_strategy() != self._original_values.get(
                "export_strategy", "same_as_source"
            ):
                has_changes = True
            if self.export_static_path_edit.text() != self._original_values.get(
                "export_static_path", ""
            ):
                has_changes = True
            if self.export_subfolder_name_edit.text() != self._original_values.get(
                "export_subfolder_name", "PDFs"
            ):
                has_changes = True

            # Appearance tab
            if self.theme_combo.currentData() != self._original_values.get("theme", ""):
                has_changes = True
            if self.png_zoom_combo.currentText() != self._original_values.get("png_zoom_mode", ""):
                has_changes = True
            if self.pdf_zoom_combo.currentText() != self._original_values.get("pdf_zoom_mode", ""):
                has_changes = True
            if self.png_zoom_percent.value() != self._original_values.get("png_zoom_percent", 0):
                has_changes = True
            if self.pdf_zoom_percent.value() != self._original_values.get("pdf_zoom_percent", 0):
                has_changes = True
            if self.minimize_to_tray_checkbox.isChecked() != self._original_values.get(
                "minimize_to_tray", False
            ):
                has_changes = True
            if self.close_to_tray_checkbox.isChecked() != self._original_values.get(
                "close_to_tray", False
            ):
                has_changes = True

            # Log what changed
            if changed_fields:
                self._get_logger().debug(f"Changes detected in {len(changed_fields)} field(s):")
                for field in changed_fields:
                    self._get_logger().debug(f"  - {field}")
            else:
                self._get_logger().debug("No changes detected")

            # Update save button state and style
            self._update_save_button_style(has_changes)
        except Exception as e:
            self._get_logger().error(f"Error checking for changes: {e}", exc_info=True)
            # On error, enable the save button to be safe
            if hasattr(self, "save_button") and self.save_button:
                self._update_save_button_style(True)
