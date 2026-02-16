"""Tests for PdfImagePagesRepository"""

import sqlite3
from datetime import datetime
from unittest.mock import patch

import pytest

from db.connection import DatabaseConnection
from db.repositories.pdf_image_pages_repo import PdfImagePagesRepository
from db.schema import create_all_tables


@pytest.fixture
def db_conn(tmp_path):
    """Create a temporary database connection for testing."""
    db_path = tmp_path / "test_pdf_image_pages.db"
    conn = DatabaseConnection(str(db_path))
    create_all_tables(conn)
    # Enable foreign key constraints
    conn.connection.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def repo(db_conn):
    """Create a PdfImagePagesRepository instance for testing."""
    return PdfImagePagesRepository(db_conn)


@pytest.fixture
def sample_pdf_id(db_conn):
    """Create a sample PDF and return its ID."""
    cursor = db_conn.connection.cursor()

    # Create bundle first
    cursor.execute(
        "INSERT INTO document_bundles (bundle_name, status) VALUES (?, ?)",
        ("Test Bundle", "suggested"),
    )
    bundle_id = cursor.lastrowid

    # Create PDF
    cursor.execute(
        """
        INSERT INTO pdf_files (pdf_path, pdf_filename, bundle_id, page_count, generation_status)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("/test/output.pdf", "output.pdf", bundle_id, 3, "completed"),
    )
    pdf_id = cursor.lastrowid
    db_conn.connection.commit()
    return pdf_id


@pytest.fixture
def sample_image_ids(db_conn):
    """Create sample image files and return their IDs."""
    cursor = db_conn.connection.cursor()
    image_ids = []

    for i in range(3):
        cursor.execute(
            """
            INSERT INTO image_files (
                file_path, file_hash, directory_path, filename,
                file_size, file_mtime, discovered_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"/test/page{i}.png",
                f"hash{i}",
                "/test",
                f"page{i}.png",
                1024 * (i + 1),
                1234567890.0 + i,
                datetime.now().isoformat(),
            ),
        )
        image_ids.append(cursor.lastrowid)

    db_conn.connection.commit()
    return image_ids


class TestPdfImagePagesRepositoryBasics:
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


class TestAddPage:
    """Test add_page() method for adding images to PDF pages."""

    def test_add_page_creates_mapping(self, repo, sample_pdf_id, sample_image_ids):
        """Test adding an image to a PDF page."""
        record_id = repo.add_page(
            pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[0], page_number=1
        )

        assert record_id > 0

        # Verify record was created
        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT * FROM pdf_image_pages WHERE id = ?", (record_id,))
        record = cursor.fetchone()

        assert record is not None
        assert record[1] == sample_pdf_id  # pdf_file_id
        assert record[2] == sample_image_ids[0]  # image_file_id
        assert record[3] == 1  # page_number

    def test_add_page_multiple_pages(self, repo, sample_pdf_id, sample_image_ids):
        """Test adding multiple images to different pages."""
        id1 = repo.add_page(
            pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[0], page_number=1
        )
        id2 = repo.add_page(
            pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[1], page_number=2
        )
        id3 = repo.add_page(
            pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[2], page_number=3
        )

        assert id1 > 0
        assert id2 > 0
        assert id3 > 0
        assert id1 != id2 != id3

    def test_add_page_handles_operational_error(self, repo, sample_pdf_id, sample_image_ids):
        """Test add_page handles OperationalError."""
        with patch.object(
            repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
        ), pytest.raises(sqlite3.OperationalError, match="Database is locked"):
            repo.add_page(
                pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[0], page_number=1
            )

    def test_add_page_handles_generic_error(self, repo, sample_pdf_id, sample_image_ids):
        """Test add_page handles generic sqlite3.Error."""
        with patch.object(repo.conn, "commit", side_effect=sqlite3.Error("Generic database error")):
            with pytest.raises(sqlite3.Error, match="Failed to add page to PDF"):
                repo.add_page(
                    pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[0], page_number=1
                )


class TestGetImagesForPdf:
    """Test get_images_for_pdf() retrieval method."""

    def test_get_images_for_pdf_returns_ordered_list(self, repo, sample_pdf_id, sample_image_ids):
        """Test retrieving images for a PDF ordered by page number."""
        # Add pages in non-sequential order
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[2], page_number=3)
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[0], page_number=1)
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[1], page_number=2)

        images = repo.get_images_for_pdf(sample_pdf_id)

        assert len(images) == 3
        # Should be ordered by page_number
        assert images[0]["page_number"] == 1
        assert images[1]["page_number"] == 2
        assert images[2]["page_number"] == 3
        # Verify file paths match expected order
        assert images[0]["file_path"] == "/test/page0.png"
        assert images[1]["file_path"] == "/test/page1.png"
        assert images[2]["file_path"] == "/test/page2.png"

    def test_get_images_for_pdf_returns_empty_for_no_pages(self, repo, sample_pdf_id):
        """Test retrieving images for PDF with no pages."""
        images = repo.get_images_for_pdf(sample_pdf_id)
        assert images == []

    def test_get_images_for_pdf_returns_empty_for_nonexistent_pdf(self, repo):
        """Test retrieving images for non-existent PDF."""
        images = repo.get_images_for_pdf(99999)
        assert images == []

    def test_get_images_for_pdf_includes_image_file_details(
        self, repo, sample_pdf_id, sample_image_ids
    ):
        """Test that get_images_for_pdf includes full image file details via JOIN."""
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[0], page_number=1)

        images = repo.get_images_for_pdf(sample_pdf_id)

        assert len(images) == 1
        # Should include fields from image_files table
        assert "file_path" in images[0]
        assert "file_hash" in images[0]
        assert images[0]["file_path"] == "/test/page0.png"


