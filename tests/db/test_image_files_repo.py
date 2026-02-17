"""
Comprehensive tests for ImageFilesRepository.

Tests the image file lifecycle tracking and ignore functionality.
"""

import os
import tempfile

import pytest

from db.connection import DatabaseConnection
from db.repositories.image_files_repo import ImageFilesRepository


class TestImageFilesRepositoryIgnore:
    """Tests for ignore functionality in ImageFilesRepository."""

    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.remove(db_path)

    @pytest.fixture
    def conn(self, temp_db_path):
        """Create database connection with schema."""
        connection = DatabaseConnection(temp_db_path)
        from db.schema import create_all_tables

        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        """Create ImageFilesRepository instance."""
        return ImageFilesRepository(conn)

    @pytest.fixture
    def sample_image_path(self):
        """Create temporary test image file."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"test image content")
            file_path = f.name
        yield file_path
        if os.path.exists(file_path):
            os.remove(file_path)

    def test_set_ignored_true(self, repo, sample_image_path):
        """Test setting image as ignored."""
        # Arrange - register image first
        repo.register(
            file_path=sample_image_path,
            file_hash="test_hash_123",
            directory_path=os.path.dirname(sample_image_path),
            filename=os.path.basename(sample_image_path),
            file_size=100,
            file_mtime=1234567890.0,
        )

        # Act
        repo.set_ignored(sample_image_path, ignored=True)

        # Assert
        image_record = repo.get_by_path(sample_image_path)
        assert image_record is not None
        assert image_record["is_ignored"] == 1  # SQLite stores boolean as 0/1

    def test_set_ignored_false(self, repo, sample_image_path):
        """Test un-ignoring an image."""
        # Arrange - register and ignore
        repo.register(
            file_path=sample_image_path,
            file_hash="test_hash_123",
            directory_path=os.path.dirname(sample_image_path),
            filename=os.path.basename(sample_image_path),
            file_size=100,
            file_mtime=1234567890.0,
        )
        repo.set_ignored(sample_image_path, ignored=True)

        # Act - un-ignore
        repo.set_ignored(sample_image_path, ignored=False)

        # Assert
        image_record = repo.get_by_path(sample_image_path)
        assert image_record is not None
        assert image_record["is_ignored"] == 0

    def test_set_ignored_nonexistent_file(self, repo):
        """Test setting ignored on non-existent file doesn't raise error."""
        # Act - should not raise exception
        repo.set_ignored("/nonexistent/file.jpg", ignored=True)

        # Assert - verify it didn't affect anything
        assert repo.get_ignored_count() == 0

    def test_get_ignored_count_empty(self, repo):
        """Test ignored count when no images are ignored."""
        # Act
        count = repo.get_ignored_count()

        # Assert
        assert count == 0

    def test_get_ignored_count_single(self, repo, sample_image_path):
        """Test ignored count with one ignored image."""
        # Arrange
        repo.register(
            file_path=sample_image_path,
            file_hash="test_hash_123",
            directory_path=os.path.dirname(sample_image_path),
            filename=os.path.basename(sample_image_path),
            file_size=100,
            file_mtime=1234567890.0,
        )
        repo.set_ignored(sample_image_path, ignored=True)

        # Act
        count = repo.get_ignored_count()

        # Assert
        assert count == 1

    def test_get_ignored_count_multiple(self, repo):
        """Test ignored count with multiple ignored images."""
        # Arrange - register and ignore 3 images
        for i in range(3):
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(b"test content")
                file_path = f.name

            repo.register(
                file_path=file_path,
                file_hash=f"hash_{i}",
                directory_path=os.path.dirname(file_path),
                filename=os.path.basename(file_path),
                file_size=100,
                file_mtime=1234567890.0,
            )
            repo.set_ignored(file_path, ignored=True)

            # Clean up temp file
            os.remove(file_path)

        # Act
        count = repo.get_ignored_count()

        # Assert
        assert count == 3

    def test_set_ignored_batch_empty_list(self, repo):
        """Test batch ignore with empty list."""
        # Act
        affected = repo.set_ignored_batch([], ignored=True)

        # Assert
        assert affected == 0

    def test_set_ignored_batch_single(self, repo, sample_image_path):
        """Test batch ignore with single file."""
        # Arrange
        repo.register(
            file_path=sample_image_path,
            file_hash="test_hash_123",
            directory_path=os.path.dirname(sample_image_path),
            filename=os.path.basename(sample_image_path),
            file_size=100,
            file_mtime=1234567890.0,
        )

        # Act
        affected = repo.set_ignored_batch([sample_image_path], ignored=True)

        # Assert
        assert affected == 1
        image_record = repo.get_by_path(sample_image_path)
        assert image_record["is_ignored"] == 1

    def test_set_ignored_batch_multiple(self, repo):
        """Test batch ignore with multiple files."""
        # Arrange - register 5 images
        file_paths = []
        for i in range(5):
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(b"test content")
                file_path = f.name
                file_paths.append(file_path)

            repo.register(
                file_path=file_path,
                file_hash=f"hash_{i}",
                directory_path=os.path.dirname(file_path),
                filename=os.path.basename(file_path),
                file_size=100,
                file_mtime=1234567890.0,
            )

        # Act
        affected = repo.set_ignored_batch(file_paths, ignored=True)

        # Assert
        assert affected == 5
        assert repo.get_ignored_count() == 5

        # Verify each file is ignored
        for file_path in file_paths:
            image_record = repo.get_by_path(file_path)
            assert image_record["is_ignored"] == 1
            os.remove(file_path)  # Clean up

    def test_set_ignored_batch_un_ignore(self, repo):
        """Test batch un-ignore operation."""
        # Arrange - register and ignore 3 images
        file_paths = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(b"test content")
                file_path = f.name
                file_paths.append(file_path)

            repo.register(
                file_path=file_path,
                file_hash=f"hash_{i}",
                directory_path=os.path.dirname(file_path),
                filename=os.path.basename(file_path),
                file_size=100,
                file_mtime=1234567890.0,
            )
            repo.set_ignored(file_path, ignored=True)

        # Verify they're ignored
        assert repo.get_ignored_count() == 3

        # Act - batch un-ignore
        affected = repo.set_ignored_batch(file_paths, ignored=False)

        # Assert
        assert affected == 3
        assert repo.get_ignored_count() == 0

        # Verify each file is not ignored
        for file_path in file_paths:
            image_record = repo.get_by_path(file_path)
            assert image_record["is_ignored"] == 0
            os.remove(file_path)  # Clean up

    def test_set_ignored_batch_mixed_files(self, repo):
        """Test batch ignore with mix of existing and non-existing files."""
        # Arrange - register only 2 out of 3 files
        file_paths = []
        for i in range(2):
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(b"test content")
                file_path = f.name
                file_paths.append(file_path)

            repo.register(
                file_path=file_path,
                file_hash=f"hash_{i}",
                directory_path=os.path.dirname(file_path),
                filename=os.path.basename(file_path),
                file_size=100,
                file_mtime=1234567890.0,
            )

        # Add non-existent file to batch
        file_paths.append("/nonexistent/file.jpg")

        # Act
        affected = repo.set_ignored_batch(file_paths, ignored=True)

        # Assert - only 2 should be affected
        assert affected == 2
        assert repo.get_ignored_count() == 2

        # Clean up
        for file_path in file_paths[:-1]:  # Exclude the non-existent one
            os.remove(file_path)

    def test_get_all_filters_ignored_by_default(self, repo):
        """Test that get_all() does NOT filter ignored images (returns all non-deleted)."""
        # Arrange - register 3 images, ignore 1
        file_paths = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(b"test content")
                file_path = f.name
                file_paths.append(file_path)

            repo.register(
                file_path=file_path,
                file_hash=f"hash_{i}",
                directory_path=os.path.dirname(file_path),
                filename=os.path.basename(file_path),
                file_size=100,
                file_mtime=1234567890.0,
            )

        # Ignore the first one
        repo.set_ignored(file_paths[0], ignored=True)

        # Act
        all_images = repo.get_all()

        # Assert - should include all 3 (ignored images still returned by get_all)
        assert len(all_images) == 3

        # Clean up
        for file_path in file_paths:
            os.remove(file_path)

    def test_ignored_survives_status_update(self, repo, sample_image_path):
        """Test that ignore flag persists when status is updated."""
        # Arrange
        repo.register(
            file_path=sample_image_path,
            file_hash="test_hash_123",
            directory_path=os.path.dirname(sample_image_path),
            filename=os.path.basename(sample_image_path),
            file_size=100,
            file_mtime=1234567890.0,
        )
        repo.set_ignored(sample_image_path, ignored=True)

        # Act - change status
        repo.update_status(sample_image_path, "analyzed")

        # Assert - ignore flag should still be set
        image_record = repo.get_by_path(sample_image_path)
        assert image_record["status"] == "analyzed"
        assert image_record["is_ignored"] == 1


