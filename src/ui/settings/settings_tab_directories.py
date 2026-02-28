# mypy: disable-error-code=attr-defined
"""Directories tab mixin for EnhancedSettingsWindow."""

import os

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStyle,
    QVBoxLayout,
    QWidget,
)


class _SettingsTabDirectoriesMixin:
    """Mixin providing the Directories & Discovery settings tab."""

    def _create_directories_tab(self) -> QWidget:
        """Tab 3: Multi-Directory Management & Discovery"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Section 1: Directory Management
        dir_section_label = QLabel("Source Directories")
        dir_section_label.setStyleSheet("font-weight: bold; font-size: 11pt; padding: 5px 0px;")
        layout.addWidget(dir_section_label)

        info_label = QLabel("Manage directories to monitor for document scanning and discovery.")
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

        # Add spacing between sections
        layout.addSpacing(15)

        # Section 2: Discovery & Scheduling
        discovery_section_label = QLabel("Discovery & Scheduling")
        discovery_section_label.setStyleSheet(
            "font-weight: bold; font-size: 11pt; padding: 5px 0px;"
        )
        layout.addWidget(discovery_section_label)

        discovery_info_label = QLabel("Configure automatic file discovery and periodic scheduling.")
        discovery_info_label.setWordWrap(True)
        layout.addWidget(discovery_info_label)

        # Scan on startup checkbox
        self.scan_on_startup_checkbox = QCheckBox("Discover files on application startup")
        self.scan_on_startup_checkbox.setToolTip(
            "Automatically discover new files when the application starts.\n\n"
            "When enabled: Application will scan all directories for new files\n"
            "on startup and show a toast notification with the count.\n\n"
            "When disabled: You must manually click 'Discover Images'\n"
            "to find new files.\n\n"
            "Recommended: Enabled for frequent document scanning workflows."
        )
        scan_on_startup = self.config_manager.get_setting(
            "SourceDirectories", "scan_on_startup", "true"
        )
        self.scan_on_startup_checkbox.setChecked(scan_on_startup.lower() == "true")
        layout.addWidget(self.scan_on_startup_checkbox)

        # Enable periodic discovery checkbox
        self.discovery_enabled_checkbox = QCheckBox("Enable periodic discovery (background)")
        self.discovery_enabled_checkbox.setToolTip(
            "Automatically discover new image files on a schedule.\n\n"
            "When enabled: Application will periodically scan directories\n"
            "and register new files in the background.\n\n"
            "When disabled: Discovery only runs manually or on startup."
        )
        discovery_enabled = self.config_manager.get_bool("Discovery", "enabled", True)
        self.discovery_enabled_checkbox.setChecked(discovery_enabled)
        layout.addWidget(self.discovery_enabled_checkbox)

        # Discovery interval
        interval_layout = QHBoxLayout()
        interval_label = QLabel("  Discovery interval:")
        interval_label.setToolTip(
            "How often to scan for new files.\n\n"
            "Recommended: 60 minutes for normal use\n"
            "Lower values increase CPU/disk usage but find new files faster."
        )
        interval_layout.addWidget(interval_label)

        self.discovery_interval_spinbox = QSpinBox()
        self.discovery_interval_spinbox.setRange(1, 1440)  # 1 minute to 24 hours
        self.discovery_interval_spinbox.setSuffix(" min")
        discovery_interval = self.config_manager.get_int("Discovery", "interval_minutes", 60)
        self.discovery_interval_spinbox.setValue(discovery_interval)
        self.discovery_interval_spinbox.setToolTip(
            "Time between automatic discovery runs.\n\n"
            "Range: 1 to 1440 minutes (1 minute to 24 hours)\n"
            "Default: 60 minutes"
        )
        interval_layout.addWidget(self.discovery_interval_spinbox)
        interval_layout.addStretch()
        layout.addLayout(interval_layout)

        # Auto-analyze after discovery checkbox
        self.auto_analyze_checkbox = QCheckBox("Auto-analyze files after discovery")
        self.auto_analyze_checkbox.setToolTip(
            "Automatically start LLM analysis after discovering new files.\n\n"
            "When enabled: Discovery will launch the Analysis window\n"
            "if new files are found.\n\n"
            "When disabled: Files are only registered, analysis must be\n"
            "triggered manually.\n\n"
            "Recommended: Disabled for manual control over analysis."
        )
        auto_analyze = self.config_manager.get_bool(
            "Discovery", "auto_analyze_after_discovery", False
        )
        self.auto_analyze_checkbox.setChecked(auto_analyze)
        layout.addWidget(self.auto_analyze_checkbox)

        # Last discovery run timestamp (read-only)
        last_run_layout = QHBoxLayout()
        last_run_label = QLabel("  Last discovery run:")
        last_run_layout.addWidget(last_run_label)

        last_run = self.config_manager.get_setting("Discovery", "last_run", "Never")
        if last_run and last_run != "Never":
            try:
                from datetime import datetime

                # Parse ISO format timestamp
                dt = datetime.fromisoformat(last_run)
                last_run_display = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                last_run_display = last_run
        else:
            last_run_display = "Never"

        self.last_run_value_label = QLabel(last_run_display)
        self.last_run_value_label.setStyleSheet("color: #666;")
        last_run_layout.addWidget(self.last_run_value_label)
        last_run_layout.addStretch()
        layout.addLayout(last_run_layout)

        # Add spacing between sections
        layout.addSpacing(15)

        # Section 3: Export Directory
        export_section_label = QLabel("Export Directory")
        export_section_label.setStyleSheet("font-weight: bold; font-size: 11pt; padding: 5px 0px;")
        layout.addWidget(export_section_label)

        export_info_label = QLabel("Where to save generated PDF files.")
        export_info_label.setWordWrap(True)
        layout.addWidget(export_info_label)

        # Radio buttons in a group
        self._export_radio_group = QButtonGroup(self)

        # --- Static location radio ---
        self.export_static_radio = QRadioButton("Static location – all PDFs go to one fixed folder")
        self._export_radio_group.addButton(self.export_static_radio)
        layout.addWidget(self.export_static_radio)

        static_path_layout = QHBoxLayout()
        static_path_layout.setContentsMargins(20, 0, 0, 0)
        self.export_static_path_edit = QLineEdit()
        self.export_static_path_edit.setPlaceholderText("path/to/output/folder")
        self.export_static_path_edit.setToolTip("Fixed output folder for all generated PDFs.")
        static_path_layout.addWidget(self.export_static_path_edit)

        self.export_static_browse_btn = QPushButton()
        style = self.style()
        if style is not None:
            self.export_static_browse_btn.setIcon(
                style.standardIcon(QStyle.StandardPixmap.SP_DirIcon)
            )
        self.export_static_browse_btn.setToolTip("Browse for folder")
        self.export_static_browse_btn.setFixedSize(36, 36)
        self.export_static_browse_btn.setIconSize(QSize(18, 18))
        self.export_static_browse_btn.setFlat(True)
        self.export_static_browse_btn.setObjectName("iconButton")
        self.export_static_browse_btn.clicked.connect(self._browse_export_static_folder)
        static_path_layout.addWidget(self.export_static_browse_btn)
        layout.addLayout(static_path_layout)

        # --- Subfolder within source radio ---
        self.export_subfolder_radio = QRadioButton("Subfolder within each source directory")
        self._export_radio_group.addButton(self.export_subfolder_radio)
        layout.addWidget(self.export_subfolder_radio)

        subfolder_name_layout = QHBoxLayout()
        subfolder_name_layout.setContentsMargins(20, 0, 0, 0)
        subfolder_name_layout.addWidget(QLabel("Subfolder name:"))
        self.export_subfolder_name_edit = QLineEdit()
        self.export_subfolder_name_edit.setPlaceholderText("PDFs")
        self.export_subfolder_name_edit.setToolTip(
            "Name of the subfolder created inside each source directory."
        )
        self.export_subfolder_name_edit.setFixedWidth(160)
        subfolder_name_layout.addWidget(self.export_subfolder_name_edit)
        subfolder_name_layout.addStretch()
        layout.addLayout(subfolder_name_layout)

        # --- Beside source files radio ---
        self.export_beside_radio = QRadioButton("Beside source files (no subfolder)")
        self._export_radio_group.addButton(self.export_beside_radio)
        layout.addWidget(self.export_beside_radio)

        # Load from config
        export_strategy = self.config_manager.get_setting(
            "OutputDirectory", "strategy", "same_as_source"
        )
        self.export_static_radio.setChecked(export_strategy == "global_custom")
        self.export_subfolder_radio.setChecked(export_strategy == "same_as_source")
        self.export_beside_radio.setChecked(export_strategy == "beside_source")
        self.export_static_path_edit.setText(
            self.config_manager.get_setting("OutputDirectory", "global_custom_path", "")
        )
        self.export_subfolder_name_edit.setText(
            self.config_manager.get_setting("OutputDirectory", "subdirectory_name", "PDFs")
        )

        # Connect radios to enable/disable sub-widgets
        self.export_static_radio.toggled.connect(self._update_export_strategy_ui)
        self.export_subfolder_radio.toggled.connect(self._update_export_strategy_ui)
        self.export_beside_radio.toggled.connect(self._update_export_strategy_ui)
        self._update_export_strategy_ui()

        layout.addStretch()
        return widget

    def _update_export_strategy_ui(self) -> None:
        """Enable/disable export sub-widgets based on the selected radio button."""
        is_static = self.export_static_radio.isChecked()
        is_subfolder = self.export_subfolder_radio.isChecked()
        self.export_static_path_edit.setEnabled(is_static)
        self.export_static_browse_btn.setEnabled(is_static)
        self.export_subfolder_name_edit.setEnabled(is_subfolder)

    def _browse_export_static_folder(self) -> None:
        """Browse for the static export output folder."""
        current_path = self.export_static_path_edit.text()
        if not os.path.isdir(current_path):
            current_path = os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, "Select Export Folder", current_path)
        if directory:
            self.export_static_path_edit.setText(directory)

    def _current_export_strategy(self) -> str:
        """Return the currently selected export strategy key."""
        if self.export_static_radio.isChecked():
            return "global_custom"
        if self.export_beside_radio.isChecked():
            return "beside_source"
        return "same_as_source"
