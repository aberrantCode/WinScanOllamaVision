"""Base stylesheet builder for the Settings window.

Uses a color-token dict to generate theme-specific QSS without duplicating
the entire stylesheet for each theme.
"""

_DARK_TOKENS: dict[str, str] = {
    # Backgrounds
    "bg_primary": "#0B1120",
    "bg_secondary": "#252525",
    "bg_input": "#151D2F",
    "bg_input_focus": "#353535",
    "bg_disabled": "#252525",
    "bg_button_secondary": "#3D3D3D",
    "bg_scroll": "#252525",
    "bg_scroll_handle": "#4B5563",
    "bg_scroll_handle_hover": "#6B7280",
    "bg_progress": "#3D3D3D",
    "bg_list_item": "#151D2F",
    "bg_list_alternate": "#353535",
    "bg_spinbox_button": "#3D3D3D",
    "bg_spinbox_button_hover": "#4B5563",
    "bg_spinbox_button_pressed": "#6B7280",
    # Borders
    "border_normal": "#3D3D3D",
    "border_hover": "#4B5563",
    "border_focus": "#3B82F6",
    "border_disabled": "#3D3D3D",
    # Text
    "text_primary": "#F3F4F6",
    "text_secondary": "#E5E7EB",
    "text_muted": "#9CA3AF",
    "text_disabled": "#6B7280",
    "text_tab": "#9CA3AF",
    "text_tab_selected": "#F3F4F6",
    "text_tab_hover": "#E5E7EB",
    # Selection
    "selection_bg": "#1E40AF",
    "selection_color": "#FFFFFF",
    "selection_item_hover": "#3D3D3D",
    # Checkbox
    "checkbox_border": "#4B5563",
    "checkbox_bg": "#151D2F",
    "checkbox_checked": "#3B82F6",
    "checkbox_checked_hover": "#60A5FA",
    "checkbox_disabled_bg": "#252525",
    "checkbox_disabled_border": "#3D3D3D",
    # Arrow colors
    "arrow_combo": "#9CA3AF",
    "arrow_spin": "#9CA3AF",
    # Tooltip
    "tooltip_bg": "#F3F4F6",
    "tooltip_color": "#1E1E1E",
    "tooltip_border": "#9CA3AF",
    # Progress bar
    "progress_chunk": "#3B82F6",
    # Misc
    "group_title_bg": "#252525",
    "texteditor_bg": "#252525",
    "texteditor_color": "#E5E7EB",
    # Danger/secondary buttons
    "danger_bg": "#EF4444",
    "danger_hover": "#F87171",
    "danger_pressed": "#DC2626",
    "secondary_bg": "#3D3D3D",
    "secondary_color": "#E5E7EB",
    "secondary_border": "#4B5563",
    "secondary_hover_bg": "#4B5563",
    "secondary_hover_border": "#6B7280",
    # List selected
    "list_selected_bg": "#3B82F6",
    "list_hover_bg": "#3D3D3D",
}

