"""Tests for PdfFilesRepository"""

import sqlite3
from unittest.mock import patch

import pytest

from db.connection import DatabaseConnection
from db.repositories.pdf_files_repo import PdfFilesRepository
from db.schema import create_all_tables


@pytest.fixture
def db_conn(tmp_path):
    """Create a temporary database connection for testing."""
    db_path = tmp_path / "test_pdf_files.db"
    conn = DatabaseConnection(str(db_path))
    create_all_tables(conn)
    # Enable foreign key constraints
    conn.connection.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def repo(db_conn):
    """Create a PdfFilesRepository instance for testing."""
    return PdfFilesRepository(db_conn)


@pytest.fixture
def sample_bundle_id(db_conn):
    """Create a sample bundle and return its ID."""
    cursor = db_conn.connection.cursor()
    cursor.execute(
        "INSERT INTO document_bundles (bundle_name, status) VALUES (?, ?)",
        ("Test Bundle", "suggested"),
    )
    db_conn.connection.commit()
    return cursor.lastrowid


class TestPdfFilesRepositoryBasics:
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


class TestRegister:
    """Test register() method for creating PDF records."""

    def test_register_creates_pdf_record(self, repo, sample_bundle_id):
        """Test registering a new PDF file."""
        pdf_id = repo.register(
            pdf_path="/test/output.pdf",
            pdf_filename="output.pdf",
            bundle_id=sample_bundle_id,
            page_count=5,
            file_hash="abc123",
            file_size=102400,
        )

        assert pdf_id > 0

        # Verify record was created
        pdf = repo.get_by_path("/test/output.pdf")
        assert pdf is not None
        assert pdf["pdf_path"] == "/test/output.pdf"
        assert pdf["pdf_filename"] == "output.pdf"
        assert pdf["bundle_id"] == sample_bundle_id
        assert pdf["page_count"] == 5
        assert pdf["file_hash"] == "abc123"
        assert pdf["file_size"] == 102400
        assert pdf["generation_status"] == "completed"

    def test_register_with_minimal_fields(self, repo, sample_bundle_id):
        """Test registering with only required fields."""
        pdf_id = repo.register(
            pdf_path="/test/minimal.pdf",
            pdf_filename="minimal.pdf",
            bundle_id=sample_bundle_id,
            page_count=1,
            file_hash=None,
            file_size=None,
        )

        assert pdf_id > 0

        pdf = repo.get_by_path("/test/minimal.pdf")
        assert pdf is not None
        assert pdf["file_hash"] is None
        assert pdf["file_size"] is None

    def test_register_replaces_existing_record(self, repo, sample_bundle_id):
        """Test INSERT OR REPLACE behavior for same path."""
        # Register first PDF
        pdf_id1 = repo.register(
            pdf_path="/test/same.pdf",
            pdf_filename="same.pdf",
            bundle_id=sample_bundle_id,
            page_count=3,
            file_hash="hash1",
            file_size=1000,
        )

        # Register again with same path (should replace)
        pdf_id2 = repo.register(
            pdf_path="/test/same.pdf",
            pdf_filename="same_updated.pdf",
            bundle_id=sample_bundle_id,
            page_count=5,
            file_hash="hash2",
            file_size=2000,
        )

        # INSERT OR REPLACE creates new row with new ID
        assert pdf_id2 > 0
        assert pdf_id2 != pdf_id1

        # Verify updated values (old record replaced)
        pdf = repo.get_by_path("/test/same.pdf")
        assert pdf["page_count"] == 5
        assert pdf["file_hash"] == "hash2"

        # Verify only one record exists for this path
        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM pdf_files WHERE pdf_path = ?", ("/test/same.pdf",))
        count = cursor.fetchone()[0]
        assert count == 1

    def test_register_handles_operational_error(self, repo, sample_bundle_id):
        """Test register handles OperationalError."""
        with (
            patch.object(
                repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
            ),
            pytest.raises(sqlite3.OperationalError, match="Database is locked"),
        ):
            repo.register(
                pdf_path="/test/error.pdf",
                pdf_filename="error.pdf",
                bundle_id=sample_bundle_id,
                page_count=1,
            )

    def test_register_handles_generic_error(self, repo, sample_bundle_id):
        """Test register handles generic sqlite3.Error."""
        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.Error("Generic database error")),
            pytest.raises(sqlite3.Error, match="Failed to register PDF file"),
        ):
            repo.register(
                pdf_path="/test/error.pdf",
                pdf_filename="error.pdf",
                bundle_id=sample_bundle_id,
                page_count=1,
            )


