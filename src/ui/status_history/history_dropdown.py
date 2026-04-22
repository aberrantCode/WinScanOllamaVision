"""
HistoryDropdown — the expanded popup that lists recent status events.

Opens on StatusHistoryBar click. Shows filter/search header, scrollable list
of events with severity icon + timestamp + feature + title + per-row action
buttons, and a footer with a "View All" hook (future).
"""

from __future__ import annotations

import contextlib
from datetime import timezone
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.status_event import StatusEvent
from services.status_reporter import get_reporter
from ui.status_history.row_conversion import row_to_status_event

_LEVEL_ICON = {"debug": "·", "info": "ⓘ", "warn": "⚠", "error": "⛔"}
_LEVEL_COLOR = {
    "debug": "#6B7280",
    "info": "#10B981",
    "warn": "#F59E0B",
    "error": "#DC2626",
}


class HistoryDropdown(QDialog):
    """Popup window listing recent status events.

    Uses QDialog with a frameless flag + popup behavior so clicking
    outside dismisses it cleanly. The parent panel positions it.
    """

    event_activated = pyqtSignal(object)  # StatusEvent — when a row is clicked

    def __init__(
        self,
        *,
        display_count: int = 20,
        dark_mode: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._display_count = max(int(display_count), 1)
        self._dark_mode = dark_mode
        self._filter_min_level: str | None = None
        self._search_text: str = ""

        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMinimumWidth(560)
        self.setMaximumHeight(480)

        self._build_ui()
        self._reload()

    # ---- UI --------------------------------------------------------------

    def _build_ui(self) -> None:
        container = QFrame(self)
        container.setObjectName("HistoryDropdownFrame")
        container.setStyleSheet(
            "QFrame#HistoryDropdownFrame { "
            f"background-color: {'#1F2937' if self._dark_mode else '#FFFFFF'}; "
            f"border: 1px solid {'#374151' if self._dark_mode else '#E5E7EB'}; "
            "border-radius: 6px; "
            "}"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)

        root = QVBoxLayout(container)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Header: filter + search
        header = QHBoxLayout()
        header.setSpacing(6)
        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["All", "Warnings & errors", "Errors only"])
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search history…")
        self._search_edit.textChanged.connect(self._on_search_changed)

        header.addWidget(self._filter_combo)
        header.addWidget(self._search_edit, stretch=1)
        root.addLayout(header)

        # Body: list
        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.setStyleSheet(
            "QListWidget { border: none; font-size: 9pt; } "
            "QListWidget::item { padding: 6px 4px; } "
            "QListWidget::item:hover { "
            f"background-color: {'#374151' if self._dark_mode else '#F3F4F6'}; "
            "}"
        )
        root.addWidget(self._list, stretch=1)

        # Footer: counts + view-all
        footer = QHBoxLayout()
        footer.setSpacing(6)
        self._count_lbl = QLabel("—")
        self._count_lbl.setStyleSheet(
            f"color: {'#9CA3AF' if self._dark_mode else '#6B7280'}; font-size: 8pt;"
        )
        footer.addWidget(self._count_lbl, stretch=1)

        self._export_btn = QPushButton("Export JSON")
        self._export_btn.setFlat(True)
        self._export_btn.clicked.connect(self._on_export_clicked)
        self._export_btn.setToolTip(
            "Export the currently visible events to a JSON file — useful "
            "for attaching to a bug report."
        )
        footer.addWidget(self._export_btn)

        self._close_btn = QPushButton("Close")
        self._close_btn.setFlat(True)
        self._close_btn.clicked.connect(self.close)
        footer.addWidget(self._close_btn)
        root.addLayout(footer)

    # ---- Filter / search --------------------------------------------------

    def _on_filter_changed(self, idx: int) -> None:
        mapping = {0: None, 1: "warn", 2: "error"}
        self._filter_min_level = mapping.get(idx)
        self._reload()

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text.strip().lower()
        self._reload()

    # ---- Reload from reporter ---------------------------------------------

    def _reload(self) -> None:
        reporter = get_reporter()
        rows = reporter.recent(
            limit=max(self._display_count * 3, 60),
            min_level=self._filter_min_level,  # type: ignore[arg-type]
        )

        events = [row_to_status_event(row) for row in rows]
        events = [e for e in events if self._matches_search(e)]
        events = events[: self._display_count]

        self._list.clear()
        for event, row in zip(events, rows[: len(events)], strict=False):
            item = QListWidgetItem()
            item.setText(self._format_row(event, row))
            item.setData(Qt.ItemDataRole.UserRole, event)
            item.setData(Qt.ItemDataRole.UserRole + 1, row.get("id"))
            icon_color = _LEVEL_COLOR[event.level]
            item.setForeground(
                Qt.GlobalColor.black if not self._dark_mode else Qt.GlobalColor.white
            )
            # Monospace timestamps help alignment; keep the full row in text
            # for copy/paste friendliness. Color cue is via the level icon.
            item.setToolTip(f"{event.feature}\n{event.title}\n\n{event.detail[:400]}")
            # Unused variable quiet
            _ = icon_color
            self._list.addItem(item)

        self._count_lbl.setText(f"Showing {self._list.count()} of {len(rows)} recent events")
        # Mark everything as seen so the badge drops
        with contextlib.suppress(Exception):
            reporter.acknowledge_all()

    def _matches_search(self, event: StatusEvent) -> bool:
        if not self._search_text:
            return True
        hay = " ".join([event.feature, event.title, event.detail or "", event.level]).lower()
        return self._search_text in hay

    def _format_row(self, event: StatusEvent, row: dict[str, Any]) -> str:
        ts = event.occurred_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        local = ts.astimezone()
        time_str = local.strftime("%H:%M")
        icon = _LEVEL_ICON[event.level]
        feature = event.feature or "—"
        title = event.title
        count = int(row.get("coalesced_count") or 1)
        count_suffix = f"  ×{count}" if count > 1 else ""
        starred = "★ " if int(row.get("starred") or 0) else ""
        return f"{icon}  {time_str}  {feature:28s}  {starred}{title}{count_suffix}"

    # ---- Click -----------------------------------------------------------

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        event = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(event, StatusEvent):
            self.event_activated.emit(event)

    # ---- Export ----------------------------------------------------------

    def _on_export_clicked(self) -> None:
        """Dump the currently visible events to a JSON file."""
        import json

        events: list[dict[str, Any]] = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item is None:
                continue
            event = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(event, StatusEvent):
                events.append(
                    {
                        "event_id": event.event_id,
                        "occurred_at": event.occurred_at.isoformat(),
                        "level": event.level,
                        "feature": event.feature,
                        "title": event.title,
                        "detail": event.detail,
                        "source": event.source,
                        "file_path": event.file_path,
                        "correlation_id": event.correlation_id,
                        "context": event.context,
                        "traceback": event.traceback,
                    }
                )

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Status History", "status_history.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(events, f, indent=2, default=str)
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

    # ---- Public ----------------------------------------------------------

    def set_display_count(self, count: int) -> None:
        self._display_count = max(int(count), 1)
        self._reload()

    def refresh(self) -> None:
        self._reload()
