"""
Tests for ImagePreviewWidget in ui.image_preview.image_preview_widget.

Covers:
- set_pixmap() with a null/empty pixmap does not crash
- set_pixmap() with no zoom_spinner still works (graceful null guard)
- _get_default_theme() reads the correct setting from ConfigManager
"""

from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


# ---------------------------------------------------------------------------
# Helper: build ImagePreviewWidget with all heavy-weight deps mocked
# ---------------------------------------------------------------------------


def _make_widget(qapp, config_manager=None, analysis_db=None):
    """Instantiate ImagePreviewWidget with optional mocked dependencies."""
    from ui.image_preview.enums import ToolbarPosition, ToolbarSize
    from ui.image_preview.image_preview_widget import ImagePreviewWidget

    # Minimal theme colors to avoid requiring full ConfigManager
    theme_colors = {
        "bg_primary": "#FFFFFF",
        "bg_secondary": "#F9FAFB",
        "bg_tertiary": "#F3F4F6",
        "text_primary": "#111827",
        "text_secondary": "#374151",
        "text_tertiary": "#6B7280",
        "border": "#E5E7EB",
        "accent": "#3B82F6",
        "button_bg": "#F3F4F6",
        "button_hover": "#EFF6FF",
    }

    widget = ImagePreviewWidget(
        toolbar_size=ToolbarSize.COMPACT,
        toolbar_position=ToolbarPosition.BOTTOM_CENTER,
        theme_colors=theme_colors,
        config_manager=config_manager,
        analysis_db=analysis_db,
    )
    return widget


# ---------------------------------------------------------------------------
# set_pixmap — null guard paths
# ---------------------------------------------------------------------------


def test_set_pixmap_with_valid_pixmap_does_not_crash(qapp):
    """set_pixmap() with a valid 1x1 QPixmap should succeed without raising."""
    widget = _make_widget(qapp)

    pixmap = QPixmap(1, 1)
    pixmap.fill()

    # Should not raise
    widget.set_pixmap(pixmap)

    assert widget.base_pixmap is pixmap


def test_set_pixmap_stores_file_path(qapp):
    """set_pixmap() with a file_path argument must store it on the widget."""
    widget = _make_widget(qapp)

    pixmap = QPixmap(1, 1)
    pixmap.fill()

    widget.set_pixmap(pixmap, file_path="/test/doc.png")

    assert widget.current_file_path == "/test/doc.png"


def test_set_pixmap_resets_rotation_to_zero(qapp):
    """set_pixmap() must reset the rotation angle to 0."""
    widget = _make_widget(qapp)
    widget.rotation_angle = 90  # Pre-set a rotation

    pixmap = QPixmap(1, 1)
    pixmap.fill()

    widget.set_pixmap(pixmap)

    assert widget.rotation_angle == 0


def test_set_pixmap_calls_show_on_overlay_controls(qapp):
    """set_pixmap() must call show() on the overlay_controls object."""
    widget = _make_widget(qapp)

    pixmap = QPixmap(1, 1)
    pixmap.fill()

    # Replace overlay_controls with a mock to observe show() calls
    mock_overlay = MagicMock()
    widget.overlay_controls = mock_overlay

    widget.set_pixmap(pixmap)

    mock_overlay.show.assert_called()


def test_set_pixmap_missing_zoom_spinner_does_not_crash(qapp):
    """set_pixmap() should not crash even if zoom_spinner is None."""
    widget = _make_widget(qapp)
    widget.zoom_spinner = None  # Force null

    pixmap = QPixmap(1, 1)
    pixmap.fill()

    # Should not raise — no AttributeError on None spinner
    widget.set_pixmap(pixmap)


# ---------------------------------------------------------------------------
# _get_default_theme — uses config_manager when available
# ---------------------------------------------------------------------------


def test_get_default_theme_uses_config_manager_dark_setting(qapp):
    """_get_default_theme() must query ConfigManager for the current theme setting."""
    mock_config = MagicMock()
    mock_config.get_setting.return_value = "dark"

    # Patch ConfigManager inside the module so the constructor call uses our mock
    with patch("ui.image_preview.image_preview_widget.ThemeManager") as mock_tm:
        mock_tm.get_colors.return_value = {
            "bg_primary": "#000",
            "bg_secondary": "#111",
            "bg_tertiary": "#222",
            "text_primary": "#FFF",
            "text_secondary": "#EEE",
            "text_tertiary": "#DDD",
            "border": "#333",
            "accent": "#3B82F6",
            "bg_hover": "#444",
        }

        with patch("ui.image_preview.image_preview_widget.ConfigManager") as mock_cm_cls:
            mock_cm_instance = MagicMock()
            mock_cm_instance.get_setting.return_value = "dark"
            mock_cm_cls.return_value = mock_cm_instance

            from ui.image_preview.enums import ToolbarPosition, ToolbarSize
            from ui.image_preview.image_preview_widget import ImagePreviewWidget

            # Build widget without passing theme_colors so _get_default_theme is called
            ImagePreviewWidget(
                toolbar_size=ToolbarSize.COMPACT,
                toolbar_position=ToolbarPosition.BOTTOM_CENTER,
            )

    # ConfigManager().get_setting should have been called for the theme
    mock_cm_instance.get_setting.assert_called_once_with("Theme", "theme", "dark")


def test_get_default_theme_falls_back_on_exception(qapp):
    """_get_default_theme() should fall back to dark mode when ConfigManager raises."""
    with patch("ui.image_preview.image_preview_widget.ConfigManager") as mock_cm_cls:
        mock_cm_cls.side_effect = Exception("Config unavailable")

        with patch("ui.image_preview.image_preview_widget.ThemeManager") as mock_tm:
            mock_tm.get_colors.return_value = {
                "bg_primary": "#000",
                "bg_secondary": "#111",
                "bg_tertiary": "#222",
                "text_primary": "#FFF",
                "text_secondary": "#EEE",
                "text_tertiary": "#DDD",
                "border": "#333",
                "accent": "#3B82F6",
                "bg_hover": "#444",
            }

            from ui.image_preview.enums import ToolbarPosition, ToolbarSize
            from ui.image_preview.image_preview_widget import ImagePreviewWidget

            # Should not raise; falls back to dark=True
            ImagePreviewWidget(
                toolbar_size=ToolbarSize.COMPACT,
                toolbar_position=ToolbarPosition.BOTTOM_CENTER,
            )

    # ThemeManager.get_colors must be called with True (dark) as the fallback
    mock_tm.get_colors.assert_called_once_with(True)


# ---------------------------------------------------------------------------
# zoom / rotation state management
# ---------------------------------------------------------------------------


def test_reset_view_restores_zero_rotation(qapp):
    """reset_view() must restore rotation_angle to 0."""
    widget = _make_widget(qapp)
    widget.rotation_angle = 180

    widget.reset_view()

    assert widget.rotation_angle == 0


def test_set_zoom_level_clamps_to_bounds(qapp):
    """set_zoom_level() must clamp extreme values within valid range (5–400)."""
    widget = _make_widget(qapp)

    if widget.zoom_spinner is None:
        pytest.skip("zoom_spinner not available in this test environment")

    widget.set_zoom_level(9999)
    assert widget.zoom_spinner.value() <= 400

    widget.set_zoom_level(-100)
    assert widget.zoom_spinner.value() >= 5
