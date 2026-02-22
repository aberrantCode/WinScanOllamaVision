"""
Tests for DiscoveryWorker
"""

import sqlite3
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication

from config.config_manager import ConfigManager
from services.discovery_worker import DiscoveryWorker


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
    return MagicMock(spec=ConfigManager)


def test_discovery_worker_initialization(qapp, mock_config):
    """Test DiscoveryWorker initializes correctly"""
    directories = ["/test/dir1", "/test/dir2"]
    worker = DiscoveryWorker(mock_config, directories)

    assert worker.config_manager == mock_config
    assert worker.directories == directories
    assert worker._stop_requested is False


@patch("services.discovery_worker.AnalysisDB")
@patch("services.discovery_worker.DiscoveryService")
def test_discovery_worker_successful_discovery(
    mock_service_class, mock_db_class, qapp, mock_config
):
    """Test DiscoveryWorker runs discovery successfully"""
    # Setup mocks
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db

    mock_service = MagicMock()
    mock_service_class.return_value = mock_service
    mock_service.discover_images.return_value = 5  # Simulate 5 new files discovered

    # Create worker
    directories = ["/test/dir"]
    worker = DiscoveryWorker(mock_config, directories)

    # Track signals
    finished_count = []
    error_messages = []

    def on_finished(count):
        finished_count.append(count)

    def on_error(error):
        error_messages.append(error)

    worker.finished.connect(on_finished)
    worker.error.connect(on_error)

    # Run worker in event loop
    worker.start()

    # Wait for thread to finish with timeout
    event_loop = QEventLoop()
    worker.finished.connect(event_loop.quit)
    worker.error.connect(event_loop.quit)

    # Timeout after 2 seconds
    QTimer.singleShot(2000, event_loop.quit)
    event_loop.exec()

    # Wait for thread to actually finish
    worker.wait(1000)

    # Verify finished signal was emitted with correct count
    assert len(finished_count) == 1
    assert finished_count[0] == 5

    # Verify no errors
    assert len(error_messages) == 0

    # Verify discovery service was called
    mock_service.discover_images.assert_called_once()

    # Verify database was closed
    mock_db.close.assert_called_once()


@patch("services.discovery_worker.AnalysisDB")
@patch("services.discovery_worker.DiscoveryService")
def test_discovery_worker_handles_errors(mock_service_class, mock_db_class, qapp, mock_config):
    """Test DiscoveryWorker handles errors gracefully"""
    # Setup mocks
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db

    mock_service = MagicMock()
    mock_service_class.return_value = mock_service
    # Simulate error during discovery
    mock_service.discover_images.side_effect = Exception("Database connection failed")

    # Create worker
    directories = ["/test/dir"]
    worker = DiscoveryWorker(mock_config, directories)

    # Track signals
    finished_count = []
    error_messages = []

    def on_finished(count):
        finished_count.append(count)

    def on_error(error):
        error_messages.append(error)

    worker.finished.connect(on_finished)
    worker.error.connect(on_error)

    # Run worker in event loop
    worker.start()

    # Wait for thread to finish with timeout
    event_loop = QEventLoop()
    worker.finished.connect(event_loop.quit)
    worker.error.connect(event_loop.quit)

    # Timeout after 2 seconds
    QTimer.singleShot(2000, event_loop.quit)
    event_loop.exec()

    # Wait for thread to actually finish
    worker.wait(1000)

    # Verify error signal was emitted
    assert len(error_messages) == 1
    assert "Database connection failed" in error_messages[0]

    # Verify database was closed even after error
    mock_db.close.assert_called_once()


@patch("services.discovery_worker.AnalysisDB")
@patch("services.discovery_worker.DiscoveryService")
def test_discovery_worker_cancellation(mock_service_class, mock_db_class, qapp, mock_config):
    """Test DiscoveryWorker can be cancelled mid-discovery"""
    # Setup mocks
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db

    mock_service = MagicMock()
    mock_service_class.return_value = mock_service

    # Simulate cancellation during discovery
    def mock_discover_images(directories, progress_callback=None):
        if progress_callback:
            # Call progress callback which will check for cancellation
            progress_callback("Discovering...", 1, 10)
        return 0

    mock_service.discover_images.side_effect = mock_discover_images

    # Create worker
    directories = ["/test/dir"]
    worker = DiscoveryWorker(mock_config, directories)

    # Track signals
    finished_count = []

    def on_finished(count):
        finished_count.append(count)

    worker.finished.connect(on_finished)

    # Request stop before starting
    worker.stop()

    # Run worker in event loop
    worker.start()

    # Wait for thread to finish with timeout
    event_loop = QEventLoop()
    worker.finished.connect(event_loop.quit)

    # Timeout after 2 seconds
    QTimer.singleShot(2000, event_loop.quit)
    event_loop.exec()

    # Wait for thread to actually finish
    worker.wait(1000)

    # Verify finished signal was emitted with count 0 (cancelled)
    assert len(finished_count) == 1
    assert finished_count[0] == 0

    # Verify database was closed
    mock_db.close.assert_called_once()


