"""Center-panel: large image preview with internal zoom/rotation state.

Emits no signals; the orchestrator (GuidedBundleWorkflow / BundleReviewWidget)
drives it via set_zoom(), rotate_cw/ccw(), and reads rotation_angle / zoom_level
properties at accept time only.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QTransform
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.bundle.bundle_colors import get_bundle_colors


class BundlePreviewPanel(QWidget):
    """Large-image preview that owns its own zoom and rotation state."""

    def __init__(self, dark_mode: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dark_mode = dark_mode
        self._rotation_angle: int = 0
        self._zoom_level: int = 100
        self._original_pixmap: QPixmap | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # Properties (read-only; used by orchestrator at accept time)
    # ------------------------------------------------------------------

    @property
    def rotation_angle(self) -> int:
        return self._rotation_angle

    @property
    def zoom_level(self) -> int:
        return self._zoom_level

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        theme = get_bundle_colors(self._dark_mode)
        self.setStyleSheet(f"background: {theme['preview_bg']};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(0)

        preview_area = QWidget()
        preview_area.setMinimumSize(600, 500)
        preview_area.setStyleSheet(f"background: {theme['preview_bg']};")

        preview_layout = QVBoxLayout(preview_area)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(8)

        self._page_label = QLabel("Page 1")
        self._page_label.setStyleSheet(
            f"color: {theme['text_secondary']}; font-size: 13px; font-weight: 500;"
        )
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self._page_label)

        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet(f"background: {theme['preview_bg']};")
        preview_layout.addWidget(self._preview_label)

        layout.addWidget(preview_area)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def display_page(self, pixmap: QPixmap, page_num: int, total_pages: int) -> None:
        """Store *pixmap* and render it at the current zoom and rotation.

        Args:
            pixmap:      Pre-built pixmap for the page (prototype or real).
            page_num:    1-based page number shown in the label.
            total_pages: Total page count shown in the label.
        """
        self._original_pixmap = pixmap
        self._page_label.setText(f"Page {page_num} of {total_pages}")
        self._refresh_display()

    def set_zoom(self, value: int) -> None:
        """Update the zoom level (25–400 %) and refresh the display."""
        self._zoom_level = value
        self._refresh_display()

    def reset_rotation(self) -> None:
        """Reset rotation to 0° without triggering a display refresh.

        Call this at bundle-load time before display_page() is called.
        """
        self._rotation_angle = 0

    def rotate_cw(self) -> None:
        """Rotate 90° clockwise and refresh the display."""
        self._rotation_angle = (self._rotation_angle + 90) % 360
        self._refresh_display()

    def rotate_ccw(self) -> None:
        """Rotate 90° counter-clockwise and refresh the display."""
        self._rotation_angle = (self._rotation_angle - 90) % 360
        self._refresh_display()

    def get_container_size(self) -> tuple[int, int]:
        """Return ``(width, height)`` of this widget for fit-to-* calculations."""
        return (self.width(), self.height())

    def get_original_pixel_size(self, rotation_adjusted: bool = True) -> tuple[int, int] | None:
        """Return ``(width, height)`` of the stored original pixmap.

        When *rotation_adjusted* is ``True`` and rotation is 90° or 270°,
        width and height are swapped to reflect the rotated orientation.
        Returns ``None`` when no pixmap has been loaded yet.
        """
        if self._original_pixmap is None:
            return None
        w = self._original_pixmap.width()
        h = self._original_pixmap.height()
        if rotation_adjusted and self._rotation_angle in (90, 270):
            return (h, w)
        return (w, h)

    def apply_theme(self, dark_mode: bool) -> None:
        """Re-apply colour styles for the given theme."""
        self._dark_mode = dark_mode
        theme = get_bundle_colors(dark_mode)

        self.setStyleSheet(f"background: {theme['preview_bg']};")
        for child in self.findChildren(QWidget):
            if child not in (self._page_label, self._preview_label):
                child.setStyleSheet(f"background: {theme['preview_bg']};")

        self._preview_label.setStyleSheet(f"background: {theme['preview_bg']};")
        self._page_label.setStyleSheet(
            f"color: {theme['text_secondary']}; font-weight: 500; font-size: 12px;"
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _refresh_display(self) -> None:
        """Re-apply the current transform to the stored pixmap and update the label."""
        if self._original_pixmap is None:
            return
        transformed = self.apply_transform(
            self._original_pixmap, self._rotation_angle, self._zoom_level
        )
        self._preview_label.setPixmap(transformed)

    # ------------------------------------------------------------------
    # Static transform utility
    # ------------------------------------------------------------------

    @staticmethod
    def apply_transform(pixmap: QPixmap, rotation_angle: int, zoom_level: int) -> QPixmap:
        """Apply *rotation_angle* (degrees) and *zoom_level* (%) to *pixmap*.

        This is a pure function — it creates a new pixmap without mutating the
        input.  It may also be called from outside the panel (e.g., during PDF
        conversion) without holding a panel instance.
        """
        if rotation_angle != 0:
            transform = QTransform()
            transform.rotate(rotation_angle)
            pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        if zoom_level != 100:
            zoom_factor = zoom_level / 100.0
            new_width = int(pixmap.width() * zoom_factor)
            new_height = int(pixmap.height() * zoom_factor)
            pixmap = pixmap.scaled(
                new_width,
                new_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        return pixmap
