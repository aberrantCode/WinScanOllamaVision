"""Shared fixtures for bundle UI tests.

PyQt6 requires a live QApplication before any QWidget is constructed.
"""

import logging
import sys

import pytest
from PyQt6.QtWidgets import QApplication


def pytest_configure(config):
    """Initialize LoggingService before collection.

    Importing the bundle widgets pulls in ``ui.file_details``, whose modules
    call ``get_logger()`` at import time; without this the collection phase
    raises RuntimeError before any per-test fixture runs.
    """
    from services.logging_service import LoggingService

    svc = LoggingService()
    if svc.logger is None:
        svc.initialize(log_level=logging.WARNING, console_output=False)


@pytest.fixture(scope="session")
def qapp():
    """Provide a session-wide QApplication instance for widget construction."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
