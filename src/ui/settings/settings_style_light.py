"""Light theme stylesheet for the Settings window."""


def get_light_theme_stylesheet() -> str:
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
