"""
conftest.py for file_details tests.

Ensures LoggingService is initialized before any module-level get_logger()
calls in the file_details package trigger a RuntimeError.
"""

import logging


def pytest_configure(config):
    """Initialize LoggingService during pytest configuration (before collection)."""
    from services.logging_service import LoggingService

    svc = LoggingService()
    if svc.logger is None:
        svc.initialize(log_level=logging.WARNING, console_output=False)
