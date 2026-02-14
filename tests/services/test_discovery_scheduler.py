"""
Tests for DiscoveryScheduler
"""

from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QApplication

from config.config_manager import ConfigManager
from services.discovery_scheduler import DiscoveryScheduler


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for testing Qt components"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_config():
    """Mock ConfigManager"""
    config = MagicMock(spec=ConfigManager)
    config.get_bool.return_value = True  # Discovery enabled by default
    config.get_int.return_value = 60  # 60 minute interval by default
    return config


def test_discovery_scheduler_initialization(qapp, mock_config):
    """Test DiscoveryScheduler initializes correctly"""
    scheduler = DiscoveryScheduler(mock_config)

    assert scheduler.config_manager == mock_config
    assert scheduler.timer is not None
    assert scheduler.worker is None


@patch("services.discovery_scheduler.AnalysisDB")
def test_discovery_scheduler_start(mock_db_class, qapp, mock_config):
    """Test starting the scheduler"""
    scheduler = DiscoveryScheduler(mock_config)

    # Start scheduler
    scheduler.start()

    # Verify config was checked
    mock_config.get_bool.assert_called_once_with("Discovery", "enabled", True)
    mock_config.get_int.assert_called_once_with("Discovery", "interval_minutes", 60)

    # Verify timer is running
    assert scheduler.timer.isActive()

    # Verify interval is correct (60 minutes = 3,600,000 milliseconds)
    assert scheduler.timer.interval() == 60 * 60 * 1000


@patch("services.discovery_scheduler.AnalysisDB")
def test_discovery_scheduler_start_disabled(mock_db_class, qapp, mock_config):
    """Test scheduler doesn't start when discovery is disabled"""
    # Configure discovery as disabled
    mock_config.get_bool.return_value = False

    scheduler = DiscoveryScheduler(mock_config)
    scheduler.start()

    # Verify timer was not started
    assert not scheduler.timer.isActive()


@patch("services.discovery_scheduler.AnalysisDB")
def test_discovery_scheduler_start_invalid_interval(mock_db_class, qapp, mock_config):
    """Test scheduler doesn't start with invalid interval"""
    # Configure invalid interval
    mock_config.get_int.return_value = 0

    scheduler = DiscoveryScheduler(mock_config)
    scheduler.start()

    # Verify timer was not started
    assert not scheduler.timer.isActive()


@patch("services.discovery_scheduler.AnalysisDB")
def test_discovery_scheduler_stop(mock_db_class, qapp, mock_config):
    """Test stopping the scheduler"""
    scheduler = DiscoveryScheduler(mock_config)

    # Start then stop
    scheduler.start()
    assert scheduler.timer.isActive()

    scheduler.stop()
    assert not scheduler.timer.isActive()


@patch("services.discovery_scheduler.AnalysisDB")
@patch("services.discovery_scheduler.DiscoveryWorker")
def test_discovery_scheduler_run_now(mock_worker_class, mock_db_class, qapp, mock_config):
    """Test manual discovery trigger"""
    # Setup mocks
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db
    mock_db.get_active_directories.return_value = ["/test/dir"]

    mock_worker = MagicMock()
    mock_worker_class.return_value = mock_worker

    scheduler = DiscoveryScheduler(mock_config)

    # Track signals
    started_count = []

    def on_started():
        started_count.append(1)

    scheduler.discovery_started.connect(on_started)

    # Run discovery manually
    scheduler.run_now()

    # Verify discovery was started
    assert len(started_count) == 1

    # Verify worker was created with correct directories
    mock_worker_class.assert_called_once_with(mock_config, ["/test/dir"])
    mock_worker.start.assert_called_once()


@patch("services.discovery_scheduler.AnalysisDB")
@patch("services.discovery_scheduler.DiscoveryWorker")
def test_discovery_scheduler_run_now_no_directories(
    mock_worker_class, mock_db_class, qapp, mock_config
):
    """Test manual discovery with no directories configured"""
    # Setup mocks
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db
    mock_db.get_active_directories.return_value = []  # No directories

    scheduler = DiscoveryScheduler(mock_config)

    # Track signals
    started_count = []

    def on_started():
        started_count.append(1)

    scheduler.discovery_started.connect(on_started)

    # Run discovery manually
    scheduler.run_now()

    # Verify discovery was NOT started (no directories)
    assert len(started_count) == 0
    mock_worker_class.assert_not_called()


