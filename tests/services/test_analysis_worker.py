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


@pytest.fixture(autouse=True)
def isolate_status_reporter():
    """Replace the module-level get_reporter() with a MagicMock for every test.

    Without this, each worker failure path would open a real SQLite DB in
    the user's AppData directory and pollute real status_events rows.
    """
    with patch("services.analysis_worker.get_reporter") as m:
        m.return_value = MagicMock()
        yield m


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


# ---------------------------------------------------------------------------
# run() — synchronous direct calls to cover the loop body
# ---------------------------------------------------------------------------


def test_run_exits_after_none_job_when_stop_requested(qapp, mock_config_manager, mock_queue):
    """run() breaks from the loop when dequeue returns None and stop flag is set."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)

    def dequeue_side_effect(timeout):
        worker._stop_requested = True
        return None

    mock_queue.dequeue.side_effect = dequeue_side_effect

    worker.run()

    assert mock_queue.dequeue.call_count >= 1
    assert worker._stop_requested is True


def test_run_skips_cancelled_job_without_calling_process_job(qapp, mock_config_manager, mock_queue):
    """run() skips a job that is already cancelled and does not call _process_job."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)

    mock_job = MagicMock()
    mock_job.job_id = "cancelled-job"

    call_count = [0]

    def dequeue_side_effect(timeout):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_job
        worker._stop_requested = True
        return None

    mock_queue.dequeue.side_effect = dequeue_side_effect
    mock_queue.is_job_cancelled.return_value = True

    process_calls = []
    worker._process_job = lambda job: process_calls.append(job)

    worker.run()

    assert len(process_calls) == 0
    mock_queue.is_job_cancelled.assert_called_with("cancelled-job")


def test_run_emits_queue_empty_after_successful_job(qapp, mock_config_manager, mock_queue):
    """run() emits queue_empty signal when pending count reaches 0 after a job."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)

    mock_job = MagicMock()
    mock_job.job_id = "job-1"

    call_count = [0]

    def dequeue_side_effect(timeout):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_job
        worker._stop_requested = True
        return None

    mock_queue.dequeue.side_effect = dequeue_side_effect
    mock_queue.is_job_cancelled.return_value = False
    mock_queue.get_pending_count.return_value = 0
    worker._process_job = MagicMock()

    queue_empty_calls = []
    worker.queue_empty.connect(lambda: queue_empty_calls.append(True))

    worker.run()

    assert len(queue_empty_calls) == 1


def test_run_does_not_emit_queue_empty_when_jobs_pending(qapp, mock_config_manager, mock_queue):
    """run() does not emit queue_empty when there are still pending jobs."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)

    mock_job = MagicMock()
    mock_job.job_id = "job-pending"

    call_count = [0]

    def dequeue_side_effect(timeout):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_job
        worker._stop_requested = True
        return None

    mock_queue.dequeue.side_effect = dequeue_side_effect
    mock_queue.is_job_cancelled.return_value = False
    mock_queue.get_pending_count.return_value = 3  # Still more jobs
    worker._process_job = MagicMock()

    queue_empty_calls = []
    worker.queue_empty.connect(lambda: queue_empty_calls.append(True))

    worker.run()

    assert len(queue_empty_calls) == 0


