"""Comprehensive tests for MetadataRepository.

Tests normalized metadata management including CRUD operations,
user updates, PDF linking, and statistics.
"""

import os
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

from db.connection import DatabaseConnection
from db.repositories.image_files_repo import ImageFilesRepository
from db.repositories.metadata_repo import MetadataRepository
from db.schema import create_all_tables


class TestMetadataRepositoryBasics:
    """Tests for repository initialization and basic operations."""

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
        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return MetadataRepository(conn)

    @pytest.fixture
    def image_repo(self, conn):
        return ImageFilesRepository(conn)

    def test_init_stores_connection(self, repo, conn):
        """Test that __init__ stores database connection."""
        assert repo.conn is conn

    def test_get_logger_returns_logger(self, repo):
        """Test _get_logger returns logger instance."""
        logger = repo._get_logger()
        assert logger is not None


class TestMetadataCreation:
    """Tests for metadata creation from analysis."""

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
        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return MetadataRepository(conn)

    @pytest.fixture
    def image_repo(self, conn):
        return ImageFilesRepository(conn)

    def test_create_from_analysis_creates_record(self, repo, image_repo):
        """Test create_from_analysis creates metadata record."""
        image_id = image_repo.register(
            "/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0
        )

        normalized_metadata = {
            "company": "Test Corp",
            "document_type": "Invoice",
            "document_date": "2024-01-15",
            "page_number": 1,
            "total_pages": 1,
            "belongs_to_same_doc": True,
            "rotation": 0,
            "confidence_score": 0.95,
            "tax_related": False,
            "is_blank": False,
        }

        metadata_id = repo.create_from_analysis(
            image_file_id=image_id,
            analysis_result_id=None,
            normalized_metadata=normalized_metadata,
            output_filename="output.pdf",
            document_category="Financial",
        )

        assert metadata_id > 0

        # Verify record was created
        record = repo.get_by_image_file_id(image_id)
        assert record is not None
        assert record["company"] == "Test Corp"
        assert record["document_type"] == "Invoice"
        assert record["output_filename"] == "output.pdf"
        assert record["document_category"] == "Financial"
        assert record["auto_approved"] == 1
        assert record["last_edited_by"] == "ai"

    def test_create_from_analysis_handles_partial_metadata(self, repo, image_repo):
        """Test create_from_analysis handles partial metadata."""
        image_id = image_repo.register(
            "/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0
        )

        # Only some fields provided
        normalized_metadata = {
            "company": "Test Corp",
            "document_type": "Invoice",
        }

        metadata_id = repo.create_from_analysis(
            image_file_id=image_id,
            analysis_result_id=None,
            normalized_metadata=normalized_metadata,
        )

        assert metadata_id > 0

        record = repo.get_by_image_file_id(image_id)
        assert record["company"] == "Test Corp"
        assert record["document_type"] == "Invoice"
        assert record["page_number"] is None
        assert record["output_filename"] is None

    def test_create_from_analysis_handles_operational_error(self, repo, image_repo):
        """Test create_from_analysis handles database lock error."""
        image_id = image_repo.register(
            "/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0
        )

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.OperationalError("locked")),
            pytest.raises(sqlite3.OperationalError, match="Database is locked"),
        ):
            repo.create_from_analysis(
                image_file_id=image_id,
                analysis_result_id=None,
                normalized_metadata={"company": "Test"},
            )

    def test_create_from_analysis_handles_database_error(self, repo, image_repo):
        """Test create_from_analysis handles general database error."""
        image_id = image_repo.register(
            "/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0
        )

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.Error("constraint violation")),
            pytest.raises(sqlite3.Error, match="Failed to create metadata record"),
        ):
            repo.create_from_analysis(
                image_file_id=image_id,
                analysis_result_id=None,
                normalized_metadata={"company": "Test"},
            )


