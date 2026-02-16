"""Pytest configuration and fixtures for config tests."""

import logging
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_logging_service(monkeypatch):
    """
    Mock the logging service to avoid initialization errors in tests.

    This fixture automatically runs for all tests in the config module.
    It patches get_logger() to return a mock logger instead of requiring
    LoggingService initialization.
    """
    # Create a mock logger that behaves like a real logger
    mock_logger = MagicMock(spec=logging.Logger)

    # Configure the mock to return itself for method chaining
    mock_logger.info.return_value = None
    mock_logger.debug.return_value = None
    mock_logger.warning.return_value = None
    mock_logger.error.return_value = None
    mock_logger.critical.return_value = None

    # Patch the get_logger function in the services.logging_service module
    def mock_get_logger():
        return mock_logger

    # Patch both the module-level function and any imports
    monkeypatch.setattr("services.logging_service.get_logger", mock_get_logger)

    return mock_logger
