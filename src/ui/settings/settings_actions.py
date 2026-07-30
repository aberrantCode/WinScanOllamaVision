# mypy: disable-error-code=attr-defined
"""Action handler mixin for EnhancedSettingsWindow."""

from typing import cast

from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QMessageBox,
    QPlainTextEdit,
    QWidget,
)

from ui.settings.settings_workers import PromptComparisonDialog, PromptOptimizationThread
from ui.theme.styles import show_critical, show_information, show_question, show_warning


class _SettingsActionsMixin:
    """Mixin providing action handlers for the settings window."""

    def _on_provider_changed(self):
        """Update visible provider settings panel and reload models"""
        provider = self.provider_combo.currentData()

        # Safety check - ensure widgets are created before switching
        if not hasattr(self, "provider_stack"):
            return

        # Use QStackedWidget's setCurrentWidget for proper switching
        if provider == "ollama" and hasattr(self, "ollama_settings_widget"):
            self.provider_stack.setCurrentWidget(self.ollama_settings_widget)
            # Reload Ollama models when switching to Ollama
            if hasattr(self, "ollama_model_combo"):
                self._load_ollama_models()
        elif provider == "claude_cli" and hasattr(self, "claude_settings_widget"):
            self.provider_stack.setCurrentWidget(self.claude_settings_widget)
            # Reload Claude models when switching to Claude
            if hasattr(self, "claude_model_combo"):
                self._load_claude_models()
        elif provider == "gemini_cli" and hasattr(self, "gemini_settings_widget"):
            self.provider_stack.setCurrentWidget(self.gemini_settings_widget)
            # Reload Gemini models when switching to Gemini
            if hasattr(self, "gemini_model_combo"):
                self._load_gemini_models()

    def _validate_ollama_connection(self) -> None:
        """Test the currently-entered (not necessarily saved) Ollama base URL
        and model combination, without requiring Save first.

        Uses OllamaProvider.test_connection() against a transient provider
        built from the in-progress form values, then — if reachable — checks
        the selected model is actually present so a typo'd or not-yet-pulled
        model is caught, not just server reachability.
        """
        from llm_providers.ollama_provider import OllamaProvider

        base_url = self.ollama_url_edit.text().strip()
        model = (self.ollama_model_combo.currentData() or "").strip()
        timeout = self.ollama_timeout_spin.value()

        if not base_url:
            self.ollama_validate_status_label.setText("⚠ Enter a base URL first")
            return

        self.ollama_validate_status_label.setText("Testing…")
        from PyQt6.QtWidgets import QApplication

        QApplication.processEvents()

        try:
            provider = OllamaProvider({"base_url": base_url, "timeout": timeout, "model": model})
            if not provider.test_connection():
                self.ollama_validate_status_label.setText(f"✗ Could not reach {base_url}")
                return

            if model:
                available = provider.get_available_models()
                if not any(m.startswith(model) for m in available):
                    self.ollama_validate_status_label.setText(
                        f"⚠ Connected, but '{model}' is not downloaded"
                    )
                    return

            self.ollama_validate_status_label.setText(
                f"✓ Connected — {model or 'server reachable'}"
            )
        except Exception as e:
            self.ollama_validate_status_label.setText(f"✗ Validation failed: {e}")

    def _optimize_prompt(self, prompt_edit: QPlainTextEdit):
        """Use AI to optimize a prompt"""
        current_prompt = prompt_edit.toPlainText().strip()

        # Validation
        if not current_prompt:
            show_warning(
                self,
                "Empty Prompt",
                "Cannot optimize an empty prompt. Please enter a prompt first.",
            )
            return

        # Get active provider info
        try:
            active_provider = self.config_manager.get_active_provider()
            provider_display_name = {
                "ollama": "Ollama",
                "claude_cli": "Claude CLI",
                "gemini_cli": "Gemini CLI",
            }.get(active_provider, active_provider)
        except Exception as e:
            show_critical(self, "Configuration Error", f"Failed to get active provider: {str(e)}")
            return

        # Confirm action
        reply = show_question(
            self,
            "Optimize Prompt",
            f"This will send your current prompt to {provider_display_name} for optimization.\n\n"
            "The AI will suggest improvements while preserving JSON schema requirements.\n\n"
            "Continue?",
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Store reference to the prompt edit widget
        self.optimization_prompt_edit = prompt_edit

        # Create and show progress dialog
        progress = QMessageBox(cast(QWidget, self))
        progress.setWindowTitle("Optimizing Prompt")
        progress.setText(
            "Sending prompt to LLM for optimization...\n\nThis may take 10-60 seconds."
        )
        progress.setIcon(QMessageBox.Icon.Information)
        progress.setStandardButtons(QMessageBox.StandardButton.NoButton)
        progress.setModal(True)
        progress.show()

        # Process events to show dialog
        from PyQt6.QtWidgets import QApplication

        QApplication.processEvents()

        # Create and start optimization thread
        self.optimization_thread = PromptOptimizationThread(self.config_manager, current_prompt)
        self.optimization_thread.finished.connect(
            lambda success, optimized, error: self._handle_optimization_result(
                success, optimized, error, progress
            )
        )
        self.optimization_thread.start()

    def _handle_optimization_result(
        self, success: bool, optimized_prompt: str, error_message: str, progress_dialog: QMessageBox
    ):
        """Handle the result of prompt optimization"""
        # Close progress dialog
        progress_dialog.close()

        if not success:
            # Show error message
            error_detail = error_message if error_message else "Unknown error"

            # Check for common error patterns
            if "analyze_images" in error_detail.lower() and "image" in error_detail.lower():
                error_detail += (
                    "\n\nNote: The current provider may require image inputs. "
                    "Text-only optimization is not supported by this provider."
                )
            elif "timeout" in error_detail.lower():
                error_detail += (
                    "\n\nThe request timed out. Try increasing the timeout in provider settings."
                )
            elif "connection" in error_detail.lower():
                error_detail += (
                    "\n\nCannot connect to the LLM provider. Please check your configuration."
                )

            show_critical(
                self, "Optimization Failed", f"Failed to optimize prompt:\n\n{error_detail}"
            )
            return

        # Validate optimized prompt
        if not optimized_prompt or not optimized_prompt.strip():
            show_warning(
                self,
                "Invalid Response",
                "The LLM returned an empty response. Please try again or edit manually.",
            )
            return

        # Show comparison dialog
        original_prompt = self.optimization_prompt_edit.toPlainText()
        comparison_dialog = PromptComparisonDialog(original_prompt, optimized_prompt, self)

        if comparison_dialog.exec() == QDialog.DialogCode.Accepted:
            # User accepted the optimization
            final_prompt = comparison_dialog.get_final_prompt()
            self.optimization_prompt_edit.setPlainText(final_prompt)

            show_information(
                self,
                "Prompt Updated",
                "The prompt has been updated with the optimized version.\n\n"
                "Don't forget to click 'OK' to save your settings.",
            )
        # else: User cancelled, do nothing

    def _add_directory(self):
        """Add a new directory to the list"""
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            # Check if already in list
            for i in range(self.directories_list.count()):
                if self.directories_list.item(i).text() == directory:
                    show_information(
                        self, "Already Added", "This directory is already in the list."
                    )
                    return

            self.directories_list.addItem(directory)

    def _remove_directory(self):
        """Remove selected directory from list"""
        current_item = self.directories_list.currentItem()
        if current_item:
            reply = show_question(
                self,
                "Remove Directory",
                f"Remove this directory from monitoring?\n\n{current_item.text()}",
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.directories_list.takeItem(self.directories_list.currentRow())

    def _show_database_statistics(self):
        """Display database statistics"""
        try:
            # Get statistics from both databases
            metadata_stats = self.metadata_db.get_statistics()
            analysis_stats = self.analysis_db.get_extended_statistics()

            stats_text = "=== Database Statistics ===\n\n"

            stats_text += "Metadata Cache:\n"
            stats_text += f"  Active Files: {metadata_stats.get('active_count', 0)}\n"
            stats_text += f"  Archived Files: {metadata_stats.get('archived_count', 0)}\n"
            stats_text += f"  Total Size: {metadata_stats.get('database_size_mb', 0):.2f} MB\n\n"

            stats_text += "Analysis Data:\n"
            stats_text += f"  Analyzed Pages: {analysis_stats.get('total_analyzed_pages', 0)}\n"
            stats_text += f"  Cache Hits: {analysis_stats.get('total_cache_hits', 0)}\n"
            stats_text += f"  Providers Used: {analysis_stats.get('unique_providers', 0)}\n"
            stats_text += (
                f"  Bundle Suggestions: {analysis_stats.get('total_bundle_suggestions', 0)}\n"
            )
            stats_text += (
                f"  High Confidence Bundles: {analysis_stats.get('high_confidence_bundles', 0)}\n"
            )

            self.stats_text.setPlainText(stats_text)

        except Exception as e:
            self.stats_text.setPlainText(f"Error loading statistics: {e}")

    def _backup_database(self):
        """Create database backup"""
        try:
            backup_path = self.metadata_db.create_backup()
            show_information(
                self, "Backup Created", f"Database backup created successfully:\n\n{backup_path}"
            )
        except Exception as e:
            show_critical(self, "Backup Failed", f"Failed to create database backup:\n\n{e}")

    def _purge_data(self, data_type: str):
        """Purge database data"""
        type_names = {
            "cache": "cached metadata",
            "analysis": "analysis results",
            "bundles": "bundle suggestions",
            "all": "ALL DATA",
        }

        reply = show_question(
            self,
            "Confirm Purge",
            f"Are you sure you want to purge {type_names[data_type]}?\n\n"
            "This action cannot be undone!",
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                if data_type == "all":
                    self.analysis_db.purge_all_data()
                    self.metadata_db.purge_all_data()
                elif data_type == "cache":
                    self.metadata_db.purge_cache()
                elif data_type == "analysis":
                    self.analysis_db.purge_analysis_results()
                elif data_type == "bundles":
                    self.analysis_db.purge_bundles()

                show_information(
                    self, "Purge Complete", f"Successfully purged {type_names[data_type]}."
                )
                self._show_database_statistics()  # Refresh stats

            except Exception as e:
                show_critical(self, "Purge Failed", f"Failed to purge data:\n\n{e}")
