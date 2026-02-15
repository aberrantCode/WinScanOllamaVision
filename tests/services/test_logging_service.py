"""
Comprehensive tests for LoggingService.

Tests singleton pattern, log file creation, and logging methods.
"""

import logging
import os
import tempfile
from unittest.mock import patch

import pytest

from services.logging_service import LoggingService, get_logger


class TestLoggingService:
    """Tests for LoggingService class"""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton state before each test"""
        LoggingService._instance = None
        LoggingService._initialized = False
        yield
        # Cleanup after test - close all handlers to release file locks
        if LoggingService._instance and LoggingService._instance.logger:
            for handler in LoggingService._instance.logger.handlers[:]:
                handler.close()
                LoggingService._instance.logger.removeHandler(handler)
        LoggingService._instance = None
        LoggingService._initialized = False

    @pytest.fixture
    def temp_appdata(self):
        """Create temporary AppData directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Manual cleanup with handler closing
        import shutil
        import time

        # Close any handlers first
        if LoggingService._instance and LoggingService._instance.logger:
            for handler in LoggingService._instance.logger.handlers[:]:
                handler.close()
                LoggingService._instance.logger.removeHandler(handler)

        # Retry cleanup for Windows file locks
        for attempt in range(3):
            try:
                shutil.rmtree(temp_dir, ignore_errors=False)
                break
            except PermissionError:
                if attempt < 2:
                    time.sleep(0.1)
                else:
                    # Final attempt with ignore_errors
                    shutil.rmtree(temp_dir, ignore_errors=True)

    def test_singleton_pattern_returns_same_instance(self):
        # Act
        service1 = LoggingService()
        service2 = LoggingService()

        # Assert
        assert service1 is service2

    def test_init_only_runs_once(self):
        # Act
        _ = LoggingService()
        _ = LoggingService()

        # Assert - _initialized should only be set once
        assert LoggingService._initialized is True

    def test_initialize_creates_log_directory(self, temp_appdata):
        # Arrange
        service = LoggingService()

        # Act
        with patch.dict(os.environ, {"APPDATA": temp_appdata}):
            service.initialize(app_name="TestApp")

        # Assert
        log_dir = os.path.join(temp_appdata, "TestApp", "logs")
        assert os.path.exists(log_dir)

    def test_initialize_creates_log_file(self, temp_appdata):
        # Arrange
        service = LoggingService()

        # Act
        with patch.dict(os.environ, {"APPDATA": temp_appdata}):
            service.initialize(app_name="TestApp")

        # Assert
        log_file = os.path.join(temp_appdata, "TestApp", "logs", "app.log")
        assert service.log_file_path == log_file

    def test_initialize_sets_logger(self, temp_appdata):
        # Arrange
        service = LoggingService()

        # Act
        with patch.dict(os.environ, {"APPDATA": temp_appdata}):
            service.initialize(app_name="TestApp")

        # Assert
        assert service.logger is not None
        assert isinstance(service.logger, logging.Logger)

    def test_initialize_only_runs_once(self, temp_appdata):
        # Arrange
        service = LoggingService()

        # Act
        with patch.dict(os.environ, {"APPDATA": temp_appdata}):
            service.initialize(app_name="TestApp", log_level=logging.DEBUG)
            first_logger = service.logger
            # Try to initialize again with different level
            service.initialize(app_name="TestApp", log_level=logging.ERROR)

        # Assert - should be same logger instance
        assert service.logger is first_logger

    def test_initialize_sets_log_level(self, temp_appdata):
        # Arrange
        service = LoggingService()

        # Act
        with patch.dict(os.environ, {"APPDATA": temp_appdata}):
            service.initialize(app_name="TestApp", log_level=logging.DEBUG)

        # Assert
        assert service.logger.level == logging.DEBUG

    def test_initialize_creates_rotating_file_handler(self, temp_appdata):
        # Arrange
        service = LoggingService()

        # Act
        with patch.dict(os.environ, {"APPDATA": temp_appdata}):
            service.initialize(app_name="TestApp", max_bytes=1024, backup_count=3)

        # Assert - only file handler by default (console_output=False by default)
        handlers = service.logger.handlers
        assert len(handlers) == 1  # File handler only
        file_handler = handlers[0]
        assert isinstance(file_handler, logging.handlers.RotatingFileHandler)

    def test_get_logger_returns_logger_when_initialized(self, temp_appdata):
        # Arrange
        service = LoggingService()
        with patch.dict(os.environ, {"APPDATA": temp_appdata}):
            service.initialize(app_name="TestApp")

        # Act
        logger = service.get_logger()

        # Assert
        assert logger is not None
        assert isinstance(logger, logging.Logger)

    def test_get_logger_raises_when_not_initialized(self):
        # Arrange
        service = LoggingService()

        # Act & Assert
        with pytest.raises(RuntimeError, match="LoggingService not initialized"):
            service.get_logger()

    def test_get_log_file_path_returns_path(self, temp_appdata):
        # Arrange
        service = LoggingService()
        with patch.dict(os.environ, {"APPDATA": temp_appdata}):
            service.initialize(app_name="TestApp")

        # Act
        path = service.get_log_file_path()

        # Assert
        assert path is not None
        assert path.endswith("app.log")

    def test_get_log_file_path_returns_none_when_not_initialized(self):
        # Arrange
        service = LoggingService()

        # Act
        path = service.get_log_file_path()

        # Assert
        assert path is None

    def test_debug_logs_message(self, temp_appdata):
        # Arrange
        service = LoggingService()
        with patch.dict(os.environ, {"APPDATA": temp_appdata}):
            service.initialize(app_name="TestApp", log_level=logging.DEBUG)

        # Act
        service.debug("Test debug message")

        # Assert - check log file contains message
        with open(service.log_file_path) as f:
            content = f.read()
            assert "Test debug message" in content
            assert "DEBUG" in content

    def test_info_logs_message(self, temp_appdata):
        # Arrange
        service = LoggingService()
        with patch.dict(os.environ, {"APPDATA": temp_appdata}):
            service.initialize(app_name="TestApp")

        # Act
        service.info("Test info message")

        # Assert
        with open(service.log_file_path) as f:
            content = f.read()
            assert "Test info message" in content

    def test_warning_logs_message(self, temp_appdata):
        # Arrange
        service = LoggingService()
        with patch.dict(os.environ, {"APPDATA": temp_appdata}):
            service.initialize(app_name="TestApp")

        # Act
        service.warning("Test warning message")

        # Assert
        with open(service.log_file_path) as f:
            content = f.read()
            assert "Test warning message" in content
            assert "WARNING" in content

    def test_error_logs_message(self, temp_appdata):
        # Arrange
        service = LoggingService()
        with patch.dict(os.environ, {"APPDATA": temp_appdata}):
            service.initialize(app_name="TestApp")

        # Act
        service.error("Test error message")

        # Assert
        with open(service.log_file_path) as f:
            content = f.read()
            assert "Test error message" in content
            assert "ERROR" in content

    def test_error_includes_traceback_when_exc_info_true(self, temp_appdata):
        # Arrange
        service = LoggingService()
        with patch.dict(os.environ, {"APPDATA": temp_appdata}):
            service.initialize(app_name="TestApp")

        # Act
        try:
            raise ValueError("Test exception")
        except ValueError:
            service.error("Error occurred", exc_info=True)

        # Assert
        with open(service.log_file_path) as f:
            content = f.read()
            assert "Error occurred" in content
            assert "Traceback" in content

    def test_critical_logs_message(self, temp_appdata):
        # Arrange
        service = LoggingService()
        with patch.dict(os.environ, {"APPDATA": temp_appdata}):
            service.initialize(app_name="TestApp")

        # Act
        service.critical("Test critical message")

        # Assert
        with open(service.log_file_path) as f:
            content = f.read()
            assert "Test critical message" in content
            assert "CRITICAL" in content

    def test_exception_logs_with_traceback(self, temp_appdata):
        # Arrange
        service = LoggingService()
        with patch.dict(os.environ, {"APPDATA": temp_appdata}):
            service.initialize(app_name="TestApp")

        # Act
        try:
            raise RuntimeError("Test exception")
        except RuntimeError:
            service.exception("Exception caught")

        # Assert
        with open(service.log_file_path) as f:
            content = f.read()
            assert "Exception caught" in content
            assert "RuntimeError" in content
            assert "Traceback" in content

    def test_clear_log_file_clears_content(self, temp_appdata):
        # Arrange
        service = LoggingService()
        with patch.dict(os.environ, {"APPDATA": temp_appdata}):
            service.initialize(app_name="TestApp")
            service.info("Message before clear")

        # Act
        service.clear_log_file()

        # Assert
        with open(service.log_file_path) as f:
            content = f.read()
            # Should only have the "Log file cleared" message
            assert "Message before clear" not in content

    def test_clear_log_file_handles_nonexistent_file(self, temp_appdata):
        # Arrange
        service = LoggingService()
        with patch.dict(os.environ, {"APPDATA": temp_appdata}):
            service.initialize(app_name="TestApp")
            # Close handlers to release file lock
            for handler in service.logger.handlers[:]:
                handler.close()
                service.logger.removeHandler(handler)
            # Remove log file
            os.remove(service.log_file_path)

        # Act - should not raise exception
        service.log_file_path = None  # Simulate uninitialized state
        service.clear_log_file()

        # Assert - test passes if no exception raised
        pass

    def test_initialize_uses_fallback_when_appdata_not_set(self):
        # Arrange
        service = LoggingService()

        # Act
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("os.path.expanduser") as mock_expand,
            patch("os.makedirs"),  # Mock makedirs to avoid permission errors on CI
            patch("services.logging_service.RotatingFileHandler") as mock_handler,
        ):
            mock_expand.return_value = "/home/user"
            # Configure mock handler to have a level attribute
            mock_handler.return_value.level = 20  # INFO level
            service.initialize(app_name="TestApp")

        # Assert
        assert "/home/user" in service.log_file_path
        assert "AppData" in service.log_file_path


