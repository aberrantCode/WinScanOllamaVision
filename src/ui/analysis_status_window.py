"""
Analysis Status Window
Provides visibility into analysis service status with 2 tabs: Collection Status and File Analysis Grid.
"""

import time

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from db.analysis_db import AnalysisDB


class AnalysisStatusWindow(QDialog):
    """Main Analysis Status Window with 2 tabs: Collection Status and File Analysis Grid"""

    # Signals
    retry_failed_requested = pyqtSignal()

    def __init__(
        self,
        parent=None,
        analysis_db=None,
        config_manager=None,
        analysis_service=None,
        auto_start_analysis: bool = False,
    ):
        super().__init__(parent)
        self.analysis_db = analysis_db if analysis_db else AnalysisDB()
        self.config_manager = config_manager
        self.analysis_service = analysis_service
        self._auto_start_analysis = auto_start_analysis

        # Determine theme
        self.is_dark_mode = False
        if self.config_manager:
            theme = self.config_manager.get_setting("Theme", "theme", "light")
            self.is_dark_mode = theme == "dark"

        # Initialize attributes referenced in closeEvent
        self.auto_refresh_timer = None
        self.analysis_worker = None
        self._analysis_thread = None
        self._analysis_start_time = None
        self._analysis_stats = {"analyzed": 0, "cached": 0, "errors": 0}

        self._init_ui()
        self._load_all_data()

        # If requested, start analysis using provided AnalysisService
        if self._auto_start_analysis and self.analysis_service:
            self._start_analysis_internal()

    def _get_theme_colors(self):
        """Return color palette based on current theme"""
        if self.is_dark_mode:
            return {
                "bg_primary": "#1E1E1E",
                "bg_secondary": "#2D2D2D",
                "bg_tertiary": "#3A3A3A",
                "text_primary": "#E0E0E0",
                "text_secondary": "#B0B0B0",
                "text_tertiary": "#808080",
                "border": "#4A4A4A",
                "tab_active_bg": "#2D2D2D",
                "tab_inactive_bg": "#1E1E1E",
                "tab_hover_bg": "#3A3A3A",
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
        self.setWindowTitle("Analysis Status")
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
        # Start button uses accent color for primary action
        self.start_analysis_btn = QPushButton("▶ Start Analysis")
        self.start_analysis_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                font-weight: 600;
                padding: 6px 16px;
                border: none;
            }
            QPushButton:hover {
                background-color: #2563EB;
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
                background-color: {self.theme_colors['bg_tertiary']};
                color: {self.theme_colors['text_primary']};
                border: 1px solid {self.theme_colors['border']};
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {self.theme_colors['tab_hover_bg']};
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
        self.tabs.addTab(self._create_collection_status_tab(), "Collection Status")
        self.tabs.addTab(self._create_file_grid_tab(), "File Analysis")

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
                background-color: {self.theme_colors['bg_secondary']};
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
        self.total_files_card = create_metric_card(self.theme_colors, "📄 Total Files", "0")
        self.total_files_card.setToolTip(
            "Total number of image files detected in all configured source directories"
        )

        self.analyzed_pages_card = create_metric_card(
            self.theme_colors, "✅ Analyzed Pages", "0 (0%)"
        )
        self.analyzed_pages_card.setToolTip(
            "Number of pages that have been analyzed by the LLM to extract metadata (percentage of total files)"
        )

        self.documents_card = create_metric_card(self.theme_colors, "📦 Documents", "0 (0p)")
        self.documents_card.setToolTip(
            "Number of multi-page documents created from bundled pages (total pages in parentheses)"
        )

        self.cache_card = create_metric_card(self.theme_colors, "⚡ Cache Hit Rate", "0%")
        self.cache_card.setToolTip(
            "Percentage of files served from cache (based on file hash) without re-analyzing"
        )

        self.avg_processing_card = create_metric_card(self.theme_colors, "⏱️ Avg Processing", "--")
        self.avg_processing_card.setToolTip(
            "Average time to process a single file and extract metadata (excludes cached files)"
        )

        self.total_files_card.setMinimumWidth(140)
        self.analyzed_pages_card.setMinimumWidth(160)
        self.documents_card.setMinimumWidth(140)
        self.cache_card.setMinimumWidth(140)
        self.avg_processing_card.setMinimumWidth(140)

        metrics_row.addWidget(self.total_files_card)
        metrics_row.addWidget(self.analyzed_pages_card)
        metrics_row.addWidget(self.documents_card)
        metrics_row.addWidget(self.cache_card)
        metrics_row.addWidget(self.avg_processing_card)

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
                background-color: {self.theme_colors['bg_secondary']};
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
        self.file_grid = FileDetailsGrid(self)
        layout.addWidget(self.file_grid)

        # Set container as scroll area widget
        scroll_area.setWidget(container)
        return scroll_area

    def _load_all_data(self):
        """Load data for all tabs"""
        self._refresh_collection_status()
        self._refresh_file_grid()

    def _refresh_all(self):
        """Refresh all tabs"""
        self._refresh_collection_status()
        self._refresh_file_grid()

    def _on_analysis_progress(self, status_text, current, total):
        """Handle progress updates from background analysis thread"""
        try:  # noqa: SIM105
            self.scan_status_label.setText(f"{status_text} ({current}/{total})")
        except Exception:
            pass  # Ignore errors during UI updates in callbacks

    def _on_analysis_finished(self, stats: dict):
        """Handle analysis finished event"""
        # Refresh displayed data
        try:
            self.scan_status_label.setText("Analysis complete")
            self._load_all_data()
        except Exception:
            pass

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
                print(f"Error refreshing collection status: {e}")

    def _calculate_collection_statistics(self):
        """Calculate comprehensive collection statistics from database"""
        import os

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

        # Files analyzed (non-cached)
        cursor.execute("SELECT COUNT(*) FROM analysis_results WHERE is_cached = 0")
        files_analyzed = cursor.fetchone()[0]

        # High confidence (>= 80%)
        cursor.execute(
            """
            SELECT COUNT(*) FROM analysis_results
            WHERE confidence_score >= 0.8
        """
        )
        high_confidence = cursor.fetchone()[0]

        # Pages bundled (count distinct file paths in bundles)
        cursor.execute(
            """
            SELECT COUNT(DISTINCT json_each.value)
            FROM document_bundles, json_each(document_bundles.file_paths)
            WHERE status IN ('suggested', 'accepted', 'completed')
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

        # Cache hit rate
        cursor.execute("SELECT COUNT(*) FROM analysis_results WHERE is_cached = 1")
        cached_count = cursor.fetchone()[0]
        cache_hit_rate = (cached_count / files_detected * 100) if files_detected > 0 else 0

        # Processing speed (last 100 analyses, non-cached)
        cursor.execute(
            """
            SELECT analyzed_at, processing_time_ms
            FROM analysis_results
            WHERE is_cached = 0 AND processing_time_ms IS NOT NULL
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

        # Average confidence score
        cursor.execute(
            "SELECT AVG(confidence_score) FROM analysis_results WHERE confidence_score IS NOT NULL"
        )
        avg_confidence_result = cursor.fetchone()[0]
        avg_confidence = (avg_confidence_result * 100) if avg_confidence_result else 0

        # Error rate (from analysis_errors table)
        cursor.execute("SELECT COUNT(*) FROM analysis_errors")
        error_count = cursor.fetchone()[0]
        error_rate = (error_count / files_detected * 100) if files_detected > 0 else 0

        # Metadata completeness
        metadata_completeness = {}
        for field in ["company", "document_type", "document_date", "page_number"]:
            cursor.execute(
                f"""
                SELECT COUNT(*) * 100.0 / (SELECT COUNT(*) FROM analysis_results)
                FROM analysis_results
                WHERE {field} IS NOT NULL AND {field} != ''
            """
            )
            result = cursor.fetchone()[0]
            metadata_completeness[field] = result if result else 0

        # Pending action items
        pending_bundles = len(self.analysis_db.get_bundle_suggestions(status_filter="suggested"))
        failed_files = error_count
        unbundled_files = files_detected - pages_bundled

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

        # Company distribution (top 5)
        cursor.execute(
            """
            SELECT company, COUNT(*) as count
            FROM analysis_results
            WHERE company IS NOT NULL AND company != ''
            GROUP BY company
            ORDER BY count DESC
            LIMIT 5
        """
        )
        company_dist = {row[0]: row[1] for row in cursor.fetchall()}

        # Total archived pages (sum of page counts from bundles)
        cursor.execute(
            """
            SELECT SUM(json_array_length(file_paths))
            FROM document_bundles
            WHERE status IN ('accepted', 'completed')
        """
        )
        archived_pages_result = cursor.fetchone()[0]
        total_archived_pages = archived_pages_result if archived_pages_result else 0

        # Average processing time (non-cached files only)
        cursor.execute(
            """
            SELECT AVG(processing_time_ms)
            FROM analysis_results
            WHERE is_cached = 0 AND processing_time_ms IS NOT NULL
        """
        )
        avg_processing_result = cursor.fetchone()[0]
        avg_processing_time_ms = avg_processing_result if avg_processing_result else 0

        return {
            "files_detected": files_detected,
            "files_analyzed": files_analyzed,
            "high_confidence": high_confidence,
            "pages_bundled": pages_bundled,
            "documents_archived": documents_archived,
            "cache_hit_rate": cache_hit_rate,
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
        }

    def _update_metric_cards(self, stats):
        """Update the 5 metric cards at the top"""
        # Total Files
        self.total_files_card.findChild(QLabel, "📄_total_files_value").setText(
            str(stats["files_detected"])
        )

        # Analyzed Pages (with percentage)
        analyzed_pct = (
            (stats["files_analyzed"] / stats["files_detected"] * 100)
            if stats["files_detected"] > 0
            else 0
        )
        self.analyzed_pages_card.findChild(QLabel, "✅_analyzed_pages_value").setText(
            f"{stats['files_analyzed']} ({analyzed_pct:.1f}%)"
        )

        # Documents (with page count)
        self.documents_card.findChild(QLabel, "📦_documents_value").setText(
            f"{stats['documents_archived']} ({stats['total_archived_pages']}p)"
        )

        # Cache Hit Rate
        self.cache_card.findChild(QLabel, "⚡_cache_hit_rate_value").setText(
            f"{stats['cache_hit_rate']:.1f}%"
        )

        # Average Processing Time
        avg_time = stats.get("avg_processing_time_ms", 0)
        if avg_time > 0:
            if avg_time >= 1000:
                # Show in seconds if >= 1000ms
                self.avg_processing_card.findChild(QLabel, "⏱️_avg_processing_value").setText(
                    f"{avg_time / 1000:.1f}s"
                )
            else:
                # Show in milliseconds
                self.avg_processing_card.findChild(QLabel, "⏱️_avg_processing_value").setText(
                    f"{avg_time:.0f}ms"
                )
        else:
            self.avg_processing_card.findChild(QLabel, "⏱️_avg_processing_value").setText("--")

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

            # Create analysis service if not provided
            if self.config_manager:
                from db.metadata_db import MetadataDB
                from services.analysis_service import AnalysisService

                metadata_db = MetadataDB()
                self.analysis_service = AnalysisService(
                    self.config_manager, self.analysis_db, metadata_db
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
        """Start analysis in background thread with real-time progress"""
        from PyQt6.QtCore import pyqtSignal

        if self._analysis_thread and self._analysis_thread.isRunning():
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Analysis Running", "Analysis is already in progress.")
            return

        # Update toolbar status
        self._update_toolbar_status("analyzing", "Starting analysis...")

        # Initialize analysis tracking
        self._analysis_start_time = time.time()
        self._analysis_stats = {"analyzed": 0, "cached": 0, "errors": 0}

        # Create analysis thread that creates its own database connections
        class _AnalysisThread(QThread):
            progress = pyqtSignal(str, int, int)
            finished = pyqtSignal(dict)

            def __init__(self, config_manager):
                super().__init__()
                self.config_manager = config_manager
                self._cancelled = False

            def run(self):
                # Create thread-local database connections
                from db.analysis_db import AnalysisDB
                from db.metadata_db import MetadataDB
                from services.analysis_service import AnalysisService

                try:
                    # Create new database instances for this thread
                    thread_analysis_db = AnalysisDB()
                    thread_metadata_db = MetadataDB()
                    thread_analysis_service = AnalysisService(
                        self.config_manager, thread_analysis_db, thread_metadata_db
                    )

                    def progress_callback(status_text, current, total):
                        if self._cancelled:
                            raise InterruptedError("Analysis cancelled by user")
                        self.progress.emit(status_text, current, total)

                    def abort_check():
                        return self._cancelled

                    stats = thread_analysis_service.scan_all_directories(
                        progress_callback=progress_callback,
                        incremental=True,
                        abort_check=abort_check,
                    )

                    # Close thread-local connections
                    thread_analysis_db.close()
                    thread_metadata_db.close()

                    self.finished.emit(stats)
                except InterruptedError:
                    self.finished.emit(
                        {
                            "total_files": 0,
                            "analyzed": 0,
                            "cached": 0,
                            "errors": 0,
                            "message": "Analysis cancelled",
                        }
                    )
                except Exception as e:
                    import traceback

                    self.finished.emit(
                        {
                            "total_files": 0,
                            "analyzed": 0,
                            "cached": 0,
                            "errors": 1,
                            "message": str(e) + "\n" + traceback.format_exc(),
                        }
                    )

            def cancel(self):
                self._cancelled = True

        # Instantiate and start with config manager (not service)
        self._analysis_thread = _AnalysisThread(self.config_manager)
        self._analysis_thread.progress.connect(self._on_analysis_progress_update)
        self._analysis_thread.finished.connect(self._on_analysis_complete)
        self._analysis_thread.start()

    def _on_stop_analysis(self):
        """Stop analysis gracefully (saves progress)"""
        if self._analysis_thread and self._analysis_thread.isRunning():
            # Immediately update UI to show cancellation is pending
            self._update_toolbar_status("canceling", "Canceling (waiting for current file)...")
            # Request cancellation
            self._analysis_thread.cancel()

    def _on_abort_analysis(self):
        """Abort analysis without saving"""
        from PyQt6.QtWidgets import QMessageBox

        if self._analysis_thread and self._analysis_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Abort Analysis",
                "Are you sure you want to abort without saving progress?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Immediately update UI to show cancellation is pending
                self._update_toolbar_status("canceling", "Aborting (waiting for current file)...")
                # Request cancellation
                self._analysis_thread.cancel()

    def _on_analysis_progress_update(self, status_text: str, current: int, total: int):
        """Handle progress updates from analysis thread"""
        # Update toolbar progress
        percentage = int((current / total) * 100) if total > 0 else 0
        self._update_toolbar_status(
            "analyzing", "Analyzing...", f"{current}/{total} files ({percentage}%)"
        )

        # Update stats (increment based on status text)
        if "cached" in status_text.lower():
            self._analysis_stats["cached"] += 1
        elif "error" in status_text.lower() or "failed" in status_text.lower():
            self._analysis_stats["errors"] += 1
        else:
            self._analysis_stats["analyzed"] += 1

    def _on_analysis_complete(self, stats: dict):
        """Handle analysis completion"""
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

        # Show completion message if there were actual results
        if total > 0:
            from PyQt6.QtWidgets import QMessageBox

            message = (
                f"Analysis Complete!\n\n"
                f"Total Files: {total}\n"
                f"Analyzed: {analyzed}\n"
                f"Cached: {stats.get('cached', 0)}\n"
                f"Errors: {errors}"
            )

            if stats.get("message"):
                message += f"\n\n{stats['message']}"

            QMessageBox.information(self, "Analysis Complete", message)

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
        if progress:
            self.progress_info.setText(progress)
            self.progress_info.setVisible(True)
        else:
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
            except Exception:
                # Silently ignore errors during shutdown
                pass

    def _transform_data_for_grid(self, db_data):
        """Transform database data to grid format with all required fields"""
        import os
        from datetime import datetime

        transformed = []
        for row in db_data:
            file_path = row.get("file_path", "")

            # Determine status
            if row.get("confidence_score") is None:
                status = "Failed"
            elif row.get("is_cached"):
                status = "Cached"
            else:
                status = "Analyzed"

            # Get file stats if file exists
            file_size = 0
            modified_time = None
            if file_path and os.path.exists(file_path):
                try:
                    file_stats = os.stat(file_path)
                    file_size = file_stats.st_size
                    modified_time = datetime.fromtimestamp(file_stats.st_mtime)
                except Exception:
                    pass

            # Build transformed row
            transformed_row = {
                "filename": os.path.basename(file_path) if file_path else "Unknown",
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
                "file_size": file_size,
                "modified_time": modified_time,
                "analysis_time": row.get("analyzed_at"),
                "processing_duration": (row.get("processing_time_ms", 0) / 1000.0)
                if row.get("processing_time_ms")
                else None,
                "model_used": row.get("model_name", ""),
                "provider": row.get("provider_name", ""),
                "cache_hit": bool(row.get("is_cached", False)),
                "error_message": "",  # TODO: Get from errors table
                "file_hash": row.get("file_hash", ""),
                "raw_response": row.get("raw_response", ""),
            }

            transformed.append(transformed_row)

        return transformed

    def closeEvent(self, event):  # noqa: N802
        """Handle window close"""
        # Stop timers
        if self.auto_refresh_timer:
            self.auto_refresh_timer.stop()

        # Disconnect signals from analysis thread to prevent callbacks during shutdown
        if self._analysis_thread:
            try:
                self._analysis_thread.progress.disconnect()
                self._analysis_thread.finished.disconnect()
            except (TypeError, RuntimeError):
                pass  # Already disconnected or never connected

            # Cancel if running
            if self._analysis_thread.isRunning():
                self._analysis_thread.cancel()
                self._analysis_thread.wait(2000)  # Wait max 2 seconds

        # Cancel analysis worker if running (legacy)
        if (
            self.analysis_worker
            and hasattr(self.analysis_worker, "isRunning")
            and self.analysis_worker.isRunning()
        ):
            self.analysis_worker.cancel()
            self.analysis_worker.wait(2000)  # Wait max 2 seconds

        # Close database connection
        if self.analysis_db:
            self.analysis_db.close()

        super().closeEvent(event)