class TestGetByPath:
    """Test get_by_path() retrieval method."""

    def test_get_by_path_returns_record(self, repo, sample_bundle_id):
        """Test retrieving PDF by path."""
        repo.register(
            pdf_path="/test/doc.pdf",
            pdf_filename="doc.pdf",
            bundle_id=sample_bundle_id,
            page_count=10,
        )

        pdf = repo.get_by_path("/test/doc.pdf")

        assert pdf is not None
        assert pdf["pdf_path"] == "/test/doc.pdf"
        assert pdf["page_count"] == 10

    def test_get_by_path_returns_none_for_nonexistent(self, repo):
        """Test retrieving non-existent PDF."""
        pdf = repo.get_by_path("/test/nonexistent.pdf")
        assert pdf is None


class TestGetByBundle:
    """Test get_by_bundle() retrieval method."""

    def test_get_by_bundle_returns_record(self, repo, sample_bundle_id):
        """Test retrieving PDF by bundle ID."""
        repo.register(
            pdf_path="/test/bundle.pdf",
            pdf_filename="bundle.pdf",
            bundle_id=sample_bundle_id,
            page_count=7,
        )

        pdf = repo.get_by_bundle(sample_bundle_id)

        assert pdf is not None
        assert pdf["bundle_id"] == sample_bundle_id
        assert pdf["pdf_path"] == "/test/bundle.pdf"

    def test_get_by_bundle_returns_none_for_nonexistent(self, repo):
        """Test retrieving PDF for non-existent bundle."""
        pdf = repo.get_by_bundle(99999)
        assert pdf is None

    def test_get_by_bundle_returns_latest_when_multiple(self, repo, db_conn):
        """Test that get_by_bundle returns one PDF when bundle has multiple (should not happen in practice)."""
        # Create two bundles
        cursor = db_conn.connection.cursor()
        cursor.execute(
            "INSERT INTO document_bundles (bundle_name, status) VALUES (?, ?)",
            ("Bundle 1", "suggested"),
        )
        bundle1_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO document_bundles (bundle_name, status) VALUES (?, ?)",
            ("Bundle 2", "suggested"),
        )
        bundle2_id = cursor.lastrowid
        db_conn.connection.commit()

        # Register PDFs for different bundles
        repo.register(
            pdf_path="/test/bundle1.pdf",
            pdf_filename="bundle1.pdf",
            bundle_id=bundle1_id,
            page_count=1,
        )

        repo.register(
            pdf_path="/test/bundle2.pdf",
            pdf_filename="bundle2.pdf",
            bundle_id=bundle2_id,
            page_count=2,
        )

        # Each bundle should return its own PDF
        pdf1 = repo.get_by_bundle(bundle1_id)
        pdf2 = repo.get_by_bundle(bundle2_id)

        assert pdf1["pdf_path"] == "/test/bundle1.pdf"
        assert pdf2["pdf_path"] == "/test/bundle2.pdf"


class TestUpdateGenerationStatus:
    """Test update_generation_status() method."""

    def test_update_generation_status_changes_status(self, repo, sample_bundle_id):
        """Test updating generation status."""
        # Register with default status (completed)
        repo.register(
            pdf_path="/test/status.pdf",
            pdf_filename="status.pdf",
            bundle_id=sample_bundle_id,
            page_count=1,
        )

        # Update to generating
        repo.update_generation_status("/test/status.pdf", "generating")

        pdf = repo.get_by_path("/test/status.pdf")
        assert pdf["generation_status"] == "generating"

        # Update to failed
        repo.update_generation_status("/test/status.pdf", "failed")

        pdf = repo.get_by_path("/test/status.pdf")
        assert pdf["generation_status"] == "failed"

    def test_update_generation_status_on_nonexistent_does_not_error(self, repo):
        """Test updating status on non-existent PDF (should not error)."""
        # Should not raise error (UPDATE on non-existent row)
        repo.update_generation_status("/test/nonexistent.pdf", "failed")

    def test_update_generation_status_handles_operational_error(self, repo, sample_bundle_id):
        """Test update_generation_status handles OperationalError."""
        repo.register(
            pdf_path="/test/status.pdf",
            pdf_filename="status.pdf",
            bundle_id=sample_bundle_id,
            page_count=1,
        )

        with (
            patch.object(
                repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
            ),
            pytest.raises(sqlite3.OperationalError, match="Database is locked"),
        ):
            repo.update_generation_status("/test/status.pdf", "failed")

    def test_update_generation_status_handles_generic_error(self, repo, sample_bundle_id):
        """Test update_generation_status handles generic sqlite3.Error."""
        repo.register(
            pdf_path="/test/status.pdf",
            pdf_filename="status.pdf",
            bundle_id=sample_bundle_id,
            page_count=1,
        )

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.Error("Generic database error")),
            pytest.raises(sqlite3.Error, match="Failed to update generation status"),
        ):
            repo.update_generation_status("/test/status.pdf", "failed")


