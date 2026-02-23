# mypy: disable-error-code=attr-defined
"""LLM Provider tab mixin for EnhancedSettingsWindow."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class _SettingsTabProviderMixin:
    """Mixin providing the LLM Provider settings tab."""

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

        # Don't load models here - will be loaded from showEvent after initialization
        # to prevent race conditions with change tracking

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
