"""Left-panel: reorderable page thumbnails.

Emits signals; the orchestrator (GuidedBundleWorkflow / BundleReviewWidget)
owns the page-order list and processes all navigation state.
"""

from __future__ import annotations

from functools import partial

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.bundle.bundle_colors import get_bundle_colors
from ui.bundle.draggable_thumbnail import DraggableThumbnail


class BundleThumbnailPanel(QWidget):
    """Scrollable thumbnail list with drag-and-drop reordering controls."""

    page_selected = pyqtSignal(int)
    page_reorder_requested = pyqtSignal(int, int)
    page_move_up_requested = pyqtSignal(int)
    page_move_down_requested = pyqtSignal(int)
    page_remove_requested = pyqtSignal(int)
    reanalyze_requested = pyqtSignal()
    add_page_requested = pyqtSignal()

    def __init__(self, dark_mode: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dark_mode = dark_mode
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        theme = get_bundle_colors(self._dark_mode)
        self.setStyleSheet(f"background: {theme['bg_primary']};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(10)

        # Header
        header_row = QHBoxLayout()
        self._pages_header = QLabel("📄 Pages")
        self._pages_header.setStyleSheet(
            f"font-weight: 600; color: {theme['text_primary']}; font-size: 13px;"
        )
        header_row.addWidget(self._pages_header)
        header_row.addStretch()
        layout.addLayout(header_row)

        # Action buttons (centred)
        actions_row = QHBoxLayout()
        actions_row.setSpacing(4)
        actions_row.addStretch()

        btn_style = f"""
            QPushButton {{
                background: {theme["button_bg"]};
                color: {theme["button_text"]};
                border: 1px solid {theme["border"]};
                border-radius: 4px;
                font-size: 10px;
                font-weight: 600;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                background: {theme["button_hover"]};
                border-color: {theme["border"]};
            }}
        """

        self._reanalyze_btn = QPushButton("↻ Re-analyze")
        self._reanalyze_btn.setToolTip("Re-analyze current page")
        self._reanalyze_btn.setStyleSheet(btn_style)
        self._reanalyze_btn.clicked.connect(self.reanalyze_requested)
        actions_row.addWidget(self._reanalyze_btn)

        self._add_page_btn = QPushButton("+ Add")
        self._add_page_btn.setToolTip("Add page from other bundles")
        self._add_page_btn.setStyleSheet(btn_style)
        self._add_page_btn.clicked.connect(self.add_page_requested)
        actions_row.addWidget(self._add_page_btn)

        actions_row.addStretch()
        layout.addLayout(actions_row)

        # Instructions
        self._instructions = QLabel("Drag to reorder • Click to preview")
        self._instructions.setStyleSheet(
            f"color: {theme['text_tertiary']}; font-size: 10px; background: transparent;"
        )
        self._instructions.setWordWrap(True)
        self._instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._instructions)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: {theme["bg_primary"]};
            }}
            QScrollArea > QWidget > QWidget {{
                background: {theme["bg_primary"]};
            }}
            QScrollArea > QWidget {{
                background: {theme["bg_primary"]};
            }}
        """)

        self._thumbnail_container = QWidget()
        self._thumbnail_container.setStyleSheet(f"background: {theme['bg_primary']};")
        self._thumbnail_layout = QVBoxLayout(self._thumbnail_container)
        self._thumbnail_layout.setSpacing(8)
        self._thumbnail_layout.setContentsMargins(0, 0, 0, 0)
        self._thumbnail_layout.addStretch()

        self._scroll.setWidget(self._thumbnail_container)
        layout.addWidget(self._scroll)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def populate(
        self,
        file_paths: list[str],
        page_order: list[int],
        current_page_index: int,
        prototype_mode: bool,
    ) -> None:
        """Rebuild the thumbnail grid.

        Args:
            file_paths:         Ordered list of all image paths in this bundle.
            page_order:         Visual→actual index mapping (len == visible pages).
            current_page_index: Visual index of the currently selected page.
            prototype_mode:     When True, generate placeholder images instead of
                                loading real files.
        """
        # Clear existing widgets
        widgets_to_delete = []
        while self._thumbnail_layout.count():
            item = self._thumbnail_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.hide()
                widget.setParent(None)
                widgets_to_delete.append(widget)
        for widget in widgets_to_delete:
            widget.deleteLater()

        QApplication.processEvents()

        for visual_index, actual_index in enumerate(page_order):
            row = self._create_thumbnail_row(
                visual_index,
                actual_index,
                file_paths[actual_index],
                current_page_index,
                len(page_order),
                prototype_mode,
            )
            self._thumbnail_layout.addWidget(row)

        self._thumbnail_layout.addStretch()

    def apply_theme(self, dark_mode: bool) -> None:
        """Re-apply colour styles for the given theme."""
        self._dark_mode = dark_mode
        theme = get_bundle_colors(dark_mode)

        self.setStyleSheet(f"background: {theme['bg_primary']};")
        self._pages_header.setStyleSheet(
            f"font-weight: 600; color: {theme['text_primary']}; font-size: 13px; "
            f"background: transparent;"
        )
        self._thumbnail_container.setStyleSheet(f"background: {theme['bg_primary']};")
        self._scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {theme['bg_primary']}; }}"
        )
        self._instructions.setStyleSheet(f"color: {theme['text_tertiary']}; font-size: 10px;")

        btn_style = f"""
            QPushButton {{
                background: {theme["button_bg"]};
                color: {theme["button_text"]};
                border: 1px solid {theme["border"]};
                border-radius: 4px;
                font-size: 10px;
                font-weight: 600;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                background: {theme["button_hover"]};
                border-color: {theme["border"]};
            }}
        """
        self._reanalyze_btn.setStyleSheet(btn_style)
        self._add_page_btn.setStyleSheet(btn_style)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_thumbnail_row(
        self,
        visual_index: int,
        actual_index: int,
        file_path: str,
        current_page_index: int,
        total_pages: int,
        prototype_mode: bool,
    ) -> QWidget:
        theme = get_bundle_colors(self._dark_mode)

        row = QWidget()
        row.setStyleSheet(f"background: {theme['bg_primary']};")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # --- Thumbnail pixmap ---
        if prototype_mode:
            pixmap = QPixmap(80, 100)
            base_color = QColor(220 + (actual_index * 10) % 30, 230, 245)
            pixmap.fill(base_color)
            painter = QPainter(pixmap)
            painter.drawText(
                pixmap.rect(), Qt.AlignmentFlag.AlignCenter, f"Page\n{actual_index + 1}"
            )
            painter.end()
        else:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                pixmap = QPixmap(80, 100)
                pixmap.fill(QColor(220, 230, 245))
                painter = QPainter(pixmap)
                painter.drawText(
                    pixmap.rect(),
                    Qt.AlignmentFlag.AlignCenter,
                    f"Page\n{actual_index + 1}\n(Error)",
                )
                painter.end()
            else:
                pixmap = pixmap.scaled(
                    80,
                    100,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

        thumbnail = DraggableThumbnail(visual_index)
        thumbnail.setPixmap(pixmap)
        thumbnail.setFixedSize(80, 100)

        # Selection border
        if visual_index == current_page_index:
            border_color = theme["selected"]
            border_width = 3
        else:
            border_color = theme["border"]
            border_width = 1

        thumbnail.setStyleSheet(f"""
            DraggableThumbnail {{
                border: {border_width}px solid {border_color};
                background: {theme["bg_primary"]};
                border-radius: 4px;
            }}
            DraggableThumbnail:hover {{
                border-color: {theme["selected"]};
            }}
        """)

        # Signals: forward drag-drop as page_reorder_requested, click as page_selected
        thumbnail.drop_requested.connect(self.page_reorder_requested)
        thumbnail.clicked.connect(partial(self.page_selected.emit, visual_index))

        layout.addWidget(thumbnail)

        # --- Action buttons (page-number + up/down/remove) ---
        actions_container = QWidget()
        actions_layout = QVBoxLayout(actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(2)

        page_num_lbl = QLabel(f"{visual_index + 1}")
        page_num_lbl.setStyleSheet(
            f"color: {theme['text_primary']}; font-size: 10px; font-weight: 700; "
            f"background: transparent;"
        )
        page_num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_num_lbl.setFixedWidth(24)
        actions_layout.addWidget(page_num_lbl)

        btn_style = f"""
            QPushButton {{
                background: {theme["button_bg"]};
                border: 1px solid {theme["border"]};
                border-radius: 2px;
                color: {theme["text_primary"]};
                font-size: 8px;
                font-weight: bold;
                min-width: 20px;
                max-width: 20px;
                min-height: 18px;
                max-height: 18px;
                padding: 0;
            }}
            QPushButton:hover {{
                background: {theme["bg_hover"]};
                border-color: {theme["border_focus"]};
            }}
            QPushButton:disabled {{
                background: {theme["bg_secondary"]};
                color: {theme["text_disabled"]};
                border-color: {theme["border_light"]};
            }}
        """

        remove_style = f"""
            QPushButton {{
                background: {theme["button_bg"]};
                color: {theme["text_primary"]};
                border: 1px solid {theme["border"]};
                border-radius: 2px;
                font-size: 11px;
                font-weight: bold;
                min-width: 20px;
                max-width: 20px;
                min-height: 18px;
                max-height: 18px;
                padding: 0;
            }}
            QPushButton:hover {{
                background: {theme["danger"]};
                color: white;
                border-color: {theme["danger"]};
            }}
        """

        up_btn = QPushButton("▲")
        up_btn.setStyleSheet(btn_style)
        up_btn.setToolTip("Move page up")
        up_btn.setEnabled(visual_index > 0)
        up_btn.clicked.connect(lambda: self.page_move_up_requested.emit(visual_index))
        actions_layout.addWidget(up_btn)

        down_btn = QPushButton("▼")
        down_btn.setStyleSheet(btn_style)
        down_btn.setToolTip("Move page down")
        down_btn.setEnabled(visual_index < total_pages - 1)
        down_btn.clicked.connect(lambda: self.page_move_down_requested.emit(visual_index))
        actions_layout.addWidget(down_btn)

        remove_btn = QPushButton("×")
        remove_btn.setStyleSheet(remove_style)
        remove_btn.setToolTip("Remove page from bundle")
        remove_btn.clicked.connect(lambda: self.page_remove_requested.emit(visual_index))
        actions_layout.addWidget(remove_btn)

        layout.addWidget(actions_container)
        return row
