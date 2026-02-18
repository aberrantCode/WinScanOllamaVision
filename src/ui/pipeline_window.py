"""
Document Pipeline Window

Unified Import → Analyze → Bundle → Export workflow.
Replaces the separate Discover, Analysis Status, and Bundle windows
with a single surface that guides the operator through the full process.
"""

import logging
import os
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config.config_manager import ConfigManager
from db.analysis_db import AnalysisDB
from db.metadata_db import MetadataDB
from db.repositories.image_files_repo import ImageFilesRepository
from services.analysis_queue import AnalysisJob, AnalysisQueue, JobPriority, JobType
from services.bundling_service import BundlingService
from services.discovery_worker import DiscoveryWorker
from ui.analysis_status_window import AnalysisWorker
from ui.image_preview_widget import ImagePreviewWidget, ToolbarPosition, ToolbarSize
from ui.styles import Colors, show_information, show_warning
from ui.theme_manager import ThemeManager

if TYPE_CHECKING:
    from services.logging_service import get_logger
else:
    get_logger = None

logger: logging.Logger | None = None

STAGE_IMPORT = 0
STAGE_ANALYZE = 1
STAGE_BUNDLE = 2
STAGE_EXPORT = 3
STAGE_LABELS = ["Import", "Analyze", "Bundle", "Export"]


