"""Tests for bundle_colors.py — both palettes must expose required keys."""

from ui.bundle.bundle_colors import get_bundle_colors, hex_to_rgb

REQUIRED_KEYS = {
    "bg_primary",
    "bg_secondary",
    "bg_tertiary",
    "bg_input",
    "bg_hover",
    "text_primary",
    "text_secondary",
    "text_tertiary",
    "text_disabled",
    "border",
    "border_light",
    "border_focus",
    "hover",
    "selected",
    "active",
    "danger",
    "danger_hover",
    "success",
    "success_hover",
    "warning",
    "warning_hover",
    "info",
    "info_hover",
    "thumbnail_border",
    "thumbnail_selected",
    "preview_bg",
    "metadata_bg",
    "button_bg",
    "button_text",
    "button_hover",
}


class TestGetBundleColors:
    def test_dark_palette_has_required_keys(self):
        palette = get_bundle_colors(dark_mode=True)
        missing = REQUIRED_KEYS - set(palette)
        assert not missing, f"Dark palette missing keys: {missing}"

    def test_light_palette_has_required_keys(self):
        palette = get_bundle_colors(dark_mode=False)
        missing = REQUIRED_KEYS - set(palette)
        assert not missing, f"Light palette missing keys: {missing}"

    def test_dark_palette_values_are_strings(self):
        palette = get_bundle_colors(dark_mode=True)
        for key, value in palette.items():
            assert isinstance(value, str), f"Key '{key}' is not a string: {value!r}"

    def test_light_palette_values_are_strings(self):
        palette = get_bundle_colors(dark_mode=False)
        for key, value in palette.items():
            assert isinstance(value, str), f"Key '{key}' is not a string: {value!r}"

    def test_dark_and_light_have_same_keys(self):
        dark = set(get_bundle_colors(True))
        light = set(get_bundle_colors(False))
        assert dark == light

    def test_dark_bg_primary_differs_from_light(self):
        assert get_bundle_colors(True)["bg_primary"] != get_bundle_colors(False)["bg_primary"]


class TestHexToRgb:
    def test_black(self):
        assert hex_to_rgb("#000000") == (0, 0, 0)

    def test_white(self):
        assert hex_to_rgb("#ffffff") == (255, 255, 255)

    def test_known_color(self):
        # #1e293b → (30, 41, 59)
        assert hex_to_rgb("#1e293b") == (30, 41, 59)

    def test_no_leading_hash(self):
        assert hex_to_rgb("ffffff") == (255, 255, 255)
