"""Tests for database schema creation and migrations."""

import os
import tempfile

import pytest

from db.connection import DatabaseConnection
from db.schema import create_all_tables, get_schema_version


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


@pytest.mark.skip(
    reason="Schema refactored: pdf_path moved to pdf_files table, file_paths replaced by bundle_images join table"
)
def test_pdf_path_column_exists(temp_db):
    """Test that pdf_path column exists in document_bundles table.

    NOTE: Schema has been refactored. PDF paths are now in pdf_files table with bundle_id FK.
    This is a more normalized design.
    """
    create_all_tables(temp_db)

    cursor = temp_db.connection.cursor()
    cursor.execute("PRAGMA table_info(document_bundles)")
    columns = {col[1]: col[2] for col in cursor.fetchall()}

    assert "pdf_path" in columns, "pdf_path column should exist"
    assert columns["pdf_path"] == "TEXT", "pdf_path should be TEXT type"


@pytest.mark.skip(reason="Schema refactored: pdf_path moved to pdf_files table")
def test_pdf_path_column_is_nullable(temp_db):
    """Test that pdf_path column is nullable.

    NOTE: Schema has been refactored. PDF paths are now in pdf_files table.
    """
    create_all_tables(temp_db)

    cursor = temp_db.connection.cursor()
    cursor.execute("PRAGMA table_info(document_bundles)")
    columns = {col[1]: col[3] for col in cursor.fetchall()}  # col[3] is notnull flag

    # notnull flag should be 0 (nullable)
    assert columns.get("pdf_path", 1) == 0, "pdf_path should be nullable"


@pytest.mark.skip(
    reason="Schema refactored: file_paths column removed, replaced by bundle_images join table"
)
def test_existing_records_have_null_pdf_path(temp_db):
    """Test that existing records have NULL for new pdf_path column.

    NOTE: Schema has been refactored. File paths are tracked via bundle_images join table.
    """
    create_all_tables(temp_db)

    cursor = temp_db.connection.cursor()

    # Insert a test bundle without pdf_path
    cursor.execute("""
        INSERT INTO document_bundles (bundle_name, file_paths, status)
        VALUES ('Test Bundle', '["file1.png", "file2.png"]', 'suggested')
    """)
    temp_db.commit()

    # Verify pdf_path is NULL
    cursor.execute("SELECT pdf_path FROM document_bundles WHERE bundle_name = 'Test Bundle'")
    result = cursor.fetchone()

    assert result is not None, "Bundle should exist"
    assert result[0] is None, "pdf_path should be NULL for existing records"


@pytest.mark.skip(reason="Migration 5 removed during schema refactoring")
def test_migration_version_5_applied(temp_db):
    """Test that migration version 5 is applied correctly.

    NOTE: Migration 5 was part of old schema. Current schema doesn't use that migration.
    """
    create_all_tables(temp_db)

    version = get_schema_version(temp_db)
    assert version >= 5, "Schema version should be at least 5 after migrations"

    cursor = temp_db.connection.cursor()
    cursor.execute("SELECT description FROM schema_version WHERE version = 5")
    result = cursor.fetchone()

    assert result is not None, "Migration 5 should exist"
    assert "pdf_path" in result[0].lower(), "Migration 5 should mention pdf_path"


@pytest.mark.skip(reason="Schema refactored: pdf_path in pdf_files table, file_paths removed")
def test_pdf_path_can_be_set_and_retrieved(temp_db):
    """Test that pdf_path can be set and retrieved correctly.

    NOTE: Schema refactored. Use pdf_files table for PDF paths, bundle_images for file associations.
    """
    create_all_tables(temp_db)

    cursor = temp_db.connection.cursor()

    # Insert bundle with pdf_path
    pdf_path = "C:/output/test_document.pdf"
    cursor.execute(
        """
        INSERT INTO document_bundles (bundle_name, file_paths, status, pdf_path)
        VALUES ('PDF Bundle', '["page1.png"]', 'completed', ?)
    """,
        (pdf_path,),
    )
    temp_db.commit()

    # Retrieve and verify
    cursor.execute("SELECT pdf_path FROM document_bundles WHERE bundle_name = 'PDF Bundle'")
    result = cursor.fetchone()

    assert result is not None, "Bundle should exist"
    assert result[0] == pdf_path, "pdf_path should match inserted value"


def test_bundles_index_on_status_exists(temp_db):
    """Test that index on status column exists."""
    create_all_tables(temp_db)

    cursor = temp_db.connection.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_bundles_status'"
    )
    result = cursor.fetchone()

    assert result is not None, "idx_bundles_status index should exist"
