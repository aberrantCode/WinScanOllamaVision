"""Dark theme stylesheet for the Settings window."""


def get_dark_theme_stylesheet() -> str:
    """Return the complete dark theme stylesheet."""
    return """
            /* ===== TAB WIDGET STRUCTURE ===== */
            QTabWidget::pane {
                border: 1px solid #3D3D3D;
                border-radius: 8px;
                background-color: #0B1120;
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
                background-color: #0B1120;
                color: #F3F4F6;
                border-bottom: 2px solid #0B1120;
                font-weight: 600;
            }

            QTabBar::tab:hover:!selected {
                background-color: #3D3D3D;
                color: #E5E7EB;
            }

            /* ===== CONTENT WIDGETS ===== */
            QTabWidget > QWidget {
                background-color: #0B1120;
            }

            QStackedWidget {
                background-color: #0B1120;
            }

            QStackedWidget > QWidget {
                background-color: #0B1120;
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
                background-color: #151D2F;
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
                background-color: #151D2F;
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
                background-color: #151D2F;
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
                background-color: #151D2F;
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
                background-color: #151D2F;
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
                background-color: #151D2F;
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
                background-color: #151D2F;
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
                background-color: #151D2F;
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