class TestImageFilesRepositoryBasic:
    """Tests for basic ImageFilesRepository functionality (non-ignore)."""

    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.remove(db_path)

    @pytest.fixture
    def conn(self, temp_db_path):
        """Create database connection with schema."""
        connection = DatabaseConnection(temp_db_path)
        from db.schema import create_all_tables

        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        """Create ImageFilesRepository instance."""
        return ImageFilesRepository(conn)

    def test_register_new_image(self, repo):
        """Test registering a new image file."""
        # Act
        file_id = repo.register(
            file_path="/test/image.jpg",
            file_hash="abc123",
            directory_path="/test",
            filename="image.jpg",
            file_size=1024,
            file_mtime=1234567890.0,
        )

        # Assert
        assert file_id > 0
        image_record = repo.get_by_path("/test/image.jpg")
        assert image_record is not None
        assert image_record["file_hash"] == "abc123"
        assert image_record["status"] == "registered"

    def test_get_by_path(self, repo):
        """Test retrieving image by path."""
        # Arrange
        repo.register(
            file_path="/test/image.jpg",
            file_hash="abc123",
            directory_path="/test",
            filename="image.jpg",
            file_size=1024,
            file_mtime=1234567890.0,
        )

        # Act
        image_record = repo.get_by_path("/test/image.jpg")

        # Assert
        assert image_record is not None
        assert image_record["filename"] == "image.jpg"

    def test_update_status(self, repo):
        """Test updating image status."""
        # Arrange
        repo.register(
            file_path="/test/image.jpg",
            file_hash="abc123",
            directory_path="/test",
            filename="image.jpg",
            file_size=1024,
            file_mtime=1234567890.0,
        )

        # Act
        repo.update_status("/test/image.jpg", "analyzed")

        # Assert
        image_record = repo.get_by_path("/test/image.jpg")
        assert image_record["status"] == "analyzed"

    def test_mark_deleted(self, repo):
        """Test marking image as deleted."""
        # Arrange
        repo.register(
            file_path="/test/image.jpg",
            file_hash="abc123",
            directory_path="/test",
            filename="image.jpg",
            file_size=1024,
            file_mtime=1234567890.0,
        )

        # Act
        repo.mark_deleted("/test/image.jpg")

        # Assert
        image_record = repo.get_by_path("/test/image.jpg")
        assert image_record["status"] == "deleted"
        assert image_record["deleted_at"] is not None