def test_run_emits_error_on_process_job_exception(qapp, mock_config_manager, mock_queue):
    """run() emits error signal and marks job cancelled when _process_job raises."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)

    mock_job = MagicMock()
    mock_job.job_id = "failing-job"

    call_count = [0]

    def dequeue_side_effect(timeout):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_job
        worker._stop_requested = True
        return None

    mock_queue.dequeue.side_effect = dequeue_side_effect
    mock_queue.is_job_cancelled.return_value = False
    worker._process_job = MagicMock(side_effect=RuntimeError("something went wrong"))

    error_calls = []
    worker.error.connect(lambda jid, msg: error_calls.append((jid, msg)))

    worker.run()

    assert len(error_calls) == 1
    assert error_calls[0][0] == "failing-job"
    assert "something went wrong" in error_calls[0][1]
    mock_queue.mark_cancelled.assert_called_with("failing-job")


def test_run_clears_current_job_id_after_processing(qapp, mock_config_manager, mock_queue):
    """run() resets _current_job_id to None after job finishes."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)

    mock_job = MagicMock()
    mock_job.job_id = "job-99"

    call_count = [0]

    def dequeue_side_effect(timeout):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_job
        worker._stop_requested = True
        return None

    mock_queue.dequeue.side_effect = dequeue_side_effect
    mock_queue.is_job_cancelled.return_value = False
    mock_queue.get_pending_count.return_value = 0
    worker._process_job = MagicMock()

    worker.run()

    assert worker._current_job_id is None


# ---------------------------------------------------------------------------
# _process_job() — SCAN_ALL
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_logger():
    return MagicMock()


def _make_scan_job(job_id="scan-job", force_reanalysis=False):
    from services.analysis_queue import JobType

    job = MagicMock()
    job.job_id = job_id
    job.job_type = JobType.SCAN_ALL
    job.force_reanalysis = force_reanalysis
    return job


def _make_analyze_job(job_id="analyze-job", file_paths=None, force_reanalysis=False):
    from services.analysis_queue import JobType

    job = MagicMock()
    job.job_id = job_id
    job.job_type = JobType.ANALYZE_FILES
    job.force_reanalysis = force_reanalysis
    job.file_paths = file_paths or ["/path/to/file.jpg"]
    return job


def test_process_job_scan_all_emits_job_started(qapp, mock_config_manager, mock_queue, mock_logger):
    """_process_job() emits job_started with description for SCAN_ALL."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    mock_queue.is_job_cancelled.return_value = False
    mock_job = _make_scan_job()

    job_started_calls = []
    worker.job_started.connect(lambda jid, desc: job_started_calls.append((jid, desc)))

    with (
        patch("db.analysis_db.AnalysisDB") as mock_db_class,
        patch("db.metadata_db.MetadataDB") as mock_meta_class,
        patch("services.analysis_service.AnalysisService") as mock_service_class,
        patch("services.analysis_worker.logger", mock_logger),
    ):
        mock_db_class.return_value = MagicMock()
        mock_meta_class.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.scan_all_directories.return_value = {}

        worker._process_job(mock_job)

    assert len(job_started_calls) == 1
    assert job_started_calls[0][0] == "scan-job"
    assert "Scanning" in job_started_calls[0][1]


def test_process_job_scan_all_passes_incremental_flag(
    qapp, mock_config_manager, mock_queue, mock_logger
):
    """_process_job() passes incremental=False when force_reanalysis=True."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    mock_queue.is_job_cancelled.return_value = False
    mock_job = _make_scan_job(force_reanalysis=True)

    with (
        patch("db.analysis_db.AnalysisDB") as mock_db_class,
        patch("db.metadata_db.MetadataDB") as mock_meta_class,
        patch("services.analysis_service.AnalysisService") as mock_service_class,
        patch("services.analysis_worker.logger", mock_logger),
    ):
        mock_db_class.return_value = MagicMock()
        mock_meta_class.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.scan_all_directories.return_value = {}

        worker._process_job(mock_job)

    call_kwargs = mock_service.scan_all_directories.call_args
    assert call_kwargs.kwargs["incremental"] is False


