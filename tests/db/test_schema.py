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


def test_pdf_path_column_exists(temp_db):
    """Test that pdf_path column exists in document_bundles table."""
    create_all_tables(temp_db)

    cursor = temp_db.connection.cursor()
    cursor.execute("PRAGMA table_info(document_bundles)")
    columns = {col[1]: col[2] for col in cursor.fetchall()}

    assert "pdf_path" in columns, "pdf_path column should exist"
    assert columns["pdf_path"] == "TEXT", "pdf_path should be TEXT type"


def test_pdf_path_column_is_nullable(temp_db):
    """Test that pdf_path column is nullable."""
    create_all_tables(temp_db)

    cursor = temp_db.connection.cursor()
    cursor.execute("PRAGMA table_info(document_bundles)")
    columns = {col[1]: col[3] for col in cursor.fetchall()}  # col[3] is notnull flag

    # notnull flag should be 0 (nullable)
    assert columns.get("pdf_path", 1) == 0, "pdf_path should be nullable"


def test_existing_records_have_null_pdf_path(temp_db):
    """Test that existing records have NULL for new pdf_path column."""
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


def test_migration_version_5_applied(temp_db):
    """Test that migration version 5 is applied correctly."""
    create_all_tables(temp_db)

    version = get_schema_version(temp_db)
    assert version >= 5, "Schema version should be at least 5 after migrations"

    cursor = temp_db.connection.cursor()
    cursor.execute("SELECT description FROM schema_version WHERE version = 5")
    result = cursor.fetchone()

    assert result is not None, "Migration 5 should exist"
    assert "pdf_path" in result[0].lower(), "Migration 5 should mention pdf_path"


def test_pdf_path_can_be_set_and_retrieved(temp_db):
    """Test that pdf_path can be set and retrieved correctly."""
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


def test_image_files_table_exists(temp_db):
    """Test that image_files table is created."""
    create_all_tables(temp_db)

    cursor = temp_db.connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='image_files'")
    result = cursor.fetchone()

    assert result is not None, "image_files table should exist"


def test_image_files_columns(temp_db):
    """Test that image_files table has all required columns."""
    create_all_tables(temp_db)

    cursor = temp_db.connection.cursor()
    cursor.execute("PRAGMA table_info(image_files)")
    columns = {col[1]: col[2] for col in cursor.fetchall()}

    expected_columns = {
        "id": "INTEGER",
        "file_path": "TEXT",
        "file_hash": "TEXT",
        "directory_path": "TEXT",
        "filename": "TEXT",
        "file_size": "INTEGER",
        "file_mtime": "REAL",
        "status": "TEXT",
        "discovered_at": "TIMESTAMP",
        "last_seen_at": "TIMESTAMP",
        "deleted_at": "TIMESTAMP",
        "analysis_id": "INTEGER",
        "output_filename": "TEXT",
    }

    for col_name, col_type in expected_columns.items():
        assert col_name in columns, f"Column {col_name} should exist"
        assert columns[col_name] == col_type, f"Column {col_name} should be {col_type}"


def test_image_files_indices(temp_db):
    """Test that all image_files indices are created."""
    create_all_tables(temp_db)

    cursor = temp_db.connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='image_files'")
    indices = {row[0] for row in cursor.fetchall()}

    expected_indices = {
        "idx_image_files_path",
        "idx_image_files_status",
        "idx_image_files_directory",
        "idx_image_files_hash",
    }

    for idx in expected_indices:
        assert idx in indices, f"Index {idx} should exist"


def test_pdf_files_table_exists(temp_db):
    """Test that pdf_files table is created."""
    create_all_tables(temp_db)

    cursor = temp_db.connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pdf_files'")
    result = cursor.fetchone()

    assert result is not None, "pdf_files table should exist"


def test_pdf_files_columns(temp_db):
    """Test that pdf_files table has all required columns."""
    create_all_tables(temp_db)

    cursor = temp_db.connection.cursor()
    cursor.execute("PRAGMA table_info(pdf_files)")
    columns = {col[1]: col[2] for col in cursor.fetchall()}

    expected_columns = {
        "id": "INTEGER",
        "pdf_path": "TEXT",
        "pdf_filename": "TEXT",
        "file_hash": "TEXT",
        "file_size": "INTEGER",
        "page_count": "INTEGER",
        "bundle_id": "INTEGER",
        "generation_status": "TEXT",
        "source_image_ids": "TEXT",
        "generated_at": "TIMESTAMP",
    }

    for col_name, col_type in expected_columns.items():
        assert col_name in columns, f"Column {col_name} should exist"
        assert columns[col_name] == col_type, f"Column {col_name} should be {col_type}"


def test_pdf_files_indices(temp_db):
    """Test that all pdf_files indices are created."""
    create_all_tables(temp_db)

    cursor = temp_db.connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='pdf_files'")
    indices = {row[0] for row in cursor.fetchall()}

    expected_indices = {
        "idx_pdf_files_path",
        "idx_pdf_files_bundle",
    }

    for idx in expected_indices:
        assert idx in indices, f"Index {idx} should exist"


def test_migration_version_6_applied(temp_db):
    """Test that migration version 6 is applied correctly."""
    create_all_tables(temp_db)

    version = get_schema_version(temp_db)
    assert version >= 6, "Schema version should be at least 6 after migrations"

    cursor = temp_db.connection.cursor()
    cursor.execute("SELECT description FROM schema_version WHERE version = 6")
    result = cursor.fetchone()

    assert result is not None, "Migration 6 should exist"
    assert "image_files" in result[0].lower(), "Migration 6 should mention image_files"


