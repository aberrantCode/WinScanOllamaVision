"""
Tests for AnalyzePanel in ui.pipeline.analyze_panel.
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
def mock_analysis_db():
    db = MagicMock()
    db.connection = MagicMock()
    db.connection.fetch_all_dicts = MagicMock(return_value=[])
    return db


@pytest.fixture
def mock_metadata_db():
    return MagicMock()


@pytest.fixture
def mock_config_manager():
    cfg = MagicMock()
    cfg.get_setting.return_value = "dark"
    cfg.get_directories.return_value = []
    return cfg


def _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager):
    from ui.pipeline_window import AnalyzePanel

    with patch("ui.pipeline.analyze_panel.AnalysisWorker"):
        panel = AnalyzePanel(
            analysis_db=mock_analysis_db,
            metadata_db=mock_metadata_db,
            config_manager=mock_config_manager,
            dark_mode=True,
        )
    return panel


# ---------------------------------------------------------------------------
# H1 — debounce _on_file_status_changed
# ---------------------------------------------------------------------------


def test_file_status_changed_does_not_call_refresh_immediately(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """_on_file_status_changed must not call refresh() synchronously."""
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    panel.refresh = MagicMock()

    panel._on_file_status_changed("/some/file.png", "analyzed")

    panel.refresh.assert_not_called()


def test_file_status_changed_rapid_calls_start_timer_once(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """Multiple rapid calls to _on_file_status_changed restart the same timer,
    so refresh() is still only invoked once when it eventually fires."""
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    panel.refresh = MagicMock()

    # Simulate 5 rapid status-change signals
    for i in range(5):
        panel._on_file_status_changed(f"/file{i}.png", "analyzed")

    # Timer is still pending — refresh must not have been called yet
    panel.refresh.assert_not_called()

    # The debounce timer must be active (started but not yet fired)
    assert panel._refresh_debounce_timer.isActive()


def test_file_status_changed_calls_refresh_after_timer_fires(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """refresh() is called exactly once when the debounce timer fires."""
    from PyQt6.QtTest import QTest

    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    panel.refresh = MagicMock()

    panel._on_file_status_changed("/some/file.png", "analyzed")

    # Wait long enough for the 500 ms timer to fire (use 600 ms to be safe)
    QTest.qWait(600)

    panel.refresh.assert_called_once()


def test_debounce_timer_interval_is_500ms(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """Debounce interval is exactly 500 ms."""
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    assert panel._refresh_debounce_timer.interval() == 500


# ---------------------------------------------------------------------------
# H3 — shutdown() replaces dead closeEvent
# ---------------------------------------------------------------------------


def test_shutdown_stops_running_worker(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """shutdown() calls stop() and wait() when the worker is running."""
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    panel._worker.isRunning.return_value = True

    panel.shutdown()

    panel._worker.stop.assert_called_once()
    panel._worker.wait.assert_called_once_with(2000)


def test_shutdown_is_noop_when_worker_idle(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """shutdown() does nothing when the worker is not running."""
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    panel._worker.isRunning.return_value = False

    panel.shutdown()

    panel._worker.stop.assert_not_called()
    panel._worker.wait.assert_not_called()


def test_analyze_panel_has_no_close_event_override(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """AnalyzePanel must not override closeEvent — it never fires on embedded widgets."""
    from ui.pipeline_window import AnalyzePanel

    # closeEvent should not be defined on AnalyzePanel itself (only on QWidget base)
    assert "closeEvent" not in AnalyzePanel.__dict__


# ---------------------------------------------------------------------------
# H4 — unified dark_mode / is_dark_mode
# ---------------------------------------------------------------------------


def test_is_dark_mode_property_matches_dark_mode(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """is_dark_mode must equal dark_mode — both must always agree."""
    for mode in (True, False):
        panel = _make_panel_with_mode(
            qapp, mock_analysis_db, mock_metadata_db, mock_config_manager, mode
        )
        assert panel.is_dark_mode == panel.dark_mode
        assert panel.is_dark_mode == mode


def test_is_dark_mode_not_stored_as_instance_attribute(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """is_dark_mode must be a property, not a duplicate instance attribute in __dict__."""
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    assert "is_dark_mode" not in panel.__dict__


def test_file_details_grid_can_read_is_dark_mode_from_analyze_panel(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """FileDetailsGrid uses hasattr(parent, 'is_dark_mode') — the property must be visible."""
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    assert hasattr(panel, "is_dark_mode")


# ---------------------------------------------------------------------------
# H5 — _stats reset on each run
# ---------------------------------------------------------------------------


def test_on_start_resets_stats_to_zero(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """_on_start() must reset _stats so a second run doesn't inflate totals."""
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)

    # Simulate stats left over from a previous run
    panel._stats = {"analyzed": 10, "cached": 5, "errors": 2, "total_files": 17}

    panel._on_start()

    assert panel._stats == {"analyzed": 0, "cached": 0, "errors": 0, "total_files": 0}