class TestMetadataUpdates:
    """Tests for user metadata updates."""

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
        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return MetadataRepository(conn)

    @pytest.fixture
    def image_repo(self, conn):
        return ImageFilesRepository(conn)

    def test_update_from_user_creates_record_if_not_exists(self, repo, image_repo):
        """Test update_from_user creates metadata if doesn't exist (UPSERT)."""
        image_id = image_repo.register(
            "/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0
        )

        repo.update_from_user(
            image_file_id=image_id,
            updates={"company": "Updated Corp", "document_type": "Receipt"},
        )

        record = repo.get_by_image_file_id(image_id)
        assert record is not None
        assert record["company"] == "Updated Corp"
        assert record["document_type"] == "Receipt"
        # Note: user_verified is only set to 1 during UPDATE, not INSERT
        # During INSERT (new record), user_verified defaults to 0

    def test_update_from_user_updates_existing_record(self, repo, image_repo):
        """Test update_from_user updates existing metadata."""
        image_id = image_repo.register(
            "/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0
        )

        # Create initial metadata
        repo.create_from_analysis(
            image_file_id=image_id,
            analysis_result_id=None,
            normalized_metadata={"company": "Original", "document_type": "Invoice"},
        )

        # Update via user
        repo.update_from_user(
            image_file_id=image_id,
            updates={"company": "Updated Corp"},
        )

        record = repo.get_by_image_file_id(image_id)
        assert record["company"] == "Updated Corp"
        assert record["document_type"] == "Invoice"  # Unchanged
        assert record["user_verified"] == 1

    def test_update_from_user_filters_disallowed_fields(self, repo, image_repo):
        """Test update_from_user filters out disallowed fields."""
        image_id = image_repo.register(
            "/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0
        )

        # Try to update with disallowed field
        repo.update_from_user(
            image_file_id=image_id,
            updates={
                "company": "Test Corp",
                "malicious_field": "evil",  # Should be filtered
                "id": 9999,  # Should be filtered
            },
        )

        record = repo.get_by_image_file_id(image_id)
        assert record["company"] == "Test Corp"
        # Verify malicious fields weren't added (would fail on query if they existed)

    def test_update_from_user_returns_early_for_empty_updates(self, repo, image_repo):
        """Test update_from_user returns early for empty updates."""
        image_id = image_repo.register(
            "/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0
        )

        # Update with only disallowed fields (filtered to empty)
        repo.update_from_user(
            image_file_id=image_id,
            updates={"invalid_field": "value"},
        )

        # Should not have created a record
        record = repo.get_by_image_file_id(image_id)
        assert record is None

    def test_update_from_user_handles_operational_error(self, repo, image_repo):
        """Test update_from_user handles database lock error."""
        image_id = image_repo.register(
            "/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0
        )

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.OperationalError("locked")),
            pytest.raises(sqlite3.OperationalError, match="Database is locked"),
        ):
            repo.update_from_user(
                image_file_id=image_id,
                updates={"company": "Test"},
            )

    def test_update_from_user_handles_database_error(self, repo, image_repo):
        """Test update_from_user handles general database error."""
        image_id = image_repo.register(
            "/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0
        )

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.Error("constraint violation")),
            pytest.raises(sqlite3.Error, match="Failed to update metadata"),
        ):
            repo.update_from_user(
                image_file_id=image_id,
                updates={"company": "Test"},
            )


