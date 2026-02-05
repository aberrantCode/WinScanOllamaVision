"""
Theme Manager - Centralized styling for the entire application

Provides a single source of truth for all colors and styles, ensuring
consistent theming across all windows, dialogs, and widgets.
"""


class ThemeManager:
    """Manages application-wide theming with light/dark mode support"""

    @staticmethod
    def _get_colors(is_dark_mode: bool) -> dict[str, str]:
        """Get color palette for the specified theme"""
        if is_dark_mode:
            return {
                # Backgrounds
                "bg_primary": "#1E1E1E",
                "bg_secondary": "#2D2D2D",
                "bg_tertiary": "#3A3A3A",
                "bg_hover": "#4A4A4A",
                # Text
                "text_primary": "#E0E0E0",
                "text_secondary": "#B0B0B0",
                "text_tertiary": "#808080",
                "text_disabled": "#606060",
                # UI Elements
                "border": "#4A4A4A",
                "border_light": "#5A5A5A",
                "border_focus": "#3B82F6",
                # Accents
                "accent": "#3B82F6",
                "accent_hover": "#2563EB",
                "success": "#10B981",
                "warning": "#F59E0B",
                "error": "#EF4444",
                # Selection
                "selection_bg": "#3B82F640",
                "selection_text": "#E0E0E0",
            }
        else:
            return {
                # Backgrounds
                "bg_primary": "#FFFFFF",
                "bg_secondary": "#F9FAFB",
                "bg_tertiary": "#F3F4F6",
                "bg_hover": "#E5E7EB",
                # Text
                "text_primary": "#111827",
                "text_secondary": "#374151",
                "text_tertiary": "#6B7280",
                "text_disabled": "#9CA3AF",
                # UI Elements
                "border": "#E5E7EB",
                "border_light": "#F3F4F6",
                "border_focus": "#3B82F6",
                # Accents
                "accent": "#3B82F6",
                "accent_hover": "#2563EB",
                "success": "#10B981",
                "warning": "#F59E0B",
                "error": "#EF4444",
                # Selection
                "selection_bg": "#DBEAFE",
                "selection_text": "#1E40AF",
            }

    @staticmethod
    def get_stylesheet(is_dark_mode: bool = False) -> str:
        """
        Get complete application stylesheet.

        This stylesheet applies to ALL widgets in the application,
        ensuring consistent theming without per-widget styling.

        Args:
            is_dark_mode: Whether to use dark theme (default: False)

        Returns:
            Complete CSS stylesheet string
        """
        c = ThemeManager._get_colors(is_dark_mode)

        return f"""
            /* ============================================
               GLOBAL WIDGETS
               ============================================ */

            QWidget {{
                background-color: {c["bg_primary"]};
                color: {c["text_primary"]};
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 10pt;
            }}

            /* ============================================
               LABELS
               ============================================ */

            QLabel {{
                background-color: transparent;
                color: {c["text_primary"]};
                border: none;
                padding: 0px;
            }}

            /* ============================================
               BUTTONS
               ============================================ */

            QPushButton {{
                background-color: {c["bg_tertiary"]};
                color: {c["text_primary"]};
                border: 1px solid {c["border"]};
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: 500;
            }}

            QPushButton:hover {{
                background-color: {c["bg_hover"]};
                border-color: {c["border_light"]};
            }}

            QPushButton:pressed {{
                background-color: {c["border"]};
            }}

            QPushButton:disabled {{
                background-color: {c["bg_secondary"]};
                color: {c["text_disabled"]};
                border-color: {c["border"]};
            }}

            QPushButton:checked {{
                background-color: {c["accent"]};
                color: white;
                border-color: {c["accent"]};
                font-weight: 600;
            }}

            QPushButton:checked:hover {{
                background-color: {c["accent_hover"]};
            }}

            /* Dialog Buttons */
            QDialogButtonBox QPushButton {{
                min-width: 80px;
                padding: 8px 16px;
            }}

            /* ============================================
               TEXT INPUT
               ============================================ */

            QLineEdit, QTextEdit, QPlainTextEdit {{
                background-color: {c["bg_primary"]};
                color: {c["text_primary"]};
                border: 1px solid {c["border"]};
                border-radius: 4px;
                padding: 6px 10px;
                selection-background-color: {c["selection_bg"]};
                selection-color: {c["selection_text"]};
            }}

            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
                border-color: {c["border_focus"]};
                border-width: 2px;
            }}

            QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
                background-color: {c["bg_secondary"]};
                color: {c["text_disabled"]};
            }}

            /* ============================================
               COMBO BOX (DROPDOWN)
               ============================================ */

            QComboBox {{
                background-color: {c["bg_primary"]};
                color: {c["text_primary"]};
                border: 1px solid {c["border"]};
                border-radius: 4px;
                padding: 6px 10px;
                min-width: 100px;
            }}

            QComboBox:hover {{
                background-color: {c["bg_tertiary"]};
                border-color: {c["border_light"]};
            }}

            QComboBox:focus {{
                border-color: {c["border_focus"]};
            }}

            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}

            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {c["text_secondary"]};
                margin-right: 6px;
            }}

            QComboBox QAbstractItemView {{
                background-color: {c["bg_secondary"]};
                color: {c["text_primary"]};
                border: 1px solid {c["border"]};
                selection-background-color: {c["accent"]};
                selection-color: white;
                outline: none;
            }}

            QComboBox QAbstractItemView::item {{
                padding: 6px 10px;
                min-height: 24px;
            }}

            QComboBox QAbstractItemView::item:hover {{
                background-color: {c["bg_hover"]};
            }}

            /* ============================================
               CHECK BOX & RADIO BUTTON
               ============================================ */

            QCheckBox, QRadioButton {{
                background-color: transparent;
                color: {c["text_primary"]};
                spacing: 8px;
            }}

            QCheckBox::indicator, QRadioButton::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {c["border"]};
                background-color: {c["bg_primary"]};
            }}

            QCheckBox::indicator {{
                border-radius: 3px;
            }}

            QRadioButton::indicator {{
                border-radius: 9px;
            }}

            QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
                background-color: {c["accent"]};
                border-color: {c["accent"]};
            }}

            QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
                border-color: {c["accent"]};
            }}

            /* ============================================
               SPIN BOX
               ============================================ */

            QSpinBox, QDoubleSpinBox {{
                background-color: {c["bg_primary"]};
                color: {c["text_primary"]};
                border: 1px solid {c["border"]};
                border-radius: 4px;
                padding: 6px 10px;
            }}

            QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: {c["border_focus"]};
            }}

            /* ============================================
               SLIDER
               ============================================ */

            QSlider::groove:horizontal {{
                background-color: {c["bg_tertiary"]};
                height: 6px;
                border-radius: 3px;
            }}

            QSlider::handle:horizontal {{
                background-color: {c["accent"]};
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}

            QSlider::handle:horizontal:hover {{
                background-color: {c["accent_hover"]};
            }}

            /* ============================================
               PROGRESS BAR
               ============================================ */

            QProgressBar {{
                background-color: {c["bg_tertiary"]};
                border: 1px solid {c["border"]};
                border-radius: 4px;
                text-align: center;
                color: {c["text_primary"]};
                font-weight: 600;
                min-height: 20px;
            }}

            QProgressBar::chunk {{
                background-color: {c["accent"]};
                border-radius: 3px;
            }}

            /* ============================================
               SCROLL BARS
               ============================================ */

            QScrollBar:vertical {{
                background-color: {c["bg_secondary"]};
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }}

            QScrollBar::handle:vertical {{
                background-color: {c["border"]};
                border-radius: 6px;
                min-height: 30px;
            }}

            QScrollBar::handle:vertical:hover {{
                background-color: {c["border_light"]};
            }}

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}

            QScrollBar:horizontal {{
                background-color: {c["bg_secondary"]};
                height: 12px;
                border-radius: 6px;
                margin: 0px;
            }}

            QScrollBar::handle:horizontal {{
                background-color: {c["border"]};
                border-radius: 6px;
                min-width: 30px;
            }}

            QScrollBar::handle:horizontal:hover {{
                background-color: {c["border_light"]};
            }}

            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}

            /* ============================================
               TABLE VIEW
               ============================================ */

            QTableView {{
                background-color: {c["bg_primary"]};
                alternate-background-color: {c["bg_secondary"]};
                gridline-color: {c["border"]};
                border: 1px solid {c["border"]};
                border-radius: 4px;
                selection-background-color: {c["selection_bg"]};
                selection-color: {c["selection_text"]};
            }}

            QTableView::item {{
                padding: 6px;
                border: none;
            }}

            QTableView::item:selected {{
                background-color: {c["selection_bg"]};
                color: {c["selection_text"]};
            }}

            QTableView::item:hover {{
                background-color: {c["bg_tertiary"]};
            }}

            QHeaderView::section {{
                background-color: {c["bg_secondary"]};
                color: {c["text_primary"]};
                font-weight: 600;
                padding: 8px;
                border: none;
                border-bottom: 2px solid {c["border"]};
                border-right: 1px solid {c["border"]};
            }}

            QHeaderView::section:hover {{
                background-color: {c["bg_tertiary"]};
            }}

            /* ============================================
               TREE VIEW & LIST VIEW
               ============================================ */

            QTreeView, QListView {{
                background-color: {c["bg_primary"]};
                alternate-background-color: {c["bg_secondary"]};
                border: 1px solid {c["border"]};
                border-radius: 4px;
                selection-background-color: {c["selection_bg"]};
                selection-color: {c["selection_text"]};
            }}

            QTreeView::item, QListView::item {{
                padding: 4px;
            }}

            QTreeView::item:selected, QListView::item:selected {{
                background-color: {c["selection_bg"]};
                color: {c["selection_text"]};
            }}

            QTreeView::item:hover, QListView::item:hover {{
                background-color: {c["bg_tertiary"]};
            }}

            /* ============================================
               TAB WIDGET
               ============================================ */

            QTabWidget::pane {{
                border: 1px solid {c["border"]};
                border-radius: 8px;
                background-color: {c["bg_primary"]};
                top: -1px;
            }}

            QTabBar::tab {{
                background-color: {c["bg_secondary"]};
                color: {c["text_secondary"]};
                border: 1px solid {c["border"]};
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 20px;
                margin-right: 2px;
                font-size: 11pt;
            }}

            QTabBar::tab:selected {{
                background-color: {c["bg_primary"]};
                color: {c["text_primary"]};
                font-weight: 600;
                border-color: {c["border"]};
                border-bottom: 1px solid {c["bg_primary"]};
            }}

            QTabBar::tab:hover:!selected {{
                background-color: {c["bg_tertiary"]};
                color: {c["text_primary"]};
            }}

            /* ============================================
               GROUP BOX
               ============================================ */

            QGroupBox {{
                background-color: {c["bg_secondary"]};
                border: 1px solid {c["border"]};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: 600;
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 8px;
                background-color: {c["bg_primary"]};
                border-radius: 4px;
                color: {c["text_primary"]};
            }}

            /* ============================================
               FRAMES
               ============================================ */

            QFrame {{
                background-color: {c["bg_secondary"]};
                border: 1px solid {c["border"]};
                border-radius: 8px;
            }}

            QFrame[frameShape="0"] {{
                /* No frame */
                border: none;
                background-color: transparent;
            }}

            /* ============================================
               MENU
               ============================================ */

            QMenu {{
                background-color: {c["bg_secondary"]};
                color: {c["text_primary"]};
                border: 1px solid {c["border"]};
                padding: 4px;
            }}

            QMenu::item {{
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
            }}

            QMenu::item:selected {{
                background-color: {c["accent"]};
                color: white;
            }}

            QMenu::separator {{
                height: 1px;
                background-color: {c["border"]};
                margin: 4px 8px;
            }}

            /* ============================================
               TOOLTIP
               ============================================ */

            QToolTip {{
                background-color: {c["bg_tertiary"]};
                color: {c["text_primary"]};
                border: 1px solid {c["border"]};
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 9pt;
            }}

            /* ============================================
               STATUS BAR
               ============================================ */

            QStatusBar {{
                background-color: {c["bg_secondary"]};
                color: {c["text_secondary"]};
                border-top: 1px solid {c["border"]};
            }}

            QStatusBar::item {{
                border: none;
            }}

            /* ============================================
               DIALOG
               ============================================ */

            QDialog {{
                background-color: {c["bg_primary"]};
            }}

            QMessageBox {{
                background-color: {c["bg_primary"]};
            }}

            QMessageBox QLabel {{
                color: {c["text_primary"]};
            }}

            /* ============================================
               TEXT BROWSER
               ============================================ */

            QTextBrowser {{
                background-color: {c["bg_primary"]};
                color: {c["text_primary"]};
                border: 1px solid {c["border"]};
                border-radius: 4px;
                padding: 8px;
            }}
        """

    @staticmethod
    def get_colors(is_dark_mode: bool = False) -> dict[str, str]:
        """
        Get color dictionary for custom styling.

        Use this when you need direct access to theme colors
        for custom widget styling that can't be done via CSS.

        Args:
            is_dark_mode: Whether to use dark theme (default: False)

        Returns:
            Dictionary of color names to hex values
        """
        return ThemeManager._get_colors(is_dark_mode)