def test_process_job_scan_all_emits_job_finished(
    qapp, mock_config_manager, mock_queue, mock_logger
):
    """_process_job() emits job_finished with stats after successful SCAN_ALL."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    mock_queue.is_job_cancelled.return_value = False
    mock_job = _make_scan_job()

    job_finished_calls = []
    worker.job_finished.connect(lambda jid, stats: job_finished_calls.append((jid, stats)))

    expected_stats = {"analyzed": 5, "cached": 2, "errors": 0}

    with (
        patch("db.analysis_db.AnalysisDB") as mock_db_class,
        patch("db.metadata_db.MetadataDB") as mock_meta_class,
        patch("services.analysis_service.AnalysisService") as mock_service_class,
        patch("services.analysis_worker.logger", mock_logger),
    ):
        mock_db_class.return_value = MagicMock()
        mock_meta_class.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.scan_all_directories.return_value = expected_stats

        worker._process_job(mock_job)

    assert len(job_finished_calls) == 1
    assert job_finished_calls[0][0] == "scan-job"
    assert job_finished_calls[0][1] == expected_stats


def test_process_job_scan_all_cancelled_via_progress_callback(
    qapp, mock_config_manager, mock_queue, mock_logger
):
    """_process_job() handles InterruptedError from progress_callback when job cancelled."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    mock_job = _make_scan_job()

    # Job is cancelled — progress_callback will raise InterruptedError
    mock_queue.is_job_cancelled.return_value = True

    job_finished_calls = []
    worker.job_finished.connect(lambda jid, stats: job_finished_calls.append((jid, stats)))

    with (
        patch("db.analysis_db.AnalysisDB") as mock_db_class,
        patch("db.metadata_db.MetadataDB") as mock_meta_class,
        patch("services.analysis_service.AnalysisService") as mock_service_class,
        patch("services.analysis_worker.logger", mock_logger),
    ):
        mock_db_class.return_value = MagicMock()
        mock_meta_class.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        # Make scan_all_directories invoke the progress_callback, triggering InterruptedError
        def fake_scan(progress_callback, incremental, abort_check):
            progress_callback("scanning...", 1, 10)

        mock_service.scan_all_directories.side_effect = fake_scan

        worker._process_job(mock_job)

    assert len(job_finished_calls) == 1
    assert job_finished_calls[0][1].get("message") == "Job cancelled"


def test_process_job_closes_db_connections_in_finally(
    qapp, mock_config_manager, mock_queue, mock_logger
):
    """_process_job() closes both DB connections in the finally block."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    mock_queue.is_job_cancelled.return_value = False
    mock_job = _make_scan_job()

    with (
        patch("db.analysis_db.AnalysisDB") as mock_db_class,
        patch("db.metadata_db.MetadataDB") as mock_meta_class,
        patch("services.analysis_service.AnalysisService") as mock_service_class,
        patch("services.analysis_worker.logger", mock_logger),
    ):
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_meta = MagicMock()
        mock_meta_class.return_value = mock_meta
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.scan_all_directories.return_value = {}

        worker._process_job(mock_job)

    mock_db.close.assert_called_once()
    mock_meta.close.assert_called_once()


# ---------------------------------------------------------------------------
# _process_job() — ANALYZE_FILES
# ---------------------------------------------------------------------------


def test_process_job_analyze_files_success_increments_analyzed_count(
    qapp, mock_config_manager, mock_queue, mock_logger
):
    """_process_job() counts analyzed files correctly when all succeed."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    mock_queue.is_job_cancelled.return_value = False
    mock_job = _make_analyze_job(file_paths=["/a.jpg", "/b.jpg"])

    job_finished_calls = []
    worker.job_finished.connect(lambda jid, stats: job_finished_calls.append((jid, stats)))

    with (
        patch("db.analysis_db.AnalysisDB") as mock_db_class,
        patch("db.metadata_db.MetadataDB") as mock_meta_class,
        patch("services.analysis_service.AnalysisService") as mock_service_class,
        patch("services.analysis_worker.logger", mock_logger),
    ):
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_meta_class.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service._analyze_single_page.return_value = {"success": True}

        worker._process_job(mock_job)

    assert job_finished_calls[0][1]["analyzed"] == 2
    assert job_finished_calls[0][1]["errors"] == 0


