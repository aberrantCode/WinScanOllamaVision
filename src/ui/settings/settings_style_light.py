"""Light theme stylesheet for the Settings window."""

from ui.settings.settings_style_base import get_settings_stylesheet


def get_light_theme_stylesheet() -> str:
    """Return the complete light theme stylesheet."""
    return get_settings_stylesheet(is_dark=False)