_LIGHT_TOKENS: dict[str, str] = {
    # Backgrounds
    "bg_primary": "#FFFFFF",
    "bg_secondary": "#FFFFFF",
    "bg_input": "#FFFFFF",
    "bg_input_focus": "#F0F9FF",
    "bg_disabled": "#F3F4F6",
    "bg_button_secondary": "#F3F4F6",
    "bg_scroll": "#F3F4F6",
    "bg_scroll_handle": "#D1D5DB",
    "bg_scroll_handle_hover": "#9CA3AF",
    "bg_progress": "#E5E7EB",
    "bg_list_item": "#FFFFFF",
    "bg_list_alternate": "#F9FAFB",
    "bg_spinbox_button": "#F3F4F6",
    "bg_spinbox_button_hover": "#E5E7EB",
    "bg_spinbox_button_pressed": "#D1D5DB",
    # Borders
    "border_normal": "#E5E7EB",
    "border_hover": "#D1D5DB",
    "border_focus": "#2563EB",
    "border_disabled": "#E5E7EB",
    # Text
    "text_primary": "#111827",
    "text_secondary": "#374151",
    "text_muted": "#374151",
    "text_disabled": "#9CA3AF",
    "text_tab": "#374151",
    "text_tab_selected": "#111827",
    "text_tab_hover": "#111827",
    # Selection
    "selection_bg": "#DBEAFE",
    "selection_color": "#1E40AF",
    "selection_item_hover": "#F3F4F6",
    # Checkbox
    "checkbox_border": "#D1D5DB",
    "checkbox_bg": "#FFFFFF",
    "checkbox_checked": "#2563EB",
    "checkbox_checked_hover": "#1E40AF",
    "checkbox_disabled_bg": "#F3F4F6",
    "checkbox_disabled_border": "#E5E7EB",
    # Arrow colors
    "arrow_combo": "#6B7280",
    "arrow_spin": "#6B7280",
    # Tooltip
    "tooltip_bg": "#1F2937",
    "tooltip_color": "#F9FAFB",
    "tooltip_border": "#374151",
    # Progress bar
    "progress_chunk": "#2563EB",
    # Misc
    "group_title_bg": "#FFFFFF",
    "texteditor_bg": "#F9FAFB",
    "texteditor_color": "#111827",
    # Danger/secondary buttons
    "danger_bg": "#DC2626",
    "danger_hover": "#B91C1C",
    "danger_pressed": "#991B1B",
    "secondary_bg": "#F3F4F6",
    "secondary_color": "#374151",
    "secondary_border": "#D1D5DB",
    "secondary_hover_bg": "#E5E7EB",
    "secondary_hover_border": "#9CA3AF",
    # List selected
    "list_selected_bg": "#2563EB",
    "list_hover_bg": "#DBEAFE",
}


