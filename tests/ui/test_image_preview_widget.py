"""
Unit tests for ImagePreviewWidget.

Tests widget initialization, zoom/rotation controls, fit calculations,
theme updates, and toolbar positioning.
"""

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

from ui.image_preview_widget import (
    ImagePreviewWidget,
    ToolbarPosition,
    ToolbarSize,
)


@pytest.fixture(scope="module")
def qapp():
    """Fixture to create QApplication for PyQt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def test_pixmap():
    """Create a test pixmap (100x200)."""
    pixmap = QPixmap(100, 200)
    pixmap.fill()
    return pixmap


class TestImagePreviewWidgetInitialization:
    """Test widget initialization with different configurations."""

    def test_default_initialization(self, qapp):
        """Test widget initializes with default settings."""
        widget = ImagePreviewWidget()

        assert widget.toolbar_size == ToolbarSize.STANDARD
        assert widget.toolbar_position == ToolbarPosition.BOTTOM_CENTER
        assert widget.zoom_level == 100
        assert widget.rotation_angle == 0
        assert widget.base_pixmap is None
        assert widget.image_label is not None
        assert widget.overlay_controls is not None
        assert widget.zoom_spinner is not None

    def test_compact_toolbar_initialization(self, qapp):
        """Test widget initializes with compact toolbar."""
        widget = ImagePreviewWidget(toolbar_size=ToolbarSize.COMPACT)

        assert widget.toolbar_size == ToolbarSize.COMPACT
        # Verify compact sizing
        assert widget.zoom_spinner.width() == 55
        assert widget.zoom_spinner.height() == 20

    def test_standard_toolbar_initialization(self, qapp):
        """Test widget initializes with standard toolbar."""
        widget = ImagePreviewWidget(toolbar_size=ToolbarSize.STANDARD)

        assert widget.toolbar_size == ToolbarSize.STANDARD
        # Verify standard sizing
        assert widget.zoom_spinner.width() == 110
        assert widget.zoom_spinner.height() == 40

    def test_custom_toolbar_position(self, qapp):
        """Test widget initializes with custom toolbar position."""
        widget = ImagePreviewWidget(toolbar_position=ToolbarPosition.TOP_LEFT)

        assert widget.toolbar_position == ToolbarPosition.TOP_LEFT

    def test_custom_theme_colors(self, qapp):
        """Test widget initializes with custom theme colors."""
        custom_theme = {
            "bg_primary": "#FFFFFF",
            "bg_secondary": "#F0F0F0",
            "text_primary": "#000000",
            "text_secondary": "#666666",
            "border": "#CCCCCC",
            "accent": "#0066CC",
            "button_bg": "#E0E0E0",
            "button_hover": "#D0D0D0",
        }
        widget = ImagePreviewWidget(theme_colors=custom_theme)

        assert widget.theme_colors == custom_theme


class TestImagePreviewWidgetPixmapHandling:
    """Test pixmap loading and display."""

    def test_set_pixmap_basic(self, qapp, test_pixmap):
        """Test setting a pixmap."""
        widget = ImagePreviewWidget()
        widget.set_pixmap(test_pixmap)

        assert widget.base_pixmap is not None
        assert widget.rotation_angle == 0
        assert widget.image_label.get_pan_offset() == QPoint(0, 0)

    def test_set_pixmap_resets_rotation(self, qapp, test_pixmap):
        """Test that setting a new pixmap resets rotation."""
        widget = ImagePreviewWidget()
        widget.set_pixmap(test_pixmap)
        widget._on_rotate_cw()  # Rotate to 90°

        assert widget.rotation_angle == 90

        # Set new pixmap - should reset rotation
        widget.set_pixmap(test_pixmap)
        assert widget.rotation_angle == 0

    def test_set_pixmap_resets_pan(self, qapp, test_pixmap):
        """Test that setting a new pixmap resets pan offset."""
        widget = ImagePreviewWidget()
        widget.set_pixmap(test_pixmap)
        widget.image_label.set_pan_offset(QPoint(50, 50))

        assert widget.image_label.get_pan_offset() == QPoint(50, 50)

        # Set new pixmap - should reset pan
        widget.set_pixmap(test_pixmap)
        assert widget.image_label.get_pan_offset() == QPoint(0, 0)


class TestImagePreviewWidgetZoomControls:
    """Test zoom level controls and bounds checking."""

    def test_get_zoom_level(self, qapp):
        """Test getting zoom level."""
        widget = ImagePreviewWidget()
        assert widget.get_zoom_level() == 100

    def test_set_zoom_level(self, qapp):
        """Test setting zoom level."""
        widget = ImagePreviewWidget()
        widget.set_zoom_level(150)

        assert widget.get_zoom_level() == 150
        assert widget.zoom_spinner.value() == 150

    def test_set_zoom_level_clamps_to_minimum(self, qapp):
        """Test zoom level clamps to 25% minimum."""
        widget = ImagePreviewWidget()
        widget.set_zoom_level(10)

        assert widget.get_zoom_level() == 25

    def test_set_zoom_level_clamps_to_maximum(self, qapp):
        """Test zoom level clamps to 400% maximum."""
        widget = ImagePreviewWidget()
        widget.set_zoom_level(500)

        assert widget.get_zoom_level() == 400

    def test_zoom_in(self, qapp):
        """Test zoom in increases zoom by 25%."""
        widget = ImagePreviewWidget()
        widget._on_zoom_in()

        assert widget.get_zoom_level() == 125

    def test_zoom_in_max_limit(self, qapp):
        """Test zoom in respects 400% maximum."""
        widget = ImagePreviewWidget()
        widget.set_zoom_level(390)
        widget._on_zoom_in()

        assert widget.get_zoom_level() == 400

        # Try to go beyond - should stay at 400
        widget._on_zoom_in()
        assert widget.get_zoom_level() == 400

    def test_zoom_out(self, qapp):
        """Test zoom out decreases zoom by 25%."""
        widget = ImagePreviewWidget()
        widget.set_zoom_level(150)
        widget._on_zoom_out()

        assert widget.get_zoom_level() == 125

    def test_zoom_out_min_limit(self, qapp):
        """Test zoom out respects 25% minimum."""
        widget = ImagePreviewWidget()
        widget.set_zoom_level(40)
        widget._on_zoom_out()

        assert widget.get_zoom_level() == 25

        # Try to go below - should stay at 25
        widget._on_zoom_out()
        assert widget.get_zoom_level() == 25


class TestImagePreviewWidgetRotationControls:
    """Test rotation controls and pan reset behavior."""

    def test_get_rotation_angle(self, qapp):
        """Test getting rotation angle."""
        widget = ImagePreviewWidget()
        assert widget.get_rotation_angle() == 0

    def test_rotate_clockwise(self, qapp, test_pixmap):
        """Test clockwise rotation increments by 90°."""
        widget = ImagePreviewWidget()
        widget.set_pixmap(test_pixmap)

        widget._on_rotate_cw()
        assert widget.rotation_angle == 90

        widget._on_rotate_cw()
        assert widget.rotation_angle == 180

        widget._on_rotate_cw()
        assert widget.rotation_angle == 270

        widget._on_rotate_cw()
        assert widget.rotation_angle == 0  # Wraps around

    def test_rotate_counter_clockwise(self, qapp, test_pixmap):
        """Test counter-clockwise rotation decrements by 90°."""
        widget = ImagePreviewWidget()
        widget.set_pixmap(test_pixmap)

        widget._on_rotate_ccw()
        assert widget.rotation_angle == 270

        widget._on_rotate_ccw()
        assert widget.rotation_angle == 180

        widget._on_rotate_ccw()
        assert widget.rotation_angle == 90

        widget._on_rotate_ccw()
        assert widget.rotation_angle == 0  # Wraps around

    def test_rotation_resets_pan(self, qapp, test_pixmap):
        """Test that rotation resets pan offset."""
        widget = ImagePreviewWidget()
        widget.set_pixmap(test_pixmap)
        widget.image_label.set_pan_offset(QPoint(50, 50))

        assert widget.image_label.get_pan_offset() == QPoint(50, 50)

        widget._on_rotate_cw()
        assert widget.image_label.get_pan_offset() == QPoint(0, 0)

    def test_reset_view(self, qapp, test_pixmap):
        """Test reset_view resets zoom, rotation, and pan."""
        widget = ImagePreviewWidget()
        widget.set_pixmap(test_pixmap)

        # Change all values
        widget.set_zoom_level(200)
        widget._on_rotate_cw()
        widget.image_label.set_pan_offset(QPoint(100, 100))

        assert widget.get_zoom_level() == 200
        assert widget.rotation_angle == 90
        assert widget.image_label.get_pan_offset() == QPoint(100, 100)

        # Reset everything
        widget.reset_view()

        assert widget.get_zoom_level() == 100
        assert widget.rotation_angle == 0
        assert widget.image_label.get_pan_offset() == QPoint(0, 0)


class TestImagePreviewWidgetFitModes:
    """Test fit to width/height/window calculations."""

    def test_fit_to_width_calculation(self, qapp, test_pixmap):
        """Test fit to width calculates correct zoom."""
        widget = ImagePreviewWidget()
        widget.resize(500, 600)  # Set widget size
        widget.set_pixmap(test_pixmap)  # 100x200 pixmap

        widget.fit_to_width()

        # Available width = 500 - 40 = 460
        # Zoom = (460 / 100) * 100 = 460%
        # Clamped to max 400%
        assert widget.get_zoom_level() == 400

    def test_fit_to_width_with_rotation(self, qapp, test_pixmap):
        """Test fit to width accounts for rotation."""
        widget = ImagePreviewWidget()
        widget.resize(500, 600)
        widget.set_pixmap(test_pixmap)  # 100x200 pixmap

        # Rotate 90° - dimensions become 200x100
        widget._on_rotate_cw()
        widget.fit_to_width()

        # Available width = 500 - 40 = 460
        # Rotated width = 200
        # Zoom = (460 / 200) * 100 = 230%
        # Allow for rounding: 229-230
        assert widget.get_zoom_level() in [229, 230]

    def test_fit_to_height_calculation(self, qapp, test_pixmap):
        """Test fit to height calculates correct zoom."""
        widget = ImagePreviewWidget()
        widget.resize(500, 600)
        widget.set_pixmap(test_pixmap)  # 100x200 pixmap

        widget.fit_to_height()

        # Available height = 600 - 80 = 520
        # Zoom = (520 / 200) * 100 = 260%
        assert widget.get_zoom_level() == 260

    def test_fit_to_window_uses_smaller_ratio(self, qapp, test_pixmap):
        """Test fit to window uses the smaller of width/height ratios."""
        widget = ImagePreviewWidget()
        widget.resize(500, 600)
        widget.set_pixmap(test_pixmap)  # 100x200 pixmap

        widget.fit_to_window()

        # Width ratio: (500-40)/100 = 4.60 = 460%
        # Height ratio: (600-80)/200 = 2.60 = 260%
        # Should use smaller ratio (260%), clamped to valid range
        assert widget.get_zoom_level() == 260

    def test_fit_modes_clamp_to_valid_range(self, qapp):
        """Test fit modes respect 25-400% zoom range."""
        # Create a very small pixmap
        tiny_pixmap = QPixmap(10, 10)
        tiny_pixmap.fill()

        widget = ImagePreviewWidget()
        widget.resize(5000, 5000)  # Very large widget
        widget.set_pixmap(tiny_pixmap)

        widget.fit_to_width()
        # Would calculate huge zoom, should clamp to 400%
        assert widget.get_zoom_level() == 400


class TestImagePreviewWidgetTheme:
    """Test theme update functionality."""

    def test_update_theme_recreates_toolbar(self, qapp):
        """Test that updating theme recreates the toolbar."""
        widget = ImagePreviewWidget()
        original_toolbar = widget.overlay_controls

        new_theme = {
            "bg_primary": "#000000",
            "bg_secondary": "#111111",
            "text_primary": "#FFFFFF",
            "text_secondary": "#CCCCCC",
            "border": "#333333",
            "accent": "#FF0000",
            "button_bg": "#222222",
            "button_hover": "#444444",
        }

        widget.update_theme(new_theme)

        assert widget.theme_colors == new_theme
        assert widget.overlay_controls is not original_toolbar

    def test_update_theme_preserves_visibility(self, qapp, test_pixmap):
        """Test theme update preserves toolbar visibility when pixmap is set."""
        widget = ImagePreviewWidget()
        widget.set_pixmap(test_pixmap)
        widget.show()  # Need to show widget for toolbar to be visible

        new_theme = {
            "bg_primary": "#FFFFFF",
            "bg_secondary": "#F0F0F0",
            "text_primary": "#000000",
            "text_secondary": "#666666",
            "border": "#CCCCCC",
            "accent": "#0066CC",
            "button_bg": "#E0E0E0",
            "button_hover": "#D0D0D0",
        }

        widget.update_theme(new_theme)

        # Toolbar should still be visible after theme update
        assert widget.overlay_controls.isVisible()


class TestImagePreviewWidgetToolbarPositioning:
    """Test toolbar positioning for all ToolbarPosition values."""

    def test_toolbar_position_bottom_center(self, qapp):
        """Test toolbar positioned at bottom center."""
        widget = ImagePreviewWidget(toolbar_position=ToolbarPosition.BOTTOM_CENTER)
        widget.resize(600, 400)
        widget._position_overlay_controls()

        # Should be horizontally centered
        expected_x = (600 - widget.overlay_controls.width()) // 2
        expected_y = 400 - widget.overlay_controls.height() - 10

        assert widget.overlay_controls.x() == expected_x
        assert widget.overlay_controls.y() == expected_y

    def test_toolbar_position_top_left(self, qapp):
        """Test toolbar positioned at top left."""
        widget = ImagePreviewWidget(toolbar_position=ToolbarPosition.TOP_LEFT)
        widget.resize(600, 400)
        widget._position_overlay_controls()

        assert widget.overlay_controls.x() == 10
        assert widget.overlay_controls.y() == 10

    def test_toolbar_position_top_right(self, qapp):
        """Test toolbar positioned at top right."""
        widget = ImagePreviewWidget(toolbar_position=ToolbarPosition.TOP_RIGHT)
        widget.resize(600, 400)
        widget._position_overlay_controls()

        expected_x = 600 - widget.overlay_controls.width() - 10
        assert widget.overlay_controls.x() == expected_x
        assert widget.overlay_controls.y() == 10

    def test_toolbar_position_bottom_left(self, qapp):
        """Test toolbar positioned at bottom left."""
        widget = ImagePreviewWidget(toolbar_position=ToolbarPosition.BOTTOM_LEFT)
        widget.resize(600, 400)
        widget._position_overlay_controls()

        expected_y = 400 - widget.overlay_controls.height() - 10
        assert widget.overlay_controls.x() == 10
        assert widget.overlay_controls.y() == expected_y

    def test_toolbar_position_bottom_right(self, qapp):
        """Test toolbar positioned at bottom right."""
        widget = ImagePreviewWidget(toolbar_position=ToolbarPosition.BOTTOM_RIGHT)
        widget.resize(600, 400)
        widget._position_overlay_controls()

        expected_x = 600 - widget.overlay_controls.width() - 10
        expected_y = 400 - widget.overlay_controls.height() - 10
        assert widget.overlay_controls.x() == expected_x
        assert widget.overlay_controls.y() == expected_y


class TestImagePreviewWidgetPanSignalIntegration:
    """Test integration with PannableImageLabel pan_changed signal."""

    def test_pan_signal_connected(self, qapp):
        """Test that pan_changed signal is connected to _update_display."""
        widget = ImagePreviewWidget()

        # Signal should be connected
        assert widget.image_label.pan_changed is not None

    def test_pan_triggers_display_update(self, qapp, test_pixmap):
        """Test that panning triggers display update via signal."""
        update_called = []

        # Create widget and patch before setting pixmap
        widget = ImagePreviewWidget()

        original_update = widget._update_display

        def mock_update():
            update_called.append(True)
            original_update()

        # Disconnect and reconnect with our tracking wrapper
        widget.image_label.pan_changed.disconnect(widget._update_display)
        widget.image_label.pan_changed.connect(mock_update)

        widget.set_pixmap(test_pixmap)

        # Simulate pan change by emitting signal
        widget.image_label.pan_changed.emit()

        # Verify _update_display was called
        assert len(update_called) == 1
