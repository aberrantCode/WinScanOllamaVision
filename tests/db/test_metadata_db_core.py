"""
Core tests for MetadataDB focusing on critical functionality.

Target: 80%+ coverage on core methods
"""

import os
import sqlite3
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
        cursor = db.connection.cursor()
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [table[0] for table in tables]

        # Assert
        assert "schema_version" in table_names
        assert "active_metadata" in table_names
        assert "archived_metadata" in table_names

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

        # Assert
        try:
            db.connection.execute("SELECT 1")
            is_open = True
        except sqlite3.ProgrammingError:
            is_open = False
        assert not is_open

    def test_context_manager(self, temp_db_path):
        # Act & Assert
        with MetadataDB(temp_db_path) as db:
            assert db.connection is not None
