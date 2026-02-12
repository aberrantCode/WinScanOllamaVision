"""
Core tests for MetadataDB focusing on new architecture.

Tests:
- Normalized metadata operations
- Image file operations
- Archived document operations
- Autocomplete/distinct values

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

    # ==================== Basic Initialization Tests ====================

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

        # Assert
        assert "schema_version" in table_names
        assert "metadata" in table_names  # Normalized metadata table
        assert "image_files" in table_names  # Image file tracking
        assert "document_bundles" in table_names
        assert "pdf_files" in table_names

    def test_compute_file_hash_returns_consistent_hash(self, temp_file):
        # Act
        hash1 = MetadataDB.compute_file_hash(temp_file)
        hash2 = MetadataDB.compute_file_hash(temp_file)

        # Assert
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256

    def test_compute_file_hash_file_not_found(self):
        """Test that compute_file_hash raises FileNotFoundError for nonexistent file"""
        # Arrange
        nonexistent_path = "/nonexistent/path/to/file.png"

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="does not exist"):
            MetadataDB.compute_file_hash(nonexistent_path)

    def test_compute_file_hash_permission_denied(self, temp_file, monkeypatch):
        """Test that compute_file_hash raises PermissionError when file is not accessible"""

        # Arrange - Mock open to raise PermissionError
        def mock_open(*args, **kwargs):
            raise PermissionError("Access denied")

        monkeypatch.setattr("builtins.open", mock_open)

        # Act & Assert
        with pytest.raises(PermissionError, match="Cannot access file"):
            MetadataDB.compute_file_hash(temp_file)

    def test_compute_file_hash_os_error(self, temp_file, monkeypatch):
        """Test that compute_file_hash raises OSError for OS-level errors"""

        # Arrange - Mock open to raise OSError
        def mock_open(*args, **kwargs):
            raise OSError("Disk I/O error")

        monkeypatch.setattr("builtins.open", mock_open)

        # Act & Assert
        with pytest.raises(OSError, match="Failed to read file"):
            MetadataDB.compute_file_hash(temp_file)

    # ==================== Image File Operations Tests ====================

    def test_register_image_file(self, db, temp_file):
        """Test registering an image file"""
        # Arrange
        file_hash = MetadataDB.compute_file_hash(temp_file)
        file_size = os.path.getsize(temp_file)
        file_mtime = os.path.getmtime(temp_file)

        # Act
        image_id = db.register_image_file(
            file_path=temp_file,
            file_hash=file_hash,
            directory_path=os.path.dirname(temp_file),
            filename=os.path.basename(temp_file),
            file_size=file_size,
            file_mtime=file_mtime,
        )

        # Assert
        assert image_id is not None
        assert image_id > 0

    def test_get_image_file(self, db, temp_file):
        """Test retrieving image file metadata"""
        # Arrange
        file_hash = MetadataDB.compute_file_hash(temp_file)
        file_size = os.path.getsize(temp_file)
        file_mtime = os.path.getmtime(temp_file)

        db.register_image_file(
            temp_file,
            file_hash,
            os.path.dirname(temp_file),
            os.path.basename(temp_file),
            file_size,
            file_mtime,
        )

        # Act
        result = db.get_image_file(temp_file)

        # Assert
        assert result is not None
        assert result["file_path"] == temp_file
        assert result["file_hash"] == file_hash
        assert result["status"] == "registered"  # Default status

    def test_update_image_rotation(self, db, temp_file):
        """Test updating image rotation"""
        # Arrange
        file_hash = MetadataDB.compute_file_hash(temp_file)
        db.register_image_file(
            temp_file, file_hash, os.path.dirname(temp_file), os.path.basename(temp_file), 100, 0.0
        )

        # Act
        db.update_image_rotation(temp_file, 90)
        rotation = db.get_image_rotation(temp_file)

        # Assert
        assert rotation == 90

    def test_get_image_rotation_default(self, db, temp_file):
        """Test that default rotation is 0"""
        # Arrange
        file_hash = MetadataDB.compute_file_hash(temp_file)
        db.register_image_file(
            temp_file, file_hash, os.path.dirname(temp_file), os.path.basename(temp_file), 100, 0.0
        )

        # Act
        rotation = db.get_image_rotation(temp_file)

        # Assert
        assert rotation == 0

    def test_update_image_status(self, db, temp_file):
        """Test updating image file status"""
        # Arrange
        file_hash = MetadataDB.compute_file_hash(temp_file)
        db.register_image_file(
            temp_file, file_hash, os.path.dirname(temp_file), os.path.basename(temp_file), 100, 0.0
        )

        # Act
        db.update_image_status(temp_file, "analyzed")
        result = db.get_image_file(temp_file)

        # Assert
        assert result["status"] == "analyzed"

    # ==================== Normalized Metadata Tests ====================

    def test_get_normalized_metadata_by_path(self, db, temp_file):
        """Test retrieving normalized metadata by file path"""
        # Arrange
        file_hash = MetadataDB.compute_file_hash(temp_file)
        image_id = db.register_image_file(
            temp_file, file_hash, os.path.dirname(temp_file), os.path.basename(temp_file), 100, 0.0
        )

        # Create metadata record
        normalized_metadata = {
            "company": "Test Corp",
            "document_type": "Invoice",
            "document_date": "2024-01-15",
        }
        db.create_normalized_metadata(image_id, None, normalized_metadata)

        # Act
        result = db.get_normalized_metadata_by_path(temp_file)

        # Assert
        assert result is not None
        assert result["company"] == "Test Corp"
        assert result["document_type"] == "Invoice"

    def test_get_normalized_metadata_by_image_id(self, db, temp_file):
        """Test retrieving normalized metadata by image ID"""
        # Arrange
        file_hash = MetadataDB.compute_file_hash(temp_file)
        image_id = db.register_image_file(
            temp_file, file_hash, os.path.dirname(temp_file), os.path.basename(temp_file), 100, 0.0
        )

        # Create metadata record
        normalized_metadata = {
            "company": "Test Corp",
            "document_type": "Receipt",
        }
        db.create_normalized_metadata(image_id, None, normalized_metadata)

        # Act
        result = db.get_normalized_metadata_by_image_id(image_id)

        # Assert
        assert result is not None
        assert result["company"] == "Test Corp"
        assert result["document_type"] == "Receipt"

    def test_update_normalized_metadata(self, db, temp_file):
        """Test updating normalized metadata"""
        # Arrange
        file_hash = MetadataDB.compute_file_hash(temp_file)
        image_id = db.register_image_file(
            temp_file, file_hash, os.path.dirname(temp_file), os.path.basename(temp_file), 100, 0.0
        )

        # Create initial metadata
        db.create_normalized_metadata(image_id, None, {"company": "Original Corp"})

        # Act - Update the company
        db.update_normalized_metadata(image_id, {"company": "Updated Corp"})

        result = db.get_normalized_metadata_by_image_id(image_id)

        # Assert
        assert result["company"] == "Updated Corp"

    # ==================== Archived Document Tests ====================

    def test_archive_document(self, db):
        """Test archiving a completed document"""
        # Arrange - Create bundle and PDF first
        pdf_path = "/output/test_invoice.pdf"
        source_files = ["/scans/page1.jpg", "/scans/page2.jpg"]
        document_metadata = {
            "company": "Acme Corp",
            "document_type": "Invoice",
            "date": "2024-01-15",
        }

        # Create bundle
        cursor = db.connection.execute(
            "INSERT INTO document_bundles (bundle_name, confidence_score, confidence_level, status) VALUES (?, ?, ?, ?)",
            ("Test Invoice", 0.9, "high", "completed"),
        )
        bundle_id = cursor.lastrowid

        # Create PDF file
        db.connection.execute(
            "INSERT INTO pdf_files (pdf_path, pdf_filename, bundle_id, page_count) VALUES (?, ?, ?, ?)",
            (pdf_path, "test_invoice.pdf", bundle_id, 2),
        )
        db.connection.commit()

        # Act - archive_document is now a no-op, but get_archived_document should work
        db.archive_document(pdf_path, source_files, document_metadata)
        result = db.get_archived_document(pdf_path)

        # Assert - check PDF info (metadata is stored separately in metadata table)
        assert result is not None
        assert result["pdf_path"] == pdf_path
        assert result["page_count"] == 2
        assert result["bundle_name"] == "Test Invoice"

    def test_get_archived_statistics(self, db):
        """Test getting archived document statistics"""
        # Arrange - Create bundles and PDFs
        # Create bundle 1
        cursor = db.connection.execute(
            "INSERT INTO document_bundles (bundle_name, status) VALUES (?, ?)",
            ("Doc 1", "completed"),
        )
        bundle_id1 = cursor.lastrowid
        db.connection.execute(
            "INSERT INTO pdf_files (pdf_path, pdf_filename, bundle_id, page_count, generation_status) VALUES (?, ?, ?, ?, ?)",
            ("/out/doc1.pdf", "doc1.pdf", bundle_id1, 1, "completed"),
        )

        # Create bundle 2
        cursor = db.connection.execute(
            "INSERT INTO document_bundles (bundle_name, status) VALUES (?, ?)",
            ("Doc 2", "completed"),
        )
        bundle_id2 = cursor.lastrowid
        db.connection.execute(
            "INSERT INTO pdf_files (pdf_path, pdf_filename, bundle_id, page_count, generation_status) VALUES (?, ?, ?, ?, ?)",
            ("/out/doc2.pdf", "doc2.pdf", bundle_id2, 2, "completed"),
        )
        db.connection.commit()

        # Act
        stats = db.get_archived_statistics()

        # Assert - new keys from ArchivedMetadataRepository
        assert stats["total_pdfs"] == 2
        assert stats["total_pages"] == 3

    # ==================== Autocomplete / Distinct Values Tests ====================

    def test_get_unique_companies(self, db, temp_file):
        """Test getting unique company names"""
        # Arrange
        file_hash = MetadataDB.compute_file_hash(temp_file)

        # Register and add metadata for multiple files
        for i, company in enumerate(["Acme Corp", "Test Inc", "Acme Corp"]):
            temp_path = f"{temp_file}_{i}"
            with open(temp_path, "wb") as f:
                f.write(f"test{i}".encode())

            image_id = db.register_image_file(
                temp_path,
                file_hash,
                os.path.dirname(temp_path),
                os.path.basename(temp_path),
                100,
                0.0,
            )
            db.create_normalized_metadata(image_id, None, {"company": company})

            # Cleanup
            if os.path.exists(temp_path):
                os.remove(temp_path)

        # Act
        companies = db.get_unique_companies(use_cache=False)

        # Assert
        assert "Acme Corp" in companies
        assert "Test Inc" in companies
        assert len(companies) == 2  # Acme Corp should appear once

    def test_get_unique_titles(self, db, temp_file):
        """Test getting unique document types"""
        # Arrange
        file_hash = MetadataDB.compute_file_hash(temp_file)

        for i, doc_type in enumerate(["Invoice", "Receipt", "Invoice"]):
            temp_path = f"{temp_file}_{i}"
            with open(temp_path, "wb") as f:
                f.write(f"test{i}".encode())

            image_id = db.register_image_file(
                temp_path,
                file_hash,
                os.path.dirname(temp_path),
                os.path.basename(temp_path),
                100,
                0.0,
            )
            db.create_normalized_metadata(image_id, None, {"document_type": doc_type})

            if os.path.exists(temp_path):
                os.remove(temp_path)

        # Act
        titles = db.get_unique_titles(use_cache=False)

        # Assert
        assert "Invoice" in titles
        assert "Receipt" in titles
        assert len(titles) == 2

    def test_get_unique_categories(self, db, temp_file):
        """Test getting unique document categories"""
        # Arrange
        file_hash = MetadataDB.compute_file_hash(temp_file)
        temp_files = []

        for i, category in enumerate(["Tax Documents", "Receipts", "Tax Documents"]):
            temp_path = f"{temp_file}_{i}"
            with open(temp_path, "wb") as f:
                f.write(f"test{i}".encode())
            temp_files.append(temp_path)

            image_id = db.register_image_file(
                temp_path,
                file_hash,
                os.path.dirname(temp_path),
                os.path.basename(temp_path),
                100,
                0.0,
            )
            db.create_normalized_metadata(image_id, None, {"document_category": category})

        # Act
        categories = db.get_unique_categories()

        # Cleanup
        for temp_path in temp_files:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        # Assert
        assert "Tax Documents" in categories
        assert "Receipts" in categories
        assert len(categories) == 2

    def test_invalidate_field_history_cache(self, db):
        """Test cache invalidation"""
        # Arrange - This should set cache
        db.get_unique_companies(use_cache=True)

        # Act
        db.invalidate_field_history_cache()

        # Assert - Just verify it doesn't error
        # Cache should be cleared, next call will rebuild
        companies = db.get_unique_companies(use_cache=True)
        assert isinstance(companies, list)

    # ==================== Context Manager / Cleanup Tests ====================

    def test_close_closes_connection(self, temp_db_path):
        # Arrange
        db = MetadataDB(temp_db_path)

        # Act
        db.close()

        # Assert - connection should be closed
        assert db.connection.connection is None

    def test_context_manager(self, temp_db_path):
        # Act & Assert
        with MetadataDB(temp_db_path) as db:
            assert db.connection is not None

    def test_get_schema_version(self, db):
        # Act
        version = db.get_schema_version()

        # Assert
        assert version > 0  # Should have a version number
        assert isinstance(version, int)
