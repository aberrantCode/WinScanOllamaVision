"""
Root conftest.py for pytest configuration.

Provides shared fixtures for all tests.
"""

import logging

import pytest


@pytest.fixture(autouse=True)
def initialize_logging():
    """Ensure LoggingService is initialized before every test.

    Using function scope (the default) so this re-runs before each test.
    test_logging_service.py resets LoggingService._instance to None after
    every test it runs; without re-initialization subsequent tests that call
    get_logger() would raise RuntimeError.

    The guard (``if svc.logger is None``) makes this a no-op for the vast
    majority of tests where the singleton is already alive, so there is no
    meaningful overhead.
    """
    from services.logging_service import LoggingService

    svc = LoggingService()
    if svc.logger is None:
        svc.initialize(log_level=logging.WARNING, console_output=False)

    yield
