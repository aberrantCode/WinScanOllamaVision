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
from ui.styles import show_critical, show_information, show_question, show_warning


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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.metadata_db = MetadataDB()
        self.analysis_db = AnalysisDB()

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
        folder_layout.addWidget(self.scan_folder_edit)

        browse_button = QPushButton()
        browse_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
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

        # Auto-Approval Group
        approval_group = QGroupBox("Auto-Approval")
        approval_layout = QGridLayout(approval_group)

        self.auto_approval_checkbox = QCheckBox("Enable Automatic Approvals")
        auto_approval_enabled = self.config_manager.get_setting(
            "AutoApproval", "enable_automatic_approvals", "false"
        )
        self.auto_approval_checkbox.setChecked(auto_approval_enabled.lower() == "true")
        self.auto_approval_checkbox.stateChanged.connect(self._on_auto_approval_toggled)
        approval_layout.addWidget(self.auto_approval_checkbox, 0, 0, 1, 2)

        self.approval_delay_label = QLabel("Approval Delay (seconds):")
        approval_layout.addWidget(self.approval_delay_label, 1, 0)

        self.approval_delay_spinbox = QSpinBox()
        self.approval_delay_spinbox.setMinimum(3)
        self.approval_delay_spinbox.setMaximum(60)
        self.approval_delay_spinbox.setValue(
            int(self.config_manager.get_setting("AutoApproval", "automatic_approval_delay", "5"))
        )
        approval_layout.addWidget(self.approval_delay_spinbox, 1, 1)

        # Set initial visibility
        is_checked = self.auto_approval_checkbox.isChecked()
        self.approval_delay_label.setVisible(is_checked)
        self.approval_delay_spinbox.setVisible(is_checked)

        layout.addWidget(approval_group)

        # Audit Trail Group
        audit_group = QGroupBox("Audit Trail")
        audit_layout = QVBoxLayout(audit_group)

        self.audit_trail_checkbox = QCheckBox("Enable Audit Trail Logging")
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
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
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

        # Prompts Group
        prompts_group = QGroupBox("Prompts Configuration")
        prompts_layout = QVBoxLayout(prompts_group)

        # Document Pages Prompt
        prompts_layout.addWidget(QLabel("Document Validation Prompt:"))
        self.pages_prompt_edit = ExpandablePromptEdit()
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
        prompts_layout.addWidget(QLabel("Metadata Extraction Prompt:"))
        self.metadata_prompt_edit = ExpandablePromptEdit()
        metadata_prompt_default = """You are an expert at analyzing scanned documents and extracting comprehensive metadata.

Analyze the provided image(s) and extract the following information:

**Document Identification:**
1. **company** (string): Organization name from logos, headers, footers, or return addresses. Use null if not found.
2. **document_type** (string): Document purpose (e.g., Invoice, Statement, Bill, Receipt, Report, Contract, Agreement, Letter). Use null if unclear.
3. **document_date** (string): Primary date in YYYY-MM-DD format (invoice date, statement date, issue date). Use null if not found.

**Page Information:**
4. **page_number** (integer): Current page number if shown. Use null if not found.
5. **total_pages** (integer): Total page count if indicated (e.g., "Page 1 of 3"). Use null if not found.
6. **belongs_to_same_doc** (boolean): Does this SINGLE page show indicators it's likely part of a multi-page document? Look for:
   - Text starts or ends mid-sentence (incomplete thoughts)
   - Explicit page indicators ("Page 1 of 3", "Continued on next page")
   - References to unseen content ("as mentioned above", "see below", "continued from previous page")
   - Partial tables, lists, or paragraphs that appear cut off
   - Total page count > 1
   Set to true if ANY indicators present, false if page appears complete and standalone.

**Image Quality & Rotation:**
7. **rotation_needed** (boolean): Does the image need rotation to be upright and readable? Check if text appears sideways or upside-down.
8. **suggested_rotation** (integer): If rotation needed, specify degrees clockwise: 90, 180, or 270. Use 0 if no rotation needed.
9. **rotation_confidence** (string): Confidence in rotation assessment: "high", "medium", or "low".
10. **legibility** (string): Image readability: "clear" (easily readable), "degraded" (readable but poor quality), "illegible" (cannot read).
11. **resolution_assessment** (string): Estimated quality: "high" (300+ DPI), "medium" (150-300 DPI), "low" (<150 DPI), or "unknown".

**Overall Confidence:**
12. **confidence_score** (float): Your overall confidence in the extracted data (0.0 to 1.0).
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
        layout.addWidget(self.ollama_model_combo, 0, 1)

        download_btn = QPushButton("Download Model")
        download_btn.clicked.connect(self._download_ollama_model)
        download_btn.setObjectName("compactButton")
        layout.addWidget(download_btn, 0, 2)

        layout.addWidget(QLabel("Base URL:"), 1, 0)
        self.ollama_url_edit = QLineEdit(
            self.config_manager.get_setting("Ollama", "base_url", "http://localhost:11434")
        )
        layout.addWidget(self.ollama_url_edit, 1, 1, 1, 2)

        layout.addWidget(QLabel("Timeout (seconds):"), 2, 0)
        self.ollama_timeout_spin = QSpinBox()
        self.ollama_timeout_spin.setMinimum(10)
        self.ollama_timeout_spin.setMaximum(600)
        self.ollama_timeout_spin.setValue(
            int(self.config_manager.get_setting("Ollama", "timeout", "300"))
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
        claude_models = self.config_manager.get_setting("ClaudeCLI", "models", "").split(",")
        for model in claude_models:
            if model.strip():
                self.claude_model_combo.addItem(model.strip())
        # Set default model
        default_model = self.config_manager.get_setting("ClaudeCLI", "default_model")
        if default_model:
            index = self.claude_model_combo.findText(default_model)
            if index >= 0:
                self.claude_model_combo.setCurrentIndex(index)
        layout.addWidget(self.claude_model_combo, 0, 1)

        layout.addWidget(QLabel("Command Template:"), 1, 0, Qt.AlignmentFlag.AlignTop)
        self.claude_command_edit = QPlainTextEdit()
        self.claude_command_edit.setMaximumHeight(60)
        self.claude_command_edit.setPlainText(
            self.config_manager.get_setting("ClaudeCLI", "command_template", "")
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
        layout.addWidget(self.claude_timeout_spin, 3, 1)

        return widget

    def _create_gemini_cli_settings(self) -> QWidget:
        """Gemini CLI-specific settings panel"""
        widget = QGroupBox("Gemini CLI Settings")
        layout = QGridLayout(widget)

        layout.addWidget(QLabel("Model:"), 0, 0)
        self.gemini_model_combo = QComboBox()
        gemini_models = self.config_manager.get_setting("GeminiCLI", "models", "").split(",")
        for model in gemini_models:
            if model.strip():
                self.gemini_model_combo.addItem(model.strip())
        # Set default model
        default_model = self.config_manager.get_setting("GeminiCLI", "default_model")
        if default_model:
            index = self.gemini_model_combo.findText(default_model)
            if index >= 0:
                self.gemini_model_combo.setCurrentIndex(index)
        layout.addWidget(self.gemini_model_combo, 0, 1)

        layout.addWidget(QLabel("Command Template:"), 1, 0, Qt.AlignmentFlag.AlignTop)
        self.gemini_command_edit = QPlainTextEdit()
        self.gemini_command_edit.setMaximumHeight(60)
        self.gemini_command_edit.setPlainText(
            self.config_manager.get_setting("GeminiCLI", "command_template", "")
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
        layout.addWidget(self.gemini_timeout_spin, 3, 1)

        return widget

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
        add_btn.clicked.connect(self._add_directory)
        button_layout.addWidget(add_btn)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.setObjectName("compactButton")
        remove_btn.clicked.connect(self._remove_directory)
        button_layout.addWidget(remove_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Scan on startup checkbox
        self.scan_on_startup_checkbox = QCheckBox("Scan all directories on application startup")
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
        stats_btn.clicked.connect(self._show_database_statistics)
        stats_layout.addWidget(stats_btn)

        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(150)
        # Theme stylesheet handles styling - no inline styles needed
        stats_layout.addWidget(self.stats_text)

        layout.addWidget(stats_group)

        # Maintenance Group
        maintenance_group = QGroupBox("Database Maintenance")
        maintenance_layout = QGridLayout(maintenance_group)

        backup_btn = QPushButton("Create Backup")
        backup_btn.setObjectName("compactButton")
        backup_btn.setToolTip("Create a timestamped backup of the database")
        backup_btn.clicked.connect(self._backup_database)
        maintenance_layout.addWidget(backup_btn, 0, 0)

        purge_cache_btn = QPushButton("Purge Cached Metadata")
        purge_cache_btn.setObjectName("compactButton")
        purge_cache_btn.setToolTip("Remove all cached metadata (forces re-analysis)")
        purge_cache_btn.clicked.connect(lambda: self._purge_data("cache"))
        maintenance_layout.addWidget(purge_cache_btn, 1, 0)

        purge_analysis_btn = QPushButton("Purge Analysis Results")
        purge_analysis_btn.setObjectName("compactButton")
        purge_analysis_btn.setToolTip("Remove all analysis results")
        purge_analysis_btn.clicked.connect(lambda: self._purge_data("analysis"))
        maintenance_layout.addWidget(purge_analysis_btn, 1, 1)

        purge_bundles_btn = QPushButton("Purge Bundle Suggestions")
        purge_bundles_btn.setObjectName("compactButton")
        purge_bundles_btn.setToolTip("Remove all bundle suggestions")
        purge_bundles_btn.clicked.connect(lambda: self._purge_data("bundles"))
        maintenance_layout.addWidget(purge_bundles_btn, 2, 0)

        purge_all_btn = QPushButton("Purge All Data")
        purge_all_btn.setObjectName("dangerButton")
        purge_all_btn.setToolTip("Remove all data from extended tables (keeps schema)")
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
        png_zoom = self.config_manager.get_setting("Theme", "default_zoom_mode_png", "fit_to_width")
        self.png_zoom_combo.setCurrentText(png_zoom.replace("_", " ").title())
        zoom_layout.addWidget(self.png_zoom_combo, 0, 1)

        zoom_layout.addWidget(QLabel("PDF Zoom Mode:"), 1, 0)
        self.pdf_zoom_combo = QComboBox()
        self.pdf_zoom_combo.addItems(["Fit to Width", "Fit to Height", "Fit to Window", "Custom %"])
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
        zoom_layout.addWidget(self.pdf_zoom_percent, 3, 1)

        layout.addWidget(zoom_group)

        # System Tray Group
        tray_group = QGroupBox("System Tray")
        tray_layout = QVBoxLayout(tray_group)

        self.minimize_to_tray_checkbox = QCheckBox("Minimize to system tray")
        minimize_tray = self.config_manager.get_setting("SystemTray", "minimize_to_tray", "false")
        self.minimize_to_tray_checkbox.setChecked(minimize_tray.lower() == "true")
        tray_layout.addWidget(self.minimize_to_tray_checkbox)

        self.close_to_tray_checkbox = QCheckBox("Close to system tray (don't exit)")
        close_tray = self.config_manager.get_setting("SystemTray", "close_to_tray", "false")
        self.close_to_tray_checkbox.setChecked(close_tray.lower() == "true")
        tray_layout.addWidget(self.close_to_tray_checkbox)

        layout.addWidget(tray_group)

        layout.addStretch()
        return widget

    # Event Handlers

    def _on_provider_changed(self):
        """Update visible provider settings panel"""
        provider = self.provider_combo.currentData()

        # Safety check - ensure widgets are created before switching
        if not hasattr(self, "provider_stack"):
            return

        # Use QStackedWidget's setCurrentWidget for proper switching
        if provider == "ollama" and hasattr(self, "ollama_settings_widget"):
            self.provider_stack.setCurrentWidget(self.ollama_settings_widget)
        elif provider == "claude_cli" and hasattr(self, "claude_settings_widget"):
            self.provider_stack.setCurrentWidget(self.claude_settings_widget)
        elif provider == "gemini_cli" and hasattr(self, "gemini_settings_widget"):
            self.provider_stack.setCurrentWidget(self.gemini_settings_widget)

    def _on_auto_approval_toggled(self, state):
        """Show/hide approval delay controls"""
        is_checked = state == Qt.CheckState.Checked.value
        self.approval_delay_label.setVisible(is_checked)
        self.approval_delay_spinbox.setVisible(is_checked)

    def _browse_scan_folder(self):
        """Browse for scan folder"""
        current_path = self.scan_folder_edit.text()
        if not os.path.isdir(current_path):
            current_path = os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, "Select Scan Folder", current_path)
        if directory:
            self.scan_folder_edit.setText(directory)

    def _load_ollama_models(self):
        """Load available Ollama models"""
        self.ollama_model_combo.clear()
        try:
            local_models = self.ollama_service.list_models()
            vision_models = [
                m.get("name") or m.get("model")
                for m in local_models
                if self.ollama_service.is_vision_model(m.get("name") or m.get("model", ""))
            ]

            for model in vision_models:
                self.ollama_model_combo.addItem(model)

            # Set current model
            current_model = self.config_manager.get_setting("Ollama", "model")
            index = self.ollama_model_combo.findText(current_model)
            if index >= 0:
                self.ollama_model_combo.setCurrentIndex(index)

        except Exception as e:
            show_warning(self, "Error", f"Failed to load Ollama models: {e}")

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
                "AutoApproval",
                "enable_automatic_approvals",
                "true" if self.auto_approval_checkbox.isChecked() else "false",
            )
            self.config_manager.set_setting(
                "AutoApproval", "automatic_approval_delay", str(self.approval_delay_spinbox.value())
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
                self.config_manager.set_setting(
                    "Ollama", "model", self.ollama_model_combo.currentText()
                )
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
