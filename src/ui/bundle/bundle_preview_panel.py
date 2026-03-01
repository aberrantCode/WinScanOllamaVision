"""Center-panel: large image preview backed by ImagePreviewWidget.

The embedded ImagePreviewWidget owns its own zoom/rotation state and
renders a floating toolbar overlay for those controls.  The orchestrator
(BundleReviewWidget) drives the panel via ``display_page()``, reads
``rotation_angle`` at accept time, and calls ``reset_rotation()`` when
loading a new bundle.
"""

from __future__ import annotations

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from ui.bundle.bundle_colors import get_bundle_colors
from ui.image_preview.enums import ToolbarPosition, ToolbarSize
from ui.image_preview.image_preview_widget import ImagePreviewWidget


class BundlePreviewPanel(QWidget):
    """Large-image preview that delegates zoom/rotation to ImagePreviewWidget."""

    def __init__(self, dark_mode: bool, parent: QWidget | None = None) -> None:
        self._dark_mode = dark_mode
        self._original_pixmap: QPixmap | None = None
        super().__init__(parent)
        self._build_ui()

    # ------------------------------------------------------------------
    # Properties (read-only; used by orchestrator at accept time)
    # ------------------------------------------------------------------

    @property
    def rotation_angle(self) -> int:
        return self._ipw.rotation_angle

    @property
    def zoom_level(self) -> int:
        return self._ipw.zoom_level

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        theme = get_bundle_colors(self._dark_mode)
        self.setStyleSheet(f"background: {theme['preview_bg']};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        theme_colors = {
            "bg_primary": theme["preview_bg"],
            "bg_secondary": theme["bg_secondary"],
            "bg_tertiary": theme.get("bg_tertiary", theme["bg_secondary"]),
            "bg_hover": theme["bg_hover"],
            "text_primary": theme["text_primary"],
            "text_secondary": theme["text_secondary"],
            "text_tertiary": theme.get("text_tertiary", theme["text_secondary"]),
            "border": theme["border"],
            "accent": theme.get("selected", "#3B82F6"),
            "button_bg": theme["button_bg"],
            "button_hover": theme["button_hover"],
        }

        self._ipw = ImagePreviewWidget(
            parent=self,
            toolbar_size=ToolbarSize.COMPACT,
            toolbar_position=ToolbarPosition.BOTTOM_CENTER,
            theme_colors=theme_colors,
        )
        layout.addWidget(self._ipw)

    # ------------------------------------------------------------------
    # Public API (matches the interface BundleReviewWidget expects)
    # ------------------------------------------------------------------

    def display_page(self, pixmap: QPixmap, page_num: int, total_pages: int) -> None:
        """Display *pixmap* in the preview, resetting pan and applying a fit."""
        self._original_pixmap = pixmap
        self._ipw.set_pixmap(pixmap, apply_fit="width")

    def reset_rotation(self) -> None:
        """Reset rotation to 0° — called when a new bundle is loaded."""
        self._ipw.rotation_angle = 0

    def set_zoom(self, value: int) -> None:
        """Set zoom level (25–400 %). No-op once the toolbar owns zoom."""
        self._ipw.set_zoom_level(value)

    def rotate_cw(self) -> None:
        """Rotate 90° clockwise."""
        self._ipw._on_rotate_cw()  # noqa: SLF001

    def rotate_ccw(self) -> None:
        """Rotate 90° counter-clockwise."""
        self._ipw._on_rotate_ccw()  # noqa: SLF001

    def get_container_size(self) -> tuple[int, int]:
        """Return ``(width, height)`` of this widget for fit-to-* calculations."""
        return (self._ipw.width(), self._ipw.height())

    def get_original_pixel_size(self, rotation_adjusted: bool = True) -> tuple[int, int] | None:
        """Return ``(width, height)`` of the stored original pixmap."""
        if self._original_pixmap is None:
            return None
        w = self._original_pixmap.width()
        h = self._original_pixmap.height()
        angle = self._ipw.rotation_angle
        if rotation_adjusted and angle in (90, 270):
            return (h, w)
        return (w, h)

    def apply_theme(self, dark_mode: bool) -> None:
        """Re-apply colour styles for the given theme."""
        self._dark_mode = dark_mode
        theme = get_bundle_colors(dark_mode)
        self.setStyleSheet(f"background: {theme['preview_bg']};")
        theme_colors = {
            "bg_primary": theme["preview_bg"],
            "bg_secondary": theme["bg_secondary"],
            "bg_tertiary": theme.get("bg_tertiary", theme["bg_secondary"]),
            "bg_hover": theme["bg_hover"],
            "text_primary": theme["text_primary"],
            "text_secondary": theme["text_secondary"],
            "text_tertiary": theme.get("text_tertiary", theme["text_secondary"]),
            "border": theme["border"],
            "accent": theme.get("selected", "#3B82F6"),
            "button_bg": theme["button_bg"],
            "button_hover": theme["button_hover"],
        }
        self._ipw.theme_colors = theme_colors
        # Re-apply toolbar styling without recreating the widget
        if self._ipw.overlay_controls:
            self._ipw.overlay_controls.setStyleSheet(
                f"QWidget {{ background: {theme['preview_bg']}; "
                f"border: 2px solid {theme['border']}; border-radius: 6px; }}"
            )
