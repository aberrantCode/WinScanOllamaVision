"""
UI Styles and Themes
Color constants and component-level overrides for WinScanLLM.

Design system: ThemeManager (theme_manager.py) is the single source of truth
for application-wide theming. This module provides:
  - Colors: semantic color constants (accent, success, danger — same in both themes)
  - get_*_button_style(): accent-colored button overrides (primary, success, danger, secondary)
  - get_*_bar_style(): progress bar overrides
  - show_*(): themed message box helpers
"""

import time

from ui.theme.theme_manager import ThemeManager

# ===== COLOR CONSTANTS =====


class Colors:
    """Semantic color constants. Accent/status colors are theme-invariant."""

    # Accent (same in light and dark — matches ThemeManager)
    PRIMARY = "#3B82F6"
    PRIMARY_HOVER = "#2563EB"
    PRIMARY_LIGHT = "#60A5FA"
    PRIMARY_PALE = "#DBEAFE"

    # Status (same in light and dark — matches ThemeManager)
    SUCCESS = "#10B981"
    SUCCESS_HOVER = "#059669"
    SUCCESS_LIGHT = "#34D399"
    SUCCESS_PALE = "#D1FAE5"

    DANGER = "#EF4444"
    DANGER_HOVER = "#DC2626"
    DANGER_LIGHT = "#F87171"
    DANGER_PALE = "#FEE2E2"

    WARNING = "#F59E0B"
    WARNING_HOVER = "#D97706"
    WARNING_LIGHT = "#FCD34D"
    WARNING_PALE = "#FEF3C7"

    # Legacy neutral constants — prefer ThemeManager.get_colors() for theme-aware values
    WHITE = "#FFFFFF"
    BLACK = "#000000"
    GRAY_900 = "#111827"
    GRAY_800 = "#1F2937"
    GRAY_700 = "#374151"
    GRAY_600 = "#4B5563"
    GRAY_500 = "#6B7280"
    GRAY_400 = "#9CA3AF"
    GRAY_300 = "#D1D5DB"
    GRAY_200 = "#E5E7EB"
    GRAY_100 = "#F3F4F6"
    GRAY_50 = "#F9FAFB"


# ===== INTERNAL HELPERS =====

_dark_mode_cache: tuple[bool, float] | None = None


def _is_dark(config_manager=None) -> bool:
    """Read current theme setting. Matches main.py startup logic.

    Uses a 1-second TTL cache to avoid repeatedly instantiating ConfigManager
    for module-level / high-frequency callers. Pass an existing config_manager
    to bypass the cache entirely (uses the supplied instance directly).
    """
    global _dark_mode_cache
    if config_manager is None:
        now = time.time()
        if _dark_mode_cache is not None and now - _dark_mode_cache[1] < 1.0:
            return _dark_mode_cache[0]
    try:
        from config.config_manager import ConfigManager

        cm = config_manager or ConfigManager()
        theme: str = str(cm.get_setting("Theme", "theme", "dark"))
        result = theme == "dark"
    except Exception:
        result = True  # Default to dark mode
    if config_manager is None:
        _dark_mode_cache = (result, time.time())
    return result


def _get_message_box_stylesheet() -> str:
    """Stylesheet for message boxes using ThemeManager colors."""
    is_dark = _is_dark()
    c = ThemeManager.get_colors(is_dark)

    return f"""
        QMessageBox {{
            background-color: {c["bg_primary"]};
        }}
        QMessageBox QLabel {{
            color: {c["text_primary"]};
            background-color: transparent;
        }}
        QMessageBox QPushButton {{
            background-color: {c["bg_tertiary"]};
            color: {c["text_primary"]};
            border: 1px solid {c["border"]};
            border-radius: 4px;
            padding: 6px 14px;
            min-width: 70px;
        }}
        QMessageBox QPushButton:hover {{
            background-color: {c["bg_hover"]};
            border-color: {c["border_light"]};
        }}
        QMessageBox QPushButton:pressed {{
            background-color: {c["border"]};
        }}
        QMessageBox QPushButton:default {{
            background-color: {c["accent"]};
            color: white;
            border-color: {c["accent"]};
            font-weight: 600;
        }}
        QMessageBox QPushButton:default:hover {{
            background-color: {c["accent_hover"]};
        }}
    """


# ===== BUTTON STYLES =====
# These provide accent-colored variants beyond ThemeManager's neutral default.
# Primary, success, danger use the same colors in both themes.
# Secondary adapts neutral colors to the active theme.


def get_primary_button_style() -> str:
    """Blue accent button — same appearance in both themes."""
    return f"""
        QPushButton {{
            background-color: {Colors.PRIMARY};
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 11pt;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {Colors.PRIMARY_HOVER};
        }}
        QPushButton:pressed {{
            background-color: {Colors.PRIMARY_HOVER};
        }}
        QPushButton:disabled {{
            background-color: {Colors.GRAY_300};
            color: {Colors.GRAY_500};
        }}
    """


def get_success_button_style() -> str:
    """Green accent button — same appearance in both themes."""
    return f"""
        QPushButton {{
            background-color: {Colors.SUCCESS};
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 11pt;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {Colors.SUCCESS_HOVER};
        }}
        QPushButton:pressed {{
            background-color: {Colors.SUCCESS_HOVER};
        }}
        QPushButton:disabled {{
            background-color: {Colors.GRAY_300};
            color: {Colors.GRAY_500};
        }}
    """


def get_danger_button_style() -> str:
    """Red accent button — same appearance in both themes."""
    return f"""
        QPushButton {{
            background-color: {Colors.DANGER};
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 11pt;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {Colors.DANGER_HOVER};
        }}
        QPushButton:pressed {{
            background-color: {Colors.DANGER_HOVER};
        }}
        QPushButton:disabled {{
            background-color: {Colors.GRAY_300};
            color: {Colors.GRAY_500};
        }}
    """