def _get_logger() -> logging.Logger:
    global logger
    if logger is None:
        from services.logging_service import get_logger as _gl

        logger = _gl()
    return logger


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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_stage = STAGE_IMPORT
        self._completed: set[int] = set()
        self.setFixedHeight(72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

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

        w, h = self.width(), self.height()
        n = len(STAGE_LABELS)
        node_r = 14
        y_center = h // 2 - 8  # leave room for labels below

        # Evenly distribute nodes
        xs = [int(w * (i + 0.5) / n) for i in range(n)]

        # Colors
        col_complete = QColor("#10B981")  # green
        col_active = QColor("#3B82F6")  # blue
        col_pending = QColor("#4A4A4A")  # grey border, no fill
        col_line = QColor("#4A4A4A")

        pen = QPen(col_line, 2)
        painter.setPen(pen)

        # Connecting lines (behind nodes)
        for i in range(n - 1):
            x1, x2 = xs[i], xs[i + 1]
            if i in self._completed:
                painter.setPen(QPen(col_complete, 2))
            else:
                painter.setPen(QPen(col_line, 2))
            painter.drawLine(x1 + node_r, y_center, x2 - node_r, y_center)

        # Stage nodes and labels
        for i, label in enumerate(STAGE_LABELS):
            x = xs[i]

            if i in self._completed:
                painter.setBrush(col_complete)
                painter.setPen(QPen(col_complete, 2))
                painter.drawEllipse(QPoint(x, y_center), node_r, node_r)
                # Checkmark
                painter.setPen(QPen(QColor("white"), 2))
                painter.drawLine(x - 6, y_center, x - 2, y_center + 5)
                painter.drawLine(x - 2, y_center + 5, x + 6, y_center - 5)
            elif i == self._current_stage:
                painter.setBrush(col_active)
                painter.setPen(QPen(col_active, 2))
                painter.drawEllipse(QPoint(x, y_center), node_r, node_r)
                painter.setPen(QPen(QColor("white"), 1))
                f = QFont()
                f.setPointSize(8)
                f.setBold(True)
                painter.setFont(f)
                painter.drawText(x - 4, y_center + 4, str(i + 1))
            else:
                painter.setBrush(QColor("transparent"))
                painter.setPen(QPen(col_pending, 2))
                painter.drawEllipse(QPoint(x, y_center), node_r, node_r)
                painter.setPen(QPen(col_pending, 1))
                f = QFont()
                f.setPointSize(8)
                painter.setFont(f)
                painter.drawText(x - 4, y_center + 4, str(i + 1))

            # Label below node
            painter.setPen(
                QPen(
                    QColor("#E0E0E0") if i == self._current_stage else QColor("#808080"),
                    1,
                )
            )
            f = QFont()
            f.setPointSize(8)
            f.setBold(i == self._current_stage)
            painter.setFont(f)
            label_y = y_center + node_r + 16
            painter.drawText(x - 30, label_y, 60, 14, Qt.AlignmentFlag.AlignCenter, label)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        w = self.width()
        n = len(STAGE_LABELS)
        xs = [int(w * (i + 0.5) / n) for i in range(n)]
        for i, x in enumerate(xs):
            if abs(event.pos().x() - x) < 20:
                self.stage_clicked.emit(i)
                return


# ---------------------------------------------------------------------------
# Import Panel
# ---------------------------------------------------------------------------


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

        self._discovery_worker: DiscoveryWorker | None = None
        self.image_tree: QTreeWidget | None = None
        self.preview_widget: ImagePreviewWidget | None = None
        self.directory_combo: QComboBox | None = None
        self.show_analyzed_cb: QCheckBox | None = None
        self.tree_count_label: QLabel | None = None
        self.scan_progress_bar: QProgressBar | None = None
        self.scan_btn: QPushButton | None = None

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
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: file tree
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        tree_header = QHBoxLayout()
        self.tree_count_label = QLabel("0 images")
        self.tree_count_label.setStyleSheet(f"color: {self._c()['text_tertiary']}; font-size: 9pt;")
        tree_header.addStretch()
        tree_header.addWidget(self.tree_count_label)
        left_layout.addLayout(tree_header)

        self.image_tree = QTreeWidget()
        self.image_tree.setHeaderLabels(["Image", "Status"])
        tree_hdr = self.image_tree.header()
        assert tree_hdr is not None
        tree_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.image_tree.setColumnWidth(1, 90)
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

        splitter.addWidget(left)

        # Right: image preview
        c = self._c()
        preview_colors = {**c, "button_bg": c["bg_tertiary"], "button_hover": c["bg_hover"]}
        self.preview_widget = ImagePreviewWidget(
            toolbar_size=ToolbarSize.COMPACT,
            toolbar_position=ToolbarPosition.BOTTOM_CENTER,
            theme_colors=preview_colors,
            config_manager=self.config_manager,
            analysis_db=self.analysis_db,
        )
        splitter.addWidget(self.preview_widget)
        splitter.setSizes([380, 580])

        root.addWidget(splitter, stretch=1)

        # ── Footer navigation
        root.addWidget(self._divider())
        footer = QHBoxLayout()
        footer.addStretch()
        next_btn = QPushButton("Next: Analyze →")
        next_btn.setFixedHeight(30)
        next_btn.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.PRIMARY}; color: white; "
            f"border: none; border-radius: 4px; padding: 4px 16px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: {Colors.PRIMARY_HOVER}; }}"
        )
        next_btn.clicked.connect(self.next_requested)
        footer.addWidget(next_btn)
        root.addLayout(footer)

    def _post_init(self) -> None:
        self._populate_directory_combo()
        self._refresh()

    def _populate_directory_combo(self) -> None:
        if not self.directory_combo:
            return
        self.directory_combo.blockSignals(True)
        self.directory_combo.clear()
        self.directory_combo.addItem("All Directories")
        try:
            dirs = self.config_manager.get_directories()
            for d in dirs:
                self.directory_combo.addItem(d)
        except Exception:
            pass
        self.directory_combo.blockSignals(False)

    def _refresh(self) -> None:
        if not self.image_tree:
            return

        image_repo = ImageFilesRepository(self.analysis_db.connection)
        all_images: list[dict[str, Any]] = image_repo.get_all()

        # Filter
        dir_filter = (
            self.directory_combo.currentText() if self.directory_combo else "All Directories"
        )
        if dir_filter != "All Directories":
            all_images = [i for i in all_images if i["directory_path"] == dir_filter]

        show_analyzed = self.show_analyzed_cb.isChecked() if self.show_analyzed_cb else True
        if not show_analyzed:
            all_images = [i for i in all_images if i.get("status") != "analyzed"]

        all_images = [i for i in all_images if not i.get("is_ignored", False)]

        # Group by directory
        grouped: dict[str, list[dict[str, Any]]] = {}
        for img in all_images:
            d = img["directory_path"]
            grouped.setdefault(d, []).append(img)

        self.image_tree.clear()
        total = 0
        c = self._c()

        for dir_path, images in grouped.items():
            dir_item = QTreeWidgetItem([os.path.basename(dir_path), ""])
            dir_item.setForeground(0, QColor(c["text_secondary"]))
            dir_item.setFont(0, QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.image_tree.addTopLevelItem(dir_item)

            for img in images:
                status = img.get("status", "registered")
                file_item = QTreeWidgetItem([img["filename"], status])
                file_item.setData(0, Qt.ItemDataRole.UserRole, img["file_path"])

                status_color = {
                    "analyzed": "#10B981",
                    "error": "#EF4444",
                    "registered": c["text_tertiary"],
                }.get(status, c["text_tertiary"])
                file_item.setForeground(1, QColor(status_color))

                dir_item.addChild(file_item)
                total += 1

            dir_item.setExpanded(True)

        if self.tree_count_label:
            self.tree_count_label.setText(f"{total} image{'s' if total != 1 else ''}")

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
        if paths:
            from PyQt6.QtGui import QPixmap

            pixmap = QPixmap(paths[0])
            if not pixmap.isNull():
                self.preview_widget.set_pixmap(pixmap, apply_fit="window", file_path=paths[0])

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
        image_repo = ImageFilesRepository(self.analysis_db.connection)
        for p in paths:
            image_repo.mark_deleted(p)
        self._refresh()

    def _on_ignore(self) -> None:
        paths = self._selected_paths()
        if not paths:
            return
        image_repo = ImageFilesRepository(self.analysis_db.connection)
        for p in paths:
            image_repo.set_ignored(p, ignored=True)
        self._refresh()

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        return line


# ---------------------------------------------------------------------------
# Analyze Panel
# ---------------------------------------------------------------------------


class AnalyzePanel(QWidget):
    """
    Stage 2: Analyze — run LLM metadata extraction.

    Drives AnalysisWorker from a focused control surface: start/stop,
    live progress bar, per-file status table, and running stats.
    """

    back_requested = pyqtSignal()
    next_requested = pyqtSignal()

    def __init__(
        self,
        config_manager: ConfigManager,
        analysis_db: AnalysisDB,
        dark_mode: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config_manager = config_manager
        self.analysis_db = analysis_db
        self.dark_mode = dark_mode

        self._queue = AnalysisQueue()
        self._worker = AnalysisWorker(self.config_manager, self._queue)
        self._stats: dict[str, int] = {
            "analyzed": 0,
            "cached": 0,
            "errors": 0,
            "total_files": 0,
        }

        # widgets populated in _build_ui
        self.start_btn: QPushButton | None = None
        self.stop_btn: QPushButton | None = None
        self.abort_btn: QPushButton | None = None
        self.status_lbl: QLabel | None = None
        self.progress_bar: QProgressBar | None = None
        self.stats_lbl: QLabel | None = None
        self.file_table: QTableWidget | None = None

        self._build_ui()
        self._connect_worker()
        QTimer.singleShot(0, self.refresh)

    def _c(self) -> dict[str, str]:
        return ThemeManager.get_colors(self.dark_mode)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 8)
        root.setSpacing(8)

        # ── Section title
        title = QLabel("Analyze — Extract metadata with LLM")
        title.setStyleSheet(
            f"font-size: 11pt; font-weight: 600; color: {self._c()['text_primary']};"
        )
        root.addWidget(title)

        # ── Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.status_lbl = QLabel("Ready to analyze.")
        self.status_lbl.setStyleSheet(f"font-size: 9pt; color: {self._c()['text_secondary']};")
        toolbar.addWidget(self.status_lbl)
        toolbar.addStretch()

        self.start_btn = QPushButton("▶  Start Analysis")
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #10B981; color: white; font-weight: 600; "
            "padding: 6px 16px; border: none; border-radius: 4px; }"
            "QPushButton:hover { background-color: #059669; }"
            "QPushButton:pressed { background-color: #047857; }"
        )
        self.start_btn.clicked.connect(self._on_start)
        toolbar.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏸  Stop")
        is_dark = self.dark_mode
        stop_bg = "#D97706" if is_dark else "#F59E0B"
        stop_hover = "#B45309" if is_dark else "#D97706"
        self.stop_btn.setStyleSheet(
            f"QPushButton {{ background-color: {stop_bg}; color: #1F2937; font-weight: 600; "
            f"padding: 6px 16px; border: none; border-radius: 4px; }}"
            f"QPushButton:hover {{ background-color: {stop_hover}; }}"
        )
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setVisible(False)
        toolbar.addWidget(self.stop_btn)

        self.abort_btn = QPushButton("⏹  Abort")
        abort_bg = "#991B1B" if is_dark else "#EF4444"
        abort_hover = "#7F1D1D" if is_dark else "#DC2626"
        abort_text = "#E0E0E0" if is_dark else "white"
        self.abort_btn.setStyleSheet(
            f"QPushButton {{ background-color: {abort_bg}; color: {abort_text}; "
            f"font-weight: 600; padding: 6px 16px; border: none; border-radius: 4px; }}"
            f"QPushButton:hover {{ background-color: {abort_hover}; }}"
        )
        self.abort_btn.clicked.connect(self._on_abort)
        self.abort_btn.setVisible(False)
        toolbar.addWidget(self.abort_btn)

        root.addLayout(toolbar)

        # ── Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        root.addWidget(self.progress_bar)

        # ── Stats row
        self.stats_lbl = QLabel("—")
        self.stats_lbl.setStyleSheet(f"font-size: 9pt; color: {self._c()['text_tertiary']};")
        root.addWidget(self.stats_lbl)

        # ── Per-file table
        self.file_table = QTableWidget(0, 3)
        self.file_table.setHorizontalHeaderLabels(["File", "Status", "Info"])
        tbl_hdr = self.file_table.horizontalHeader()
        assert tbl_hdr is not None
        tbl_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tbl_hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.file_table.setColumnWidth(1, 100)
        tbl_hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.file_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.file_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        v_hdr = self.file_table.verticalHeader()
        assert v_hdr is not None
        v_hdr.setVisible(False)
        root.addWidget(self.file_table, stretch=1)

        # ── Footer navigation
        root.addWidget(self._divider())
        footer = QHBoxLayout()

        back_btn = QPushButton("← Back")
        back_btn.setFixedHeight(30)
        back_btn.clicked.connect(self.back_requested)
        footer.addWidget(back_btn)

        footer.addStretch()

        self._next_btn = QPushButton("Next: Bundle →")
        self._next_btn.setFixedHeight(30)
        self._next_btn.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.PRIMARY}; color: white; "
            f"border: none; border-radius: 4px; padding: 4px 16px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: {Colors.PRIMARY_HOVER}; }}"
        )
        self._next_btn.clicked.connect(self.next_requested)
        footer.addWidget(self._next_btn)

        root.addLayout(footer)

    def refresh(self) -> None:
        """Load (or reload) current file statuses from the database."""
        if not self.file_table:
            return

        self.file_table.setRowCount(0)

        try:
            image_repo = ImageFilesRepository(self.analysis_db.connection)
            all_images = image_repo.get_all()
            # Exclude deleted / ignored
            all_images = [
                img
                for img in all_images
                if img.get("status") != "deleted" and not img.get("is_ignored", False)
            ]
        except Exception as e:
            _get_logger().warning(f"[AnalyzePanel] could not load images: {e}")
            return

        c = self._c()
        for img in all_images:
            status = img.get("status", "registered")
            row = self.file_table.rowCount()
            self.file_table.insertRow(row)

            name_item = QTableWidgetItem(img["filename"])
            name_item.setData(Qt.ItemDataRole.UserRole, img["file_path"])
            name_item.setToolTip(img["file_path"])
            self.file_table.setItem(row, 0, name_item)

            status_item = QTableWidgetItem(status)
            status_color = {
                "analyzed": "#10B981",
                "error": "#EF4444",
                "cached": "#3B82F6",
                "registered": c["text_tertiary"],
            }.get(status, c["text_tertiary"])
            status_item.setForeground(QColor(status_color))
            self.file_table.setItem(row, 1, status_item)

            self.file_table.setItem(row, 2, QTableWidgetItem(""))

        total = len(all_images)
        analyzed = sum(1 for img in all_images if img.get("status") == "analyzed")
        if self.stats_lbl:
            self.stats_lbl.setText(
                f"Total: {total}  ·  Analyzed: {analyzed}  " f"·  Pending: {total - analyzed}"
            )

    def _connect_worker(self) -> None:
        ct = Qt.ConnectionType.QueuedConnection
        self._worker.job_started.connect(self._on_job_started, ct)  # type: ignore[call-arg]
        self._worker.progress.connect(self._on_progress, ct)  # type: ignore[call-arg]
        self._worker.file_status_changed.connect(self._on_file_status_changed, ct)  # type: ignore[call-arg]
        self._worker.job_finished.connect(self._on_job_finished, ct)  # type: ignore[call-arg]
        self._worker.error.connect(self._on_worker_error, ct)  # type: ignore[call-arg]
        self._worker.queue_empty.connect(self._on_queue_empty, ct)  # type: ignore[call-arg]

    def _on_start(self) -> None:
        job = AnalysisJob.create(
            job_type=JobType.SCAN_ALL,
            priority=JobPriority.NORMAL,
        )
        self._queue.enqueue(job)

        if not self._worker.isRunning():
            self._worker.start()

        if self.start_btn:
            self.start_btn.setVisible(False)
        if self.stop_btn:
            self.stop_btn.setVisible(True)
        if self.abort_btn:
            self.abort_btn.setVisible(True)
        if self.status_lbl:
            self.status_lbl.setText("Starting analysis…")

    def _on_stop(self) -> None:
        self._worker.stop()
        if self.stop_btn:
            self.stop_btn.setVisible(False)
        if self.abort_btn:
            self.abort_btn.setVisible(False)
        if self.start_btn:
            self.start_btn.setVisible(True)
        if self.status_lbl:
            self.status_lbl.setText("Stopping…")

    def _on_abort(self) -> None:
        self._worker.cancel_current_job()
        self._on_stop()

    def _on_job_started(self, job_id: str, description: str) -> None:
        if self.status_lbl:
            self.status_lbl.setText(description)

    def _on_progress(self, status: str, current: int, total: int) -> None:
        if self.progress_bar:
            if total > 0:
                self.progress_bar.setRange(0, total)
                self.progress_bar.setValue(current)
                pct = int(current / total * 100)
                self.progress_bar.setFormat(f"{pct}% — {status}")
            else:
                self.progress_bar.setRange(0, 0)
        if self.status_lbl:
            self.status_lbl.setText(status)

    def _on_file_status_changed(self, file_path: str, new_status: str) -> None:
        if not self.file_table:
            return
        filename = os.path.basename(file_path)

        # Update existing row or add new one
        for row in range(self.file_table.rowCount()):
            item = self.file_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == file_path:
                status_item = self.file_table.item(row, 1)
                if status_item:
                    status_item.setText(new_status)
                    status_color = {
                        "analyzed": "#10B981",
                        "error": "#EF4444",
                        "cached": "#3B82F6",
                    }.get(new_status, self._c()["text_secondary"])
                    status_item.setForeground(QColor(status_color))
                return

        row = self.file_table.rowCount()
        self.file_table.insertRow(row)

        name_item = QTableWidgetItem(filename)
        name_item.setData(Qt.ItemDataRole.UserRole, file_path)
        name_item.setToolTip(file_path)
        self.file_table.setItem(row, 0, name_item)

        status_item = QTableWidgetItem(new_status)
        status_color = {
            "analyzed": "#10B981",
            "error": "#EF4444",
            "cached": "#3B82F6",
        }.get(new_status, self._c()["text_secondary"])
        status_item.setForeground(QColor(status_color))
        self.file_table.setItem(row, 1, status_item)

        self.file_table.setItem(row, 2, QTableWidgetItem(""))
        self.file_table.scrollToBottom()

    def _on_job_finished(self, job_id: str, stats: dict) -> None:
        self._stats["analyzed"] += stats.get("analyzed", 0)
        self._stats["cached"] += stats.get("cached", 0)
        self._stats["errors"] += stats.get("errors", 0)
        self._stats["total_files"] += stats.get("total_files", 0)
        self._update_stats_label()

        if self.progress_bar:
            total = stats.get("total_files", 0)
            if total > 0:
                self.progress_bar.setRange(0, total)
                self.progress_bar.setValue(total)
                self.progress_bar.setFormat("100% — Complete")

    def _on_worker_error(self, job_id: str, error_msg: str) -> None:
        if self.status_lbl:
            self.status_lbl.setText(f"Error: {error_msg[:80]}")
        _get_logger().error(f"[Pipeline AnalyzePanel] worker error: {error_msg}")

    def _on_queue_empty(self) -> None:
        if self.stop_btn:
            self.stop_btn.setVisible(False)
        if self.abort_btn:
            self.abort_btn.setVisible(False)
        if self.start_btn:
            self.start_btn.setVisible(True)
        if self.status_lbl:
            self.status_lbl.setText("Analysis complete.")
        if self.progress_bar:
            self.progress_bar.setFormat("Complete")

    def _update_stats_label(self) -> None:
        if not self.stats_lbl:
            return
        s = self._stats
        self.stats_lbl.setText(
            f"Analyzed: {s['analyzed']}  ·  Cached: {s['cached']}  "
            f"·  Errors: {s['errors']}  ·  Total: {s['total_files']}"
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2000)
        super().closeEvent(event)

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        return line