def test_on_start_resets_stats_before_worker_starts(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """Stats must be zeroed even if the worker is already running (re-queue scenario)."""
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    panel._worker.isRunning.return_value = True
    panel._stats = {"analyzed": 3, "cached": 1, "errors": 0, "total_files": 4}

    panel._on_start()

    assert all(v == 0 for v in panel._stats.values())


def test_job_finished_accumulates_onto_zeroed_stats(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """After _on_start() resets stats, _on_job_finished() accumulates correctly."""
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    panel._stats = {"analyzed": 99, "cached": 99, "errors": 99, "total_files": 99}

    panel._on_start()  # resets to zero

    panel._on_job_finished("job-1", {"analyzed": 5, "cached": 2, "errors": 1, "total_files": 8})

    assert panel._stats == {"analyzed": 5, "cached": 2, "errors": 1, "total_files": 8}


def _make_panel_with_mode(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager, dark_mode):
    from ui.pipeline_window import AnalyzePanel

    with patch("ui.pipeline.analyze_panel.AnalysisWorker"):
        return AnalyzePanel(
            analysis_db=mock_analysis_db,
            metadata_db=mock_metadata_db,
            config_manager=mock_config_manager,
            dark_mode=dark_mode,
        )


# ---------------------------------------------------------------------------
# M2 — public is_running property
# ---------------------------------------------------------------------------


def test_is_running_true_when_worker_running(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """is_running must return True when the worker thread is active."""
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    panel._worker.isRunning.return_value = True

    assert panel.is_running is True


def test_is_running_false_when_worker_idle(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """is_running must return False when the worker thread is not running."""
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    panel._worker.isRunning.return_value = False

    assert panel.is_running is False


def test_is_running_is_property_not_attribute(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """is_running must be a property (not stored in __dict__) so callers can't overwrite it."""
    from ui.pipeline_window import AnalyzePanel

    assert isinstance(AnalyzePanel.is_running, property)


def test_window_close_event_calls_shutdown(qapp):
    """DocumentPipelineWindow.closeEvent delegates worker cleanup to analyze_panel.shutdown()."""
    from PyQt6.QtGui import QCloseEvent

    from ui.pipeline_window import DocumentPipelineWindow

    with (
        patch.object(DocumentPipelineWindow, "_build_ui"),
        patch.object(DocumentPipelineWindow, "_apply_theme"),
    ):
        cfg = MagicMock()
        cfg.get_setting.return_value = "dark"
        window = DocumentPipelineWindow(
            analysis_db=MagicMock(),
            metadata_db=MagicMock(),
            config_manager=cfg,
        )

    window._owns_analysis_db = False
    window._owns_metadata_db = False
    window.analyze_panel = MagicMock()

    window.closeEvent(QCloseEvent())

    window.analyze_panel.shutdown.assert_called_once()


# ---------------------------------------------------------------------------
# M9 — timezone-aware datetime in _transform_data_for_grid
# ---------------------------------------------------------------------------


def test_transform_data_for_grid_modified_time_is_timezone_aware(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """_transform_data_for_grid must produce a timezone-aware modified_time."""
    import time
    from datetime import timezone

    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)

    mtime = time.time()
    raw = [
        {
            "file_path": "/some/file.png",
            "filename": "file.png",
            "status": "analyzed",
            "file_mtime": mtime,
            "analysis_id": 1,
            "confidence_score": 0.9,
        }
    ]

    transformed = panel._transform_data_for_grid(raw)

    assert len(transformed) == 1
    dt = transformed[0]["modified_time"]
    assert dt is not None, "modified_time must not be None when file_mtime is set"
    assert dt.tzinfo is not None, "modified_time must be timezone-aware"
    assert dt.tzinfo == timezone.utc


def test_transform_data_for_grid_none_mtime_gives_none_modified_time(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """_transform_data_for_grid must return None modified_time when file_mtime is 0/None."""
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)

    raw = [
        {
            "file_path": "/some/file.png",
            "filename": "file.png",
            "status": "registered",
            "file_mtime": 0,
            "analysis_id": None,
            "confidence_score": None,
        }
    ]

    transformed = panel._transform_data_for_grid(raw)

    assert len(transformed) == 1
    assert transformed[0]["modified_time"] is None
