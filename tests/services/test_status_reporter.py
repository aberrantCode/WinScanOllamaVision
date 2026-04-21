"""Tests for StatusReporter — signal emission, filtering, persistence, session id."""

from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QApplication

from services.status_event import StatusEvent
from services.status_reporter import StatusReporter


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.insert.return_value = 1
    repo.purge_older_than.return_value = 0
    return repo


# ---------------------------------------------------------------------------
# Signal emission
# ---------------------------------------------------------------------------


def test_info_emits_signal_with_event(qapp, mock_repo):
    reporter = StatusReporter(repo=mock_repo)
    received = []
    reporter.event_recorded.connect(received.append)

    reporter.info("Analyze → Start", "Hi there")

    assert len(received) == 1
    assert isinstance(received[0], StatusEvent)
    assert received[0].level == "info"
    assert received[0].title == "Hi there"


def test_error_auto_captures_traceback_from_exception(qapp, mock_repo):
    reporter = StatusReporter(repo=mock_repo)
    received = []
    reporter.event_recorded.connect(received.append)

    try:
        raise RuntimeError("boom")
    except RuntimeError as e:
        reporter.error("Analyze → X", "Failed", exc=e)

    assert received[0].traceback is not None
    assert "RuntimeError" in received[0].traceback
    assert "boom" in received[0].detail


def test_auto_capture_of_source_file_line(qapp, mock_repo):
    reporter = StatusReporter(repo=mock_repo)
    received: list[StatusEvent] = []
    reporter.event_recorded.connect(received.append)

    reporter.warn("Analyze → X", "heads up")

    assert received[0].source is not None
    # Source should be "test_status_reporter.py:<some line>"
    assert received[0].source.startswith("test_status_reporter.py:")


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_insert_is_called_with_session_id(qapp, mock_repo):
    reporter = StatusReporter(repo=mock_repo)
    reporter.info("F", "T")
    args, _ = mock_repo.insert.call_args
    assert isinstance(args[0], StatusEvent)
    assert args[1] == reporter.session_id


def test_db_failure_does_not_swallow_signal(qapp):
    """If the DB raises, the Qt signal still fires."""
    repo = MagicMock()
    repo.insert.side_effect = RuntimeError("db down")

    reporter = StatusReporter(repo=repo)
    received = []
    reporter.event_recorded.connect(received.append)

    reporter.info("F", "T")
    assert len(received) == 1


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def test_min_level_drops_below_threshold(qapp, mock_repo):
    reporter = StatusReporter(repo=mock_repo, min_level="warn")
    received = []
    reporter.event_recorded.connect(received.append)

    reporter.info("F", "lo")
    reporter.warn("F", "mid")
    reporter.error("F", "hi")

    assert [e.title for e in received] == ["mid", "hi"]
    # And only two persisted
    assert mock_repo.insert.call_count == 2


def test_set_min_level_updates_threshold(qapp, mock_repo):
    reporter = StatusReporter(repo=mock_repo, min_level="warn")
    received = []
    reporter.event_recorded.connect(received.append)

    reporter.info("F", "dropped")
    reporter.set_min_level("info")
    reporter.info("F", "kept")

    assert [e.title for e in received] == ["kept"]


# ---------------------------------------------------------------------------
# Session id
# ---------------------------------------------------------------------------


def test_session_id_stable_across_calls(qapp, mock_repo):
    reporter = StatusReporter(repo=mock_repo)
    a = reporter.session_id
    reporter.info("F", "one")
    reporter.info("F", "two")
    assert reporter.session_id == a


def test_two_reporters_have_distinct_session_ids(qapp, mock_repo):
    a = StatusReporter(repo=mock_repo)
    b = StatusReporter(repo=mock_repo)
    assert a.session_id != b.session_id


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------


def test_purge_expired_delegates_to_repo(qapp, mock_repo):
    reporter = StatusReporter(repo=mock_repo)
    mock_repo.purge_older_than.return_value = 17
    assert reporter.purge_expired(30) == 17
    mock_repo.purge_older_than.assert_called_once_with(30)


def test_purge_without_repo_returns_zero(qapp):
    reporter = StatusReporter(repo=None)
    assert reporter.purge_expired(30) == 0


# ---------------------------------------------------------------------------
# emit_event() low-level entry point
# ---------------------------------------------------------------------------


def test_emit_event_passes_through(qapp, mock_repo):
    reporter = StatusReporter(repo=mock_repo)
    received = []
    reporter.event_recorded.connect(received.append)

    event = StatusEvent(level="warn", feature="F", title="T")
    returned = reporter.emit_event(event)
    assert returned is event
    assert received[0] is event
