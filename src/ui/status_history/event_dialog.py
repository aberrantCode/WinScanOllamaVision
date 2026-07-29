"""
StatusEventDialog — the detail popup for a single StatusEvent.

Shows every field of the event, plus Star / Copy as Markdown / Retry /
File GitHub Issue action buttons. The Retry action is a signal the parent
panel wires up per feature (e.g. the Analyze panel knows how to re-queue
an ANALYZE_FILES job for a ``file_path``).

The dialog is designed to be opened **modelessly** (``.show()`` rather than
``.exec()``) so it doesn't lock the rest of the app. When constructed with a
list of sibling events it also grows Prev/Next controls (and ←/→ shortcuts)
so the user can walk the history without reopening the dropdown each time.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from datetime import timezone

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog,
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
_LEVEL_ICON = {"debug": "·", "info": "ⓘ", "warn": "⚠", "error": "⛔"}

# retry_enabled may be a plain bool (single-event use) or a predicate that is
# re-evaluated for whichever event is currently shown (navigation use).
RetrySpec = bool | Callable[[StatusEvent], bool]


class StatusEventDialog(QDialog):
    """Detail view for a StatusEvent, with optional prev/next navigation."""

    star_toggled = pyqtSignal(bool)
    retry_requested = pyqtSignal(object)  # StatusEvent
    file_issue_requested = pyqtSignal(object)  # StatusEvent

    def __init__(
        self,
        event: StatusEvent,
        *,
        events: list[StatusEvent] | None = None,
        index: int = 0,
        retry_enabled: RetrySpec = False,
        starred: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # ``events`` is the ordered sibling list for navigation; when absent we
        # degrade to a single-event view (preserves the original constructor).
        self._events: list[StatusEvent] = list(events) if events else [event]
        self._index = index if events else 0
        if not (0 <= self._index < len(self._events)):
            self._index = 0
        self._event = self._events[self._index]
        self._starred = starred
        self._retry_spec: RetrySpec = retry_enabled

        self.resize(680, 600)

        # Persistent scaffold: a body area (rebuilt per event) above a fixed
        # control bar (built once). Rebuilding only the body avoids the
        # "widget already has a layout" trap and keeps signal wiring stable.
        self._root = QVBoxLayout(self)
        self._root.setSpacing(10)
        self._body = QWidget()
        self._root.addWidget(self._body, stretch=1)
        self._build_controls()

        # ←/→ walk the history. Created once (not per rebuild) so they don't
        # stack up and fire N times after N navigations.
        prev_sc = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        prev_sc.activated.connect(self._go_prev)
        next_sc = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        next_sc.activated.connect(self._go_next)

        self._show_event(self._index)

    # ---- Body (rebuilt per event) ---------------------------------------

    def _populate_body(self) -> None:
        """Replace the body widget with fields for the current event."""
        old = self._body
        self._root.removeWidget(old)
        old.deleteLater()

        self._body = QWidget()
        self._root.insertWidget(0, self._body, stretch=1)
        body = QVBoxLayout(self._body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(10)

        ev = self._event

        # Header: severity icon + title
        header = QHBoxLayout()
        header.setSpacing(8)
        icon_lbl = QLabel(_LEVEL_ICON[ev.level])
        icon_lbl.setStyleSheet(f"color: {_LEVEL_COLOR[ev.level]}; font-size: 18pt; border: none;")
        title_lbl = QLabel(ev.title)
        title_lbl.setStyleSheet("font-size: 12pt; font-weight: 600;")
        title_lbl.setWordWrap(True)
        header.addWidget(icon_lbl)
        header.addWidget(title_lbl, stretch=1)
        body.addLayout(header)

        # Field grid: Feature / When / File / IDs
        grid = QFormLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)
        grid.addRow("Feature:", QLabel(ev.feature or "—"))
        grid.addRow("When:", QLabel(self._format_when()))
        file_row = QHBoxLayout()
        file_lbl = QLabel(ev.file_path or "—")
        file_lbl.setStyleSheet("font-family: Consolas, monospace;")
        file_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        file_row.addWidget(file_lbl, stretch=1)
        if ev.file_path:
            open_btn = QPushButton("Open folder")
            open_btn.setFlat(True)
            open_btn.clicked.connect(self._open_containing_folder)
            file_row.addWidget(open_btn)
        file_wrap = QWidget()
        file_wrap.setLayout(file_row)
        grid.addRow("File:", file_wrap)
        grid.addRow("Event ID:", QLabel(ev.event_id))
        if ev.correlation_id:
            grid.addRow("Correlation:", QLabel(ev.correlation_id))
        body.addLayout(grid)

        # Detail
        if ev.detail:
            detail_group = QGroupBox("Details")
            detail_layout = QVBoxLayout(detail_group)
            detail_box = QPlainTextEdit(ev.detail)
            detail_box.setReadOnly(True)
            detail_box.setMinimumHeight(80)
            detail_box.setMaximumHeight(160)
            detail_layout.addWidget(detail_box)
            body.addWidget(detail_group)

        # Context
        if ev.context:
            ctx_group = QGroupBox("Context")
            ctx_layout = QVBoxLayout(ctx_group)
            ctx_text = QPlainTextEdit(json.dumps(ev.context, indent=2, default=str))
            ctx_text.setReadOnly(True)
            ctx_text.setMaximumHeight(140)
            ctx_text.setStyleSheet("font-family: Consolas, monospace; font-size: 9pt;")
            ctx_layout.addWidget(ctx_text)
            body.addWidget(ctx_group)

        # Developer Details (framed box)
        dev_group = QGroupBox("Developer Details")
        dev_layout = QFormLayout(dev_group)
        dev_layout.addRow("Source:", QLabel(ev.source or "—"))
        dev_layout.addRow("Level:", QLabel(ev.level))
        body.addWidget(dev_group)

        # Traceback
        if ev.traceback:
            tb_group = QGroupBox("Traceback")
            tb_layout = QVBoxLayout(tb_group)
            tb_text = QTextEdit()
            tb_text.setReadOnly(True)
            tb_text.setPlainText(ev.traceback)
            tb_text.setStyleSheet("font-family: Consolas, monospace; font-size: 9pt;")
            tb_text.setMinimumHeight(100)
            tb_text.setMaximumHeight(220)
            tb_layout.addWidget(tb_text)
            body.addWidget(tb_group)

        body.addStretch()

    # ---- Controls (built once) ------------------------------------------

    def _build_controls(self) -> None:
        """Build the persistent bottom bar: nav cluster | stretch | actions.

        A plain QHBoxLayout (not QDialogButtonBox) so we control ordering and
        can slot a position label between the nav buttons — QDialogButtonBox
        reorders by platform and only accepts QAbstractButtons.
        """
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        # Navigation cluster (left). Hidden entirely for single events.
        self._prev_btn = QPushButton("◀ Prev")
        self._prev_btn.setAutoDefault(False)
        self._prev_btn.clicked.connect(self._go_prev)
        self._pos_lbl = QLabel("")
        self._pos_lbl.setStyleSheet("color: #6B7280; font-size: 9pt;")
        self._next_btn = QPushButton("Next ▶")
        self._next_btn.setAutoDefault(False)
        self._next_btn.clicked.connect(self._go_next)
        row.addWidget(self._prev_btn)
        row.addWidget(self._pos_lbl)
        row.addWidget(self._next_btn)

        row.addStretch(1)

        # Action cluster (right).
        self._star_btn = QPushButton("★ Starred" if self._starred else "☆ Star")
        self._star_btn.setCheckable(True)
        self._star_btn.setChecked(self._starred)
        self._star_btn.setAutoDefault(False)
        self._star_btn.clicked.connect(self._on_star_clicked)

        copy_btn = QPushButton("📋 Copy as Markdown")
        copy_btn.setAutoDefault(False)
        copy_btn.clicked.connect(self._on_copy_markdown)

        self._retry_btn = QPushButton("🔁 Retry")
        self._retry_btn.setAutoDefault(False)
        self._retry_btn.clicked.connect(self._on_retry)

        issue_btn = QPushButton("🐙 File GitHub Issue")
        issue_btn.setAutoDefault(False)
        issue_btn.clicked.connect(self._on_file_issue)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)

        for btn in (self._star_btn, copy_btn, self._retry_btn, issue_btn, close_btn):
            row.addWidget(btn)

        self._root.addWidget(bar)

    def _sync_controls(self) -> None:
        """Update per-event control state (nav bounds, retry, star, position)."""
        multi = len(self._events) > 1
        self._prev_btn.setVisible(multi)
        self._next_btn.setVisible(multi)
        self._pos_lbl.setVisible(multi)
        if multi:
            self._prev_btn.setEnabled(self._index > 0)
            self._next_btn.setEnabled(self._index < len(self._events) - 1)
            self._pos_lbl.setText(f"{self._index + 1} of {len(self._events)}")

        self._retry_btn.setVisible(self._retry_is_enabled())

        # Starred state isn't persisted yet, so it resets as you navigate.
        self._star_btn.setChecked(self._starred)
        self._star_btn.setText("★ Starred" if self._starred else "☆ Star")

    # ---- Navigation ------------------------------------------------------

    def _show_event(self, index: int) -> None:
        self._index = max(0, min(index, len(self._events) - 1))
        self._event = self._events[self._index]
        self._starred = False  # per-event star state not persisted yet
        self.setWindowTitle(f"Status Event — {self._event.title[:60]}")
        self._populate_body()
        self._sync_controls()

    def _go_prev(self) -> None:
        if self._index > 0:
            self._show_event(self._index - 1)

    def _go_next(self) -> None:
        if self._index < len(self._events) - 1:
            self._show_event(self._index + 1)

    # ---- Helpers ---------------------------------------------------------

    def _retry_is_enabled(self) -> bool:
        spec = self._retry_spec
        if callable(spec):
            try:
                return bool(spec(self._event))
            except Exception:  # pragma: no cover - defensive predicate guard
                return False
        return bool(spec)

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
        ev = self._event
        lines = [
            f"**{ev.title}**",
            f"- Feature: {ev.feature}",
            f"- Level: {ev.level}",
            f"- When: {self._format_when()}",
        ]
        if ev.file_path:
            lines.append(f"- File: `{ev.file_path}`")
        if ev.detail:
            lines += ["", "```", ev.detail, "```"]
        if ev.traceback:
            lines += [
                "",
                "<details><summary>Traceback</summary>",
                "",
                "```",
                ev.traceback,
                "```",
                "</details>",
            ]
        md = "\n".join(lines)
        from PyQt6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(md)

    def _on_retry(self) -> None:
        self.retry_requested.emit(self._event)
        self.accept()

    def _on_file_issue(self) -> None:
        self.file_issue_requested.emit(self._event)
