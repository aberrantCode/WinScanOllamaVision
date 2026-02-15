"""Comprehensive tests for ImageFilesRepository.

Tests image file registration, lifecycle tracking, status management,
and complex query operations.
"""

import os
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

from db.connection import DatabaseConnection
from db.repositories.image_files_repo import ImageFilesRepository
from db.schema import create_all_tables


class TestImageFilesRepositoryBasics:
    """Tests for repository initialization and basic operations."""

    @pytest.fixture
    def temp_db_path(self):
        """Create temp database file."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.remove(db_path)

    @pytest.fixture
    def conn(self, temp_db_path):
        """Create database connection with schema."""
        connection = DatabaseConnection(temp_db_path)
        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        """Create repository instance."""
        return ImageFilesRepository(conn)

    def test_init_stores_connection(self, repo, conn):
        """Test that __init__ stores database connection."""
        assert repo.conn is conn

    def test_get_logger_returns_logger(self, repo):
        """Test _get_logger returns logger instance."""
        logger = repo._get_logger()
        assert logger is not None


class TestImageFileRegistration:
    """Tests for image file registration."""

    @pytest.fixture
    def temp_db_path(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.remove(db_path)

    @pytest.fixture
    def conn(self, temp_db_path):
        connection = DatabaseConnection(temp_db_path)
        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return ImageFilesRepository(conn)

    def test_register_creates_record(self, repo):
        """Test register creates new image file record."""
        image_id = repo.register(
            file_path="/test/image.jpg",
            file_hash="abc123",
            directory_path="/test",
            filename="image.jpg",
            file_size=1024,
            file_mtime=12345.0,
        )

        assert image_id > 0

        # Verify record was created
        record = repo.get_by_path("/test/image.jpg")
        assert record is not None
        assert record["file_path"] == "/test/image.jpg"
        assert record["file_hash"] == "abc123"
        assert record["directory_path"] == "/test"
        assert record["filename"] == "image.jpg"
        assert record["file_size"] == 1024
        assert record["status"] == "registered"

    def test_register_replaces_existing_record(self, repo):
        """Test register replaces existing record (UPSERT behavior)."""
        # Register first time
        first_id = repo.register(
            file_path="/test/image.jpg",
            file_hash="abc123",
            directory_path="/test",
            filename="image.jpg",
            file_size=1024,
            file_mtime=12345.0,
        )

        # Register again with different hash
        second_id = repo.register(
            file_path="/test/image.jpg",
            file_hash="xyz789",
            directory_path="/test",
            filename="image.jpg",
            file_size=2048,
            file_mtime=54321.0,
        )

        # INSERT OR REPLACE creates new row with new ID (SQLite behavior)
        assert second_id > 0
        assert second_id != first_id

        # Verify record was updated
        record = repo.get_by_path("/test/image.jpg")
        assert record["file_hash"] == "xyz789"
        assert record["file_size"] == 2048

    def test_register_handles_operational_error(self, repo):
        """Test register handles database lock error."""
        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.OperationalError("locked")),
            pytest.raises(sqlite3.OperationalError, match="Database is locked"),
        ):
            repo.register(
                file_path="/test/image.jpg",
                file_hash="abc123",
                directory_path="/test",
                filename="image.jpg",
                file_size=1024,
                file_mtime=12345.0,
            )

    def test_register_handles_database_error(self, repo):
        """Test register handles general database error."""
        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.Error("constraint violation")),
            pytest.raises(sqlite3.Error, match="Failed to register image file"),
        ):
            repo.register(
                file_path="/test/image.jpg",
                file_hash="abc123",
                directory_path="/test",
                filename="image.jpg",
                file_size=1024,
                file_mtime=12345.0,
            )


class TestImageFileRetrieval:
    """Tests for image file retrieval methods."""

    @pytest.fixture
    def temp_db_path(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.remove(db_path)

    @pytest.fixture
    def conn(self, temp_db_path):
        connection = DatabaseConnection(temp_db_path)
        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return ImageFilesRepository(conn)

    def test_get_by_path_returns_record(self, repo):
        """Test get_by_path returns existing record."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        record = repo.get_by_path("/test/image.jpg")

        assert record is not None
        assert record["file_path"] == "/test/image.jpg"

    def test_get_by_path_returns_none_for_missing(self, repo):
        """Test get_by_path returns None for missing record."""
        record = repo.get_by_path("/nonexistent/image.jpg")
        assert record is None

    def test_get_by_directory_returns_images(self, repo):
        """Test get_by_directory returns all images in directory."""
        repo.register("/test/image1.jpg", "abc123", "/test", "image1.jpg", 1024, 12345.0)
        repo.register("/test/image2.jpg", "def456", "/test", "image2.jpg", 2048, 12346.0)
        repo.register("/other/image3.jpg", "ghi789", "/other", "image3.jpg", 3072, 12347.0)

        images = repo.get_by_directory("/test")

        assert len(images) == 2
        assert all(img["directory_path"] == "/test" for img in images)
        # Should be ordered by filename
        assert images[0]["filename"] == "image1.jpg"
        assert images[1]["filename"] == "image2.jpg"

    def test_get_by_status_returns_filtered_images(self, repo):
        """Test get_by_status returns images with specified status."""
        repo.register("/test/image1.jpg", "abc123", "/test", "image1.jpg", 1024, 12345.0)
        repo.register("/test/image2.jpg", "def456", "/test", "image2.jpg", 2048, 12346.0)

        # Update one to 'analyzed'
        repo.update_status("/test/image2.jpg", "analyzed")

        registered = repo.get_by_status("registered")
        analyzed = repo.get_by_status("analyzed")

        assert len(registered) == 1
        assert registered[0]["file_path"] == "/test/image1.jpg"

        assert len(analyzed) == 1
        assert analyzed[0]["file_path"] == "/test/image2.jpg"

    def test_get_all_excludes_deleted(self, repo):
        """Test get_all excludes deleted images."""
        repo.register("/test/image1.jpg", "abc123", "/test", "image1.jpg", 1024, 12345.0)
        repo.register("/test/image2.jpg", "def456", "/test", "image2.jpg", 2048, 12346.0)

        # Mark one as deleted
        repo.mark_deleted("/test/image2.jpg")

        all_images = repo.get_all()

        assert len(all_images) == 1
        assert all_images[0]["file_path"] == "/test/image1.jpg"


