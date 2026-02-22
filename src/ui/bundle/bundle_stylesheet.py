"""Build the shared QSS stylesheet for bundle UI components.

The single public function ``build_bundle_stylesheet(dark_mode)`` merges what
was previously the separate ``_apply_dark_theme`` / ``_apply_light_theme``
methods in GuidedBundleWorkflow into one parameterised function.
"""

from ui.bundle.bundle_colors import get_bundle_colors


def build_bundle_stylesheet(dark_mode: bool) -> str:
    """Return the complete QSS stylesheet string for the bundle UI.

    Args:
        dark_mode: When ``True`` the dark palette is used; otherwise light.

    Returns:
        A QSS string suitable for ``QWidget.setStyleSheet()``.
    """
    theme = get_bundle_colors(dark_mode)

    # These two values differ between dark and light themes:
    #   dark  → pressed / disabled backgrounds use bg_secondary (#0f172a)
    #   light → pressed / disabled backgrounds use bg_tertiary  (#f3f4f6)
    pressed_bg = theme["bg_secondary"] if dark_mode else theme["bg_tertiary"]

    return f"""
        QDialog {{
            background-color: {theme["bg_primary"]};
            color: {theme["text_primary"]};
        }}
        QWidget {{
            background-color: {theme["bg_primary"]};
            color: {theme["text_primary"]};
        }}
        QLabel {{
            color: {theme["text_primary"]};
            background-color: transparent;
            border: none;
        }}
        QLineEdit {{
            background-color: {theme["bg_input"]};
            color: {theme["text_primary"]};
            border: 1px solid {theme["border"]};
            border-radius: 4px;
            padding: 6px 8px;
        }}
        QLineEdit:focus {{
            border-color: {theme["border_focus"]};
        }}
        QLineEdit:disabled {{
            background-color: {pressed_bg};
            color: {theme["text_disabled"]};
        }}
        QComboBox {{
            background-color: {theme["bg_input"]};
            color: {theme["text_primary"]};
            border: 1px solid {theme["border"]};
            border-radius: 4px;
            padding: 6px 8px;
        }}
        QComboBox:focus {{
            border-color: {theme["border_focus"]};
        }}
        QComboBox::drop-down {{
            border: none;
            padding-right: 8px;
            background: {theme["bg_input"]};
        }}
        QComboBox::down-arrow {{
            width: 0;
            height: 0;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid {theme["text_primary"]};
        }}
        QComboBox QAbstractItemView {{
            background-color: {theme["bg_tertiary"]};
            color: {theme["text_primary"]};
            selection-background-color: {theme["selected"]};
            selection-color: white;
            border: 1px solid {theme["border"]};
            outline: none;
        }}
        QComboBox QAbstractItemView::item {{
            padding: 6px 8px;
            background-color: {theme["bg_tertiary"]};
            color: {theme["text_primary"]};
        }}
        QComboBox QAbstractItemView::item:hover {{
            background-color: {theme["bg_hover"]};
            color: {theme["text_primary"]};
        }}
        QComboBox QAbstractItemView::item:selected {{
            background-color: {theme["selected"]};
            color: white;
        }}
        QCheckBox {{
            color: {theme["text_primary"]};
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {theme["border"]};
            border-radius: 3px;
            background-color: {theme["bg_input"]};
        }}
        QCheckBox::indicator:checked {{
            background-color: {theme["selected"]};
            border-color: {theme["selected"]};
        }}
        QPushButton {{
            background-color: {theme["button_bg"]};
            color: {theme["button_text"]};
            border: 1px solid {theme["border"]};
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {theme["bg_hover"]};
            border-color: {theme["border_focus"]};
        }}
        QPushButton:pressed {{
            background-color: {pressed_bg};
        }}
        QPushButton:disabled {{
            background-color: {pressed_bg};
            color: {theme["text_disabled"]};
            border-color: {theme["border_light"]};
        }}
        QScrollBar:vertical {{
            background-color: {theme["bg_secondary"]};
            width: 12px;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background-color: {theme["border"]};
            border-radius: 6px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {theme["text_tertiary"]};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background-color: {theme["bg_secondary"]};
            height: 12px;
            border: none;
        }}
        QScrollBar::handle:horizontal {{
            background-color: {theme["border"]};
            border-radius: 6px;
            min-width: 20px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background-color: {theme["text_tertiary"]};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            border: none;
            background: none;
            width: 0px;
        }}
        QScrollArea {{
            background-color: {theme["bg_primary"]};
            border: none;
        }}
        QFrame {{
            background-color: transparent;
            border: none;
        }}
        QToolTip {{
            background-color: {theme["bg_tertiary"]};
            color: {theme["text_primary"]};
            border: 1px solid {theme["border"]};
            padding: 6px 8px;
            font-size: 11px;
            font-weight: 600;
        }}
        QSpinBox {{
            background-color: {theme["bg_input"]};
            color: {theme["text_primary"]};
            border: 1px solid {theme["border"]};
            border-radius: 4px;
            padding: 4px 8px;
        }}
        QSpinBox:focus {{
            border-color: {theme["border_focus"]};
        }}
    """