class TestMetadataRetrieval:
    """Tests for metadata retrieval methods."""

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
        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return MetadataRepository(conn)

    @pytest.fixture
    def image_repo(self, conn):
        return ImageFilesRepository(conn)

    def test_get_by_image_file_id_returns_record(self, repo, image_repo):
        """Test get_by_image_file_id returns existing record."""
        image_id = image_repo.register(
            "/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0
        )

        repo.create_from_analysis(
            image_file_id=image_id,
            analysis_result_id=None,
            normalized_metadata={"company": "Test Corp"},
        )

        record = repo.get_by_image_file_id(image_id)

        assert record is not None
        assert record["company"] == "Test Corp"

    def test_get_by_image_file_id_returns_none_for_missing(self, repo):
        """Test get_by_image_file_id returns None for missing record."""
        record = repo.get_by_image_file_id(9999)
        assert record is None

    def test_get_by_image_path_returns_record(self, repo, image_repo):
        """Test get_by_image_path returns record via image path."""
        image_id = image_repo.register(
            "/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0
        )

        repo.create_from_analysis(
            image_file_id=image_id,
            analysis_result_id=None,
            normalized_metadata={"company": "Test Corp"},
        )

        record = repo.get_by_image_path("/test/image.jpg")

        assert record is not None
        assert record["company"] == "Test Corp"

    def test_get_by_image_path_returns_none_for_missing(self, repo):
        """Test get_by_image_path returns None for missing record."""
        record = repo.get_by_image_path("/nonexistent/image.jpg")
        assert record is None

    def test_get_all_returns_all_metadata(self, repo, image_repo):
        """Test get_all returns all metadata records."""
        id1 = image_repo.register(
            "/test/image1.jpg", "abc123", "/test", "image1.jpg", 1024, 12345.0
        )
        id2 = image_repo.register(
            "/test/image2.jpg", "def456", "/test", "image2.jpg", 2048, 12346.0
        )

        repo.create_from_analysis(
            image_file_id=id1,
            analysis_result_id=None,
            normalized_metadata={"company": "Corp A"},
        )
        repo.create_from_analysis(
            image_file_id=id2,
            analysis_result_id=None,
            normalized_metadata={"company": "Corp B"},
        )

        results = repo.get_all()

        assert len(results) == 2
        assert any(r["company"] == "Corp A" for r in results)
        assert any(r["company"] == "Corp B" for r in results)

    def test_get_all_filters_by_status(self, repo, image_repo):
        """Test get_all filters by image status."""
        id1 = image_repo.register(
            "/test/image1.jpg", "abc123", "/test", "image1.jpg", 1024, 12345.0
        )
        id2 = image_repo.register(
            "/test/image2.jpg", "def456", "/test", "image2.jpg", 2048, 12346.0
        )

        # Update one image status
        image_repo.update_status("/test/image2.jpg", "analyzed")

        repo.create_from_analysis(
            image_file_id=id1,
            analysis_result_id=None,
            normalized_metadata={"company": "Corp A"},
        )
        repo.create_from_analysis(
            image_file_id=id2,
            analysis_result_id=None,
            normalized_metadata={"company": "Corp B"},
        )

        results = repo.get_all(status_filter="analyzed")

        assert len(results) == 1
        assert results[0]["company"] == "Corp B"

    def test_get_all_filters_by_directory(self, repo, image_repo):
        """Test get_all filters by directory path."""
        id1 = image_repo.register(
            "/test/image1.jpg", "abc123", "/test", "image1.jpg", 1024, 12345.0
        )
        id2 = image_repo.register(
            "/other/image2.jpg", "def456", "/other", "image2.jpg", 2048, 12346.0
        )

        repo.create_from_analysis(
            image_file_id=id1,
            analysis_result_id=None,
            normalized_metadata={"company": "Corp A"},
        )
        repo.create_from_analysis(
            image_file_id=id2,
            analysis_result_id=None,
            normalized_metadata={"company": "Corp B"},
        )

        results = repo.get_all(directory_filter="/test")

        assert len(results) == 1
        assert results[0]["company"] == "Corp A"

    def test_get_all_returns_empty_list_for_no_results(self, repo):
        """Test get_all returns empty list when no metadata exists."""
        results = repo.get_all()
        assert results == []


class TestMetadataDeletion:
    """Tests for metadata deletion."""

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
        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return MetadataRepository(conn)

    @pytest.fixture
    def image_repo(self, conn):
        return ImageFilesRepository(conn)

    def test_delete_by_image_file_id_removes_record(self, repo, image_repo):
        """Test delete_by_image_file_id removes metadata."""
        image_id = image_repo.register(
            "/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0
        )

        repo.create_from_analysis(
            image_file_id=image_id,
            analysis_result_id=None,
            normalized_metadata={"company": "Test Corp"},
        )

        repo.delete_by_image_file_id(image_id)

        record = repo.get_by_image_file_id(image_id)
        assert record is None

    def test_delete_by_image_file_id_handles_operational_error(self, repo, image_repo):
        """Test delete_by_image_file_id handles database lock error."""
        image_id = image_repo.register(
            "/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0
        )

        repo.create_from_analysis(
            image_file_id=image_id,
            analysis_result_id=None,
            normalized_metadata={"company": "Test"},
        )

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.OperationalError("locked")),
            pytest.raises(sqlite3.OperationalError, match="Database is locked"),
        ):
            repo.delete_by_image_file_id(image_id)

    def test_delete_by_image_file_id_handles_database_error(self, repo, image_repo):
        """Test delete_by_image_file_id handles general database error."""
        image_id = image_repo.register(
            "/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0
        )

        repo.create_from_analysis(
            image_file_id=image_id,
            analysis_result_id=None,
            normalized_metadata={"company": "Test"},
        )

        with (
            patch.object(repo.conn, "commit", side_effect=sqlite3.Error("constraint violation")),
            pytest.raises(sqlite3.Error, match="Failed to delete metadata record"),
        ):
            repo.delete_by_image_file_id(image_id)