class TestImageFileStatusUpdates:
    """Tests for status and lifecycle updates."""

    @pytest.fixture
    def temp_db_path(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.remove(db_path)

    @pytest.fixture
    def conn(self, temp_db_path):
        connection = DatabaseConnection(temp_db_path)
        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return ImageFilesRepository(conn)

    def test_update_status_changes_status(self, repo):
        """Test update_status changes image status."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        repo.update_status("/test/image.jpg", "analyzing")

        record = repo.get_by_path("/test/image.jpg")
        assert record["status"] == "analyzing"

    def test_update_status_handles_operational_error(self, repo):
        """Test update_status handles database lock error."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.OperationalError("locked")),
            pytest.raises(sqlite3.OperationalError, match="Database is locked"),
        ):
            repo.update_status("/test/image.jpg", "analyzing")

    def test_update_status_handles_database_error(self, repo):
        """Test update_status handles general database error."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.Error("constraint violation")),
            pytest.raises(sqlite3.Error, match="Failed to update image status"),
        ):
            repo.update_status("/test/image.jpg", "analyzing")

    def test_update_last_seen_updates_timestamp(self, repo):
        """Test update_last_seen updates last_seen_at timestamp."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        # Update last seen
        repo.update_last_seen("/test/image.jpg")

        # Verify timestamp is set
        updated = repo.get_by_path("/test/image.jpg")
        # Due to CURRENT_TIMESTAMP, timestamp should be present
        assert updated["last_seen_at"] is not None

    def test_update_last_seen_handles_operational_error(self, repo):
        """Test update_last_seen handles database lock error."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.OperationalError("locked")),
            pytest.raises(sqlite3.OperationalError, match="Database is locked"),
        ):
            repo.update_last_seen("/test/image.jpg")

    def test_update_last_seen_handles_database_error(self, repo):
        """Test update_last_seen handles general database error."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.Error("constraint violation")),
            pytest.raises(sqlite3.Error, match="Failed to update last seen timestamp"),
        ):
            repo.update_last_seen("/test/image.jpg")

    def test_update_hash_changes_file_hash(self, repo):
        """Test update_hash changes file hash."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        repo.update_hash("/test/image.jpg", "newhas789")

        record = repo.get_by_path("/test/image.jpg")
        assert record["file_hash"] == "newhas789"

    def test_update_hash_handles_operational_error(self, repo):
        """Test update_hash handles database lock error."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.OperationalError("locked")),
            pytest.raises(sqlite3.OperationalError, match="Database is locked"),
        ):
            repo.update_hash("/test/image.jpg", "newhash789")

    def test_update_hash_handles_database_error(self, repo):
        """Test update_hash handles general database error."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.Error("constraint violation")),
            pytest.raises(sqlite3.Error, match="Failed to update file hash"),
        ):
            repo.update_hash("/test/image.jpg", "newhash789")

    def test_mark_deleted_sets_status_and_timestamp(self, repo):
        """Test mark_deleted sets status to deleted and sets deleted_at."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        repo.mark_deleted("/test/image.jpg")

        record = repo.get_by_path("/test/image.jpg")
        assert record["status"] == "deleted"
        assert record["deleted_at"] is not None

    def test_mark_deleted_handles_operational_error(self, repo):
        """Test mark_deleted handles database lock error."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.OperationalError("locked")),
            pytest.raises(sqlite3.OperationalError, match="Database is locked"),
        ):
            repo.mark_deleted("/test/image.jpg")

    def test_mark_deleted_handles_database_error(self, repo):
        """Test mark_deleted handles general database error."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.Error("constraint violation")),
            pytest.raises(sqlite3.Error, match="Failed to mark image as deleted"),
        ):
            repo.mark_deleted("/test/image.jpg")

    def test_mark_deleted_batch_deletes_multiple(self, repo):
        """Test mark_deleted_batch deletes multiple images."""
        repo.register("/test/image1.jpg", "abc123", "/test", "image1.jpg", 1024, 12345.0)
        repo.register("/test/image2.jpg", "def456", "/test", "image2.jpg", 2048, 12346.0)
        repo.register("/test/image3.jpg", "ghi789", "/test", "image3.jpg", 3072, 12347.0)

        count = repo.mark_deleted_batch(["/test/image1.jpg", "/test/image3.jpg"])

        assert count == 2

        # Verify both were deleted
        img1 = repo.get_by_path("/test/image1.jpg")
        img2 = repo.get_by_path("/test/image2.jpg")
        img3 = repo.get_by_path("/test/image3.jpg")

        assert img1["status"] == "deleted"
        assert img2["status"] == "registered"
        assert img3["status"] == "deleted"

    def test_mark_deleted_batch_returns_zero_for_empty_list(self, repo):
        """Test mark_deleted_batch returns 0 for empty list."""
        count = repo.mark_deleted_batch([])
        assert count == 0

    def test_mark_deleted_batch_handles_operational_error(self, repo):
        """Test mark_deleted_batch handles database lock error."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.OperationalError("locked")),
            pytest.raises(sqlite3.OperationalError, match="Database is locked"),
        ):
            repo.mark_deleted_batch(["/test/image.jpg"])

    def test_mark_deleted_batch_handles_database_error(self, repo):
        """Test mark_deleted_batch handles general database error."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.Error("constraint violation")),
            pytest.raises(sqlite3.Error, match="Failed to mark images as deleted"),
        ):
            repo.mark_deleted_batch(["/test/image.jpg"])


