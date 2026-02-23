"""Worker threads and helper dialog classes for the Settings window."""

import logging
import subprocess
from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)

from config.config_manager import ConfigManager
from llm_providers.provider_factory import ProviderFactory

if TYPE_CHECKING:
    from ui.settings_window_enhanced import EnhancedSettingsWindow

logger: logging.Logger | None = None


def _get_logger() -> logging.Logger:
    """Get logger instance (lazy initialization)."""
    global logger
    if logger is None:
        from services.logging_service import get_logger as _gl

        logger = _gl()
    return logger


class ExpandablePromptEdit(QPlainTextEdit):
    """Custom text edit that expands based on content"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setMaximumHeight(200)

    def _get_logger(self) -> logging.Logger:
        """Get logger instance (lazy initialization)."""
        return _get_logger()


class PromptOptimizationThread(QThread):
    """Background thread for prompt optimization"""

    finished = pyqtSignal(bool, str, str)  # success, optimized_prompt, error_message

    def __init__(self, config_manager: ConfigManager, current_prompt: str):
        super().__init__()
        self.config_manager = config_manager
        self.current_prompt = current_prompt

    def _get_logger(self) -> logging.Logger:
        """Get logger instance (lazy initialization)."""
        return _get_logger()

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

        self._setup_ui()

    def _get_logger(self) -> logging.Logger:
        """Get logger instance (lazy initialization)."""
        return _get_logger()

    def _setup_ui(self):
        """Setup UI components."""
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
        self.original_text.setPlainText(self.original_prompt)
        self.original_text.setReadOnly(True)
        original_layout.addWidget(self.original_text)
        splitter_layout.addWidget(original_group)

        # Optimized prompt
        optimized_group = QGroupBox("Optimized Prompt")
        optimized_layout = QVBoxLayout(optimized_group)
        self.optimized_text = QPlainTextEdit()
        self.optimized_text.setPlainText(self.optimized_prompt)
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


class ModelLoadingWorker(QThread):
    """Background worker for loading models from providers without blocking UI"""

    finished = pyqtSignal()  # Emitted when all models are loaded
    error = pyqtSignal(str)  # Emitted if loading fails

    def __init__(self, settings_window: "EnhancedSettingsWindow"):
        super().__init__()
        self.settings_window = settings_window

    def _get_logger(self) -> logging.Logger:
        """Get logger instance (lazy initialization)."""
        return _get_logger()

    def run(self):
        """Load models in background thread"""
        try:
            self._get_logger().debug("[MODEL LOADING] Starting background model loading")

            # Load all models (these methods already have caching)
            self.settings_window._load_ollama_models()
            self.settings_window._load_claude_models()
            self.settings_window._load_gemini_models()

            self._get_logger().debug("[MODEL LOADING] All models loaded successfully")
            self.finished.emit()

        except Exception as e:
            self._get_logger().error(f"[MODEL LOADING] Error loading models: {e}")
            self.error.emit(str(e))
