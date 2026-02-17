"""
Analysis Status Window
Provides visibility into analysis service status with 3 tabs: Collection Status, Image Details, and PDF Details.
"""

import logging
import os
import subprocess
import time
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from db.analysis_db import AnalysisDB
from db.image_status import ImageStatus
from services.analysis_queue import AnalysisJob, AnalysisQueue, JobPriority, JobType

if TYPE_CHECKING:
    from services.logging_service import get_logger
else:
    get_logger = None

logger: logging.Logger | None = None

# Whitelist of allowed metadata fields for SQL queries (security)
# Using frozenset to prevent mutation
ALLOWED_METADATA_FIELDS = frozenset({"company", "document_type", "document_date", "page_number"})


class AnalysisWorker(QThread):
    """Persistent worker thread that processes analysis jobs from queue."""

    # Signals
    job_started = pyqtSignal(str, str)  # (job_id, description)
    progress = pyqtSignal(str, int, int)  # (status_text, current, total)
    job_finished = pyqtSignal(str, dict)  # (job_id, stats)
    error = pyqtSignal(str, str)  # (job_id, error_message)
    queue_empty = pyqtSignal()  # All jobs processed

    def __init__(self, config_manager, analysis_queue: AnalysisQueue):
        super().__init__()
        self.config_manager = config_manager
        self.analysis_queue = analysis_queue
        self._stop_requested = False
        self._current_job_id = None

    def _get_logger(self) -> logging.Logger:
        """Get logger instance (lazy initialization)."""
        global logger
        if logger is None:
            from services.logging_service import get_logger as _get_logger

            logger = _get_logger()
        return logger

    def run(self):
        """Continuously process jobs from queue until stopped."""
        while not self._stop_requested:
            # Get next job (blocking with timeout to allow checking stop flag)
            job = self.analysis_queue.dequeue(timeout=0.5)

            if job is None:
                # No job available, check if we should continue waiting
                if self._stop_requested:
                    break
                continue

            # Check if job was cancelled before we started
            if self.analysis_queue.is_job_cancelled(job.job_id):
                continue

            self._current_job_id = job.job_id

            try:
                # Process the job
                self._process_job(job)
            except Exception as e:
                import traceback

                error_msg = f"{str(e)}\n{traceback.format_exc()}"
                self._get_logger().error(f"Error processing job {job.job_id}: {error_msg}")
                self.error.emit(job.job_id, error_msg)
                self.analysis_queue.mark_cancelled(job.job_id)
            finally:
                self._current_job_id = None

            # Check if queue is empty
            if self.analysis_queue.get_pending_count() == 0:
                self.queue_empty.emit()

    def _process_job(self, job: AnalysisJob):
        """Process a single analysis job."""
        # Create thread-local database connections
        from db.analysis_db import AnalysisDB
        from db.metadata_db import MetadataDB
        from services.analysis_service import AnalysisService

        thread_analysis_db = None
        thread_metadata_db = None

        try:
            # Emit job started
            if job.job_type == JobType.SCAN_ALL:
                description = "Scanning all directories"
            else:
                description = f"Re-analyzing {len(job.file_paths)} file(s)"
            self.job_started.emit(job.job_id, description)

            # Create new database instances for this thread
            thread_analysis_db = AnalysisDB()
            thread_metadata_db = MetadataDB()
            thread_analysis_service = AnalysisService(
                self.config_manager, thread_analysis_db, thread_metadata_db
            )

            def progress_callback(status_text, current, total):
                if self.analysis_queue.is_job_cancelled(job.job_id):
                    raise InterruptedError("Job cancelled by user")
                self.progress.emit(status_text, current, total)

            def abort_check():
                return self.analysis_queue.is_job_cancelled(job.job_id)

            # Execute based on job type
            if job.job_type == JobType.SCAN_ALL:
                stats = thread_analysis_service.scan_all_directories(
                    progress_callback=progress_callback,
                    incremental=not job.force_reanalysis,
                    abort_check=abort_check,
                )
            else:  # JobType.ANALYZE_FILES
                # Process specific files
                stats = {
                    "analyzed": 0,
                    "cached": 0,
                    "errors": 0,
                    "total_files": len(job.file_paths),
                }
                for idx, file_path in enumerate(job.file_paths, 1):
                    if self.analysis_queue.is_job_cancelled(job.job_id):
                        raise InterruptedError("Job cancelled by user")

                    # Set status to "analyzing" when actually starting to process this file
                    thread_analysis_db.update_image_status(file_path, ImageStatus.ANALYZING.value)

                    progress_callback(
                        f"Analyzing {os.path.basename(file_path)}", idx, len(job.file_paths)
                    )

                    # Re-analyze the file (using private method _analyze_single_page)
                    result = thread_analysis_service._analyze_single_page(
                        file_path, incremental=not job.force_reanalysis
                    )

                    if result.get("success"):
                        stats["analyzed"] += 1
                        # Set status to "analyzed" after successful processing
                        thread_analysis_db.update_image_status(
                            file_path, ImageStatus.ANALYZED.value
                        )
                    else:
                        stats["errors"] += 1
                        # Keep status as "analyzing" to indicate incomplete processing

            # Mark job complete
            self.analysis_queue.mark_complete(job.job_id)
            self.job_finished.emit(job.job_id, stats)

        except InterruptedError:
            # Job was cancelled
            self.analysis_queue.mark_cancelled(job.job_id)
            self.job_finished.emit(
                job.job_id,
                {
                    "total_files": 0,
                    "analyzed": 0,
                    "cached": 0,
                    "errors": 0,
                    "message": "Job cancelled",
                },
            )
        finally:
            # Clean up thread-local connections
            if thread_analysis_db:
                thread_analysis_db.close()
            if thread_metadata_db:
                thread_metadata_db.close()

    def stop(self):
        """Request worker to stop after current job."""
        self._stop_requested = True

    def cancel_current_job(self):
        """Cancel the currently processing job."""
        if self._current_job_id:
            self.analysis_queue.mark_cancelled(self._current_job_id)


