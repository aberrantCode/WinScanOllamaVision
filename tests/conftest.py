"""
Root conftest.py for pytest configuration.

Provides shared fixtures for all tests.
"""

import logging

import pytest


@pytest.fixture(scope="session", autouse=True)
def initialize_logging():
    """Initialize logging service for all tests.

    This fixture runs automatically before any tests,
    ensuring the logging service is initialized.
    """
    from services.logging_service import LoggingService

    # Initialize with minimal logging for tests
    LoggingService().initialize(log_level=logging.WARNING, console_output=False)

    yield

    # Cleanup is handled automatically
