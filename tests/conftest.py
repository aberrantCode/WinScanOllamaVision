"""
Shared pytest fixtures for all tests.

Provides database isolation and cleanup to prevent test data leaking into production.
"""

import contextlib
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add src directory to Python path (same as root conftest.py)
src_dir = Path(__file__).parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))


@pytest.fixture(scope="function")
def temp_test_dir():
    """Create temporary directory for test files with guaranteed cleanup."""
    temp_dir = tempfile.mkdtemp(prefix="test_")
    yield temp_dir
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def isolated_analysis_db(temp_test_dir):
    """
    Provide isolated AnalysisDB instance for testing.

    Uses temporary database file that is automatically cleaned up.
    Prevents test data from leaking into production database.
    """
    from db.analysis_db import AnalysisDB

    db_path = os.path.join(temp_test_dir, "test_analysis.db")
    db = AnalysisDB(db_path)
    yield db
    # Cleanup
    with contextlib.suppress(Exception):
        db.close()
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture(scope="function")
def isolated_metadata_db(temp_test_dir):
    """
    Provide isolated MetadataDB instance for testing.

    Uses temporary database file that is automatically cleaned up.
    Prevents test data from leaking into production database.
    """
    from db.metadata_db import MetadataDB

    db_path = os.path.join(temp_test_dir, "test_metadata.db")
    db = MetadataDB(db_path)
    yield db
    # Cleanup
    with contextlib.suppress(Exception):
        db.close()
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture(scope="function")
def mock_analysis_db():
    """Mock AnalysisDB for unit tests that don't need real database."""
    db = MagicMock()
    db.get_all_analyses.return_value = []
    db.get_analysis.return_value = None
    db.get_active_directories.return_value = []
    db.save_analysis.return_value = 1
    db.close.return_value = None
    return db


@pytest.fixture(scope="function")
def mock_metadata_db():
    """Mock MetadataDB for unit tests that don't need real database."""
    db = MagicMock()
    db.get_metadata.return_value = None
    db.save_metadata.return_value = None
    db.get_all_metadata.return_value = []
    db.close.return_value = None
    return db


# Global database path override to prevent production database access
@pytest.fixture(autouse=True, scope="function")
def prevent_production_db_access(tmp_path, monkeypatch):
    """
    Automatically redirect all database paths to temporary test directories.

    This prevents ANY test from accidentally accessing the production database.
    Tests that need real databases will use temporary isolated databases.
    """
    # Create temp database paths
    test_db_path = str(tmp_path / "test_analysis.db")

    # Patch the main database path function
    monkeypatch.setattr("db.connection.get_appdata_db_path", lambda *args, **kwargs: test_db_path)

    yield

    # Cleanup happens automatically via tmp_path fixture