class AnalysisStatusWindow(QDialog):
    """Main Analysis Status Window with 3 tabs: Collection Status, Image Details, and PDF Details"""

    # Signals
    retry_failed_requested = pyqtSignal()

    def __init__(
        self,
        parent=None,
        analysis_db=None,
        metadata_db=None,
        config_manager=None,
        analysis_service=None,
        auto_start_analysis: bool = False,
    ):
        super().__init__(parent)
        # Track ownership: only close DB connections we create ourselves
        self._owns_analysis_db = analysis_db is None
        self._owns_metadata_db = metadata_db is None
        self.analysis_db = analysis_db if analysis_db is not None else AnalysisDB()
        self.config_manager = config_manager
        self.analysis_service = analysis_service
        self._auto_start_analysis = auto_start_analysis

        # Initialize metadata_db for delete operations
        if metadata_db is None:
            from db.metadata_db import MetadataDB

            metadata_db = MetadataDB()
        self.metadata_db = metadata_db

        # Determine theme
        self.is_dark_mode = False
        if self.config_manager:
            theme = self.config_manager.get_setting("Theme", "theme", "light")
            self.is_dark_mode = theme == "dark"

        # Initialize attributes referenced in closeEvent
        self.auto_refresh_timer = None
        self._analysis_thread = None
        self._analysis_start_time: float | None = None
        self._analysis_stats: dict[str, int] = {
            "analyzed": 0,
            "cached": 0,
            "errors": 0,
            "total_files": 0,
        }
        self._last_grid_refresh_time: float = 0  # Timestamp of last grid refresh
        self._first_progress_update: bool = (
            True  # Track first progress update to show "Analyzing" immediately
        )

        # Timer for live progress updates
        self._progress_timer: QTimer | None = None
        self._current_job_start_time: float | None = None
        self._avg_processing_time_ms: float | None = None

        # Initialize queue-based analysis system
        self.analysis_queue: AnalysisQueue = AnalysisQueue()
        self.analysis_worker = AnalysisWorker(self.config_manager, self.analysis_queue)

        # Connect worker signals
        self.analysis_worker.job_started.connect(self._on_job_started)
        self.analysis_worker.progress.connect(self._on_analysis_progress_update)
        self.analysis_worker.job_finished.connect(self._on_job_finished)
        self.analysis_worker.error.connect(self._on_job_error)
        self.analysis_worker.queue_empty.connect(self._on_queue_empty)

        self._init_ui()
        self._load_all_data()

        # If requested, start analysis using provided AnalysisService
        if self._auto_start_analysis and self.analysis_service:
            self._start_analysis_internal()

    def _get_logger(self) -> logging.Logger:
        """Get logger instance (lazy initialization)."""
        global logger
        if logger is None:
            from services.logging_service import get_logger as _get_logger

            logger = _get_logger()
        return logger

    def _get_theme_colors(self):
        """Return color palette based on current theme"""
        if self.is_dark_mode:
            return {
                "bg_primary": "#0B1120",
                "bg_secondary": "#151D2F",
                "bg_tertiary": "#1F2A40",
                "text_primary": "#E0E0E0",
                "text_secondary": "#B0B0B0",
                "text_tertiary": "#808080",
                "border": "#2A3550",
                "tab_active_bg": "#151D2F",
                "tab_inactive_bg": "#0B1120",
                "tab_hover_bg": "#1F2A40",
            }
        else:
            return {
                "bg_primary": "#F9FAFB",
                "bg_secondary": "#FFFFFF",
                "bg_tertiary": "#F3F4F6",
                "text_primary": "#111827",
                "text_secondary": "#374151",
                "text_tertiary": "#6B7280",
                "border": "#E5E7EB",
                "tab_active_bg": "#FFFFFF",
                "tab_inactive_bg": "#F3F4F6",
                "tab_hover_bg": "#E5E7EB",
            }

    def _init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Analytics & Details")
        self.setMinimumSize(1200, 800)
        self.setModal(False)

        # Store theme colors as instance variables for use throughout tabs
        self.theme_colors = self._get_theme_colors()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # Enhanced toolbar with status and controls
        # Global ThemeManager handles basic styling; only custom state-based colors here
        toolbar_frame = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_frame)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        toolbar_layout.setSpacing(12)

        # Left side: Status indicator (color set dynamically in _update_toolbar_status)
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("font-size: 14pt;")
        toolbar_layout.addWidget(self.status_indicator)

        self.status_text = QLabel("Ready")
        self.status_text.setStyleSheet("font-weight: 600; font-size: 11pt;")
        toolbar_layout.addWidget(self.status_text)

        # Progress info (shown when analyzing)
        self.progress_info = QLabel("")
        self.progress_info.setStyleSheet("font-size: 10pt;")
        self.progress_info.setVisible(False)
        toolbar_layout.addWidget(self.progress_info)

        toolbar_layout.addStretch()

        # Right side: Control buttons
        # Start button uses green color for primary action
        self.start_analysis_btn = QPushButton("▶ Start Analysis")
        self.start_analysis_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                font-weight: 600;
                padding: 6px 16px;
                border: none;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        self.start_analysis_btn.clicked.connect(self._on_toolbar_start_analysis)
        toolbar_layout.addWidget(self.start_analysis_btn)

        # Stop button - yellow/amber warning style (darker in dark mode)
        self.stop_analysis_btn = QPushButton("⏸ Stop")
        self.stop_analysis_btn.setToolTip("Stop analysis gracefully (saves progress)")
        stop_bg = "#D97706" if self.is_dark_mode else "#F59E0B"
        stop_hover = "#B45309" if self.is_dark_mode else "#D97706"
        self.stop_analysis_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {stop_bg};
                color: #1F2937;
                font-weight: 600;
                padding: 6px 16px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {stop_hover};
            }}
        """)
        self.stop_analysis_btn.clicked.connect(self._on_stop_analysis)
        self.stop_analysis_btn.setVisible(False)
        toolbar_layout.addWidget(self.stop_analysis_btn)

        # Abort button - red danger style (very dark crimson in dark mode)
        self.abort_analysis_btn = QPushButton("⏹ Abort")
        self.abort_analysis_btn.setToolTip("Abort analysis without saving")
        abort_bg = "#991B1B" if self.is_dark_mode else "#EF4444"
        abort_hover = "#7F1D1D" if self.is_dark_mode else "#DC2626"
        abort_text = "#E0E0E0" if self.is_dark_mode else "#1F2937"  # Light text for dark button
        self.abort_analysis_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {abort_bg};
                color: {abort_text};
                font-weight: 600;
                padding: 6px 16px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {abort_hover};
            }}
        """)
        self.abort_analysis_btn.clicked.connect(self._on_abort_analysis)
        self.abort_analysis_btn.setVisible(False)
        toolbar_layout.addWidget(self.abort_analysis_btn)

        # Refresh button (always visible) with label and background
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setToolTip("Refresh all statistics and data")
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme_colors["bg_tertiary"]};
                color: {self.theme_colors["text_primary"]};
                border: 1px solid {self.theme_colors["border"]};
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {self.theme_colors["tab_hover_bg"]};
            }}
        """)
        self.refresh_btn.clicked.connect(self._refresh_all)
        toolbar_layout.addWidget(self.refresh_btn)

        main_layout.addWidget(toolbar_frame)

        # Create 2-tab layout with seamless styling
        self.tabs = QTabWidget()
        colors = self.theme_colors
        self.tabs.setStyleSheet(f"""
            /* Tab widget pane - solid background, no border on top where tabs connect */
            QTabWidget::pane {{
                background-color: {colors["bg_secondary"]};
                border: 1px solid {colors["border"]};
                border-top: none;
                border-radius: 0px 0px 8px 8px;
                margin-top: 0px;
            }}

            /* Tab bar */
            QTabBar::tab {{
                background-color: {colors["bg_tertiary"]};
                color: {colors["text_secondary"]};
                border: 1px solid {colors["border"]};
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 20px;
                margin-right: 2px;
                font-size: 11pt;
            }}

            /* Selected tab - seamlessly connects to content */
            QTabBar::tab:selected {{
                background-color: {colors["bg_secondary"]};
                color: {colors["text_primary"]};
                font-weight: 600;
                border-color: {colors["border"]};
                border-bottom: none;
                margin-bottom: -1px;
            }}

            QTabBar::tab:hover:!selected {{
                background-color: {colors["tab_hover_bg"]};
                color: {colors["text_primary"]};
            }}
        """)
        self.tabs.addTab(self._create_collection_status_tab(), "Analytics")
        self.tabs.addTab(self._create_file_grid_tab(), "Image Details")
        self.tabs.addTab(self._create_document_details_tab(), "PDF Details")

        main_layout.addWidget(self.tabs)

        # Status label (uses default theme colors)
        self.scan_status_label = QLabel("")
        self.scan_status_label.setObjectName("scanStatusLabel")
        main_layout.addWidget(self.scan_status_label)

    def _create_collection_status_tab(self) -> QWidget:
        """Create the Collection Status tab with comprehensive metrics in responsive grid layout"""
        from PyQt6.QtWidgets import QGridLayout, QScrollArea

        from ui.collection_status_helpers import (
            create_action_items_widget,
            create_collapsible_section,
            create_funnel_widget,
            create_metric_card,
            create_quality_metrics_widget,
            create_speed_eta_widget,
        )

        # Create scroll area wrapper with solid background
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {self.theme_colors["bg_secondary"]};
                border: none;
            }}
        """)

        # Create content widget with matching background
        widget = QWidget()
        widget.setStyleSheet(f"background-color: {self.theme_colors['bg_secondary']};")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Key Metrics Cards in Collapsible Panel
        metrics_container = QWidget()
        metrics_row = QHBoxLayout(metrics_container)
        metrics_row.setSpacing(12)
        metrics_row.setContentsMargins(0, 0, 0, 0)

        # Create metric cards with tooltips
        self.total_files_card = create_metric_card(self.theme_colors, "📄 Images", "0")
        self.total_files_card.setToolTip("Total number of unique image files in the database")

        self.analyzed_pages_card = create_metric_card(self.theme_colors, "✅ Analyzed", "0%")
        self.analyzed_pages_card.setToolTip(
            "Percentage of files analyzed by the LLM to extract metadata"
        )

        self.documents_card = create_metric_card(self.theme_colors, "📦 Bundled", "0")
        self.documents_card.setToolTip(
            "Total number of pages that have been bundled into accepted/completed documents"
        )

        self.metadata_quality_card = create_metric_card(self.theme_colors, "📋 Needs Review", "0")
        self.metadata_quality_card.setToolTip(
            "Number of images with 'analyzed' status awaiting review"
        )

        self.avg_processing_card = create_metric_card(self.theme_colors, "⏱️ Avg Inference", "--")
        self.avg_processing_card.setToolTip(
            "Average time to analyze a file with the LLM (files analyzed from cache show 0ms)"
        )

        self.tax_related_card = create_metric_card(self.theme_colors, "💰 Tax Related", "0%")
        self.tax_related_card.setToolTip("Percentage of documents identified as tax-related")

        self.pdfs_generated_card = create_metric_card(self.theme_colors, "📑 PDFs", "0")
        self.pdfs_generated_card.setToolTip("Number of completed bundles with generated PDF files")

        self.total_files_card.setMinimumWidth(140)
        self.analyzed_pages_card.setMinimumWidth(160)
        self.documents_card.setMinimumWidth(140)
        self.metadata_quality_card.setMinimumWidth(160)
        self.avg_processing_card.setMinimumWidth(140)
        self.tax_related_card.setMinimumWidth(140)
        self.pdfs_generated_card.setMinimumWidth(140)

        metrics_row.addWidget(self.total_files_card)
        metrics_row.addWidget(self.analyzed_pages_card)
        metrics_row.addWidget(self.documents_card)
        metrics_row.addWidget(self.metadata_quality_card)
        metrics_row.addWidget(self.avg_processing_card)
        metrics_row.addWidget(self.pdfs_generated_card)
        metrics_row.addWidget(self.tax_related_card)

        # Create main grid layout
        grid = QGridLayout()
        grid.setSpacing(15)
        grid.setContentsMargins(0, 0, 0, 0)
        # Set column stretch so both columns share space equally
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        # Row 0: Key Metrics (spans both columns)
        metrics_section = create_collapsible_section(
            self.theme_colors, "📊 Key Metrics", metrics_container, initially_expanded=True
        )
        grid.addWidget(metrics_section, 0, 0, 1, 2)  # Row 0, column 0, span 1 row, 2 columns

        # Left column container (Row 1, Column 0)
        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(15)

        # Left: Analysis Pipeline (collapsed by default)
        funnel_widget, self.funnel_bars = create_funnel_widget(self.theme_colors)
        funnel_section = create_collapsible_section(
            self.theme_colors, "📊 Analysis Pipeline", funnel_widget, initially_expanded=False
        )
        left_layout.addWidget(funnel_section)

        # Left: Action Items (collapsed by default)
        action_callbacks = {
            "start_analysis": self._on_start_analysis,
            "review_bundles": self._on_review_bundles,
            "view_errors": self._on_view_errors,
            "create_bundles": self._on_create_bundles,
        }
        action_items_widget, self.action_items = create_action_items_widget(
            self.theme_colors, action_callbacks
        )
        action_section = create_collapsible_section(
            self.theme_colors, "📋 Action Items", action_items_widget, initially_expanded=False
        )
        left_layout.addWidget(action_section)

        # Left: Document Insights (collapsed by default)
        from ui.collection_status_helpers import create_document_insights_widget_split

        (
            doc_insights_content,
            self.docs_created_label,
            self.pages_archived_label,
            self.avg_pages_label,
            self.bundle_acceptance_label,
            self.type_distribution_container,
        ) = create_document_insights_widget_split(self.theme_colors)
        doc_insights_section = create_collapsible_section(
            self.theme_colors,
            "📑 Document Insights",
            doc_insights_content,
            initially_expanded=False,
        )
        left_layout.addWidget(doc_insights_section)

        left_layout.addStretch()
        grid.addWidget(left_column, 1, 0)

        # Right column container (Row 1, Column 1)
        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)

        # Right: Processing Speed (collapsed by default)
        speed_eta_widget, self.speed_label, self.eta_label = create_speed_eta_widget(
            self.theme_colors
        )
        speed_section = create_collapsible_section(
            self.theme_colors, "⚡ Processing Speed", speed_eta_widget, initially_expanded=False
        )
        right_layout.addWidget(speed_section)

        # Right: Quality Metrics (collapsed by default)
        (
            quality_content,
            self.avg_confidence_label,
            self.error_rate_label,
            self.completeness_bars,
        ) = create_quality_metrics_widget(self.theme_colors)
        quality_section = create_collapsible_section(
            self.theme_colors, "✅ Quality Metrics", quality_content, initially_expanded=False
        )
        right_layout.addWidget(quality_section)

        # Right: Company Insights (collapsed by default)
        from ui.collection_status_helpers import create_company_insights_widget

        company_insights_content, self.company_distribution_container = (
            create_company_insights_widget(self.theme_colors)
        )
        company_insights_section = create_collapsible_section(
            self.theme_colors,
            "🏢 Company Insights",
            company_insights_content,
            initially_expanded=False,
        )
        right_layout.addWidget(company_insights_section)

        right_layout.addStretch()
        grid.addWidget(right_column, 1, 1)

        layout.addLayout(grid)
        layout.addStretch()

        # Set widget to scroll area and return scroll area
        scroll_area.setWidget(widget)
        return scroll_area

    def _create_file_grid_tab(self) -> QWidget:
        """Create the File Analysis Grid tab"""
        from PyQt6.QtWidgets import QScrollArea, QVBoxLayout

        from ui.file_details_grid import FileDetailsGrid

        # Create scroll area wrapper with solid background (matching Collection Status tab)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {self.theme_colors["bg_secondary"]};
                border: none;
            }}
        """)

        # Create content widget with matching background
        container = QWidget()
        container.setStyleSheet(f"background-color: {self.theme_colors['bg_secondary']};")
        container.setAutoFillBackground(True)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Add file grid to container
        self.file_grid = FileDetailsGrid(
            self, analysis_db=self.analysis_db, metadata_db=self.metadata_db
        )
        layout.addWidget(self.file_grid)

        # CRITICAL: Connect re-analysis signal from context menu
        self.file_grid.re_analyze_requested.connect(self._on_re_analyze_requested)

        # Set container as scroll area widget
        scroll_area.setWidget(container)
        return scroll_area

    def _create_document_details_tab(self) -> QWidget:
        """Create the PDF Details tab showing generated PDFs"""
        # Create scroll area wrapper with solid background
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {self.theme_colors["bg_secondary"]};
                border: none;
            }}
        """)

        # Create content widget with matching background
        container = QWidget()
        container.setStyleSheet(f"background-color: {self.theme_colors['bg_secondary']};")
        container.setAutoFillBackground(True)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Create table
        self.document_table = QTableWidget()
        self.document_table.setColumnCount(6)
        self.document_table.setHorizontalHeaderLabels(
            ["PDF Filename", "Company", "Document Type", "Date", "Pages", "Created At"]
        )

        # Style table with current theme
        colors = self.theme_colors
        self.document_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {colors["bg_secondary"]};
                color: {colors["text_primary"]};
                border: 1px solid {colors["border"]};
                gridline-color: {colors["border"]};
                selection-background-color: #3B82F6;
                selection-color: white;
            }}
            QHeaderView::section {{
                background-color: {colors["bg_tertiary"]};
                color: {colors["text_primary"]};
                padding: 8px;
                border: 1px solid {colors["border"]};
                font-weight: 600;
            }}
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {colors["border"]};
            }}
            QTableWidget::item:selected {{
                background-color: #3B82F6;
                color: white;
            }}
        """)

        # Configure table
        self.document_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.document_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.document_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Configure headers (with null checks for mypy)
        h_header = self.document_table.horizontalHeader()
        v_header = self.document_table.verticalHeader()
        if h_header:
            h_header.setStretchLastSection(True)
            h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        if v_header:
            v_header.setVisible(False)

        # Set column widths
        self.document_table.setColumnWidth(0, 300)  # PDF Filename
        self.document_table.setColumnWidth(1, 200)  # Company
        self.document_table.setColumnWidth(2, 200)  # Document Type
        self.document_table.setColumnWidth(3, 120)  # Date
        self.document_table.setColumnWidth(4, 80)  # Pages
        self.document_table.setColumnWidth(5, 180)  # Created At

        # Connect double-click handler
        self.document_table.itemDoubleClicked.connect(self._on_document_table_double_click)

        layout.addWidget(self.document_table)

        # Set container as scroll area widget
        scroll_area.setWidget(container)
        return scroll_area

    def _load_all_data(self):
        """Load data for all tabs"""
        self._refresh_collection_status()
        self._refresh_file_grid()
        self._refresh_document_details()

    def _refresh_all(self):
        """Refresh all tabs"""
        self._refresh_collection_status()
        self._refresh_file_grid()
        self._refresh_document_details()

    def _on_analysis_progress(self, status_text, current, total):
        """Handle progress updates from background analysis thread"""
        try:  # noqa: SIM105
            self.scan_status_label.setText(f"{status_text} ({current}/{total})")
        except Exception as e:
            # Log UI update errors but don't crash during callbacks
            self._get_logger().warning(f"Error updating scan status label: {e}")

    def _on_analysis_finished(self, stats: dict):
        """Handle analysis finished event"""
        # Refresh displayed data
        try:
            self.scan_status_label.setText("Analysis complete")
            self._load_all_data()
        except Exception as e:
            # Log analysis finished errors but don't crash
            self._get_logger().error(f"Error handling analysis finished event: {e}", exc_info=True)

    def _refresh_collection_status(self):
        """Refresh Collection Status tab with live statistics"""
        if not hasattr(self, "funnel_bars"):
            return  # Tab not yet created

        # Check if database connection is still valid
        if (
            not self.analysis_db
            or not hasattr(self.analysis_db, "connection")
            or not self.analysis_db.connection
        ):
            return  # Database is closed, skip refresh

        try:
            # Get comprehensive statistics
            stats = self._calculate_collection_statistics()

            # Update metric cards
            self._update_metric_cards(stats)

            # Update funnel
            self._update_funnel(stats)

            # Update speed/ETA
            self._update_speed_eta(stats)

            # Update action items
            self._update_action_items(stats)

            # Update quality metrics
            self._update_quality_metrics(stats)

            # Update document insights
            self._update_document_insights(stats)

        except Exception as e:
            # Silently ignore errors during shutdown
            if self.analysis_db and self.analysis_db.connection:
                self._get_logger().error(f"Error refreshing collection status: {e}")

    def _calculate_collection_statistics(self):
        """Calculate comprehensive collection statistics from database"""
        import os

        # Verify database connection is valid
        if (
            not self.analysis_db
            or not hasattr(self.analysis_db, "connection")
            or not self.analysis_db.connection
            or not hasattr(self.analysis_db.connection, "connection")
            or not self.analysis_db.connection.connection
        ):
            # Return default empty stats if database not available
            return {
                "files_detected": 0,
                "files_analyzed": 0,
                "high_confidence": 0,
                "pages_bundled": 0,
                "documents_archived": 0,
                "pdfs_generated": 0,
                "needs_review_count": 0,
                "processing_speed": 0,
                "eta_minutes": 0,
                "avg_confidence": 0,
                "error_rate": 0,
                "metadata_completeness": 0,
                "pending_analysis": 0,
                "pending_bundles": 0,
                "failed_files": 0,
                "unbundled_files": 0,
                "bundle_acceptance_rate": 0,
                "type_distribution": {},
                "company_distribution": {},
                "total_archived_pages": 0,
                "cached_count": 0,
                "avg_processing_time_ms": 0,
            }

        cursor = self.analysis_db.connection.connection.cursor()

        # Total files detected (scan actual directories, not just analyzed files)
        files_detected = 0
        if self.config_manager:
            directories = self.config_manager.get_directories()
            for directory in directories:
                if os.path.exists(directory):
                    for _, _, files in os.walk(directory):
                        for file in files:
                            if file.lower().endswith((".png", ".jpg", ".jpeg")):
                                files_detected += 1

        # Files analyzed (distinct images with metadata, excluding deleted)
        cursor.execute(
            """
            SELECT COUNT(DISTINCT m.image_file_id)
            FROM metadata m
            INNER JOIN image_files img ON m.image_file_id = img.id
            WHERE img.status != 'deleted'
        """
        )
        files_analyzed = cursor.fetchone()[0]

        # Cap files_analyzed at files_detected to prevent >100% (handles deleted/moved files)
        files_analyzed = min(files_analyzed, files_detected)

        # High confidence (>= 80%) - from user-approved metadata
        cursor.execute(
            """
            SELECT COUNT(*) FROM metadata m
            INNER JOIN image_files img ON m.image_file_id = img.id
            WHERE img.status != 'deleted'
            AND m.confidence_score >= 0.8
        """
        )
        high_confidence = cursor.fetchone()[0]

        # Pages bundled (count distinct images in finalized bundles only)
        # After Migration 16: use bundle_images junction table
        cursor.execute(
            """
            SELECT COUNT(DISTINCT bi.image_file_id)
            FROM bundle_images bi
            INNER JOIN document_bundles b ON bi.bundle_id = b.id
            WHERE b.status IN ('accepted', 'completed')
        """
        )
        pages_bundled_result = cursor.fetchone()
        pages_bundled = pages_bundled_result[0] if pages_bundled_result else 0

        # Documents archived (from bundle table with accepted/completed status)
        cursor.execute(
            """
            SELECT COUNT(*) FROM document_bundles
            WHERE status IN ('accepted', 'completed')
        """
        )
        documents_archived = cursor.fetchone()[0]

        # PDFs generated (count PDFs linked to completed bundles)
        # After Migration 16: pdf_path moved to pdf_files table
        cursor.execute(
            """
            SELECT COUNT(*) FROM pdf_files pf
            INNER JOIN document_bundles b ON pf.bundle_id = b.id
            WHERE b.status = 'completed'
        """
        )
        pdfs_generated = cursor.fetchone()[0]

        # Cached files count - files with multiple analyses (re-analyzed)
        # After Migration 16, cache detection is based on multiple analyses per image_file_id
        cursor.execute("""
            SELECT COUNT(DISTINCT image_file_id)
            FROM (
                SELECT image_file_id, COUNT(*) as analysis_count
                FROM analysis_results
                GROUP BY image_file_id
                HAVING analysis_count > 1
            )
        """)
        cached_count = cursor.fetchone()[0]

        # Needs review count - images with 'analyzed' status awaiting review
        cursor.execute(
            """
            SELECT COUNT(*) FROM image_files
            WHERE status = 'analyzed'
        """
        )
        needs_review_count = cursor.fetchone()[0]

        # Processing speed (last 100 successful analyses)
        # After Migration 16, use had_error flag instead of is_cached
        cursor.execute(
            """
            SELECT analyzed_at, processing_time_ms
            FROM analysis_results
            WHERE had_error = 0 AND processing_time_ms IS NOT NULL
            ORDER BY analyzed_at DESC
            LIMIT 100
        """
        )
        recent_analyses = cursor.fetchall()

        processing_speed = 0
        eta_minutes = 0
        if len(recent_analyses) >= 2:
            # Calculate pages per minute from recent analyses
            from datetime import datetime

            first_time = datetime.fromisoformat(recent_analyses[-1][0])
            last_time = datetime.fromisoformat(recent_analyses[0][0])
            time_span_minutes = (last_time - first_time).total_seconds() / 60

            if time_span_minutes > 0:
                processing_speed = len(recent_analyses) / time_span_minutes

                # Calculate ETA for pending files
                pending_files = 0  # For now, set to 0 since we don't track pending files
                if processing_speed > 0 and pending_files > 0:
                    eta_minutes = pending_files / processing_speed

        # Average confidence score - from user-approved metadata
        cursor.execute(
            """
            SELECT AVG(m.confidence_score)
            FROM metadata m
            INNER JOIN image_files img ON m.image_file_id = img.id
            WHERE img.status != 'deleted'
            AND m.confidence_score IS NOT NULL
        """
        )
        avg_confidence_result = cursor.fetchone()[0]
        avg_confidence = (avg_confidence_result * 100) if avg_confidence_result else 0

        # Error rate (from analysis_results table)
        # After Migration 16: use had_error flag instead of analysis_errors table
        cursor.execute("SELECT COUNT(*) FROM analysis_results WHERE had_error = 1")
        error_count = cursor.fetchone()[0]
        error_rate = (error_count / files_detected * 100) if files_detected > 0 else 0

        # Metadata completeness - from user-approved metadata
        metadata_completeness = {}
        for field in ["company", "document_type", "document_date", "page_number"]:
            # Validate field name against whitelist
            if field not in ALLOWED_METADATA_FIELDS:
                raise ValueError(f"Invalid metadata field: {field}")

            # Now safe to use in SQL query
            cursor.execute(
                f"""
                SELECT COUNT(*) * 100.0 / (
                    SELECT COUNT(*) FROM metadata m
                    INNER JOIN image_files img ON m.image_file_id = img.id
                    WHERE img.status != 'deleted'
                )
                FROM metadata m
                INNER JOIN image_files img ON m.image_file_id = img.id
                WHERE img.status != 'deleted'
                AND m.{field} IS NOT NULL AND m.{field} != ''
            """
            )
            result = cursor.fetchone()[0]
            metadata_completeness[field] = result if result else 0

        # Pending action items
        pending_bundles = len(self.analysis_db.get_bundle_suggestions(status_filter="suggested"))
        failed_files = error_count
        unbundled_files = files_analyzed - pages_bundled  # Only count analyzed files

        # Bundle acceptance rate
        cursor.execute(
            "SELECT COUNT(*) FROM document_bundles WHERE status IN ('accepted', 'completed')"
        )
        accepted_count = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM document_bundles
            WHERE status IN ('accepted', 'rejected', 'completed')
        """
        )
        reviewed_count = cursor.fetchone()[0]
        bundle_acceptance_rate = (
            (accepted_count / reviewed_count * 100) if reviewed_count > 0 else 0
        )

        # Document type distribution
        type_dist = self.analysis_db.get_document_type_breakdown()

        # Company distribution (top 5) - from user-approved metadata
        cursor.execute(
            """
            SELECT m.company, COUNT(*) as count
            FROM metadata m
            INNER JOIN image_files img ON m.image_file_id = img.id
            WHERE img.status != 'deleted'
            AND m.company IS NOT NULL AND m.company != ''
            GROUP BY m.company
            ORDER BY count DESC
            LIMIT 5
        """
        )
        company_dist = {row[0]: row[1] for row in cursor.fetchall()}

        # Total archived pages (sum of page counts from bundles)
        # After Migration 16: count from bundle_images junction table
        cursor.execute(
            """
            SELECT COUNT(bi.image_file_id)
            FROM bundle_images bi
            INNER JOIN document_bundles b ON bi.bundle_id = b.id
            WHERE b.status IN ('accepted', 'completed')
        """
        )
        archived_pages_result = cursor.fetchone()[0]
        total_archived_pages = archived_pages_result if archived_pages_result else 0

        # Average processing time (only successful, non-error analyses with real LLM inference time)
        # Exclude cache hits (processing_time_ms < 1000ms) which are very fast retrievals
        cursor.execute(
            """
            SELECT AVG(processing_time_ms)
            FROM analysis_results
            WHERE had_error = 0
              AND processing_time_ms IS NOT NULL
              AND processing_time_ms >= 1000
        """
        )
        avg_processing_result = cursor.fetchone()[0]
        avg_processing_time_ms = avg_processing_result if avg_processing_result else 0

        # Tax related count and percentage - from user-approved metadata
        cursor.execute(
            """
            SELECT COUNT(*) FROM metadata m
            INNER JOIN image_files img ON m.image_file_id = img.id
            WHERE img.status != 'deleted'
            AND m.tax_related = 1
        """
        )
        tax_related_count = cursor.fetchone()[0]
        tax_related_pct = (tax_related_count / files_analyzed * 100) if files_analyzed > 0 else 0

        return {
            "files_detected": files_detected,
            "files_analyzed": files_analyzed,
            "high_confidence": high_confidence,
            "pages_bundled": pages_bundled,
            "documents_archived": documents_archived,
            "pdfs_generated": pdfs_generated,
            "needs_review_count": needs_review_count,
            "processing_speed": processing_speed,
            "eta_minutes": eta_minutes,
            "avg_confidence": avg_confidence,
            "error_rate": error_rate,
            "metadata_completeness": metadata_completeness,
            "pending_analysis": 0,  # We don't track pending files yet
            "pending_bundles": pending_bundles,
            "failed_files": failed_files,
            "unbundled_files": unbundled_files,
            "bundle_acceptance_rate": bundle_acceptance_rate,
            "type_distribution": type_dist,
            "company_distribution": company_dist,
            "total_archived_pages": total_archived_pages,
            "cached_count": cached_count,
            "avg_processing_time_ms": avg_processing_time_ms,
            "tax_related_count": tax_related_count,
            "tax_related_pct": tax_related_pct,
        }

    def _update_metric_cards(self, stats):
        """Update the metric cards at the top"""
        # Images
        self.total_files_card.findChild(QLabel, "📄_images_value").setText(
            str(stats["files_detected"])
        )

        # Analyzed (percentage only, count in tooltip)
        analyzed_pct = (
            (stats["files_analyzed"] / stats["files_detected"] * 100)
            if stats["files_detected"] > 0
            else 0
        )
        self.analyzed_pages_card.findChild(QLabel, "✅_analyzed_value").setText(
            f"{analyzed_pct:.1f}%"
        )
        # Update tooltip with count
        self.analyzed_pages_card.setToolTip(
            f"Percentage of files analyzed by the LLM to extract metadata\n\n"
            f"{stats['files_analyzed']:,} of {stats['files_detected']:,} files analyzed"
        )

        # Bundled
        self.documents_card.findChild(QLabel, "📦_bundled_value").setText(
            str(stats["total_archived_pages"])
        )

        # Needs Review Count
        self.metadata_quality_card.findChild(QLabel, "📋_needs_review_value").setText(
            str(stats["needs_review_count"])
        )

        # Average Inference Time
        avg_time = stats.get("avg_processing_time_ms", 0)
        if avg_time > 0:
            if avg_time >= 1000:
                # Show in seconds if >= 1000ms
                self.avg_processing_card.findChild(QLabel, "⏱️_avg_inference_value").setText(
                    f"{avg_time / 1000:.1f}s"
                )
            else:
                # Show in milliseconds
                self.avg_processing_card.findChild(QLabel, "⏱️_avg_inference_value").setText(
                    f"{avg_time:.0f}ms"
                )
        else:
            self.avg_processing_card.findChild(QLabel, "⏱️_avg_inference_value").setText("--")

        # Tax Related Percentage
        tax_related_pct = stats.get("tax_related_pct", 0)
        tax_related_count = stats.get("tax_related_count", 0)
        self.tax_related_card.findChild(QLabel, "💰_tax_related_value").setText(
            f"{tax_related_pct:.1f}%"
        )
        # Update tooltip with count
        self.tax_related_card.setToolTip(
            f"Percentage of documents identified as tax-related\n\n"
            f"{tax_related_count:,} of {stats['files_analyzed']:,} files are tax-related"
        )

        # PDFs
        pdfs_generated = stats.get("pdfs_generated", 0)
        self.pdfs_generated_card.findChild(QLabel, "📑_pdfs_value").setText(str(pdfs_generated))

    def _update_funnel(self, stats):
        """Update analysis completion funnel"""
        total = max(stats["files_detected"], 1)  # Avoid division by zero

        stages = [
            ("files_detected", stats["files_detected"]),
            ("files_analyzed", stats["files_analyzed"]),
            ("high_confidence", stats["high_confidence"]),
            ("pages_bundled", stats["pages_bundled"]),
            ("documents_archived", stats["documents_archived"]),
        ]

        for key, value in stages:
            percentage = int((value / total) * 100)
            stage_name = self.funnel_bars[key].get("stage_name", key.replace("_", " ").title())
            label_text = f"{stage_name}: {value} ({percentage}%)"
            self.funnel_bars[key]["label"].setText(label_text)
            self.funnel_bars[key]["bar"].setValue(percentage)

    def _update_speed_eta(self, stats):
        """Update processing speed and ETA labels"""
        # Calculate pending files (total in directories - analyzed)
        pending_files = stats["files_detected"] - stats["files_analyzed"]

        if stats["processing_speed"] > 0:
            self.speed_label.setText(f"Processing Speed: {stats['processing_speed']:.1f} pages/min")

            if pending_files > 0 and stats["eta_minutes"] > 0:
                # Show ETA for remaining files
                hours = int(stats["eta_minutes"] // 60)
                minutes = int(stats["eta_minutes"] % 60)
                eta_text = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                self.eta_label.setText(f"ETA: ~{eta_text} ({pending_files} pending)")
            elif pending_files == 0:
                # All files are analyzed
                self.eta_label.setText("ETA: All files analyzed ✓")
            else:
                # Can't calculate ETA (not enough data)
                self.eta_label.setText(f"ETA: -- ({pending_files} pending)")
        else:
            self.speed_label.setText("Processing Speed: -- pages/min")
            if pending_files > 0:
                self.eta_label.setText(f"ETA: -- ({pending_files} pending)")
            else:
                self.eta_label.setText("ETA: All files analyzed ✓")

    def _update_action_items(self, stats):
        """Update action items panel text and button states"""
        action_data = [
            (
                stats["pending_analysis"],
                "⚡ Ready to analyze files from configured directories",
                True,  # Always show Start Analysis
            ),
            (
                stats["pending_bundles"],
                f"⚠️ {stats['pending_bundles']} bundles suggested for review",
                stats["pending_bundles"] > 0,  # Only show if bundles exist
            ),
            (
                stats["failed_files"],
                f"❌ {stats['failed_files']} files with analysis errors",
                stats["failed_files"] > 0,  # Only show if errors exist
            ),
            (
                stats["unbundled_files"],
                f"✅ {stats['unbundled_files']} analyzed files not yet bundled",
                stats["unbundled_files"] > 0,  # Only show if unbundled files exist
            ),
        ]

        for i, (_, text, should_show) in enumerate(action_data):
            if i < len(self.action_items):
                item_widget = self.action_items[i]
                label = item_widget.findChild(QLabel, "action_text")
                button = item_widget.findChild(QPushButton, "action_button")

                if label:
                    label.setText(text)
                if button:
                    button.setEnabled(True)  # All buttons enabled when visible

                # Show/hide based on logic
                item_widget.setVisible(should_show)

    def _update_quality_metrics(self, stats):
        """Update quality metrics section"""
        # Average confidence
        conf = stats["avg_confidence"]
        stars = "⭐" * min(5, int(conf / 20))
        self.avg_confidence_label.setText(f"Average Confidence: {conf:.1f}% {stars}")

        # Error rate
        error_rate = stats["error_rate"]
        status = (
            "✅ Excellent" if error_rate < 1 else ("⚠️ Moderate" if error_rate < 5 else "❌ High")
        )
        self.error_rate_label.setText(f"Error Rate: {error_rate:.1f}% {status}")

        # Metadata completeness
        for field, widget in self.completeness_bars.items():
            percentage = stats["metadata_completeness"].get(field, 0)
            widget.label.setText(f"{field.replace('_', ' ').title()}: {percentage:.1f}%")
            widget.bar.setValue(int(percentage))

    def _update_document_insights(self, stats):
        """Update document insights section"""
        from ui.collection_status_helpers import create_distribution_bar

        # Summary stats
        self.docs_created_label.setText(f"Documents Created: {stats['documents_archived']}")
        self.pages_archived_label.setText(f"Pages Archived: {stats['total_archived_pages']}")

        avg_pages = (
            (stats["total_archived_pages"] / stats["documents_archived"])
            if stats["documents_archived"] > 0
            else 0
        )
        self.avg_pages_label.setText(f"Avg Pages per Document: {avg_pages:.1f}")

        self.bundle_acceptance_label.setText(
            f"Bundle Acceptance Rate: {stats['bundle_acceptance_rate']:.1f}%"
        )

        # Type distribution
        type_layout = self.type_distribution_container.layout
        self._clear_layout(type_layout)

        total_pages = stats["files_detected"]
        for doc_type, count in stats["type_distribution"].items():
            bar = create_distribution_bar(self.theme_colors, doc_type, count, total_pages)
            type_layout.addWidget(bar)

        # Company distribution
        company_layout = self.company_distribution_container.layout
        self._clear_layout(company_layout)

        for company, count in stats["company_distribution"].items():
            bar = create_distribution_bar(self.theme_colors, company, count, total_pages)
            company_layout.addWidget(bar)

    def _clear_layout(self, layout):
        """Clear all widgets from a layout"""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # Toolbar button handlers
    def _on_toolbar_start_analysis(self):
        """Start analysis from toolbar"""
        self._on_start_analysis()

    # Action item handlers
    def _on_start_analysis(self):
        """Start analysis from action items or toolbar"""
        if not self.analysis_service:
            from PyQt6.QtWidgets import QMessageBox

            # Create analysis service if not provided, using existing db instances
            if self.config_manager:
                from services.analysis_service import AnalysisService

                self.analysis_service = AnalysisService(
                    self.config_manager, self.analysis_db, self.metadata_db
                )
            else:
                QMessageBox.warning(
                    self, "Cannot Start Analysis", "No configuration manager available."
                )
                return

        # Start analysis in background thread
        self._start_analysis_internal()

    def _on_review_bundles(self):
        """Open bundle review window with suggested bundles"""
        from PyQt6.QtWidgets import QMessageBox

        # Get suggested bundles
        bundles = self.analysis_db.get_bundle_suggestions(status_filter="suggested")

        if not bundles:
            QMessageBox.information(
                self,
                "No Bundles",
                "No bundle suggestions found.\n\n"
                "Click 'Create Bundles' to generate suggestions first.",
            )
            return

        # Import and open ConvertImagesWindow
        try:
            from ui.gui import ConvertImagesWindow

            bundle_window = ConvertImagesWindow(
                parent=self,
                config_manager=self.config_manager,
                analysis_db=self.analysis_db,
            )
            bundle_window.show()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open bundle window: {str(e)}")

    def _on_view_errors(self):
        """Switch to File Grid tab and filter to errors"""
        self.tabs.setCurrentIndex(1)  # Switch to File Analysis Grid
        if hasattr(self.file_grid, "apply_quick_filter"):
            self.file_grid.apply_quick_filter("has_errors")

    def _on_create_bundles(self):
        """Generate bundle suggestions using BundlingService"""
        from PyQt6.QtWidgets import QMessageBox

        from services.bundling_service import BundlingService

        try:
            # Create bundling service
            bundling_service = BundlingService(self.analysis_db)

            # Generate recommendations
            bundles = bundling_service.generate_bundle_recommendations()

            # Refresh to show new bundles
            self._refresh_all()

            QMessageBox.information(
                self,
                "Bundles Created",
                f"Generated {len(bundles)} bundle suggestion(s).\n\n"
                "Click 'Review Bundles' to review them.",
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create bundles: {str(e)}")

    def _start_analysis_internal(self):
        """Start full directory scan via queue."""
        if self.analysis_worker.isRunning() and self.analysis_queue.get_current_job():
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Analysis Running", "Analysis is already in progress.")
            return

        # Initialize analysis tracking
        self._analysis_start_time = time.time()
        self._analysis_stats = {"analyzed": 0, "cached": 0, "errors": 0, "total_files": 0}

        # Create job for full directory scan
        job = AnalysisJob.create(
            job_type=JobType.SCAN_ALL,
            priority=JobPriority.NORMAL,
            file_paths=[],
            force_reanalysis=False,
        )

        self.analysis_queue.enqueue(job)
        self._update_toolbar_status("analyzing", "Starting analysis...")

        # Start worker if not already running
        if not self.analysis_worker.isRunning():
            self.analysis_worker.start()

    def _on_stop_analysis(self):
        """Stop current job gracefully, continue with queue."""
        if self.analysis_worker.isRunning():
            # Cancel current job only
            self._update_toolbar_status("canceling", "Canceling current job...")
            self.analysis_worker.cancel_current_job()

    def _on_abort_analysis(self):
        """Abort all jobs and clear queue."""
        from PyQt6.QtWidgets import QMessageBox

        if self.analysis_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Abort All Jobs",
                "Are you sure you want to abort all queued jobs?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Stop timer
                self._stop_progress_timer()
                # Clear entire queue
                self._update_toolbar_status("canceling", "Aborting all jobs...")
                self.analysis_queue.clear_queue()
                self.analysis_worker.cancel_current_job()
                # Reset stats
                self._analysis_stats = {"analyzed": 0, "cached": 0, "errors": 0, "total_files": 0}

    def _on_analysis_progress_update(self, status_text: str, current: int, total: int):
        """Handle progress updates from analysis thread"""
        # Start timer on first progress update
        if self._first_progress_update:
            self._start_progress_timer()

        # Update toolbar status (timer display handled by _update_progress_display)
        display_text = f"{status_text}"
        self._update_toolbar_status("analyzing", display_text, "")

        # Force immediate timer display update
        self._update_progress_display()

        # Stats are accumulated in _on_job_finished, not here.
        # This handler only updates the UI to show progress.

        # Refresh grid to show status changes
        # First progress update: refresh immediately to show "Analyzing" status
        # Subsequent updates: throttled to max once per second
        current_time = time.time()
        if self._first_progress_update or current_time - self._last_grid_refresh_time >= 1.0:
            self._refresh_file_grid()
            self._last_grid_refresh_time = current_time
            self._first_progress_update = False  # Clear flag after first refresh

    def _on_analysis_complete(self, stats: dict):
        """Handle analysis completion"""
        # Stop progress timer
        self._stop_progress_timer()

        # Update toolbar status
        total = stats.get("total_files", 0)
        analyzed = stats.get("analyzed", 0)
        errors = stats.get("errors", 0)

        if errors > 0:
            self._update_toolbar_status("error", f"Complete with {errors} error(s)")
        elif analyzed > 0:
            self._update_toolbar_status("success", f"Completed: {analyzed}/{total} files")
        else:
            self._update_toolbar_status("ready", "Ready")

        # Refresh all data
        self._refresh_all()

    def _on_re_analyze_requested(self, file_paths: list):
        """Handle re-analysis request from FileDetailsGrid context menu.

        Args:
            file_paths: List of file paths to re-analyze
        """
        if not file_paths:
            return

        # Update database status to "pending" for all queued files (waiting in queue)
        for file_path in file_paths:
            self.analysis_db.update_image_status(file_path, ImageStatus.PENDING.value)

        # Refresh grid to show status change immediately
        self._refresh_file_grid()

        # Create high-priority job for on-demand re-analysis
        job = AnalysisJob.create(
            job_type=JobType.ANALYZE_FILES,
            priority=JobPriority.HIGH,
            file_paths=file_paths,
            force_reanalysis=True,
        )

        self.analysis_queue.enqueue(job)

        # Update UI immediately
        self._update_toolbar_status(
            "analyzing", f"Queued {len(file_paths)} file(s) for re-analysis"
        )

        # Defer worker start by 100ms to give UI time to render the "pending" status
        # This ensures users see the status transition: pending → analyzing → analyzed
        from PyQt6.QtCore import QTimer

        def start_worker_if_needed():
            if not self.analysis_worker.isRunning():
                self.analysis_worker.start()

        QTimer.singleShot(100, start_worker_if_needed)

    def _on_job_started(self, job_id: str, description: str):
        """Worker started processing a job.

        Args:
            job_id: Unique job identifier
            description: Human-readable description
        """
        self._analysis_start_time = time.time()
        self._update_toolbar_status("analyzing", description)
        # Mark that we need to refresh on first progress update (to show "Analyzing" status)
        self._first_progress_update = True
        # Refresh grid immediately to show status change from "pending" to "analyzing"
        self._refresh_file_grid()
        self._last_grid_refresh_time = time.time()

    def _on_job_finished(self, job_id: str, stats: dict):
        """Worker finished a job.

        Args:
            job_id: Unique job identifier
            stats: Job statistics dict
        """
        # Accumulate stats
        self._analysis_stats["analyzed"] += stats.get("analyzed", 0)
        self._analysis_stats["cached"] += stats.get("cached", 0)
        self._analysis_stats["errors"] += stats.get("errors", 0)
        self._analysis_stats["total_files"] += stats.get("total_files", 0)

        # Refresh file grid to show updated analysis results
        self._refresh_file_grid()
        self._last_grid_refresh_time = time.time()

        # Check if more jobs pending
        pending = self.analysis_queue.get_pending_count()
        if pending > 0:
            self._update_toolbar_status(
                "analyzing", f"Processing queue ({pending} job(s) remaining)"
            )
        else:
            # Queue empty - delegate to existing completion handler
            self._on_analysis_complete(self._analysis_stats)

    def _on_job_error(self, job_id: str, error_message: str):
        """Worker encountered an error.

        Args:
            job_id: Unique job identifier
            error_message: Error details
        """
        from PyQt6.QtWidgets import QMessageBox

        self._get_logger().error(f"Job {job_id} error: {error_message}")
        QMessageBox.critical(self, "Analysis Error", f"Job failed:\n\n{error_message}")

        # Stop timer if no more jobs pending
        if self.analysis_queue.get_pending_count() == 0:
            self._stop_progress_timer()
            self._update_toolbar_status("error", "Job failed")

    def _on_queue_empty(self):
        """All queued jobs completed."""
        # Refresh all data
        self._refresh_all()

    def _update_toolbar_status(self, state: str, text: str = "", progress: str = ""):
        """
        Update toolbar status indicator and buttons.

        Args:
            state: "ready", "analyzing", "success", "error", "canceling"
            text: Status text to display
            progress: Optional progress info (e.g., "15/47 files")
        """
        if not hasattr(self, "status_indicator"):
            return

        colors = self.theme_colors

        # Update indicator color
        if state == "ready":
            color = colors["text_tertiary"]
            self.status_indicator.setStyleSheet(f"font-size: 14pt; color: {color};")
        elif state == "analyzing":
            color = "#3B82F6"  # Blue
            self.status_indicator.setStyleSheet(f"font-size: 14pt; color: {color};")
        elif state == "canceling":
            color = "#F59E0B"  # Orange/Amber - indicates pending cancellation
            self.status_indicator.setStyleSheet(f"font-size: 14pt; color: {color};")
        elif state == "success":
            color = "#10B981"  # Green
            self.status_indicator.setStyleSheet(f"font-size: 14pt; color: {color};")
        elif state == "error":
            color = "#EF4444"  # Red
            self.status_indicator.setStyleSheet(f"font-size: 14pt; color: {color};")

        # Update status text
        self.status_text.setText(text or state.capitalize())

        # Update progress info
        # Don't hide if timer is active (it will manage visibility)
        if progress:
            self.progress_info.setText(progress)
            self.progress_info.setVisible(True)
        elif not (self._progress_timer and self._progress_timer.isActive()):
            self.progress_info.setVisible(False)

        # Show/hide appropriate buttons
        is_running = state == "analyzing"
        is_canceling = state == "canceling"

        self.start_analysis_btn.setVisible(not is_running and not is_canceling)
        self.stop_analysis_btn.setVisible(is_running)
        self.abort_analysis_btn.setVisible(is_running)

        # Disable buttons during cancellation
        if is_canceling:
            self.stop_analysis_btn.setEnabled(False)
            self.abort_analysis_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
        else:
            self.stop_analysis_btn.setEnabled(True)
            self.abort_analysis_btn.setEnabled(True)
            self.refresh_btn.setEnabled(True)

    def _start_progress_timer(self):
        """Start timer for live progress updates."""
        # Get average processing time from database
        try:
            stats = self.analysis_db.get_analysis_statistics()
            avg_time_ms = stats.get("avg_processing_time_ms", 0)
            # Only use average if it's a reasonable value (not 0 or None)
            self._avg_processing_time_ms = avg_time_ms if avg_time_ms and avg_time_ms > 0 else None
            self._get_logger().debug(f"Average processing time: {self._avg_processing_time_ms}ms")
        except Exception as e:
            self._get_logger().warning(f"Failed to get average processing time: {e}")
            self._avg_processing_time_ms = None

        # Record job start time
        self._current_job_start_time = time.time()

        # Create and start timer if not already running
        if self._progress_timer is None:
            self._progress_timer = QTimer(self)
            self._progress_timer.timeout.connect(self._update_progress_display)

        if not self._progress_timer.isActive():
            self._progress_timer.start(1000)  # Update every second

    def _stop_progress_timer(self):
        """Stop the progress timer."""
        if self._progress_timer and self._progress_timer.isActive():
            self._progress_timer.stop()
        self._current_job_start_time = None

    def _update_progress_display(self):
        """Update the progress display with elapsed time and average."""
        if self._current_job_start_time is None:
            return

        # Calculate elapsed time
        elapsed_seconds = int(time.time() - self._current_job_start_time)

        # Format average time
        if self._avg_processing_time_ms:
            avg_seconds = int(self._avg_processing_time_ms / 1000)
            avg_text = f" (avg ~{avg_seconds}s)"
        else:
            avg_text = ""

        # Update progress info with timer
        if hasattr(self, "progress_info"):
            display_text = f"{elapsed_seconds}s{avg_text}"
            self.progress_info.setText(display_text)
            self.progress_info.setVisible(True)

    def _refresh_file_grid(self):
        """Refresh File Analysis Grid tab"""
        # Check if database connection is still valid
        if (
            not self.analysis_db
            or not hasattr(self.analysis_db, "connection")
            or not self.analysis_db.connection
        ):
            return  # Database is closed, skip refresh

        if hasattr(self, "file_grid"):
            try:
                # Get analyzed pages and transform to grid format
                data = self._transform_data_for_grid(self.analysis_db.get_analyzed_pages())
                self.file_grid.refresh_data(data)
            except Exception as e:
                # Log errors during shutdown (database may be closing)
                self._get_logger().debug(f"Error refreshing file grid during shutdown: {e}")

    def _transform_data_for_grid(self, db_data):
        """
        Transform database data to grid format with all required fields.

        Data now comes from image_files table (primary) with LEFT JOIN to analysis_results,
        so unanalyzed images will have NULL analysis fields.
        """
        import os
        from datetime import datetime

        transformed = []
        for row in db_data:
            file_path = row.get("file_path", "")
            has_analysis = row.get("analysis_id") is not None

            # Determine status - ALWAYS use image_files.status as source of truth
            image_status = row.get("status", "registered")
            status_mapping = {
                ImageStatus.REGISTERED.value: "Registered",
                ImageStatus.PENDING.value: "Pending",
                ImageStatus.ANALYZING.value: "Analyzing",
                ImageStatus.ANALYZED.value: "Analyzed",
                ImageStatus.BUNDLED.value: "Bundled",
                ImageStatus.DELETED.value: "Deleted",
            }
            status = status_mapping.get(image_status, image_status.title())

            # Override to "Failed" if analyzed but missing confidence score
            if (
                image_status == ImageStatus.ANALYZED.value
                and has_analysis
                and row.get("confidence_score") is None
            ):
                status = "Failed"

            # File metadata from image_files table (always available)
            file_size = row.get("file_size", 0)
            file_mtime = row.get("file_mtime", 0)
            modified_time = datetime.fromtimestamp(file_mtime) if file_mtime else None

            # Build transformed row
            transformed_row = {
                "filename": row.get(
                    "filename", os.path.basename(file_path) if file_path else "Unknown"
                ),
                "full_path": file_path,
                "status": status,
                # Analysis fields (NULL if not analyzed yet)
                "confidence": (row.get("confidence_score", 0) * 100)
                if row.get("confidence_score") is not None
                else None,
                "company": row.get("company", ""),
                "document_type": row.get("document_type", ""),
                "document_date": row.get("document_date", ""),
                "page_number": row.get("page_number"),
                "total_pages": row.get("total_pages"),
                "rotation": row.get(
                    "rotation", 0
                ),  # Use image_files.rotation (authoritative source)
                "file_size": file_size,
                "modified_time": modified_time,
                "analysis_time": row.get("analyzed_at"),
                "processing_duration": (row.get("processing_time_ms", 0) / 1000.0)
                if row.get("processing_time_ms")
                else None,
                "model_used": row.get("model_name", ""),
                "provider": row.get("provider_name", ""),
                "cache_hit": bool(
                    row.get("is_cached", False)
                ),  # Calculated via subquery in get_all_with_analysis()
                "error_message": "",  # TODO: Get from errors table
                "file_hash": row.get("file_hash", ""),
                "raw_response": row.get(
                    "response_text", ""
                ),  # Migration 16: renamed from raw_response
                "response_text": row.get("response_text", ""),  # New name after Migration 16
                "prompt_text": row.get("prompt_text", ""),
                "tax_related": bool(row.get("tax_related", False)),
                "is_blank": bool(row.get("is_blank", False)),
            }

            transformed.append(transformed_row)

        return transformed

    def _refresh_document_details(self):
        """Refresh PDF Details tab with generated PDFs"""
        # Check if database connection is still valid
        if (
            not self.analysis_db
            or not hasattr(self.analysis_db, "connection")
            or not self.analysis_db.connection
        ):
            return  # Database is closed, skip refresh

        if not hasattr(self, "document_table"):
            return  # Tab not yet created

        try:
            # Query document_bundles table for completed bundles with PDFs
            # Get metadata from first image in bundle (they should all match)
            cursor = self.analysis_db.connection.connection.cursor()
            cursor.execute("""
                SELECT
                    b.id,
                    pf.pdf_path,
                    b.created_at,
                    COUNT(bi.image_file_id) as page_count,
                    m.company,
                    m.document_type,
                    m.document_date
                FROM document_bundles b
                INNER JOIN pdf_files pf ON b.id = pf.bundle_id
                LEFT JOIN bundle_images bi ON b.id = bi.bundle_id
                LEFT JOIN image_files img ON bi.image_file_id = img.id AND bi.sequence_order = 1
                LEFT JOIN metadata m ON img.id = m.image_file_id
                WHERE b.status = 'completed'
                GROUP BY b.id, pf.pdf_path, b.created_at, m.company, m.document_type, m.document_date
                ORDER BY b.created_at DESC
            """)
            rows = cursor.fetchall()

            # Clear existing rows
            self.document_table.setRowCount(0)

            # Populate table
            for row in rows:
                bundle_id, pdf_path, created_at, page_count, company, doc_type, doc_date = row

                # Format created_at timestamp
                if created_at:
                    from datetime import datetime

                    try:
                        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        created_str = dt.strftime("%Y-%m-%d %I:%M:%S %p")
                    except (ValueError, AttributeError):
                        created_str = str(created_at)
                else:
                    created_str = ""

                # Add row to table
                row_position = self.document_table.rowCount()
                self.document_table.insertRow(row_position)

                # PDF Filename
                pdf_filename = os.path.basename(pdf_path) if pdf_path else ""
                filename_item = QTableWidgetItem(pdf_filename)
                filename_item.setData(Qt.ItemDataRole.UserRole, pdf_path)  # Store full path
                self.document_table.setItem(row_position, 0, filename_item)

                # Company
                company_item = QTableWidgetItem(company or "")
                self.document_table.setItem(row_position, 1, company_item)

                # Document Type
                type_item = QTableWidgetItem(doc_type or "")
                self.document_table.setItem(row_position, 2, type_item)

                # Date
                date_item = QTableWidgetItem(doc_date or "")
                self.document_table.setItem(row_position, 3, date_item)

                # Pages
                pages_item = QTableWidgetItem(str(page_count))
                self.document_table.setItem(row_position, 4, pages_item)

                # Created At
                created_item = QTableWidgetItem(created_str)
                self.document_table.setItem(row_position, 5, created_item)

        except Exception as e:
            # Log errors during document details refresh (database may be closing)
            self._get_logger().error(f"Error refreshing document details: {e}", exc_info=True)

    def _on_document_table_double_click(self, item):
        """Handle double-click on document table to open PDF"""
        # Get PDF path from first column (stored in UserRole data)
        row = item.row()
        filename_item = self.document_table.item(row, 0)
        if not filename_item:
            return

        pdf_path = filename_item.data(Qt.ItemDataRole.UserRole)
        if not pdf_path or not os.path.exists(pdf_path):
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "File Not Found", f"PDF file not found:\n{pdf_path}")
            return

        # Open PDF in default viewer
        try:
            if os.name == "nt":  # Windows
                os.startfile(pdf_path)
            elif os.name == "posix":  # macOS and Linux
                subprocess.run(["open" if os.uname().sysname == "Darwin" else "xdg-open", pdf_path])
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(self, "Error Opening PDF", f"Failed to open PDF:\n{str(e)}")

    def closeEvent(self, event):  # noqa: N802
        """Handle window close"""
        # Stop timers
        if self.auto_refresh_timer:
            self.auto_refresh_timer.stop()
        self._stop_progress_timer()

        # Disconnect signals from worker to prevent callbacks during shutdown
        if self.analysis_worker:
            try:
                self.analysis_worker.job_started.disconnect()
                self.analysis_worker.progress.disconnect()
                self.analysis_worker.job_finished.disconnect()
                self.analysis_worker.error.disconnect()
                self.analysis_worker.queue_empty.disconnect()
            except (TypeError, RuntimeError):
                pass  # Already disconnected or never connected

            # Stop worker if running
            if self.analysis_worker.isRunning():
                self.analysis_worker.stop()
                self.analysis_worker.wait(2000)  # Wait max 2 seconds

        # Close database connection only if we own it (not injected)
        if self._owns_analysis_db and self.analysis_db:
            self.analysis_db.close()
        if self._owns_metadata_db and self.metadata_db:
            self.metadata_db.close()

        super().closeEvent(event)
