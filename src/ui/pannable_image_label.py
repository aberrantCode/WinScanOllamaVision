"""
Pannable image label widget for zoomed image navigation.

Provides a QLabel subclass with click & drag panning support.
"""

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QLabel


class PannableImageLabel(QLabel):
    """QLabel with click & drag panning support for zoomed images."""

    # Signal emitted when pan offset changes
    pan_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_panning = False
        self.pan_start_pos = QPoint()
        self.pan_offset = QPoint(0, 0)
        self.zoom_level = 100
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
        """Start panning on left click when zoomed."""
        if self.zoom_level > 100 and event.button() == Qt.MouseButton.LeftButton:
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

    def _update_cursor(self):
        """Update cursor based on zoom level."""
        if self.zoom_level > 100:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
