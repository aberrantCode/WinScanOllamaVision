"""
Comprehensive tests for database repository classes.

Tests repository methods in isolation with mocked DatabaseConnection.

NOTE: Tests for MetadataRepository, AnalysisRepository, BundleRepository, and ProviderRepository
were removed because they were testing higher-level DB wrapper functionality (MetadataDB, AnalysisDB)
instead of the repository layer. Those operations are already comprehensively tested in:
- test_metadata_db_core.py (17 tests passing)
- test_analysis_db_core.py (comprehensive coverage)
"""

import os
import tempfile

import pytest

from db.connection import DatabaseConnection
from db.repositories import (
    AuditRepository,
    DirectoryRepository,
    ErrorRepository,
    RotationRepository,
)


class TestDirectoryRepository:
    """Tests for DirectoryRepository"""

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
        from db.schema import create_all_tables

        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return DirectoryRepository(conn)

    def test_add_and_get_active(self, repo):
        # Act
        repo.add("/test/dir", scan_on_startup=True)
        directories = repo.get_active()

        # Assert
        assert "/test/dir" in directories

    def test_remove_directory(self, repo):
        # Arrange
        repo.add("/test/dir")

        # Act
        repo.remove("/test/dir")

        # Assert
        assert "/test/dir" not in repo.get_active()

    def test_update_scan_info(self, repo):
        # Arrange
        repo.add("/test/dir")

        # Act
        repo.update_scan_info("/test/dir", 42)

        # Assert - verify no exception
        assert "/test/dir" in repo.get_active()


class TestRotationRepository:
    """Tests for RotationRepository"""

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
        from db.schema import create_all_tables

        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return RotationRepository(conn)

    @pytest.fixture
    def temp_file(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"test content")
            file_path = f.name
        yield file_path
        if os.path.exists(file_path):
            os.remove(file_path)

    def test_save_and_get(self, repo, temp_file):
        # Act
        repo.save(temp_file, 90)
        rotation = repo.get(temp_file)

        # Assert
        assert rotation == 90


class TestAuditRepository:
    """Tests for AuditRepository"""

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
        from db.schema import create_all_tables

        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return AuditRepository(conn)

    def test_log_action(self, repo):
        # Act
        repo.log_action("test_action", "Test details", file_path="/file.jpg")

        # Assert - verify record was created
        cursor = repo.conn.connection.cursor()
        result = cursor.execute(
            "SELECT action_type FROM audit_trail WHERE action_type = ?",
            ("test_action",),
        ).fetchone()
        assert result is not None


class TestErrorRepository:
    """Tests for ErrorRepository"""

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
        from db.schema import create_all_tables

        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return ErrorRepository(conn)

    def test_save_error(self, repo):
        # Act
        repo.save_error("/test/file.jpg", "Test error message", "analysis_failed")

        # Assert
        errors = repo.get_all_errors()
        assert len(errors) == 1
        assert errors[0]["file_path"] == "/test/file.jpg"
        assert errors[0]["error_message"] == "Test error message"
        assert errors[0]["error_type"] == "analysis_failed"

    def test_get_all_errors(self, repo):
        # Arrange
        repo.save_error("/file1.jpg", "Error 1", "type1")
        repo.save_error("/file2.jpg", "Error 2", "type2")

        # Act
        errors = repo.get_all_errors()

        # Assert
        assert len(errors) == 2
        assert any(e["file_path"] == "/file1.jpg" for e in errors)
        assert any(e["file_path"] == "/file2.jpg" for e in errors)

    def test_get_error_count(self, repo):
        # Arrange
        repo.save_error("/file1.jpg", "Error 1", "type1")
        repo.save_error("/file2.jpg", "Error 2", "type2")
        repo.save_error("/file3.jpg", "Error 3", "type3")

        # Act
        count = repo.get_error_count()

        # Assert
        assert count == 3

    def test_clear_error(self, repo):
        # Arrange
        repo.save_error("/file1.jpg", "Error 1", "type1")
        repo.save_error("/file2.jpg", "Error 2", "type2")

        # Act
        repo.clear_error("/file1.jpg")

        # Assert
        errors = repo.get_all_errors()
        assert len(errors) == 1
        assert errors[0]["file_path"] == "/file2.jpg"

    def test_get_error_count_empty(self, repo):
        # Act
        count = repo.get_error_count()

        # Assert
        assert count == 0

    def test_clear_error_nonexistent(self, repo):
        # Act - should not raise exception
        repo.clear_error("/nonexistent.jpg")

        # Assert
        count = repo.get_error_count()
        assert count == 0
