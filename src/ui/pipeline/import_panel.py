"""
Stage 1: Import panel — discover and review image files.
"""

import contextlib
import os
from datetime import datetime, timezone
from typing import Any

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config.config_manager import ConfigManager
from db.analysis_db import AnalysisDB
from db.repositories.image_files_repo import ImageFilesRepository
from services.discovery_worker import DiscoveryWorker
from services.logging_service import get_logger
from ui.image_preview_widget import ImagePreviewWidget, ToolbarPosition, ToolbarSize
from ui.pipeline.stages import _LINK_STYLE
from ui.styles import Colors, show_information, show_warning
from ui.theme_manager import ThemeManager


class ImportPanel(QWidget):
    """
    Stage 1: Import — discover and review image files.

    Lets the operator scan source directories for new images,
    inspect them, and remove unwanted items before analysis.
    """

    next_requested = pyqtSignal()

    def __init__(
        self,
        analysis_db: AnalysisDB,
        config_manager: ConfigManager,
        dark_mode: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.analysis_db = analysis_db
        self.config_manager = config_manager
        self.dark_mode = dark_mode
        self._image_repo: ImageFilesRepository = ImageFilesRepository(analysis_db.connection)

        self._discovery_worker: DiscoveryWorker | None = None
        self.image_tree: QTreeWidget | None = None
        self.preview_widget: ImagePreviewWidget | None = None
        self.directory_combo: QComboBox | None = None
        self.show_analyzed_cb: QCheckBox | None = None
        self.tree_count_label: QLabel | None = None
        self.scan_progress_bar: QProgressBar | None = None
        self.scan_btn: QPushButton | None = None
        self._splitter: QSplitter | None = None
        self._preview_stack: QStackedWidget | None = None
        self._select_all_btn: QPushButton | None = None
        self._deselect_btn: QPushButton | None = None

        self._build_ui()
        QTimer.singleShot(0, self._post_init)

    def _c(self) -> dict[str, str]:
        return ThemeManager.get_colors(self.dark_mode)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 8)
        root.setSpacing(8)

        # ── Section title
        title = QLabel("Import — Review discovered images")
        title.setStyleSheet(
            f"font-size: 11pt; font-weight: 600; color: {self._c()['text_primary']};"
        )
        root.addWidget(title)

        # ── Controls bar
        bar = QHBoxLayout()
        bar.setSpacing(8)

        dir_lbl = QLabel("Directory:")
        dir_lbl.setFixedHeight(28)
        bar.addWidget(dir_lbl)

        self.directory_combo = QComboBox()
        self.directory_combo.setFixedHeight(28)
        self.directory_combo.setMinimumWidth(220)
        c = self._c()
        self.directory_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {c['bg_secondary']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: 4px;
                padding: 2px 8px;
                min-height: 25px;
            }}
            QComboBox:drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {c['text_secondary']};
                margin-right: 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {c['bg_secondary']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                selection-background-color: {c['bg_hover']};
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 25px;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {c['bg_hover']};
            }}
        """)
        self._populate_directory_combo()
        self.directory_combo.currentIndexChanged.connect(self._refresh)
        bar.addWidget(self.directory_combo, stretch=1)

        self.show_analyzed_cb = QCheckBox("Show analyzed")
        self.show_analyzed_cb.setChecked(True)
        self.show_analyzed_cb.setFixedHeight(28)
        self.show_analyzed_cb.stateChanged.connect(self._refresh)
        bar.addWidget(self.show_analyzed_cb)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedHeight(28)
        refresh_btn.setFixedWidth(70)
        refresh_btn.clicked.connect(self._refresh)
        bar.addWidget(refresh_btn)

        self.scan_btn = QPushButton("Discover Images")
        self.scan_btn.setFixedHeight(28)
        self.scan_btn.setFixedWidth(130)
        self.scan_btn.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.PRIMARY}; color: white; "
            f"border: none; border-radius: 4px; padding: 4px 12px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: {Colors.PRIMARY_HOVER}; }}"
            f"QPushButton:pressed {{ background-color: #1D4ED8; }}"
        )
        self.scan_btn.clicked.connect(self._on_scan_clicked)
        bar.addWidget(self.scan_btn)

        root.addLayout(bar)

        # ── Progress bar (hidden until scanning)
        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setTextVisible(True)
        self.scan_progress_bar.setFixedHeight(18)
        self.scan_progress_bar.setVisible(False)
        root.addWidget(self.scan_progress_bar)

        # ── Tree / Preview splitter
        # Left: file tree
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        tree_header = QHBoxLayout()
        tree_header.setSpacing(10)
        self.tree_count_label = QLabel("0 images")
        self.tree_count_label.setStyleSheet(f"color: {self._c()['text_tertiary']}; font-size: 9pt;")
        tree_header.addStretch()
        tree_header.addWidget(self.tree_count_label)

        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.setFlat(True)
        self._select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._select_all_btn.setStyleSheet(_LINK_STYLE.format(self._c().get("accent", "#3B82F6")))
        self._select_all_btn.clicked.connect(self._on_select_all)
        tree_header.addWidget(self._select_all_btn)

        self._deselect_btn = QPushButton("Deselect")
        self._deselect_btn.setFlat(True)
        self._deselect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._deselect_btn.setStyleSheet(
            _LINK_STYLE.format(self._c().get("text_secondary", "#9CA3AF"))
        )
        self._deselect_btn.setVisible(False)
        self._deselect_btn.clicked.connect(self._on_deselect)
        tree_header.addWidget(self._deselect_btn)

        left_layout.addLayout(tree_header)

        self.image_tree = QTreeWidget()
        self.image_tree.setHeaderLabels(["Image", "Status", "Date Created", "Size"])
        self.image_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        tree_hdr = self.image_tree.header()
        if tree_hdr is None:
            return
        tree_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        tree_hdr.setStretchLastSection(False)
        self.image_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.image_tree.setColumnWidth(1, 90)
        self.image_tree.setColumnWidth(2, 96)
        self.image_tree.setColumnWidth(3, 68)
        self.image_tree.itemSelectionChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.image_tree)

        # Action buttons
        act_bar = QHBoxLayout()
        act_bar.setSpacing(6)

        unregister_btn = QPushButton("Unregister")
        unregister_btn.setToolTip("Remove from database (file stays on disk)")
        unregister_btn.clicked.connect(self._on_unregister)
        act_bar.addWidget(unregister_btn)

        ignore_btn = QPushButton("Ignore")
        ignore_btn.setToolTip("Skip during future analysis runs")
        ignore_btn.clicked.connect(self._on_ignore)
        act_bar.addWidget(ignore_btn)

        act_bar.addStretch()
        left_layout.addLayout(act_bar)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(left)

        # Right: placeholder or image preview, always visible
        c = self._c()
        preview_colors = {**c, "button_bg": c["bg_tertiary"], "button_hover": c["bg_hover"]}
        self.preview_widget = ImagePreviewWidget(
            toolbar_size=ToolbarSize.COMPACT,
            toolbar_position=ToolbarPosition.BOTTOM_CENTER,
            theme_colors=preview_colors,
            config_manager=self.config_manager,
            analysis_db=self.analysis_db,
        )
        self._preview_stack = QStackedWidget()
        self._preview_stack.addWidget(self._build_preview_placeholder())  # index 0: no selection
        self._preview_stack.addWidget(self.preview_widget)  # index 1: image preview
        self._preview_stack.setCurrentIndex(0)

        self._splitter.addWidget(self._preview_stack)
        self._splitter.setSizes([500, 500])
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, False)

        root.addWidget(self._splitter, stretch=1)

        # ── Footer navigation

    def _build_preview_placeholder(self) -> QWidget:
        """Empty-state widget shown in the preview pane when no item is selected."""
        c = self._c()
        outer = QWidget()
        layout = QVBoxLayout(outer)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QWidget()
        card.setMaximumWidth(260)
        card.setStyleSheet("border: 1px dashed rgba(128,128,128,0.35); border-radius: 12px;")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 32, 28, 32)
        card_layout.setSpacing(10)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel("\U0001f5bc")  # 🖼 frame with picture
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(
            f"font-size: 32pt; color: {c['text_tertiary']};"
            " border: none; background: transparent;"
        )
        card_layout.addWidget(icon_lbl)

        title_lbl = QLabel("Select an image to preview")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet(
            f"font-size: 10pt; font-weight: 600; color: {c['text_secondary']};"
            " border: none; background: transparent;"
        )
        card_layout.addWidget(title_lbl)

        hint_lbl = QLabel("Click any item in the list\nto see a full preview here.")
        hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_lbl.setStyleSheet(
            f"font-size: 9pt; color: {c['text_tertiary']};"
            " border: none; background: transparent;"
        )
        card_layout.addWidget(hint_lbl)

        layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        return outer

    def _post_init(self) -> None:
        self._populate_directory_combo()
        self._refresh()

    def _populate_directory_combo(self) -> None:
        if self.directory_combo is None:
            return

        # Temporarily disconnect to avoid triggering _refresh mid-population.
        # We use disconnect/reconnect rather than blockSignals because blockSignals
        # suppresses Qt's internal state update that sets currentIndex when the
        # first item is added, leaving the display blank.
        with contextlib.suppress(RuntimeError, TypeError):
            self.directory_combo.currentIndexChanged.disconnect(self._refresh)

        current_text = self.directory_combo.currentText()

        self.directory_combo.clear()
        self.directory_combo.addItem("All Directories")

        try:
            dirs = self.config_manager.get_directories()
            for d in dirs:
                self.directory_combo.addItem(d)
        except Exception as e:
            get_logger().error("[ImportPanel] Failed to load directories: %s", e, exc_info=True)

        # Restore previous selection if it still exists; otherwise keep index 0
        idx = self.directory_combo.findText(current_text)
        if idx > 0:
            self.directory_combo.setCurrentIndex(idx)

        self.directory_combo.currentIndexChanged.connect(self._refresh)

    def _refresh(self) -> None:
        if not self.image_tree:
            return

        image_repo = self._image_repo
        all_images: list[dict[str, Any]] = image_repo.get_all()

        # Filter
        dir_filter = (
            self.directory_combo.currentText() if self.directory_combo else "All Directories"
        )
        if dir_filter != "All Directories":
            normalized_filter = os.path.normpath(dir_filter)
            all_images = [i for i in all_images if i["directory_path"] == normalized_filter]

        show_analyzed = self.show_analyzed_cb.isChecked() if self.show_analyzed_cb else True
        if not show_analyzed:
            all_images = [i for i in all_images if i.get("status") != "analyzed"]

        all_images = [i for i in all_images if not i.get("is_ignored", False)]

        self.image_tree.clear()
        c = self._c()

        for img in all_images:
            status = img.get("status", "registered")
            mtime = img.get("file_mtime") or 0
            date_str = (
                datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d") if mtime else ""
            )
            size_str = self._fmt_size(img.get("file_size") or 0)

            item = QTreeWidgetItem([img["filename"], status, date_str, size_str])
            item.setData(0, Qt.ItemDataRole.UserRole, img["file_path"])
            item.setTextAlignment(3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            status_color = {
                "analyzed": "#10B981",
                "error": "#EF4444",
                "registered": c["text_tertiary"],
            }.get(status, c["text_tertiary"])
            item.setForeground(1, QColor(status_color))
            item.setForeground(2, QColor(c["text_tertiary"]))
            item.setForeground(3, QColor(c["text_tertiary"]))

            self.image_tree.addTopLevelItem(item)

        total = self.image_tree.topLevelItemCount()

        if self.tree_count_label:
            self.tree_count_label.setText(f"{total} image{'s' if total != 1 else ''}")

        # Fit column 0 to the widest filename; the horizontal scrollbar appears
        # automatically if the tree narrows (e.g. when the preview panel opens).
        self.image_tree.resizeColumnToContents(0)

    def refresh(self) -> None:
        """Public entry point — parent calls this instead of the private _refresh."""
        self._refresh()

    def _selected_paths(self) -> list[str]:
        if not self.image_tree:
            return []
        paths = []
        for item in self.image_tree.selectedItems():
            p = item.data(0, Qt.ItemDataRole.UserRole)
            if p:
                paths.append(p)
        return paths

    def _on_selection_changed(self) -> None:
        if not self.preview_widget or not self.image_tree:
            return
        paths = self._selected_paths()
        has_selection = len(paths) > 0

        if self._preview_stack:
            self._preview_stack.setCurrentIndex(1 if has_selection else 0)
        if self._deselect_btn:
            self._deselect_btn.setVisible(has_selection)

        if not has_selection:
            return

        from PyQt6.QtGui import QPixmap

        pixmap = QPixmap(paths[0])
        if not pixmap.isNull():
            self.preview_widget.set_pixmap(pixmap, apply_fit="window", file_path=paths[0])

    def _on_select_all(self) -> None:
        """Select all items in the tree."""
        if self.image_tree:
            self.image_tree.selectAll()

    def _on_deselect(self) -> None:
        """Clear the current tree selection."""
        if self.image_tree:
            self.image_tree.clearSelection()

    def _on_scan_clicked(self) -> None:
        if self._discovery_worker and self._discovery_worker.isRunning():
            self._discovery_worker.stop()
            return

        dirs = self.config_manager.get_directories()
        if not dirs:
            show_warning(self, "No Directories", "No source directories configured.")
            return

        if self.scan_btn:
            self.scan_btn.setText("Stop Scan")
        if self.scan_progress_bar:
            self.scan_progress_bar.setVisible(True)
            self.scan_progress_bar.setRange(0, 0)

        self._discovery_worker = DiscoveryWorker(self.config_manager, dirs)
        self._discovery_worker.progress.connect(self._on_scan_progress)
        self._discovery_worker.finished.connect(self._on_scan_finished)
        self._discovery_worker.error.connect(self._on_scan_error)
        self._discovery_worker.start()

    def _on_scan_progress(self, status: str, current: int, total: int) -> None:
        if self.scan_progress_bar:
            if total > 0:
                self.scan_progress_bar.setRange(0, total)
                self.scan_progress_bar.setValue(current)
            self.scan_progress_bar.setFormat(f"{status} ({current}/{total})")

    def _on_scan_finished(self, count: int) -> None:
        if self.scan_btn:
            self.scan_btn.setText("Discover Images")
        if self.scan_progress_bar:
            self.scan_progress_bar.setVisible(False)
        self._refresh()
        if count > 0:
            show_information(self, "Discovery Complete", f"Found {count} new image(s).")

    def _on_scan_error(self, error_msg: str) -> None:
        if self.scan_btn:
            self.scan_btn.setText("Discover Images")
        if self.scan_progress_bar:
            self.scan_progress_bar.setVisible(False)
        show_warning(self, "Discovery Error", f"Scan failed:\n{error_msg}")

    def _on_unregister(self) -> None:
        paths = self._selected_paths()
        if not paths:
            return
        image_repo = self._image_repo
        for p in paths:
            image_repo.mark_deleted(p)
        self._refresh()

    def _on_ignore(self) -> None:
        paths = self._selected_paths()
        if not paths:
            return
        image_repo = self._image_repo
        for p in paths:
            image_repo.set_ignored(p, ignored=True)
        self._refresh()

    @staticmethod
    def _fmt_size(size_bytes: int) -> str:
        if size_bytes >= 1_048_576:
            return f"{size_bytes / 1_048_576:.1f} MB"
        if size_bytes >= 1_024:
            return f"{size_bytes / 1_024:.1f} KB"
        return f"{size_bytes} B"
