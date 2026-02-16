"""
Core tests for MetadataDB focusing on critical functionality.

Target: 80%+ coverage on core methods
"""

import os
import tempfile

import pytest

from db.metadata_db import MetadataDB


class TestMetadataDBCore:
    """Core test suite for MetadataDB"""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.remove(db_path)

    @pytest.fixture
    def db(self, temp_db_path):
        """Create MetadataDB instance"""
        database = MetadataDB(temp_db_path)
        yield database
        database.close()

    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for testing"""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"test content")
            file_path = f.name
        yield file_path
        if os.path.exists(file_path):
            os.remove(file_path)

    def test_init_creates_database(self, temp_db_path):
        # Act
        db = MetadataDB(temp_db_path)

        # Assert
        assert os.path.exists(temp_db_path)
        assert db.connection is not None
        db.close()

    def test_create_tables_creates_required_tables(self, db):
        # Act
        cursor = db.connection.connection.cursor()
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [table[0] for table in tables]

        # Assert - Check for new schema table names
        assert "schema_version" in table_names
        assert "image_files" in table_names
        assert "metadata" in table_names  # Replaces active_metadata
        assert "pdf_files" in table_names  # Archived documents

    def test_compute_file_hash_returns_consistent_hash(self, temp_file):
        # Act
        hash1 = MetadataDB.compute_file_hash(temp_file)
        hash2 = MetadataDB.compute_file_hash(temp_file)

        # Assert
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256

    def test_save_and_get_metadata(self, db, temp_file):
        # Arrange
        metadata = {
            "company": "Test Corp",
            "document_type": "Invoice",
            "page_number": 1,
            "total_pages": 3,
        }

        # Act
        db.save_metadata(temp_file, metadata)
        result = db.get_metadata(temp_file)

        # Assert
        assert result is not None
        assert result["company"] == "Test Corp"
        assert result["document_type"] == "Invoice"

    def test_get_metadata_returns_none_when_not_exists(self, db):
        # Act
        result = db.get_metadata("/nonexistent/file.jpg")

        # Assert
        assert result is None

    def test_delete_metadata_removes_record(self, db, temp_file):
        # Arrange
        db.save_metadata(temp_file, {"company": "Test"})

        # Act
        db.delete_metadata(temp_file)

        # Assert
        assert db.get_metadata(temp_file) is None

    def test_archive_document(self, db, temp_file):
        # Arrange
        db.save_metadata(temp_file, {"company": "Test Corp"})
        pdf_path = "/output/doc.pdf"
        doc_metadata = {"company": "Test Corp", "title": "Invoice"}

        # Act
        db.archive_document(pdf_path, [temp_file], doc_metadata)

        # Assert
        archived = db.get_archived_document(pdf_path)
        assert archived is not None
        assert archived["company"] == "Test Corp"

    def test_get_statistics(self, db, temp_file):
        # Arrange
        db.save_metadata(temp_file, {"company": "Test"})

        # Act
        stats = db.get_statistics()

        # Assert
        assert "active_metadata_count" in stats
        assert "archived_documents_count" in stats
        assert stats["active_metadata_count"] >= 1

    def test_save_and_get_rotation(self, db, temp_file):
        # Act
        db.save_rotation(temp_file, 90)
        rotation = db.get_rotation(temp_file)

        # Assert
        assert rotation == 90

    def test_get_rotation_returns_zero_when_not_set(self, db):
        # Act
        rotation = db.get_rotation("/nonexistent.jpg")

        # Assert
        assert rotation == 0

    def test_close_closes_connection(self, temp_db_path):
        # Arrange
        db = MetadataDB(temp_db_path)

        # Act
        db.close()

        # Assert - connection should be None after close
        assert db.connection.connection is None

    def test_context_manager(self, temp_db_path):
        # Act & Assert
        with MetadataDB(temp_db_path) as db:
            assert db.connection is not None

    def test_get_unique_companies(self, db, temp_file):
        # Arrange
        db.save_metadata(temp_file, {"company": "Test Corp"})

        # Act
        companies = db.get_unique_companies()

        # Assert
        assert "Test Corp" in companies

    def test_get_unique_companies_uses_cache(self, db, temp_file):
        # Arrange
        db.save_metadata(temp_file, {"company": "Test Corp"})

        # Act - first call populates cache
        companies1 = db.get_unique_companies(use_cache=True)
        # Second call uses cache
        companies2 = db.get_unique_companies(use_cache=True)

        # Assert
        assert companies1 == companies2

    def test_get_unique_titles(self, db, temp_file):
        # Arrange
        db.save_metadata(temp_file, {"document_type": "Invoice"})

        # Act
        titles = db.get_unique_titles()

        # Assert
        assert "Invoice" in titles

    def test_invalidate_field_history_cache(self, db, temp_file):
        # Arrange
        db.save_metadata(temp_file, {"company": "Test Corp"})
        db.get_unique_companies(use_cache=True)  # Populate cache

        # Act
        db.invalidate_field_history_cache()

        # Assert - cache should be cleared
        assert db._companies_cache is None
        assert db._titles_cache is None

    def test_get_schema_version(self, db):
        # Act
        version = db.get_schema_version()

        # Assert
        assert version >= 1

    def test_compute_file_hash_raises_file_not_found_error(self):
        # Act & Assert
        with pytest.raises(FileNotFoundError) as exc_info:
            MetadataDB.compute_file_hash("/nonexistent/file.jpg")

        assert "does not exist" in str(exc_info.value)

    def test_compute_file_hash_raises_permission_error(self, temp_file, monkeypatch):
        # Arrange - Mock open to raise PermissionError
        def mock_open(*args, **kwargs):
            raise PermissionError("Access denied")

        monkeypatch.setattr("builtins.open", mock_open)

        # Act & Assert
        with pytest.raises(PermissionError) as exc_info:
            MetadataDB.compute_file_hash(temp_file)

        assert "Cannot access file" in str(exc_info.value)

    def test_compute_file_hash_raises_os_error(self, temp_file, monkeypatch):
        # Arrange - Mock open to raise OSError
        def mock_open(*args, **kwargs):
            raise OSError("Disk read error")

        monkeypatch.setattr("builtins.open", mock_open)

        # Act & Assert
        with pytest.raises(OSError) as exc_info:
            MetadataDB.compute_file_hash(temp_file)

        assert "Failed to read file" in str(exc_info.value)

    def test_save_metadata_skips_nonexistent_file(self, db):
        # Arrange
        nonexistent_file = "/nonexistent/file.jpg"
        metadata = {"company": "Test"}

        # Act - should not raise error, just return early
        db.save_metadata(nonexistent_file, metadata)

        # Assert - metadata should not be saved
        result = db.get_metadata(nonexistent_file)
        assert result is None

    def test_cleanup_orphaned_metadata(self, db, temp_file):
        # Arrange - save metadata for temp file
        db.save_metadata(temp_file, {"company": "Test Corp"})

        # Delete the actual file (making metadata orphaned)
        os.remove(temp_file)

        # Act
        deleted_count = db.cleanup_orphaned_metadata()

        # Assert
        assert deleted_count == 1
        # Metadata should be removed
        assert db.get_metadata(temp_file) is None

    def test_cleanup_orphaned_metadata_with_no_orphans(self, db, temp_file):
        # Arrange
        db.save_metadata(temp_file, {"company": "Test Corp"})

        # Act - file still exists, so no orphans
        deleted_count = db.cleanup_orphaned_metadata()

        # Assert
        assert deleted_count == 0
        # Metadata should still exist
        assert db.get_metadata(temp_file) is not None

    def test_create_backup_with_auto_timestamp(self, db, temp_file):
        # Arrange
        db.save_metadata(temp_file, {"company": "Test"})

        # Act - create backup with auto-generated path
        backup_path = db.create_backup()

        # Assert
        assert os.path.exists(backup_path)
        assert "_backup_" in backup_path
        assert backup_path.endswith(".db")

        # Cleanup
        if os.path.exists(backup_path):
            os.remove(backup_path)

    def test_create_backup_with_custom_path(self, db, temp_file):
        # Arrange
        db.save_metadata(temp_file, {"company": "Test"})
        custom_backup_path = db.db_path.replace(".db", "_custom_backup.db")

        # Act
        returned_path = db.create_backup(custom_backup_path)

        # Assert
        assert returned_path == custom_backup_path
        assert os.path.exists(custom_backup_path)

        # Cleanup
        if os.path.exists(custom_backup_path):
            os.remove(custom_backup_path)

    def test_get_unique_titles_uses_cache(self, db, temp_file):
        # Arrange
        db.save_metadata(temp_file, {"document_type": "Invoice"})

        # Act - first call populates cache
        titles1 = db.get_unique_titles(use_cache=True)
        # Second call uses cache (line 251 coverage)
        titles2 = db.get_unique_titles(use_cache=True)

        # Assert
        assert titles1 == titles2
        assert "Invoice" in titles1

    def test_init_with_default_appdata_path(self, monkeypatch):
        # Arrange - create temp directory to use as AppData
        with tempfile.TemporaryDirectory() as temp_appdata:
            # Mock get_appdata_db_path to return a path in our temp directory
            temp_db_path = os.path.join(temp_appdata, "metadata.db")

            def mock_get_appdata_db_path():
                return temp_db_path

            monkeypatch.setattr("db.metadata_db.get_appdata_db_path", mock_get_appdata_db_path)

            # Act - initialize with None (should use default AppData path)
            db = MetadataDB(db_path=None)

            try:
                # Assert
                assert db.db_path == temp_db_path
                assert os.path.exists(temp_db_path)
            finally:
                db.close()

    def test_get_logger_initializes_logger(self, db):
        # Act
        logger = db._get_logger()

        # Assert
        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
