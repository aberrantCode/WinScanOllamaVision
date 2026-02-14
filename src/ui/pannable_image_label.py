"""
Pannable image label widget for zoomed image navigation.

Provides a QLabel subclass with click & drag panning and scroll wheel zoom support.
"""

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QWheelEvent
from PyQt6.QtWidgets import QLabel


class PannableImageLabel(QLabel):
    """QLabel with click & drag panning and scroll wheel zoom support."""

    # Signal emitted when pan offset changes
    pan_changed = pyqtSignal()
    # Signal emitted when zoom is requested via scroll wheel (delta in steps)
    zoom_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_panning = False
        self.pan_start_pos = QPoint()
        self.pan_offset = QPoint(0, 0)
        self.zoom_level = 100
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Enable mouse tracking to show appropriate cursor
        self.setMouseTracking(True)

    def set_zoom_level(self, zoom: int):
        """Update zoom level to control cursor and panning behavior."""
        self.zoom_level = zoom
        self._update_cursor()

    def reset_pan(self):
        """Reset pan offset to center."""
        self.pan_offset = QPoint(0, 0)

    def get_pan_offset(self) -> QPoint:
        """Get current pan offset."""
        return QPoint(self.pan_offset)

    def set_pan_offset(self, offset: QPoint):
        """Set pan offset."""
        self.pan_offset = offset

    def mousePressEvent(self, event):  # noqa: N802
        """Start panning on left click (works at any zoom level)."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_panning = True
            self.pan_start_pos = event.pos()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        """Update pan offset while dragging."""
        if self.is_panning:
            delta = event.pos() - self.pan_start_pos
            self.pan_offset += delta
            self.pan_start_pos = event.pos()

            # Emit signal for modern signal-based communication
            self.pan_changed.emit()

            # Backward compatibility: also call parent method if it exists
            if self.parent():
                parent = self.parent()
                while parent:
                    if hasattr(parent, "_update_image_preview"):
                        parent._update_image_preview()
                        break
                    parent = parent.parent()

            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        """End panning."""
        if self.is_panning and event.button() == Qt.MouseButton.LeftButton:
            self.is_panning = False
            self._update_cursor()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent | None):  # noqa: N802
        """Handle scroll wheel for zooming."""
        if event is None:
            return

        # Get the scroll delta (positive = zoom in, negative = zoom out)
        delta = event.angleDelta().y()

        # Convert delta to zoom steps (120 units = 1 step on most mice)
        # Each step changes zoom by 10%
        steps = delta // 120
        zoom_change = steps * 10

        # Emit signal for parent to handle zoom change
        if zoom_change != 0:
            self.zoom_requested.emit(zoom_change)

        event.accept()

    def _update_cursor(self):
        """Update cursor to show panning capability."""
        if not self.is_panning:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
