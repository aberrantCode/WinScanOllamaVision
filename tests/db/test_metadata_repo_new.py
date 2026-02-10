"""Tests for new MetadataRepository (normalized metadata table)."""

import pytest

from db.connection import DatabaseConnection
from db.repositories.metadata_repo import MetadataRepository
from db.schema import create_all_tables


@pytest.fixture
def db_conn(tmp_path):
    """Create temporary database connection."""
    db_path = tmp_path / "test_metadata.db"
    conn = DatabaseConnection(str(db_path))
    create_all_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def metadata_repo(db_conn):
    """Create MetadataRepository instance."""
    return MetadataRepository(db_conn)


@pytest.fixture
def sample_image_files(db_conn):
    """Create sample image files for testing."""
    # Insert test image files
    image_ids = []
    cursor = db_conn.connection.cursor()
    for i in range(3):
        cursor.execute(
            """
            INSERT INTO image_files (
                file_path, file_hash, directory_path, filename,
                file_size, file_mtime, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                f"/test/image{i}.png",
                f"hash{i}",
                "/test",
                f"image{i}.png",
                1000,
                1234567890.0,
                "analyzed",
            ),
        )
        image_ids.append(cursor.lastrowid)
    db_conn.commit()
    return image_ids


@pytest.fixture
def sample_analysis_results(db_conn, sample_image_files):
    """Create sample analysis results for testing."""
    analysis_ids = []
    cursor = db_conn.connection.cursor()
    for i, image_id in enumerate(sample_image_files):
        cursor.execute(
            """
            INSERT INTO analysis_results (
                image_file_id, provider_name, model_name,
                prompt_text, response_text, confidence_score,
                processing_time_ms, had_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                image_id,
                "test_provider",
                "test_model",
                "Extract document metadata",
                f'{{"company": "Company {i}", "document_type": "Invoice", "document_date": "2024-01-15"}}',
                0.95,
                100,
                0,
            ),
        )
        analysis_ids.append(cursor.lastrowid)
    db_conn.commit()
    return analysis_ids