def get_settings_stylesheet(is_dark: bool) -> str:
    """Return the complete settings-window stylesheet for the given theme.

    Args:
        is_dark: If True, use dark-theme color tokens; otherwise use light tokens.

    Returns:
        QSS stylesheet string.
    """
    t = _DARK_TOKENS if is_dark else _LIGHT_TOKENS
    tab_pane_border_bottom = t["bg_primary"]  # makes selected tab merge with pane

    return f"""
            /* ===== TAB WIDGET STRUCTURE ===== */
            QTabWidget::pane {{
                border: 1px solid {t["border_normal"]};
                border-radius: 8px;
                background-color: {t["bg_primary"]};
                padding: 0;
            }}

            QTabBar::tab {{
                background-color: {t["bg_secondary"]};
                color: {t["text_tab"]};
                border: 1px solid {t["border_normal"]};
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 20px;
                margin-right: 2px;
                font-weight: 500;
            }}

            QTabBar::tab:selected {{
                background-color: {t["bg_primary"]};
                color: {t["text_tab_selected"]};
                border-bottom: 2px solid {tab_pane_border_bottom};
                font-weight: 600;
            }}

            QTabBar::tab:hover:!selected {{
                background-color: {t["border_normal"]};
                color: {t["text_tab_hover"]};
            }}

            /* ===== CONTENT WIDGETS ===== */
            QTabWidget > QWidget {{
                background-color: {t["bg_primary"]};
            }}

            QStackedWidget {{
                background-color: {t["bg_primary"]};
            }}

            QStackedWidget > QWidget {{
                background-color: {t["bg_primary"]};
            }}

            /* ===== GROUP BOXES ===== */
            QGroupBox {{
                background-color: {t["bg_secondary"]};
                border: 1px solid {t["border_normal"]};
                border-radius: 8px;
                margin-top: 16px;
                padding: 16px;
                padding-top: 24px;
                font-weight: 600;
                color: {t["text_primary"]};
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                top: 4px;
                padding: 0 8px;
                background-color: {t["group_title_bg"]};
                color: {t["text_primary"]};
                font-size: 10pt;
            }}

            /* ===== TEXT INPUTS ===== */
            QLineEdit {{
                background-color: {t["bg_input"]};
                border: 2px solid {t["border_normal"]};
                border-radius: 6px;
                padding: 8px 12px;
                color: {t["text_primary"]};
                font-size: 10pt;
                selection-background-color: {t["selection_bg"]};
                selection-color: {t["selection_color"]};
            }}

            QLineEdit:focus {{
                border-color: {t["border_focus"]};
                background-color: {t["bg_input_focus"]};
            }}

            QLineEdit:hover:!focus {{
                border-color: {t["border_hover"]};
            }}

            QLineEdit:disabled {{
                background-color: {t["bg_disabled"]};
                color: {t["text_disabled"]};
                border-color: {t["border_disabled"]};
            }}

            QPlainTextEdit {{
                background-color: {t["bg_input"]};
                border: 2px solid {t["border_normal"]};
                border-radius: 6px;
                padding: 8px 12px;
                color: {t["text_primary"]};
                font-size: 10pt;
                selection-background-color: {t["selection_bg"]};
                selection-color: {t["selection_color"]};
            }}

            QPlainTextEdit:focus {{
                border-color: {t["border_focus"]};
                background-color: {t["bg_input_focus"]};
            }}

            QPlainTextEdit:hover:!focus {{
                border-color: {t["border_hover"]};
            }}

            QTextEdit {{
                background-color: {t["texteditor_bg"]};
                border: 1px solid {t["border_normal"]};
                border-radius: 6px;
                padding: 8px;
                color: {t["texteditor_color"]};
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
                selection-background-color: {t["selection_bg"]};
                selection-color: {t["selection_color"]};
            }}

            QTextEdit:focus {{
                border-color: {t["border_focus"]};
            }}

            /* ===== DROPDOWNS ===== */
            QComboBox {{
                background-color: {t["bg_input"]};
                border: 2px solid {t["border_normal"]};
                border-radius: 6px;
                padding: 8px 12px;
                color: {t["text_primary"]};
                font-size: 10pt;
                min-height: 20px;
            }}

            QComboBox:hover {{
                border-color: {t["border_hover"]};
            }}

            QComboBox:focus {{
                border-color: {t["border_focus"]};
            }}

            QComboBox:disabled {{
                background-color: {t["bg_disabled"]};
                color: {t["text_disabled"]};
            }}

            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}

            QComboBox::down-arrow {{
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {t["arrow_combo"]};
                margin-right: 8px;
            }}

            QComboBox QAbstractItemView {{
                background-color: {t["bg_input"]};
                border: 2px solid {t["border_normal"]};
                border-radius: 6px;
                selection-background-color: {t["selection_bg"]};
                selection-color: {t["selection_color"]};
                padding: 4px;
                color: {t["text_primary"]};
                outline: none;
            }}

            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                min-height: 24px;
            }}

            QComboBox QAbstractItemView::item:hover {{
                background-color: {t["selection_item_hover"]};
            }}

            /* ===== SPINBOX ===== */
            QSpinBox {{
                background-color: {t["bg_input"]};
                border: 2px solid {t["border_normal"]};
                border-radius: 6px;
                padding: 8px 12px;
                color: {t["text_primary"]};
                font-size: 10pt;
            }}

            QSpinBox:focus {{
                border-color: {t["border_focus"]};
            }}

            QSpinBox:hover:!focus {{
                border-color: {t["border_hover"]};
            }}

            QSpinBox:disabled {{
                background-color: {t["bg_disabled"]};
                color: {t["text_disabled"]};
            }}

            QSpinBox::up-button, QSpinBox::down-button {{
                background-color: {t["bg_spinbox_button"]};
                border: none;
                border-radius: 3px;
                width: 20px;
            }}

            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: {t["bg_spinbox_button_hover"]};
            }}

            QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {{
                background-color: {t["bg_spinbox_button_pressed"]};
            }}

            QSpinBox::up-arrow {{
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 5px solid {t["arrow_spin"]};
            }}

            QSpinBox::down-arrow {{
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {t["arrow_spin"]};
            }}

            /* ===== LABELS ===== */
            QLabel {{
                color: {t["text_secondary"]};
                background-color: transparent;
            }}

            /* ===== CHECKBOXES ===== */
            QCheckBox {{
                color: {t["text_secondary"]};
                spacing: 8px;
                background-color: transparent;
            }}

            QCheckBox:disabled {{
                color: {t["text_disabled"]};
            }}

            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {t["checkbox_border"]};
                border-radius: 4px;
                background-color: {t["checkbox_bg"]};
            }}

            QCheckBox::indicator:hover {{
                border-color: {t["border_focus"]};
            }}

            QCheckBox::indicator:checked {{
                background-color: {t["checkbox_checked"]};
                border-color: {t["checkbox_checked"]};
            }}

            QCheckBox::indicator:checked:hover {{
                background-color: {t["checkbox_checked_hover"]};
                border-color: {t["checkbox_checked_hover"]};
            }}

            QCheckBox::indicator:disabled {{
                background-color: {t["checkbox_disabled_bg"]};
                border-color: {t["checkbox_disabled_border"]};
            }}

            /* ===== LIST WIDGETS ===== */
            QListWidget {{
                background-color: {t["bg_input"]};
                border: 2px solid {t["border_normal"]};
                border-radius: 6px;
                color: {t["text_primary"]};
                padding: 4px;
                outline: none;
            }}

            QListWidget:focus {{
                border-color: {t["border_focus"]};
            }}

            QListWidget::item {{
                padding: 10px 12px;
                border-radius: 4px;
                color: {t["text_primary"]};
                background-color: {t["bg_list_item"]};
            }}

            QListWidget::item:alternate {{
                background-color: {t["bg_list_alternate"]};
            }}

            QListWidget::item:selected {{
                background-color: {t["list_selected_bg"]};
                color: #FFFFFF;
            }}

            QListWidget::item:hover:!selected {{
                background-color: {t["list_hover_bg"]};
            }}

            /* ===== BUTTONS ===== */
            /* Keep only scoped button overrides here; general sizing comes
               from the application stylesheet (src/ui/style.qss). */

            QPushButton[objectName="dangerButton"] {{
                background-color: {t["danger_bg"]};
            }}

            QPushButton[objectName="dangerButton"]:hover {{
                background-color: {t["danger_hover"]};
            }}

            QPushButton[objectName="dangerButton"]:pressed {{
                background-color: {t["danger_pressed"]};
            }}

            QPushButton[objectName="secondaryButton"] {{
                background-color: {t["secondary_bg"]};
                color: {t["secondary_color"]};
                border: 1px solid {t["secondary_border"]};
            }}

            QPushButton[objectName="secondaryButton"]:hover {{
                background-color: {t["secondary_hover_bg"]};
                border-color: {t["secondary_hover_border"]};
            }}

            /* ===== SCROLL BARS ===== */
            QScrollBar:vertical {{
                background-color: {t["bg_scroll"]};
                width: 12px;
                border-radius: 6px;
                margin: 0;
            }}

            QScrollBar::handle:vertical {{
                background-color: {t["bg_scroll_handle"]};
                border-radius: 6px;
                min-height: 30px;
                margin: 2px;
            }}

            QScrollBar::handle:vertical:hover {{
                background-color: {t["bg_scroll_handle_hover"]};
            }}

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
                background: none;
            }}

            QScrollBar:horizontal {{
                background-color: {t["bg_scroll"]};
                height: 12px;
                border-radius: 6px;
                margin: 0;
            }}

            QScrollBar::handle:horizontal {{
                background-color: {t["bg_scroll_handle"]};
                border-radius: 6px;
                min-width: 30px;
                margin: 2px;
            }}

            QScrollBar::handle:horizontal:hover {{
                background-color: {t["bg_scroll_handle_hover"]};
            }}

            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0;
                background: none;
            }}

            QToolTip {{
                background-color: {t["tooltip_bg"]};
                color: {t["tooltip_color"]};
                border: 1px solid {t["tooltip_border"]};
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 9pt;
            }}

            QProgressBar {{
                background-color: {t["bg_progress"]};
                border: none;
                border-radius: 4px;
                height: 8px;
                text-align: center;
                color: {t["text_primary"]};
            }}

            QProgressBar::chunk {{
                background-color: {t["progress_chunk"]};
                border-radius: 4px;
            }}
        """