@patch("services.discovery_scheduler.AnalysisDB")
@patch("services.discovery_scheduler.DiscoveryWorker")
def test_discovery_scheduler_run_now_already_running(
    mock_worker_class, mock_db_class, qapp, mock_config
):
    """Test manual discovery when worker is already running"""
    # Setup mocks
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db
    mock_db.get_active_directories.return_value = ["/test/dir"]

    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = True  # Simulate worker is running
    mock_worker_class.return_value = mock_worker

    scheduler = DiscoveryScheduler(mock_config)

    # First run
    scheduler.run_now()

    # Try to run again while first is running
    scheduler.run_now()

    # Verify worker was only created once (second run skipped)
    assert mock_worker_class.call_count == 1


@patch("services.discovery_scheduler.AnalysisDB")
@patch("services.discovery_scheduler.DiscoveryWorker")
def test_discovery_scheduler_on_discovery_finished(
    mock_worker_class, mock_db_class, qapp, mock_config
):
    """Test handling discovery finished"""
    # Setup mocks
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db
    mock_db.get_active_directories.return_value = ["/test/dir"]

    mock_worker = MagicMock()
    mock_worker_class.return_value = mock_worker

    scheduler = DiscoveryScheduler(mock_config)

    # Track signals
    finished_counts = []

    def on_finished(count):
        finished_counts.append(count)

    scheduler.discovery_finished.connect(on_finished)

    # Run discovery
    scheduler.run_now()

    # Simulate discovery finishing with 5 new files
    scheduler._on_discovery_finished(5)

    # Verify finished signal was emitted with correct count
    assert len(finished_counts) == 1
    assert finished_counts[0] == 5

    # Verify last_run timestamp was saved
    mock_config.set_setting.assert_called_once()
    call_args = mock_config.set_setting.call_args
    assert call_args[0][0] == "Discovery"
    assert call_args[0][1] == "last_run"
    # Timestamp should be an ISO format string (just check it's a string)
    assert isinstance(call_args[0][2], str)


@patch("services.discovery_scheduler.AnalysisDB")
@patch("services.discovery_scheduler.DiscoveryWorker")
def test_discovery_scheduler_on_discovery_error(
    mock_worker_class, mock_db_class, qapp, mock_config
):
    """Test handling discovery error"""
    # Setup mocks
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db
    mock_db.get_active_directories.return_value = ["/test/dir"]

    mock_worker = MagicMock()
    mock_worker_class.return_value = mock_worker

    scheduler = DiscoveryScheduler(mock_config)

    # Track signals
    error_messages = []

    def on_error(error):
        error_messages.append(error)

    scheduler.discovery_error.connect(on_error)

    # Run discovery
    scheduler.run_now()

    # Simulate discovery error
    scheduler._on_discovery_error("Database connection failed")

    # Verify error signal was emitted with correct message
    assert len(error_messages) == 1
    assert error_messages[0] == "Database connection failed"


@patch("services.discovery_scheduler.AnalysisDB")
@patch("services.discovery_scheduler.DiscoveryWorker")
def test_discovery_scheduler_stop_with_running_worker(
    mock_worker_class, mock_db_class, qapp, mock_config
):
    """Test stopping scheduler with running worker"""
    # Setup mocks
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db
    mock_db.get_active_directories.return_value = ["/test/dir"]

    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = True
    mock_worker_class.return_value = mock_worker

    scheduler = DiscoveryScheduler(mock_config)

    # Run discovery
    scheduler.run_now()

    # Stop scheduler
    scheduler.stop()

    # Verify worker was stopped
    mock_worker.stop.assert_called_once()
    mock_worker.wait.assert_called_once_with(2000)