def test_process_job_analyze_files_failure_increments_error_count(
    qapp, mock_config_manager, mock_queue, mock_logger
):
    """_process_job() counts errors when _analyze_single_page returns success=False."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    mock_queue.is_job_cancelled.return_value = False
    mock_job = _make_analyze_job(file_paths=["/bad.jpg"])

    job_finished_calls = []
    worker.job_finished.connect(lambda jid, stats: job_finished_calls.append((jid, stats)))

    with (
        patch("db.analysis_db.AnalysisDB") as mock_db_class,
        patch("db.metadata_db.MetadataDB") as mock_meta_class,
        patch("services.analysis_service.AnalysisService") as mock_service_class,
        patch("services.analysis_worker.logger", mock_logger),
    ):
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_meta_class.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service._analyze_single_page.return_value = {"success": False}

        worker._process_job(mock_job)

    assert job_finished_calls[0][1]["errors"] == 1
    assert job_finished_calls[0][1]["analyzed"] == 0


def test_process_job_analyze_files_emits_file_status_signals(
    qapp, mock_config_manager, mock_queue, mock_logger
):
    """_process_job() emits file_status_changed for ANALYZING then ANALYZED per file."""
    from db.image_status import ImageStatus
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    mock_queue.is_job_cancelled.return_value = False
    mock_job = _make_analyze_job(file_paths=["/file.jpg"])

    status_changes = []
    worker.file_status_changed.connect(lambda path, status: status_changes.append((path, status)))

    with (
        patch("db.analysis_db.AnalysisDB") as mock_db_class,
        patch("db.metadata_db.MetadataDB") as mock_meta_class,
        patch("services.analysis_service.AnalysisService") as mock_service_class,
        patch("services.analysis_worker.logger", mock_logger),
    ):
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_meta_class.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service._analyze_single_page.return_value = {"success": True}

        worker._process_job(mock_job)

    # ANALYZING then ANALYZED
    assert len(status_changes) == 2
    assert status_changes[0][1] == ImageStatus.ANALYZING.value
    assert status_changes[1][1] == ImageStatus.ANALYZED.value


def test_process_job_analyze_files_error_sets_error_status(
    qapp, mock_config_manager, mock_queue, mock_logger
):
    """_process_job() emits ERROR status when analysis fails."""
    from db.image_status import ImageStatus
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    mock_queue.is_job_cancelled.return_value = False
    mock_job = _make_analyze_job(file_paths=["/fail.jpg"])

    status_changes = []
    worker.file_status_changed.connect(lambda path, status: status_changes.append((path, status)))

    with (
        patch("db.analysis_db.AnalysisDB") as mock_db_class,
        patch("db.metadata_db.MetadataDB") as mock_meta_class,
        patch("services.analysis_service.AnalysisService") as mock_service_class,
        patch("services.analysis_worker.logger", mock_logger),
    ):
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_meta_class.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service._analyze_single_page.return_value = {"success": False}

        worker._process_job(mock_job)

    assert status_changes[-1][1] == ImageStatus.ERROR.value


def test_process_job_analyze_files_cancelled_mid_loop(
    qapp, mock_config_manager, mock_queue, mock_logger
):
    """_process_job() stops on cancellation inside the file loop."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    mock_job = _make_analyze_job(file_paths=["/a.jpg", "/b.jpg"])

    # Return False on first call (job check before loop), True on second (inside loop)
    is_cancelled_seq = [False, True]
    call_idx = [0]

    def is_cancelled(job_id):
        idx = call_idx[0]
        call_idx[0] += 1
        return is_cancelled_seq[idx] if idx < len(is_cancelled_seq) else True

    mock_queue.is_job_cancelled.side_effect = is_cancelled

    job_finished_calls = []
    worker.job_finished.connect(lambda jid, stats: job_finished_calls.append((jid, stats)))

    with (
        patch("db.analysis_db.AnalysisDB") as mock_db_class,
        patch("db.metadata_db.MetadataDB") as mock_meta_class,
        patch("services.analysis_service.AnalysisService") as mock_service_class,
        patch("services.analysis_worker.logger", mock_logger),
    ):
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_meta_class.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        worker._process_job(mock_job)

    assert len(job_finished_calls) == 1
    assert job_finished_calls[0][1].get("message") == "Job cancelled"


