"""DraggableThumbnail — a QLabel that emits clicked and supports drag-and-drop reordering."""

from PyQt6.QtCore import QMimeData, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QDrag
from PyQt6.QtWidgets import QLabel

from ui.theme.styles import Colors


class DraggableThumbnail(QLabel):
    """Thumbnail widget that emits a clicked signal and supports drag-and-drop page reordering."""

    clicked = pyqtSignal()
    drag_started = pyqtSignal(int)  # index
    drop_requested = pyqtSignal(int, int)  # from_index, to_index

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.index = index
        self.setAcceptDrops(True)
        self.drag_active = False

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.pos()
        self.clicked.emit()

    def mouseMoveEvent(self, event):  # noqa: N802
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if (event.pos() - self.drag_start_position).manhattanLength() < 10:
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(str(self.index))
        drag.setMimeData(mime_data)
        drag.setPixmap(self.pixmap().scaled(60, 80, Qt.AspectRatioMode.KeepAspectRatio))

        self.drag_started.emit(self.index)
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self.setStyleSheet(self.styleSheet() + f"background: {Colors.PRIMARY_PALE};")

    def dragLeaveEvent(self, event):  # noqa: N802
        current_style = self.styleSheet()
        self.setStyleSheet(current_style.replace(f"background: {Colors.PRIMARY_PALE};", ""))

    def dropEvent(self, event):  # noqa: N802
        from_index = int(event.mimeData().text())
        to_index = self.index
        self.drop_requested.emit(from_index, to_index)
        event.acceptProposedAction()

        current_style = self.styleSheet()
        self.setStyleSheet(current_style.replace(f"background: {Colors.PRIMARY_PALE};", ""))