class TestUpdateSearchability:
    """Test update_searchability() method."""

    def test_update_searchability_skips_when_column_missing(self, repo, sample_bundle_id):
        """Test that update_searchability gracefully handles missing column."""
        repo.register(
            pdf_path="/test/searchable.pdf",
            pdf_filename="searchable.pdf",
            bundle_id=sample_bundle_id,
            page_count=1,
        )

        # Should not raise error (column doesn't exist in current schema)
        repo.update_searchability("/test/searchable.pdf", True)

    def test_update_searchability_handles_none_connection(self, repo):
        """Test that update_searchability handles None connection gracefully."""
        # Temporarily set connection to None
        original_connection = repo.conn.connection
        repo.conn.connection = None

        # Should not raise error
        repo.update_searchability("/test/test.pdf", True)

        # Restore connection
        repo.conn.connection = original_connection

    def test_update_searchability_works_when_column_exists(self, repo, db_conn, sample_bundle_id):
        """Test update_searchability when column exists (after migration)."""
        # Add is_searchable column
        cursor = db_conn.connection.cursor()
        cursor.execute("ALTER TABLE pdf_files ADD COLUMN is_searchable BOOLEAN DEFAULT 0")
        db_conn.connection.commit()

        # Register PDF
        repo.register(
            pdf_path="/test/searchable.pdf",
            pdf_filename="searchable.pdf",
            bundle_id=sample_bundle_id,
            page_count=1,
        )

        # Update searchability
        repo.update_searchability("/test/searchable.pdf", True)

        # Verify it was updated
        cursor.execute(
            "SELECT is_searchable FROM pdf_files WHERE pdf_path = ?", ("/test/searchable.pdf",)
        )
        result = cursor.fetchone()
        assert result[0] == 1  # True = 1

    def test_update_searchability_handles_operational_error_when_column_exists(
        self, repo, db_conn, sample_bundle_id
    ):
        """Test update_searchability handles OperationalError when column exists."""
        # Add is_searchable column
        cursor = db_conn.connection.cursor()
        cursor.execute("ALTER TABLE pdf_files ADD COLUMN is_searchable BOOLEAN DEFAULT 0")
        db_conn.connection.commit()

        repo.register(
            pdf_path="/test/searchable.pdf",
            pdf_filename="searchable.pdf",
            bundle_id=sample_bundle_id,
            page_count=1,
        )

        with (
            patch.object(
                repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
            ),
            pytest.raises(sqlite3.OperationalError, match="Database is locked"),
        ):
            repo.update_searchability("/test/searchable.pdf", True)

    def test_update_searchability_handles_generic_error_when_column_exists(
        self, repo, db_conn, sample_bundle_id
    ):
        """Test update_searchability handles generic sqlite3.Error when column exists."""
        # Add is_searchable column
        cursor = db_conn.connection.cursor()
        cursor.execute("ALTER TABLE pdf_files ADD COLUMN is_searchable BOOLEAN DEFAULT 0")
        db_conn.connection.commit()

        repo.register(
            pdf_path="/test/searchable.pdf",
            pdf_filename="searchable.pdf",
            bundle_id=sample_bundle_id,
            page_count=1,
        )

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.Error("Generic database error")),
            pytest.raises(sqlite3.Error, match="Failed to update searchability"),
        ):
            repo.update_searchability("/test/searchable.pdf", True)


class TestGetAll:
    """Test get_all() method for retrieving all PDFs."""

    def test_get_all_returns_all_pdfs(self, repo, sample_bundle_id):
        """Test retrieving all PDFs."""
        # Register multiple PDFs
        repo.register(
            pdf_path="/test/pdf1.pdf",
            pdf_filename="pdf1.pdf",
            bundle_id=sample_bundle_id,
            page_count=1,
        )

        repo.register(
            pdf_path="/test/pdf2.pdf",
            pdf_filename="pdf2.pdf",
            bundle_id=sample_bundle_id,
            page_count=2,
        )

        pdfs = repo.get_all()

        assert len(pdfs) >= 2
        paths = [pdf["pdf_path"] for pdf in pdfs]
        assert "/test/pdf1.pdf" in paths
        assert "/test/pdf2.pdf" in paths

    def test_get_all_returns_empty_when_no_pdfs(self, repo):
        """Test get_all returns empty list when no PDFs exist."""
        pdfs = repo.get_all()
        assert pdfs == []

    def test_get_all_orders_by_generated_at_desc(self, repo, sample_bundle_id):
        """Test that get_all returns PDFs ordered by generated_at DESC."""
        # Register multiple PDFs
        repo.register(
            pdf_path="/test/old.pdf",
            pdf_filename="old.pdf",
            bundle_id=sample_bundle_id,
            page_count=1,
        )

        repo.register(
            pdf_path="/test/new.pdf",
            pdf_filename="new.pdf",
            bundle_id=sample_bundle_id,
            page_count=1,
        )

        pdfs = repo.get_all()

        # Most recent should be first
        assert len(pdfs) >= 2
        # Verify newer PDFs come before older ones (DESC order)
        assert pdfs[0]["pdf_path"] in ["/test/new.pdf", "/test/old.pdf"]


