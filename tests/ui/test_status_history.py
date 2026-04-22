"""Smoke + behavior tests for the status_history UI package.

These are deliberately narrow tests that exercise the widgets enough to
confirm they render and wire signals correctly, without asserting on
pixel-level Qt behavior.
"""

from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QApplication

from services.status_event import StatusEvent
from services.status_reporter import reset_reporter_for_tests
from ui.status_history.row_conversion import row_to_status_event


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def isolate_reporter():
    """Replace the global reporter with a lightweight mock for every test.

    The UI widgets subscribe to StatusReporter signals and query methods on
    construction — we don't want that to hit a real AppData DB.
    """
    reset_reporter_for_tests()
    with patch("services.status_reporter.get_reporter") as gm:
        reporter = MagicMock()
        reporter.recent.return_value = []
        reporter.unacknowledged_count.return_value = 0
        # Real QObject signal so callers' .connect() works
        from PyQt6.QtCore import QObject, pyqtSignal

        class _DummyEmitter(QObject):
            event_recorded = pyqtSignal(object)

        emitter = _DummyEmitter()
        reporter.event_recorded = emitter.event_recorded
        reporter._emitter = emitter  # keep alive
        gm.return_value = reporter
        # Patch every import site that uses get_reporter() from status_reporter
        with (
            patch("ui.status_history.history_bar.get_reporter", return_value=reporter),
            patch("ui.status_history.history_dropdown.get_reporter", return_value=reporter),
        ):
            yield reporter


def _event(**overrides) -> StatusEvent:
    base = {
        "level": "error",
        "feature": "Analyze → Re-analyze Files",
        "title": "boom",
        "detail": "detail text",
        "source": "worker.py:100",
        "context": {"provider": "claude_cli"},
        "file_path": "/fake/a.png",
        "correlation_id": "job-1",
    }
    base.update(overrides)
    return StatusEvent(**base)


# ---------------------------------------------------------------------------
# row_conversion
# ---------------------------------------------------------------------------


def test_row_to_status_event_basic():
    row = {
        "event_id": "abc",
        "occurred_at": "2026-04-20 14:22:08.123456",
        "session_id": "s1",
        "level": "warn",
        "feature": "Analyze → Start",
        "source": "svc.py:10",
        "title": "No dirs",
        "detail": "nothing to do",
        "traceback": None,
        "context_json": {"k": "v"},
        "file_path": None,
        "correlation_id": None,
    }
    event = row_to_status_event(row)
    assert event.level == "warn"
    assert event.title == "No dirs"
    assert event.context == {"k": "v"}
    assert event.occurred_at.year == 2026


def test_row_to_status_event_handles_seconds_precision_timestamp():
    row = {
        "event_id": "abc",
        "occurred_at": "2026-04-20 14:22:08",
        "session_id": "s1",
        "level": "info",
        "feature": "X",
        "source": None,
        "title": "t",
        "detail": None,
        "traceback": None,
        "context_json": None,
        "file_path": None,
        "correlation_id": None,
    }
    event = row_to_status_event(row)
    assert event.occurred_at.minute == 22


def test_row_to_status_event_missing_context_defaults_to_empty_dict():
    row = {
        "event_id": "abc",
        "occurred_at": "2026-04-20 14:22:08",
        "session_id": "s1",
        "level": "info",
        "feature": "X",
        "source": None,
        "title": "t",
        "detail": None,
        "traceback": None,
        "context_json": None,
        "file_path": None,
        "correlation_id": None,
    }
    event = row_to_status_event(row)
    assert event.context == {}


# ---------------------------------------------------------------------------
# StatusHistoryBar
# ---------------------------------------------------------------------------


def test_status_history_bar_renders_initial_placeholder(qapp, isolate_reporter):
    from ui.status_history.history_bar import StatusHistoryBar

    bar = StatusHistoryBar(dark_mode=False)
    # No events → "Ready." default
    assert bar._title_lbl.text() == "Ready."
    bar.deleteLater()


def test_status_history_bar_updates_on_reporter_signal(qapp, isolate_reporter):
    from ui.status_history.history_bar import StatusHistoryBar

    bar = StatusHistoryBar(dark_mode=False)
    event = _event(level="error", title="something broke")

    # Simulate reporter firing the signal
    isolate_reporter.event_recorded.emit(event)
    qapp.processEvents()

    assert bar._title_lbl.text() == "something broke"
    assert bar._icon_lbl.text() == "⛔"
    bar.deleteLater()


