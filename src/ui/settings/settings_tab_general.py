# mypy: disable-error-code=attr-defined
"""General tab mixin for EnhancedSettingsWindow."""

from PyQt6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class _SettingsTabGeneralMixin:
    """Mixin providing the General settings tab."""

    def _create_general_tab(self) -> QWidget:
        """Tab 1: General Settings"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Audit Trail Group
        audit_group = QGroupBox("Audit Trail")
        audit_layout = QVBoxLayout(audit_group)

        self.audit_trail_checkbox = QCheckBox("Enable Audit Trail Logging")
        self.audit_trail_checkbox.setToolTip(
            "Records all user actions and decisions for compliance and review.\n"
            "Logs include: file operations, metadata edits, bundle accept/reject decisions,\n"
            "and document processing history. Useful for auditing and troubleshooting."
        )
        audit_enabled = self.config_manager.get_setting("AuditTrail", "enabled", "false")
        self.audit_trail_checkbox.setChecked(audit_enabled.lower() == "true")
        audit_layout.addWidget(self.audit_trail_checkbox)

        audit_info = QLabel(
            "When enabled, user actions and decisions will be logged for review.\n"
            "Logs include: file operations, metadata edits, bundle decisions."
        )
        audit_info.setWordWrap(True)
        audit_layout.addWidget(audit_info)

        layout.addWidget(audit_group)

        # Application Behavior Group
        behavior_group = QGroupBox("Application Behavior")
        behavior_layout = QVBoxLayout(behavior_group)

        self.auto_start_analysis_checkbox = QCheckBox("Auto Start Analysis")
        auto_start_enabled = self.config_manager.get_bool("GUI", "auto_start_analysis", False)
        self.auto_start_analysis_checkbox.setChecked(auto_start_enabled)
        self.auto_start_analysis_checkbox.setToolTip(
            "Automatically start analysis when opening the Analysis Status window"
        )
        behavior_layout.addWidget(self.auto_start_analysis_checkbox)

        self.confirm_exit_checkbox = QCheckBox("Confirm Before Exit")
        confirm_exit_enabled = self.config_manager.get_bool("GUI", "confirm_before_exit", True)
        self.confirm_exit_checkbox.setChecked(confirm_exit_enabled)
        self.confirm_exit_checkbox.setToolTip(
            "Show confirmation dialog when closing the application"
        )
        behavior_layout.addWidget(self.confirm_exit_checkbox)

        self.persist_rotation_checkbox = QCheckBox("Persist Image Rotation")
        persist_rotation_enabled = self.config_manager.get_bool("GUI", "persist_rotation", True)
        self.persist_rotation_checkbox.setChecked(persist_rotation_enabled)
        self.persist_rotation_checkbox.setToolTip(
            "Automatically save and restore image rotation preferences"
        )
        behavior_layout.addWidget(self.persist_rotation_checkbox)

        layout.addWidget(behavior_group)

        # Logging Group
        logging_group = QGroupBox("Logging")
        logging_layout = QVBoxLayout(logging_group)

        self.log_sql_checkbox = QCheckBox("Log SQL Statements")
        log_sql_enabled = self.config_manager.get_bool("Logging", "log_sql_statements", False)
        self.log_sql_checkbox.setChecked(log_sql_enabled)
        self.log_sql_checkbox.setToolTip(
            "Enable logging of SQL statements to the application log.\n"
            "When enabled, all database queries will be written to the log file.\n"
            "Useful for debugging database issues, but can increase log file size significantly."
        )
        logging_layout.addWidget(self.log_sql_checkbox)

        logging_info = QLabel(
            "Note: SQL logging is primarily useful for debugging.\n"
            "Keep this disabled during normal operation to reduce log file size."
        )
        logging_info.setWordWrap(True)
        logging_layout.addWidget(logging_info)

        layout.addWidget(logging_group)

        layout.addStretch()
        return widget
