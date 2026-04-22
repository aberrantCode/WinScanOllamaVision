"""PannableImageLabel — QLabel with click-drag pan and scroll-wheel zoom."""

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QWheelEvent
from PyQt6.QtWidgets import QLabel


class PannableImageLabel(QLabel):
    """QLabel with click & drag panning and scroll wheel zoom support."""

    pan_changed = pyqtSignal()
    zoom_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_panning = False
        self.pan_start_pos = QPoint()
        self.pan_offset = QPoint(0, 0)
        self.zoom_level = 100
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
            self.pan_changed.emit()
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
        delta = event.angleDelta().y()
        steps = delta // 120
        zoom_change = steps * 10
        if zoom_change != 0:
            self.zoom_requested.emit(zoom_change)
        event.accept()

    def _update_cursor(self):
        """Update cursor to show panning capability."""
        if not self.is_panning:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