@patch("services.discovery_worker.AnalysisDB")
@patch("services.discovery_worker.DiscoveryService")
def test_discovery_worker_emits_progress_signals(
    mock_service_class, mock_db_class, qapp, mock_config
):
    """Test DiscoveryWorker emits progress signals during discovery"""
    # Setup mocks
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db

    mock_service = MagicMock()
    mock_service_class.return_value = mock_service

    # Simulate progress callbacks
    def mock_discover_images(directories, progress_callback=None):
        if progress_callback:
            progress_callback("Finding files...", 1, 10)
            progress_callback("Finding files...", 5, 10)
            progress_callback("Finding files...", 10, 10)
        return 3

    mock_service.discover_images.side_effect = mock_discover_images

    # Create worker
    directories = ["/test/dir"]
    worker = DiscoveryWorker(mock_config, directories)

    # Track progress signals
    progress_updates = []

    def on_progress(status, current, total):
        progress_updates.append((status, current, total))

    worker.progress.connect(on_progress)

    # Run worker in event loop
    worker.start()

    # Wait for thread to finish with timeout
    event_loop = QEventLoop()
    worker.finished.connect(event_loop.quit)

    # Timeout after 2 seconds
    QTimer.singleShot(2000, event_loop.quit)
    event_loop.exec()

    # Wait for thread to actually finish
    worker.wait(1000)

    # Verify progress signals were emitted
    assert len(progress_updates) == 3
    assert progress_updates[0] == ("Finding files...", 1, 10)
    assert progress_updates[1] == ("Finding files...", 5, 10)
    assert progress_updates[2] == ("Finding files...", 10, 10)


@patch("services.discovery_worker.AnalysisDB")
@patch("services.discovery_worker.DiscoveryService")
def test_discovery_worker_empty_directories(mock_service_class, mock_db_class, qapp, mock_config):
    """Test DiscoveryWorker with empty directory list"""
    # Setup mocks
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db

    mock_service = MagicMock()
    mock_service_class.return_value = mock_service
    mock_service.discover_images.return_value = 0

    # Create worker with empty directories
    directories = []
    worker = DiscoveryWorker(mock_config, directories)

    # Track signals
    finished_count = []

    def on_finished(count):
        finished_count.append(count)

    worker.finished.connect(on_finished)

    # Run worker in event loop
    worker.start()

    # Wait for thread to finish with timeout
    event_loop = QEventLoop()
    worker.finished.connect(event_loop.quit)

    # Timeout after 2 seconds
    QTimer.singleShot(2000, event_loop.quit)
    event_loop.exec()

    # Wait for thread to actually finish
    worker.wait(1000)

    # Verify finished signal was emitted with count 0
    assert len(finished_count) == 1
    assert finished_count[0] == 0

    # Verify database was closed
    mock_db.close.assert_called_once()


@patch("services.discovery_worker.AnalysisDB")
@patch("services.discovery_worker.DiscoveryService")
def test_discovery_worker_handles_sqlite_error(
    mock_service_class, mock_db_class, qapp, mock_config
):
    """Test DiscoveryWorker handles sqlite3.Error specifically"""
    # Setup mocks
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db

    mock_service = MagicMock()
    mock_service_class.return_value = mock_service
    # Simulate sqlite3.Error during discovery
    mock_service.discover_images.side_effect = sqlite3.Error("Database is locked")

    # Create worker
    directories = ["/test/dir"]
    worker = DiscoveryWorker(mock_config, directories)

    # Track signals
    error_messages = []

    def on_error(error):
        error_messages.append(error)

    worker.error.connect(on_error)

    # Run worker in event loop
    worker.start()

    # Wait for thread to finish with timeout
    event_loop = QEventLoop()
    worker.error.connect(event_loop.quit)
    worker.finished.connect(event_loop.quit)

    # Timeout after 2 seconds
    QTimer.singleShot(2000, event_loop.quit)
    event_loop.exec()

    # Wait for thread to actually finish
    worker.wait(1000)

    # Verify error signal was emitted with sqlite3 error
    assert len(error_messages) == 1
    assert "Database error" in error_messages[0]
    assert "Database is locked" in error_messages[0]

    # Verify database was closed even after error
    mock_db.close.assert_called_once()


