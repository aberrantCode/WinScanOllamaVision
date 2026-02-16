"""Tests for DirectoryRepository"""

import sqlite3
from unittest.mock import patch

import pytest

from db.connection import DatabaseConnection
from db.repositories.directory_repo import DirectoryRepository
from db.schema import create_all_tables


@pytest.fixture
def db_conn(tmp_path):
    """Create a temporary database connection for testing."""
    db_path = tmp_path / "test_directory.db"
    conn = DatabaseConnection(str(db_path))
    create_all_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def repo(db_conn):
    """Create a DirectoryRepository instance for testing."""
    return DirectoryRepository(db_conn)


class TestDirectoryRepositoryBasics:
    """Test basic repository initialization and setup."""

    def test_repository_initialization(self, repo, db_conn):
        """Test that repository initializes with correct connection."""
        assert repo.conn == db_conn
        assert repo.conn.connection is not None

    def test_repository_has_logger(self, repo):
        """Test that repository has logger initialized."""
        logger = repo._get_logger()
        assert logger is not None
        assert hasattr(logger, "info")


class TestAdd:
    """Test add() method for adding directories."""

    def test_add_creates_directory_record(self, repo):
        """Test adding a new source directory."""
        repo.add("/test/dir1", scan_on_startup=True)

        # Verify record was created
        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT * FROM source_directories WHERE directory_path = ?", ("/test/dir1",))
        record = cursor.fetchone()

        assert record is not None
        assert record[1] == "/test/dir1"  # directory_path
        assert record[2] == 1  # is_active
        assert record[3] == 1  # scan_on_startup (True = 1)

    def test_add_with_scan_on_startup_false(self, repo):
        """Test adding directory with scan_on_startup=False."""
        repo.add("/test/dir2", scan_on_startup=False)

        cursor = repo.conn.connection.cursor()
        cursor.execute(
            "SELECT scan_on_startup FROM source_directories WHERE directory_path = ?",
            ("/test/dir2",),
        )
        scan_on_startup = cursor.fetchone()[0]

        assert scan_on_startup == 0  # False = 0

    def test_add_replaces_existing_directory(self, repo):
        """Test INSERT OR REPLACE behavior for same directory path."""
        # Add first time
        repo.add("/test/dir", scan_on_startup=True)

        cursor = repo.conn.connection.cursor()
        cursor.execute(
            "SELECT scan_on_startup FROM source_directories WHERE directory_path = ?",
            ("/test/dir",),
        )
        assert cursor.fetchone()[0] == 1  # True

        # Add again with different scan_on_startup (should replace)
        repo.add("/test/dir", scan_on_startup=False)

        cursor.execute(
            "SELECT scan_on_startup FROM source_directories WHERE directory_path = ?",
            ("/test/dir",),
        )
        assert cursor.fetchone()[0] == 0  # False (updated)

        # Verify only one record exists
        cursor.execute(
            "SELECT COUNT(*) FROM source_directories WHERE directory_path = ?", ("/test/dir",)
        )
        count = cursor.fetchone()[0]
        assert count == 1

    def test_add_handles_operational_error(self, repo):
        """Test add handles OperationalError."""
        with patch.object(
            repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
        ), pytest.raises(sqlite3.OperationalError, match="Database is locked"):
            repo.add("/test/dir")

    def test_add_handles_generic_error(self, repo):
        """Test add handles generic sqlite3.Error."""
        with patch.object(repo.conn, "commit", side_effect=sqlite3.Error("Generic database error")):
            with pytest.raises(sqlite3.Error, match="Failed to add directory"):
                repo.add("/test/dir")


