# mypy: disable-error-code=attr-defined
"""General tab mixin for EnhancedSettingsWindow."""

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
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

        # Updates Group
        updates_group = QGroupBox("Software Updates")
        updates_layout = QVBoxLayout(updates_group)

        self.check_updates_on_startup_checkbox = QCheckBox("Check for updates on startup")
        check_on_startup = self.config_manager.get_bool("Updates", "check_on_startup", True)
        self.check_updates_on_startup_checkbox.setChecked(check_on_startup)
        self.check_updates_on_startup_checkbox.setToolTip(
            "Poll GitHub Releases once per startup (at most every 6 hours) to detect\n"
            "newer versions. Never downloads or installs without explicit confirmation."
        )
        updates_layout.addWidget(self.check_updates_on_startup_checkbox)

        check_now_row = QHBoxLayout()
        self.check_updates_now_button = QPushButton("Check for updates now")
        self.check_updates_now_button.setToolTip(
            "Force an immediate update check, bypassing the cache."
        )
        check_now_row.addWidget(self.check_updates_now_button)
        check_now_row.addStretch()
        updates_layout.addLayout(check_now_row)

        updates_info = QLabel(
            "Source: public GitHub Releases. Downloads are SHA-256 verified before install.\n"
            "Install requires administrator permission (per-machine install to Program Files)."
        )
        updates_info.setWordWrap(True)
        updates_layout.addWidget(updates_info)

        layout.addWidget(updates_group)

        # LLM Readiness Group
        readiness_group = QGroupBox("LLM Readiness")
        readiness_layout = QVBoxLayout(readiness_group)

        self.preflight_verify_startup_checkbox = QCheckBox("Verify LLM readiness on startup")
        verify_on_startup = self.config_manager.get_bool("LLMPreflight", "verify_on_startup", True)
        self.preflight_verify_startup_checkbox.setChecked(verify_on_startup)
        self.preflight_verify_startup_checkbox.setToolTip(
            "Shortly after launch, check (off the UI thread) that the active provider is\n"
            "reachable and its configured model is installed — before analysis runs."
        )
        readiness_layout.addWidget(self.preflight_verify_startup_checkbox)

        self.preflight_verify_save_checkbox = QCheckBox("Verify LLM readiness when saving settings")
        verify_on_save = self.config_manager.get_bool("LLMPreflight", "verify_on_save", True)
        self.preflight_verify_save_checkbox.setChecked(verify_on_save)
        self.preflight_verify_save_checkbox.setToolTip(
            "After saving, confirm the selected provider/model is ready and, per the\n"
            "download policy below, offer to download a missing Ollama model."
        )
        readiness_layout.addWidget(self.preflight_verify_save_checkbox)

        policy_row = QHBoxLayout()
        policy_label = QLabel("Missing-model download policy:")
        policy_row.addWidget(policy_label)
        self.preflight_policy_combo = QComboBox()
        # (label, stored value)
        for label, value in (
            ("Off — never download", "off"),
            ("Prompt — ask before downloading", "prompt"),
            ("Auto — download automatically", "auto"),
        ):
            self.preflight_policy_combo.addItem(label, value)
        current_policy = self.config_manager.get_setting(
            "LLMPreflight", "model_download_policy", "prompt"
        )
        policy_index = self.preflight_policy_combo.findData(current_policy)
        self.preflight_policy_combo.setCurrentIndex(policy_index if policy_index >= 0 else 1)
        self.preflight_policy_combo.setToolTip(
            "Only Ollama can auto-download models. Claude/Gemini CLI models must be\n"
            "installed CLI-side. Downloads can be multi-GB — 'Prompt' asks first."
        )
        policy_row.addWidget(self.preflight_policy_combo)
        policy_row.addStretch()
        readiness_layout.addLayout(policy_row)

        layout.addWidget(readiness_group)

        layout.addStretch()
        return widget