class TestMetadataAutocomplete:
    """Tests for autocomplete helper methods."""

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
        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return MetadataRepository(conn)

    @pytest.fixture
    def image_repo(self, conn):
        return ImageFilesRepository(conn)

    def test_get_unique_companies_returns_distinct_companies(self, repo, image_repo):
        """Test get_unique_companies returns distinct company names."""
        for i, company in enumerate(["Corp A", "Corp B", "Corp A", "Corp C"]):
            image_id = image_repo.register(
                f"/test/image{i}.jpg",
                f"hash{i}",
                "/test",
                f"image{i}.jpg",
                1024,
                12345.0 + i,
            )
            repo.create_from_analysis(
                image_file_id=image_id,
                analysis_result_id=None,
                normalized_metadata={"company": company},
            )

        companies = repo.get_unique_companies()

        assert len(companies) == 3
        assert "Corp A" in companies
        assert "Corp B" in companies
        assert "Corp C" in companies

    def test_get_unique_companies_excludes_null_and_empty(self, repo, image_repo):
        """Test get_unique_companies excludes NULL and empty strings."""
        id1 = image_repo.register(
            "/test/image1.jpg", "abc123", "/test", "image1.jpg", 1024, 12345.0
        )
        id2 = image_repo.register(
            "/test/image2.jpg", "def456", "/test", "image2.jpg", 2048, 12346.0
        )
        id3 = image_repo.register(
            "/test/image3.jpg", "ghi789", "/test", "image3.jpg", 3072, 12347.0
        )

        repo.create_from_analysis(
            image_file_id=id1,
            analysis_result_id=None,
            normalized_metadata={"company": "Corp A"},
        )
        repo.create_from_analysis(
            image_file_id=id2,
            analysis_result_id=None,
            normalized_metadata={"company": ""},  # Empty string
        )
        repo.create_from_analysis(
            image_file_id=id3,
            analysis_result_id=None,
            normalized_metadata={},  # No company field (NULL)
        )

        companies = repo.get_unique_companies()

        assert len(companies) == 1
        assert companies[0] == "Corp A"

    def test_get_unique_document_types_returns_distinct_types(self, repo, image_repo):
        """Test get_unique_document_types returns distinct types."""
        for i, doc_type in enumerate(["Invoice", "Receipt", "Invoice", "Contract"]):
            image_id = image_repo.register(
                f"/test/image{i}.jpg",
                f"hash{i}",
                "/test",
                f"image{i}.jpg",
                1024,
                12345.0 + i,
            )
            repo.create_from_analysis(
                image_file_id=image_id,
                analysis_result_id=None,
                normalized_metadata={"document_type": doc_type},
            )

        doc_types = repo.get_unique_document_types()

        assert len(doc_types) == 3
        assert "Invoice" in doc_types
        assert "Receipt" in doc_types
        assert "Contract" in doc_types

    def test_get_unique_categories_returns_distinct_categories(self, repo, image_repo):
        """Test get_unique_categories returns distinct categories."""
        for i, category in enumerate(["Financial", "Legal", "Financial", "Medical"]):
            image_id = image_repo.register(
                f"/test/image{i}.jpg",
                f"hash{i}",
                "/test",
                f"image{i}.jpg",
                1024,
                12345.0 + i,
            )
            repo.create_from_analysis(
                image_file_id=image_id,
                analysis_result_id=None,
                normalized_metadata={},
                document_category=category,
            )

        categories = repo.get_unique_categories()

        assert len(categories) == 3
        assert "Financial" in categories
        assert "Legal" in categories
        assert "Medical" in categories


class TestMetadataStatistics:
    """Tests for metadata statistics."""

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
        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return MetadataRepository(conn)

    @pytest.fixture
    def image_repo(self, conn):
        return ImageFilesRepository(conn)

    def test_get_stats_returns_counts(self, repo, image_repo):
        """Test get_stats returns all statistics."""
        id1 = image_repo.register(
            "/test/image1.jpg", "abc123", "/test", "image1.jpg", 1024, 12345.0
        )
        id2 = image_repo.register(
            "/test/image2.jpg", "def456", "/test", "image2.jpg", 2048, 12346.0
        )

        # Create id1 via analysis (auto_approved)
        repo.create_from_analysis(
            image_file_id=id1,
            analysis_result_id=None,
            normalized_metadata={"company": "Corp A"},
        )

        # Create id2 via analysis first, then update via user (user_verified)
        repo.create_from_analysis(
            image_file_id=id2,
            analysis_result_id=None,
            normalized_metadata={"company": "Original"},
        )
        repo.update_from_user(
            image_file_id=id2,
            updates={"company": "Corp B"},
        )

        stats = repo.get_stats()

        assert stats["total"] == 2
        assert stats["auto_approved"] == 2  # Both created via auto
        assert stats["user_verified"] == 1  # Only id2 updated by user

    def test_get_stats_returns_zero_for_empty_database(self, repo):
        """Test get_stats returns 0 for empty database."""
        stats = repo.get_stats()

        assert stats["total"] == 0
        assert stats["auto_approved"] == 0
        assert stats["user_verified"] == 0

    def test_get_stats_raises_for_uninitialized_connection(self, repo):
        """Test get_stats raises RuntimeError for uninitialized connection."""
        # Temporarily set connection to None to simulate uninitialized state
        original_connection = repo.conn.connection
        repo.conn.connection = None

        try:
            with pytest.raises(RuntimeError, match="Database connection not initialized"):
                repo.get_stats()
        finally:
            # Restore original connection
            repo.conn.connection = original_connection