# ---------------------------------------------------------------------------
# Bundle Panel
# ---------------------------------------------------------------------------


class BundlePanel(QWidget):
    """
    Stage 3: Bundle — review AI bundle suggestions and approve PDFs.

    Shows available bundles and opens GuidedBundleWorkflow as a dialog.
    """

    back_requested = pyqtSignal()
    next_requested = pyqtSignal()
    bundles_completed = pyqtSignal(dict)  # workflow stats

    def __init__(
        self,
        analysis_db: AnalysisDB,
        metadata_db: MetadataDB,
        config_manager: ConfigManager,
        dark_mode: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.analysis_db = analysis_db
        self.metadata_db = metadata_db
        self.config_manager = config_manager
        self.dark_mode = dark_mode
        self._bundling_service = BundlingService(self.analysis_db)
        self._workflow_stats: dict = {}

        self.bundle_count_lbl: QLabel | None = None
        self.accepted_lbl: QLabel | None = None
        self.review_btn: QPushButton | None = None

        self._build_ui()

    def _c(self) -> dict[str, str]:
        return ThemeManager.get_colors(self.dark_mode)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 8)
        root.setSpacing(12)

        title = QLabel("Bundle — Review AI suggestions and create PDFs")
        title.setStyleSheet(
            f"font-size: 11pt; font-weight: 600; color: {self._c()['text_primary']};"
        )
        root.addWidget(title)

        desc = QLabel(
            "The AI has grouped your analyzed images into document bundles. "
            "Review each bundle, adjust metadata or page order, then accept to produce a PDF."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size: 9pt; color: {self._c()['text_secondary']};")
        root.addWidget(desc)

        # Stats area
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.Shape.StyledPanel)
        c = self._c()
        stats_frame.setStyleSheet(
            f"QFrame {{ background-color: {c['bg_secondary']}; "
            f"border: 1px solid {c['border']}; border-radius: 4px; }}"
        )
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setContentsMargins(16, 12, 16, 12)

        self.bundle_count_lbl = QLabel("Loading bundle count…")
        self.bundle_count_lbl.setStyleSheet(
            f"font-size: 14pt; font-weight: 700; color: {c['text_primary']};"
        )
        stats_layout.addWidget(self.bundle_count_lbl)

        self.accepted_lbl = QLabel("")
        self.accepted_lbl.setStyleSheet(f"font-size: 9pt; color: {c['text_secondary']};")
        stats_layout.addWidget(self.accepted_lbl)

        root.addWidget(stats_frame)

        # Review button
        self.review_btn = QPushButton("Review Bundles →")
        self.review_btn.setFixedHeight(42)
        self.review_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.review_btn.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.PRIMARY}; color: white; "
            f"font-size: 11pt; font-weight: 600; border: none; border-radius: 4px; }}"
            f"QPushButton:hover {{ background-color: {Colors.PRIMARY_HOVER}; }}"
            f"QPushButton:pressed {{ background-color: #1D4ED8; }}"
        )
        self.review_btn.clicked.connect(self._on_review)
        root.addWidget(self.review_btn)

        root.addStretch()

        # Footer
        root.addWidget(self._divider())
        footer = QHBoxLayout()

        back_btn = QPushButton("← Back")
        back_btn.setFixedHeight(30)
        back_btn.clicked.connect(self.back_requested)
        footer.addWidget(back_btn)

        footer.addStretch()

        self._next_btn = QPushButton("Next: Export →")
        self._next_btn.setFixedHeight(30)
        self._next_btn.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.PRIMARY}; color: white; "
            f"border: none; border-radius: 4px; padding: 4px 16px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: {Colors.PRIMARY_HOVER}; }}"
        )
        self._next_btn.clicked.connect(self.next_requested)
        footer.addWidget(self._next_btn)

        root.addLayout(footer)

    def refresh_bundle_count(self) -> None:
        """Update the displayed bundle count from the database."""
        try:
            bundles = self._bundling_service.generate_bundle_recommendations()
            n = len(bundles) if bundles else 0
            if self.bundle_count_lbl:
                label = f"{n} bundle{'s' if n != 1 else ''} available"
                self.bundle_count_lbl.setText(label)
        except Exception as e:
            _get_logger().warning(f"[Pipeline BundlePanel] could not count bundles: {e}")
            if self.bundle_count_lbl:
                self.bundle_count_lbl.setText("Bundle count unavailable")

    def _on_review(self) -> None:
        from ui.guided_bundle_workflow import GuidedBundleWorkflow

        try:
            bundles = self._bundling_service.generate_bundle_recommendations()
        except Exception as e:
            show_warning(self, "Bundle Error", f"Could not load bundles:\n{e}")
            return

        if not bundles:
            show_information(
                self,
                "No Bundles",
                "No bundle suggestions found. Run analysis first or check your source directories.",
            )
            return

        workflow_bundles = self._prepare_bundles(bundles)

        workflow = GuidedBundleWorkflow(
            bundles=workflow_bundles,
            start_index=0,
            prototype_mode=False,
            analysis_db=self.analysis_db,
            metadata_db=self.metadata_db,
            config_manager=self.config_manager,
            parent=self,
        )
        workflow.workflow_completed.connect(self._on_workflow_completed)
        workflow.exec()

    def _on_workflow_completed(self, stats: dict) -> None:
        self._workflow_stats = stats
        accepted = stats.get("accepted", 0)
        rejected = stats.get("rejected", 0)
        if self.accepted_lbl:
            self.accepted_lbl.setText(f"Accepted: {accepted}  ·  Rejected: {rejected}")
        self.bundles_completed.emit(stats)

    def _prepare_bundles(self, bundles: list[dict]) -> list[dict]:
        workflow_bundles = []
        for bundle in bundles:
            analyses = bundle.get("analyses", [])
            formatted = []
            for analysis in analyses:
                formatted.append(
                    {
                        "document_type": analysis.get("document_type"),
                        "company": analysis.get("company"),
                        "document_date": analysis.get("document_date"),
                        "page_number": analysis.get("page_number"),
                        "total_pages": analysis.get("total_pages"),
                        "rotation_needed": analysis.get("rotation_needed", "none"),
                        "confidence_score": analysis.get("confidence_score", 0.0),
                        "tax_related": analysis.get("tax_related", False),
                    }
                )
            workflow_bundles.append(
                {
                    "bundle_id": bundle.get("id"),
                    "company": bundle.get("company", ""),
                    "document_type": bundle.get("document_type", ""),
                    "document_date": bundle.get("document_date", ""),
                    "confidence_score": bundle.get("confidence_score", 0.0),
                    "file_paths": bundle.get("file_paths", []),
                    "analyses": formatted,
                }
            )
        return workflow_bundles

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        return line


