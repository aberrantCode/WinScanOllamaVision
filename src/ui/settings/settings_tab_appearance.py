# mypy: disable-error-code=attr-defined
"""Appearance tab mixin for EnhancedSettingsWindow."""

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class _SettingsTabAppearanceMixin:
    """Mixin providing the Appearance settings tab."""

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
