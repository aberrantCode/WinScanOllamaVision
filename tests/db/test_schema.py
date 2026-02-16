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
from unittest.mock import MagicMock

import pytest

from db.connection import DatabaseConnection
from db.schema import (
    _create_core_tables,
    _create_indices,
    _create_junction_tables,
    _run_migrations,
    clear_schema_cache,
    create_all_tables,
    get_schema_version,
)


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


def test_create_core_tables_raises_error_when_connection_none():
    """Test _create_core_tables raises RuntimeError when connection is None (line 102)."""
    # Arrange - create a mock connection with None
    mock_conn = MagicMock()
    mock_conn.connection = None

    # Act & Assert
    with pytest.raises(RuntimeError, match="Database connection not initialized"):
        _create_core_tables(mock_conn)


def test_create_junction_tables_raises_error_when_connection_none():
    """Test _create_junction_tables raises RuntimeError when connection is None (line 374)."""
    # Arrange
    mock_conn = MagicMock()
    mock_conn.connection = None

    # Act & Assert
    with pytest.raises(RuntimeError, match="Database connection not initialized"):
        _create_junction_tables(mock_conn)


def test_create_indices_raises_error_when_connection_none():
    """Test _create_indices raises RuntimeError when connection is None (line 416)."""
    # Arrange
    mock_conn = MagicMock()
    mock_conn.connection = None

    # Act & Assert
    with pytest.raises(RuntimeError, match="Database connection not initialized"):
        _create_indices(mock_conn)


def test_run_migrations_raises_error_when_connection_none():
    """Test _run_migrations raises RuntimeError when connection is None (line 591)."""
    # Arrange
    mock_conn = MagicMock()
    mock_conn.connection = None

    # Act & Assert
    with pytest.raises(RuntimeError, match="Database connection not initialized"):
        _run_migrations(mock_conn)


def test_get_schema_version_raises_error_when_connection_none():
    """Test get_schema_version raises RuntimeError when connection is None (line 655)."""
    # Arrange
    mock_conn = MagicMock()
    mock_conn.connection = None

    # Act & Assert
    with pytest.raises(RuntimeError, match="Database connection not initialized"):
        get_schema_version(mock_conn)


def test_old_analysis_results_schema_detection_and_drop(temp_db, caplog):
    """Test old analysis_results schema detection and drop (lines 156-162)."""
    import logging

    # Arrange - create table with old schema (missing image_file_id column)
    cursor = temp_db.connection.cursor()
    cursor.execute(
        """
        CREATE TABLE analysis_results (
            id INTEGER PRIMARY KEY,
            file_path TEXT,
            analysis_text TEXT
        )
    """
    )
    temp_db.commit()

    # Act - create_all_tables should detect old schema and drop it
    with caplog.at_level(logging.WARNING):
        _create_core_tables(temp_db)

    # Assert - warning should be logged
    assert any(
        "Dropping analysis_results table with old schema" in record.message
        for record in caplog.records
    )

    # Verify new schema was created
    columns_info = cursor.execute("PRAGMA table_info(analysis_results)").fetchall()
    column_names = [col[1] for col in columns_info]
    assert "image_file_id" in column_names


def test_old_document_bundles_schema_detection_and_drop(temp_db, caplog):
    """Test old document_bundles schema detection and drop (lines 248-251)."""
    import logging

    # Arrange - create table with old schema (has file_paths column)
    cursor = temp_db.connection.cursor()
    cursor.execute(
        """
        CREATE TABLE document_bundles (
            id INTEGER PRIMARY KEY,
            file_paths TEXT,
            status TEXT
        )
    """
    )
    temp_db.commit()

    # Act - create_all_tables should detect old schema and drop it
    with caplog.at_level(logging.WARNING):
        _create_core_tables(temp_db)

    # Assert - warning should be logged
    assert any(
        "Dropping document_bundles table with old schema" in record.message
        for record in caplog.records
    )

    # Verify new schema was created (without file_paths column)
    columns_info = cursor.execute("PRAGMA table_info(document_bundles)").fetchall()
    column_names = [col[1] for col in columns_info]
    assert "file_paths" not in column_names


def test_migration_16_adds_is_blank_column(temp_db):
    """Test Migration 16 adds is_blank column to metadata table (lines 623-630)."""
    # Arrange - create schema without is_blank column
    cursor = temp_db.connection.cursor()

    # Create schema_version table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        )
    """
    )

    # Create metadata table without is_blank
    cursor.execute(
        """
        CREATE TABLE metadata (
            id INTEGER PRIMARY KEY,
            image_file_id INTEGER NOT NULL UNIQUE,
            company TEXT
        )
    """
    )

    # Set schema version to 1 (before migration 16)
    cursor.execute("INSERT INTO schema_version (version, description) VALUES (1, 'Initial schema')")
    temp_db.commit()

    # Verify is_blank column does NOT exist before migration
    columns_before = cursor.execute("PRAGMA table_info(metadata)").fetchall()
    column_names_before = [col[1] for col in columns_before]
    assert "is_blank" not in column_names_before

    # Act - run migrations
    _run_migrations(temp_db)

    # Assert - is_blank column should be added (line 627)
    columns_after = cursor.execute("PRAGMA table_info(metadata)").fetchall()
    column_names_after = [col[1] for col in columns_after]
    assert "is_blank" in column_names_after

    # Verify migration record was created
    version_record = cursor.execute(
        "SELECT description FROM schema_version WHERE version = 16"
    ).fetchone()
    assert version_record is not None
    assert "is_blank" in version_record[0]


def test_migration_16_skips_if_column_exists(temp_db):
    """Test Migration 16 skips ALTER if is_blank already exists."""
    # Arrange - create schema with is_blank column already present
    cursor = temp_db.connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE metadata (
            id INTEGER PRIMARY KEY,
            image_file_id INTEGER NOT NULL UNIQUE,
            is_blank BOOLEAN DEFAULT 0
        )
    """
    )

    cursor.execute("INSERT INTO schema_version (version, description) VALUES (1, 'Initial')")
    temp_db.commit()

    # Act - run migrations (should not fail even though column exists)
    _run_migrations(temp_db)

    # Assert - column should still exist
    columns_info = cursor.execute("PRAGMA table_info(metadata)").fetchall()
    column_names = [col[1] for col in columns_info]
    assert "is_blank" in column_names


def test_clear_schema_cache_clears_specific_db_path(temp_db):
    """Test clear_schema_cache clears cache for specific db_path (lines 673-675)."""
    # Arrange - create schema and populate cache
    create_all_tables(temp_db)

    # Simulate cache entry
    from db.schema import _schema_initialized

    test_db_path = temp_db.db_path
    _schema_initialized[test_db_path] = 1

    # Act
    clear_schema_cache(test_db_path)

    # Assert - cache should be cleared for this path
    assert test_db_path not in _schema_initialized


def test_clear_schema_cache_clears_all_when_none(temp_db):
    """Test clear_schema_cache clears all cache entries when db_path is None (lines 677-678)."""
    # Arrange - populate cache with multiple entries
    from db.schema import _schema_initialized

    _schema_initialized["/db1.db"] = 1
    _schema_initialized["/db2.db"] = 2
    _schema_initialized["/db3.db"] = 3

    # Act
    clear_schema_cache(db_path=None)

    # Assert - all cache entries should be cleared
    assert len(_schema_initialized) == 0
