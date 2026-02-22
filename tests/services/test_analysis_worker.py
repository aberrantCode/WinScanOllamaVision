"""
Tests for AnalysisWorker in services.analysis_worker.
"""

from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_queue():
    q = MagicMock()
    q.get_pending_count.return_value = 0
    return q


@pytest.fixture
def mock_config_manager():
    return MagicMock()


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_worker_initialises_stop_flag_false(qapp, mock_config_manager, mock_queue):
    """AnalysisWorker._stop_requested is False after construction."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    assert worker._stop_requested is False


def test_worker_initialises_current_job_none(qapp, mock_config_manager, mock_queue):
    """AnalysisWorker._current_job_id is None after construction."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    assert worker._current_job_id is None


def test_worker_stores_config_manager(qapp, mock_config_manager, mock_queue):
    """AnalysisWorker stores config_manager on self."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    assert worker.config_manager is mock_config_manager


def test_worker_stores_analysis_queue(qapp, mock_config_manager, mock_queue):
    """AnalysisWorker stores analysis_queue on self."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    assert worker.analysis_queue is mock_queue


# ---------------------------------------------------------------------------
# stop() / cancel_current_job()
# ---------------------------------------------------------------------------


def test_stop_sets_flag(qapp, mock_config_manager, mock_queue):
    """stop() sets _stop_requested to True."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    worker.stop()
    assert worker._stop_requested is True


def test_cancel_current_job_does_nothing_when_no_job(qapp, mock_config_manager, mock_queue):
    """cancel_current_job() is a no-op when _current_job_id is None."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    worker.cancel_current_job()
    mock_queue.mark_cancelled.assert_not_called()


def test_cancel_current_job_marks_cancelled(qapp, mock_config_manager, mock_queue):
    """cancel_current_job() calls mark_cancelled on the queue with the current job id."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    worker._current_job_id = "job-42"
    worker.cancel_current_job()
    mock_queue.mark_cancelled.assert_called_once_with("job-42")


# ---------------------------------------------------------------------------
# Logger lazy initialisation
# ---------------------------------------------------------------------------


def test_get_logger_returns_logger(qapp, mock_config_manager, mock_queue):
    """_get_logger() returns a logging.Logger instance."""
    import logging

    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    with patch("services.analysis_worker.logger", None):
        logger = worker._get_logger()
    assert isinstance(logger, logging.Logger)


# ---------------------------------------------------------------------------
# Import path
# ---------------------------------------------------------------------------


def test_importable_from_services(qapp):
    """AnalysisWorker is importable from services.analysis_worker (new canonical location)."""
    from services.analysis_worker import AnalysisWorker  # noqa: F401 – just verifying import

    assert AnalysisWorker is not None
