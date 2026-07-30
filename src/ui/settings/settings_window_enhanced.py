"""
Enhanced Settings Window for WinScanLLM - Phase 6 Implementation
Comprehensive 5-tab settings interface with multi-provider support
"""

import json
import logging
import os
import sys
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# Import existing components
from config.config_manager import ConfigManager
from db.analysis_db import AnalysisDB
from db.metadata_db import MetadataDB
from llm_providers.ollama_service import OllamaService
from ui.settings.settings_actions import _SettingsActionsMixin
from ui.settings.settings_change_tracker import _ChangeTrackerMixin
from ui.settings.settings_model_loader import _ModelLoaderMixin
from ui.settings.settings_style_dark import get_dark_theme_stylesheet
from ui.settings.settings_style_light import get_light_theme_stylesheet
from ui.settings.settings_tab_appearance import _SettingsTabAppearanceMixin
from ui.settings.settings_tab_database import _SettingsTabDatabaseMixin
from ui.settings.settings_tab_directories import _SettingsTabDirectoriesMixin
from ui.settings.settings_tab_general import _SettingsTabGeneralMixin
from ui.settings.settings_tab_prompts import _SettingsTabPromptsMixin
from ui.settings.settings_tab_provider import _SettingsTabProviderMixin
from ui.theme.styles import show_critical, show_warning

if TYPE_CHECKING:
    from services.logging_service import get_logger
else:
    get_logger = None

logger: logging.Logger | None = None