class TestGetActive:
    """Test get_active() method for retrieving directories."""

    def test_get_active_returns_active_directories(self, repo):
        """Test retrieving active directories."""
        # Add directories
        repo.add("/test/dir1")
        repo.add("/test/dir2")
        repo.add("/test/dir3")

        active_dirs = repo.get_active()

        assert len(active_dirs) == 3
        assert "/test/dir1" in active_dirs
        assert "/test/dir2" in active_dirs
        assert "/test/dir3" in active_dirs

    def test_get_active_returns_empty_when_no_directories(self, repo):
        """Test get_active returns empty list when no directories exist."""
        active_dirs = repo.get_active()
        assert active_dirs == []

    def test_get_active_excludes_inactive_directories(self, repo, db_conn):
        """Test that inactive directories are excluded."""
        # Add active directory
        repo.add("/test/active")

        # Manually create inactive directory
        cursor = db_conn.connection.cursor()
        cursor.execute(
            "INSERT INTO source_directories (directory_path, is_active, scan_on_startup) VALUES (?, 0, 0)",
            ("/test/inactive",),
        )
        db_conn.connection.commit()

        active_dirs = repo.get_active()

        assert len(active_dirs) == 1
        assert "/test/active" in active_dirs
        assert "/test/inactive" not in active_dirs


class TestRemove:
    """Test remove() method for deleting directories."""

    def test_remove_deletes_directory(self, repo):
        """Test removing a source directory."""
        # Add directory
        repo.add("/test/dir")

        # Verify it exists
        assert "/test/dir" in repo.get_active()

        # Remove it
        repo.remove("/test/dir")

        # Verify it's gone
        assert "/test/dir" not in repo.get_active()

        # Verify record was actually deleted
        cursor = repo.conn.connection.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM source_directories WHERE directory_path = ?", ("/test/dir",)
        )
        count = cursor.fetchone()[0]
        assert count == 0

    def test_remove_handles_nonexistent_directory(self, repo):
        """Test removing non-existent directory (should not error)."""
        # Should not raise error
        repo.remove("/test/nonexistent")

    def test_remove_handles_operational_error(self, repo):
        """Test remove handles OperationalError."""
        repo.add("/test/dir")

        with patch.object(
            repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
        ), pytest.raises(sqlite3.OperationalError, match="Database is locked"):
            repo.remove("/test/dir")

    def test_remove_handles_generic_error(self, repo):
        """Test remove handles generic sqlite3.Error."""
        repo.add("/test/dir")

        with patch.object(repo.conn, "commit", side_effect=sqlite3.Error("Generic database error")):
            with pytest.raises(sqlite3.Error, match="Failed to remove directory"):
                repo.remove("/test/dir")


