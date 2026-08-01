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
    from ui.pipeline import AnalyzePanel

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
    from ui.pipeline import AnalyzePanel

    # closeEvent should not be defined on AnalyzePanel itself (only on QWidget base)
    assert "closeEvent" not in AnalyzePanel.__dict__


# ---------------------------------------------------------------------------
# Refresh button
# ---------------------------------------------------------------------------


def test_refresh_button_exists_and_is_wired(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """The Refresh button must exist, have the correct text, and trigger refresh()."""
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)

    # Verify the button exists
    assert panel._refresh_btn is not None

    # Verify the button text
    assert panel._refresh_btn.text() == "⟳ Refresh"

    # Verify the button's tooltip indicates it reloads the grid
    assert "Reload" in panel._refresh_btn.toolTip()

    # Verify the button has a connected slot by checking the signal receivers
    # (Qt stores a count of receivers for each signal)
    receivers = panel._refresh_btn.receivers(panel._refresh_btn.clicked)
    assert receivers > 0, "Refresh button must have at least one connected slot"


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
    from ui.pipeline import AnalyzePanel

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
    from ui.pipeline import AnalyzePanel

    assert isinstance(AnalyzePanel.is_running, property)


def test_window_close_event_calls_shutdown(qapp):
    """DocumentPipelineWindow.closeEvent delegates worker cleanup to analyze_panel.shutdown()."""
    from PyQt6.QtGui import QCloseEvent

    from ui.pipeline import DocumentPipelineWindow

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


# ---------------------------------------------------------------------------
# Analytics section — Phase 3 additions
# ---------------------------------------------------------------------------


def test_analytics_section_created_in_build_ui(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """AnalyzePanel must create _analytics_section during _build_ui."""
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    assert panel._analytics_section is not None


def test_refresh_analytics_section_does_not_raise_when_db_returns_empty(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """_refresh_analytics_section must handle empty DB result without raising."""
    mock_analysis_db.get_analyzed_pages.return_value = []
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    # Should not raise
    panel._refresh_analytics_section()


def test_refresh_analytics_section_does_not_raise_when_db_fails(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """_refresh_analytics_section must swallow DB errors gracefully."""
    mock_analysis_db.get_analyzed_pages.side_effect = RuntimeError("DB unavailable")
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    # Should not raise
    panel._refresh_analytics_section()


def test_refresh_analytics_section_updates_confidence_label(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """_refresh_analytics_section updates the confidence label when data is available."""
    mock_analysis_db.get_analyzed_pages.return_value = [
        {
            "analyzed_at": "2024-01-01T00:00:00",
            "confidence_score": 0.80,
            "status": "analyzed",
            "document_type": "Invoice",
            "company": "ACME",
            "document_date": "2024-01-01",
            "page_number": 1,
        },
        {
            "analyzed_at": "2024-02-01T00:00:00",
            "confidence_score": 0.60,
            "status": "analyzed",
            "document_type": "Statement",
            "company": "Globex",
            "document_date": "2024-02-01",
            "page_number": 1,
        },
    ]
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    panel._refresh_analytics_section()

    if panel._avg_conf_label:
        text = panel._avg_conf_label.text()
        assert "70.0%" in text


def test_refresh_analytics_updates_error_rate(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """_refresh_analytics_section computes error rate from status field."""
    mock_analysis_db.get_analyzed_pages.return_value = [
        {
            "analyzed_at": "2024-01-01T00:00:00",
            "confidence_score": 0.9,
            "status": "analyzed",
            "document_type": "Invoice",
            "company": "ACME",
            "document_date": "",
            "page_number": 1,
        },
        {
            "analyzed_at": None,
            "had_error": True,
            "confidence_score": None,
            "status": "error",
            "document_type": None,
            "company": None,
            "document_date": None,
            "page_number": None,
        },
    ]
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    panel._refresh_analytics_section()

    if panel._error_rate_label:
        text = panel._error_rate_label.text()
        assert "50.0%" in text


def test_job_finished_calls_refresh_analytics(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """_on_job_finished must trigger _refresh_analytics_section."""
    mock_analysis_db.get_analyzed_pages.return_value = []
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)

    with patch.object(panel, "_refresh_analytics_section") as mock_refresh:
        panel._on_job_finished("job-1", {"analyzed": 1, "cached": 0, "errors": 0, "total_files": 1})

    mock_refresh.assert_called_once()


# ---------------------------------------------------------------------------
# Progress bar behavior — determinate vs. indeterminate
# ---------------------------------------------------------------------------


def test_on_progress_shows_determinate_percentage_when_not_last_file(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """_on_progress with current < total must show a determinate bar with percentage."""
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)

    panel._on_progress("Analyzing x.png...", 2, 5)

    assert panel.progress_bar.maximum() == 5
    assert panel.progress_bar.value() == 2
    assert "40%" in panel.progress_bar.format()


def test_on_progress_switches_to_indeterminate_on_last_file(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """_on_progress with current == total must switch to indeterminate mode (no fake 100%)."""
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)

    panel._on_progress("Analyzing last.png...", 5, 5)

    # Indeterminate mode: setRange(0, 0)
    assert panel.progress_bar.minimum() == 0
    assert panel.progress_bar.maximum() == 0
    # Format must not contain "100%" — only status text
    assert "100%" not in panel.progress_bar.format()
    assert "Analyzing last.png..." in panel.progress_bar.format()


def test_on_progress_indeterminate_when_total_zero(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """_on_progress with total == 0 must remain in indeterminate mode (unchanged behavior)."""
    panel = _make_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)

    panel._on_progress("Starting...", 0, 0)

    # Indeterminate mode: maximum should be 0
    assert panel.progress_bar.maximum() == 0