class TestGetPdfsForImage:
    """Test get_pdfs_for_image() retrieval method."""

    def test_get_pdfs_for_image_returns_pdfs(self, repo, db_conn, sample_image_ids):
        """Test retrieving all PDFs containing a specific image."""
        cursor = db_conn.connection.cursor()

        # Create bundle
        cursor.execute(
            "INSERT INTO document_bundles (bundle_name, status) VALUES (?, ?)",
            ("Bundle", "suggested"),
        )
        bundle_id = cursor.lastrowid

        # Create two PDFs
        cursor.execute(
            """
            INSERT INTO pdf_files (pdf_path, pdf_filename, bundle_id, page_count, generation_status)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("/test/pdf1.pdf", "pdf1.pdf", bundle_id, 1, "completed"),
        )
        pdf1_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO pdf_files (pdf_path, pdf_filename, bundle_id, page_count, generation_status)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("/test/pdf2.pdf", "pdf2.pdf", bundle_id, 1, "completed"),
        )
        pdf2_id = cursor.lastrowid
        db_conn.connection.commit()

        # Add same image to both PDFs
        repo.add_page(pdf_file_id=pdf1_id, image_file_id=sample_image_ids[0], page_number=1)
        repo.add_page(pdf_file_id=pdf2_id, image_file_id=sample_image_ids[0], page_number=1)

        pdfs = repo.get_pdfs_for_image(sample_image_ids[0])

        assert len(pdfs) == 2
        pdf_paths = [p["pdf_path"] for p in pdfs]
        assert "/test/pdf1.pdf" in pdf_paths
        assert "/test/pdf2.pdf" in pdf_paths

    def test_get_pdfs_for_image_returns_empty_for_no_pdfs(self, repo, sample_image_ids):
        """Test retrieving PDFs for image not in any PDF."""
        pdfs = repo.get_pdfs_for_image(sample_image_ids[0])
        assert pdfs == []

    def test_get_pdfs_for_image_returns_empty_for_nonexistent_image(self, repo):
        """Test retrieving PDFs for non-existent image."""
        pdfs = repo.get_pdfs_for_image(99999)
        assert pdfs == []


class TestRemovePage:
    """Test remove_page() method for removing pages."""

    def test_remove_page_removes_mapping(self, repo, sample_pdf_id, sample_image_ids):
        """Test removing a specific page from a PDF."""
        # Add three pages
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[0], page_number=1)
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[1], page_number=2)
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[2], page_number=3)

        # Remove middle page
        repo.remove_page(pdf_file_id=sample_pdf_id, page_number=2)

        # Verify only 2 pages remain
        images = repo.get_images_for_pdf(sample_pdf_id)
        assert len(images) == 2
        page_numbers = [img["page_number"] for img in images]
        assert 1 in page_numbers
        assert 2 not in page_numbers
        assert 3 in page_numbers

    def test_remove_page_handles_nonexistent_page(self, repo, sample_pdf_id):
        """Test removing page that doesn't exist (should not error)."""
        # Should not raise error
        repo.remove_page(pdf_file_id=sample_pdf_id, page_number=99)

    def test_remove_page_handles_operational_error(self, repo, sample_pdf_id, sample_image_ids):
        """Test remove_page handles OperationalError."""
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[0], page_number=1)

        with patch.object(
            repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
        ), pytest.raises(sqlite3.OperationalError, match="Database is locked"):
            repo.remove_page(pdf_file_id=sample_pdf_id, page_number=1)

    def test_remove_page_handles_generic_error(self, repo, sample_pdf_id, sample_image_ids):
        """Test remove_page handles generic sqlite3.Error."""
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[0], page_number=1)

        with patch.object(repo.conn, "commit", side_effect=sqlite3.Error("Generic database error")):
            with pytest.raises(sqlite3.Error, match="Failed to remove page from PDF"):
                repo.remove_page(pdf_file_id=sample_pdf_id, page_number=1)