@patch("services.discovery_worker.AnalysisDB")
@patch("services.discovery_worker.DiscoveryService")
def test_discovery_worker_handles_oserror(mock_service_class, mock_db_class, qapp, mock_config):
    """Test DiscoveryWorker handles OSError specifically"""
    # Setup mocks
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db

    mock_service = MagicMock()
    mock_service_class.return_value = mock_service
    # Simulate OSError during discovery (e.g., permission denied, file not found)
    mock_service.discover_images.side_effect = OSError("Permission denied")

    # Create worker
    directories = ["/test/dir"]
    worker = DiscoveryWorker(mock_config, directories)

    # Track signals
    error_messages = []

    def on_error(error):
        error_messages.append(error)

    worker.error.connect(on_error)

    # Run worker in event loop
    worker.start()

    # Wait for thread to finish with timeout
    event_loop = QEventLoop()
    worker.error.connect(event_loop.quit)
    worker.finished.connect(event_loop.quit)

    # Timeout after 2 seconds
    QTimer.singleShot(2000, event_loop.quit)
    event_loop.exec()

    # Wait for thread to actually finish
    worker.wait(1000)

    # Verify error signal was emitted with OSError
    assert len(error_messages) == 1
    assert "File system error" in error_messages[0]
    assert "Permission denied" in error_messages[0]

    # Verify database was closed even after error
    mock_db.close.assert_called_once()


# ---------------------------------------------------------------------------
# Direct run() calls — these cover the thread body without background threads
# so that coverage.py tracks the executed lines.
# ---------------------------------------------------------------------------


@patch("services.discovery_worker.AnalysisDB")
@patch("services.discovery_worker.DiscoveryService")
def test_run_direct_successful_discovery(mock_service_class, mock_db_class, qapp, mock_config):
    """Calling run() directly covers the run body and emits finished signal."""
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db

    mock_service = MagicMock()
    mock_service_class.return_value = mock_service
    mock_service.discover_images.return_value = 7

    worker = DiscoveryWorker(mock_config, ["/test/dir"])

    finished_count = []
    worker.finished.connect(lambda c: finished_count.append(c))

    mock_logger = MagicMock()
    with patch("services.discovery_worker.logger", mock_logger):
        worker.run()

    assert finished_count == [7]
    mock_db.close.assert_called_once()
    mock_service.discover_images.assert_called_once()


@patch("services.discovery_worker.AnalysisDB")
@patch("services.discovery_worker.DiscoveryService")
def test_run_direct_emits_progress_signals(mock_service_class, mock_db_class, qapp, mock_config):
    """run() forwards progress signals when discover_images calls the callback (covers line 70)."""
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db

    mock_service = MagicMock()
    mock_service_class.return_value = mock_service

    def fake_discover(directories, progress_callback=None):
        if progress_callback:
            progress_callback("Finding files...", 1, 5)
            progress_callback("Finding files...", 3, 5)
            progress_callback("Finding files...", 5, 5)
        return 3

    mock_service.discover_images.side_effect = fake_discover

    worker = DiscoveryWorker(mock_config, ["/test/dir"])

    progress_updates = []
    worker.progress.connect(lambda s, c, t: progress_updates.append((s, c, t)))

    mock_logger = MagicMock()
    with patch("services.discovery_worker.logger", mock_logger):
        worker.run()

    assert len(progress_updates) == 3
    assert progress_updates[0] == ("Finding files...", 1, 5)
    assert progress_updates[2] == ("Finding files...", 5, 5)


@patch("services.discovery_worker.AnalysisDB")
@patch("services.discovery_worker.DiscoveryService")
def test_run_direct_interrupted_error(mock_service_class, mock_db_class, qapp, mock_config):
    """Calling run() directly with cancellation covers the InterruptedError branch."""
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db

    mock_service = MagicMock()
    mock_service_class.return_value = mock_service

    # Worker is already stopped; progress_callback will raise InterruptedError
    def fake_discover(directories, progress_callback=None):
        if progress_callback:
            progress_callback("scanning", 1, 10)
        return 0

    mock_service.discover_images.side_effect = fake_discover

    worker = DiscoveryWorker(mock_config, ["/test/dir"])
    worker._stop_requested = True  # Ensures progress_callback raises

    finished_count = []
    worker.finished.connect(lambda c: finished_count.append(c))

    mock_logger = MagicMock()
    with patch("services.discovery_worker.logger", mock_logger):
        worker.run()

    assert finished_count == [0]
    mock_db.close.assert_called_once()