# ---------------------------------------------------------------------------
# Export Panel
# ---------------------------------------------------------------------------


class ExportPanel(QWidget):
    """
    Stage 4: Export — confirm completion.

    Displays a session summary: how many PDFs were accepted and where
    they were written. Offers to open the output directory.
    """

    back_requested = pyqtSignal()

    def __init__(
        self,
        config_manager: ConfigManager,
        dark_mode: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config_manager = config_manager
        self.dark_mode = dark_mode
        self._stats: dict = {}

        self.summary_lbl: QLabel | None = None
        self._build_ui()

    def _c(self) -> dict[str, str]:
        return ThemeManager.get_colors(self.dark_mode)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 8)
        root.setSpacing(12)

        title = QLabel("Export — Session complete")
        title.setStyleSheet(
            f"font-size: 11pt; font-weight: 600; color: {self._c()['text_primary']};"
        )
        root.addWidget(title)

        self.summary_lbl = QLabel(
            "No bundles have been accepted in this session yet.\n"
            "Go back to Bundle to review suggestions."
        )
        self.summary_lbl.setWordWrap(True)
        self.summary_lbl.setStyleSheet(f"font-size: 10pt; color: {self._c()['text_secondary']};")
        root.addWidget(self.summary_lbl)

        # Open output directory
        open_dir_btn = QPushButton("Open Output Directory")
        open_dir_btn.setFixedHeight(32)
        open_dir_btn.setFixedWidth(200)
        open_dir_btn.clicked.connect(self._open_output_dir)
        root.addWidget(open_dir_btn)

        root.addStretch()

        root.addWidget(self._divider())
        footer = QHBoxLayout()

        back_btn = QPushButton("← Back to Bundle")
        back_btn.setFixedHeight(30)
        back_btn.clicked.connect(self.back_requested)
        footer.addWidget(back_btn)

        footer.addStretch()
        root.addLayout(footer)

    def update_stats(self, stats: dict) -> None:
        self._stats = stats
        accepted = stats.get("accepted", 0)
        rejected = stats.get("rejected", 0)

        import contextlib

        output_dir = ""
        with contextlib.suppress(Exception):
            output_dir = str(self.config_manager.get_setting("OutputDirectory", "path", ""))

        lines = [
            f"PDFs accepted: {accepted}",
            f"Bundles rejected: {rejected}",
        ]
        if output_dir:
            lines.append(f"\nOutput directory:\n{output_dir}")

        if self.summary_lbl:
            self.summary_lbl.setText("\n".join(lines))

    def _open_output_dir(self) -> None:
        import subprocess

        try:
            output_dir = str(self.config_manager.get_setting("OutputDirectory", "path", ""))
            if output_dir and os.path.isdir(output_dir):
                subprocess.Popen(["explorer", output_dir])
            else:
                show_warning(self, "Directory Not Found", "Output directory is not configured.")
        except Exception as e:
            show_warning(self, "Error", f"Could not open directory:\n{e}")

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        return line


