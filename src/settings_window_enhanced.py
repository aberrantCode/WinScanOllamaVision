"""
Enhanced Settings Window for WinScanLLM - Phase 6 Implementation
Comprehensive 5-tab settings interface with multi-provider support
"""

import os
import sys
import json
from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QCheckBox, QSpinBox,
    QListWidget, QListWidgetItem, QTextEdit, QPlainTextEdit, QFileDialog,
    QMessageBox, QDialogButtonBox, QGroupBox, QSizePolicy, QStyle,
    QProgressBar, QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon

# Import existing components
try:
    from config_manager import ConfigManager
    from metadata_db import MetadataDB
    from analysis_db import AnalysisDB
    from ollama_service import OllamaService
    from llm_providers.provider_factory import ProviderFactory
except ImportError:
    # Fallback for different import paths
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from config_manager import ConfigManager
    from metadata_db import MetadataDB
    from analysis_db import AnalysisDB
    from ollama_service import OllamaService
    from llm_providers.provider_factory import ProviderFactory


class ExpandablePromptEdit(QPlainTextEdit):
    """Custom text edit that expands based on content"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setMaximumHeight(200)


class EnhancedSettingsWindow(QDialog):
    """Enhanced Settings Window with 5-tab interface"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.metadata_db = MetadataDB()
        self.analysis_db = AnalysisDB()

        # Initialize Ollama service (for backward compatibility)
        timeout = float(self.config_manager.get_setting('Ollama', 'timeout', '300'))
        self.ollama_service = OllamaService(
            base_url=self.config_manager.get_setting('Ollama', 'base_url'),
            timeout=timeout
        )

        app_name = self.config_manager.get_setting("GUI", "app_name", "WinScanLLM")
        self.setWindowTitle(f"{app_name} - Settings")
        icon_path = os.path.join("assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setMinimumWidth(750)
        self.setMinimumHeight(600)
        self._init_ui()

    def _init_ui(self):
        """Initialize the tabbed UI"""
        layout = QVBoxLayout(self)

        # Create tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #CCCCCC;
                border-radius: 3px;
            }
            QTabBar::tab {
                background: #F0F0F0;
                border: 1px solid #CCCCCC;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom-color: white;
            }
            QLineEdit, QComboBox, QPlainTextEdit, QSpinBox {
                background-color: white;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 5px;
                color: black;
            }
            QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QSpinBox:focus {
                border: 2px solid #0078D7;
            }
        """)

        # Create tabs
        self.tabs.addTab(self._create_general_tab(), "General")
        self.tabs.addTab(self._create_llm_provider_tab(), "LLM Provider")
        self.tabs.addTab(self._create_directories_tab(), "Directories")
        self.tabs.addTab(self._create_database_tab(), "Database")
        self.tabs.addTab(self._create_appearance_tab(), "Appearance")

        layout.addWidget(self.tabs)

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
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
        audit_info.setStyleSheet("color: #666; font-size: 10px;")
        audit_info.setWordWrap(True)
        audit_layout.addWidget(audit_info)

        layout.addWidget(audit_group)

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
        pages_prompt_default = """You are an expert document analyst. Examine the provided images. Determine if all pages belong to the *same continuous physical document*. Respond ONLY with 'YES' if all pages are from the same document, or 'NO' if they are not. Do not add any other text or explanation."""
        pages_prompt = self.config_manager.get_setting("Prompts", "document_pages", pages_prompt_default)
        self.pages_prompt_edit.setPlainText(pages_prompt)
        prompts_layout.addWidget(self.pages_prompt_edit)

        pages_buttons = QHBoxLayout()
        optimize_pages_btn = QPushButton("Optimize Prompt")
        optimize_pages_btn.clicked.connect(lambda: self._optimize_prompt(self.pages_prompt_edit))
        reset_pages_btn = QPushButton("Reset to Default")
        reset_pages_btn.clicked.connect(lambda: self.pages_prompt_edit.setPlainText(pages_prompt_default))
        pages_buttons.addWidget(optimize_pages_btn)
        pages_buttons.addWidget(reset_pages_btn)
        pages_buttons.addStretch()
        prompts_layout.addLayout(pages_buttons)

        # Document Metadata Prompt
        prompts_layout.addWidget(QLabel("Metadata Extraction Prompt:"))
        self.metadata_prompt_edit = ExpandablePromptEdit()
        metadata_prompt_default = """You are an expert at extracting key information from scanned documents.