def get_secondary_button_style() -> str:
    """Outlined neutral button — adapts to active theme."""
    c = ThemeManager.get_colors(_is_dark())
    return f"""
        QPushButton {{
            background-color: {c["bg_primary"]};
            color: {c["text_primary"]};
            border: 1px solid {c["border"]};
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 11pt;
            font-weight: 600;
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
    """


def get_button_style(color: str = "primary") -> str:
    """
    Unified button style for common variants.

    Args:
        color: 'primary' (blue), 'success' (green), 'danger' (red), 'secondary' (neutral)
    """
    if color == "primary":
        return get_primary_button_style()
    if color == "success":
        return get_success_button_style()
    if color == "danger":
        return get_danger_button_style()
    return get_secondary_button_style()


# ===== PROGRESS BAR STYLES =====


def get_progress_bar_style(percentage: float) -> str:
    """
    Progress bar with color-coded chunk. Background adapts to active theme.

    Chunk color: green ≥80%, yellow 60-80%, red <60%.
    """
    if percentage >= 80:
        chunk_color = Colors.SUCCESS
    elif percentage >= 60:
        chunk_color = Colors.WARNING
    else:
        chunk_color = Colors.DANGER

    c = ThemeManager.get_colors(_is_dark())
    return f"""
        QProgressBar {{
            background-color: {c["bg_tertiary"]};
            border: 1px solid {c["border"]};
            border-radius: 10px;
            height: 20px;
            text-align: center;
            color: {c["text_primary"]};
            font-weight: 600;
            font-size: 10pt;
        }}
        QProgressBar::chunk {{
            background-color: {chunk_color};
            border-radius: 9px;
        }}
    """


def get_distribution_bar_style() -> str:
    """Compact progress bar for distribution visualizations. Adapts to active theme."""
    c = ThemeManager.get_colors(_is_dark())
    return f"""
        QProgressBar {{
            background-color: {c["bg_tertiary"]};
            border: none;
            border-radius: 6px;
            height: 12px;
            text-align: center;
        }}
        QProgressBar::chunk {{
            background-color: {Colors.PRIMARY};
            border-radius: 6px;
        }}
    """


# ===== MESSAGE BOX HELPERS =====


def show_message(
    parent,
    title: str,
    text: str,
    icon=None,
    buttons=None,
    default_button=None,
    detailed_text: str | None = None,
):
    """
    Show a themed message box.

    Args:
        parent: Parent widget
        title: Window title
        text: Main message text
        icon: QMessageBox.Icon (Information, Warning, Critical, Question, NoIcon)
        buttons: Button combination (default: Ok)
        default_button: Which button should be default
        detailed_text: Optional expandable text

    Returns:
        QMessageBox.StandardButton for which button was clicked
    """
    from PyQt6.QtWidgets import QMessageBox

    msg_box = QMessageBox(parent)

    if icon is not None:
        msg_box.setIcon(icon)

    msg_box.setWindowTitle(title)
    msg_box.setText(text)

    if detailed_text:
        msg_box.setDetailedText(detailed_text)

    if buttons is not None:
        msg_box.setStandardButtons(buttons)
    else:
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)

    if default_button is not None:
        msg_box.setDefaultButton(default_button)

    msg_box.setStyleSheet(_get_message_box_stylesheet())

    return msg_box.exec()


def show_information(parent, title: str, text: str, detailed_text: str | None = None):
    """Show themed information message box (Ok button)."""
    from PyQt6.QtWidgets import QMessageBox

    show_message(
        parent, title, text, icon=QMessageBox.Icon.Information, detailed_text=detailed_text
    )


def show_warning(parent, title: str, text: str, detailed_text: str | None = None):
    """Show themed warning message box (Ok button)."""
    from PyQt6.QtWidgets import QMessageBox

    show_message(parent, title, text, icon=QMessageBox.Icon.Warning, detailed_text=detailed_text)


def show_critical(parent, title: str, text: str, detailed_text: str | None = None):
    """Show themed critical/error message box (Ok button)."""
    from PyQt6.QtWidgets import QMessageBox

    show_message(parent, title, text, icon=QMessageBox.Icon.Critical, detailed_text=detailed_text)


def show_question(parent, title: str, text: str, buttons=None, default_button=None):
    """
    Show themed question message box with customizable buttons.

    Returns:
        QMessageBox.StandardButton for which button was clicked
    """
    from PyQt6.QtWidgets import QMessageBox

    if buttons is None:
        buttons = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No

    if default_button is None:
        default_button = QMessageBox.StandardButton.No

    return show_message(
        parent,
        title,
        text,
        icon=QMessageBox.Icon.Question,
        buttons=buttons,
        default_button=default_button,
    )


def show_confirm(
    parent,
    title: str,
    text: str,
    confirm_text: str = "Yes",
    cancel_text: str = "No",
    default_cancel: bool = True,
) -> bool:
    """
    Show a simple confirmation dialog with custom button labels.

    Returns:
        True if user confirmed, False if cancelled
    """
    from PyQt6.QtWidgets import QMessageBox

    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Icon.Question)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setStyleSheet(_get_message_box_stylesheet())

    btn_yes = msg_box.addButton(confirm_text, QMessageBox.ButtonRole.YesRole)
    btn_no = msg_box.addButton(cancel_text, QMessageBox.ButtonRole.NoRole)

    if default_cancel:
        msg_box.setDefaultButton(btn_no)
    else:
        msg_box.setDefaultButton(btn_yes)

    msg_box.exec()
    return bool(msg_box.clickedButton() == btn_yes)
