"""
Analysis Status Window
Provides visibility into analysis service status, recent runs, and historical results.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QLineEdit, QComboBox, QProgressBar, QTextEdit, QMessageBox,
    QAbstractItemView, QFrame, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from analysis_db import AnalysisDB
from styles import (
    show_information, show_warning, show_question, show_critical,
    Colors, get_primary_button_style, get_danger_button_style, get_success_button_style
)
import json
import os


class AnalysisStatusWindow(QDialog):
    """Main Analysis Status Window with 4 tabs"""

    # Signals
    retry_failed_requested = pyqtSignal()

    def __init__(self, parent=None, analysis_service=None, config_manager=None, auto_start_analysis=False):
        super().__init__(parent)
        self.analysis_db = AnalysisDB()
        self.analysis_service = analysis_service
        self.config_manager = config_manager
        self.auto_refresh_timer = None
        self.analysis_worker = None
        self.analysis_start_time = None
        self.elapsed_timer = None

        self._init_ui()
        self._load_all_data()

        # Auto-start analysis if requested
        if auto_start_analysis:
            # Use QTimer to defer start until after window is shown
            QTimer.singleShot(100, self._start_analysis)

    def _init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Analysis Status")
        self.setMinimumSize(900, 700)
        self.setModal(False)

        # Apply consistent styling
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #F9FAFB;
            }}
            QTabWidget::pane {{
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                background-color: white;
                top: -1px;
            }}
            QTabBar::tab {{
                background-color: #F3F4F6;
                color: #6B7280;
                border: 1px solid #E5E7EB;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 20px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: white;
                color: {Colors.PRIMARY};
                border-color: #E5E7EB;
                border-bottom: 1px solid white;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: #E5E7EB;
            }}
            QPushButton {{
                background-color: {Colors.PRIMARY};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 10pt;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: {Colors.PRIMARY_HOVER};
            }}
            QPushButton:disabled {{
                background-color: #9CA3AF;
            }}
            QLineEdit, QComboBox {{
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 6px;
                background-color: white;
            }}
            QTableWidget {{
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                background-color: white;
                gridline-color: #E5E7EB;
            }}
            QHeaderView::section {{
                background-color: #F3F4F6;
                color: #374151;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #D1D5DB;
                font-weight: bold;
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # Header with refresh button
        header_layout = QHBoxLayout()

        title_label = QLabel("Analysis Status")
        title_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #1F2937; background-color: transparent;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._refresh_all)
        header_layout.addWidget(self.refresh_button)

        main_layout.addLayout(header_layout)

        # Tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create tabs
        self.current_tab = self._create_current_status_tab()
        self.recent_runs_tab = self._create_recent_runs_tab()
        self.file_details_tab = self._create_file_details_tab()
        self.statistics_tab = self._create_statistics_tab()

        self.tab_widget.addTab(self.current_tab, "Current Status")
        self.tab_widget.addTab(self.recent_runs_tab, "Recent Runs")
        self.tab_widget.addTab(self.file_details_tab, "File Details")
        self.tab_widget.addTab(self.statistics_tab, "Statistics")

        # Footer buttons
        footer_layout = QHBoxLayout()

        self.export_button = QPushButton("Export Report")
        self.export_button.clicked.connect(self._export_report)
        footer_layout.addWidget(self.export_button)

        self.clear_history_button = QPushButton("Clear History")
        self.clear_history_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.DANGER};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 10pt;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: {Colors.DANGER_HOVER};
            }}
        """)
        self.clear_history_button.clicked.connect(self._clear_history)
        footer_layout.addWidget(self.clear_history_button)

        footer_layout.addStretch()

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        footer_layout.addWidget(close_button)

        main_layout.addLayout(footer_layout)

    def _create_current_status_tab(self) -> QWidget:
        """Create the Current Status tab"""
        widget = QWidget()
        widget.setStyleSheet("QWidget { background-color: white; }")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Status indicator
        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {Colors.GRAY_500};")
        layout.addWidget(self.status_label)

        # Info frame
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #F3F4F6;
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        info_layout = QVBoxLayout(info_frame)

        self.current_info_label = QLabel("No analysis currently running.")
        self.current_info_label.setStyleSheet("color: #374151; font-size: 11pt;")
        self.current_info_label.setWordWrap(True)
        info_layout.addWidget(self.current_info_label)

        layout.addWidget(info_frame)

        # Active analysis frame (initially hidden)
        self.active_analysis_frame = QFrame()
        self.active_analysis_frame.setVisible(False)
        self.active_analysis_frame.setStyleSheet("""
            QFrame {
                background-color: #F0F9FF;
                border: 1px solid #BFDBFE;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        active_layout = QVBoxLayout(self.active_analysis_frame)

        # Current file label
        self.current_file_label = QLabel("Current: --")
        self.current_file_label.setStyleSheet(f"color: {Colors.PRIMARY}; font-size: 10pt; font-weight: bold;")
        self.current_file_label.setWordWrap(True)
        active_layout.addWidget(self.current_file_label)

        # Progress bar
        self.current_progress_bar = QProgressBar()
        self.current_progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                text-align: center;
                background-color: white;
                height: 24px;
            }}
            QProgressBar::chunk {{
                background-color: {Colors.PRIMARY};
            }}
        """)
        active_layout.addWidget(self.current_progress_bar)

        # Real-time stats label
        self.realtime_stats_label = QLabel("Analyzed: 0 | Cached: 0 | Errors: 0")
        self.realtime_stats_label.setStyleSheet("color: #374151; font-size: 10pt;")
        active_layout.addWidget(self.realtime_stats_label)

        # Elapsed time label
        self.elapsed_time_label = QLabel("Elapsed: 0s")
        self.elapsed_time_label.setStyleSheet("color: #6B7280; font-size: 9pt;")
        active_layout.addWidget(self.elapsed_time_label)

        layout.addWidget(self.active_analysis_frame)

        # Action buttons
        button_layout = QHBoxLayout()

        self.start_analysis_button = QPushButton("Start Analysis")
        self.start_analysis_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.SUCCESS};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 10pt;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: {Colors.SUCCESS_HOVER};
            }}
            QPushButton:disabled {{
                background-color: #9CA3AF;
            }}
        """)
        self.start_analysis_button.clicked.connect(self._start_analysis)
        button_layout.addWidget(self.start_analysis_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.DANGER};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 10pt;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: {Colors.DANGER_HOVER};
            }}
        """)
        self.cancel_button.clicked.connect(self._cancel_analysis)
        self.cancel_button.setVisible(False)
        button_layout.addWidget(self.cancel_button)

        self.retry_failed_button = QPushButton("Retry Failed")
        self.retry_failed_button.clicked.connect(self._retry_failed)
        self.retry_failed_button.setEnabled(False)
        button_layout.addWidget(self.retry_failed_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        layout.addStretch()

        return widget

    def _create_recent_runs_tab(self) -> QWidget:
        """Create the Recent Runs tab"""
        widget = QWidget()
        widget.setStyleSheet("QWidget { background-color: white; }")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        label = QLabel("Recent Analysis Runs")
        label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #1F2937;")
        layout.addWidget(label)

        # Scroll area for runs
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.runs_container = QWidget()
        self.runs_layout = QVBoxLayout(self.runs_container)
        self.runs_layout.setSpacing(10)
        self.runs_layout.addStretch()

        scroll.setWidget(self.runs_container)
        layout.addWidget(scroll)

        return widget

    def _create_file_details_tab(self) -> QWidget:
        """Create the File Details tab"""
        widget = QWidget()
        widget.setStyleSheet("QWidget { background-color: white; }")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Filter controls
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        # Filter label
        filter_label = QLabel("Filter:")
        filter_label.setStyleSheet("color: #374151; font-size: 10pt; font-weight: 600; background-color: transparent;")
        filter_layout.addWidget(filter_label)

        # Filter combo box
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Analyzed", "Cached", "Failed"])
        self.filter_combo.currentTextChanged.connect(self._apply_file_filter)
        self.filter_combo.setMinimumWidth(120)
        self.filter_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: white;
                color: #1F2937;
                font-size: 10pt;
            }
            QComboBox:hover {
                border-color: #3B82F6;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #D1D5DB;
                background-color: white;
                color: #1F2937;
                selection-background-color: #3B82F6;
                selection-color: white;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 6px 10px;
                min-height: 24px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #EFF6FF;
                color: #1F2937;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #3B82F6;
                color: white;
            }
        """)
        filter_layout.addWidget(self.filter_combo)

        filter_layout.addSpacing(20)

        # Search label
        search_label = QLabel("Search:")
        search_label.setStyleSheet("color: #374151; font-size: 10pt; font-weight: 600; background-color: transparent;")
        filter_layout.addWidget(search_label)

        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search filename...")
        self.search_input.textChanged.connect(self._apply_file_filter)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: white;
                color: #1F2937;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border-color: #3B82F6;
                outline: none;
            }
        """)
        filter_layout.addWidget(self.search_input, 1)

        layout.addLayout(filter_layout)

        # Table
        self.files_table = QTableWidget()
        self.files_table.setColumnCount(4)
        self.files_table.setHorizontalHeaderLabels(["File", "Status", "Details", "Date"])
        self.files_table.horizontalHeader().setStretchLastSection(False)
        self.files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.files_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.files_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.files_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.files_table.setColumnWidth(1, 100)
        self.files_table.setColumnWidth(2, 100)
        self.files_table.setColumnWidth(3, 150)
        self.files_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.files_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.files_table.doubleClicked.connect(self._show_file_details)
        layout.addWidget(self.files_table)

        # Count label
        self.file_count_label = QLabel("Showing 0 of 0 files")
        self.file_count_label.setStyleSheet("color: #6B7280; font-size: 9pt;")
        layout.addWidget(self.file_count_label)

        return widget

    def _create_statistics_tab(self) -> QWidget:
        """Create the Statistics tab"""
        widget = QWidget()
        widget.setStyleSheet("QWidget { background-color: white; }")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        stats_container = QWidget()
        stats_layout = QVBoxLayout(stats_container)
        stats_layout.setSpacing(20)

        # Overall summary section
        summary_label = QLabel("Overall Summary")
        summary_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #1F2937;")
        stats_layout.addWidget(summary_label)

        self.summary_text = QLabel()
        self.summary_text.setStyleSheet("""
            QLabel {
                background-color: #F3F4F6;
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                padding: 15px;
                color: #374151;
                font-size: 10pt;
            }
        """)
        self.summary_text.setWordWrap(True)
        stats_layout.addWidget(self.summary_text)

        # Document type breakdown section
        breakdown_label = QLabel("Document Type Breakdown")
        breakdown_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #1F2937;")
        stats_layout.addWidget(breakdown_label)

        self.breakdown_container = QWidget()
        self.breakdown_layout = QVBoxLayout(self.breakdown_container)
        self.breakdown_layout.setSpacing(5)
        stats_layout.addWidget(self.breakdown_container)

        stats_layout.addStretch()

        scroll.setWidget(stats_container)
        layout.addWidget(scroll)

        return widget

    def _load_all_data(self):
        """Load data for all tabs"""
        self._refresh_current_status()
        self._refresh_recent_runs()
        self._refresh_file_details()
        self._refresh_statistics()

    def _refresh_all(self):
        """Refresh all tabs"""
        self._load_all_data()

    def _refresh_current_status(self):
        """Refresh Current Status tab"""
        # Get last analysis run
        runs = self.analysis_db.get_recent_runs(limit=1)

        if not runs:
            self.status_label.setText("Status: Idle")
            self.status_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #6B7280;")
            self.current_info_label.setText("No analysis has been run yet.")
            self.current_progress_bar.setVisible(False)
        else:
            run = runs[0]
            timestamp = datetime.fromisoformat(run['timestamp'])
            time_ago = self._format_relative_time(timestamp)

            self.status_label.setText("Status: Idle")
            self.status_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #059669;")

            info_text = f"""Last analysis: {time_ago}
• {run['total_files']} files processed
• {run['analyzed']} newly analyzed
• {run['cached']} from cache ({int(run['cached']/run['total_files']*100) if run['total_files'] > 0 else 0}%)
• {run['errors']} errors
• Completed in {self._format_duration(run['duration_seconds'])}"""

            self.current_info_label.setText(info_text)
            self.current_progress_bar.setVisible(False)

        # Check for failed analyses
        failed = self.analysis_db.get_failed_analyses()
        self.retry_failed_button.setEnabled(len(failed) > 0)

    def _refresh_recent_runs(self):
        """Refresh Recent Runs tab"""
        # Clear existing runs
        while self.runs_layout.count() > 1:  # Keep the stretch
            item = self.runs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        runs = self.analysis_db.get_recent_runs(limit=10)

        for run in runs:
            run_widget = self._create_run_widget(run)
            self.runs_layout.insertWidget(self.runs_layout.count() - 1, run_widget)

        if not runs:
            no_data = QLabel("No analysis runs found.")
            no_data.setStyleSheet("color: #6B7280; font-size: 11pt; padding: 20px;")
            no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.runs_layout.insertWidget(0, no_data)

    def _refresh_file_details(self):
        """Refresh File Details tab - show both successful and failed analyses"""
        self.files_table.setRowCount(0)

        # Get successfully analyzed files
        files = self.analysis_db.get_analyzed_pages()

        # Get recent runs to find failed files
        recent_runs = self.analysis_db.get_recent_runs(limit=1)
        failed_files = []

        if recent_runs and recent_runs[0].get('errors', 0) > 0:
            # Get errors from most recent run
            errors = self.analysis_db.get_run_errors(recent_runs[0]['run_id'])
            for error in errors:
                failed_files.append({
                    'file_path': error['file_path'],
                    'status': 'Failed',
                    'error_message': error.get('error_message', 'Unknown error'),
                    'error_at': error.get('error_at'),
                    'analyzed_at': error.get('error_at')
                })

        # Combine successful and failed files
        self.all_files = files + failed_files  # Store for filtering
        self._apply_file_filter()

    def _refresh_statistics(self):
        """Refresh Statistics tab"""
        stats = self.analysis_db.get_analysis_statistics()

        # Format summary
        summary = f"""Total Files Analyzed: {stats['total_files']}
Total Analysis Runs: {stats['total_runs']}
Success Rate: {stats['success_rate']:.1f}%
Average Confidence: {stats['avg_confidence']*100:.1f}%

Cache Hit Rate: {stats['cache_hit_rate']:.1f}% ({stats['cached_files']} / {stats['total_files']})
Total Processing Time: {self._format_duration(stats['total_processing_time_ms']//1000)}
Average Time per Page: {stats['avg_processing_time_ms']/1000:.1f} seconds"""

        self.summary_text.setText(summary)

        # Document type breakdown
        breakdown = self.analysis_db.get_document_type_breakdown()

        # Clear existing breakdown
        while self.breakdown_layout.count() > 0:
            item = self.breakdown_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if breakdown:
            total = sum(breakdown.values())
            for doc_type, count in breakdown.items():
                percentage = (count / total * 100) if total > 0 else 0
                bar_widget = self._create_breakdown_bar(doc_type, count, percentage)
                self.breakdown_layout.addWidget(bar_widget)
        else:
            no_data = QLabel("No document data available.")
            no_data.setStyleSheet("color: #6B7280; font-size: 10pt;")
            self.breakdown_layout.addWidget(no_data)

    def _apply_file_filter(self):
        """Apply filter and search to file table"""
        if not hasattr(self, 'all_files'):
            return

        filter_type = self.filter_combo.currentText()
        search_text = self.search_input.text().lower()

        filtered_files = []
        for file_data in self.all_files:
            # Determine file status
            is_failed = file_data.get('status') == 'Failed'
            is_cached = file_data.get('is_cached', False)
            is_analyzed = not is_failed and not is_cached

            # Apply type filter
            if filter_type == "Analyzed" and not is_analyzed:
                continue
            elif filter_type == "Cached" and not is_cached:
                continue
            elif filter_type == "Failed" and not is_failed:
                continue

            # Apply search filter
            file_path = file_data.get('file_path', '')
            if search_text and file_path and search_text not in file_path.lower():
                continue

            filtered_files.append(file_data)

        # Populate table
        self.files_table.setRowCount(len(filtered_files))

        for row, file_data in enumerate(filtered_files):
            # File name - handle None or empty paths
            file_path = file_data.get('file_path', '')
            if not file_path:
                filename = 'Unknown'
                full_path = 'Unknown path'
            else:
                try:
                    filename = os.path.basename(file_path)
                    full_path = file_path
                except Exception as e:
                    filename = str(file_path)
                    full_path = str(file_path)

            file_item = QTableWidgetItem(filename)
            file_item.setToolTip(full_path)  # Full path in tooltip
            file_item.setData(Qt.ItemDataRole.UserRole, file_data)  # Store data for details
            self.files_table.setItem(row, 0, file_item)

            # Status
            if file_data.get('status') == 'Failed':
                status = "❌ Failed"
                color = QColor("#DC2626")
            elif file_data.get('is_cached', False):
                status = "⚡ Cached"
                color = QColor("#6B7280")
            else:
                status = "✓ Analyzed"
                color = QColor("#059669")

            status_item = QTableWidgetItem(status)
            status_item.setForeground(color)
            self.files_table.setItem(row, 1, status_item)

            # Confidence (or error message for failed files)
            if file_data.get('status') == 'Failed':
                error_msg = file_data.get('error_message', 'Unknown error')
                # Truncate long error messages
                if len(error_msg) > 50:
                    conf_text = error_msg[:47] + "..."
                else:
                    conf_text = error_msg
                conf_item = QTableWidgetItem(conf_text)
                conf_item.setToolTip(error_msg)  # Full error in tooltip
                conf_item.setForeground(QColor("#DC2626"))
            else:
                confidence = file_data.get('confidence_score')
                if confidence is not None:
                    conf_text = f"{confidence*100:.0f}%"
                else:
                    conf_text = "--"
                conf_item = QTableWidgetItem(conf_text)
            self.files_table.setItem(row, 2, conf_item)

            # Date
            date_str = file_data.get('analyzed_at', '')
            if date_str:
                date = datetime.fromisoformat(date_str)
                date_text = self._format_relative_time(date)
            else:
                date_text = "Unknown"
            date_item = QTableWidgetItem(date_text)
            self.files_table.setItem(row, 3, date_item)

            # Store full data in row
            file_item.setData(Qt.ItemDataRole.UserRole, file_data)

        self.file_count_label.setText(f"Showing {len(filtered_files)} of {len(self.all_files)} files")

    def _create_run_widget(self, run: Dict[str, Any]) -> QWidget:
        """Create widget for a single run"""
        widget = QFrame()
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        widget.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                padding: 12px;
            }}
            QFrame:hover {{
                background-color: #F9FAFB;
                border-color: {Colors.PRIMARY};
            }}
        """)

        # Make widget clickable to show error details
        widget.mousePressEvent = lambda event: self._show_run_errors(run)

        layout = QHBoxLayout(widget)

        # Status icon
        status_icon = QLabel("✓" if run['errors'] == 0 else "⚠")
        status_icon.setStyleSheet(f"font-size: 18pt; color: {'#059669' if run['errors'] == 0 else '#F59E0B'};")
        layout.addWidget(status_icon)

        # Info
        info_layout = QVBoxLayout()

        timestamp = datetime.fromisoformat(run['timestamp'])
        time_text = self._format_relative_time(timestamp)

        title = QLabel(time_text)
        title.setStyleSheet("font-weight: bold; color: #1F2937; font-size: 11pt;")
        info_layout.addWidget(title)

        details = QLabel(
            f"{run['total_files']} files • {run['analyzed']} analyzed • "
            f"{run['cached']} cached • {run['errors']} errors"
        )
        details.setStyleSheet("color: #6B7280; font-size: 9pt;")
        info_layout.addWidget(details)

        duration_text = QLabel(f"Duration: {self._format_duration(run['duration_seconds'])}")
        duration_text.setStyleSheet("color: #6B7280; font-size: 9pt;")
        info_layout.addWidget(duration_text)

        # Hint to click for error details
        if run['errors'] > 0:
            hint = QLabel("Click to view error details →")
            hint.setStyleSheet(f"color: {Colors.PRIMARY}; font-size: 9pt; font-style: italic;")
            info_layout.addWidget(hint)

        layout.addLayout(info_layout, 1)

        return widget

    def _create_breakdown_bar(self, doc_type: str, count: int, percentage: float) -> QWidget:
        """Create visual bar for document type breakdown"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 5)
        layout.setSpacing(3)

        # Label
        label = QLabel(f"{doc_type}: {count} ({percentage:.0f}%)")
        label.setStyleSheet("color: #374151; font-size: 10pt;")
        layout.addWidget(label)

        # Progress bar as visual indicator
        bar = QProgressBar()
        bar.setMaximum(100)
        bar.setValue(int(percentage))
        bar.setTextVisible(False)
        bar.setFixedHeight(20)
        bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                background-color: #F3F4F6;
            }}
            QProgressBar::chunk {{
                background-color: {Colors.PRIMARY};
            }}
        """)
        layout.addWidget(bar)

        return widget

    def _show_run_errors(self, run: Dict[str, Any]):
        """Show error details for a run"""
        if run['errors'] == 0:
            show_information(
                self,
                "No Errors",
                f"This run completed successfully with no errors.\n\n"
                f"Analyzed: {run['analyzed']}\nCached: {run['cached']}"
            )
            return

        # Get errors for this run
        errors = self.analysis_db.get_run_errors(run['run_id'])

        if not errors:
            show_warning(
                self,
                "No Error Details",
                f"This run had {run['errors']} errors, but error details are not available."
            )
            return

        # Create error details dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Error Details - {run['run_id']}")
        dialog.setMinimumSize(800, 600)

        layout = QVBoxLayout(dialog)

        # Header
        header = QLabel(f"{run['errors']} errors from analysis run")
        header.setStyleSheet("font-size: 14pt; font-weight: bold; padding: 10px;")
        layout.addWidget(header)

        # Error table
        error_table = QTableWidget()
        error_table.setColumnCount(2)
        error_table.setHorizontalHeaderLabels(["File", "Error Message"])
        error_table.horizontalHeader().setStretchLastSection(True)
        error_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        error_table.setColumnWidth(0, 300)
        error_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        error_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        error_table.setRowCount(len(errors))
        for i, error in enumerate(errors):
            # File path (basename only)
            file_item = QTableWidgetItem(os.path.basename(error['file_path']))
            file_item.setToolTip(error['file_path'])  # Full path in tooltip
            error_table.setItem(i, 0, file_item)

            # Error message
            error_msg = error.get('error_message', 'Unknown error')
            error_item = QTableWidgetItem(error_msg)
            error_item.setToolTip(error_msg)  # Full message in tooltip
            error_table.setItem(i, 1, error_item)

        layout.addWidget(error_table)

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)

        dialog.exec()

    def _show_file_details(self, index):
        """Show detailed file analysis dialog"""
        row = index.row()
        file_item = self.files_table.item(row, 0)
        file_data = file_item.data(Qt.ItemDataRole.UserRole)

        dialog = FileDetailsDialog(file_data, self)
        dialog.exec()

    def _retry_failed(self):
        """Retry failed analyses"""
        failed = self.analysis_db.get_failed_analyses()

        if not failed:
            show_information(self, "No Failures", "No failed analyses to retry.")
            return

        reply = show_question(
            self,
            "Retry Failed Analyses",
            f"Retry {len(failed)} failed analyses?"
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.retry_failed_requested.emit()
            show_information(
                self,
                "Retry Started",
                f"Retrying {len(failed)} failed files..."
            )

    def _export_report(self):
        """Export analysis report"""
        show_information(self, "Export Report", "Export functionality will be implemented in a future update.")

    def _clear_history(self):
        """Clear analysis history"""
        reply = show_question(
            self,
            "Clear History",
            "Clear all analysis history?\n\nThis cannot be undone."
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.analysis_db.purge_analysis_results()
            show_information(self, "History Cleared", "Analysis history has been cleared.")
            self._load_all_data()

    def _format_relative_time(self, dt: datetime) -> str:
        """Format datetime as relative time string"""
        now = datetime.now()
        diff = now - dt

        if diff.total_seconds() < 60:
            return "Just now"
        elif diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.days == 1:
            return f"Yesterday {dt.strftime('%I:%M %p')}"
        elif diff.days < 7:
            return f"{diff.days} days ago"
        else:
            return dt.strftime("%Y-%m-%d %I:%M %p")

    def _format_duration(self, seconds: int) -> str:
        """Format duration in seconds to human-readable string"""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"

    def _format_time(self, seconds: int) -> str:
        """Format seconds as 'Xs', 'Xm Ys', or 'Xh Ym'"""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"

    def _start_analysis(self):
        """Start analysis operation"""
        # Check if analysis already running
        if self.analysis_worker and self.analysis_worker.isRunning():
            show_warning(self, "Analysis Running", "Analysis is already in progress.")
            return

        # Ensure config_manager is available
        if not self.config_manager:
            show_critical(
                self,
                "Configuration Error",
                "Config manager not available. Cannot start analysis."
            )
            return

        # Update UI
        self.status_label.setText("Status: Running")
        self.status_label.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {Colors.WARNING};")
        self.current_info_label.setText("Analysis in progress...")

        # Show active analysis frame
        self.active_analysis_frame.setVisible(True)

        # Update buttons
        self.start_analysis_button.setEnabled(False)
        self.cancel_button.setVisible(True)

        # Start elapsed time timer
        import time
        self.analysis_start_time = time.time()
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.timeout.connect(self._update_elapsed_time)
        self.elapsed_timer.start(1000)  # Update every second

        # Create and start worker
        from gui import AnalysisWorker
        self.analysis_worker = AnalysisWorker(self.config_manager)
        self.analysis_worker.progress.connect(self._on_analysis_progress)
        self.analysis_worker.finished.connect(self._on_analysis_finished)
        self.analysis_worker.start()

    def _on_analysis_progress(self, status_text, current, total, stats):
        """Handle analysis progress updates"""
        # Update progress bar
        self.current_progress_bar.setMaximum(total)
        self.current_progress_bar.setValue(current)
        self.current_progress_bar.setFormat(f"{current}/{total} files")

        # Parse current filename from status_text (format: "Analyzing filename.png...")
        if status_text.startswith("Analyzing ") and "..." in status_text:
            filename = status_text.replace("Analyzing ", "").replace("...", "").strip()
            self.current_file_label.setText(f"Current: {filename}")
        else:
            self.current_file_label.setText(f"Current: {status_text}")

        # Update real-time stats
        analyzed = stats.get('analyzed', 0)
        cached = stats.get('cached', 0)
        errors = stats.get('errors', 0)
        self.realtime_stats_label.setText(f"Analyzed: {analyzed} | Cached: {cached} | Errors: {errors}")

        # Store stats for use in _on_analysis_finished
        if hasattr(self, 'analysis_worker') and self.analysis_worker:
            self.analysis_worker.current_stats = stats

    def _on_analysis_finished(self, stats):
        """Handle analysis completion"""
        # Stop elapsed timer
        if self.elapsed_timer:
            self.elapsed_timer.stop()
            self.elapsed_timer = None

        # Update status based on results
        total_files = stats.get('total_files', 0)
        errors = stats.get('errors', 0)
        analyzed = stats.get('analyzed', 0)
        cached = stats.get('cached', 0)

        if total_files == 0:
            self.status_label.setText("Status: Idle")
            self.status_label.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {Colors.GRAY_500};")
            self.current_info_label.setText("No files to analyze.")
        elif errors == total_files:
            self.status_label.setText("Status: Failed")
            self.status_label.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {Colors.DANGER};")
            self.current_info_label.setText(f"Analysis failed for all {total_files} files.")
        else:
            self.status_label.setText("Status: Complete")
            self.status_label.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {Colors.SUCCESS};")

            if errors > 0:
                message = f"Analysis complete: {analyzed + cached}/{total_files} pages ({errors} errors)"
            else:
                message = f"Analysis complete: {analyzed + cached}/{total_files} pages"
            self.current_info_label.setText(message)

        # Hide active analysis frame
        self.active_analysis_frame.setVisible(False)

        # Update buttons
        self.start_analysis_button.setEnabled(True)
        self.cancel_button.setVisible(False)

        # Clear worker reference
        self.analysis_worker = None

        # Refresh all data
        self._refresh_all()

    def _cancel_analysis(self):
        """Cancel ongoing analysis"""
        if not self.analysis_worker or not self.analysis_worker.isRunning():
            return

        reply = show_question(
            self,
            "Cancel Analysis?",
            "Analysis is in progress. Do you want to cancel?\n\n"
            "Already analyzed pages will be kept."
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.analysis_worker.cancel()
            # UI updates will happen via the finished signal

    def _update_elapsed_time(self):
        """Update elapsed time display"""
        import time
        if self.analysis_start_time:
            elapsed = int(time.time() - self.analysis_start_time)
            self.elapsed_time_label.setText(f"Elapsed: {self._format_time(elapsed)}")

    def closeEvent(self, event):
        """Handle window close"""
        # Stop timers
        if self.auto_refresh_timer:
            self.auto_refresh_timer.stop()
        if self.elapsed_timer:
            self.elapsed_timer.stop()

        # Cancel analysis worker if running
        if self.analysis_worker and self.analysis_worker.isRunning():
            self.analysis_worker.cancel()
            self.analysis_worker.wait()  # Wait for worker to finish

        self.analysis_db.close()
        super().closeEvent(event)


class FileDetailsDialog(QDialog):
    """Dialog showing detailed file analysis information"""

    def __init__(self, file_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.file_data = file_data
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI"""
        from styles import Colors, get_primary_button_style

        filename = os.path.basename(self.file_data.get('file_path', 'Unknown'))
        self.setWindowTitle(f"Analysis Details: {filename}")
        self.setMinimumSize(600, 500)

        # Apply dialog styling
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.WHITE};
            }}
            QLabel {{
                color: {Colors.GRAY_900};
                background-color: transparent;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # File information section
        file_section = QFrame()
        file_section.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.GRAY_50};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        file_layout = QVBoxLayout(file_section)
        file_info = QLabel(f"<b>File:</b> {self.file_data.get('file_path', 'Unknown')}")
        file_info.setWordWrap(True)
        file_info.setStyleSheet(f"background-color: transparent; color: {Colors.GRAY_900}; font-size: 11pt;")
        file_layout.addWidget(file_info)
        layout.addWidget(file_section)

        # Analysis information
        analyzed_at = self.file_data.get('analyzed_at', 'Unknown')
        provider = self.file_data.get('provider_name', 'Unknown')
        model = self.file_data.get('model_name', 'Unknown')
        confidence = self.file_data.get('confidence_score')
        processing_time = self.file_data.get('processing_time_ms', 0)

        # Build confidence string
        if confidence is not None:
            confidence_str = f"{confidence*100:.0f}%"
        else:
            confidence_str = "N/A"

        # Check if this is a failed file
        if self.file_data.get('status') == 'Failed':
            error_msg = self.file_data.get('error_message', 'Unknown error')
            analysis_info = f"""<b>Analysis Information:</b><br>
• Failed: {analyzed_at}<br>
• Error: {error_msg}<br>"""
        else:
            analysis_info = f"""<b>Analysis Information:</b><br>
• Analyzed: {analyzed_at}<br>
• Provider: {provider} ({model})<br>
• Processing Time: {processing_time/1000:.2f} seconds<br>
• Confidence: {confidence_str}"""

        # Analysis information section
        info_section = QFrame()
        info_section.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.GRAY_50};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        info_layout = QVBoxLayout(info_section)
        info_label = QLabel(analysis_info)
        info_label.setWordWrap(True)
        info_label.setStyleSheet(f"background-color: transparent; color: {Colors.GRAY_900}; font-size: 10pt;")
        info_layout.addWidget(info_label)
        layout.addWidget(info_section)

        # Extracted metadata
        metadata_label = QLabel("<b>Extracted Metadata:</b>")
        metadata_label.setStyleSheet(f"font-size: 11pt; margin-top: 10px;")
        layout.addWidget(metadata_label)

        metadata_text = QTextEdit()
        metadata_text.setReadOnly(True)
        metadata_text.setMaximumHeight(150)
        metadata_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Colors.GRAY_50};
                color: {Colors.GRAY_900};
                border: 1px solid {Colors.GRAY_300};
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
            }}
        """)

        extracted = self.file_data.get('extracted_metadata', {})
        if isinstance(extracted, str):
            try:
                extracted = json.loads(extracted)
            except:
                pass

        metadata_text.setPlainText(json.dumps(extracted, indent=2) if extracted else "No metadata")
        layout.addWidget(metadata_text)

        # Raw response
        raw_label = QLabel("<b>Raw Response:</b>")
        raw_label.setStyleSheet(f"font-size: 11pt; margin-top: 10px;")
        layout.addWidget(raw_label)

        raw_text = QTextEdit()
        raw_text.setReadOnly(True)
        raw_text.setPlainText(self.file_data.get('raw_response', 'No response data'))
        raw_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Colors.GRAY_50};
                color: {Colors.GRAY_900};
                border: 1px solid {Colors.GRAY_300};
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
            }}
        """)
        layout.addWidget(raw_text)

        # Buttons
        button_layout = QHBoxLayout()

        copy_button = QPushButton("Copy JSON")
        copy_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.GRAY_200};
                color: {Colors.GRAY_900};
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 600;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: {Colors.GRAY_300};
            }}
        """)
        copy_button.clicked.connect(self._copy_json)
        button_layout.addWidget(copy_button)

        button_layout.addStretch()

        close_button = QPushButton("Close")
        close_button.setStyleSheet(get_primary_button_style())
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

    def _copy_json(self):
        """Copy JSON to clipboard"""
        from PyQt6.QtWidgets import QApplication

        metadata = self.file_data.get('extracted_metadata', {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                pass

        json_text = json.dumps(metadata, indent=2)
        QApplication.clipboard().setText(json_text)

        show_information(self, "Copied", "JSON copied to clipboard.")
