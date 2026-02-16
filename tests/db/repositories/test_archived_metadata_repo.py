"""Tests for ArchivedMetadataRepository"""

import tempfile

import pytest

from db.connection import DatabaseConnection
from db.repositories.archived_metadata_repo import ArchivedMetadataRepository
from db.schema import create_all_tables


@pytest.fixture
def db_conn(tmp_path):
    """Create a temporary database connection for testing."""
    db_path = tmp_path / "test_archived.db"
    conn = DatabaseConnection(str(db_path))
    create_all_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def repo(db_conn):
    """Create an ArchivedMetadataRepository instance for testing."""
    return ArchivedMetadataRepository(db_conn)


@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"test image data")
        file_path = f.name
    yield file_path
    import os

    if os.path.exists(file_path):
        os.remove(file_path)


class TestArchivedMetadataRepositoryBasics:
    """Test basic repository initialization."""

    def test_repository_initialization(self, repo, db_conn):
        """Test that repository initializes with correct connection."""
        assert repo.conn == db_conn
        assert repo.conn.connection is not None


class TestArchiveDocument:
    """Test archive_document() method."""

    def test_archive_document_creates_pdf_record(self, repo, temp_file, db_conn):
        """Test archiving a document creates PDF record."""
        import hashlib
        import os

        # Register the image file first
        file_hash = hashlib.sha256(b"test image data").hexdigest()
        file_size = os.path.getsize(temp_file)
        file_mtime = os.path.getmtime(temp_file)
        directory_path = os.path.dirname(temp_file)
        filename = os.path.basename(temp_file)

        db_conn.execute(
            """
            INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (temp_file, file_hash, directory_path, filename, file_size, file_mtime),
        )
        db_conn.commit()

        # Archive the document
        pdf_path = "/output/test_doc.pdf"
        document_metadata = {"title": "Test Document", "company": "Test Corp"}

        repo.archive_document(pdf_path, [temp_file], document_metadata)

        # Verify PDF record was created
        cursor = db_conn.connection.cursor()
        cursor.execute(
            "SELECT pdf_path, pdf_filename, page_count FROM pdf_files WHERE pdf_path = ?",
            (pdf_path,),
        )
        record = cursor.fetchone()

        assert record is not None
        assert record[0] == pdf_path
        assert record[1] == "test_doc.pdf"
        assert record[2] == 1  # One source file

    def test_archive_document_creates_bundle(self, repo, temp_file, db_conn):
        """Test that archive_document creates a bundle."""
        import hashlib
        import os

        # Register image file
        file_hash = hashlib.sha256(b"test image data").hexdigest()
        file_size = os.path.getsize(temp_file)
        file_mtime = os.path.getmtime(temp_file)
        directory_path = os.path.dirname(temp_file)
        filename = os.path.basename(temp_file)

        db_conn.execute(
            """
            INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (temp_file, file_hash, directory_path, filename, file_size, file_mtime),
        )
        db_conn.commit()

        # Archive document
        pdf_path = "/output/invoice.pdf"
        document_metadata = {"title": "Invoice 2024"}

        repo.archive_document(pdf_path, [temp_file], document_metadata)

        # Verify bundle was created
        cursor = db_conn.connection.cursor()
        cursor.execute("SELECT bundle_name, status FROM document_bundles")
        bundle = cursor.fetchone()

        assert bundle is not None
        assert bundle[0] == "Invoice 2024"  # Uses title from metadata
        assert bundle[1] == "completed"

    def test_archive_document_uses_filename_when_no_title(self, repo, temp_file, db_conn):
        """Test archive_document uses PDF filename when no title provided."""
        import hashlib
        import os

        # Register image file
        file_hash = hashlib.sha256(b"test image data").hexdigest()
        file_size = os.path.getsize(temp_file)
        file_mtime = os.path.getmtime(temp_file)
        directory_path = os.path.dirname(temp_file)
        filename = os.path.basename(temp_file)

        db_conn.execute(
            """
            INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (temp_file, file_hash, directory_path, filename, file_size, file_mtime),
        )
        db_conn.commit()

        # Archive without title
        pdf_path = "/output/report.pdf"
        document_metadata = {}

        repo.archive_document(pdf_path, [temp_file], document_metadata)

        # Verify bundle name is PDF filename
        cursor = db_conn.connection.cursor()
        cursor.execute("SELECT bundle_name FROM document_bundles")
        bundle_name = cursor.fetchone()[0]

        assert bundle_name == "report.pdf"

    def test_archive_document_links_source_images_to_bundle(self, repo, temp_file, db_conn):
        """Test that source images are linked to bundle."""
        import hashlib
        import os

        # Register image file
        file_hash = hashlib.sha256(b"test image data").hexdigest()
        file_size = os.path.getsize(temp_file)
        file_mtime = os.path.getmtime(temp_file)
        directory_path = os.path.dirname(temp_file)
        filename = os.path.basename(temp_file)

        db_conn.execute(
            """
            INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (temp_file, file_hash, directory_path, filename, file_size, file_mtime),
        )
        db_conn.commit()

        # Archive document
        pdf_path = "/output/doc.pdf"
        document_metadata = {"title": "Document"}

        repo.archive_document(pdf_path, [temp_file], document_metadata)

        # Verify bundle_images link was created
        cursor = db_conn.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM bundle_images")
        count = cursor.fetchone()[0]

        assert count == 1

    def test_archive_document_on_conflict_updates(self, repo, temp_file, db_conn):
        """Test archiving same PDF path twice updates existing record."""
        import hashlib
        import os

        # Register image file
        file_hash = hashlib.sha256(b"test image data").hexdigest()
        file_size = os.path.getsize(temp_file)
        file_mtime = os.path.getmtime(temp_file)
        directory_path = os.path.dirname(temp_file)
        filename = os.path.basename(temp_file)

        db_conn.execute(
            """
            INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (temp_file, file_hash, directory_path, filename, file_size, file_mtime),
        )
        db_conn.commit()

        # Archive first time
        pdf_path = "/output/test.pdf"
        repo.archive_document(pdf_path, [temp_file], {"title": "First"})

        # Archive again (should update)
        repo.archive_document(pdf_path, [temp_file], {"title": "Second"})

        # Verify only one PDF record exists
        cursor = db_conn.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM pdf_files WHERE pdf_path = ?", (pdf_path,))
        count = cursor.fetchone()[0]

        assert count == 1

    def test_archive_document_raises_error_if_bundle_creation_fails(
        self, repo, temp_file, db_conn, monkeypatch
    ):
        """Test that archive_document raises RuntimeError if bundle creation fails."""

        # Mock fetch_one to return None (simulating bundle creation failure)
        def mock_fetch_one(*args):
            return None

        monkeypatch.setattr(db_conn, "fetch_one", mock_fetch_one)

        with pytest.raises(RuntimeError) as exc_info:
            repo.archive_document("/output/test.pdf", [temp_file], {})

        assert "Failed to create bundle" in str(exc_info.value)


class TestGetArchivedDocument:
    """Test get_archived_document() method."""

    def test_get_archived_document_returns_pdf_info(self, repo, temp_file, db_conn):
        """Test retrieving archived document."""
        import hashlib
        import os

        # Register image file
        file_hash = hashlib.sha256(b"test image data").hexdigest()
        file_size = os.path.getsize(temp_file)
        file_mtime = os.path.getmtime(temp_file)
        directory_path = os.path.dirname(temp_file)
        filename = os.path.basename(temp_file)

        db_conn.execute(
            """
            INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (temp_file, file_hash, directory_path, filename, file_size, file_mtime),
        )
        db_conn.commit()

        # Archive document
        pdf_path = "/output/test.pdf"
        document_metadata = {"title": "Test Document", "company": "Test Corp"}
        repo.archive_document(pdf_path, [temp_file], document_metadata)

        # Retrieve archived document
        result = repo.get_archived_document(pdf_path)

        assert result is not None
        assert result["pdf_path"] == pdf_path
        assert result["pdf_filename"] == "test.pdf"
        assert result["page_count"] == 1
        assert result["bundle_name"] == "Test Document"

    def test_get_archived_document_includes_metadata(self, repo, temp_file, db_conn):
        """Test that get_archived_document includes metadata from source images."""
        import hashlib
        import os

        # Register image file
        file_hash = hashlib.sha256(b"test image data").hexdigest()
        file_size = os.path.getsize(temp_file)
        file_mtime = os.path.getmtime(temp_file)
        directory_path = os.path.dirname(temp_file)
        filename = os.path.basename(temp_file)

        db_conn.execute(
            """
            INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (temp_file, file_hash, directory_path, filename, file_size, file_mtime),
        )
        image_file_id = db_conn.fetch_one("SELECT last_insert_rowid()")[0]

        # Add metadata for the image
        db_conn.execute(
            """
            INSERT INTO metadata (image_file_id, company, document_type)
            VALUES (?, ?, ?)
        """,
            (image_file_id, "Acme Corp", "Invoice"),
        )
        db_conn.commit()

        # Archive document
        pdf_path = "/output/invoice.pdf"
        repo.archive_document(pdf_path, [temp_file], {"title": "Invoice"})

        # Retrieve and verify metadata is included
        result = repo.get_archived_document(pdf_path)

        assert result is not None
        assert result["company"] == "Acme Corp"
        assert result["document_type"] == "Invoice"

    def test_get_archived_document_returns_none_when_not_found(self, repo):
        """Test get_archived_document returns None for non-existent PDF."""
        result = repo.get_archived_document("/nonexistent/file.pdf")

        assert result is None


class TestGetStatistics:
    """Test get_statistics() method."""

    def test_get_statistics_returns_counts(self, repo, temp_file, db_conn):
        """Test getting archived document statistics."""
        import hashlib
        import os

        # Register image file
        file_hash = hashlib.sha256(b"test image data").hexdigest()
        file_size = os.path.getsize(temp_file)
        file_mtime = os.path.getmtime(temp_file)
        directory_path = os.path.dirname(temp_file)
        filename = os.path.basename(temp_file)

        db_conn.execute(
            """
            INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (temp_file, file_hash, directory_path, filename, file_size, file_mtime),
        )
        db_conn.commit()

        # Archive 2 documents
        repo.archive_document("/output/doc1.pdf", [temp_file], {"title": "Doc 1"})
        repo.archive_document("/output/doc2.pdf", [temp_file], {"title": "Doc 2"})

        # Get statistics
        stats = repo.get_statistics()

        assert stats["total_pdfs"] == 2
        assert stats["total_pages"] == 2  # 1 page each

    def test_get_statistics_returns_zero_when_empty(self, repo):
        """Test get_statistics returns zero when no archived documents."""
        stats = repo.get_statistics()

        assert stats["total_pdfs"] == 0
        assert stats["total_pages"] == 0


class TestIntegration:
    """Test integration scenarios."""

    def test_archive_and_retrieve_workflow(self, repo, temp_file, db_conn):
        """Test complete archive and retrieve workflow."""
        import hashlib
        import os

        # Register image file
        file_hash = hashlib.sha256(b"test image data").hexdigest()
        file_size = os.path.getsize(temp_file)
        file_mtime = os.path.getmtime(temp_file)
        directory_path = os.path.dirname(temp_file)
        filename = os.path.basename(temp_file)

        db_conn.execute(
            """
            INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (temp_file, file_hash, directory_path, filename, file_size, file_mtime),
        )
        db_conn.commit()

        # Archive
        pdf_path = "/output/complete_doc.pdf"
        metadata = {"title": "Complete Document", "company": "Test Company"}
        repo.archive_document(pdf_path, [temp_file], metadata)

        # Retrieve
        result = repo.get_archived_document(pdf_path)

        assert result is not None
        assert result["pdf_path"] == pdf_path
        assert result["bundle_name"] == "Complete Document"

        # Check statistics
        stats = repo.get_statistics()
        assert stats["total_pdfs"] == 1