class TestMetadataAnalysisHistory:
    """Tests for analysis history retrieval."""

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
        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return MetadataRepository(conn)

    @pytest.fixture
    def image_repo(self, conn):
        return ImageFilesRepository(conn)

    def test_get_analysis_history_returns_all_analyses(self, repo, image_repo, conn):
        """Test get_analysis_history returns all analysis results for image."""
        from db.repositories import AnalysisRepository

        analysis_repo = AnalysisRepository(conn)

        image_id = image_repo.register(
            "/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0
        )

        # Create multiple analysis results
        analysis_repo.save(
            image_file_id=image_id,
            provider_name="ollama",
            model_name="test-model",
            prompt_text="test prompt",
            response_text="response 1",
            confidence_score=0.9,
            processing_time_ms=100,
            had_error=False,
        )

        analysis_repo.save(
            image_file_id=image_id,
            provider_name="claude",
            model_name="test-model",
            prompt_text="test prompt",
            response_text="response 2",
            confidence_score=0.95,
            processing_time_ms=150,
            had_error=False,
        )

        history = repo.get_analysis_history(image_id)

        assert len(history) == 2
        assert history[0]["provider_name"] in ["ollama", "claude"]
        assert history[1]["provider_name"] in ["ollama", "claude"]

    def test_get_analysis_history_returns_empty_for_no_analyses(self, repo, image_repo):
        """Test get_analysis_history returns empty list for image with no analyses."""
        image_id = image_repo.register(
            "/test/image.jpg", "abc123", "/test", "image.jpg", 1024, 12345.0
        )

        history = repo.get_analysis_history(image_id)

        assert history == []