class TestMetadataRepository:
    """Test suite for MetadataRepository."""

    def test_create_from_analysis(self, metadata_repo, sample_image_files, sample_analysis_results):
        """Test creating metadata from analysis."""
        normalized_metadata = {
            "company": "Acme Corp",
            "document_type": "Invoice",
            "document_date": "2024-01-15T00:00:00Z",
            "page_number": 1,
            "total_pages": 3,
            "belongs_to_same_doc": True,
            "rotation": 90,
            "confidence_score": 0.95,
            "tax_related": False,
        }

        metadata_id = metadata_repo.create_from_analysis(
            image_file_id=sample_image_files[0],
            analysis_result_id=sample_analysis_results[0],
            normalized_metadata=normalized_metadata,
            output_filename="test_output.pdf",
            document_category="Tax Documents",
        )

        assert metadata_id is not None
        assert metadata_id > 0

        # Verify metadata was created
        metadata = metadata_repo.get_by_image_file_id(sample_image_files[0])
        assert metadata is not None
        assert metadata["company"] == "Acme Corp"
        assert metadata["document_type"] == "Invoice"
        assert metadata["rotation"] == 90
        assert metadata["output_filename"] == "test_output.pdf"
        assert metadata["document_category"] == "Tax Documents"
        assert metadata["auto_approved"] == 1
        assert metadata["last_edited_by"] == "ai"

    def test_update_from_user(self, metadata_repo, sample_image_files, sample_analysis_results):
        """Test updating metadata after user edit."""
        # Create initial metadata
        normalized_metadata = {
            "company": "Acme Corp",
            "document_type": "Invoice",
            "rotation": 0,
        }

        metadata_repo.create_from_analysis(
            image_file_id=sample_image_files[0],
            analysis_result_id=sample_analysis_results[0],
            normalized_metadata=normalized_metadata,
        )

        # Update metadata
        updates = {
            "company": "Updated Company",
            "document_type": "Receipt",
            "rotation": 90,
            "output_filename": "new_filename.pdf",
        }

        metadata_repo.update_from_user(sample_image_files[0], updates)

        # Verify updates
        metadata = metadata_repo.get_by_image_file_id(sample_image_files[0])
        assert metadata["company"] == "Updated Company"
        assert metadata["document_type"] == "Receipt"
        assert metadata["rotation"] == 90
        assert metadata["output_filename"] == "new_filename.pdf"
        assert metadata["user_verified"] == 1
        assert metadata["last_edited_by"] == "user"

    def test_update_from_user_filters_invalid_fields(
        self, metadata_repo, sample_image_files, sample_analysis_results
    ):
        """Test that update_from_user filters out invalid fields."""
        normalized_metadata = {"company": "Test Corp"}

        metadata_repo.create_from_analysis(
            image_file_id=sample_image_files[0],
            analysis_result_id=sample_analysis_results[0],
            normalized_metadata=normalized_metadata,
        )

        # Try to update with invalid field
        updates = {
            "company": "Updated",
            "invalid_field": "should be ignored",
            "id": 999,  # Should not allow updating ID
        }

        metadata_repo.update_from_user(sample_image_files[0], updates)

        # Verify only valid fields updated
        metadata = metadata_repo.get_by_image_file_id(sample_image_files[0])
        assert metadata["company"] == "Updated"
        assert "invalid_field" not in metadata

    def test_get_by_image_file_id(self, metadata_repo, sample_image_files, sample_analysis_results):
        """Test retrieving metadata by image file ID."""
        normalized_metadata = {"company": "Test Company"}

        metadata_repo.create_from_analysis(
            image_file_id=sample_image_files[0],
            analysis_result_id=sample_analysis_results[0],
            normalized_metadata=normalized_metadata,
        )

        metadata = metadata_repo.get_by_image_file_id(sample_image_files[0])
        assert metadata is not None
        assert metadata["company"] == "Test Company"

    def test_get_by_image_file_id_not_found(self, metadata_repo):
        """Test retrieving non-existent metadata."""
        metadata = metadata_repo.get_by_image_file_id(999)
        assert metadata is None

    def test_get_by_image_path(
        self, metadata_repo, db_conn, sample_image_files, sample_analysis_results
    ):
        """Test retrieving metadata by image file path."""
        normalized_metadata = {"company": "Path Test"}

        metadata_repo.create_from_analysis(
            image_file_id=sample_image_files[0],
            analysis_result_id=sample_analysis_results[0],
            normalized_metadata=normalized_metadata,
        )

        metadata = metadata_repo.get_by_image_path("/test/image0.png")
        assert metadata is not None
        assert metadata["company"] == "Path Test"

    def test_link_to_pdf(self, metadata_repo, db_conn, sample_image_files, sample_analysis_results):
        """Test linking metadata to PDF."""
        # Create metadata for multiple images
        for i, (img_id, analysis_id) in enumerate(
            zip(sample_image_files, sample_analysis_results, strict=False)
        ):
            metadata_repo.create_from_analysis(
                image_file_id=img_id,
                analysis_result_id=analysis_id,
                normalized_metadata={"company": f"Company {i}"},
            )

        # Create bundle first
        cursor = db_conn.execute(
            """
            INSERT INTO document_bundles (bundle_name, confidence_score, confidence_level, status)
            VALUES (?, ?, ?, ?)
        """,
            ("Test Bundle", 0.9, "high", "completed"),
        )
        bundle_id = cursor.lastrowid

        # Create PDF file
        cursor = db_conn.execute(
            """
            INSERT INTO pdf_files (
                pdf_path, pdf_filename, bundle_id, page_count
            ) VALUES (?, ?, ?, ?)
        """,
            ("/test/output.pdf", "output.pdf", bundle_id, 3),
        )
        db_conn.commit()
        pdf_file_id = cursor.lastrowid

        # Link images to PDF (via bundle)
        metadata_repo.link_to_pdf(sample_image_files[:2], pdf_file_id)

        # Verify links - check bundle_images table
        cursor = db_conn.connection.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM bundle_images
            WHERE bundle_id = ? AND image_file_id IN (?, ?)
        """,
            (bundle_id, sample_image_files[0], sample_image_files[1]),
        )
        count = cursor.fetchone()[0]
        assert count == 2

        # Verify third image is not linked to bundle
        cursor.execute(
            """
            SELECT COUNT(*) FROM bundle_images
            WHERE bundle_id = ? AND image_file_id = ?
        """,
            (bundle_id, sample_image_files[2]),
        )
        count_third = cursor.fetchone()[0]
        assert count_third == 0

    def test_get_analysis_history(
        self, metadata_repo, db_conn, sample_image_files, sample_analysis_results
    ):
        """Test retrieving analysis history for an image."""
        # Create multiple analyses for same image
        image_file_id = sample_image_files[0]
        cursor = db_conn.connection.cursor()
        for i in range(3):
            cursor.execute(
                """
                INSERT INTO analysis_results (
                    image_file_id, provider_name, model_name,
                    prompt_text, response_text, processing_time_ms, confidence_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    image_file_id,
                    f"provider_{i}",
                    f"model_{i}",
                    "Extract metadata",
                    f'{{"company": "Company Version {i}"}}',
                    100,
                    0.9,
                ),
            )
        db_conn.commit()

        # Get history
        history = metadata_repo.get_analysis_history(sample_image_files[0])

        assert len(history) == 4  # 3 new + 1 from fixture
        # Verify all provider names are present
        provider_names = {h["provider_name"] for h in history}
        assert "test_provider" in provider_names
        assert "provider_0" in provider_names
        assert "provider_1" in provider_names
        assert "provider_2" in provider_names

    def test_get_all(self, metadata_repo, sample_image_files, sample_analysis_results):
        """Test retrieving all metadata records."""
        # Create metadata for all images
        for img_id, analysis_id in zip(sample_image_files, sample_analysis_results, strict=False):
            metadata_repo.create_from_analysis(
                image_file_id=img_id,
                analysis_result_id=analysis_id,
                normalized_metadata={"company": "Test"},
            )

        all_metadata = metadata_repo.get_all()
        assert len(all_metadata) == 3

    def test_get_all_with_status_filter(
        self, metadata_repo, db_conn, sample_image_files, sample_analysis_results
    ):
        """Test retrieving metadata with status filter."""
        # Update one image status
        db_conn.execute(
            "UPDATE image_files SET status = ? WHERE id = ?",
            ("completed", sample_image_files[0]),
        )
        db_conn.commit()

        # Create metadata
        for img_id, analysis_id in zip(sample_image_files, sample_analysis_results, strict=False):
            metadata_repo.create_from_analysis(
                image_file_id=img_id,
                analysis_result_id=analysis_id,
                normalized_metadata={"company": "Test"},
            )

        # Filter by status
        completed_metadata = metadata_repo.get_all(status_filter="completed")
        assert len(completed_metadata) == 1

    def test_get_unique_companies(self, metadata_repo, sample_image_files, sample_analysis_results):
        """Test retrieving unique company names."""
        # Create metadata with different companies
        companies = ["Acme Corp", "Beta Inc", "Acme Corp"]  # One duplicate
        for img_id, analysis_id, company in zip(
            sample_image_files, sample_analysis_results, companies, strict=False
        ):
            metadata_repo.create_from_analysis(
                image_file_id=img_id,
                analysis_result_id=analysis_id,
                normalized_metadata={"company": company},
            )

        unique_companies = metadata_repo.get_unique_companies()
        assert len(unique_companies) == 2
        assert "Acme Corp" in unique_companies
        assert "Beta Inc" in unique_companies

    def test_get_unique_document_types(
        self, metadata_repo, sample_image_files, sample_analysis_results
    ):
        """Test retrieving unique document types."""
        doc_types = ["Invoice", "Receipt", "Invoice"]
        for img_id, analysis_id, doc_type in zip(
            sample_image_files, sample_analysis_results, doc_types, strict=False
        ):
            metadata_repo.create_from_analysis(
                image_file_id=img_id,
                analysis_result_id=analysis_id,
                normalized_metadata={"document_type": doc_type},
            )

        unique_types = metadata_repo.get_unique_document_types()
        assert len(unique_types) == 2
        assert "Invoice" in unique_types
        assert "Receipt" in unique_types

    def test_get_unique_categories(
        self, metadata_repo, sample_image_files, sample_analysis_results
    ):
        """Test retrieving unique document categories."""
        categories = ["Tax Documents", "Receipts", "Tax Documents"]
        for img_id, analysis_id, category in zip(
            sample_image_files, sample_analysis_results, categories, strict=False
        ):
            metadata_repo.create_from_analysis(
                image_file_id=img_id,
                analysis_result_id=analysis_id,
                normalized_metadata={"company": "Test"},
                document_category=category,
            )

        unique_categories = metadata_repo.get_unique_categories()
        assert len(unique_categories) == 2
        assert "Tax Documents" in unique_categories
        assert "Receipts" in unique_categories

    def test_get_stats(self, metadata_repo, sample_image_files, sample_analysis_results):
        """Test retrieving metadata statistics."""
        # Create metadata with various states
        metadata_repo.create_from_analysis(
            image_file_id=sample_image_files[0],
            analysis_result_id=sample_analysis_results[0],
            normalized_metadata={"company": "Test"},
        )

        # Update one to user-verified
        metadata_repo.update_from_user(sample_image_files[0], {"company": "Updated"})

        stats = metadata_repo.get_stats()
        assert stats["total"] == 1
        assert stats["user_verified"] == 1
        assert stats["auto_approved"] == 1

    def test_delete_by_image_file_id(
        self, metadata_repo, sample_image_files, sample_analysis_results
    ):
        """Test deleting metadata record."""
        metadata_repo.create_from_analysis(
            image_file_id=sample_image_files[0],
            analysis_result_id=sample_analysis_results[0],
            normalized_metadata={"company": "Test"},
        )

        # Verify exists
        assert metadata_repo.get_by_image_file_id(sample_image_files[0]) is not None

        # Delete
        metadata_repo.delete_by_image_file_id(sample_image_files[0])

        # Verify deleted
        assert metadata_repo.get_by_image_file_id(sample_image_files[0]) is None