def test_status_history_bar_shows_badge_when_unack_count_positive(qapp, isolate_reporter):
    from ui.status_history.history_bar import StatusHistoryBar

    isolate_reporter.unacknowledged_count.return_value = 3
    bar = StatusHistoryBar(dark_mode=False)

    # Simulate an event to refresh the badge
    isolate_reporter.event_recorded.emit(_event())
    qapp.processEvents()

    # isVisible() requires the top-level window to be shown; use the
    # widget-local "not explicitly hidden" flag via isVisibleTo(parent).
    assert bar._badge_lbl.isVisibleTo(bar)
    assert "3" in bar._badge_lbl.text()
    bar.deleteLater()


def test_status_history_bar_click_emits_open_requested(qapp, isolate_reporter):
    from PyQt6.QtCore import QEvent, QPointF, Qt
    from PyQt6.QtGui import QMouseEvent

    from ui.status_history.history_bar import StatusHistoryBar

    bar = StatusHistoryBar(dark_mode=False)
    received = []
    bar.open_requested.connect(lambda: received.append(True))

    # Synthesize a left-click
    mouse_event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(5.0, 5.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    bar.mousePressEvent(mouse_event)
    assert received == [True]
    bar.deleteLater()


# ---------------------------------------------------------------------------
# IssuePreviewDialog
# ---------------------------------------------------------------------------


def test_issue_preview_dialog_builds_valid_url(qapp):
    from ui.status_history.issue_preview_dialog import IssuePreviewDialog

    dlg = IssuePreviewDialog(_event(), app_version="1.2.3")
    url = dlg.current_url
    assert url.startswith("https://github.com/")
    assert "title=" in url
    assert "body=" in url
    assert "labels=" in url
    dlg.deleteLater()


def test_issue_preview_dialog_continue_invokes_opener(qapp):
    from ui.status_history.issue_preview_dialog import IssuePreviewDialog

    captured = []
    dlg = IssuePreviewDialog(
        _event(),
        app_version="1.2.3",
        url_opener=lambda u: captured.append(u) or True,
    )
    dlg._on_continue()
    assert len(captured) == 1
    assert captured[0].startswith("https://github.com/")
    dlg.deleteLater()


def test_issue_preview_dialog_redaction_toggle_changes_url(qapp):
    from ui.status_history.issue_preview_dialog import IssuePreviewDialog

    dlg = IssuePreviewDialog(_event(), app_version="1.2.3", default_redact_paths=True)
    redacted = dlg.current_url

    dlg._redact_cb.setChecked(False)
    dlg._refresh_preview()
    full = dlg.current_url

    assert redacted != full
    # The full-path url should contain the raw path's basename at minimum
    # and the redacted one should contain "redacted"
    assert "redacted" in redacted
    dlg.deleteLater()


# ---------------------------------------------------------------------------
# StatusEventDialog
# ---------------------------------------------------------------------------


def test_event_dialog_renders_all_sections_for_full_event(qapp):
    from ui.status_history.event_dialog import StatusEventDialog

    event = _event(traceback="Traceback...\nRuntimeError: boom")
    dialog = StatusEventDialog(event, retry_enabled=True)
    # Dialog constructs without error → pass
    dialog.deleteLater()


def test_event_dialog_star_toggle_emits_signal(qapp):
    from ui.status_history.event_dialog import StatusEventDialog

    received: list[bool] = []
    dialog = StatusEventDialog(_event())
    dialog.star_toggled.connect(received.append)

    dialog._on_star_clicked()
    dialog._on_star_clicked()
    assert received == [True, False]
    dialog.deleteLater()


def test_event_dialog_retry_button_emits_event(qapp):
    from ui.status_history.event_dialog import StatusEventDialog

    received: list[StatusEvent] = []
    dialog = StatusEventDialog(_event(), retry_enabled=True)
    dialog.retry_requested.connect(received.append)

    dialog._on_retry()
    assert len(received) == 1
    assert received[0].file_path == "/fake/a.png"
    dialog.deleteLater()


def test_event_dialog_file_issue_emits_event(qapp):
    from ui.status_history.event_dialog import StatusEventDialog

    received: list[StatusEvent] = []
    dialog = StatusEventDialog(_event())
    dialog.file_issue_requested.connect(received.append)

    dialog._on_file_issue()
    assert len(received) == 1
    dialog.deleteLater()
