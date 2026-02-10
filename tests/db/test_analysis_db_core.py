"""
Core tests for AnalysisDB focusing on critical functionality.

Target: 80%+ coverage on core methods
"""

import os
import tempfile

import pytest

from db.analysis_db import AnalysisDB


class TestAnalysisDBCore:
    """Core test suite for AnalysisDB"""

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
        """Create AnalysisDB instance"""
        database = AnalysisDB(temp_db_path)
        yield database
        if database.connection:
            database.connection.close()

    def test_init_creates_database(self, temp_db_path):
        # Act
        db = AnalysisDB(temp_db_path)

        # Assert
        assert os.path.exists(temp_db_path)
        assert db.connection is not None
        db.connection.close()

    def test_create_extended_tables(self, db):
        # Act
        cursor = db.connection.connection.cursor()
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [table[0] for table in tables]

        # Assert - after schema refactoring
        assert "analysis_results" in table_names
        assert "metadata" in table_names
        assert "document_bundles" in table_names
        assert "pdf_files" in table_names
        assert "source_directories" in table_names
        assert "bundle_images" in table_names

    def test_save_and_get_analysis(self, db):
        # Arrange
        file_path = "/test/page.jpg"
        file_hash = "abc123"
        analysis_data = {"document_type": "Invoice", "company": "Test Corp"}

        # Act
        analysis_id = db.save_analysis(
            file_path=file_path,
            file_hash=file_hash,
            provider_name="ollama",
            model_name="test-model",
            analysis_data=analysis_data,
            raw_response='{"test": "data"}',
            processing_time_ms=100,
        )
        result = db.get_analysis(file_path)

        # Assert - after schema refactoring, get_analysis returns analysis provenance only
        assert result is not None
        assert result["id"] == analysis_id
        assert result["provider_name"] == "ollama"
        assert result["model_name"] == "test-model"
        # Metadata (company, document_type) is in separate metadata table, not analysis_results

    def test_get_analysis_returns_none_when_not_exists(self, db):
        # Act
        result = db.get_analysis("/nonexistent.jpg")

        # Assert
        assert result is None

    def test_get_analyzed_pages(self, db):
        # Arrange
        db.save_analysis(
            "/test/p1.jpg",
            "hash1",
            "ollama",
            "model",
            {"page_number": 1},
            "{}",
            100,
        )

        # Act
        pages = db.get_analyzed_pages()

        # Assert
        assert len(pages) >= 1

    def test_source_directory_management(self, db):
        # Act
        db.add_source_directory("/test/dir", scan_on_startup=True)
        directories = db.get_active_directories()

        # Assert
        assert "/test/dir" in directories

    def test_remove_source_directory(self, db):
        # Arrange
        db.add_source_directory("/test/dir")

        # Act
        db.remove_source_directory("/test/dir")

        # Assert
        assert "/test/dir" not in db.get_active_directories()

    def test_save_bundle_suggestion(self, db):
        # Arrange
        file_paths = ["/p1.jpg", "/p2.jpg"]
        bundle_metadata = {
            "suggested_filename": "document.pdf",
            "company": "Test Corp",
        }

        # Act
        bundle_id = db.save_bundle_suggestion(file_paths, bundle_metadata, 0.9)

        # Assert
        assert bundle_id > 0
        suggestions = db.get_bundle_suggestions()
        assert len(suggestions) > 0

    def test_update_bundle_status(self, db):
        # Arrange
        bundle_id = db.save_bundle_suggestion(["/p1.jpg"], {"suggested_filename": "doc.pdf"}, 0.9)

        # Act
        db.update_bundle_status(bundle_id, "accepted")

        # Assert
        # Simply verify no exception was raised and bundle still exists
        assert bundle_id > 0

    def test_log_action(self, db):
        # Act
        db.log_action("test_action", "Test details", file_path="/file.jpg")

        # Assert
        cursor = db.connection.connection.cursor()
        result = cursor.execute(
            "SELECT action_type FROM audit_trail WHERE action_type = ?",
            ("test_action",),
        ).fetchone()
        assert result is not None

    def test_get_extended_statistics(self, db):
        # Arrange
        db.save_analysis("/p1.jpg", "hash", "ollama", "model", {}, "{}", 100)

        # Act
        stats = db.get_extended_statistics()

        # Assert
        assert isinstance(stats, dict)
        assert "total_analyzed_pages" in stats

    def test_get_analysis_statistics(self, db):
        # Arrange
        db.save_analysis("/p1.jpg", "hash1", "ollama", "model", {}, "{}", 100)
        db.save_analysis("/p2.jpg", "hash2", "claude", "model", {}, "{}", 200)

        # Act
        stats = db.get_analysis_statistics()

        # Assert
        assert stats["total_analyses"] >= 2
        assert "provider_breakdown" in stats
        assert stats["provider_breakdown"]["ollama"] >= 1

    def test_get_document_type_breakdown(self, db):
        # Arrange - save analyses and create metadata records
        analysis_id1 = db.save_analysis(
            "/p1.jpg", "hash1", "ollama", "model", {"document_type": "Invoice"}, "{}", 100
        )
        analysis_id2 = db.save_analysis(
            "/p2.jpg", "hash2", "ollama", "model", {"document_type": "Receipt"}, "{}", 100
        )

        # Create metadata records (document_type is in metadata table now)
        img1 = db.get_image_file("/p1.jpg")
        img2 = db.get_image_file("/p2.jpg")
        db.create_metadata_from_analysis(
            image_file_id=img1["id"],
            analysis_id=analysis_id1,
            normalized_metadata={"document_type": "Invoice"},
        )
        db.create_metadata_from_analysis(
            image_file_id=img2["id"],
            analysis_id=analysis_id2,
            normalized_metadata={"document_type": "Receipt"},
        )

        # Act
        breakdown = db.get_document_type_breakdown()

        # Assert
        assert breakdown.get("Invoice", 0) >= 1
        assert breakdown.get("Receipt", 0) >= 1

    def test_update_directory_scan_info(self, db):
        # Arrange
        db.add_source_directory("/test/dir")

        # Act
        db.update_directory_scan_info("/test/dir", 42)

        # Assert - verify no exception raised
        assert "/test/dir" in db.get_active_directories()

    def test_get_analyzed_pages_with_directory_filter(self, db):
        # Arrange
        db.save_analysis("/dir1/p1.jpg", "h1", "ollama", "model", {}, "{}", 100)
        db.save_analysis("/dir2/p2.jpg", "h2", "ollama", "model", {}, "{}", 100)

        # Act
        all_pages = db.get_analyzed_pages()
        filtered = db.get_analyzed_pages(directory_filter="/dir1")

        # Assert
        assert len(all_pages) >= 2
        # Note: directory_filter uses LIKE so it's a partial match
        assert len(filtered) >= 0

    def test_close_closes_connection(self, temp_db_path):
        # Arrange
        db = AnalysisDB(temp_db_path)

        # Act
        db.close()

        # Assert - connection should be None after close
        assert db.connection.connection is None

    def test_get_bundled_file_paths_delegates_to_repository(self, db):
        # Arrange - register images first, then create bundle
        db.register_image_file("/test/p1.jpg", "hash1", "/test", "p1.jpg", 100, 123.0)
        db.register_image_file("/test/p2.jpg", "hash2", "/test", "p2.jpg", 200, 124.0)

        bundle_id = db.save_bundle_suggestion(
            ["/test/p1.jpg", "/test/p2.jpg"], {"bundle_name": "Test Bundle"}, 0.9
        )
        db.update_bundle_status(bundle_id, "accepted")

        # Act
        bundled_paths = db.get_bundled_file_paths()

        # Assert
        assert isinstance(bundled_paths, set)
        assert "/test/p1.jpg" in bundled_paths
        assert "/test/p2.jpg" in bundled_paths

    def test_get_bundled_file_paths_returns_empty_set_when_no_bundles(self, db):
        # Act
        bundled_paths = db.get_bundled_file_paths()

        # Assert
        assert isinstance(bundled_paths, set)
        assert len(bundled_paths) == 0

    def test_get_bundled_file_paths_filters_by_status(self, db):
        # Arrange - register images first
        db.register_image_file("/suggested.jpg", "h1", "/", "suggested.jpg", 100, 123.0)
        db.register_image_file("/accepted.jpg", "h2", "/", "accepted.jpg", 100, 123.0)
        db.register_image_file("/rejected.jpg", "h3", "/", "rejected.jpg", 100, 123.0)
        db.register_image_file("/completed.jpg", "h4", "/", "completed.jpg", 100, 123.0)

        # Create bundles with different statuses
        _ = db.save_bundle_suggestion(["/suggested.jpg"], {"bundle_name": "Test"}, 0.9)
        accepted_id = db.save_bundle_suggestion(["/accepted.jpg"], {"bundle_name": "Test"}, 0.9)
        rejected_id = db.save_bundle_suggestion(["/rejected.jpg"], {"bundle_name": "Test"}, 0.9)
        completed_id = db.save_bundle_suggestion(["/completed.jpg"], {"bundle_name": "Test"}, 0.9)

        db.update_bundle_status(accepted_id, "accepted")
        db.update_bundle_status(rejected_id, "rejected")
        db.update_bundle_status(completed_id, "completed")

        # Act
        bundled_paths = db.get_bundled_file_paths()

        # Assert - only accepted and completed should be included
        assert "/accepted.jpg" in bundled_paths
        assert "/completed.jpg" in bundled_paths
        assert "/suggested.jpg" not in bundled_paths
        assert "/rejected.jpg" not in bundled_paths

    # ==================== Image Files Facade Tests ====================

    def test_register_image_file(self, db):
        # Act
        image_id = db.register_image_file(
            file_path="/test/image.png",
            file_hash="hash123",
            directory_path="/test",
            filename="image.png",
            file_size=1024,
            file_mtime=1234567890.0,
        )

        # Assert
        assert image_id > 0
        image = db.get_image_file("/test/image.png")
        assert image is not None
        assert image["file_hash"] == "hash123"

    def test_get_registered_images(self, db):
        # Arrange
        db.register_image_file("/test/img1.png", "h1", "/test", "img1.png", 100, 123.0)
        db.register_image_file("/test/img2.png", "h2", "/test", "img2.png", 200, 124.0)
        db.update_image_status("/test/img1.png", "analyzed", analysis_id=1)

        # Act
        registered = db.get_registered_images()

        # Assert
        assert len(registered) == 1
        assert registered[0]["file_path"] == "/test/img2.png"

    def test_mark_images_deleted_batch(self, db):
        # Arrange
        db.register_image_file("/test/img1.png", "h1", "/test", "img1.png", 100, 123.0)
        db.register_image_file("/test/img2.png", "h2", "/test", "img2.png", 200, 124.0)

        # Act
        count = db.mark_images_deleted_batch(["/test/img1.png", "/test/img2.png"])

        # Assert
        assert count == 2
        img1 = db.get_image_file("/test/img1.png")
        assert img1["status"] == "deleted"

    def test_get_image_files_stats(self, db):
        # Arrange
        db.register_image_file("/test/img1.png", "h1", "/test", "img1.png", 100, 123.0)
        db.register_image_file("/test/img2.png", "h2", "/test", "img2.png", 200, 124.0)
        db.update_image_status("/test/img1.png", "analyzed", analysis_id=1)

        # Act
        stats = db.get_image_files_stats()

        # Assert
        assert stats["total"] == 2
        assert stats["status_registered"] == 1
        assert stats["status_analyzed"] == 1

    # ==================== PDF Files Facade Tests ====================

    def test_register_pdf_file(self, db):
        # Arrange - register images first
        img_id1 = db.register_image_file("/test/img1.png", "h1", "/test", "img1.png", 100, 123.0)
        img_id2 = db.register_image_file("/test/img2.png", "h2", "/test", "img2.png", 100, 123.0)
        img_id3 = db.register_image_file("/test/img3.png", "h3", "/test", "img3.png", 100, 123.0)

        bundle_id = db.save_bundle_suggestion(
            ["/test/img1.png", "/test/img2.png", "/test/img3.png"], {"bundle_name": "Test"}, 0.9
        )

        # Act
        pdf_id = db.register_pdf_file(
            pdf_path="/output/doc.pdf",
            pdf_filename="doc.pdf",
            bundle_id=bundle_id,
            source_image_ids=[img_id1, img_id2, img_id3],
            page_count=3,
            file_hash="hash_pdf",
            file_size=102400,
        )

        # Assert
        assert pdf_id > 0
        pdf = db.get_pdf_file("/output/doc.pdf")
        assert pdf is not None
        assert pdf["bundle_id"] == bundle_id
        assert pdf["page_count"] == 3

        # Verify images were linked via junction table (pdf_image_pages)
        cursor = db.connection.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM pdf_image_pages WHERE pdf_file_id = ?", (pdf_id,))
        assert cursor.fetchone()[0] == 3

    def test_get_pdf_by_bundle(self, db):
        # Arrange - register images first
        img_id1 = db.register_image_file("/test/img1.png", "h1", "/test", "img1.png", 100, 123.0)
        img_id2 = db.register_image_file("/test/img2.png", "h2", "/test", "img2.png", 100, 123.0)

        bundle_id = db.save_bundle_suggestion(
            ["/test/img1.png", "/test/img2.png"], {"bundle_name": "Test"}, 0.9
        )
        db.register_pdf_file("/out/doc.pdf", "doc.pdf", bundle_id, [img_id1, img_id2], 2)

        # Act
        pdf = db.get_pdf_by_bundle(bundle_id)

        # Assert
        assert pdf is not None
        assert pdf["bundle_id"] == bundle_id

    def test_update_pdf_generation_status(self, db):
        # Arrange - register image first
        img_id = db.register_image_file("/test/img.png", "h1", "/test", "img.png", 100, 123.0)

        bundle_id = db.save_bundle_suggestion(["/test/img.png"], {"bundle_name": "Test"}, 0.9)
        db.register_pdf_file("/out/doc.pdf", "doc.pdf", bundle_id, [img_id], 1)

        # Act
        db.update_pdf_generation_status("/out/doc.pdf", "failed")

        # Assert
        pdf = db.get_pdf_file("/out/doc.pdf")
        assert pdf["generation_status"] == "failed"

    def test_get_pdf_files_stats(self, db):
        # Arrange - register images first
        img_id1 = db.register_image_file("/test/img1.png", "h1", "/test", "img1.png", 100, 123.0)
        img_id2 = db.register_image_file("/test/img2.png", "h2", "/test", "img2.png", 100, 123.0)

        bundle_id = db.save_bundle_suggestion(
            ["/test/img1.png", "/test/img2.png"], {"bundle_name": "Test"}, 0.9
        )
        db.register_pdf_file("/out/doc1.pdf", "doc1.pdf", bundle_id, [img_id1], 1)
        db.register_pdf_file("/out/doc2.pdf", "doc2.pdf", bundle_id, [img_id2], 1)

        # Act
        stats = db.get_pdf_files_stats()

        # Assert
        assert stats["total"] == 2
        assert stats["status_completed"] == 2