# ---------------------------------------------------------------------------
# Document Pipeline Window
# ---------------------------------------------------------------------------


class DocumentPipelineWindow(QMainWindow):
    """
    Unified Import → Analyze → Bundle → Export window.

    Owns shared database instances and coordinates the four stage panels
    through a QStackedWidget, driven by the PipelineHeaderWidget rail.
    """

    def __init__(
        self,
        analysis_db: AnalysisDB | None = None,
        metadata_db: MetadataDB | None = None,
        config_manager: ConfigManager | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._owns_analysis_db = analysis_db is None
        self._owns_metadata_db = metadata_db is None
        self.analysis_db = analysis_db or AnalysisDB()
        self.metadata_db = metadata_db or MetadataDB()
        self.config_manager = config_manager or ConfigManager()

        theme = self.config_manager.get_setting("Theme", "theme", "dark")
        self.dark_mode = theme == "dark"

        self._current_stage = STAGE_IMPORT
        self._completed_stages: set[int] = set()

        self._build_ui()
        self._apply_theme()

    def _c(self) -> dict[str, str]:
        return ThemeManager.get_colors(self.dark_mode)

    def _build_ui(self) -> None:
        self.setWindowTitle("Document Pipeline")
        self.resize(1200, 800)
        self.setMinimumSize(900, 640)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Pipeline header rail
        self.header = PipelineHeaderWidget()
        self.header.set_stage(STAGE_IMPORT)
        self.header.stage_clicked.connect(self._go_to_stage)
        root.addWidget(self.header)

        # Thin separator under header
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        root.addWidget(sep)

        # ── Stage panels
        self.stack = QStackedWidget()

        self.import_panel = ImportPanel(
            analysis_db=self.analysis_db,
            config_manager=self.config_manager,
            dark_mode=self.dark_mode,
        )
        self.import_panel.next_requested.connect(lambda: self._go_to_stage(STAGE_ANALYZE))

        self.analyze_panel = AnalyzePanel(
            config_manager=self.config_manager,
            analysis_db=self.analysis_db,
            dark_mode=self.dark_mode,
        )
        self.analyze_panel.back_requested.connect(lambda: self._go_to_stage(STAGE_IMPORT))
        self.analyze_panel.next_requested.connect(lambda: self._go_to_stage(STAGE_BUNDLE))

        self.bundle_panel = BundlePanel(
            analysis_db=self.analysis_db,
            metadata_db=self.metadata_db,
            config_manager=self.config_manager,
            dark_mode=self.dark_mode,
        )
        self.bundle_panel.back_requested.connect(lambda: self._go_to_stage(STAGE_ANALYZE))
        self.bundle_panel.next_requested.connect(lambda: self._go_to_stage(STAGE_EXPORT))
        self.bundle_panel.bundles_completed.connect(self._on_bundles_completed)

        self.export_panel = ExportPanel(
            config_manager=self.config_manager,
            dark_mode=self.dark_mode,
        )
        self.export_panel.back_requested.connect(lambda: self._go_to_stage(STAGE_BUNDLE))

        self.stack.addWidget(self.import_panel)
        self.stack.addWidget(self.analyze_panel)
        self.stack.addWidget(self.bundle_panel)
        self.stack.addWidget(self.export_panel)

        root.addWidget(self.stack, stretch=1)

    def _apply_theme(self) -> None:
        c = self._c()
        self.setStyleSheet(ThemeManager.get_stylesheet(self.dark_mode))
        self.header.setStyleSheet(f"background-color: {c['bg_secondary']};")

    def _go_to_stage(self, stage: int) -> None:
        # Mark the current stage complete when moving forward
        if stage > self._current_stage:
            self._completed_stages.add(self._current_stage)

        self._current_stage = stage
        self.stack.setCurrentIndex(stage)
        self.header.set_stage(stage, self._completed_stages)

        # Trigger stage-specific refresh
        if stage == STAGE_IMPORT:
            self.import_panel._refresh()
        elif stage == STAGE_ANALYZE:
            self.analyze_panel.refresh()
        elif stage == STAGE_BUNDLE:
            self.bundle_panel.refresh_bundle_count()

    def _on_bundles_completed(self, stats: dict) -> None:
        self.export_panel.update_stats(stats)

    def closeEvent(self, event) -> None:  # noqa: N802
        # Gracefully stop the analysis worker before closing
        if hasattr(self, "analyze_panel") and self.analyze_panel._worker.isRunning():
            self.analyze_panel._worker.stop()
            self.analyze_panel._worker.wait(3000)

        if self._owns_analysis_db:
            self.analysis_db.close()
        if self._owns_metadata_db:
            self.metadata_db.close()

        super().closeEvent(event)