def test_migration_version_7_applied(temp_db):
    """Test that migration version 7 is applied correctly."""
    create_all_tables(temp_db)

    version = get_schema_version(temp_db)
    assert version >= 7, "Schema version should be at least 7 after migrations"

    cursor = temp_db.connection.cursor()
    cursor.execute("SELECT description FROM schema_version WHERE version = 7")
    result = cursor.fetchone()

    assert result is not None, "Migration 7 should exist"
    assert "pdf_files" in result[0].lower(), "Migration 7 should mention pdf_files"


def test_migration_version_8_applied(temp_db):
    """Test that migration version 8 is applied correctly."""
    create_all_tables(temp_db)

    version = get_schema_version(temp_db)
    assert version >= 8, "Schema version should be at least 8 after migrations"

    cursor = temp_db.connection.cursor()
    cursor.execute("SELECT description FROM schema_version WHERE version = 8")
    result = cursor.fetchone()

    assert result is not None, "Migration 8 should exist"
    assert (
        "back-fill" in result[0].lower() or "backfill" in result[0].lower()
    ), "Migration 8 should mention back-fill"


def test_backfill_populates_image_files(temp_db):
    """Test that back-fill migration populates image_files from analysis_results."""
    from db.schema import _create_analysis_tables, _create_indices, _create_metadata_tables

    # Create tables without running migrations
    _create_metadata_tables(temp_db)
    _create_analysis_tables(temp_db)
    _create_indices(temp_db)

    cursor = temp_db.connection.cursor()

    # Insert initial schema version
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (1, 'Initial schema')
    """)
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (2, 'Migration 2')
    """)
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (3, 'Migration 3')
    """)
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (4, 'Migration 4')
    """)
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (5, 'Migration 5')
    """)
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (6, 'Migration 6')
    """)
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (7, 'Migration 7')
    """)
    temp_db.commit()

    # Insert test analysis results BEFORE migration 8 runs
    test_data = [
        ("/path/to/file1.png", "hash1", "provider1", "model1"),
        ("/path/to/file2.png", "hash2", "provider2", "model2"),
        ("C:\\Windows\\path\\file3.png", "hash3", "provider3", "model3"),
    ]

    for file_path, file_hash, provider, model in test_data:
        cursor.execute(
            """
            INSERT INTO analysis_results (file_path, file_hash, provider_name, model_name)
            VALUES (?, ?, ?, ?)
        """,
            (file_path, file_hash, provider, model),
        )
    temp_db.commit()

    # Now run migrations (which will execute migration 8)
    create_all_tables(temp_db)

    # Verify image_files are populated
    cursor.execute("SELECT COUNT(*) FROM image_files")
    count = cursor.fetchone()[0]
    assert count == len(test_data), f"Should have {len(test_data)} image_files entries"

    # Verify status is 'analyzed'
    cursor.execute("SELECT status FROM image_files")
    statuses = [row[0] for row in cursor.fetchall()]
    assert all(
        s == "analyzed" for s in statuses
    ), "All back-filled images should have status='analyzed'"

    # Verify analysis_id references are correct
    cursor.execute("""
        SELECT if1.file_path, if1.analysis_id, ar.id
        FROM image_files if1
        JOIN analysis_results ar ON if1.file_path = ar.file_path
    """)
    for row in cursor.fetchall():
        assert row[1] == row[2], "analysis_id should match analysis_results.id"


def test_image_files_unique_constraint(temp_db):
    """Test that file_path has UNIQUE constraint."""
    create_all_tables(temp_db)

    cursor = temp_db.connection.cursor()

    # Insert first record
    cursor.execute(
        """
        INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        ("/test/file.png", "hash1", "/test", "file.png", 1024, 1234567890.0),
    )
    temp_db.commit()

    # Attempt to insert duplicate
    with pytest.raises(Exception) as exc_info:
        cursor.execute(
            """
            INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            ("/test/file.png", "hash2", "/test", "file.png", 2048, 1234567891.0),
        )
        temp_db.commit()

    assert "UNIQUE constraint failed" in str(exc_info.value), "Should raise UNIQUE constraint error"


def test_pdf_files_unique_constraint(temp_db):
    """Test that pdf_path has UNIQUE constraint."""
    create_all_tables(temp_db)

    cursor = temp_db.connection.cursor()

    # Insert first record
    cursor.execute(
        """
        INSERT INTO pdf_files (pdf_path, pdf_filename, source_image_ids)
        VALUES (?, ?, ?)
    """,
        ("/output/doc.pdf", "doc.pdf", "[1, 2, 3]"),
    )
    temp_db.commit()

    # Attempt to insert duplicate
    with pytest.raises(Exception) as exc_info:
        cursor.execute(
            """
            INSERT INTO pdf_files (pdf_path, pdf_filename, source_image_ids)
            VALUES (?, ?, ?)
        """,
            ("/output/doc.pdf", "doc.pdf", "[4, 5, 6]"),
        )
        temp_db.commit()

    assert "UNIQUE constraint failed" in str(exc_info.value), "Should raise UNIQUE constraint error"


def test_migrations_are_idempotent(temp_db):
    """Test that running migrations multiple times is safe."""
    # Run migrations first time
    create_all_tables(temp_db)
    version1 = get_schema_version(temp_db)

    # Run migrations again
    create_all_tables(temp_db)
    version2 = get_schema_version(temp_db)

    assert version1 == version2, "Running migrations multiple times should not change version"

    # Verify tables still exist
    cursor = temp_db.connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}

    assert "image_files" in tables, "image_files table should still exist"
    assert "pdf_files" in tables, "pdf_files table should still exist"
