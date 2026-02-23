# mypy: disable-error-code=attr-defined
"""Database tab mixin for EnhancedSettingsWindow."""

from PyQt6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class _SettingsTabDatabaseMixin:
    """Mixin providing the Database settings tab."""

    def _create_database_tab(self) -> QWidget:
        """Tab 4: Database Management"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Statistics Group
        stats_group = QGroupBox("Database Statistics")
        stats_layout = QVBoxLayout(stats_group)

        stats_btn = QPushButton("View Statistics")
        stats_btn.setObjectName("compactButton")
        stats_btn.setToolTip(
            "Display current database statistics.\n\n"
            "Shows:\n"
            "• Total analyzed files and pages\n"
            "• Number of bundle suggestions\n"
            "• Cache hit rate and efficiency\n"
            "• Database file size and location\n\n"
            "Statistics are automatically refreshed when this tab is displayed."
        )
        stats_btn.clicked.connect(self._show_database_statistics)
        stats_layout.addWidget(stats_btn)

        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(150)
        self.stats_text.setToolTip(
            "Database statistics display.\n\n"
            "Real-time view of database contents including:\n"
            "• Analysis results count\n"
            "• Bundle suggestions count\n"
            "• Cache performance metrics\n"
            "• Storage usage information"
        )
        # Theme stylesheet handles styling - no inline styles needed
        stats_layout.addWidget(self.stats_text)

        layout.addWidget(stats_group)

        # Maintenance Group
        maintenance_group = QGroupBox("Database Maintenance")
        maintenance_layout = QGridLayout(maintenance_group)

        backup_btn = QPushButton("Create Backup")
        backup_btn.setObjectName("compactButton")
        backup_btn.setToolTip(
            "Create a timestamped backup of the database.\n\n"
            "Creates a backup copy of analysis.db and metadata.db in the\n"
            "AppData directory with timestamp (e.g., analysis_backup_20260207_143052.db).\n\n"
            "Use before performing maintenance operations or major updates.\n"
            "Backups can be manually restored by renaming the backup file."
        )
        backup_btn.clicked.connect(self._backup_database)
        maintenance_layout.addWidget(backup_btn, 0, 0)

        purge_cache_btn = QPushButton("Purge Cached Metadata")
        purge_cache_btn.setObjectName("compactButton")
        purge_cache_btn.setToolTip(
            "Remove all cached metadata from the database.\n\n"
            "Forces re-analysis of all files on next scan. Use when:\n"
            "• Prompt templates have been significantly changed\n"
            "• LLM provider or model has been updated\n"
            "• Previous analyses appear incorrect or incomplete\n\n"
            "Warning: Re-analysis may take time and consume LLM resources."
        )
        purge_cache_btn.clicked.connect(lambda: self._purge_data("cache"))
        maintenance_layout.addWidget(purge_cache_btn, 1, 0)

        purge_analysis_btn = QPushButton("Purge Analysis Results")
        purge_analysis_btn.setObjectName("compactButton")
        purge_analysis_btn.setToolTip(
            "Remove all LLM analysis results from the database.\n\n"
            "Deletes:\n"
            "• All page-level analysis data\n"
            "• Extracted metadata (company, document type, dates)\n"
            "• Confidence scores and analysis timestamps\n\n"
            "Use for a complete fresh start with existing files.\n"
            "Does not delete bundle suggestions or configuration."
        )
        purge_analysis_btn.clicked.connect(lambda: self._purge_data("analysis"))
        maintenance_layout.addWidget(purge_analysis_btn, 1, 1)

        purge_bundles_btn = QPushButton("Purge Bundle Suggestions")
        purge_bundles_btn.setObjectName("compactButton")
        purge_bundles_btn.setToolTip(
            "Remove all bundle suggestions from the database.\n\n"
            "Deletes generated bundle recommendations but keeps:\n"
            "• Individual page analysis results\n"
            "• Extracted metadata\n"
            "• Cache data\n\n"
            "Use when you want to regenerate bundles with different\n"
            "bundling logic or after editing metadata."
        )
        purge_bundles_btn.clicked.connect(lambda: self._purge_data("bundles"))
        maintenance_layout.addWidget(purge_bundles_btn, 2, 0)

        purge_all_btn = QPushButton("Purge All Data")
        purge_all_btn.setObjectName("dangerButton")
        purge_all_btn.setToolTip(
            "⚠️ DANGER: Remove ALL data from the database.\n\n"
            "Deletes:\n"
            "• All analysis results\n"
            "• All bundle suggestions\n"
            "• All cached metadata\n"
            "• Analysis run history\n\n"
            "Database schema and structure are preserved.\n"
            "This action cannot be undone - create a backup first!\n\n"
            "Use only for complete database reset."
        )
        purge_all_btn.clicked.connect(lambda: self._purge_data("all"))
        maintenance_layout.addWidget(purge_all_btn, 2, 1)

        layout.addWidget(maintenance_group)

        # Auto-refresh stats on tab display
        self._show_database_statistics()

        layout.addStretch()
        return widget