@patch("services.discovery_worker.AnalysisDB")
@patch("services.discovery_worker.DiscoveryService")
def test_run_direct_sqlite_error(mock_service_class, mock_db_class, qapp, mock_config):
    """Calling run() directly with sqlite3.Error covers the sqlite error branch."""
    import sqlite3

    mock_db = MagicMock()
    mock_db_class.return_value = mock_db

    mock_service = MagicMock()
    mock_service_class.return_value = mock_service
    mock_service.discover_images.side_effect = sqlite3.Error("table locked")

    worker = DiscoveryWorker(mock_config, ["/test/dir"])

    error_messages = []
    worker.error.connect(lambda msg: error_messages.append(msg))

    mock_logger = MagicMock()
    with patch("services.discovery_worker.logger", mock_logger):
        worker.run()

    assert len(error_messages) == 1
    assert "Database error" in error_messages[0]
    assert "table locked" in error_messages[0]
    mock_db.close.assert_called_once()


@patch("services.discovery_worker.AnalysisDB")
@patch("services.discovery_worker.DiscoveryService")
def test_run_direct_oserror(mock_service_class, mock_db_class, qapp, mock_config):
    """Calling run() directly with OSError covers the file system error branch."""
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db

    mock_service = MagicMock()
    mock_service_class.return_value = mock_service
    mock_service.discover_images.side_effect = OSError("no such directory")

    worker = DiscoveryWorker(mock_config, ["/test/dir"])

    error_messages = []
    worker.error.connect(lambda msg: error_messages.append(msg))

    mock_logger = MagicMock()
    with patch("services.discovery_worker.logger", mock_logger):
        worker.run()

    assert len(error_messages) == 1
    assert "File system error" in error_messages[0]
    mock_db.close.assert_called_once()


@patch("services.discovery_worker.AnalysisDB")
@patch("services.discovery_worker.DiscoveryService")
def test_run_direct_generic_exception(mock_service_class, mock_db_class, qapp, mock_config):
    """Calling run() directly with a generic Exception covers the unexpected error branch."""
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db

    mock_service = MagicMock()
    mock_service_class.return_value = mock_service
    mock_service.discover_images.side_effect = ValueError("unexpected problem")

    worker = DiscoveryWorker(mock_config, ["/test/dir"])

    error_messages = []
    worker.error.connect(lambda msg: error_messages.append(msg))

    mock_logger = MagicMock()
    with patch("services.discovery_worker.logger", mock_logger):
        worker.run()

    assert len(error_messages) == 1
    assert "Unexpected discovery error" in error_messages[0]
    mock_db.close.assert_called_once()


# ---------------------------------------------------------------------------
# _get_logger() — lazy initialisation (covers lines 49-51)
# ---------------------------------------------------------------------------


def test_get_logger_lazy_init_when_module_logger_is_none(qapp, mock_config):
    """_get_logger() initialises the module-level logger when it is None."""
    import logging

    worker = DiscoveryWorker(mock_config, [])

    mock_logger_instance = MagicMock(spec=logging.Logger)

    with (
        patch("services.discovery_worker.logger", None),
        patch("services.logging_service.get_logger", return_value=mock_logger_instance),
    ):
        result = worker._get_logger()

    assert result is mock_logger_instance


def test_get_logger_returns_cached_logger(qapp, mock_config):
    """_get_logger() returns the already-cached module-level logger without re-init."""
    import logging

    worker = DiscoveryWorker(mock_config, [])

    cached = MagicMock(spec=logging.Logger)

    with patch("services.discovery_worker.logger", cached):
        result = worker._get_logger()

    assert result is cached


# ---------------------------------------------------------------------------
# stop() — covers the logger call in stop()
# ---------------------------------------------------------------------------


def test_stop_logs_message(qapp, mock_config):
    """stop() calls _get_logger().info after setting the stop flag."""
    worker = DiscoveryWorker(mock_config, [])

    mock_logger_instance = MagicMock()
    with patch("services.discovery_worker.logger", mock_logger_instance):
        worker.stop()

    assert worker._stop_requested is True
    mock_logger_instance.info.assert_called()