class TestRemoveAllPages:
    """Test remove_all_pages() method for clearing PDF."""

    def test_remove_all_pages_clears_pdf(self, repo, sample_pdf_id, sample_image_ids):
        """Test removing all pages from a PDF."""
        # Add pages
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[0], page_number=1)
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[1], page_number=2)
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[2], page_number=3)

        # Remove all
        repo.remove_all_pages(sample_pdf_id)

        # Verify PDF is empty
        images = repo.get_images_for_pdf(sample_pdf_id)
        assert len(images) == 0

    def test_remove_all_pages_on_empty_pdf(self, repo, sample_pdf_id):
        """Test removing all pages from already empty PDF (should not error)."""
        # Should not raise error
        repo.remove_all_pages(sample_pdf_id)

        images = repo.get_images_for_pdf(sample_pdf_id)
        assert len(images) == 0

    def test_remove_all_pages_handles_operational_error(
        self, repo, sample_pdf_id, sample_image_ids
    ):
        """Test remove_all_pages handles OperationalError."""
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[0], page_number=1)

        with patch.object(
            repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
        ), pytest.raises(sqlite3.OperationalError, match="Database is locked"):
            repo.remove_all_pages(sample_pdf_id)

    def test_remove_all_pages_handles_generic_error(self, repo, sample_pdf_id, sample_image_ids):
        """Test remove_all_pages handles generic sqlite3.Error."""
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[0], page_number=1)

        with patch.object(repo.conn, "commit", side_effect=sqlite3.Error("Generic database error")):
            with pytest.raises(sqlite3.Error, match="Failed to remove all pages from PDF"):
                repo.remove_all_pages(sample_pdf_id)


class TestGetPageCount:
    """Test get_page_count() method for counting pages."""

    def test_get_page_count_returns_correct_count(self, repo, sample_pdf_id, sample_image_ids):
        """Test counting pages in a PDF."""
        # Initially 0
        assert repo.get_page_count(sample_pdf_id) == 0

        # Add pages
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[0], page_number=1)
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[1], page_number=2)
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[2], page_number=3)

        # Should be 3
        assert repo.get_page_count(sample_pdf_id) == 3

    def test_get_page_count_after_removal(self, repo, sample_pdf_id, sample_image_ids):
        """Test count after removing pages."""
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[0], page_number=1)
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[1], page_number=2)
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[2], page_number=3)
        assert repo.get_page_count(sample_pdf_id) == 3

        # Remove one
        repo.remove_page(sample_pdf_id, 2)
        assert repo.get_page_count(sample_pdf_id) == 2

        # Remove all
        repo.remove_all_pages(sample_pdf_id)
        assert repo.get_page_count(sample_pdf_id) == 0

    def test_get_page_count_for_nonexistent_pdf(self, repo):
        """Test count for non-existent PDF."""
        assert repo.get_page_count(99999) == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_add_page_enforces_unique_page_number_constraint(
        self, repo, sample_pdf_id, sample_image_ids
    ):
        """Test that same page number can't be used twice in same PDF."""
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[0], page_number=1)

        # Attempting to add different image to same page number should fail
        with pytest.raises(sqlite3.IntegrityError):
            repo.add_page(
                pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[1], page_number=1
            )

    def test_cascade_delete_on_pdf_deletion(self, repo, db_conn, sample_pdf_id, sample_image_ids):
        """Test that deleting a PDF cascades to pdf_image_pages."""
        # Add pages to PDF
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[0], page_number=1)
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[1], page_number=2)

        # Verify pages exist
        assert repo.get_page_count(sample_pdf_id) == 2

        # Delete the PDF
        cursor = db_conn.connection.cursor()
        cursor.execute("DELETE FROM pdf_files WHERE id = ?", (sample_pdf_id,))
        db_conn.connection.commit()

        # Verify pdf_image_pages records were cascade deleted
        cursor.execute(
            "SELECT COUNT(*) FROM pdf_image_pages WHERE pdf_file_id = ?", (sample_pdf_id,)
        )
        count = cursor.fetchone()[0]
        assert count == 0

    def test_cascade_delete_on_image_file_deletion(
        self, repo, db_conn, sample_pdf_id, sample_image_ids
    ):
        """Test that deleting an image file cascades to pdf_image_pages."""
        # Add pages
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[0], page_number=1)
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[1], page_number=2)
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[2], page_number=3)

        # Verify pages exist
        assert repo.get_page_count(sample_pdf_id) == 3

        # Delete one image file
        cursor = db_conn.connection.cursor()
        cursor.execute("DELETE FROM image_files WHERE id = ?", (sample_image_ids[0],))
        db_conn.connection.commit()

        # Verify corresponding pdf_image_pages record was cascade deleted
        assert repo.get_page_count(sample_pdf_id) == 2

    def test_add_page_with_non_sequential_page_numbers(self, repo, sample_pdf_id, sample_image_ids):
        """Test adding pages with non-sequential page numbers (gaps allowed)."""
        # Add pages 1, 5, 10 (skipping 2, 3, 4, 6-9)
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[0], page_number=1)
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[1], page_number=5)
        repo.add_page(pdf_file_id=sample_pdf_id, image_file_id=sample_image_ids[2], page_number=10)

        images = repo.get_images_for_pdf(sample_pdf_id)
        assert len(images) == 3
        assert images[0]["page_number"] == 1
        assert images[1]["page_number"] == 5
        assert images[2]["page_number"] == 10