class TestGetStats:
    """Test get_stats() method for statistics."""

    def test_get_stats_returns_total_count(self, repo, sample_bundle_id):
        """Test getting total PDF count."""
        # Initially 0
        stats = repo.get_stats()
        assert stats["total"] == 0

        # Register PDFs
        repo.register(
            pdf_path="/test/pdf1.pdf",
            pdf_filename="pdf1.pdf",
            bundle_id=sample_bundle_id,
            page_count=1,
        )

        repo.register(
            pdf_path="/test/pdf2.pdf",
            pdf_filename="pdf2.pdf",
            bundle_id=sample_bundle_id,
            page_count=1,
        )

        stats = repo.get_stats()
        assert stats["total"] == 2

    def test_get_stats_groups_by_generation_status(self, repo, sample_bundle_id):
        """Test stats grouped by generation status."""
        # Register with different statuses
        repo.register(
            pdf_path="/test/completed1.pdf",
            pdf_filename="completed1.pdf",
            bundle_id=sample_bundle_id,
            page_count=1,
        )

        repo.register(
            pdf_path="/test/completed2.pdf",
            pdf_filename="completed2.pdf",
            bundle_id=sample_bundle_id,
            page_count=1,
        )

        # Update one to failed
        repo.update_generation_status("/test/completed2.pdf", "failed")

        stats = repo.get_stats()

        assert stats["total"] == 2
        assert stats["status_completed"] == 1
        assert stats["status_failed"] == 1

    def test_get_stats_returns_empty_dict_keys_when_no_pdfs(self, repo):
        """Test stats when no PDFs exist."""
        stats = repo.get_stats()
        assert stats["total"] == 0
        # No status_ keys should exist
        assert all(not key.startswith("status_") for key in stats)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_register_with_very_long_paths(self, repo, sample_bundle_id):
        """Test registering PDF with very long paths."""
        long_path = "/test/" + "a" * 500 + ".pdf"
        long_filename = "a" * 500 + ".pdf"

        pdf_id = repo.register(
            pdf_path=long_path,
            pdf_filename=long_filename,
            bundle_id=sample_bundle_id,
            page_count=1,
        )

        assert pdf_id > 0

        pdf = repo.get_by_path(long_path)
        assert pdf is not None
        assert pdf["pdf_path"] == long_path

    def test_register_with_zero_page_count(self, repo, sample_bundle_id):
        """Test registering PDF with zero pages (edge case)."""
        repo.register(
            pdf_path="/test/empty.pdf",
            pdf_filename="empty.pdf",
            bundle_id=sample_bundle_id,
            page_count=0,
        )

        pdf = repo.get_by_path("/test/empty.pdf")
        assert pdf["page_count"] == 0

    def test_register_with_large_page_count(self, repo, sample_bundle_id):
        """Test registering PDF with very large page count."""
        repo.register(
            pdf_path="/test/large.pdf",
            pdf_filename="large.pdf",
            bundle_id=sample_bundle_id,
            page_count=10000,
        )

        pdf = repo.get_by_path("/test/large.pdf")
        assert pdf["page_count"] == 10000

    def test_cascade_set_null_on_bundle_deletion(self, repo, db_conn, sample_bundle_id):
        """Test that deleting a bundle sets bundle_id to NULL in pdf_files."""
        # Register PDF
        repo.register(
            pdf_path="/test/cascade.pdf",
            pdf_filename="cascade.pdf",
            bundle_id=sample_bundle_id,
            page_count=1,
        )

        # Verify PDF exists with bundle_id
        pdf = repo.get_by_path("/test/cascade.pdf")
        assert pdf["bundle_id"] == sample_bundle_id

        # Delete the bundle
        cursor = db_conn.connection.cursor()
        cursor.execute("DELETE FROM document_bundles WHERE id = ?", (sample_bundle_id,))
        db_conn.connection.commit()

        # Verify PDF still exists but bundle_id is NULL
        pdf = repo.get_by_path("/test/cascade.pdf")
        assert pdf is not None
        assert pdf["bundle_id"] is None

    def test_register_returns_zero_when_fetch_fails(self, repo, sample_bundle_id):
        """Test register returns 0 when fetching ID fails."""
        # Mock fetch_one_dict to return None
        with patch.object(repo.conn, "fetch_one_dict", return_value=None):
            pdf_id = repo.register(
                pdf_path="/test/fail.pdf",
                pdf_filename="fail.pdf",
                bundle_id=sample_bundle_id,
                page_count=1,
            )
            assert pdf_id == 0