def test_run_continues_loop_when_job_is_none_and_not_stopped(qapp, mock_config_manager, mock_queue):
    """run() hits the 'continue' path (line 60) when dequeue returns None but stop is False."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)

    call_count = [0]

    def dequeue_side_effect(timeout):
        call_count[0] += 1
        if call_count[0] == 1:
            # stop_requested is still False — triggers line 60 (continue)
            return None
        # Second call: set stop flag and return None to exit
        worker._stop_requested = True
        return None

    mock_queue.dequeue.side_effect = dequeue_side_effect

    worker.run()

    assert call_count[0] == 2  # Loop ran twice: once for continue, once for break


def test_process_job_analyze_files_cancelled_at_loop_start_covers_raise(
    qapp, mock_config_manager, mock_queue, mock_logger
):
    """_process_job() raises InterruptedError at line 144 when job cancelled at start of 2nd file."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    mock_job = _make_analyze_job(file_paths=["/a.jpg", "/b.jpg"])

    # Calls: [line 143 file1=False, progress_callback file1=False, line 143 file2=True]
    is_cancelled_seq = [False, False, True]
    call_idx = [0]

    def is_cancelled(job_id):
        idx = min(call_idx[0], len(is_cancelled_seq) - 1)
        call_idx[0] += 1
        return is_cancelled_seq[idx]

    mock_queue.is_job_cancelled.side_effect = is_cancelled

    job_finished_calls = []
    worker.job_finished.connect(lambda jid, stats: job_finished_calls.append((jid, stats)))

    with (
        patch("db.analysis_db.AnalysisDB") as mock_db_class,
        patch("db.metadata_db.MetadataDB") as mock_meta_class,
        patch("services.analysis_service.AnalysisService") as mock_service_class,
        patch("services.analysis_worker.logger", mock_logger),
    ):
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_meta_class.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service._analyze_single_page.return_value = {"success": True}

        worker._process_job(mock_job)

    # Should emit job_finished with cancelled message after InterruptedError
    assert len(job_finished_calls) == 1
    assert job_finished_calls[0][1].get("message") == "Job cancelled"