class TestUpdateScanInfo:
    """Test update_scan_info() method for updating scan metadata."""

    def test_update_scan_info_updates_file_count(self, repo):
        """Test updating file count for a directory."""
        # Add directory
        repo.add("/test/dir")

        # Update scan info
        repo.update_scan_info("/test/dir", file_count=150)

        # Verify file count was updated
        cursor = repo.conn.connection.cursor()
        cursor.execute(
            "SELECT file_count, last_scanned_at FROM source_directories WHERE directory_path = ?",
            ("/test/dir",),
        )
        record = cursor.fetchone()

        assert record is not None
        assert record[0] == 150  # file_count
        assert record[1] is not None  # last_scanned_at should be set

    def test_update_scan_info_updates_timestamp(self, repo):
        """Test that update_scan_info updates last_scanned_at timestamp."""
        # Add directory
        repo.add("/test/dir")

        # Get initial timestamp (should be NULL)
        cursor = repo.conn.connection.cursor()
        cursor.execute(
            "SELECT last_scanned_at FROM source_directories WHERE directory_path = ?",
            ("/test/dir",),
        )
        initial_timestamp = cursor.fetchone()[0]
        assert initial_timestamp is None

        # Update scan info
        repo.update_scan_info("/test/dir", file_count=100)

        # Get new timestamp
        cursor.execute(
            "SELECT last_scanned_at FROM source_directories WHERE directory_path = ?",
            ("/test/dir",),
        )
        new_timestamp = cursor.fetchone()[0]

        # Timestamp should now be set
        assert new_timestamp is not None

    def test_update_scan_info_with_zero_files(self, repo):
        """Test updating with zero file count."""
        repo.add("/test/empty_dir")
        repo.update_scan_info("/test/empty_dir", file_count=0)

        cursor = repo.conn.connection.cursor()
        cursor.execute(
            "SELECT file_count FROM source_directories WHERE directory_path = ?",
            ("/test/empty_dir",),
        )
        file_count = cursor.fetchone()[0]

        assert file_count == 0

    def test_update_scan_info_on_nonexistent_directory(self, repo):
        """Test updating scan info on non-existent directory (should not error)."""
        # Should not raise error (UPDATE on non-existent row)
        repo.update_scan_info("/test/nonexistent", file_count=50)

    def test_update_scan_info_handles_operational_error(self, repo):
        """Test update_scan_info handles OperationalError."""
        repo.add("/test/dir")

        with patch.object(
            repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
        ), pytest.raises(sqlite3.OperationalError, match="Database is locked"):
            repo.update_scan_info("/test/dir", file_count=100)

    def test_update_scan_info_handles_generic_error(self, repo):
        """Test update_scan_info handles generic sqlite3.Error."""
        repo.add("/test/dir")

        with patch.object(repo.conn, "commit", side_effect=sqlite3.Error("Generic database error")):
            with pytest.raises(sqlite3.Error, match="Failed to update scan info"):
                repo.update_scan_info("/test/dir", file_count=100)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_add_with_very_long_path(self, repo):
        """Test adding directory with very long path."""
        long_path = "/test/" + "a" * 500
        repo.add(long_path)

        active_dirs = repo.get_active()
        assert long_path in active_dirs

    def test_add_with_special_characters_in_path(self, repo):
        """Test adding directory with special characters."""
        special_path = "/test/dir with spaces & symbols!@#"
        repo.add(special_path)

        active_dirs = repo.get_active()
        assert special_path in active_dirs

    def test_update_scan_info_with_large_file_count(self, repo):
        """Test updating with very large file count."""
        repo.add("/test/large_dir")
        repo.update_scan_info("/test/large_dir", file_count=1000000)

        cursor = repo.conn.connection.cursor()
        cursor.execute(
            "SELECT file_count FROM source_directories WHERE directory_path = ?",
            ("/test/large_dir",),
        )
        file_count = cursor.fetchone()[0]

        assert file_count == 1000000

    def test_multiple_updates_to_same_directory(self, repo):
        """Test multiple scan info updates to same directory."""
        repo.add("/test/dir")

        # Update multiple times
        repo.update_scan_info("/test/dir", file_count=50)
        repo.update_scan_info("/test/dir", file_count=75)
        repo.update_scan_info("/test/dir", file_count=100)

        # Final count should be latest update
        cursor = repo.conn.connection.cursor()
        cursor.execute(
            "SELECT file_count FROM source_directories WHERE directory_path = ?", ("/test/dir",)
        )
        file_count = cursor.fetchone()[0]

        assert file_count == 100


class TestIntegration:
    """Test integration scenarios combining multiple operations."""

    def test_add_update_remove_workflow(self, repo):
        """Test complete workflow: add, update, remove."""
        # Add directory
        repo.add("/test/workflow")
        assert "/test/workflow" in repo.get_active()

        # Update scan info
        repo.update_scan_info("/test/workflow", file_count=200)
        cursor = repo.conn.connection.cursor()
        cursor.execute(
            "SELECT file_count FROM source_directories WHERE directory_path = ?",
            ("/test/workflow",),
        )
        assert cursor.fetchone()[0] == 200

        # Remove directory
        repo.remove("/test/workflow")
        assert "/test/workflow" not in repo.get_active()

    def test_manage_multiple_directories(self, repo):
        """Test managing multiple directories simultaneously."""
        # Add multiple directories
        paths = ["/test/dir1", "/test/dir2", "/test/dir3", "/test/dir4"]
        for path in paths:
            repo.add(path)

        # Verify all are active
        active_dirs = repo.get_active()
        assert len(active_dirs) == 4
        for path in paths:
            assert path in active_dirs

        # Update some
        repo.update_scan_info("/test/dir1", file_count=10)
        repo.update_scan_info("/test/dir3", file_count=30)

        # Remove some
        repo.remove("/test/dir2")
        repo.remove("/test/dir4")

        # Verify correct state
        active_dirs = repo.get_active()
        assert len(active_dirs) == 2
        assert "/test/dir1" in active_dirs
        assert "/test/dir3" in active_dirs
