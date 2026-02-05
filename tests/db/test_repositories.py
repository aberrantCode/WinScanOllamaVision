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
    ErrorRepository,
    MetadataRepository,
    ProviderRepository,
    RotationRepository,
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

    def test_save_with_tax_related_field(self, repo):
        # Arrange
        analysis_data = {"document_type": "Invoice", "company": "Test Corp", "tax_related": True}

        # Act
        repo.save(
            file_path="/test/tax_doc.jpg",
            file_hash="xyz789",
            provider_name="ollama",
            model_name="test-model",
            analysis_data=analysis_data,
            raw_response='{"test": "data"}',
            processing_time_ms=100,
        )
        result = repo.get_by_path("/test/tax_doc.jpg")

        # Assert
        assert result["tax_related"] == 1  # SQLite stores boolean as integer
        assert result["company"] == "Test Corp"

    def test_save_without_tax_related_defaults_to_false(self, repo):
        # Arrange - analysis_data without tax_related field
        analysis_data = {"document_type": "Receipt", "company": "Other Corp"}

        # Act
        repo.save(
            file_path="/test/non_tax_doc.jpg",
            file_hash="def456",
            provider_name="claude",
            model_name="claude-3",
            analysis_data=analysis_data,
            raw_response='{"test": "data"}',
            processing_time_ms=150,
        )
        result = repo.get_by_path("/test/non_tax_doc.jpg")

        # Assert
        assert result["tax_related"] == 0  # Should default to False (0)

    def test_update_metadata_with_tax_related(self, repo):
        # Arrange - save initial analysis
        repo.save(
            file_path="/test/update_tax.jpg",
            file_hash="hash123",
            provider_name="ollama",
            model_name="test-model",
            analysis_data={"document_type": "Invoice", "tax_related": False},
            raw_response='{"test": "data"}',
            processing_time_ms=100,
        )

        # Act - update metadata with tax_related
        updated_metadata = {
            "document_type": "Tax Invoice",
            "tax_related": True,
            "company": "Updated Corp",
        }
        repo.update_metadata("/test/update_tax.jpg", updated_metadata)
        result = repo.get_by_path("/test/update_tax.jpg")

        # Assert
        assert result["tax_related"] == 1
        assert result["document_type"] == "Tax Invoice"
        assert result["company"] == "Updated Corp"

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
