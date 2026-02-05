"""
Analysis Status Window
Provides visibility into analysis service status with 2 tabs: Collection Status and File Analysis Grid.
"""

from PyQt6.QtCore import pyqtSignal
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
from ui.styles import Colors


class AnalysisStatusWindow(QDialog):
    """Main Analysis Status Window with 2 tabs: Collection Status and File Analysis Grid"""

    # Signals
    retry_failed_requested = pyqtSignal()

    def __init__(self, parent=None, analysis_db=None, config_manager=None):
        super().__init__(parent)
        self.analysis_db = analysis_db if analysis_db else AnalysisDB()
        self.config_manager = config_manager

        # Determine theme
        self.is_dark_mode = False
        if self.config_manager:
            theme = self.config_manager.get_setting("Theme", "theme", "light")
            self.is_dark_mode = theme == "dark"

        # Initialize attributes referenced in closeEvent
        self.auto_refresh_timer = None
        self.elapsed_timer = None
        self.analysis_worker = None

        self._init_ui()
        self._load_all_data()

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
        colors = self.theme_colors

        # Apply consistent styling
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors["bg_primary"]};
            }}
            QTabWidget::pane {{
                border: 1px solid {colors["border"]};
                border-radius: 8px;
                background-color: {colors["bg_secondary"]};
                top: -1px;
            }}
            QTabBar::tab {{
                background-color: {colors["tab_inactive_bg"]};
                color: {colors["text_tertiary"]};
                border: 1px solid {colors["border"]};
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 20px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {colors["tab_active_bg"]};
                color: {Colors.PRIMARY};
                border-color: {colors["border"]};
                border-bottom: 1px solid {colors["tab_active_bg"]};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {colors["tab_hover_bg"]};
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
            QLabel {{
                color: {colors["text_primary"]};
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # Toolbar with refresh button
        toolbar_layout = QHBoxLayout()
        toolbar_layout.addStretch()

        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self._refresh_all)
        toolbar_layout.addWidget(self.refresh_btn)

        main_layout.addLayout(toolbar_layout)

        # Create 2-tab layout
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_collection_status_tab(), "Collection Status")
        self.tabs.addTab(self._create_file_grid_tab(), "File Analysis Grid")

        main_layout.addWidget(self.tabs)

    def _create_collection_status_tab(self) -> QWidget:
        """Create the Collection Status tab - placeholder for now"""
        widget = QWidget()
        widget.setStyleSheet(
            f"QWidget {{ background-color: {self.theme_colors['bg_secondary']}; }}"
        )
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        placeholder_label = QLabel("Collection Status tab - Implementation in progress")
        placeholder_label.setStyleSheet(
            f"font-size: 14pt; font-weight: bold; color: {self.theme_colors['text_tertiary']};"
        )
        layout.addWidget(placeholder_label)

        info_label = QLabel(
            "This tab will display collection-level statistics and analysis status."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(f"color: {self.theme_colors['text_secondary']}; font-size: 11pt;")
        layout.addWidget(info_label)

        layout.addStretch()
        return widget

    def _create_file_grid_tab(self) -> QWidget:
        """Create the File Analysis Grid tab"""
        from file_details_grid import FileDetailsGrid

        self.file_grid = FileDetailsGrid(self)
        return self.file_grid

    def _load_all_data(self):
        """Load data for all tabs"""
        self._refresh_collection_status()
        self._refresh_file_grid()

    def _refresh_all(self):
        """Refresh all tabs"""
        self._refresh_collection_status()
        self._refresh_file_grid()

    def _refresh_collection_status(self):
        """Refresh Collection Status tab - placeholder implementation"""
        # To be implemented in next task
        pass

    def _refresh_file_grid(self):
        """Refresh File Analysis Grid tab"""
        if hasattr(self, "file_grid"):
            data = self.analysis_db.get_analyzed_pages_detailed()
            self.file_grid.refresh_data(data)

    def closeEvent(self, event):
        """Handle window close"""
        # Stop timers
        if self.auto_refresh_timer:
            self.auto_refresh_timer.stop()
        if self.elapsed_timer:
            self.elapsed_timer.stop()

        # Cancel analysis worker if running
        if self.analysis_worker and hasattr(self.analysis_worker, "isRunning"):
            if self.analysis_worker.isRunning():
                self.analysis_worker.cancel()
                self.analysis_worker.wait()  # Wait for worker to finish

        self.analysis_db.close()
        super().closeEvent(event)
