"""
Comprehensive tests for database repository classes.

Tests repository methods in isolation with mocked DatabaseConnection.
"""

import os
import tempfile

import pytest

from db.connection import DatabaseConnection
from db.repositories import (
    AnalysisRepository,
    AuditRepository,
    BundleRepository,
    DirectoryRepository,
    MetadataRepository,
    ProviderRepository,
    RotationRepository,
    RunTrackingRepository,
)


class TestMetadataRepository:
    """Tests for MetadataRepository"""

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
        # Create schema
        from db.schema import create_all_tables

        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return MetadataRepository(conn)

    @pytest.fixture
    def temp_file(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"test content")
            file_path = f.name
        yield file_path
        if os.path.exists(file_path):
            os.remove(file_path)

    def test_save_metadata(self, repo, temp_file):
        # Arrange
        metadata = {"company": "Test Corp", "document_type": "Invoice"}

        # Act
        repo.save_metadata(temp_file, metadata)

        # Assert
        result = repo.get_metadata(temp_file)
        assert result["company"] == "Test Corp"

    def test_get_metadata_returns_none_when_not_exists(self, repo):
        # Act
        result = repo.get_metadata("/nonexistent.jpg")

        # Assert
        assert result is None

    def test_delete_metadata(self, repo, temp_file):
        # Arrange
        repo.save_metadata(temp_file, {"company": "Test"})

        # Act
        repo.delete_metadata(temp_file)

        # Assert
        assert repo.get_metadata(temp_file) is None

    def test_archive_document(self, repo, temp_file):
        # Arrange
        pdf_path = "/output/doc.pdf"
        source_files = [temp_file]
        doc_metadata = {"company": "Test Corp", "title": "Invoice"}

        # Act
        repo.archive_document(pdf_path, source_files, doc_metadata)

        # Assert
        archived = repo.get_archived_document(pdf_path)
        assert archived is not None
        assert archived["company"] == "Test Corp"

    def test_get_statistics(self, repo, temp_file):
        # Arrange
        repo.save_metadata(temp_file, {"company": "Test"})

        # Act
        stats = repo.get_statistics()

        # Assert
        assert stats["active_metadata_count"] >= 1
        assert "archived_documents_count" in stats

    def test_cleanup_orphaned_metadata(self, repo):
        # Arrange - save metadata for non-existent file
        fake_file = "/nonexistent/file.jpg"
        repo.conn.execute(
            """INSERT INTO active_metadata
               (file_path, file_hash, file_size, file_mtime)
               VALUES (?, ?, ?, ?)""",
            (fake_file, "hash123", 1000, 123456.0),
        )
        repo.conn.commit()

        # Act
        removed_count = repo.cleanup_orphaned_metadata()

        # Assert
        assert removed_count >= 1

    def test_create_backup(self, repo, temp_file, temp_db_path):
        # Arrange
        repo.save_metadata(temp_file, {"company": "Test"})

        # Act - pass None to generate automatic backup path
        backup_path = repo.create_backup(None)

        # Assert
        assert os.path.exists(backup_path)
        assert backup_path.startswith(temp_db_path)
        # Cleanup
        if os.path.exists(backup_path):
            os.remove(backup_path)


class TestAnalysisRepository:
    """Tests for AnalysisRepository"""

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
        return AnalysisRepository(conn)

    def test_save_and_get(self, repo):
        # Arrange
        analysis_data = {"document_type": "Invoice", "company": "Test Corp"}

        # Act
        repo.save(
            file_path="/test/page.jpg",
            file_hash="abc123",
            provider_name="ollama",
            model_name="test-model",
            analysis_data=analysis_data,
            raw_response='{"test": "data"}',
            processing_time_ms=100,
        )
        result = repo.get_by_path("/test/page.jpg")

        # Assert
        assert result["company"] == "Test Corp"
        assert result["provider_name"] == "ollama"

    def test_get_all_with_filters(self, repo):
        # Arrange
        repo.save("/p1.jpg", "h1", "ollama", "m1", {"page_number": 1}, "{}", 100)
        repo.save("/p2.jpg", "h2", "claude", "m2", {"page_number": 2}, "{}", 100)

        # Act
        all_results = repo.get_all()
        ollama_only = repo.get_all(provider_filter="ollama")

        # Assert
        assert len(all_results) >= 2
        assert len(ollama_only) >= 1


