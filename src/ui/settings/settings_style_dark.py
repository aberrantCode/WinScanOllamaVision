"""Dark theme stylesheet for the Settings window."""

from ui.settings.settings_style_base import get_settings_stylesheet


def get_dark_theme_stylesheet() -> str:
    """Return the complete dark theme stylesheet."""
    return get_settings_stylesheet(is_dark=True)
