"""Reusable QLabel subclass that emits a clicked signal."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QLabel


class ClickableLabel(QLabel):
    """QLabel that emits a clicked signal."""

    clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def mousePressEvent(self, event):  # noqa: N802
        self.clicked.emit()
