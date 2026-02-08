"""
Enhanced Settings Window for WinScanLLM - Phase 6 Implementation
Comprehensive 5-tab settings interface with multi-provider support
"""

import json
import os
import sys

from PyQt6.QtCore import QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Import existing components
from config.config_manager import ConfigManager
from db.analysis_db import AnalysisDB
from db.metadata_db import MetadataDB
from llm_providers.ollama_service import OllamaService
from llm_providers.provider_factory import ProviderFactory
from services.logging_service import get_logger
from ui.styles import show_critical, show_information, show_question, show_warning

logger = get_logger()


class ExpandablePromptEdit(QPlainTextEdit):
    """Custom text edit that expands based on content"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setMaximumHeight(200)


class PromptOptimizationThread(QThread):
    """Background thread for prompt optimization"""

    finished = pyqtSignal(bool, str, str)  # success, optimized_prompt, error_message

    def __init__(self, config_manager: ConfigManager, current_prompt: str):
        super().__init__()
        self.config_manager = config_manager
        self.current_prompt = current_prompt

    def run(self):
        """Execute prompt optimization in background"""
        try:
            # Get active provider
            active_provider_name = self.config_manager.get_active_provider()
            provider = ProviderFactory.create_from_config_manager(self.config_manager)

            # Create optimization prompt
            optimization_request = (
                "You are an AI prompt engineer. Improve this prompt for better responses from vision models. "
                "Keep the JSON schema requirements intact. Return ONLY the improved prompt.\n\n"
                f"Current prompt:\n{self.current_prompt}"
            )

            # For CLI-based providers (Claude CLI, Gemini CLI), we can try text-only
            # For Ollama vision models, we need a workaround
            if active_provider_name == "ollama":
                # Ollama vision models require images, so we'll create a minimal placeholder
                # We'll use subprocess to call ollama with text-only chat
                import subprocess

                model = provider.get_default_model()
                timeout = provider.get_timeout()

                try:
                    # Use Ollama chat API directly (not vision)
                    # This allows text-only requests
                    result = subprocess.run(
                        ["ollama", "run", model, optimization_request],
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                    )

                    if result.returncode == 0:
                        optimized_prompt = result.stdout.strip()
                        self.finished.emit(True, optimized_prompt, "")
                    else:
                        self.finished.emit(False, "", f"Ollama error: {result.stderr}")

                except subprocess.TimeoutExpired:
                    self.finished.emit(False, "", "Request timed out")
                except Exception as e:
                    self.finished.emit(False, "", f"Ollama execution error: {str(e)}")

            else:
                # For CLI providers (Claude, Gemini), try with empty image list
                # These should handle text-only prompts gracefully
                result = provider.analyze_images(
                    image_paths=[],  # Empty list for text-only
                    prompt=optimization_request,
                    model=None,  # Use default model
                )

                if result["success"]:
                    optimized_prompt = result["response"].strip()
                    self.finished.emit(True, optimized_prompt, "")
                else:
                    self.finished.emit(False, "", result.get("error", "Unknown error"))

        except Exception as e:
            self.finished.emit(False, "", str(e))


class PromptComparisonDialog(QDialog):
    """Dialog to show before/after prompt comparison"""

    def __init__(self, original_prompt: str, optimized_prompt: str, parent=None):
        super().__init__(parent)
        self.original_prompt = original_prompt
        self.optimized_prompt = optimized_prompt
        self.accepted_optimization = False

        self.setWindowTitle("Prompt Optimization - Review Changes")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)

        layout = QVBoxLayout(self)

        # Header
        header = QLabel("Review the optimized prompt. You can accept or cancel the changes.")
        header.setStyleSheet("font-weight: bold; padding: 10px;")
        layout.addWidget(header)

        # Split view
        splitter_layout = QHBoxLayout()

        # Original prompt
        original_group = QGroupBox("Original Prompt")
        original_layout = QVBoxLayout(original_group)
        self.original_text = QPlainTextEdit()
        self.original_text.setPlainText(original_prompt)
        self.original_text.setReadOnly(True)
        original_layout.addWidget(self.original_text)
        splitter_layout.addWidget(original_group)

        # Optimized prompt
        optimized_group = QGroupBox("Optimized Prompt")
        optimized_layout = QVBoxLayout(optimized_group)
        self.optimized_text = QPlainTextEdit()
        self.optimized_text.setPlainText(optimized_prompt)
        self.optimized_text.setReadOnly(False)  # Allow editing
        optimized_layout.addWidget(self.optimized_text)

        edit_hint = QLabel("You can edit the optimized prompt before accepting.")
        edit_hint.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        optimized_layout.addWidget(edit_hint)

        splitter_layout.addWidget(optimized_group)

        layout.addLayout(splitter_layout)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._accept_optimization)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _accept_optimization(self):
        """Accept the optimization (possibly edited)"""
        self.optimized_prompt = self.optimized_text.toPlainText()
        self.accepted_optimization = True
        self.accept()

    def get_final_prompt(self) -> str:
        """Get the final prompt (possibly edited by user)"""
        return self.optimized_prompt


class EnhancedSettingsWindow(QDialog):
    """Enhanced Settings Window with 5-tab interface"""

    def __init__(self, parent=None, analysis_db=None, metadata_db=None):
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
        self.setMinimumHeight(600)
        self._init_ui()

    def closeEvent(self, event):  # noqa: N802
        """Clean up resources when window closes."""
        # Wait for optimization thread to finish
        if self.optimization_thread and self.optimization_thread.isRunning():
            self.optimization_thread.wait(2000)  # Wait up to 2 seconds
            if self.optimization_thread.isRunning():
                self.optimization_thread.terminate()

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
        return """
            /* ===== TAB WIDGET STRUCTURE ===== */
            QTabWidget::pane {
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                background-color: #FFFFFF;
                padding: 0;
            }

            QTabBar::tab {
                background-color: #F3F4F6;
                color: #374151;
                border: 1px solid #E5E7EB;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 20px;
                margin-right: 2px;
                font-weight: 500;
            }

            QTabBar::tab:selected {
                background-color: #FFFFFF;
                color: #111827;
                border-bottom: 2px solid #FFFFFF;
                font-weight: 600;
            }

            QTabBar::tab:hover:!selected {
                background-color: #E5E7EB;
                color: #111827;
            }

            /* ===== CONTENT WIDGETS ===== */
            QTabWidget > QWidget {
                background-color: #FFFFFF;
            }

            QStackedWidget {
                background-color: #FFFFFF;
            }

            QStackedWidget > QWidget {
                background-color: #FFFFFF;
            }

            /* ===== GROUP BOXES ===== */
            QGroupBox {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                margin-top: 16px;
                padding: 16px;
                padding-top: 24px;
                font-weight: 600;
                color: #111827;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                top: 4px;
                padding: 0 8px;
                background-color: #FFFFFF;
                color: #111827;
                font-size: 10pt;
            }

            /* ===== TEXT INPUTS ===== */
            QLineEdit {
                background-color: #FFFFFF;
                border: 2px solid #E5E7EB;
                border-radius: 6px;
                padding: 8px 12px;
                color: #111827;
                font-size: 10pt;
                selection-background-color: #DBEAFE;
                selection-color: #1E40AF;
            }

            QLineEdit:focus {
                border-color: #2563EB;
                background-color: #F0F9FF;
            }

            QLineEdit:hover:!focus {
                border-color: #D1D5DB;
            }

            QLineEdit:disabled {
                background-color: #F3F4F6;
                color: #9CA3AF;
                border-color: #E5E7EB;
            }

            QPlainTextEdit {
                background-color: #FFFFFF;
                border: 2px solid #E5E7EB;
                border-radius: 6px;
                padding: 8px 12px;
                color: #111827;
                font-size: 10pt;
                selection-background-color: #DBEAFE;
                selection-color: #1E40AF;
            }

            QPlainTextEdit:focus {
                border-color: #2563EB;
                background-color: #F0F9FF;
            }

            QPlainTextEdit:hover:!focus {
                border-color: #D1D5DB;
            }

            QTextEdit {
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                padding: 8px;
                color: #111827;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
                selection-background-color: #DBEAFE;
                selection-color: #1E40AF;
            }

            QTextEdit:focus {
                border-color: #2563EB;
            }

            /* ===== DROPDOWNS ===== */
            QComboBox {
                background-color: #FFFFFF;
                border: 2px solid #E5E7EB;
                border-radius: 6px;
                padding: 8px 12px;
                color: #111827;
                font-size: 10pt;
                min-height: 20px;
            }

            QComboBox:hover {
                border-color: #D1D5DB;
            }

            QComboBox:focus {
                border-color: #2563EB;
            }

            QComboBox:disabled {
                background-color: #F3F4F6;
                color: #9CA3AF;
            }

            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }

            QComboBox::down-arrow {
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #6B7280;
                margin-right: 8px;
            }

            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                border: 2px solid #E5E7EB;
                border-radius: 6px;
                selection-background-color: #DBEAFE;
                selection-color: #1E40AF;
                padding: 4px;
                color: #111827;
                outline: none;
            }

            QComboBox QAbstractItemView::item {
                padding: 8px 12px;
                min-height: 24px;
            }

            QComboBox QAbstractItemView::item:hover {
                background-color: #F3F4F6;
            }

            /* ===== SPINBOX ===== */
            QSpinBox {
                background-color: #FFFFFF;
                border: 2px solid #E5E7EB;
                border-radius: 6px;
                padding: 8px 12px;
                color: #111827;
                font-size: 10pt;
            }

            QSpinBox:focus {
                border-color: #2563EB;
            }

            QSpinBox:hover:!focus {
                border-color: #D1D5DB;
            }

            QSpinBox:disabled {
                background-color: #F3F4F6;
                color: #9CA3AF;
            }

            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #F3F4F6;
                border: none;
                border-radius: 3px;
                width: 20px;
            }

            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #E5E7EB;
            }

            QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {
                background-color: #D1D5DB;
            }

            QSpinBox::up-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 5px solid #6B7280;
            }

            QSpinBox::down-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #6B7280;
            }

            /* ===== LABELS ===== */
            QLabel {
                color: #374151;
                background-color: transparent;
            }

            /* ===== CHECKBOXES ===== */
            QCheckBox {
                color: #374151;
                spacing: 8px;
                background-color: transparent;
            }

            QCheckBox:disabled {
                color: #9CA3AF;
            }

            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #D1D5DB;
                border-radius: 4px;
                background-color: #FFFFFF;
            }

            QCheckBox::indicator:hover {
                border-color: #2563EB;
            }

            QCheckBox::indicator:checked {
                background-color: #2563EB;
                border-color: #2563EB;
            }

            QCheckBox::indicator:checked:hover {
                background-color: #1E40AF;
                border-color: #1E40AF;
            }

            QCheckBox::indicator:disabled {
                background-color: #F3F4F6;
                border-color: #E5E7EB;
            }

            /* ===== LIST WIDGETS ===== */
            QListWidget {
                background-color: #FFFFFF;
                border: 2px solid #E5E7EB;
                border-radius: 6px;
                color: #111827;
                padding: 4px;
                outline: none;
            }

            QListWidget:focus {
                border-color: #2563EB;
            }

            QListWidget::item {
                padding: 10px 12px;
                border-radius: 4px;
                color: #111827;
                background-color: #FFFFFF;
            }

            QListWidget::item:alternate {
                background-color: #F9FAFB;
            }

            QListWidget::item:selected {
                background-color: #2563EB;
                color: #FFFFFF;
            }

            QListWidget::item:hover:!selected {
                background-color: #DBEAFE;
            }

            /* ===== BUTTONS ===== */
            /* Per-window styles should avoid broad QPushButton selectors so the
               application-level stylesheet can control sizing. Keep only
               objectName-scoped rules here. */

            QPushButton[objectName="dangerButton"] {
                background-color: #DC2626;
            }

            QPushButton[objectName="dangerButton"]:hover {
                background-color: #B91C1C;
            }

            QPushButton[objectName="dangerButton"]:pressed {
                background-color: #991B1B;
            }

            QPushButton[objectName="secondaryButton"] {
                background-color: #F3F4F6;
                color: #374151;
                border: 1px solid #D1D5DB;
            }

            QPushButton[objectName="secondaryButton"]:hover {
                background-color: #E5E7EB;
                border-color: #9CA3AF;
            }

            /* ===== SCROLL BARS ===== */
            QScrollBar:vertical {
                background-color: #F3F4F6;
                width: 12px;
                border-radius: 6px;
                margin: 0;
            }

            QScrollBar::handle:vertical {
                background-color: #D1D5DB;
                border-radius: 6px;
                min-height: 30px;
                margin: 2px;
            }

            QScrollBar::handle:vertical:hover {
                background-color: #9CA3AF;
            }

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
                background: none;
            }

            QScrollBar:horizontal {
                background-color: #F3F4F6;
                height: 12px;
                border-radius: 6px;
                margin: 0;
            }

            QScrollBar::handle:horizontal {
                background-color: #D1D5DB;
                border-radius: 6px;
                min-width: 30px;
                margin: 2px;
            }

            QScrollBar::handle:horizontal:hover {
                background-color: #9CA3AF;
            }

            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
                background: none;
            }

            QToolTip {
                background-color: #1F2937;
                color: #F9FAFB;
                border: 1px solid #374151;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 9pt;
            }

            QProgressBar {
                background-color: #E5E7EB;
                border: none;
                border-radius: 4px;
                height: 8px;
                text-align: center;
            }

            QProgressBar::chunk {
                background-color: #2563EB;
                border-radius: 4px;
            }
        """

    def _get_dark_theme_stylesheet(self) -> str:
        """Return the complete dark theme stylesheet."""
        return """
            /* ===== TAB WIDGET STRUCTURE ===== */
            QTabWidget::pane {
                border: 1px solid #3D3D3D;
                border-radius: 8px;
                background-color: #1E1E1E;
                padding: 0;
            }

            QTabBar::tab {
                background-color: #252525;
                color: #9CA3AF;
                border: 1px solid #3D3D3D;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 20px;
                margin-right: 2px;
                font-weight: 500;
            }

            QTabBar::tab:selected {
                background-color: #1E1E1E;
                color: #F3F4F6;
                border-bottom: 2px solid #1E1E1E;
                font-weight: 600;
            }

            QTabBar::tab:hover:!selected {
                background-color: #3D3D3D;
                color: #E5E7EB;
            }

            /* ===== CONTENT WIDGETS ===== */
            QTabWidget > QWidget {
                background-color: #1E1E1E;
            }

            QStackedWidget {
                background-color: #1E1E1E;
            }

            QStackedWidget > QWidget {
                background-color: #1E1E1E;
            }

            /* ===== GROUP BOXES ===== */
            QGroupBox {
                background-color: #252525;
                border: 1px solid #3D3D3D;
                border-radius: 8px;
                margin-top: 16px;
                padding: 16px;
                padding-top: 24px;
                font-weight: 600;
                color: #F3F4F6;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                top: 4px;
                padding: 0 8px;
                background-color: #252525;
                color: #F3F4F6;
                font-size: 10pt;
            }

            /* ===== TEXT INPUTS ===== */
            QLineEdit {
                background-color: #2D2D2D;
                border: 2px solid #3D3D3D;
                border-radius: 6px;
                padding: 8px 12px;
                color: #F3F4F6;
                font-size: 10pt;
                selection-background-color: #1E40AF;
                selection-color: #FFFFFF;
            }

            QLineEdit:focus {
                border-color: #3B82F6;
                background-color: #353535;
            }

            QLineEdit:hover:!focus {
                border-color: #4B5563;
            }

            QLineEdit:disabled {
                background-color: #252525;
                color: #6B7280;
                border-color: #3D3D3D;
            }

            QPlainTextEdit {
                background-color: #2D2D2D;
                border: 2px solid #3D3D3D;
                border-radius: 6px;
                padding: 8px 12px;
                color: #F3F4F6;
                font-size: 10pt;
                selection-background-color: #1E40AF;
                selection-color: #FFFFFF;
            }

            QPlainTextEdit:focus {
                border-color: #3B82F6;
                background-color: #353535;
            }

            QPlainTextEdit:hover:!focus {
                border-color: #4B5563;
            }

            QTextEdit {
                background-color: #252525;
                border: 1px solid #3D3D3D;
                border-radius: 6px;
                padding: 8px;
                color: #E5E7EB;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
                selection-background-color: #1E40AF;
                selection-color: #FFFFFF;
            }

            QTextEdit:focus {
                border-color: #3B82F6;
            }

            /* ===== DROPDOWNS ===== */
            QComboBox {
                background-color: #2D2D2D;
                border: 2px solid #3D3D3D;
                border-radius: 6px;
                padding: 8px 12px;
                color: #F3F4F6;
                font-size: 10pt;
                min-height: 20px;
            }

            QComboBox:hover {
                border-color: #4B5563;
            }

            QComboBox:focus {
                border-color: #3B82F6;
            }

            QComboBox:disabled {
                background-color: #252525;
                color: #6B7280;
            }

            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }

            QComboBox::down-arrow {
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #9CA3AF;
                margin-right: 8px;
            }

            QComboBox QAbstractItemView {
                background-color: #2D2D2D;
                border: 2px solid #3D3D3D;
                border-radius: 6px;
                selection-background-color: #1E40AF;
                selection-color: #FFFFFF;
                padding: 4px;
                color: #F3F4F6;
                outline: none;
            }

            QComboBox QAbstractItemView::item {
                padding: 8px 12px;
                min-height: 24px;
            }

            QComboBox QAbstractItemView::item:hover {
                background-color: #3D3D3D;
            }

            /* ===== SPINBOX ===== */
            QSpinBox {
                background-color: #2D2D2D;
                border: 2px solid #3D3D3D;
                border-radius: 6px;
                padding: 8px 12px;
                color: #F3F4F6;
                font-size: 10pt;
            }

            QSpinBox:focus {
                border-color: #3B82F6;
            }

            QSpinBox:hover:!focus {
                border-color: #4B5563;
            }

            QSpinBox:disabled {
                background-color: #252525;
                color: #6B7280;
            }

            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #3D3D3D;
                border: none;
                border-radius: 3px;
                width: 20px;
            }

            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #4B5563;
            }

            QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {
                background-color: #6B7280;
            }

            QSpinBox::up-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 5px solid #9CA3AF;
            }

            QSpinBox::down-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #9CA3AF;
            }

            /* ===== LABELS ===== */
            QLabel {
                color: #E5E7EB;
                background-color: transparent;
            }

            /* ===== CHECKBOXES ===== */
            QCheckBox {
                color: #E5E7EB;
                spacing: 8px;
                background-color: transparent;
            }

            QCheckBox:disabled {
                color: #6B7280;
            }

            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #4B5563;
                border-radius: 4px;
                background-color: #2D2D2D;
            }

            QCheckBox::indicator:hover {
                border-color: #3B82F6;
            }

            QCheckBox::indicator:checked {
                background-color: #3B82F6;
                border-color: #3B82F6;
            }

            QCheckBox::indicator:checked:hover {
                background-color: #60A5FA;
                border-color: #60A5FA;
            }

            QCheckBox::indicator:disabled {
                background-color: #252525;
                border-color: #3D3D3D;
            }

            /* ===== LIST WIDGETS ===== */
            QListWidget {
                background-color: #2D2D2D;
                border: 2px solid #3D3D3D;
                border-radius: 6px;
                color: #F3F4F6;
                padding: 4px;
                outline: none;
            }

            QListWidget:focus {
                border-color: #3B82F6;
            }

            QListWidget::item {
                padding: 10px 12px;
                border-radius: 4px;
                color: #F3F4F6;
                background-color: #2D2D2D;
            }

            QListWidget::item:alternate {
                background-color: #353535;
            }

            QListWidget::item:selected {
                background-color: #3B82F6;
                color: #FFFFFF;
            }

            QListWidget::item:hover:!selected {
                background-color: #3D3D3D;
            }

            /* ===== BUTTONS ===== */
            /* Keep only scoped button overrides here; general sizing comes
               from the application stylesheet (src/ui/style.qss). */

            QPushButton[objectName="dangerButton"] {
                background-color: #EF4444;
            }

            QPushButton[objectName="dangerButton"]:hover {
                background-color: #F87171;
            }

            QPushButton[objectName="dangerButton"]:pressed {
                background-color: #DC2626;
            }

            QPushButton[objectName="secondaryButton"] {
                background-color: #3D3D3D;
                color: #E5E7EB;
                border: 1px solid #4B5563;
            }

            QPushButton[objectName="secondaryButton"]:hover {
                background-color: #4B5563;
                border-color: #6B7280;
            }

            /* ===== SCROLL BARS ===== */
            QScrollBar:vertical {
                background-color: #252525;
                width: 12px;
                border-radius: 6px;
                margin: 0;
            }

            QScrollBar::handle:vertical {
                background-color: #4B5563;
                border-radius: 6px;
                min-height: 30px;
                margin: 2px;
            }

            QScrollBar::handle:vertical:hover {
                background-color: #6B7280;
            }

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
                background: none;
            }

            QScrollBar:horizontal {
                background-color: #252525;
                height: 12px;
                border-radius: 6px;
                margin: 0;
            }

            QScrollBar::handle:horizontal {
                background-color: #4B5563;
                border-radius: 6px;
                min-width: 30px;
                margin: 2px;
            }

            QScrollBar::handle:horizontal:hover {
                background-color: #6B7280;
            }

            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
                background: none;
            }

            QToolTip {
                background-color: #F3F4F6;
                color: #1E1E1E;
                border: 1px solid #9CA3AF;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 9pt;
            }

            QProgressBar {
                background-color: #3D3D3D;
                border: none;
                border-radius: 4px;
                height: 8px;
                text-align: center;
                color: #F3F4F6;
            }

            QProgressBar::chunk {
                background-color: #3B82F6;
                border-radius: 4px;
            }
        """

    def _apply_theme_stylesheet(self):
        """Read current theme from config and apply appropriate stylesheet."""
        current_theme = self.config_manager.get_setting("Theme", "theme", "light")

        if current_theme == "dark":
            stylesheet = self._get_dark_theme_stylesheet()
        else:
            stylesheet = self._get_light_theme_stylesheet()

        self.tabs.setStyleSheet(stylesheet)

        # Apply background to dialog for consistency and scope smaller button sizing
        # to this dialog only so settings buttons are more compact than the
        # global application default.
        if current_theme == "dark":
            self.setStyleSheet("""
                QDialog {
                    background-color: #1E1E1E;
                }
                QDialogButtonBox {
                    background-color: #1E1E1E;
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
            """)

    def _init_ui(self):
        """Initialize the tabbed UI"""
        layout = QVBoxLayout(self)

        # Create tab widget
        self.tabs = QTabWidget()

        # Apply theme-based stylesheet
        self._apply_theme_stylesheet()

        # Create tabs
        self.tabs.addTab(self._create_general_tab(), "General")
        self.tabs.addTab(self._create_llm_provider_tab(), "LLM Provider")
        self.tabs.addTab(self._create_prompts_tab(), "Prompts")
        self.tabs.addTab(self._create_directories_tab(), "Directories")
        self.tabs.addTab(self._create_database_tab(), "Database")
        self.tabs.addTab(self._create_appearance_tab(), "Appearance")

        layout.addWidget(self.tabs)

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _create_general_tab(self) -> QWidget:
        """Tab 1: General Settings"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Scan Folder Group
        scan_group = QGroupBox("Scan Folder")
        scan_layout = QGridLayout(scan_group)

        scan_layout.addWidget(QLabel("Default Scan Folder:"), 0, 0)
        folder_layout = QHBoxLayout()
        self.scan_folder_edit = QLineEdit(
            self.config_manager.get_setting("DocumentProcessing", "scan_folder")
        )
        self.scan_folder_edit.setToolTip(
            "Default folder location for scanning documents.\n"
            "This is where the application will look for image files to analyze.\n"
            "Note: Multiple source directories can be configured in the Directories tab."
        )
        folder_layout.addWidget(self.scan_folder_edit)

        browse_button = QPushButton()
        style = self.style()
        if style is not None:
            browse_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        browse_button.setToolTip("Browse for folder")
        browse_button.clicked.connect(self._browse_scan_folder)
        # Make the icon-only browse button compact
        browse_button.setFixedSize(36, 36)
        browse_button.setIconSize(QSize(18, 18))
        browse_button.setFlat(True)
        browse_button.setObjectName("iconButton")
        folder_layout.addWidget(browse_button)

        scan_layout.addLayout(folder_layout, 0, 1)
        layout.addWidget(scan_group)

        # Audit Trail Group
        audit_group = QGroupBox("Audit Trail")
        audit_layout = QVBoxLayout(audit_group)

        self.audit_trail_checkbox = QCheckBox("Enable Audit Trail Logging")
        self.audit_trail_checkbox.setToolTip(
            "Records all user actions and decisions for compliance and review.\n"
            "Logs include: file operations, metadata edits, bundle accept/reject decisions,\n"
            "and document processing history. Useful for auditing and troubleshooting."
        )
        audit_enabled = self.config_manager.get_setting("AuditTrail", "enabled", "false")
        self.audit_trail_checkbox.setChecked(audit_enabled.lower() == "true")
        audit_layout.addWidget(self.audit_trail_checkbox)

        audit_info = QLabel(
            "When enabled, user actions and decisions will be logged for review.\n"
            "Logs include: file operations, metadata edits, bundle decisions."
        )
        audit_info.setWordWrap(True)
        audit_layout.addWidget(audit_info)

        layout.addWidget(audit_group)

        # Application Behavior Group
        behavior_group = QGroupBox("Application Behavior")
        behavior_layout = QVBoxLayout(behavior_group)

        self.auto_start_analysis_checkbox = QCheckBox("Auto Start Analysis")
        auto_start_enabled = self.config_manager.get_bool("GUI", "auto_start_analysis", False)
        self.auto_start_analysis_checkbox.setChecked(auto_start_enabled)
        self.auto_start_analysis_checkbox.setToolTip(
            "Automatically start analysis when opening the Analysis Status window"
        )
        behavior_layout.addWidget(self.auto_start_analysis_checkbox)

        self.confirm_exit_checkbox = QCheckBox("Confirm Before Exit")
        confirm_exit_enabled = self.config_manager.get_bool("GUI", "confirm_before_exit", True)
        self.confirm_exit_checkbox.setChecked(confirm_exit_enabled)
        self.confirm_exit_checkbox.setToolTip(
            "Show confirmation dialog when closing the application"
        )
        behavior_layout.addWidget(self.confirm_exit_checkbox)

        layout.addWidget(behavior_group)

        layout.addStretch()
        return widget

    def _create_llm_provider_tab(self) -> QWidget:
        """Tab 2: LLM Provider Settings"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Provider Selection Group
        provider_group = QGroupBox("Provider Selection")
        provider_layout = QGridLayout(provider_group)

        provider_layout.addWidget(QLabel("Active Provider:"), 0, 0)
        self.provider_combo = QComboBox()
        self.provider_combo.addItem("Ollama (Local HTTP API)", "ollama")
        self.provider_combo.addItem("Claude CLI", "claude_cli")
        self.provider_combo.addItem("Gemini CLI", "gemini_cli")
        self.provider_combo.setToolTip(
            "Select which LLM provider to use for document analysis.\n\n"
            "• Ollama: Local vision models (free, private, requires Ollama installed)\n"
            "• Claude CLI: Anthropic's Claude via CLI (requires API key and claude command)\n"
            "• Gemini CLI: Google's Gemini via CLI (requires API key and gemini command)\n\n"
            "All providers support vision/multimodal models for analyzing document images."
        )
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self._apply_combobox_chevron_fix(self.provider_combo)
        provider_layout.addWidget(self.provider_combo, 0, 1)

        # Set current provider
        active_provider = self.config_manager.get_active_provider()
        for i in range(self.provider_combo.count()):
            if self.provider_combo.itemData(i) == active_provider:
                self.provider_combo.setCurrentIndex(i)
                break

        layout.addWidget(provider_group)

        # Provider-Specific Settings (use QStackedWidget for proper switching)
        from PyQt6.QtWidgets import QStackedWidget

        self.provider_stack = QStackedWidget()

        # Ollama Settings
        self.ollama_settings_widget = self._create_ollama_settings()
        self.provider_stack.addWidget(self.ollama_settings_widget)

        # Claude CLI Settings
        self.claude_settings_widget = self._create_claude_cli_settings()
        self.provider_stack.addWidget(self.claude_settings_widget)

        # Gemini CLI Settings
        self.gemini_settings_widget = self._create_gemini_cli_settings()
        self.provider_stack.addWidget(self.gemini_settings_widget)

        layout.addWidget(self.provider_stack)

        layout.addStretch()

        # Update visibility based on active provider (must be after tab is fully built)
        self._on_provider_changed()

        return widget

    def _create_ollama_settings(self) -> QWidget:
        """Ollama-specific settings panel"""
        widget = QGroupBox("Ollama Settings")
        widget.setVisible(True)  # Ensure initially visible
        layout = QGridLayout(widget)

        layout.addWidget(QLabel("Model:"), 0, 0)
        self.ollama_model_combo = QComboBox()
        self.ollama_model_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ollama_model_combo.setToolTip(
            "Vision-capable model to use for document analysis.\n\n"
            "Models marked with ✓ are already downloaded and ready to use.\n"
            "Models without ✓ need to be downloaded first (use Download button or 'ollama pull' command).\n\n"
            "Recommended models:\n"
            "• qwen2.5-vl:latest - Best accuracy for document analysis\n"
            "• llava:latest - Good all-around performance\n"
            "• minicpm-v:latest - Fastest for quick processing"
        )
        self._apply_combobox_chevron_fix(self.ollama_model_combo)
        layout.addWidget(self.ollama_model_combo, 0, 1)

        # Model action buttons
        model_buttons = QHBoxLayout()
        refresh_ollama_btn = QPushButton("🔄 Refresh")
        refresh_ollama_btn.clicked.connect(lambda: self._load_ollama_models(force_refresh=True))
        refresh_ollama_btn.setObjectName("compactButton")
        refresh_ollama_btn.setToolTip(
            "Check download status of Ollama models (bypasses 24-hour cache)"
        )
        model_buttons.addWidget(refresh_ollama_btn)

        download_btn = QPushButton("📥 Download")
        download_btn.clicked.connect(self._download_ollama_model)
        download_btn.setObjectName("compactButton")
        download_btn.setToolTip("Download an Ollama model")
        model_buttons.addWidget(download_btn)

        layout.addLayout(model_buttons, 0, 2)

        layout.addWidget(QLabel("Base URL:"), 1, 0)
        self.ollama_url_edit = QLineEdit(
            self.config_manager.get_setting("Ollama", "base_url", "http://localhost:11434")
        )
        self.ollama_url_edit.setToolTip(
            "HTTP endpoint for the Ollama server.\n\n"
            "Default: http://localhost:11434 (local Ollama instance)\n\n"
            "Change this if:\n"
            "• Ollama is running on a different port\n"
            "• Using a remote Ollama server\n"
            "• Using Ollama behind a proxy"
        )
        layout.addWidget(self.ollama_url_edit, 1, 1, 1, 2)

        layout.addWidget(QLabel("Timeout (seconds):"), 2, 0)
        self.ollama_timeout_spin = QSpinBox()
        self.ollama_timeout_spin.setMinimum(10)
        self.ollama_timeout_spin.setMaximum(600)
        self.ollama_timeout_spin.setValue(
            int(self.config_manager.get_setting("Ollama", "timeout", "300"))
        )
        self.ollama_timeout_spin.setToolTip(
            "Maximum time to wait for Ollama to respond (in seconds).\n\n"
            "Vision model processing can take time, especially for:\n"
            "• Complex documents with lots of text\n"
            "• Larger models (13B, 34B parameters)\n"
            "• Systems with limited GPU/CPU resources\n\n"
            "Default: 300 seconds (5 minutes)\n"
            "Increase if you get timeout errors during analysis."
        )
        layout.addWidget(self.ollama_timeout_spin, 2, 1)

        # Load Ollama models asynchronously after window is shown
        # This prevents the blank window issue during initialization
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(0, self._load_ollama_models)

        return widget

    def _create_claude_cli_settings(self) -> QWidget:
        """Claude CLI-specific settings panel"""
        widget = QGroupBox("Claude CLI Settings")
        layout = QGridLayout(widget)

        layout.addWidget(QLabel("Model:"), 0, 0)
        self.claude_model_combo = QComboBox()
        self.claude_model_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.claude_model_combo.setToolTip(
            "Claude vision-capable model to use for document analysis.\n\n"
            "Model list is automatically fetched from the web (updated daily).\n"
            "Click Refresh to get the latest available models.\n\n"
            "Recommended models:\n"
            "• claude-3-5-sonnet-20241022 - Best balance of speed and accuracy\n"
            "• claude-3-opus-20240229 - Highest accuracy (slower, more expensive)\n"
            "• claude-3-5-haiku-20241022 - Fastest and most cost-effective"
        )
        self._apply_combobox_chevron_fix(self.claude_model_combo)
        layout.addWidget(self.claude_model_combo, 0, 1)

        refresh_claude_btn = QPushButton("🔄 Refresh")
        refresh_claude_btn.clicked.connect(lambda: self._load_claude_models(force_refresh=True))
        refresh_claude_btn.setObjectName("compactButton")
        refresh_claude_btn.setToolTip(
            "Search web for latest Claude vision models (bypasses 24-hour cache)"
        )
        layout.addWidget(refresh_claude_btn, 0, 2)

        # Load Claude models asynchronously
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(0, self._load_claude_models)

        layout.addWidget(QLabel("Command Template:"), 1, 0, Qt.AlignmentFlag.AlignTop)
        self.claude_command_edit = QPlainTextEdit()
        self.claude_command_edit.setMaximumHeight(60)
        self.claude_command_edit.setPlainText(
            self.config_manager.get_setting("ClaudeCLI", "command_template", "")
        )
        self.claude_command_edit.setToolTip(
            "Command template for invoking the Claude CLI.\n\n"
            "Available variables:\n"
            "• %MODEL% - Replaced with selected model name\n"
            "• %IMAGE_PATHS% - Replaced with space-separated image file paths\n"
            "• %PROMPT% - Replaced with the analysis prompt\n\n"
            "Example:\n"
            "claude --model %MODEL% -p %PROMPT% %IMAGE_PATHS%\n\n"
            "The template defines how the application calls the claude command."
        )
        layout.addWidget(self.claude_command_edit, 1, 1)

        template_help = QLabel("Variables: %MODEL%, %IMAGE_PATHS%, %PROMPT%")
        layout.addWidget(template_help, 2, 1)

        layout.addWidget(QLabel("Timeout (seconds):"), 3, 0)
        self.claude_timeout_spin = QSpinBox()
        self.claude_timeout_spin.setMinimum(10)
        self.claude_timeout_spin.setMaximum(600)
        self.claude_timeout_spin.setValue(
            int(self.config_manager.get_setting("ClaudeCLI", "timeout", "300"))
        )
        self.claude_timeout_spin.setToolTip(
            "Maximum time to wait for Claude CLI to respond (in seconds).\n\n"
            "Factors affecting response time:\n"
            "• Network latency to Anthropic's API\n"
            "• Model processing time (Opus slower than Haiku)\n"
            "• Document complexity and image size\n\n"
            "Default: 300 seconds (5 minutes)\n"
            "Increase if you get timeout errors during analysis."
        )
        layout.addWidget(self.claude_timeout_spin, 3, 1)

        return widget

    def _create_gemini_cli_settings(self) -> QWidget:
        """Gemini CLI-specific settings panel"""
        widget = QGroupBox("Gemini CLI Settings")
        layout = QGridLayout(widget)

        layout.addWidget(QLabel("Model:"), 0, 0)
        self.gemini_model_combo = QComboBox()
        self.gemini_model_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.gemini_model_combo.setToolTip(
            "Gemini vision-capable model to use for document analysis.\n\n"
            "Model list is automatically fetched from the web (updated daily).\n"
            "Click Refresh to get the latest available models.\n\n"
            "Recommended models:\n"
            "• gemini-2.0-flash-exp - Latest experimental model (fastest)\n"
            "• gemini-1.5-pro - Best accuracy and reasoning\n"
            "• gemini-1.5-flash - Good balance of speed and accuracy"
        )
        self._apply_combobox_chevron_fix(self.gemini_model_combo)
        layout.addWidget(self.gemini_model_combo, 0, 1)

        refresh_gemini_btn = QPushButton("🔄 Refresh")
        refresh_gemini_btn.clicked.connect(lambda: self._load_gemini_models(force_refresh=True))
        refresh_gemini_btn.setObjectName("compactButton")
        refresh_gemini_btn.setToolTip(
            "Search web for latest Gemini vision models (bypasses 24-hour cache)"
        )
        layout.addWidget(refresh_gemini_btn, 0, 2)

        # Load Gemini models asynchronously
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(0, self._load_gemini_models)

        layout.addWidget(QLabel("Command Template:"), 1, 0, Qt.AlignmentFlag.AlignTop)
        self.gemini_command_edit = QPlainTextEdit()
        self.gemini_command_edit.setMaximumHeight(60)
        self.gemini_command_edit.setPlainText(
            self.config_manager.get_setting("GeminiCLI", "command_template", "")
        )
        self.gemini_command_edit.setToolTip(
            "Command template for invoking the Gemini CLI.\n\n"
            "Available variables:\n"
            "• %MODEL% - Replaced with selected model name\n"
            "• %IMAGE_PATHS% - Replaced with space-separated image file paths\n"
            "• %PROMPT% - Replaced with the analysis prompt\n\n"
            "Example:\n"
            "gemini --model %MODEL% -p %PROMPT% %IMAGE_PATHS%\n\n"
            "The template defines how the application calls the gemini command."
        )
        layout.addWidget(self.gemini_command_edit, 1, 1)

        template_help = QLabel("Variables: %MODEL%, %IMAGE_PATHS%, %PROMPT%")
        layout.addWidget(template_help, 2, 1)

        layout.addWidget(QLabel("Timeout (seconds):"), 3, 0)
        self.gemini_timeout_spin = QSpinBox()
        self.gemini_timeout_spin.setMinimum(10)
        self.gemini_timeout_spin.setMaximum(600)
        self.gemini_timeout_spin.setValue(
            int(self.config_manager.get_setting("GeminiCLI", "timeout", "300"))
        )
        self.gemini_timeout_spin.setToolTip(
            "Maximum time to wait for Gemini CLI to respond (in seconds).\n\n"
            "Factors affecting response time:\n"
            "• Network latency to Google's API\n"
            "• Model processing time (Pro slower than Flash)\n"
            "• Document complexity and image size\n\n"
            "Default: 300 seconds (5 minutes)\n"
            "Increase if you get timeout errors during analysis."
        )
        layout.addWidget(self.gemini_timeout_spin, 3, 1)

        return widget

    def _create_prompts_tab(self) -> QWidget:
        """Create the Prompts configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Prompts Group
        prompts_group = QGroupBox("Prompts Configuration")
        prompts_layout = QVBoxLayout(prompts_group)

        # Document Pages Prompt
        doc_validation_label = QLabel("Document Validation Prompt:")
        doc_validation_label.setToolTip(
            "Prompt used to validate if multiple pages belong to the same document.\n\n"
            "Purpose: When multiple pages are found, this prompt asks the LLM to\n"
            "determine which pages belong together as a single document.\n\n"
            "Implementation: Sent to the LLM with multiple page images.\n"
            "The LLM returns JSON indicating which pages belong together.\n\n"
            "Used by: Document bundling logic during analysis."
        )
        prompts_layout.addWidget(doc_validation_label)
        self.pages_prompt_edit = ExpandablePromptEdit()
        self.pages_prompt_edit.setToolTip(
            "This prompt analyzes multiple document page images to determine\n"
            "if they belong to the same physical document.\n\n"
            "The LLM uses visual cues like:\n"
            "• Consistent formatting and layout\n"
            "• Sequential page numbers\n"
            "• Continuation of content\n"
            "• Matching headers/footers\n\n"
            "Response format must be JSON with 'all_belong', 'doc_page_count',\n"
            "and 'do_not_belong' fields."
        )
        pages_prompt_default = """You are an expert document analyst. Examine the provided images and determine which pages belong to the same continuous physical document.

The first image should ALWAYS be considered as belonging to the document (it's the anchor page). Analyze each subsequent page to determine if it belongs with the first page or not.

Respond ONLY with valid JSON in this format:
{
  "all_belong": boolean,
  "doc_page_count": integer,
  "do_not_belong": [array of integers]
}

Where:
- **all_belong**: true if all provided pages belong together, false if any page doesn't belong
- **doc_page_count**: number of pages that belong together (including the first page)
- **do_not_belong**: array of page indices (1-based) that don't belong. The first page (index 1) should NEVER be in this array.

Examples:

If all 3 pages belong together:
{ "all_belong": true, "doc_page_count": 3, "do_not_belong": [] }

If 3 pages provided and page 2 doesn't belong:
{ "all_belong": false, "doc_page_count": 2, "do_not_belong": [2] }

If 5 pages provided and pages 3 and 5 don't belong:
{ "all_belong": false, "doc_page_count": 3, "do_not_belong": [3, 5] }"""
        pages_prompt = self.config_manager.get_setting(
            "Prompts", "document_pages", pages_prompt_default
        )
        self.pages_prompt_edit.setPlainText(pages_prompt)
        prompts_layout.addWidget(self.pages_prompt_edit)

        pages_buttons = QHBoxLayout()
        optimize_pages_btn = QPushButton("Optimize Prompt")
        optimize_pages_btn.clicked.connect(lambda: self._optimize_prompt(self.pages_prompt_edit))
        optimize_pages_btn.setObjectName("compactButton")
        reset_pages_btn = QPushButton("Reset to Default")
        reset_pages_btn.clicked.connect(
            lambda: self.pages_prompt_edit.setPlainText(pages_prompt_default)
        )
        reset_pages_btn.setObjectName("compactButton")
        pages_buttons.addWidget(optimize_pages_btn)
        pages_buttons.addWidget(reset_pages_btn)
        pages_buttons.addStretch()
        prompts_layout.addLayout(pages_buttons)

        # Document Metadata Prompt
        metadata_label = QLabel("Metadata Extraction Prompt:")
        metadata_label.setToolTip(
            "Prompt used to extract metadata from document images.\n\n"
            "Purpose: Analyzes each document page to extract structured information\n"
            "like company name, document type, date, page numbers, etc.\n\n"
            "Implementation: Sent to the LLM with one or more page images.\n"
            "The LLM returns JSON with all extracted metadata fields.\n\n"
            "Used by: Analysis service for every document page analyzed."
        )
        prompts_layout.addWidget(metadata_label)
        self.metadata_prompt_edit = ExpandablePromptEdit()
        self.metadata_prompt_edit.setToolTip(
            "This prompt extracts comprehensive metadata from document images.\n\n"
            "Extracted fields include:\n"
            "• company - Organization name\n"
            "• document_type - Invoice, Statement, Receipt, etc.\n"
            "• document_date - Primary date in YYYY-MM-DD format\n"
            "• tax_related - Boolean for tax-related documents\n"
            "• page_number/total_pages - Page information\n"
            "• rotation_needed - If image needs rotation\n"
            "• confidence_score - LLM's confidence (0.0-1.0)\n\n"
            "Response format must be valid JSON with all fields."
        )
        metadata_prompt_default = """You are an expert at analyzing scanned documents and extracting comprehensive metadata.

Analyze the provided image(s) and extract the following information:

**Document Identification:**
1. **company** (string): Organization name from logos, headers, footers, or return addresses. Use null if not found.
2. **document_type** (string): Document purpose (e.g., Invoice, Statement, Bill, Receipt, Report, Contract, Agreement, Letter). Use null if unclear.
3. **document_date** (string): Primary date in YYYY-MM-DD format (invoice date, statement date, issue date). Use null if not found.
4. **tax_related** (boolean): Is this document related to taxes? Look for: W-2, 1099, tax returns, property tax bills, tax receipts, IRS correspondence, deductible expense receipts, tax statements. Set to true if tax-related, false otherwise.

**Page Information:**
5. **page_number** (integer): Current page number if shown. Use null if not found.
6. **total_pages** (integer): Total page count if indicated (e.g., "Page 1 of 3"). Use null if not found.
7. **belongs_to_same_doc** (boolean): Does this SINGLE page show indicators it's likely part of a multi-page document? Look for:
   - Text starts or ends mid-sentence (incomplete thoughts)
   - Explicit page indicators ("Page 1 of 3", "Continued on next page")
   - References to unseen content ("as mentioned above", "see below", "continued from previous page")
   - Partial tables, lists, or paragraphs that appear cut off
   - Total page count > 1
   Set to true if ANY indicators present, false if page appears complete and standalone.

**Image Quality & Rotation:**
8. **rotation_needed** (boolean): Does the image need rotation to be upright and readable? Check if text appears sideways or upside-down.
9. **suggested_rotation** (integer): If rotation needed, specify degrees clockwise: 90, 180, or 270. Use 0 if no rotation needed.
10. **rotation_confidence** (string): Confidence in rotation assessment: "high", "medium", or "low".
11. **legibility** (string): Image readability: "clear" (easily readable), "degraded" (readable but poor quality), "illegible" (cannot read).
12. **resolution_assessment** (string): Estimated quality: "high" (300+ DPI), "medium" (150-300 DPI), "low" (<150 DPI), or "unknown".

**Overall Confidence:**
13. **confidence_score** (float): Your overall confidence in the extracted data (0.0 to 1.0).
   - 0.9-1.0: Very confident in all fields
   - 0.7-0.9: Confident in most fields, some uncertainty
   - 0.5-0.7: Moderate confidence, several unclear fields
   - 0.0-0.5: Low confidence, many fields unclear or guessed

**IMPORTANT:** Respond ONLY with valid JSON. Use null for any field you cannot determine. Do not include explanations outside the JSON structure.

Example response:
{
  "company": "Acme Corporation",
  "document_type": "Invoice",
  "document_date": "2024-01-15",
  "tax_related": false,
  "page_number": 1,
  "total_pages": 3,
  "belongs_to_same_doc": true,
  "rotation_needed": false,
  "suggested_rotation": 0,
  "rotation_confidence": "high",
  "legibility": "clear",
  "resolution_assessment": "high",
  "confidence_score": 0.92
}"""
        metadata_prompt = self.config_manager.get_setting(
            "Prompts", "document_metadata", metadata_prompt_default
        )
        self.metadata_prompt_edit.setPlainText(metadata_prompt)
        prompts_layout.addWidget(self.metadata_prompt_edit)

        metadata_buttons = QHBoxLayout()
        optimize_metadata_btn = QPushButton("Optimize Prompt")
        optimize_metadata_btn.clicked.connect(
            lambda: self._optimize_prompt(self.metadata_prompt_edit)
        )
        optimize_metadata_btn.setObjectName("compactButton")
        reset_metadata_btn = QPushButton("Reset to Default")
        reset_metadata_btn.clicked.connect(
            lambda: self.metadata_prompt_edit.setPlainText(metadata_prompt_default)
        )
        reset_metadata_btn.setObjectName("compactButton")
        metadata_buttons.addWidget(optimize_metadata_btn)
        metadata_buttons.addWidget(reset_metadata_btn)
        metadata_buttons.addStretch()
        prompts_layout.addLayout(metadata_buttons)

        layout.addWidget(prompts_group)

        layout.addStretch()

        return tab

    def _create_directories_tab(self) -> QWidget:
        """Tab 3: Multi-Directory Management"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info_label = QLabel(
            "Manage multiple source directories for document scanning.\n"
            "The application will monitor all listed directories for new documents."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Directory list
        self.directories_list = QListWidget()
        self.directories_list.setAlternatingRowColors(True)
        self.directories_list.setToolTip(
            "List of directories to monitor for document scanning.\n\n"
            "The application will:\n"
            "• Scan all listed directories recursively for image files (PNG, JPG, JPEG)\n"
            "• Analyze new/changed files when 'Analyze Documents' is clicked\n"
            "• Monitor these locations for document processing\n\n"
            "Use Add/Remove buttons to manage the list."
        )
        # Theme stylesheet handles all styling

        # Load existing directories
        directories = self.config_manager.get_directories()
        for directory in directories:
            self.directories_list.addItem(directory)

        layout.addWidget(self.directories_list)

        # Buttons
        button_layout = QHBoxLayout()

        add_btn = QPushButton("Add Directory")
        add_btn.setObjectName("compactButton")
        add_btn.setToolTip(
            "Add a new directory to the scan list.\n\n"
            "You can add multiple directories to monitor different locations\n"
            "for scanned documents (e.g., multiple scan output folders,\n"
            "network drives, or cloud sync folders)."
        )
        add_btn.clicked.connect(self._add_directory)
        button_layout.addWidget(add_btn)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.setObjectName("compactButton")
        remove_btn.setToolTip(
            "Remove the selected directory from the scan list.\n\n"
            "This only removes the directory from monitoring - it does not\n"
            "delete any files or affect previously analyzed documents."
        )
        remove_btn.clicked.connect(self._remove_directory)
        button_layout.addWidget(remove_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Scan on startup checkbox
        self.scan_on_startup_checkbox = QCheckBox("Scan all directories on application startup")
        self.scan_on_startup_checkbox.setToolTip(
            "Automatically scan directories when the application starts.\n\n"
            "When enabled: Application will check all monitored directories\n"
            "for new/changed files on startup and show a summary.\n\n"
            "When disabled: You must manually click 'Analyze Documents'\n"
            "to scan directories.\n\n"
            "Recommended: Enabled for frequent document scanning workflows."
        )
        scan_on_startup = self.config_manager.get_setting(
            "SourceDirectories", "scan_on_startup", "true"
        )
        self.scan_on_startup_checkbox.setChecked(scan_on_startup.lower() == "true")
        layout.addWidget(self.scan_on_startup_checkbox)

        layout.addStretch()
        return widget

    def _create_database_tab(self) -> QWidget:
        """Tab 4: Database Management"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Statistics Group
        stats_group = QGroupBox("Database Statistics")
        stats_layout = QVBoxLayout(stats_group)

        stats_btn = QPushButton("View Statistics")
        stats_btn.setObjectName("compactButton")
        stats_btn.setToolTip(
            "Display current database statistics.\n\n"
            "Shows:\n"
            "• Total analyzed files and pages\n"
            "• Number of bundle suggestions\n"
            "• Cache hit rate and efficiency\n"
            "• Database file size and location\n\n"
            "Statistics are automatically refreshed when this tab is displayed."
        )
        stats_btn.clicked.connect(self._show_database_statistics)
        stats_layout.addWidget(stats_btn)

        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(150)
        self.stats_text.setToolTip(
            "Database statistics display.\n\n"
            "Real-time view of database contents including:\n"
            "• Analysis results count\n"
            "• Bundle suggestions count\n"
            "• Cache performance metrics\n"
            "• Storage usage information"
        )
        # Theme stylesheet handles styling - no inline styles needed
        stats_layout.addWidget(self.stats_text)

        layout.addWidget(stats_group)

        # Maintenance Group
        maintenance_group = QGroupBox("Database Maintenance")
        maintenance_layout = QGridLayout(maintenance_group)

        backup_btn = QPushButton("Create Backup")
        backup_btn.setObjectName("compactButton")
        backup_btn.setToolTip(
            "Create a timestamped backup of the database.\n\n"
            "Creates a backup copy of analysis.db and metadata.db in the\n"
            "AppData directory with timestamp (e.g., analysis_backup_20260207_143052.db).\n\n"
            "Use before performing maintenance operations or major updates.\n"
            "Backups can be manually restored by renaming the backup file."
        )
        backup_btn.clicked.connect(self._backup_database)
        maintenance_layout.addWidget(backup_btn, 0, 0)

        purge_cache_btn = QPushButton("Purge Cached Metadata")
        purge_cache_btn.setObjectName("compactButton")
        purge_cache_btn.setToolTip(
            "Remove all cached metadata from the database.\n\n"
            "Forces re-analysis of all files on next scan. Use when:\n"
            "• Prompt templates have been significantly changed\n"
            "• LLM provider or model has been updated\n"
            "• Previous analyses appear incorrect or incomplete\n\n"
            "Warning: Re-analysis may take time and consume LLM resources."
        )
        purge_cache_btn.clicked.connect(lambda: self._purge_data("cache"))
        maintenance_layout.addWidget(purge_cache_btn, 1, 0)

        purge_analysis_btn = QPushButton("Purge Analysis Results")
        purge_analysis_btn.setObjectName("compactButton")
        purge_analysis_btn.setToolTip(
            "Remove all LLM analysis results from the database.\n\n"
            "Deletes:\n"
            "• All page-level analysis data\n"
            "• Extracted metadata (company, document type, dates)\n"
            "• Confidence scores and analysis timestamps\n\n"
            "Use for a complete fresh start with existing files.\n"
            "Does not delete bundle suggestions or configuration."
        )
        purge_analysis_btn.clicked.connect(lambda: self._purge_data("analysis"))
        maintenance_layout.addWidget(purge_analysis_btn, 1, 1)

        purge_bundles_btn = QPushButton("Purge Bundle Suggestions")
        purge_bundles_btn.setObjectName("compactButton")
        purge_bundles_btn.setToolTip(
            "Remove all bundle suggestions from the database.\n\n"
            "Deletes generated bundle recommendations but keeps:\n"
            "• Individual page analysis results\n"
            "• Extracted metadata\n"
            "• Cache data\n\n"
            "Use when you want to regenerate bundles with different\n"
            "bundling logic or after editing metadata."
        )
        purge_bundles_btn.clicked.connect(lambda: self._purge_data("bundles"))
        maintenance_layout.addWidget(purge_bundles_btn, 2, 0)

        purge_all_btn = QPushButton("Purge All Data")
        purge_all_btn.setObjectName("dangerButton")
        purge_all_btn.setToolTip(
            "⚠️ DANGER: Remove ALL data from the database.\n\n"
            "Deletes:\n"
            "• All analysis results\n"
            "• All bundle suggestions\n"
            "• All cached metadata\n"
            "• Analysis run history\n\n"
            "Database schema and structure are preserved.\n"
            "This action cannot be undone - create a backup first!\n\n"
            "Use only for complete database reset."
        )
        purge_all_btn.clicked.connect(lambda: self._purge_data("all"))
        maintenance_layout.addWidget(purge_all_btn, 2, 1)

        layout.addWidget(maintenance_group)

        # Auto-refresh stats on tab display
        self._show_database_statistics()

        layout.addStretch()
        return widget

    def _create_appearance_tab(self) -> QWidget:
        """Tab 5: Appearance Settings"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Theme Group
        theme_group = QGroupBox("Theme")
        theme_layout = QGridLayout(theme_group)

        theme_layout.addWidget(QLabel("Theme:"), 0, 0)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.setToolTip(
            "Select the application's color theme.\n\n"
            "Light Mode: Traditional light background with dark text\n"
            "Dark Mode: Dark background with light text (reduces eye strain)\n\n"
            "Theme affects all application windows including:\n"
            "• Main window\n"
            "• Settings dialogs\n"
            "• Bundle workflow\n"
            "• Analysis status displays\n\n"
            "Note: Changes require application restart to take full effect."
        )

        current_theme = self.config_manager.get_setting("Theme", "theme", "light")
        index = self.theme_combo.findData(current_theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)

        theme_layout.addWidget(self.theme_combo, 0, 1)

        theme_note = QLabel("Note: Theme changes require application restart")
        theme_layout.addWidget(theme_note, 1, 1)

        layout.addWidget(theme_group)

        # Zoom Defaults Group
        zoom_group = QGroupBox("Default Zoom Settings")
        zoom_layout = QGridLayout(zoom_group)

        zoom_layout.addWidget(QLabel("PNG Zoom Mode:"), 0, 0)
        self.png_zoom_combo = QComboBox()
        self.png_zoom_combo.addItems(["Fit to Width", "Fit to Height", "Fit to Window", "Custom %"])
        self.png_zoom_combo.setToolTip(
            "Default zoom mode for PNG image previews.\n\n"
            "• Fit to Width: Scale image to viewer width (recommended for documents)\n"
            "• Fit to Height: Scale image to viewer height\n"
            "• Fit to Window: Scale to fit entire image in viewer\n"
            "• Custom %: Use specific zoom percentage (set below)\n\n"
            "Users can override this with zoom controls in the preview window.\n"
            "Applies to scanned document images and page previews."
        )
        png_zoom = self.config_manager.get_setting("Theme", "default_zoom_mode_png", "fit_to_width")
        self.png_zoom_combo.setCurrentText(png_zoom.replace("_", " ").title())
        zoom_layout.addWidget(self.png_zoom_combo, 0, 1)

        zoom_layout.addWidget(QLabel("PDF Zoom Mode:"), 1, 0)
        self.pdf_zoom_combo = QComboBox()
        self.pdf_zoom_combo.addItems(["Fit to Width", "Fit to Height", "Fit to Window", "Custom %"])
        self.pdf_zoom_combo.setToolTip(
            "Default zoom mode for PDF document previews.\n\n"
            "• Fit to Width: Scale page to viewer width (recommended for reading)\n"
            "• Fit to Height: Scale page to viewer height\n"
            "• Fit to Window: Scale to fit entire page in viewer\n"
            "• Custom %: Use specific zoom percentage (set below)\n\n"
            "Users can override this with zoom controls in the preview window.\n"
            "Applies to generated PDF outputs and PDF previews."
        )
        pdf_zoom = self.config_manager.get_setting("Theme", "default_zoom_mode_pdf", "fit_to_width")
        self.pdf_zoom_combo.setCurrentText(pdf_zoom.replace("_", " ").title())
        zoom_layout.addWidget(self.pdf_zoom_combo, 1, 1)

        zoom_layout.addWidget(QLabel("PNG Custom Zoom %:"), 2, 0)
        self.png_zoom_percent = QSpinBox()
        self.png_zoom_percent.setMinimum(25)
        self.png_zoom_percent.setMaximum(400)
        self.png_zoom_percent.setSingleStep(25)
        self.png_zoom_percent.setValue(
            int(self.config_manager.get_setting("Theme", "default_zoom_percent_png", "100"))
        )
        self.png_zoom_percent.setSuffix("%")
        self.png_zoom_percent.setToolTip(
            "Custom zoom percentage for PNG images (25% - 400%).\n\n"
            "Only used when PNG Zoom Mode is set to 'Custom %'.\n\n"
            "Common values:\n"
            "• 100% - Actual size (1:1 pixel mapping)\n"
            "• 150% - Enlarged for easier reading\n"
            "• 50% - Reduced to see more content\n\n"
            "High-DPI displays may benefit from values above 100%."
        )
        zoom_layout.addWidget(self.png_zoom_percent, 2, 1)

        zoom_layout.addWidget(QLabel("PDF Custom Zoom %:"), 3, 0)
        self.pdf_zoom_percent = QSpinBox()
        self.pdf_zoom_percent.setMinimum(25)
        self.pdf_zoom_percent.setMaximum(400)
        self.pdf_zoom_percent.setSingleStep(25)
        self.pdf_zoom_percent.setValue(
            int(self.config_manager.get_setting("Theme", "default_zoom_percent_pdf", "100"))
        )
        self.pdf_zoom_percent.setSuffix("%")
        self.pdf_zoom_percent.setToolTip(
            "Custom zoom percentage for PDF documents (25% - 400%).\n\n"
            "Only used when PDF Zoom Mode is set to 'Custom %'.\n\n"
            "Common values:\n"
            "• 100% - Standard size (comfortable reading)\n"
            "• 125% - Slightly enlarged text\n"
            "• 75% - See more of the page\n\n"
            "Adjust based on screen size and resolution."
        )
        zoom_layout.addWidget(self.pdf_zoom_percent, 3, 1)

        layout.addWidget(zoom_group)

        # System Tray Group
        tray_group = QGroupBox("System Tray")
        tray_layout = QVBoxLayout(tray_group)

        self.minimize_to_tray_checkbox = QCheckBox("Minimize to system tray")
        self.minimize_to_tray_checkbox.setToolTip(
            "Minimize application to system tray instead of taskbar.\n\n"
            "When enabled:\n"
            "• Clicking minimize sends app to system tray (near clock)\n"
            "• Application remains running in background\n"
            "• Click tray icon to restore window\n\n"
            "When disabled:\n"
            "• Minimize button works normally (taskbar)\n\n"
            "Useful for keeping the app running during long analysis tasks\n"
            "without cluttering the taskbar."
        )
        minimize_tray = self.config_manager.get_setting("SystemTray", "minimize_to_tray", "false")
        self.minimize_to_tray_checkbox.setChecked(minimize_tray.lower() == "true")
        tray_layout.addWidget(self.minimize_to_tray_checkbox)

        self.close_to_tray_checkbox = QCheckBox("Close to system tray (don't exit)")
        self.close_to_tray_checkbox.setToolTip(
            "Keep application running when main window is closed.\n\n"
            "When enabled:\n"
            "• Clicking 'X' button sends app to system tray\n"
            "• Application continues running in background\n"
            "• Right-click tray icon → 'Quit' to fully exit\n\n"
            "When disabled:\n"
            "• Clicking 'X' button exits application normally\n\n"
            "Useful for:\n"
            "• Background document monitoring\n"
            "• Quick access via tray icon\n"
            "• Preventing accidental closure during long operations"
        )
        close_tray = self.config_manager.get_setting("SystemTray", "close_to_tray", "false")
        self.close_to_tray_checkbox.setChecked(close_tray.lower() == "true")
        tray_layout.addWidget(self.close_to_tray_checkbox)

        layout.addWidget(tray_group)

        layout.addStretch()
        return widget

    # Event Handlers

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

    def _browse_scan_folder(self):
        """Browse for scan folder"""
        current_path = self.scan_folder_edit.text()
        if not os.path.isdir(current_path):
            current_path = os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, "Select Scan Folder", current_path)
        if directory:
            self.scan_folder_edit.setText(directory)

    def _load_ollama_models(self, force_refresh: bool = False):
        """Load available Ollama vision models with download status and caching

        Args:
            force_refresh: If True, bypass cache and check download status fresh
        """
        import json
        from datetime import datetime

        self.ollama_model_combo.clear()

        # Popular vision models available in Ollama
        available_vision_models = [
            "llava:latest",
            "llava:7b",
            "llava:13b",
            "llava:34b",
            "llava-llama3:latest",
            "llava-phi3:latest",
            "bakllava:latest",
            "moondream:latest",
            "qwen2-vl:latest",
            "qwen2-vl:2b",
            "qwen2-vl:7b",
            "qwen2.5-vl:latest",
            "minicpm-v:latest",
            "minicpm-v:8b",
            "cogvlm:latest",
            "phi3-vision:latest",
            "internvl:latest",
        ]

        downloaded_model_names = set()

        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_downloaded = self.config_manager.get_setting(
                "ModelCache", "ollama_downloaded_cache"
            )
            cached_timestamp = self.config_manager.get_setting(
                "ModelCache", "ollama_models_timestamp"
            )

            if cached_downloaded and cached_timestamp:
                try:
                    from datetime import timedelta

                    last_updated = datetime.fromisoformat(cached_timestamp)
                    now = datetime.now()

                    if now - last_updated < timedelta(hours=24):
                        # Use cached download status
                        downloaded_model_names = set(json.loads(cached_downloaded))
                        logger.debug(
                            f"Using cached Ollama download status (last checked: {last_updated.strftime('%Y-%m-%d %H:%M')})"
                        )
                except (ValueError, json.JSONDecodeError):
                    pass  # Cache invalid, will refresh

        # Refresh download status if not loaded from cache
        if not downloaded_model_names or force_refresh:
            try:
                local_models = self.ollama_service.list_models()
                downloaded_model_names = {
                    (m.get("name") or m.get("model")).split(":")[0] for m in local_models
                }

                # Cache the download status
                timestamp = datetime.now().isoformat()
                self.config_manager.set_setting(
                    "ModelCache",
                    "ollama_downloaded_cache",
                    json.dumps(list(downloaded_model_names)),
                )
                self.config_manager.set_setting("ModelCache", "ollama_models_timestamp", timestamp)
                logger.debug(f"Checked Ollama download status at {timestamp}")

            except Exception as e:
                show_warning(self, "Error", f"Failed to load Ollama models: {e}")
                return

        # Add models with download status
        for model in available_vision_models:
            model_base = model.split(":")[0]
            is_downloaded = model_base in downloaded_model_names

            display_text = f"{model} ✓ (Downloaded)" if is_downloaded else f"{model}"

            self.ollama_model_combo.addItem(display_text, model)

        # Set current model
        current_model = self.config_manager.get_setting("Ollama", "model")
        if current_model:
            model_found = False

            # Try exact match first
            for i in range(self.ollama_model_combo.count()):
                if self.ollama_model_combo.itemData(i) == current_model:
                    self.ollama_model_combo.setCurrentIndex(i)
                    model_found = True
                    break

            # Try partial match (base name) if exact match failed
            if not model_found:
                current_base = current_model.split(":")[0]
                for i in range(self.ollama_model_combo.count()):
                    if self.ollama_model_combo.itemData(i).startswith(current_base):
                        self.ollama_model_combo.setCurrentIndex(i)
                        model_found = True
                        break

            # If model not found in list, add it
            if not model_found:
                # Check if it's downloaded
                model_base = current_model.split(":")[0]
                is_downloaded = model_base in downloaded_model_names

                if is_downloaded:
                    display_text = f"{current_model} ✓ (Downloaded)"
                else:
                    display_text = f"{current_model}"

                self.ollama_model_combo.addItem(display_text, current_model)
                self.ollama_model_combo.setCurrentIndex(self.ollama_model_combo.count() - 1)

    def _load_claude_models(self, force_refresh: bool = False):
        """Load available Claude vision models with caching

        Args:
            force_refresh: If True, bypass cache and fetch fresh from web
        """
        self.claude_model_combo.clear()

        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_models = self._get_cached_models("claude")
            if cached_models:
                claude_vision_models = cached_models
            else:
                # Cache miss or expired - fetch from web
                claude_vision_models = self._fetch_claude_models_from_web()
                self._cache_models("claude", claude_vision_models)
        else:
            # Force refresh - fetch from web and update cache
            claude_vision_models = self._fetch_claude_models_from_web()
            self._cache_models("claude", claude_vision_models)

        # Populate dropdown
        for model in claude_vision_models:
            self.claude_model_combo.addItem(model)

        # Set current model
        current_model = self.config_manager.get_setting("ClaudeCLI", "default_model")
        if current_model:
            index = self.claude_model_combo.findText(current_model)
            if index >= 0:
                self.claude_model_combo.setCurrentIndex(index)
            else:
                # If saved model not in list, add it
                self.claude_model_combo.addItem(current_model)
                self.claude_model_combo.setCurrentIndex(self.claude_model_combo.count() - 1)

    def _apply_combobox_chevron_fix(self, combobox: QComboBox):
        """Apply custom paint event to draw dropdown chevron in dark mode

        Args:
            combobox: QComboBox widget to apply the fix to
        """
        from PyQt6.QtCore import QPoint
        from PyQt6.QtGui import QColor, QPainter, QPen, QPolygon

        # Determine theme from config
        current_theme = self.config_manager.get_setting("Theme", "theme", "light")
        is_dark = current_theme == "dark"

        # Determine colors based on theme
        if is_dark:
            arrow_color = "#E0E0E0"  # Light arrow for dark mode
            bg_color = "#2D2D2D"
            text_color = "#E0E0E0"
            border_color = "#4A4A4A"
        else:
            arrow_color = "#111827"  # Dark arrow for light mode
            bg_color = "#FFFFFF"
            text_color = "#111827"
            border_color = "#E5E7EB"

        # Apply stylesheet to hide default arrow and style the combobox
        combobox.setStyleSheet(f"""
            QComboBox {{
                background: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 5px 30px 5px 10px;
                min-height: 20px;
            }}
            QComboBox:focus {{
                border: 1px solid #3B82F6;
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
                background: {bg_color};
                color: {text_color};
                selection-background-color: #3B82F6;
                border: 1px solid {border_color};
            }}
        """)

        # Save original paint event
        original_paint = combobox.paintEvent

        def custom_paint(event):
            """Custom paint event that draws the dropdown arrow"""
            original_paint(event)
            painter = QPainter(combobox)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Draw down arrow triangle on the right side
            arrow_x = combobox.width() - 18
            arrow_y = combobox.height() // 2

            # Create triangle points
            points = [
                QPoint(arrow_x - 4, arrow_y - 2),  # Top left
                QPoint(arrow_x + 4, arrow_y - 2),  # Top right
                QPoint(arrow_x, arrow_y + 3),  # Bottom center
            ]

            polygon = QPolygon(points)
            painter.setPen(QPen(QColor(arrow_color), 1))
            painter.setBrush(QColor(arrow_color))
            painter.drawPolygon(polygon)
            painter.end()

        # Replace paint event
        combobox.paintEvent = custom_paint  # type: ignore[method-assign]

    def _get_cached_models(self, provider: str) -> list[str] | None:
        """Get cached model list if still valid (< 24 hours old)

        Args:
            provider: 'claude', 'gemini', or 'ollama'

        Returns:
            List of model names if cache is valid, None otherwise
        """
        import json
        from datetime import datetime, timedelta

        # Get cached models and timestamp from config
        cache_key = f"{provider}_models_cache"
        timestamp_key = f"{provider}_models_timestamp"

        cached_json = self.config_manager.get_setting("ModelCache", cache_key)
        cached_timestamp = self.config_manager.get_setting("ModelCache", timestamp_key)

        if not cached_json or not cached_timestamp:
            return None

        try:
            # Parse timestamp
            last_updated = datetime.fromisoformat(cached_timestamp)
            now = datetime.now()

            # Check if cache is still valid (< 24 hours old)
            if now - last_updated < timedelta(hours=24):
                # Cache is valid - parse and return models
                models = json.loads(cached_json)
                if isinstance(models, list) and len(models) > 0:
                    logger.debug(
                        f"Using cached {provider} models (last updated: {last_updated.strftime('%Y-%m-%d %H:%M')})"
                    )
                    return models

        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Error parsing cached {provider} models: {e}")

        return None

    def _cache_models(self, provider: str, models: list[str]):
        """Cache model list with current timestamp

        Args:
            provider: 'claude', 'gemini', or 'ollama'
            models: List of model names to cache
        """
        import json
        from datetime import datetime

        cache_key = f"{provider}_models_cache"
        timestamp_key = f"{provider}_models_timestamp"

        # Store models as JSON array
        models_json = json.dumps(models)
        timestamp = datetime.now().isoformat()

        self.config_manager.set_setting("ModelCache", cache_key, models_json)
        self.config_manager.set_setting("ModelCache", timestamp_key, timestamp)

        logger.debug(f"Cached {len(models)} {provider} models at {timestamp}")

    def _fetch_claude_models_from_web(self) -> list[str]:
        """Use Claude to search the web for latest vision-capable models"""
        try:
            import json
            import subprocess

            # Create prompt for Claude to search for latest models
            prompt = """Search the web for the latest Anthropic Claude vision-capable models.
Look for official Anthropic documentation or announcements about Claude models that support image input.

Return ONLY a JSON array of model IDs (full model names with dates, like "claude-3-5-sonnet-20241022").
Include only models that support vision/image inputs.
Order from newest to oldest.

Example format:
["claude-3-5-sonnet-20241022", "claude-3-opus-20240229"]

Return ONLY the JSON array, no other text."""

            # Call Claude CLI to search
            result = subprocess.run(
                ["claude", "--model", "sonnet", "-p", prompt],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                # Parse JSON response
                response = result.stdout.strip()
                # Extract JSON array from response (might have markdown code fences)
                if "```json" in response:
                    json_start = response.find("[")
                    json_end = response.rfind("]") + 1
                    if json_start >= 0 and json_end > json_start:
                        response = response[json_start:json_end]
                elif "```" in response:
                    # Remove code fences
                    response = response.replace("```json", "").replace("```", "").strip()

                models = json.loads(response)
                if isinstance(models, list) and len(models) > 0:
                    return models

        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            json.JSONDecodeError,
            FileNotFoundError,
        ) as e:
            logger.info(f"Could not fetch Claude models from web: {e}")

        # Fallback to curated list
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ]

    def _load_gemini_models(self, force_refresh: bool = False):
        """Load available Gemini vision models with caching

        Args:
            force_refresh: If True, bypass cache and fetch fresh from web
        """
        self.gemini_model_combo.clear()

        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_models = self._get_cached_models("gemini")
            if cached_models:
                gemini_vision_models = cached_models
            else:
                # Cache miss or expired - fetch from web
                gemini_vision_models = self._fetch_gemini_models_from_web()
                self._cache_models("gemini", gemini_vision_models)
        else:
            # Force refresh - fetch from web and update cache
            gemini_vision_models = self._fetch_gemini_models_from_web()
            self._cache_models("gemini", gemini_vision_models)

        # Populate dropdown
        for model in gemini_vision_models:
            self.gemini_model_combo.addItem(model)

        # Set current model
        current_model = self.config_manager.get_setting("GeminiCLI", "default_model")
        if current_model:
            index = self.gemini_model_combo.findText(current_model)
            if index >= 0:
                self.gemini_model_combo.setCurrentIndex(index)
            else:
                # If saved model not in list, add it
                self.gemini_model_combo.addItem(current_model)
                self.gemini_model_combo.setCurrentIndex(self.gemini_model_combo.count() - 1)

    def _fetch_gemini_models_from_web(self) -> list[str]:
        """Use Claude to search the web for latest Gemini vision-capable models"""
        try:
            import json
            import subprocess

            # Create prompt for Claude to search for latest Gemini models
            prompt = """Search the web for the latest Google Gemini vision-capable models.
Look for official Google AI documentation or announcements about Gemini models that support image/vision inputs.

Return ONLY a JSON array of model IDs (like "gemini-2.0-flash-exp", "gemini-1.5-pro").
Include only models that support vision/image inputs (multimodal models).
Order from newest to oldest.

Example format:
["gemini-2.0-flash-exp", "gemini-1.5-pro", "gemini-1.5-flash"]

Return ONLY the JSON array, no other text."""

            # Call Claude CLI to search
            result = subprocess.run(
                ["claude", "--model", "sonnet", "-p", prompt],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                # Parse JSON response
                response = result.stdout.strip()
                # Extract JSON array from response (might have markdown code fences)
                if "```json" in response:
                    json_start = response.find("[")
                    json_end = response.rfind("]") + 1
                    if json_start >= 0 and json_end > json_start:
                        response = response[json_start:json_end]
                elif "```" in response:
                    # Remove code fences
                    response = response.replace("```json", "").replace("```", "").strip()

                models = json.loads(response)
                if isinstance(models, list) and len(models) > 0:
                    return models

        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            json.JSONDecodeError,
            FileNotFoundError,
        ) as e:
            logger.info(f"Could not fetch Gemini models from web: {e}")

        # Fallback to curated list
        return [
            "gemini-2.0-flash-exp",
            "gemini-1.5-pro",
            "gemini-1.5-pro-002",
            "gemini-1.5-flash",
            "gemini-1.5-flash-002",
            "gemini-1.5-flash-8b",
        ]

    def _download_ollama_model(self):
        """Download an Ollama model"""
        show_information(
            self,
            "Download Model",
            "Model download functionality will be implemented in next phase.\n"
            "For now, use 'ollama pull <model-name>' in terminal.",
        )

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
        progress = QMessageBox(self)
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
                    self.metadata_db.connection.execute("DELETE FROM active_metadata")
                    self.metadata_db.connection.commit()
                elif data_type == "cache":
                    self.metadata_db.connection.execute("DELETE FROM active_metadata")
                    self.metadata_db.connection.commit()
                elif data_type == "analysis":
                    self.analysis_db.connection.execute("DELETE FROM analysis_results")
                    self.analysis_db.connection.commit()
                elif data_type == "bundles":
                    self.analysis_db.connection.execute("DELETE FROM document_bundles")
                    self.analysis_db.connection.commit()

                show_information(
                    self, "Purge Complete", f"Successfully purged {type_names[data_type]}."
                )
                self._show_database_statistics()  # Refresh stats

            except Exception as e:
                show_critical(self, "Purge Failed", f"Failed to purge data:\n\n{e}")

    def save_settings(self):
        """Save all settings"""
        try:
            # General Tab
            self.config_manager.set_setting(
                "DocumentProcessing", "scan_folder", self.scan_folder_edit.text()
            )
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

            from ui.styles import show_information

            show_information(self, "Settings Saved", "Your settings have been saved successfully.")
            self.accept()

        except Exception as e:
            from ui.styles import show_critical

            show_critical(self, "Save Failed", f"Failed to save settings:\n\n{e}")


# For backward compatibility, alias to old name
SettingsWindow = EnhancedSettingsWindow


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = EnhancedSettingsWindow()
    window.show()
    sys.exit(app.exec())