Analyze the provided images to identify the following:
1. **Source Company:** The name of the organization that issued the document. Look at headers, footers, logos, or return addresses.
2. **Document Title:** The main purpose or type of the document (e.g., Invoice, Statement, Bill, Receipt, Report, Contract, Agreement).
3. **Relevant Date:** The primary date associated with the document (e.g., issue date, statement date, invoice date, contract date). Prioritize the most prominent and relevant date.

Respond ONLY in JSON format. Your JSON should contain three keys: 'company', 'title', and 'date'.
If any information cannot be found, use null for its value.

Example: { "company": "Acme Corp", "title": "Invoice", "date": "2023-10-26" }"""
        metadata_prompt = self.config_manager.get_setting("Prompts", "document_metadata", metadata_prompt_default)
        self.metadata_prompt_edit.setPlainText(metadata_prompt)
        prompts_layout.addWidget(self.metadata_prompt_edit)

        metadata_buttons = QHBoxLayout()
        optimize_metadata_btn = QPushButton("Optimize Prompt")
        optimize_metadata_btn.clicked.connect(lambda: self._optimize_prompt(self.metadata_prompt_edit))
        reset_metadata_btn = QPushButton("Reset to Default")
        reset_metadata_btn.clicked.connect(lambda: self.metadata_prompt_edit.setPlainText(metadata_prompt_default))
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
        self.ollama_model_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.ollama_model_combo, 0, 1)

        download_btn = QPushButton("Download Model")
        download_btn.clicked.connect(self._download_ollama_model)
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

        # Load Ollama models
        self._load_ollama_models()

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
        template_help.setStyleSheet("color: #666; font-size: 10px;")
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
        template_help.setStyleSheet("color: #666; font-size: 10px;")
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
        info_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(info_label)

        # Directory list
        self.directories_list = QListWidget()
        self.directories_list.setAlternatingRowColors(True)
        self.directories_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #CCCCCC;
                border-radius: 3px;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:selected {
                background-color: #0078D7;
                color: white;
            }
        """)

        # Load existing directories
        directories = self.config_manager.get_directories()
        for directory in directories:
            self.directories_list.addItem(directory)

        layout.addWidget(self.directories_list)

        # Buttons
        button_layout = QHBoxLayout()

        add_btn = QPushButton("Add Directory")
        add_btn.clicked.connect(self._add_directory)
        button_layout.addWidget(add_btn)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_directory)
        button_layout.addWidget(remove_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Scan on startup checkbox
        self.scan_on_startup_checkbox = QCheckBox("Scan all directories on application startup")
        scan_on_startup = self.config_manager.get_setting("SourceDirectories", "scan_on_startup", "true")
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
        stats_btn.clicked.connect(self._show_database_statistics)
        stats_layout.addWidget(stats_btn)

        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(150)
        self.stats_text.setStyleSheet("""
            QTextEdit {
                background-color: #F8F8F8;
                font-family: 'Courier New', monospace;
                font-size: 10px;
            }
        """)
        stats_layout.addWidget(self.stats_text)

        layout.addWidget(stats_group)

        # Maintenance Group
        maintenance_group = QGroupBox("Database Maintenance")
        maintenance_layout = QGridLayout(maintenance_group)

        backup_btn = QPushButton("Create Backup")
        backup_btn.setToolTip("Create a timestamped backup of the database")
        backup_btn.clicked.connect(self._backup_database)
        maintenance_layout.addWidget(backup_btn, 0, 0)

        purge_cache_btn = QPushButton("Purge Cached Metadata")
        purge_cache_btn.setToolTip("Remove all cached metadata (forces re-analysis)")
        purge_cache_btn.clicked.connect(lambda: self._purge_data("cache"))
        maintenance_layout.addWidget(purge_cache_btn, 1, 0)

        purge_analysis_btn = QPushButton("Purge Analysis Results")
        purge_analysis_btn.setToolTip("Remove all analysis results")
        purge_analysis_btn.clicked.connect(lambda: self._purge_data("analysis"))
        maintenance_layout.addWidget(purge_analysis_btn, 1, 1)

        purge_bundles_btn = QPushButton("Purge Bundle Suggestions")
        purge_bundles_btn.setToolTip("Remove all bundle suggestions")
        purge_bundles_btn.clicked.connect(lambda: self._purge_data("bundles"))
        maintenance_layout.addWidget(purge_bundles_btn, 2, 0)

        purge_all_btn = QPushButton("Purge All Data")
        purge_all_btn.setToolTip("Remove all data from extended tables (keeps schema)")
        purge_all_btn.setStyleSheet("QPushButton { background-color: #D13438; color: white; }")
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
        theme_note.setStyleSheet("color: #666; font-size: 10px;")
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

        # Use QStackedWidget's setCurrentWidget for proper switching
        if provider == "ollama":
            self.provider_stack.setCurrentWidget(self.ollama_settings_widget)
        elif provider == "claude_cli":
            self.provider_stack.setCurrentWidget(self.claude_settings_widget)
        elif provider == "gemini_cli":
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
                m.get('name') or m.get('model') for m in local_models
                if self.ollama_service.is_vision_model(m.get('name') or m.get('model', ''))
            ]

            for model in vision_models:
                self.ollama_model_combo.addItem(model)

            # Set current model
            current_model = self.config_manager.get_setting("Ollama", "model")
            index = self.ollama_model_combo.findText(current_model)
            if index >= 0:
                self.ollama_model_combo.setCurrentIndex(index)

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load Ollama models: {e}")

    def _download_ollama_model(self):
        """Download an Ollama model"""
        QMessageBox.information(
            self, "Download Model",
            "Model download functionality will be implemented in next phase.\n"
            "For now, use 'ollama pull <model-name>' in terminal."
        )

    def _optimize_prompt(self, prompt_edit: QPlainTextEdit):
        """Use AI to optimize a prompt"""
        current_prompt = prompt_edit.toPlainText()

        reply = QMessageBox.question(
            self, "Optimize Prompt",
            "This will send your current prompt to the active LLM provider for optimization.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(
                self, "Coming Soon",
                "AI prompt optimization will be fully implemented in next phase.\n"
                "For now, you can manually edit prompts."
            )

    def _add_directory(self):
        """Add a new directory to the list"""
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            # Check if already in list
            for i in range(self.directories_list.count()):
                if self.directories_list.item(i).text() == directory:
                    QMessageBox.information(
                        self, "Already Added",
                        "This directory is already in the list."
                    )
                    return

            self.directories_list.addItem(directory)

    def _remove_directory(self):
        """Remove selected directory from list"""
        current_item = self.directories_list.currentItem()
        if current_item:
            reply = QMessageBox.question(
                self, "Remove Directory",
                f"Remove this directory from monitoring?\n\n{current_item.text()}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
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
            stats_text += f"  Bundle Suggestions: {analysis_stats.get('total_bundle_suggestions', 0)}\n"
            stats_text += f"  High Confidence Bundles: {analysis_stats.get('high_confidence_bundles', 0)}\n"

            self.stats_text.setPlainText(stats_text)

        except Exception as e:
            self.stats_text.setPlainText(f"Error loading statistics: {e}")

    def _backup_database(self):
        """Create database backup"""
        try:
            backup_path = self.metadata_db.create_backup()
            QMessageBox.information(
                self, "Backup Created",
                f"Database backup created successfully:\n\n{backup_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Backup Failed",
                f"Failed to create database backup:\n\n{e}"
            )

    def _purge_data(self, data_type: str):
        """Purge database data"""
        type_names = {
            "cache": "cached metadata",
            "analysis": "analysis results",
            "bundles": "bundle suggestions",
            "all": "ALL DATA"
        }

        reply = QMessageBox.warning(
            self, "Confirm Purge",
            f"Are you sure you want to purge {type_names[data_type]}?\n\n"
            "This action cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
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

                QMessageBox.information(self, "Purge Complete", f"Successfully purged {type_names[data_type]}.")
                self._show_database_statistics()  # Refresh stats

            except Exception as e:
                QMessageBox.critical(self, "Purge Failed", f"Failed to purge data:\n\n{e}")

    def save_settings(self):
        """Save all settings"""
        try:
            # General Tab
            self.config_manager.set_setting("DocumentProcessing", "scan_folder", self.scan_folder_edit.text())
            self.config_manager.set_setting("AutoApproval", "enable_automatic_approvals",
                                           "true" if self.auto_approval_checkbox.isChecked() else "false")
            self.config_manager.set_setting("AutoApproval", "automatic_approval_delay",
                                           str(self.approval_delay_spinbox.value()))
            self.config_manager.set_setting("AuditTrail", "enabled",
                                           "true" if self.audit_trail_checkbox.isChecked() else "false")

            # LLM Provider Tab
            active_provider = self.provider_combo.currentData()
            self.config_manager.set_setting("LLMProvider", "active_provider", active_provider)

            if active_provider == "ollama":
                self.config_manager.set_setting("Ollama", "model", self.ollama_model_combo.currentText())
                self.config_manager.set_setting("Ollama", "base_url", self.ollama_url_edit.text())
                self.config_manager.set_setting("Ollama", "timeout", str(self.ollama_timeout_spin.value()))
            elif active_provider == "claude_cli":
                self.config_manager.set_setting("ClaudeCLI", "default_model", self.claude_model_combo.currentText())
                self.config_manager.set_setting("ClaudeCLI", "command_template", self.claude_command_edit.toPlainText())
                self.config_manager.set_setting("ClaudeCLI", "timeout", str(self.claude_timeout_spin.value()))
            elif active_provider == "gemini_cli":
                self.config_manager.set_setting("GeminiCLI", "default_model", self.gemini_model_combo.currentText())
                self.config_manager.set_setting("GeminiCLI", "command_template", self.gemini_command_edit.toPlainText())
                self.config_manager.set_setting("GeminiCLI", "timeout", str(self.gemini_timeout_spin.value()))

            # Save prompts
            self.config_manager.set_setting("Prompts", "document_pages", self.pages_prompt_edit.toPlainText())
            self.config_manager.set_setting("Prompts", "document_metadata", self.metadata_prompt_edit.toPlainText())

            # Directories Tab
            directories = [self.directories_list.item(i).text() for i in range(self.directories_list.count())]
            self.config_manager.set_setting("SourceDirectories", "directories", json.dumps(directories))
            self.config_manager.set_setting("SourceDirectories", "scan_on_startup",
                                           "true" if self.scan_on_startup_checkbox.isChecked() else "false")

            # Appearance Tab
            self.config_manager.set_setting("Theme", "theme", self.theme_combo.currentData())
            png_zoom = self.png_zoom_combo.currentText().lower().replace(" ", "_")
            pdf_zoom = self.pdf_zoom_combo.currentText().lower().replace(" ", "_")
            self.config_manager.set_setting("Theme", "default_zoom_mode_png", png_zoom)
            self.config_manager.set_setting("Theme", "default_zoom_mode_pdf", pdf_zoom)
            self.config_manager.set_setting("Theme", "default_zoom_percent_png", str(self.png_zoom_percent.value()))
            self.config_manager.set_setting("Theme", "default_zoom_percent_pdf", str(self.pdf_zoom_percent.value()))
            self.config_manager.set_setting("SystemTray", "minimize_to_tray",
                                           "true" if self.minimize_to_tray_checkbox.isChecked() else "false")
            self.config_manager.set_setting("SystemTray", "close_to_tray",
                                           "true" if self.close_to_tray_checkbox.isChecked() else "false")

            QMessageBox.information(self, "Settings Saved", "Your settings have been saved successfully.")
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Failed to save settings:\n\n{e}")


# For backward compatibility, alias to old name
SettingsWindow = EnhancedSettingsWindow


if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = EnhancedSettingsWindow()
    window.show()
    sys.exit(app.exec())
