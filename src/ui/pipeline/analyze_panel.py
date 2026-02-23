"""
Stage 2: Analyze panel — run LLM metadata extraction.
"""

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from config.config_manager import ConfigManager
from db.analysis_db import AnalysisDB
from db.metadata_db import MetadataDB
from services.analysis_queue import AnalysisJob, AnalysisQueue, JobPriority, JobType
from services.analysis_worker import AnalysisWorker
from services.logging_service import get_logger
from ui.image_preview_widget import ImagePreviewWidget, ToolbarPosition, ToolbarSize
from ui.pipeline.stages import _LINK_STYLE
from ui.theme_manager import ThemeManager

if TYPE_CHECKING:
    from ui.file_details import FileDetailsGrid


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
        metadata_db: MetadataDB | None,
        dark_mode: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config_manager = config_manager
        self.analysis_db = analysis_db
        self.metadata_db = metadata_db
        self.dark_mode = dark_mode

        self._queue = AnalysisQueue()
        self._worker = AnalysisWorker(self.config_manager, self._queue)
        self._stats: dict[str, int] = {
            "analyzed": 0,
            "cached": 0,
            "errors": 0,
            "total_files": 0,
        }

        # Debounce timer: collapses rapid file-status-changed signals into a
        # single refresh() call, preventing one DB reload per file during analysis.
        self._refresh_debounce_timer = QTimer(self)
        self._refresh_debounce_timer.setSingleShot(True)
        self._refresh_debounce_timer.setInterval(500)
        self._refresh_debounce_timer.timeout.connect(lambda: self.refresh())

        # widgets populated in _build_ui
        self.start_btn: QPushButton | None = None
        self.stop_btn: QPushButton | None = None
        self.abort_btn: QPushButton | None = None
        self.status_lbl: QLabel | None = None
        self.progress_bar: QProgressBar | None = None
        self.stats_lbl: QLabel | None = None
        self.file_grid: FileDetailsGrid | None = None
        self.image_preview: ImagePreviewWidget | None = None
        self._content_splitter: QSplitter | None = None
        self._select_all_btn: QPushButton | None = None
        self._deselect_btn: QPushButton | None = None

        # Analytics section widgets (populated in _build_analytics_section)
        self._analytics_section: QWidget | None = None
        self._avg_conf_label: QLabel | None = None
        self._error_rate_label: QLabel | None = None
        self._completeness_bars: dict = {}
        self._docs_created_label: QLabel | None = None
        self._pages_archived_label: QLabel | None = None
        self._avg_pages_label: QLabel | None = None
        self._bundle_acceptance_label: QLabel | None = None
        self._type_dist_container: QWidget | None = None
        self._company_dist_container: QWidget | None = None

        self._build_ui()
        self._connect_worker()
        QTimer.singleShot(0, self.refresh)

    @property
    def is_dark_mode(self) -> bool:
        """Alias for dark_mode — FileDetailsGrid reads this from its parent widget."""
        return self.dark_mode

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

        # ── Progress bar (hidden until analysis is running)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

        # ── Stats row (stats label left, selection actions right)
        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)

        self.stats_lbl = QLabel("—")
        self.stats_lbl.setStyleSheet(f"font-size: 9pt; color: {self._c()['text_tertiary']};")
        stats_row.addWidget(self.stats_lbl)
        stats_row.addStretch()

        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.setFlat(True)
        self._select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._select_all_btn.setStyleSheet(_LINK_STYLE.format(self._c().get("accent", "#3B82F6")))
        self._select_all_btn.clicked.connect(self._on_select_all)
        stats_row.addWidget(self._select_all_btn)

        self._deselect_btn = QPushButton("Deselect")
        self._deselect_btn.setFlat(True)
        self._deselect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._deselect_btn.setStyleSheet(
            _LINK_STYLE.format(self._c().get("text_secondary", "#9CA3AF"))
        )
        self._deselect_btn.setVisible(False)
        self._deselect_btn.clicked.connect(self._on_deselect)
        stats_row.addWidget(self._deselect_btn)

        root.addLayout(stats_row)

        # ── Analytics section (collapsible, collapsed by default)
        self._analytics_section = self._build_analytics_section()
        root.addWidget(self._analytics_section)

        # ── Content area: file grid (left) + image preview (right)
        from ui.file_details import FileDetailsGrid

        self.file_grid = FileDetailsGrid(
            parent=self,
            analysis_db=self.analysis_db,
            metadata_db=self.metadata_db,
        )

        c = self._c()
        self.image_preview = ImagePreviewWidget(
            parent=self,
            toolbar_size=ToolbarSize.COMPACT,
            toolbar_position=ToolbarPosition.BOTTOM_CENTER,
            theme_colors={**c, "button_bg": c["bg_tertiary"], "button_hover": c["bg_hover"]},
            config_manager=self.config_manager,
            analysis_db=self.analysis_db,
        )
        self.image_preview.setMinimumWidth(180)

        self._content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._content_splitter.addWidget(self.file_grid)
        self._content_splitter.addWidget(self.image_preview)
        self._content_splitter.setSizes([680, 380])
        self._content_splitter.setCollapsible(0, False)
        self._content_splitter.setCollapsible(1, True)
        self.image_preview.setVisible(False)
        root.addWidget(self._content_splitter, stretch=1)

        # ── Footer navigation

    def _build_analytics_section(self) -> QWidget:
        """Build a collapsible analytics section with quality and document insights."""
        from ui.collection_status_helpers import (
            create_collapsible_section,
            create_company_insights_widget,
            create_document_insights_widget_split,
            create_quality_metrics_widget,
        )

        # create_collapsible_section uses 'tab_hover_bg' which is not in ThemeManager;
        # map it to bg_hover so the helper receives a complete palette.
        c = {**self._c(), "tab_hover_bg": self._c().get("bg_hover", "#E5E7EB")}

        # Quality metrics panel
        quality_widget, avg_conf_lbl, error_rate_lbl, completeness_bars = (
            create_quality_metrics_widget(c)
        )
        self._avg_conf_label = avg_conf_lbl
        self._error_rate_label = error_rate_lbl
        self._completeness_bars = completeness_bars

        # Document insights panel (without company distribution)
        (
            doc_widget,
            docs_created_lbl,
            pages_archived_lbl,
            avg_pages_lbl,
            bundle_acceptance_lbl,
            type_dist_container,
        ) = create_document_insights_widget_split(c)
        self._docs_created_label = docs_created_lbl
        self._pages_archived_label = pages_archived_lbl
        self._avg_pages_label = avg_pages_lbl
        self._bundle_acceptance_label = bundle_acceptance_lbl
        self._type_dist_container = type_dist_container

        # Company insights panel
        company_widget, company_dist_container = create_company_insights_widget(c)
        self._company_dist_container = company_dist_container

        # Combine into a horizontal row inside a scroll area
        analytics_row = QWidget()
        analytics_row.setStyleSheet("background-color: transparent;")
        row_layout = QHBoxLayout(analytics_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(quality_widget, stretch=1)
        row_layout.addWidget(doc_widget, stretch=1)
        row_layout.addWidget(company_widget, stretch=1)

        scroll = QScrollArea()
        scroll.setWidget(analytics_row)
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(220)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(scroll.Shape.NoFrame)

        section = create_collapsible_section(c, "Analytics", scroll, initially_expanded=False)
        return section

    def _refresh_analytics_section(self) -> None:
        """Recompute analytics from the DB and update labels in the analytics section."""
        if not self._avg_conf_label:
            return
        try:
            raw_data = self.analysis_db.get_analyzed_pages()
        except Exception as e:
            get_logger().warning(f"[AnalyzePanel] analytics refresh failed: {e}")
            return

        analyzed = [r for r in raw_data if r.get("analysis_id") is not None]
        total = len(raw_data)
        n_analyzed = len(analyzed)
        n_errors = sum(1 for r in raw_data if r.get("status") == "error")

        # Quality metrics
        confidences = [
            r["confidence_score"] for r in analyzed if r.get("confidence_score") is not None
        ]
        avg_conf = (sum(confidences) / len(confidences) * 100) if confidences else None
        if self._avg_conf_label:
            self._avg_conf_label.setText(
                f"Average Confidence: {avg_conf:.1f}%"
                if avg_conf is not None
                else "Average Confidence: —"
            )

        error_rate = (n_errors / total * 100) if total > 0 else 0.0
        if self._error_rate_label:
            self._error_rate_label.setText(f"Error Rate: {error_rate:.1f}%")

        # Metadata completeness bars
        fields = ["company", "document_type", "document_date", "page_number"]
        for field in fields:
            filled = sum(1 for r in analyzed if r.get(field))
            pct = int(filled / n_analyzed * 100) if n_analyzed > 0 else 0
            bar_widget = self._completeness_bars.get(field)
            if bar_widget:
                bar_widget.label.setText(f"{field.replace('_', ' ').title()}: {pct}%")
                bar_widget.bar.setValue(pct)

        # Document insights
        if self._docs_created_label:
            self._docs_created_label.setText(f"Documents Created: {n_analyzed}")
        if self._pages_archived_label:
            self._pages_archived_label.setText(f"Pages Archived: {n_analyzed}")

        if self._avg_pages_label:
            companies: dict[str, int] = {}
            for r in analyzed:
                comp = r.get("company") or "Unknown"
                companies[comp] = companies.get(comp, 0) + 1
            unique_docs = len(companies)
            avg_pgs = (n_analyzed / unique_docs) if unique_docs > 0 else 0
            self._avg_pages_label.setText(
                f"Avg Pages per Document: {avg_pgs:.1f}"
                if unique_docs > 0
                else "Avg Pages per Document: —"
            )

        if self._bundle_acceptance_label:
            self._bundle_acceptance_label.setText("Bundle Acceptance Rate: —")

        # Type distribution
        # Note: `.layout` is monkey-patched in create_document_insights_widget_split
        # to hold the QVBoxLayout instance directly (not the layout() method).
        if self._type_dist_container:
            from PyQt6.QtWidgets import QVBoxLayout

            from ui.collection_status_helpers import create_distribution_bar

            type_layout: QVBoxLayout = self._type_dist_container.layout  # type: ignore[assignment]
            while type_layout.count():
                item = type_layout.takeAt(0)
                if item:
                    w = item.widget()
                    if w:
                        w.deleteLater()
            type_counts: dict[str, int] = {}
            for r in analyzed:
                dt = r.get("document_type") or "Unknown"
                type_counts[dt] = type_counts.get(dt, 0) + 1
            for doc_type, count in sorted(type_counts.items(), key=lambda x: -x[1])[:5]:
                bar = create_distribution_bar(self._c(), doc_type, count, n_analyzed)
                type_layout.addWidget(bar)

        # Company distribution
        if self._company_dist_container:
            from PyQt6.QtWidgets import QVBoxLayout

            from ui.collection_status_helpers import create_distribution_bar

            comp_layout: QVBoxLayout = self._company_dist_container.layout  # type: ignore[assignment]
            while comp_layout.count():
                item = comp_layout.takeAt(0)
                if item:
                    w = item.widget()
                    if w:
                        w.deleteLater()
            comp_counts: dict[str, int] = {}
            for r in analyzed:
                comp = r.get("company") or "Unknown"
                comp_counts[comp] = comp_counts.get(comp, 0) + 1
            for company, count in sorted(comp_counts.items(), key=lambda x: -x[1])[:5]:
                bar = create_distribution_bar(self._c(), company, count, n_analyzed)
                comp_layout.addWidget(bar)

    def refresh(self) -> None:
        """Load (or reload) current file statuses from the database into the grid."""
        if not self.file_grid:
            return
        try:
            raw_data = self.analysis_db.get_analyzed_pages()
            data = self._transform_data_for_grid(raw_data)
        except Exception as e:
            get_logger().warning(f"[AnalyzePanel] could not load data: {e}")
            return

        self.file_grid.refresh_data(data)

        total = len(data)
        analyzed = sum(1 for r in data if r.get("status") in ("Analyzed", "analyzed"))
        if self.stats_lbl:
            self.stats_lbl.setText(
                f"Total: {total}  ·  Analyzed: {analyzed}  ·  Pending: {total - analyzed}"
            )

        self._refresh_analytics_section()

    def _transform_data_for_grid(self, db_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform raw DB rows to the format expected by FileDetailsGrid."""
        from db.image_status import ImageStatus

        status_mapping = {
            ImageStatus.REGISTERED.value: "Registered",
            ImageStatus.PENDING.value: "Pending",
            ImageStatus.ANALYZING.value: "Analyzing",
            ImageStatus.ANALYZED.value: "Analyzed",
            ImageStatus.ERROR.value: "Error",
            ImageStatus.BUNDLED.value: "Bundled",
            ImageStatus.DELETED.value: "Deleted",
        }

        seen_paths: set[str] = set()
        transformed: list[dict[str, Any]] = []

        for row in db_data:
            file_path = row.get("file_path", "")
            if file_path in seen_paths:
                continue
            seen_paths.add(file_path)

            image_status = row.get("status", "registered")
            status = status_mapping.get(image_status, image_status.title())
            has_analysis = row.get("analysis_id") is not None
            if (
                image_status == ImageStatus.ANALYZED.value
                and has_analysis
                and row.get("confidence_score") is None
            ):
                status = "Failed"

            file_mtime = row.get("file_mtime", 0)
            modified_time = (
                datetime.fromtimestamp(file_mtime, tz=timezone.utc) if file_mtime else None
            )

            transformed.append(
                {
                    "filename": row.get(
                        "filename", os.path.basename(file_path) if file_path else "Unknown"
                    ),
                    "full_path": file_path,
                    "status": status,
                    "confidence": (row.get("confidence_score", 0) * 100)
                    if row.get("confidence_score") is not None
                    else None,
                    "company": row.get("company", ""),
                    "document_type": row.get("document_type", ""),
                    "document_date": row.get("document_date", ""),
                    "page_number": row.get("page_number"),
                    "total_pages": row.get("total_pages"),
                    "rotation": row.get("rotation", 0),
                    "file_size": row.get("file_size", 0),
                    "modified_time": modified_time,
                    "analysis_time": row.get("analyzed_at"),
                    "processing_duration": (row.get("processing_time_ms", 0) / 1000.0)
                    if row.get("processing_time_ms")
                    else None,
                    "model_used": row.get("model_name", ""),
                    "provider": row.get("provider_name", ""),
                    "cache_hit": bool(row.get("is_cached", False)),
                    "error_message": "",
                    "file_hash": row.get("file_hash", ""),
                    "raw_response": row.get("response_text", ""),
                    "response_text": row.get("response_text", ""),
                    "prompt_text": row.get("prompt_text", ""),
                    "tax_related": bool(row.get("tax_related", False)),
                    "is_blank": bool(row.get("is_blank", False)),
                }
            )

        return transformed

    def _connect_worker(self) -> None:
        ct = Qt.ConnectionType.QueuedConnection
        self._worker.job_started.connect(self._on_job_started, ct)  # type: ignore[call-arg]
        self._worker.progress.connect(self._on_progress, ct)  # type: ignore[call-arg]
        self._worker.file_status_changed.connect(self._on_file_status_changed, ct)  # type: ignore[call-arg]
        self._worker.job_finished.connect(self._on_job_finished, ct)  # type: ignore[call-arg]
        self._worker.error.connect(self._on_worker_error, ct)  # type: ignore[call-arg]
        self._worker.queue_empty.connect(self._on_queue_empty, ct)  # type: ignore[call-arg]
        if self.file_grid:
            self.file_grid.re_analyze_requested.connect(self._on_re_analyze_requested)
            self.file_grid.table_view.selectionModel().selectionChanged.connect(
                self._on_grid_selection_changed
            )

    def _on_start(self) -> None:
        self._stats = {"analyzed": 0, "cached": 0, "errors": 0, "total_files": 0}

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
        if self.progress_bar:
            self.progress_bar.setVisible(True)
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
        # Debounce: restart the timer on every signal so rapid bursts (one per
        # file during analysis) collapse into a single refresh() at the end.
        self._refresh_debounce_timer.start()

    def _on_re_analyze_requested(self, file_paths: list[str]) -> None:
        """Queue re-analysis jobs for the given files."""
        for fp in file_paths:
            job = AnalysisJob.create(
                job_type=JobType.ANALYZE_FILES,
                priority=JobPriority.HIGH,
                file_paths=[fp],
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
        if self.progress_bar:
            self.progress_bar.setVisible(True)

    def _on_grid_selection_changed(self) -> None:
        """Update the inline image preview when the grid selection changes."""
        if not self.file_grid or not self.image_preview:
            return
        selection = self.file_grid.table_view.selectionModel().selectedRows()
        has_selection = len(selection) > 0

        self.image_preview.setVisible(has_selection)
        if self._deselect_btn:
            self._deselect_btn.setVisible(has_selection)

        if not has_selection:
            return

        proxy_index = selection[0]
        source_index = self.file_grid.proxy_model.mapToSource(proxy_index)
        row_data = self.file_grid.model.get_row_data(source_index.row())
        if not row_data:
            return
        file_path = row_data.get("full_path", "")
        if not file_path:
            return
        from PyQt6.QtGui import QPixmap

        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            self.image_preview.set_pixmap(pixmap, apply_fit="window", file_path=file_path)

    def _on_select_all(self) -> None:
        """Select all rows in the file grid."""
        if self.file_grid:
            self.file_grid.table_view.selectAll()

    def _on_deselect(self) -> None:
        """Clear the current grid selection."""
        if self.file_grid:
            self.file_grid.table_view.clearSelection()

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

        self._refresh_analytics_section()

    def _on_worker_error(self, job_id: str, error_msg: str) -> None:
        if self.status_lbl:
            self.status_lbl.setText(f"Error: {error_msg[:80]}")
        get_logger().error(f"[Pipeline AnalyzePanel] worker error: {error_msg}")

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
            self.progress_bar.setVisible(False)

    def _update_stats_label(self) -> None:
        if not self.stats_lbl:
            return
        s = self._stats
        self.stats_lbl.setText(
            f"Analyzed: {s['analyzed']}  ·  Cached: {s['cached']}  "
            f"·  Errors: {s['errors']}  ·  Total: {s['total_files']}"
        )

    def shutdown(self) -> None:
        """Stop the analysis worker gracefully. Called by the parent window on close."""
        if self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2000)

    @property
    def is_running(self) -> bool:
        """Return True if the analysis worker is currently active."""
        return bool(self._worker.isRunning())