class TestBundleRepository:
    """Tests for BundleRepository"""

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
        return BundleRepository(conn)

    def test_save_and_get_suggestions(self, repo):
        # Arrange
        file_paths = ["/p1.jpg", "/p2.jpg"]
        metadata = {"company": "Test Corp", "document_type": "Invoice"}

        # Act
        bundle_id = repo.save_suggestion(file_paths, metadata, 0.9)
        suggestions = repo.get_suggestions()

        # Assert
        assert bundle_id > 0
        assert len(suggestions) > 0

    def test_update_status(self, repo):
        # Arrange
        bundle_id = repo.save_suggestion(["/p1.jpg"], {"company": "Test"}, 0.9)

        # Act
        repo.update_status(bundle_id, "accepted", "user_approved")

        # Assert - verify no exception raised
        assert bundle_id > 0

    def test_get_suggestions_with_filters(self, repo):
        # Arrange
        repo.save_suggestion(["/p1.jpg"], {"company": "Test"}, 0.9)
        repo.save_suggestion(["/p2.jpg"], {"company": "Test"}, 0.5)

        # Act
        high_confidence = repo.get_suggestions(min_confidence=0.8)
        all_suggestions = repo.get_suggestions()

        # Assert
        assert len(high_confidence) >= 1
        assert len(all_suggestions) >= 2


class TestProviderRepository:
    """Tests for ProviderRepository"""

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
        return ProviderRepository(conn)

    def test_add_and_get_active(self, repo):
        # Arrange
        config = {"base_url": "http://localhost:11434"}

        # Act
        repo.add("ollama", "ollama", config, "test-model")
        repo.set_active("ollama")
        active = repo.get_active()

        # Assert
        assert active["provider_name"] == "ollama"

    def test_get_active_returns_none_when_no_active(self, repo):
        # Act
        active = repo.get_active()

        # Assert
        assert active is None


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

    def test_save_preference(self, repo, temp_file):
        # Act
        repo.save_preference(temp_file, 180, "manual")

        # Assert - save_preference stores in rotation_preferences table
        # Verify it was saved by querying directly
        cursor = repo.conn.connection.cursor()
        result = cursor.execute(
            "SELECT rotation_degrees FROM rotation_preferences WHERE file_path = ?", (temp_file,)
        ).fetchone()
        assert result is not None
        assert result["rotation_degrees"] == 180


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


class TestRunTrackingRepository:
    """Tests for RunTrackingRepository"""

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
        return RunTrackingRepository(conn)

    def test_start_and_update_run(self, repo):
        # Act
        repo.start_run("run123", total_files=10)
        repo.update_run("run123", analyzed=5, cached=2)

        # Assert - verify run was created and updated
        cursor = repo.conn.connection.cursor()
        result = cursor.execute(
            "SELECT analyzed, cached FROM analysis_runs WHERE run_id = ?",
            ("run123",),
        ).fetchone()
        assert result["analyzed"] == 5
        assert result["cached"] == 2

    def test_save_error(self, repo):
        # Arrange
        repo.start_run("run123", total_files=10)

        # Act
        repo.save_error("run123", "/test/file.jpg", "Test error", "test_type")

        # Assert
        cursor = repo.conn.connection.cursor()
        result = cursor.execute(
            "SELECT error_type FROM analysis_errors WHERE file_path = ?",
            ("/test/file.jpg",),
        ).fetchone()
        assert result["error_type"] == "test_type"

    def test_get_recent_runs(self, repo):
        # Arrange
        repo.start_run("run1", 10)
        repo.start_run("run2", 20)

        # Act
        runs = repo.get_recent_runs(limit=5)

        # Assert
        assert len(runs) >= 2

    def test_update_run_with_completed_status(self, repo):
        # Arrange
        repo.start_run("run_complete", total_files=10)

        # Act
        repo.update_run("run_complete", analyzed=10, cached=0, status="completed")

        # Assert - verify completed_at and duration_ms were set
        cursor = repo.conn.connection.cursor()
        result = cursor.execute(
            "SELECT status, completed_at, duration_ms FROM analysis_runs WHERE run_id = ?",
            ("run_complete",),
        ).fetchone()
        assert result["status"] == "completed"
        assert result["completed_at"] is not None
        assert result["duration_ms"] is not None

    def test_get_recent_runs_status_categorization(self, repo):
        # Arrange - create runs with different outcomes
        # Success: 0 errors
        repo.start_run("success_run", total_files=10)
        repo.update_run("success_run", analyzed=10, errors=0, status="completed")

        # Failed: all errors
        repo.start_run("failed_run", total_files=5)
        repo.update_run("failed_run", analyzed=0, errors=5, status="completed")

        # Partial: some errors
        repo.start_run("partial_run", total_files=10)
        repo.update_run("partial_run", analyzed=8, errors=2, status="completed")

        # Running: still in progress
        repo.start_run("running_run", total_files=10)

        # Act
        runs = repo.get_recent_runs(limit=10)

        # Assert - find each run and verify status
        runs_by_id = {run["run_id"]: run for run in runs}

        assert runs_by_id["success_run"]["status"] == "success"
        assert runs_by_id["failed_run"]["status"] == "failed"
        assert runs_by_id["partial_run"]["status"] == "partial"
        assert runs_by_id["running_run"]["status"] == "running"