class TestMetadataLinkToPdf:
    """Tests for link_to_pdf method."""

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
        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return MetadataRepository(conn)

    @pytest.fixture
    def image_repo(self, conn):
        return ImageFilesRepository(conn)

    def test_link_to_pdf_links_images_to_bundle(self, repo, image_repo, conn):
        """Test link_to_pdf adds images to PDF's bundle."""
        # Create images
        image1_id = image_repo.register(
            "/test/img1.jpg", "hash1", "/test", "img1.jpg", 1024, 12345.0
        )
        image2_id = image_repo.register(
            "/test/img2.jpg", "hash2", "/test", "img2.jpg", 2048, 12346.0
        )

        # Create bundle
        conn.execute(
            "INSERT INTO document_bundles (bundle_name, status) VALUES (?, ?)",
            ("Test Bundle", "completed"),
        )
        bundle_id = conn.fetch_one("SELECT last_insert_rowid()")[0]

        # Create PDF linked to bundle
        conn.execute(
            "INSERT INTO pdf_files (pdf_path, pdf_filename, bundle_id) VALUES (?, ?, ?)",
            ("/output/test.pdf", "test.pdf", bundle_id),
        )
        pdf_id = conn.fetch_one("SELECT last_insert_rowid()")[0]
        conn.commit()

        # Link images to PDF
        repo.link_to_pdf([image1_id, image2_id], pdf_id)

        # Verify images were added to bundle
        cursor = conn.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM bundle_images WHERE bundle_id = ?", (bundle_id,))
        count = cursor.fetchone()[0]

        assert count == 2

    def test_link_to_pdf_returns_early_for_empty_list(self, repo):
        """Test link_to_pdf returns early for empty image list."""
        # Should not raise error
        repo.link_to_pdf([], 999)

    def test_link_to_pdf_returns_early_for_nonexistent_pdf(self, repo, image_repo):
        """Test link_to_pdf returns early when PDF doesn't exist."""
        image_id = image_repo.register("/test/img.jpg", "hash", "/test", "img.jpg", 1024, 12345.0)

        # Should not raise error
        repo.link_to_pdf([image_id], 999999)

    def test_link_to_pdf_returns_early_for_pdf_without_bundle(self, repo, image_repo, conn):
        """Test link_to_pdf returns early when PDF has no bundle."""
        image_id = image_repo.register("/test/img.jpg", "hash", "/test", "img.jpg", 1024, 12345.0)

        # Create PDF without bundle_id
        conn.execute(
            "INSERT INTO pdf_files (pdf_path, pdf_filename, bundle_id) VALUES (?, ?, NULL)",
            ("/output/test.pdf", "test.pdf"),
        )
        pdf_id = conn.fetch_one("SELECT last_insert_rowid()")[0]
        conn.commit()

        # Should not raise error
        repo.link_to_pdf([image_id], pdf_id)

    def test_link_to_pdf_handles_operational_error(self, repo, image_repo, conn):
        """Test link_to_pdf handles OperationalError during commit."""
        image_id = image_repo.register("/test/img.jpg", "hash", "/test", "img.jpg", 1024, 12345.0)

        # Create bundle and PDF
        conn.execute(
            "INSERT INTO document_bundles (bundle_name, status) VALUES (?, ?)",
            ("Bundle", "completed"),
        )
        bundle_id = conn.fetch_one("SELECT last_insert_rowid()")[0]

        conn.execute(
            "INSERT INTO pdf_files (pdf_path, pdf_filename, bundle_id) VALUES (?, ?, ?)",
            ("/output/test.pdf", "test.pdf", bundle_id),
        )
        pdf_id = conn.fetch_one("SELECT last_insert_rowid()")[0]
        conn.commit()

        # Mock commit to raise OperationalError
        with patch.object(
            repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
        ), pytest.raises(sqlite3.OperationalError, match="Database is locked"):
            repo.link_to_pdf([image_id], pdf_id)

    def test_link_to_pdf_handles_database_error(self, repo, image_repo, conn):
        """Test link_to_pdf handles generic database error during commit."""
        image_id = image_repo.register("/test/img.jpg", "hash", "/test", "img.jpg", 1024, 12345.0)

        # Create bundle and PDF
        conn.execute(
            "INSERT INTO document_bundles (bundle_name, status) VALUES (?, ?)",
            ("Bundle", "completed"),
        )
        bundle_id = conn.fetch_one("SELECT last_insert_rowid()")[0]

        conn.execute(
            "INSERT INTO pdf_files (pdf_path, pdf_filename, bundle_id) VALUES (?, ?, ?)",
            ("/output/test.pdf", "test.pdf", bundle_id),
        )
        pdf_id = conn.fetch_one("SELECT last_insert_rowid()")[0]
        conn.commit()

        # Mock commit to raise generic Error
        with patch.object(repo.conn, "commit", side_effect=sqlite3.Error("constraint violation")):
            with pytest.raises(sqlite3.Error, match="Failed to link images to PDF"):
                repo.link_to_pdf([image_id], pdf_id)


class TestMetadataCreateFromAnalysisEdgeCases:
    """Additional edge case tests for create_from_analysis."""

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
        create_all_tables(connection)
        yield connection
        connection.close()

    @pytest.fixture
    def repo(self, conn):
        return MetadataRepository(conn)

    @pytest.fixture
    def image_repo(self, conn):
        return ImageFilesRepository(conn)

    def test_create_from_analysis_raises_error_when_lastrowid_is_none(
        self, repo, image_repo, monkeypatch
    ):
        """Test create_from_analysis raises RuntimeError when cursor.lastrowid is None."""
        image_id = image_repo.register("/test/img.jpg", "hash", "/test", "img.jpg", 1024, 12345.0)

        # Mock execute to return a cursor with lastrowid = None
        class MockCursor:
            lastrowid = None

        def mock_execute(*args, **kwargs):
            return MockCursor()

        monkeypatch.setattr(repo.conn, "execute", mock_execute)
        monkeypatch.setattr(repo.conn, "commit", lambda: None)

        with pytest.raises(RuntimeError, match="Failed to retrieve inserted metadata ID"):
            repo.create_from_analysis(
                image_file_id=image_id,
                analysis_result_id=None,
                normalized_metadata={"company": "Test"},
            )
