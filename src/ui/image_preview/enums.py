"""Enum types for ImagePreviewWidget toolbar configuration."""

from enum import Enum


class ToolbarSize(Enum):
    """Toolbar size options for floating controls."""

    COMPACT = "compact"  # 20x20px buttons, 10pt font (50% of standard)
    STANDARD = "standard"  # 40x40px buttons, 20pt font (100%)


class ToolbarPosition(Enum):
    """Toolbar position options."""

    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"  # Default
    BOTTOM_RIGHT = "bottom_right"