def test_process_job_scan_all_abort_check_reflects_cancelled_state(
    qapp, mock_config_manager, mock_queue, mock_logger
):
    """The abort_check callback passed to scan_all_directories reflects is_job_cancelled."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    mock_queue.is_job_cancelled.return_value = False
    mock_job = _make_scan_job()

    captured_abort_check = [None]

    with (
        patch("db.analysis_db.AnalysisDB") as mock_db_class,
        patch("db.metadata_db.MetadataDB") as mock_meta_class,
        patch("services.analysis_service.AnalysisService") as mock_service_class,
        patch("services.analysis_worker.logger", mock_logger),
    ):
        mock_db_class.return_value = MagicMock()
        mock_meta_class.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        def capture_abort_check(progress_callback, incremental, abort_check):
            captured_abort_check[0] = abort_check
            return {}

        mock_service.scan_all_directories.side_effect = capture_abort_check

        worker._process_job(mock_job)

    # abort_check should return False when not cancelled
    assert captured_abort_check[0] is not None
    assert captured_abort_check[0]() is False

    # Set cancelled and check again
    mock_queue.is_job_cancelled.return_value = True
    assert captured_abort_check[0]() is True


# ---------------------------------------------------------------------------
# ANALYZE_FILES — error detail preservation (Phase-0 patch for status history)
# ---------------------------------------------------------------------------


def test_process_job_analyze_files_failure_persists_error_to_db(
    qapp, mock_config_manager, mock_queue, mock_logger
):
    """ANALYZE_FILES must call analysis_db.save_error() on per-file failures.

    Before the Phase-0 patch, the worker only incremented stats["errors"] and
    updated image status — the failure reason from _analyze_single_page was
    silently dropped, leaving the user with 'N errors' and no way to see why.
    """
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    mock_queue.is_job_cancelled.return_value = False
    mock_job = _make_analyze_job(file_paths=["/fail.jpg"])

    with (
        patch("db.analysis_db.AnalysisDB") as mock_db_class,
        patch("db.metadata_db.MetadataDB") as mock_meta_class,
        patch("services.analysis_service.AnalysisService") as mock_service_class,
        patch("services.analysis_worker.logger", mock_logger),
    ):
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_meta_class.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service._analyze_single_page.return_value = {
            "success": False,
            "error": "Provider unreachable",
        }

        worker._process_job(mock_job)

    mock_db.save_error.assert_called_once_with(
        file_path="/fail.jpg",
        error_message="Provider unreachable",
        error_type="analysis_failed",
    )


def test_process_job_analyze_files_failure_populates_error_details_in_stats(
    qapp, mock_config_manager, mock_queue, mock_logger
):
    """stats["error_details"] must carry per-file failure records to the UI.

    This is the data path that backs the clickable "N failed — click for
    details" affordance and the future StatusReporter.error() calls.
    """
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    mock_queue.is_job_cancelled.return_value = False
    mock_job = _make_analyze_job(file_paths=["/a.jpg", "/b.jpg"])

    job_finished_calls = []
    worker.job_finished.connect(lambda jid, stats: job_finished_calls.append((jid, stats)))

    with (
        patch("db.analysis_db.AnalysisDB") as mock_db_class,
        patch("db.metadata_db.MetadataDB") as mock_meta_class,
        patch("services.analysis_service.AnalysisService") as mock_service_class,
        patch("services.analysis_worker.logger", mock_logger),
    ):
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_meta_class.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service._analyze_single_page.side_effect = [
            {"success": False, "error": "File not found"},
            {"success": False, "error": "Bad JSON response"},
        ]

        worker._process_job(mock_job)

    stats = job_finished_calls[0][1]
    assert stats["errors"] == 2
    assert "error_details" in stats
    details = stats["error_details"]
    assert len(details) == 2
    assert details[0] == {
        "file_path": "/a.jpg",
        "error_message": "File not found",
        "error_type": "analysis_failed",
        "job_type": "ANALYZE_FILES",
    }
    assert details[1]["error_message"] == "Bad JSON response"


def test_process_job_analyze_files_success_does_not_populate_error_details(
    qapp, mock_config_manager, mock_queue, mock_logger
):
    """A successful run produces an empty error_details list, not a missing one."""
    from services.analysis_worker import AnalysisWorker

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    mock_queue.is_job_cancelled.return_value = False
    mock_job = _make_analyze_job(file_paths=["/ok.jpg"])

    job_finished_calls = []
    worker.job_finished.connect(lambda jid, stats: job_finished_calls.append((jid, stats)))

    with (
        patch("db.analysis_db.AnalysisDB") as mock_db_class,
        patch("db.metadata_db.MetadataDB") as mock_meta_class,
        patch("services.analysis_service.AnalysisService") as mock_service_class,
        patch("services.analysis_worker.logger", mock_logger),
    ):
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_meta_class.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service._analyze_single_page.return_value = {"success": True}

        worker._process_job(mock_job)

    stats = job_finished_calls[0][1]
    assert stats["error_details"] == []
    mock_db.save_error.assert_not_called()


# ---------------------------------------------------------------------------
# ANALYZE_FILES — StatusReporter emission (Phase-2)
# ---------------------------------------------------------------------------


def test_process_job_analyze_files_failure_emits_status_event(
    qapp, mock_config_manager, mock_queue, mock_logger, isolate_status_reporter
):
    """Per-file failure emits a StatusReporter.error() with user-facing feature + file_path."""
    from services.analysis_worker import AnalysisWorker

    mock_reporter = MagicMock()
    isolate_status_reporter.return_value = mock_reporter

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    mock_queue.is_job_cancelled.return_value = False
    mock_job = _make_analyze_job(job_id="JOB-42", file_paths=["/fail.jpg"])

    with (
        patch("db.analysis_db.AnalysisDB") as mock_db_class,
        patch("db.metadata_db.MetadataDB") as mock_meta_class,
        patch("services.analysis_service.AnalysisService") as mock_service_class,
        patch("services.analysis_worker.logger", mock_logger),
    ):
        mock_db_class.return_value = MagicMock()
        mock_meta_class.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service._analyze_single_page.return_value = {
            "success": False,
            "error": "Provider unreachable",
        }

        worker._process_job(mock_job)

    # Reporter.error() was called for the failing file
    mock_reporter.error.assert_any_call(
        "Analyze → Re-analyze Files",
        "Re-analysis failed: fail.jpg",
        detail="Provider unreachable",
        file_path="/fail.jpg",
        correlation_id="JOB-42",
        context={
            "job_type": "ANALYZE_FILES",
            "force_reanalysis": False,
        },
    )


def test_process_job_analyze_files_emits_summary_event_when_errors(
    qapp, mock_config_manager, mock_queue, mock_logger, isolate_status_reporter
):
    """When any file in the batch fails, a WARN summary event fires with totals."""
    from services.analysis_worker import AnalysisWorker

    mock_reporter = MagicMock()
    isolate_status_reporter.return_value = mock_reporter

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    mock_queue.is_job_cancelled.return_value = False
    mock_job = _make_analyze_job(file_paths=["/a.jpg", "/b.jpg", "/c.jpg"])

    with (
        patch("db.analysis_db.AnalysisDB") as mock_db_class,
        patch("db.metadata_db.MetadataDB") as mock_meta_class,
        patch("services.analysis_service.AnalysisService") as mock_service_class,
        patch("services.analysis_worker.logger", mock_logger),
    ):
        mock_db_class.return_value = MagicMock()
        mock_meta_class.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        # Two failures, one success
        mock_service._analyze_single_page.side_effect = [
            {"success": False, "error": "e1"},
            {"success": True},
            {"success": False, "error": "e2"},
        ]

        worker._process_job(mock_job)

    # Find the summary warn() call — should have the "2 of 3" title
    warn_calls = list(mock_reporter.warn.call_args_list)
    summary_calls = [c for c in warn_calls if "of 3 files failed re-analysis" in c.args[1]]
    assert len(summary_calls) == 1, "expected exactly one summary event"
    assert "2 of 3" in summary_calls[0].args[1]


def test_process_job_analyze_files_no_summary_event_when_all_succeed(
    qapp, mock_config_manager, mock_queue, mock_logger, isolate_status_reporter
):
    """All-success runs produce no WARN summary event."""
    from services.analysis_worker import AnalysisWorker

    mock_reporter = MagicMock()
    isolate_status_reporter.return_value = mock_reporter

    worker = AnalysisWorker(mock_config_manager, mock_queue)
    mock_queue.is_job_cancelled.return_value = False
    mock_job = _make_analyze_job(file_paths=["/ok.jpg"])

    with (
        patch("db.analysis_db.AnalysisDB") as mock_db_class,
        patch("db.metadata_db.MetadataDB") as mock_meta_class,
        patch("services.analysis_service.AnalysisService") as mock_service_class,
        patch("services.analysis_worker.logger", mock_logger),
    ):
        mock_db_class.return_value = MagicMock()
        mock_meta_class.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service._analyze_single_page.return_value = {"success": True}

        worker._process_job(mock_job)

    mock_reporter.warn.assert_not_called()
    mock_reporter.error.assert_not_called()
