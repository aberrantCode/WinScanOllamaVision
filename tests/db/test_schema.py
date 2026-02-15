"""Tests for database schema creation and migrations.

NOTE: Tests for old document_bundles schema (pdf_path column, file_paths column) were removed.
The schema was refactored to use a normalized design:
- pdf_files table stores PDF paths with bundle_id FK
- bundle_images join table links bundles to image files
- Migration 5 was removed during refactoring

See git history for removed tests if needed for reference.
"""

import os
import tempfile

import pytest

from db.connection import DatabaseConnection
from db.schema import create_all_tables


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = DatabaseConnection(path)
    yield conn

    # Cleanup
    conn.close()
    if os.path.exists(path):
        os.unlink(path)


def test_bundles_index_on_status_exists(temp_db):
    """Test that index on status column exists."""
    create_all_tables(temp_db)

    cursor = temp_db.connection.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_bundles_status'"
    )
    result = cursor.fetchone()

    assert result is not None, "idx_bundles_status index should exist"
