"""
Pipeline stage constants, shared helpers, and the header widget.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QWidget

STAGE_IMPORT = 0
STAGE_ANALYZE = 1
STAGE_BUNDLE = 2
STAGE_EXPORT = 3
STAGE_LABELS = ["Import", "Analyze", "Bundle", "Export"]

_LINK_STYLE = (
    "QPushButton {{ border: none; padding: 0; font-size: 9pt; color: {0}; }}"
    " QPushButton:hover {{ text-decoration: underline; }}"
)


def _make_divider() -> QFrame:
    """Return a 1-pixel horizontal rule for use inside panel layouts."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    return line


# ---------------------------------------------------------------------------
# Pipeline header — custom painted stage rail
# ---------------------------------------------------------------------------


class PipelineHeaderWidget(QWidget):
    """
    Horizontal stage rail showing four pipeline stages as connected nodes.

    Completed stages: filled green node.
    Active stage: filled blue node, bold label.
    Pending stages: hollow node, dimmed label.
    """

    stage_clicked = pyqtSignal(int)  # emitted when user clicks a stage node

    # Node geometry constants
    _NODE_W: int = 76
    _NODE_H: int = 26
    _NODE_CORNER_R: int = 8
    _LABEL_FONT_PT: int = 8

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_stage = STAGE_IMPORT
        self._completed: set[int] = set()
        self._bg_color = QColor("#0B1120")
        self.setFixedHeight(58)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_bg_color(self, color: str) -> None:
        """Set the header background colour and trigger a repaint."""
        self._bg_color = QColor(color)
        self.update()

    # ------------------------------------------------------------------
    # Public API

    def set_stage(self, stage: int, completed: set[int] | None = None) -> None:
        self._current_stage = stage
        if completed is not None:
            self._completed = completed
        self.update()

    def mark_complete(self, stage: int) -> None:
        self._completed.add(stage)
        self.update()

    # ------------------------------------------------------------------
    # Drawing

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Stylesheet background-color is ignored on custom-painted QWidgets
        # unless we explicitly fill here.
        painter.fillRect(self.rect(), self._bg_color)

        w = self.width()
        n = len(STAGE_LABELS)
        node_w, node_h, corner_r = self._NODE_W, self._NODE_H, self._NODE_CORNER_R
        y_center = (self.height() - node_h) // 2 + node_h // 2  # vertically centred

        # Evenly distribute node centres
        xs = [int(w * (i + 0.5) / n) for i in range(n)]

        # Colors
        col_complete = QColor("#10B981")
        col_active = QColor("#3B82F6")
        col_pending = QColor("#4A4A4A")
        col_line = QColor("#4A4A4A")

        # Connecting lines (drawn behind nodes)
        for i in range(n - 1):
            x1, x2 = xs[i], xs[i + 1]
            painter.setPen(QPen(col_complete if i in self._completed else col_line, 2))
            painter.drawLine(x1 + node_w // 2, y_center, x2 - node_w // 2, y_center)

        # Stage nodes
        for i, label in enumerate(STAGE_LABELS):
            x = xs[i]
            rx, ry = x - node_w // 2, y_center - node_h // 2

            if i in self._completed:
                painter.setBrush(col_complete)
                painter.setPen(QPen(col_complete, 2))
                painter.drawRoundedRect(rx, ry, node_w, node_h, corner_r, corner_r)
                # Checkmark
                painter.setPen(QPen(QColor("white"), 2))
                painter.drawLine(x - 6, y_center, x - 2, y_center + 4)
                painter.drawLine(x - 2, y_center + 4, x + 6, y_center - 4)
            elif i == self._current_stage:
                painter.setBrush(col_active)
                painter.setPen(QPen(col_active, 2))
                painter.drawRoundedRect(rx, ry, node_w, node_h, corner_r, corner_r)
                painter.setPen(QPen(QColor("white"), 1))
                f = QFont()
                f.setPointSize(self._LABEL_FONT_PT)
                f.setBold(True)
                painter.setFont(f)
                painter.drawText(rx, ry, node_w, node_h, Qt.AlignmentFlag.AlignCenter, label)
            else:
                painter.setBrush(QColor("transparent"))
                painter.setPen(QPen(col_pending, 2))
                painter.drawRoundedRect(rx, ry, node_w, node_h, corner_r, corner_r)
                painter.setPen(QPen(col_pending, 1))
                f = QFont()
                f.setPointSize(self._LABEL_FONT_PT)
                painter.setFont(f)
                painter.drawText(rx, ry, node_w, node_h, Qt.AlignmentFlag.AlignCenter, label)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        w = self.width()
        n = len(STAGE_LABELS)
        xs = [int(w * (i + 0.5) / n) for i in range(n)]
        for i, x in enumerate(xs):
            if abs(event.pos().x() - x) < self._NODE_W // 2 + 6:
                self.stage_clicked.emit(i)
                return
