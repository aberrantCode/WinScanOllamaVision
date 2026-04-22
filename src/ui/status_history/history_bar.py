"""
StatusHistoryBar — the collapsed, always-visible strip that replaces the
plain ``status_lbl`` on the Analyze panel (and, later, elsewhere).

Shows: severity icon + most-recent title + unacknowledged-error badge + chevron.
Click anywhere → opens HistoryDropdown beneath the bar.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QMouseEvent
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from services.status_event import StatusEvent, StatusLevel
from services.status_reporter import get_reporter

_LEVEL_ICON: dict[StatusLevel, str] = {
    "debug": "·",
    "info": "ⓘ",
    "warn": "⚠",
    "error": "⛔",
}

_LEVEL_COLOR: dict[StatusLevel, str] = {
    "debug": "#6B7280",  # gray
    "info": "#10B981",  # green (matches start-analysis button)
    "warn": "#F59E0B",  # amber
    "error": "#DC2626",  # red
}


class StatusHistoryBar(QWidget):
    """Collapsed strip showing the latest event + click-to-open affordance."""

    # Emitted when the user clicks the bar; the panel that hosts it is
    # responsible for showing the dropdown. Decouples widget from dropdown
    # placement — different panels may want different popup geometry.
    open_requested = pyqtSignal()

    def __init__(self, *, dark_mode: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.dark_mode = dark_mode
        self._current_event: StatusEvent | None = None
        self._unack_count = 0

        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self._icon_lbl = QLabel("·")
        self._icon_lbl.setFixedWidth(18)
        self._title_lbl = QLabel("Ready.")
        self._title_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self._title_lbl.setSizePolicy(
            self._title_lbl.sizePolicy().horizontalPolicy(),
            self._title_lbl.sizePolicy().verticalPolicy(),
        )
        self._badge_lbl = QLabel("")
        self._badge_lbl.setVisible(False)
        self._chevron_lbl = QLabel("▾")
        self._chevron_lbl.setFixedWidth(14)

        layout.addWidget(self._icon_lbl)
        layout.addWidget(self._title_lbl, stretch=1)
        layout.addWidget(self._badge_lbl)
        layout.addWidget(self._chevron_lbl)

        self._apply_styles("info")
        self._wire_reporter()
        self._refresh_from_reporter()

    # ---- Event wiring ----------------------------------------------------

    def _wire_reporter(self) -> None:
        reporter = get_reporter()
        # PyQt6 stub doesn't list the connection-type overload; cast to silence.
        reporter.event_recorded.connect(self._on_event_recorded)  # type: ignore[call-arg]

    def _on_event_recorded(self, event: Any) -> None:
        if not isinstance(event, StatusEvent):
            return
        self._current_event = event
        self._unack_count = get_reporter().unacknowledged_count(min_level="warn")
        self._render(event)

    def _refresh_from_reporter(self) -> None:
        reporter = get_reporter()
        rows = reporter.recent(limit=1)
        if rows:
            from ui.status_history.row_conversion import row_to_status_event

            event = row_to_status_event(rows[0])
            self._current_event = event
            self._render(event)
        self._unack_count = reporter.unacknowledged_count(min_level="warn")
        self._render_badge()

    # ---- Rendering -------------------------------------------------------

    def _render(self, event: StatusEvent) -> None:
        self._icon_lbl.setText(_LEVEL_ICON[event.level])
        title = event.title or "Ready."
        self._title_lbl.setText(title)
        self._title_lbl.setToolTip(event.detail or title)
        self._apply_styles(event.level)
        self._render_badge()

    def _render_badge(self) -> None:
        if self._unack_count > 0:
            self._badge_lbl.setText(f" {self._unack_count} ")
            self._badge_lbl.setVisible(True)
            self._badge_lbl.setStyleSheet(
                "background-color: #DC2626; color: white; "
                "font-size: 9pt; font-weight: 600; "
                "border-radius: 8px; padding: 1px 6px;"
            )
        else:
            self._badge_lbl.setVisible(False)

    def _apply_styles(self, level: StatusLevel) -> None:
        color = _LEVEL_COLOR[level]
        self._icon_lbl.setStyleSheet(f"color: {color}; font-size: 12pt; border: none;")
        title_weight = 600 if level in ("warn", "error") else 500
        self._title_lbl.setStyleSheet(
            f"color: {color}; font-size: 9pt; font-weight: {title_weight}; border: none;"
        )
        self._chevron_lbl.setStyleSheet(f"color: {color}; font-size: 9pt; border: none;")
        # Container gets a subtle tinted background at warn/error.
        if level == "error":
            bg = "#FEE2E2" if not self.dark_mode else "#3F1D1D"
        elif level == "warn":
            bg = "#FEF3C7" if not self.dark_mode else "#3F2D0F"
        else:
            bg = "transparent"
        self.setStyleSheet(f"StatusHistoryBar {{ background-color: {bg}; border-radius: 4px; }}")

    # ---- Click handling --------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802  (Qt override)
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self.open_requested.emit()
        super().mousePressEvent(event)

    # ---- Public API ------------------------------------------------------

    def set_dark_mode(self, dark_mode: bool) -> None:
        self.dark_mode = dark_mode
        if self._current_event is not None:
            self._apply_styles(self._current_event.level)

    def current_event(self) -> StatusEvent | None:
        return self._current_event

    def refresh(self) -> None:
        """Reload latest event + unread count from the reporter."""
        self._refresh_from_reporter()
