"""
Tests for DiscoveryWorker
"""

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