class TestImageFileMetadata:
    """Tests for metadata-related operations."""

    @pytest.fixture
    def temp_db_path(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.remove(db_path)

    @pytest.fixture
    def conn(self, temp_db_path):
        connection = DatabaseConnection(temp_db_path)
        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return ImageFilesRepository(conn)

    def test_update_rotation_creates_metadata_record(self, repo):
        """Test update_rotation creates metadata record if doesn't exist."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        repo.update_rotation("/test/image.jpg", 90)

        rotation = repo.get_rotation("/test/image.jpg")
        assert rotation == 90

    def test_update_rotation_updates_existing_metadata(self, repo):
        """Test update_rotation updates existing metadata record."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        repo.update_rotation("/test/image.jpg", 90)
        repo.update_rotation("/test/image.jpg", 180)

        rotation = repo.get_rotation("/test/image.jpg")
        assert rotation == 180

    def test_update_rotation_handles_missing_image(self, repo):
        """Test update_rotation handles missing image gracefully."""
        # Should not raise exception
        repo.update_rotation("/nonexistent/image.jpg", 90)

    def test_update_rotation_handles_operational_error(self, repo):
        """Test update_rotation handles database lock error."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.OperationalError("locked")),
            pytest.raises(sqlite3.OperationalError, match="Database is locked"),
        ):
            repo.update_rotation("/test/image.jpg", 90)

    def test_update_rotation_handles_database_error(self, repo):
        """Test update_rotation handles general database error."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.Error("constraint violation")),
            pytest.raises(sqlite3.Error, match="Failed to update rotation"),
        ):
            repo.update_rotation("/test/image.jpg", 90)

    def test_get_rotation_returns_zero_for_missing_image(self, repo):
        """Test get_rotation returns 0 for missing image."""
        rotation = repo.get_rotation("/nonexistent/image.jpg")
        assert rotation == 0

    def test_get_rotation_returns_zero_for_no_metadata(self, repo):
        """Test get_rotation returns 0 when metadata doesn't exist."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        rotation = repo.get_rotation("/test/image.jpg")
        assert rotation == 0

    def test_set_output_filename_updates_metadata(self, repo):
        """Test set_output_filename updates metadata table."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)

        # First create metadata record with rotation
        repo.update_rotation("/test/image.jpg", 0)

        # Then set output filename
        repo.set_output_filename("/test/image.jpg", "output.pdf")

        # Verify via direct query
        image_file = repo.get_by_path("/test/image.jpg")
        result = repo.conn.fetch_one_dict(
            "SELECT output_filename FROM metadata WHERE image_file_id = ?",
            (image_file["id"],),
        )
        assert result is not None
        assert result["output_filename"] == "output.pdf"

    def test_set_output_filename_handles_missing_image(self, repo):
        """Test set_output_filename handles missing image gracefully."""
        # Should not raise exception
        repo.set_output_filename("/nonexistent/image.jpg", "output.pdf")

    def test_set_output_filename_handles_operational_error(self, repo):
        """Test set_output_filename handles database lock error."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)
        repo.update_rotation("/test/image.jpg", 0)  # Create metadata record

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.OperationalError("locked")),
            pytest.raises(sqlite3.OperationalError, match="Database is locked"),
        ):
            repo.set_output_filename("/test/image.jpg", "output.pdf")

    def test_set_output_filename_handles_database_error(self, repo):
        """Test set_output_filename handles general database error."""
        repo.register("/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0)
        repo.update_rotation("/test/image.jpg", 0)  # Create metadata record

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.Error("constraint violation")),
            pytest.raises(sqlite3.Error, match="Failed to set output filename"),
        ):
            repo.set_output_filename("/test/image.jpg", "output.pdf")


class TestImageFileComplexQueries:
    """Tests for complex query operations."""

    @pytest.fixture
    def temp_db_path(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.remove(db_path)

    @pytest.fixture
    def conn(self, temp_db_path):
        connection = DatabaseConnection(temp_db_path)
        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return ImageFilesRepository(conn)

    def test_get_all_with_analysis_returns_images(self, repo):
        """Test get_all_with_analysis returns images with metadata."""
        repo.register("/test/image1.jpg", "abc123", "/test", "image1.jpg", 1024, 12345.0)
        repo.register("/test/image2.jpg", "def456", "/test", "image2.jpg", 2048, 12346.0)

        results = repo.get_all_with_analysis()

        assert len(results) == 2
        assert results[0]["file_path"] in ["/test/image1.jpg", "/test/image2.jpg"]

    def test_get_all_with_analysis_filters_by_directory(self, repo):
        """Test get_all_with_analysis filters by directory."""
        repo.register("/test/image1.jpg", "abc123", "/test", "image1.jpg", 1024, 12345.0)
        repo.register("/other/image2.jpg", "def456", "/other", "image2.jpg", 2048, 12346.0)

        results = repo.get_all_with_analysis(directory_filter="/test")

        assert len(results) == 1
        assert results[0]["directory_path"] == "/test"

    def test_get_all_with_analysis_accepts_provider_filter(self, repo):
        """Test get_all_with_analysis accepts provider_filter parameter."""
        repo.register("/test/image1.jpg", "abc123", "/test", "image1.jpg", 1024, 12345.0)

        # Call with provider filter (should not raise exception)
        results = repo.get_all_with_analysis(provider_filter="ollama")

        # Should return results (may be empty without metadata)
        assert isinstance(results, list)

    def test_get_batch_with_analysis_returns_dict(self, repo):
        """Test get_batch_with_analysis returns dict keyed by file_path."""
        repo.register("/test/image1.jpg", "abc123", "/test", "image1.jpg", 1024, 12345.0)
        repo.register("/test/image2.jpg", "def456", "/test", "image2.jpg", 2048, 12346.0)

        results = repo.get_batch_with_analysis(["/test/image1.jpg", "/test/image2.jpg"])

        assert isinstance(results, dict)
        assert "/test/image1.jpg" in results
        assert "/test/image2.jpg" in results
        assert results["/test/image1.jpg"]["file_path"] == "/test/image1.jpg"

    def test_get_batch_with_analysis_returns_empty_for_empty_list(self, repo):
        """Test get_batch_with_analysis returns empty dict for empty list."""
        results = repo.get_batch_with_analysis([])
        assert results == {}

    def test_get_stats_returns_counts(self, repo):
        """Test get_stats returns statistics."""
        repo.register("/test/image1.jpg", "abc123", "/test", "image1.jpg", 1024, 12345.0)
        repo.register("/test/image2.jpg", "def456", "/test", "image2.jpg", 2048, 12346.0)
        repo.update_status("/test/image2.jpg", "analyzed")

        stats = repo.get_stats()

        assert stats["total"] == 2
        assert stats["status_registered"] == 1
        assert stats["status_analyzed"] == 1

    def test_get_stats_returns_zero_for_empty_database(self, repo):
        """Test get_stats returns 0 for empty database."""
        stats = repo.get_stats()
        assert stats["total"] == 0