class EnhancedSettingsWindow(
    _SettingsTabGeneralMixin,
    _SettingsTabProviderMixin,
    _SettingsTabPromptsMixin,
    _SettingsTabDirectoriesMixin,
    _SettingsTabDatabaseMixin,
    _SettingsTabAppearanceMixin,
    _SettingsActionsMixin,
    _ModelLoaderMixin,
    _ChangeTrackerMixin,
    QDialog,
):
    """Enhanced Settings Window with 5-tab interface"""

    def __init__(self, parent=None, analysis_db=None, metadata_db=None):
        try:
            super().__init__(parent)
            self.config_manager = ConfigManager()
            # Use shared database instances when provided (no ownership)
            self._owns_metadata_db = metadata_db is None
            self._owns_analysis_db = analysis_db is None
            self.metadata_db = metadata_db if metadata_db is not None else MetadataDB()
            self.analysis_db = analysis_db if analysis_db is not None else AnalysisDB()

            # Track optimization thread
            self.optimization_thread = None
            self.optimization_prompt_edit = None

            # Track model loading worker
            self.model_loading_worker = None

            # Initialize Ollama service (for backward compatibility)
            timeout = float(self.config_manager.get_setting("Ollama", "timeout", "300"))
            self.ollama_service = OllamaService(
                base_url=self.config_manager.get_setting("Ollama", "base_url"), timeout=timeout
            )

            app_name = self.config_manager.get_setting("GUI", "app_name", "WinScanLLM")
            self.setWindowTitle(f"{app_name} - Settings")
            icon_path = os.path.join("assets", "icon.png")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))

            self.setMinimumWidth(750)
            self.setMinimumHeight(400)

            self._get_logger().debug("Starting _init_ui()...")
            self._init_ui()
            self._get_logger().debug("Settings window initialized successfully")
        except Exception as e:
            self._get_logger().error(f"FATAL ERROR in Settings __init__: {e}", exc_info=True)
            # Show error dialog
            from ui.theme.styles import show_critical

            show_critical(
                None,
                "Settings Window Error",
                f"Failed to initialize settings window:\n\n{e}\n\nCheck logs for details.",
            )
            raise

    def _get_logger(self) -> logging.Logger:
        """Get logger instance (lazy initialization)."""
        global logger
        if logger is None:
            from services.logging_service import get_logger as _get_logger

            logger = _get_logger()
        return logger

    @staticmethod
    def _in_scroll(widget: QWidget) -> QScrollArea:
        """Wrap *widget* in a frameless, vertically-scrollable QScrollArea.

        The scroll area is transparent and suppresses horizontal scrolling so
        the tab content fills the available width and only scrolls vertically
        when the dialog is shorter than its natural content height.
        """
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(widget)
        return scroll

    def _constrain_to_screen(self) -> None:
        """Cap the dialog height to the active monitor's available geometry.

        Called at the start of showEvent so it accounts for the screen the
        window is actually on, including when the user moves it to a different
        monitor before re-opening settings.
        """
        from PyQt6.QtWidgets import QApplication

        screen = self.screen()
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return

        avail_h = screen.availableGeometry().height()
        # Keep a small margin so the window doesn't butt right against the taskbar.
        max_h = max(self.minimumHeight(), avail_h - 40)
        self.setMaximumHeight(max_h)
        if self.height() > max_h:
            self.resize(self.width(), max_h)

    def closeEvent(self, event):  # noqa: N802
        """Clean up resources when window closes."""
        # Wait for optimization thread to finish
        if self.optimization_thread and self.optimization_thread.isRunning():
            self.optimization_thread.requestInterruption()
            self.optimization_thread.wait(3000)

        # Close database connections only if we own them (not injected)
        if (
            hasattr(self, "_owns_metadata_db")
            and self._owns_metadata_db
            and hasattr(self, "metadata_db")
            and self.metadata_db
        ):
            self.metadata_db.close()
        if (
            hasattr(self, "_owns_analysis_db")
            and self._owns_analysis_db
            and hasattr(self, "analysis_db")
            and self.analysis_db
        ):
            self.analysis_db.close()

        event.accept()

    def _get_light_theme_stylesheet(self) -> str:
        """Return the complete light theme stylesheet."""
        return get_light_theme_stylesheet()

    def _get_dark_theme_stylesheet(self) -> str:
        """Return the complete dark theme stylesheet."""
        return get_dark_theme_stylesheet()

    def _apply_theme_stylesheet(self):
        """Read current theme from config and apply appropriate stylesheet."""
        current_theme = self.config_manager.get_setting("Theme", "theme", "light")

        if current_theme == "dark":
            stylesheet = get_dark_theme_stylesheet()
        else:
            stylesheet = get_light_theme_stylesheet()

        self.tabs.setStyleSheet(stylesheet)

        # Apply background to dialog for consistency and scope smaller button sizing
        # to this dialog only so settings buttons are more compact than the
        # global application default.
        if current_theme == "dark":
            self.setStyleSheet("""
                QDialog {
                    background-color: #0B1120;
                }
                QDialogButtonBox {
                    background-color: #0B1120;
                }
                /* Scoped: make buttons inside this dialog slightly smaller */
                QDialog QPushButton {
                    min-height: 32px;
                    padding: 6px 12px;
                    font-size: 10pt;
                }
                /* Compact buttons for inline actions */
                QDialog QPushButton[objectName="compactButton"] {
                    min-height: 32px;
                    padding: 6px 12px;
                    min-width: 88px;
                }
                /* Icon-only small buttons */
                QDialog QPushButton[objectName="iconButton"] {
                    padding: 0px;
                    min-width: 36px;
                    min-height: 36px;
                    border-radius: 6px;
                }
                QDialog QDialogButtonBox QPushButton {
                    min-width: 80px;
                }
                /* Disabled button state - visually distinct */
                QDialog QDialogButtonBox QPushButton:disabled {
                    background-color: #2D2D2D !important;
                    color: #555555 !important;
                    border: 1px solid #3D3D3D !important;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #FFFFFF;
                }
                QDialogButtonBox {
                    background-color: #FFFFFF;
                }
                /* Scoped: make buttons inside this dialog slightly smaller */
                QDialog QPushButton {
                    min-height: 32px;
                    padding: 6px 12px;
                    font-size: 10pt;
                }
                /* Compact buttons for inline actions */
                QDialog QPushButton[objectName="compactButton"] {
                    min-height: 32px;
                    padding: 6px 12px;
                    min-width: 88px;
                }
                /* Icon-only small buttons */
                QDialog QPushButton[objectName="iconButton"] {
                    padding: 0px;
                    min-width: 36px;
                    min-height: 36px;
                    border-radius: 6px;
                }
                QDialog QDialogButtonBox QPushButton {
                    min-width: 80px;
                }
                /* Disabled button state - visually distinct */
                QDialog QDialogButtonBox QPushButton:disabled {
                    background-color: #E5E7EB !important;
                    color: #9CA3AF !important;
                    border: 1px solid #D1D5DB !important;
                }
            """)

    def _init_ui(self):
        """Initialize the tabbed UI"""
        layout = QVBoxLayout(self)

        # Create tab widget
        self.tabs = QTabWidget()

        # Apply theme-based stylesheet
        self._apply_theme_stylesheet()

        # Create tabs — each tab body is wrapped in a QScrollArea so the dialog
        # can be shorter than its natural content height without clipping.
        self.tabs.addTab(self._in_scroll(self._create_general_tab()), "General")
        self.tabs.addTab(self._in_scroll(self._create_llm_provider_tab()), "LLM Provider")
        self.tabs.addTab(self._in_scroll(self._create_prompts_tab()), "Prompts")
        self.tabs.addTab(self._in_scroll(self._create_directories_tab()), "Directories & Discovery")
        self.tabs.addTab(self._in_scroll(self._create_database_tab()), "Database")
        self.tabs.addTab(self._in_scroll(self._create_appearance_tab()), "Appearance")

        layout.addWidget(self.tabs)

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Store reference to Save button for enabling/disabling
        self.save_button = button_box.button(QDialogButtonBox.StandardButton.Save)

        if self.save_button is None:
            self._get_logger().error("Failed to get Save button reference from button box")
            show_critical(self, "Initialization Error", "Failed to get Save button reference")
            return

        try:
            # Initialize change tracking (must be before connecting signals)
            self._original_values = {}
            self._tracking_enabled = False  # Temporarily disable tracking during initialization

            self._get_logger().debug("Capturing original values...")
            # Capture original values first
            self._capture_original_values()
            self._get_logger().debug(f"Captured {len(self._original_values)} original values")

            self._get_logger().debug("Connecting change signals...")
            # Connect signals after capturing values
            self._connect_change_signals()

            # DON'T enable tracking yet - wait for showEvent to recapture final values
            # self._tracking_enabled will be set to True in showEvent()
            if self.save_button:
                self._update_save_button_style(False)
                self._get_logger().debug(
                    f"Save button initialized: enabled={self.save_button.isEnabled()}"
                )
        except Exception as e:
            self._get_logger().error(f"Error during change tracking setup: {e}", exc_info=True)
            show_critical(self, "Initialization Error", f"Failed to setup change tracking:\n\n{e}")
            raise

    def showEvent(self, event):  # noqa: N802
        """Override showEvent to populate model combos from cache on first show."""
        super().showEvent(event)

        # Clamp dialog height to active monitor on every show (handles monitor switches).
        self._constrain_to_screen()

        # Only do this on first show
        if not hasattr(self, "_first_show_done"):
            self._first_show_done = True
            self._get_logger().debug("showEvent: First show - populating models from cache")

            # Populate model combos from cache or hardcoded defaults (no network calls)
            self._load_ollama_models(cache_only=True)
            self._load_claude_models(cache_only=True)
            self._load_gemini_models(cache_only=True)

            # Capture original values and enable change tracking
            self._capture_original_values()
            self._tracking_enabled = True
            if self.save_button:
                self._update_save_button_style(False)

    def _on_models_loaded(self, payload: dict):
        """Handle model loading completion (runs on main thread).

        Args:
            payload: Dict with keys "ollama", "claude", "gemini", each containing
                     a list of model name strings fetched by the background worker.
        """
        try:
            self._get_logger().debug("showEvent: Models loaded, populating combos")

            # Populate combo-boxes on the main thread using the pre-fetched data.
            # Use cache_only=True so the widget-updating methods fall back to the
            # just-written cache entries rather than making network calls again.
            self._cache_models("ollama_downloaded", payload.get("ollama", []))
            self._cache_models("claude", payload.get("claude", []))
            self._cache_models("gemini", payload.get("gemini", []))

            self._load_ollama_models(cache_only=True)
            self._load_claude_models(cache_only=True)
            self._load_gemini_models(cache_only=True)

            # Capture final state with all models loaded
            self._capture_original_values()
            self._get_logger().debug(
                f"showEvent: Captured {len(self._original_values)} original values"
            )

            # Enable tracking and disable button
            self._tracking_enabled = True
            if self.save_button:
                self._update_save_button_style(False)
                self._get_logger().debug(
                    f"showEvent: Button disabled, enabled={self.save_button.isEnabled()}"
                )
        finally:
            # Hide loading overlay
            self._hide_loading_overlay()

    def _on_model_loading_error(self, error_msg: str):
        """Handle model loading errors (runs on main thread)"""
        self._get_logger().error(f"Model loading failed: {error_msg}")
        self._hide_loading_overlay()
        show_warning(
            self,
            "Model Loading Error",
            f"Failed to load some models:\n\n{error_msg}\n\nYou can still use the settings window.",
        )

    def _show_loading_overlay(self):
        """Show a loading overlay while models are being loaded."""
        from PyQt6.QtCore import Qt

        if not hasattr(self, "_loading_overlay"):
            self._loading_overlay = QLabel("Loading models...", self)
            self._loading_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._loading_overlay.setStyleSheet("""
                QLabel {
                    background-color: rgba(30, 30, 30, 200);
                    color: #FFFFFF;
                    font-size: 14pt;
                    font-weight: 600;
                    border-radius: 8px;
                    padding: 20px;
                }
            """)
            self._loading_overlay.setFixedSize(200, 80)

        # Center the overlay
        overlay_x = (self.width() - self._loading_overlay.width()) // 2
        overlay_y = (self.height() - self._loading_overlay.height()) // 2
        self._loading_overlay.move(overlay_x, overlay_y)

        self._loading_overlay.raise_()
        self._loading_overlay.show()

    def _hide_loading_overlay(self):
        """Hide the loading overlay."""
        if hasattr(self, "_loading_overlay"):
            self._loading_overlay.hide()

    def _run_save_preflight(self) -> None:
        """Check LLM readiness after a save and act on the download policy.

        Gated on ``LLMPreflight/verify_on_save``. A ready config is silent; a
        missing model or unreachable host informs the user. For a missing Ollama
        model the policy decides: ``off`` warns, ``prompt`` asks then downloads
        (with a modal progress dialog), ``auto`` downloads immediately. CLI
        providers cannot download — the user is told to install/select manually.
        """
        if not self.config_manager.get_bool("LLMPreflight", "verify_on_save", True):
            return

        try:
            from services.llm_readiness_service import LLMReadinessService

            service = LLMReadinessService(self.config_manager)
            result = service.check_readiness()
        except Exception as e:  # pragma: no cover - defensive
            self._get_logger().error(f"Save preflight failed: {e}", exc_info=True)
            return

        if result.ok:
            return  # Provider reachable and model present — nothing to say.

        from ui.theme.styles import show_warning

        if not result.reachable:
            show_warning(self, "LLM Not Reachable", result.message)
            return

        # Reachable but the configured model is missing.
        if not result.can_download:
            show_warning(self, "Model Not Available", result.message)
            return

        policy = (
            self.config_manager.get_setting("LLMPreflight", "model_download_policy", "prompt")
            or "prompt"
        ).lower()

        if policy == "off":
            show_warning(self, "Model Missing", result.message)
            return

        if policy == "prompt":
            from PyQt6.QtWidgets import QMessageBox

            answer = QMessageBox.question(
                self,
                "Download Model?",
                f"The model '{result.model}' is not installed on Ollama.\n\n"
                "Download it now? This may be several gigabytes.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                show_warning(
                    self,
                    "Model Missing",
                    f"Model '{result.model}' was not downloaded. "
                    "Analysis may fail until it is installed.",
                )
                return

        # policy == auto, or prompt approved → download with a progress dialog.
        final = self._download_model_with_progress(result.model)

        from ui.theme.styles import show_critical, show_information

        if final is not None and getattr(final, "ok", False):
            show_information(self, "Model Ready", f"Model '{final.model}' is installed and ready.")
        else:
            message = getattr(final, "message", None) or "Model download failed."
            show_critical(self, "Download Failed", message)

    def _download_model_with_progress(self, model_name: str):
        """Download a missing Ollama model off-thread behind a modal progress dialog.

        Returns the post-download ``ReadinessResult`` (or None on worker error).
        The pull runs on ``LLMPreflightWorker`` with policy ``auto`` (approval,
        if any, already happened on the main thread), and a local event loop
        keeps the dialog responsive without blocking the outer event loop.
        """
        from PyQt6.QtCore import QEventLoop, Qt
        from PyQt6.QtWidgets import QProgressDialog

        from services.llm_readiness_worker import LLMPreflightWorker

        progress = QProgressDialog(f"Downloading '{model_name}'…", "", 0, 0, self)
        progress.setWindowTitle("Downloading Model")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)  # A model pull can't be safely interrupted.
        progress.setAutoClose(False)
        progress.setAutoReset(False)

        loop = QEventLoop()
        holder: dict[str, object] = {"result": None}

        worker = LLMPreflightWorker(self.config_manager, "auto")

        def on_progress(text: str) -> None:
            progress.setLabelText(f"Downloading '{model_name}'…\n{text}")

        def on_finished(result: object) -> None:
            holder["result"] = result
            loop.quit()

        def on_error(err: str) -> None:
            self._get_logger().error(f"Model download worker error: {err}")
            loop.quit()

        worker.progress.connect(on_progress)
        worker.result_ready.connect(on_finished)
        worker.error.connect(on_error)
        worker.start()
        progress.show()
        loop.exec()
        worker.wait(2000)
        progress.close()
        return holder["result"]

    def save_settings(self):
        """Save all settings"""
        try:
            # General Tab
            self.config_manager.set_setting(
                "AuditTrail",
                "enabled",
                "true" if self.audit_trail_checkbox.isChecked() else "false",
            )
            self.config_manager.set_setting(
                "GUI",
                "auto_start_analysis",
                "true" if self.auto_start_analysis_checkbox.isChecked() else "false",
            )
            self.config_manager.set_setting(
                "GUI",
                "confirm_before_exit",
                "true" if self.confirm_exit_checkbox.isChecked() else "false",
            )
            self.config_manager.set_setting(
                "GUI",
                "persist_rotation",
                "true" if self.persist_rotation_checkbox.isChecked() else "false",
            )
            self.config_manager.set_setting(
                "Logging",
                "log_sql_statements",
                "true" if self.log_sql_checkbox.isChecked() else "false",
            )
            self.config_manager.set_setting(
                "Updates",
                "check_on_startup",
                "true" if self.check_updates_on_startup_checkbox.isChecked() else "false",
            )
            self.config_manager.set_setting(
                "LLMPreflight",
                "verify_on_startup",
                "true" if self.preflight_verify_startup_checkbox.isChecked() else "false",
            )
            self.config_manager.set_setting(
                "LLMPreflight",
                "verify_on_save",
                "true" if self.preflight_verify_save_checkbox.isChecked() else "false",
            )
            self.config_manager.set_setting(
                "LLMPreflight",
                "model_download_policy",
                self.preflight_policy_combo.currentData(),
            )

            # LLM Provider Tab
            active_provider = self.provider_combo.currentData()
            self.config_manager.set_setting("LLMProvider", "active_provider", active_provider)

            if active_provider == "ollama":
                # Use currentData to get the actual model name (not the display text with download status)
                model_name = (
                    self.ollama_model_combo.currentData() or self.ollama_model_combo.currentText()
                )
                self.config_manager.set_setting("Ollama", "model", model_name)
                self.config_manager.set_setting("Ollama", "base_url", self.ollama_url_edit.text())
                self.config_manager.set_setting(
                    "Ollama", "timeout", str(self.ollama_timeout_spin.value())
                )
            elif active_provider == "claude_cli":
                self.config_manager.set_setting(
                    "ClaudeCLI", "default_model", self.claude_model_combo.currentText()
                )
                self.config_manager.set_setting(
                    "ClaudeCLI", "command_template", self.claude_command_edit.toPlainText()
                )
                self.config_manager.set_setting(
                    "ClaudeCLI", "timeout", str(self.claude_timeout_spin.value())
                )
            elif active_provider == "gemini_cli":
                self.config_manager.set_setting(
                    "GeminiCLI", "default_model", self.gemini_model_combo.currentText()
                )
                self.config_manager.set_setting(
                    "GeminiCLI", "command_template", self.gemini_command_edit.toPlainText()
                )
                self.config_manager.set_setting(
                    "GeminiCLI", "timeout", str(self.gemini_timeout_spin.value())
                )

            # Save prompts
            self.config_manager.set_setting(
                "Prompts", "document_pages", self.pages_prompt_edit.toPlainText()
            )
            self.config_manager.set_setting(
                "Prompts", "document_metadata", self.metadata_prompt_edit.toPlainText()
            )

            # Directories Tab
            directories = [
                self.directories_list.item(i).text() for i in range(self.directories_list.count())
            ]
            self.config_manager.set_setting(
                "SourceDirectories", "directories", json.dumps(directories)
            )
            self.config_manager.set_setting(
                "SourceDirectories",
                "scan_on_startup",
                "true" if self.scan_on_startup_checkbox.isChecked() else "false",
            )
            self.config_manager.set_setting(
                "SourceDirectories",
                "auto_advance_on_empty_discovery",
                "true" if self.auto_advance_on_empty_checkbox.isChecked() else "false",
            )

            # Export Directory
            self.config_manager.set_setting(
                "OutputDirectory", "strategy", self._current_export_strategy()
            )
            self.config_manager.set_setting(
                "OutputDirectory", "global_custom_path", self.export_static_path_edit.text()
            )
            self.config_manager.set_setting(
                "OutputDirectory", "subdirectory_name", self.export_subfolder_name_edit.text()
            )

            # Discovery & Scheduler Tab
            self.config_manager.set_setting(
                "Discovery",
                "enabled",
                "true" if self.discovery_enabled_checkbox.isChecked() else "false",
            )
            self.config_manager.set_setting(
                "Discovery", "interval_minutes", str(self.discovery_interval_spinbox.value())
            )
            self.config_manager.set_setting(
                "Discovery",
                "auto_analyze_after_discovery",
                "true" if self.auto_analyze_checkbox.isChecked() else "false",
            )

            # Appearance Tab
            self.config_manager.set_setting("Theme", "theme", self.theme_combo.currentData())
            png_zoom = self.png_zoom_combo.currentText().lower().replace(" ", "_")
            pdf_zoom = self.pdf_zoom_combo.currentText().lower().replace(" ", "_")
            self.config_manager.set_setting("Theme", "default_zoom_mode_png", png_zoom)
            self.config_manager.set_setting("Theme", "default_zoom_mode_pdf", pdf_zoom)
            self.config_manager.set_setting(
                "Theme", "default_zoom_percent_png", str(self.png_zoom_percent.value())
            )
            self.config_manager.set_setting(
                "Theme", "default_zoom_percent_pdf", str(self.pdf_zoom_percent.value())
            )
            self.config_manager.set_setting(
                "SystemTray",
                "minimize_to_tray",
                "true" if self.minimize_to_tray_checkbox.isChecked() else "false",
            )
            self.config_manager.set_setting(
                "SystemTray",
                "close_to_tray",
                "true" if self.close_to_tray_checkbox.isChecked() else "false",
            )

            # Status History section (Phase 3 / status_history.md §8)
            self.config_manager.set_setting(
                "StatusHistory",
                "display_count",
                str(self.status_history_display_count.value()),
            )
            self.config_manager.set_setting(
                "StatusHistory",
                "retention_days",
                str(self.status_history_retention_days.value()),
            )
            self.config_manager.set_setting(
                "StatusHistory",
                "min_level",
                self.status_history_min_level.currentData(),
            )
            self.config_manager.set_setting(
                "StatusHistory",
                "auto_popup_errors",
                "true" if self.status_history_auto_popup.isChecked() else "false",
            )
            self.config_manager.set_setting(
                "StatusHistory",
                "redact_paths_in_issues",
                "true" if self.status_history_redact_paths.isChecked() else "false",
            )
            # Live-apply the min-level change immediately
            try:
                from services.status_reporter import get_reporter

                get_reporter().set_min_level(self.status_history_min_level.currentData())
            except Exception:
                pass

            from ui.theme.styles import show_information

            show_information(self, "Settings Saved", "Your settings have been saved successfully.")

            # Verify the newly-saved provider/model is actually ready. A good
            # config is silent; a missing model / unreachable host surfaces here.
            self._run_save_preflight()

            # Recapture original values to reset change tracking
            self._tracking_enabled = False  # Temporarily disable tracking
            self._capture_original_values()
            self._tracking_enabled = True  # Re-enable tracking
            self._update_save_button_style(False)

            self.accept()

        except Exception as e:
            from ui.theme.styles import show_critical

            show_critical(self, "Save Failed", f"Failed to save settings:\n\n{e}")


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = EnhancedSettingsWindow()
    window.show()
    sys.exit(app.exec())