class TestGetLoggerFunction:
    """Tests for get_logger convenience function"""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton state before each test"""
        LoggingService._instance = None
        LoggingService._initialized = False
        yield
        # Cleanup after test - close all handlers to release file locks
        if LoggingService._instance and LoggingService._instance.logger:
            for handler in LoggingService._instance.logger.handlers[:]:
                handler.close()
                LoggingService._instance.logger.removeHandler(handler)
        LoggingService._instance = None
        LoggingService._initialized = False

    @pytest.fixture
    def temp_appdata(self):
        """Create temporary AppData directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Manual cleanup with handler closing
        import shutil
        import time

        # Close any handlers first
        if LoggingService._instance and LoggingService._instance.logger:
            for handler in LoggingService._instance.logger.handlers[:]:
                handler.close()
                LoggingService._instance.logger.removeHandler(handler)

        # Retry cleanup for Windows file locks
        for attempt in range(3):
            try:
                shutil.rmtree(temp_dir, ignore_errors=False)
                break
            except PermissionError:
                if attempt < 2:
                    time.sleep(0.1)
                else:
                    # Final attempt with ignore_errors
                    shutil.rmtree(temp_dir, ignore_errors=True)

    def test_get_logger_returns_logger_instance(self, temp_appdata):
        # Arrange
        service = LoggingService()
        with patch.dict(os.environ, {"APPDATA": temp_appdata}):
            service.initialize(app_name="TestApp")

        # Act
        logger = get_logger()

        # Assert
        assert isinstance(logger, logging.Logger)

    def test_get_logger_raises_when_not_initialized(self):
        # Act & Assert
        with pytest.raises(RuntimeError, match="LoggingService not initialized"):
            get_logger()
