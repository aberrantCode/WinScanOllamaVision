"""
StatusEventDialog — the detail popup for a single StatusEvent.

Shows every field of the event, plus Star / Copy as Markdown / Retry /
File GitHub Issue action buttons. The Retry action is a signal the parent
panel wires up per feature (e.g. the Analyze panel knows how to re-queue
an ANALYZE_FILES job for a ``file_path``).
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import timezone

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from services.status_event import StatusEvent

_LEVEL_COLOR = {
    "debug": "#6B7280",
    "info": "#10B981",
    "warn": "#F59E0B",
    "error": "#DC2626",
}


class StatusEventDialog(QDialog):
    """Detail view for a single StatusEvent."""

    star_toggled = pyqtSignal(bool)
    retry_requested = pyqtSignal(object)  # StatusEvent
    file_issue_requested = pyqtSignal(object)  # StatusEvent

    def __init__(
        self,
        event: StatusEvent,
        *,
        retry_enabled: bool = False,
        starred: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._event = event
        self._starred = starred
        self._retry_enabled = retry_enabled

        self.setWindowTitle(f"Status Event — {event.title[:60]}")
        self.resize(680, 560)
        self._build_ui()

    # ---- UI --------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        icon_lbl = QLabel(
            {"debug": "·", "info": "ⓘ", "warn": "⚠", "error": "⛔"}[self._event.level]
        )
        icon_lbl.setStyleSheet(
            f"color: {_LEVEL_COLOR[self._event.level]}; font-size: 18pt; border: none;"
        )
        title_lbl = QLabel(self._event.title)
        title_lbl.setStyleSheet("font-size: 12pt; font-weight: 600;")
        title_lbl.setWordWrap(True)
        header.addWidget(icon_lbl)
        header.addWidget(title_lbl, stretch=1)
        root.addLayout(header)

        # Field grid: Feature / When / File / IDs
        grid = QFormLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)
        grid.addRow("Feature:", QLabel(self._event.feature or "—"))
        grid.addRow("When:", QLabel(self._format_when()))
        file_row = QHBoxLayout()
        file_lbl = QLabel(self._event.file_path or "—")
        file_lbl.setStyleSheet("font-family: Consolas, monospace;")
        file_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        file_row.addWidget(file_lbl, stretch=1)
        if self._event.file_path:
            open_btn = QPushButton("Open folder")
            open_btn.setFlat(True)
            open_btn.clicked.connect(self._open_containing_folder)
            file_row.addWidget(open_btn)
        file_wrap = QWidget()
        file_wrap.setLayout(file_row)
        grid.addRow("File:", file_wrap)
        grid.addRow("Event ID:", QLabel(self._event.event_id))
        if self._event.correlation_id:
            grid.addRow("Correlation:", QLabel(self._event.correlation_id))
        root.addLayout(grid)

        # Detail
        if self._event.detail:
            detail_group = QGroupBox("Details")
            detail_layout = QVBoxLayout(detail_group)
            detail_box = QPlainTextEdit(self._event.detail)
            detail_box.setReadOnly(True)
            detail_box.setMinimumHeight(80)
            detail_box.setMaximumHeight(160)
            detail_layout.addWidget(detail_box)
            root.addWidget(detail_group)

        # Context
        if self._event.context:
            ctx_group = QGroupBox("Context")
            ctx_layout = QVBoxLayout(ctx_group)
            ctx_text = QPlainTextEdit(json.dumps(self._event.context, indent=2, default=str))
            ctx_text.setReadOnly(True)
            ctx_text.setMaximumHeight(140)
            ctx_text.setStyleSheet("font-family: Consolas, monospace; font-size: 9pt;")
            ctx_layout.addWidget(ctx_text)
            root.addWidget(ctx_group)

        # Developer Details (collapsible-ish — just a framed box)
        dev_group = QGroupBox("Developer Details")
        dev_layout = QFormLayout(dev_group)
        dev_layout.addRow("Source:", QLabel(self._event.source or "—"))
        dev_layout.addRow("Level:", QLabel(self._event.level))
        root.addWidget(dev_group)

        # Traceback
        if self._event.traceback:
            tb_group = QGroupBox("Traceback")
            tb_layout = QVBoxLayout(tb_group)
            tb_text = QTextEdit()
            tb_text.setReadOnly(True)
            tb_text.setPlainText(self._event.traceback)
            tb_text.setStyleSheet("font-family: Consolas, monospace; font-size: 9pt;")
            tb_text.setMinimumHeight(100)
            tb_text.setMaximumHeight(200)
            tb_layout.addWidget(tb_text)
            root.addWidget(tb_group)

        root.addStretch()

        # Button row
        bb = QDialogButtonBox()
        self._star_btn = QPushButton("★ Starred" if self._starred else "☆ Star")
        self._star_btn.setCheckable(True)
        self._star_btn.setChecked(self._starred)
        self._star_btn.clicked.connect(self._on_star_clicked)
        bb.addButton(self._star_btn, QDialogButtonBox.ButtonRole.ActionRole)

        copy_btn = QPushButton("📋 Copy as Markdown")
        copy_btn.clicked.connect(self._on_copy_markdown)
        bb.addButton(copy_btn, QDialogButtonBox.ButtonRole.ActionRole)

        if self._retry_enabled:
            retry_btn = QPushButton("🔁 Retry")
            retry_btn.clicked.connect(self._on_retry)
            bb.addButton(retry_btn, QDialogButtonBox.ButtonRole.ActionRole)

        issue_btn = QPushButton("🐙 File GitHub Issue")
        issue_btn.clicked.connect(self._on_file_issue)
        bb.addButton(issue_btn, QDialogButtonBox.ButtonRole.ActionRole)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        bb.addButton(close_btn, QDialogButtonBox.ButtonRole.RejectRole)

        root.addWidget(bb)

    # ---- Helpers ---------------------------------------------------------

    def _format_when(self) -> str:
        ts = self._event.occurred_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        local = ts.astimezone()
        return (
            f"{local.strftime('%Y-%m-%d %H:%M:%S')} local "
            f"({ts.astimezone(timezone.utc).strftime('%H:%M:%S')} UTC)"
        )

    def _open_containing_folder(self) -> None:
        path = self._event.file_path
        if not path:
            return
        folder = os.path.dirname(path)
        if not folder:
            return
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", folder])
            else:  # pragma: no cover - non-Windows branch
                subprocess.Popen(["xdg-open", folder])
        except Exception as exc:  # pragma: no cover - defensive
            QMessageBox.warning(self, "Couldn't open folder", str(exc))

    # ---- Actions ---------------------------------------------------------

    def _on_star_clicked(self) -> None:
        self._starred = not self._starred
        self._star_btn.setText("★ Starred" if self._starred else "☆ Star")
        self.star_toggled.emit(self._starred)

    def _on_copy_markdown(self) -> None:
        # Build a compact markdown representation, not the full issue body.
        lines = [
            f"**{self._event.title}**",
            f"- Feature: {self._event.feature}",
            f"- Level: {self._event.level}",
            f"- When: {self._format_when()}",
        ]
        if self._event.file_path:
            lines.append(f"- File: `{self._event.file_path}`")
        if self._event.detail:
            lines += ["", "```", self._event.detail, "```"]
        md = "\n".join(lines)
        app = self.parent()
        # Qt clipboard via QGuiApplication
        from PyQt6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(md)
        _ = app  # silence unused

    def _on_retry(self) -> None:
        self.retry_requested.emit(self._event)
        self.accept()

    def _on_file_issue(self) -> None:
        self.file_issue_requested.emit(self._event)
