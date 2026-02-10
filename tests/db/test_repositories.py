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
    BundleImagesRepository,
    BundleRepository,
    DirectoryRepository,
    ImageFilesRepository,
)


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

    @pytest.fixture
    def image_repo(self, conn):
        return ImageFilesRepository(conn)

    def test_save_and_get(self, repo, image_repo):
        # Arrange - create image file first
        image_file_id = image_repo.register(
            file_path="/test/page.jpg",
            file_hash="abc123",
            directory_path="/test",
            filename="page.jpg",
            file_size=1024,
            file_mtime=1234567890.0,
        )
        extracted_metadata = {"document_type": "Invoice", "company": "Test Corp"}

        # Act
        analysis_id = repo.save(
            image_file_id=image_file_id,
            provider_name="ollama",
            model_name="test-model",
            prompt_text="Extract document metadata",
            response_text='{"document_type": "Invoice", "company": "Test Corp"}',
            confidence_score=0.95,
            processing_time_ms=100,
            extracted_metadata=extracted_metadata,
        )
        result = repo.get_latest_by_image_file_id(image_file_id)

        # Assert
        assert result is not None
        assert result["id"] == analysis_id
        assert result["provider_name"] == "ollama"
        assert result["model_name"] == "test-model"
        assert result["confidence_score"] == 0.95
        assert result["extracted_metadata"] == extracted_metadata

    def test_save_with_extracted_metadata(self, repo, image_repo):
        # Arrange - create image file first
        image_file_id = image_repo.register(
            file_path="/test/tax_doc.jpg",
            file_hash="xyz789",
            directory_path="/test",
            filename="tax_doc.jpg",
            file_size=2048,
            file_mtime=1234567890.0,
        )
        extracted_metadata = {
            "document_type": "Invoice",
            "company": "Test Corp",
            "tax_related": True,
        }

        # Act
        _ = repo.save(
            image_file_id=image_file_id,
            provider_name="ollama",
            model_name="test-model",
            prompt_text="Extract document metadata",
            response_text='{"document_type": "Invoice", "company": "Test Corp", "tax_related": true}',
            confidence_score=0.92,
            processing_time_ms=100,
            extracted_metadata=extracted_metadata,
        )
        result = repo.get_latest_by_image_file_id(image_file_id)

        # Assert
        assert result is not None
        assert result["extracted_metadata"]["tax_related"] is True
        assert result["extracted_metadata"]["company"] == "Test Corp"

    def test_save_with_had_error_flag(self, repo, image_repo):
        # Arrange - create image file first
        image_file_id = image_repo.register(
            file_path="/test/error_doc.jpg",
            file_hash="def456",
            directory_path="/test",
            filename="error_doc.jpg",
            file_size=1536,
            file_mtime=1234567890.0,
        )

        # Act
        _ = repo.save(
            image_file_id=image_file_id,
            provider_name="claude",
            model_name="claude-3",
            prompt_text="Extract document metadata",
            response_text="ERROR: Failed to analyze image",
            confidence_score=None,
            processing_time_ms=150,
            had_error=True,
        )
        result = repo.get_latest_by_image_file_id(image_file_id)

        # Assert
        assert result is not None
        assert result["had_error"] == 1  # SQLite stores boolean as integer
        assert result["confidence_score"] is None

    def test_save_with_prompt_text(self, repo, image_repo):
        # Arrange - create image file first
        image_file_id = image_repo.register(
            file_path="/test/with_prompt.jpg",
            file_hash="abc123",
            directory_path="/test",
            filename="with_prompt.jpg",
            file_size=2048,
            file_mtime=1234567890.0,
        )
        prompt_text = (
            "Analyze this document and extract metadata including company name and document type."
        )

        # Act
        _ = repo.save(
            image_file_id=image_file_id,
            provider_name="ollama",
            model_name="test-model",
            prompt_text=prompt_text,
            response_text='{"document_type": "Invoice", "company": "Test Corp"}',
            confidence_score=0.88,
            processing_time_ms=100,
        )
        result = repo.get_latest_by_image_file_id(image_file_id)

        # Assert
        assert result is not None
        assert result["prompt_text"] == prompt_text

    def test_save_multiple_analyses_same_image(self, repo, image_repo):
        # Arrange - create image file first, analyze twice with different providers
        image_file_id = image_repo.register(
            file_path="/test/multi_analysis.jpg",
            file_hash="multi123",
            directory_path="/test",
            filename="multi_analysis.jpg",
            file_size=3072,
            file_mtime=1234567890.0,
        )

        # Act - save two analyses for the same image
        analysis_id_1 = repo.save(
            image_file_id=image_file_id,
            provider_name="ollama",
            model_name="qwen2.5-vl",
            prompt_text="Extract metadata",
            response_text='{"company": "Corp A"}',
            confidence_score=0.85,
            processing_time_ms=120,
        )
        analysis_id_2 = repo.save(
            image_file_id=image_file_id,
            provider_name="claude",
            model_name="claude-3",
            prompt_text="Extract metadata",
            response_text='{"company": "Corp B"}',
            confidence_score=0.92,
            processing_time_ms=150,
        )

        results = repo.get_by_image_file_id(image_file_id)

        # Assert - verify both analyses are present
        assert len(results) == 2
        result_ids = {r["id"] for r in results}
        assert analysis_id_1 in result_ids
        assert analysis_id_2 in result_ids

    def test_get_all_with_filters(self, repo, image_repo):
        # Arrange - create two image files
        img1_id = image_repo.register("/p1.jpg", "h1", "/", "p1.jpg", 1024, 1234567890.0)
        img2_id = image_repo.register("/p2.jpg", "h2", "/", "p2.jpg", 1024, 1234567890.0)

        repo.save(img1_id, "ollama", "m1", "prompt", "response", 0.9, 100)
        repo.save(img2_id, "claude", "m2", "prompt", "response", 0.8, 100)

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

    @pytest.fixture
    def image_repo(self, conn):
        return ImageFilesRepository(conn)

    @pytest.fixture
    def bundle_images_repo(self, conn):
        return BundleImagesRepository(conn)

    def _create_test_images(self, image_repo, file_paths):
        """Helper to create test image records and return their IDs."""
        image_ids = []
        for path in file_paths:
            img_id = image_repo.register(
                file_path=path,
                file_hash=f"hash_{path}",
                directory_path=os.path.dirname(path),
                filename=os.path.basename(path),
                file_size=1024,
                file_mtime=1234567890.0,
            )
            image_ids.append(img_id)
        return image_ids

    def test_save_and_get_suggestions(self, repo, image_repo, bundle_images_repo):
        # Arrange
        file_paths = ["/p1.jpg", "/p2.jpg"]
        metadata = {"company": "Test Corp", "document_type": "Invoice"}
        image_ids = self._create_test_images(image_repo, file_paths)

        # Act
        bundle_id = repo.save_suggestion(metadata, 0.9)
        bundle_images_repo.add_images_bulk(bundle_id, image_ids)
        suggestions = repo.get_suggestions()

        # Assert
        assert bundle_id > 0
        assert len(suggestions) > 0

    def test_update_status(self, repo):
        # Arrange
        bundle_id = repo.save_suggestion({"company": "Test"}, 0.9)

        # Act
        repo.update_status(bundle_id, "accepted", "user_approved")

        # Assert - verify no exception raised
        assert bundle_id > 0

    def test_get_suggestions_with_filters(self, repo):
        # Arrange
        repo.save_suggestion({"bundle_name": "Test Bundle 1"}, 0.9)
        repo.save_suggestion({"bundle_name": "Test Bundle 2"}, 0.5)

        # Act
        high_confidence = repo.get_suggestions(min_confidence=0.8)
        all_suggestions = repo.get_suggestions()

        # Assert
        assert len(high_confidence) >= 1
        assert len(all_suggestions) >= 2

    def test_get_bundled_file_paths_returns_empty_set_when_no_bundles(self, repo):
        # Act
        bundled_paths = repo.get_bundled_file_paths()

        # Assert
        assert isinstance(bundled_paths, set)
        assert len(bundled_paths) == 0

    def test_get_bundled_file_paths_includes_accepted_bundles(
        self, repo, image_repo, bundle_images_repo
    ):
        # Arrange
        file_paths = ["/p1.jpg", "/p2.jpg"]
        image_ids = self._create_test_images(image_repo, file_paths)
        bundle_id = repo.save_suggestion({"bundle_name": "Test Bundle"}, 0.9)
        bundle_images_repo.add_images_bulk(bundle_id, image_ids)
        repo.update_status(bundle_id, "accepted")

        # Act
        bundled_paths = repo.get_bundled_file_paths()

        # Assert
        assert "/p1.jpg" in bundled_paths
        assert "/p2.jpg" in bundled_paths

    def test_get_bundled_file_paths_includes_completed_bundles(
        self, repo, image_repo, bundle_images_repo
    ):
        # Arrange
        file_paths = ["/p3.jpg", "/p4.jpg"]
        image_ids = self._create_test_images(image_repo, file_paths)
        bundle_id = repo.save_suggestion({"bundle_name": "Test Bundle"}, 0.9)
        bundle_images_repo.add_images_bulk(bundle_id, image_ids)
        repo.update_status(bundle_id, "completed")

        # Act
        bundled_paths = repo.get_bundled_file_paths()

        # Assert
        assert "/p3.jpg" in bundled_paths
        assert "/p4.jpg" in bundled_paths

    def test_get_bundled_file_paths_excludes_suggested_bundles(
        self, repo, image_repo, bundle_images_repo
    ):
        # Arrange
        file_paths = ["/p5.jpg"]
        image_ids = self._create_test_images(image_repo, file_paths)
        bundle_id = repo.save_suggestion({"bundle_name": "Test Bundle"}, 0.9)
        bundle_images_repo.add_images_bulk(bundle_id, image_ids)

        # Act
        bundled_paths = repo.get_bundled_file_paths()

        # Assert
        assert "/p5.jpg" not in bundled_paths

    def test_get_bundled_file_paths_excludes_rejected_bundles(
        self, repo, image_repo, bundle_images_repo
    ):
        # Arrange
        file_paths = ["/p6.jpg"]
        image_ids = self._create_test_images(image_repo, file_paths)
        bundle_id = repo.save_suggestion({"bundle_name": "Test Bundle"}, 0.9)
        bundle_images_repo.add_images_bulk(bundle_id, image_ids)
        repo.update_status(bundle_id, "rejected")

        # Act
        bundled_paths = repo.get_bundled_file_paths()

        # Assert
        assert "/p6.jpg" not in bundled_paths

    def test_get_bundled_file_paths_returns_distinct_paths(
        self, repo, image_repo, bundle_images_repo
    ):
        # Arrange - two bundles with overlapping files
        file_paths1 = ["/p7.jpg", "/p8.jpg"]
        file_paths2 = ["/p8.jpg", "/p9.jpg"]

        # Create all unique images
        all_paths = list(set(file_paths1 + file_paths2))
        path_to_id = {}
        for path in all_paths:
            img_id = image_repo.register(
                file_path=path,
                file_hash=f"hash_{path}",
                directory_path=os.path.dirname(path),
                filename=os.path.basename(path),
                file_size=1024,
                file_mtime=1234567890.0,
            )
            path_to_id[path] = img_id

        # Create bundles
        bundle_id1 = repo.save_suggestion({"bundle_name": "Test Bundle 1"}, 0.9)
        bundle_images_repo.add_images_bulk(bundle_id1, [path_to_id[p] for p in file_paths1])

        bundle_id2 = repo.save_suggestion({"bundle_name": "Test Bundle 2"}, 0.9)
        bundle_images_repo.add_images_bulk(bundle_id2, [path_to_id[p] for p in file_paths2])

        repo.update_status(bundle_id1, "accepted")
        repo.update_status(bundle_id2, "accepted")

        # Act
        bundled_paths = repo.get_bundled_file_paths()

        # Assert - should have 3 distinct paths, not 4
        assert len(bundled_paths) == 3
        assert "/p7.jpg" in bundled_paths
        assert "/p8.jpg" in bundled_paths
        assert "/p9.jpg" in bundled_paths


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


class TestImageFilesRepository:
    """Tests for ImageFilesRepository"""

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
        from db.repositories.image_files_repo import ImageFilesRepository

        return ImageFilesRepository(conn)

    def test_register_new_image(self, repo):
        # Act
        image_id = repo.register(
            file_path="/test/image1.png",
            file_hash="hash123",
            directory_path="/test",
            filename="image1.png",
            file_size=1024,
            file_mtime=1234567890.0,
        )

        # Assert
        assert image_id > 0
        image = repo.get_by_path("/test/image1.png")
        assert image is not None
        assert image["file_hash"] == "hash123"
        assert image["status"] == "registered"

    def test_register_replaces_existing(self, repo):
        # Arrange - register first time
        repo.register(
            "/test/image1.png",
            "hash123",
            "/test",
            "image1.png",
            1024,
            1234567890.0,
        )

        # Act - register again with different hash
        repo.register(
            "/test/image1.png",
            "hash456",
            "/test",
            "image1.png",
            2048,
            1234567891.0,
        )

        # Assert - should be replaced
        image = repo.get_by_path("/test/image1.png")
        assert image["file_hash"] == "hash456"
        assert image["file_size"] == 2048

    def test_get_by_path_nonexistent(self, repo):
        # Act
        image = repo.get_by_path("/nonexistent.png")

        # Assert
        assert image is None

    def test_get_by_directory(self, repo):
        # Arrange
        repo.register("/test/img1.png", "h1", "/test", "img1.png", 100, 123.0)
        repo.register("/test/img2.png", "h2", "/test", "img2.png", 200, 124.0)
        repo.register("/other/img3.png", "h3", "/other", "img3.png", 300, 125.0)

        # Act
        test_images = repo.get_by_directory("/test")

        # Assert
        assert len(test_images) == 2
        assert all(img["directory_path"] == "/test" for img in test_images)

    def test_get_by_status(self, repo):
        # Arrange
        repo.register("/test/img1.png", "h1", "/test", "img1.png", 100, 123.0)
        repo.register("/test/img2.png", "h2", "/test", "img2.png", 200, 124.0)
        repo.update_status("/test/img1.png", "analyzed")

        # Act
        registered = repo.get_by_status("registered")
        analyzed = repo.get_by_status("analyzed")

        # Assert
        assert len(registered) == 1
        assert registered[0]["file_path"] == "/test/img2.png"
        assert len(analyzed) == 1
        assert analyzed[0]["file_path"] == "/test/img1.png"

    def test_get_all_excludes_deleted(self, repo):
        # Arrange
        repo.register("/test/img1.png", "h1", "/test", "img1.png", 100, 123.0)
        repo.register("/test/img2.png", "h2", "/test", "img2.png", 200, 124.0)
        repo.mark_deleted("/test/img2.png")

        # Act
        all_images = repo.get_all()

        # Assert
        assert len(all_images) == 1
        assert all_images[0]["file_path"] == "/test/img1.png"

    def test_update_status_without_analysis_id(self, repo):
        # Arrange
        repo.register("/test/img1.png", "h1", "/test", "img1.png", 100, 123.0)

        # Act
        repo.update_status("/test/img1.png", "analyzing")

        # Assert
        image = repo.get_by_path("/test/img1.png")
        assert image["status"] == "analyzing"

    def test_update_status_with_different_status(self, repo):
        # Arrange
        repo.register("/test/img1.png", "h1", "/test", "img1.png", 100, 123.0)

        # Act
        repo.update_status("/test/img1.png", "analyzed")

        # Assert
        image = repo.get_by_path("/test/img1.png")
        assert image["status"] == "analyzed"

    def test_update_last_seen(self, repo):
        # Arrange
        repo.register("/test/img1.png", "h1", "/test", "img1.png", 100, 123.0)
        image_before = repo.get_by_path("/test/img1.png")
        discovered = image_before["discovered_at"]
        last_seen_before = image_before["last_seen_at"]

        # Act
        import time

        time.sleep(0.1)  # Ensure timestamp difference
        repo.update_last_seen("/test/img1.png")

        # Assert
        image_after = repo.get_by_path("/test/img1.png")
        assert image_after["discovered_at"] == discovered  # Should not change
        # Last seen may be same or later due to CURRENT_TIMESTAMP resolution
        assert image_after["last_seen_at"] >= last_seen_before

    def test_update_hash(self, repo):
        # Arrange
        repo.register("/test/img1.png", "old_hash", "/test", "img1.png", 100, 123.0)

        # Act
        repo.update_hash("/test/img1.png", "new_hash")

        # Assert
        image = repo.get_by_path("/test/img1.png")
        assert image["file_hash"] == "new_hash"

    def test_mark_deleted(self, repo):
        # Arrange
        repo.register("/test/img1.png", "h1", "/test", "img1.png", 100, 123.0)

        # Act
        repo.mark_deleted("/test/img1.png")

        # Assert
        image = repo.get_by_path("/test/img1.png")
        assert image["status"] == "deleted"
        assert image["deleted_at"] is not None

    def test_mark_deleted_batch(self, repo):
        # Arrange
        repo.register("/test/img1.png", "h1", "/test", "img1.png", 100, 123.0)
        repo.register("/test/img2.png", "h2", "/test", "img2.png", 200, 124.0)
        repo.register("/test/img3.png", "h3", "/test", "img3.png", 300, 125.0)

        # Act
        count = repo.mark_deleted_batch(["/test/img1.png", "/test/img2.png"])

        # Assert
        assert count == 2
        img1 = repo.get_by_path("/test/img1.png")
        img2 = repo.get_by_path("/test/img2.png")
        img3 = repo.get_by_path("/test/img3.png")

        assert img1["status"] == "deleted"
        assert img2["status"] == "deleted"
        assert img3["status"] == "registered"

    def test_mark_deleted_batch_empty(self, repo):
        # Act
        count = repo.mark_deleted_batch([])

        # Assert
        assert count == 0

    def test_set_output_filename(self, repo, conn):
        # Arrange
        img_id = repo.register("/test/img1.png", "h1", "/test", "img1.png", 100, 123.0)

        # Create metadata record first (output_filename is in metadata table)
        conn.execute("INSERT INTO metadata (image_file_id) VALUES (?)", (img_id,))
        conn.commit()

        # Act
        repo.set_output_filename("/test/img1.png", "output_doc.pdf")

        # Assert - check metadata table, not image_files
        result = conn.fetch_one_dict(
            "SELECT output_filename FROM metadata WHERE image_file_id = ?", (img_id,)
        )
        assert result is not None
        assert result["output_filename"] == "output_doc.pdf"

    def test_get_stats(self, repo):
        # Arrange
        repo.register("/test/img1.png", "h1", "/test", "img1.png", 100, 123.0)
        repo.register("/test/img2.png", "h2", "/test", "img2.png", 200, 124.0)
        repo.register("/test/img3.png", "h3", "/test", "img3.png", 300, 125.0)
        repo.register("/test/img4.png", "h4", "/test", "img4.png", 400, 126.0)

        repo.update_status("/test/img1.png", "analyzed")
        repo.update_status("/test/img2.png", "bundled")
        repo.mark_deleted("/test/img3.png")
        # img4 remains "registered"

        # Act
        stats = repo.get_stats()

        # Assert
        assert stats["total"] == 3  # Excludes deleted
        assert stats["status_registered"] == 1
        assert stats["status_analyzed"] == 1
        assert stats["status_bundled"] == 1
        assert stats["status_deleted"] == 1

    def test_status_transitions(self, repo):
        # Arrange
        repo.register("/test/img1.png", "h1", "/test", "img1.png", 100, 123.0)

        # Act & Assert - registered → analyzing
        repo.update_status("/test/img1.png", "analyzing")
        img = repo.get_by_path("/test/img1.png")
        assert img["status"] == "analyzing"

        # analyzing → analyzed
        repo.update_status("/test/img1.png", "analyzed")
        img = repo.get_by_path("/test/img1.png")
        assert img["status"] == "analyzed"

        # analyzed → bundled
        repo.update_status("/test/img1.png", "bundled")
        img = repo.get_by_path("/test/img1.png")
        assert img["status"] == "bundled"

        # bundled → deleted
        repo.mark_deleted("/test/img1.png")
        img = repo.get_by_path("/test/img1.png")
        assert img["status"] == "deleted"
        assert img["deleted_at"] is not None

    def test_get_all_with_analysis_no_analysis(self, repo):
        """Test get_all_with_analysis returns images without analysis data."""
        # Arrange - register images without analysis
        repo.register("/test/img1.png", "h1", "/test", "img1.png", 100, 123.0)
        repo.register("/test/img2.png", "h2", "/test", "img2.png", 200, 124.0)

        # Act
        results = repo.get_all_with_analysis()

        # Assert
        assert len(results) == 2
        assert results[0]["file_path"] in ["/test/img1.png", "/test/img2.png"]
        assert results[0]["status"] == "registered"
        # Metadata fields should be None (no metadata record created)
        assert results[0]["document_type"] is None
        assert results[0]["company"] is None

    def test_get_all_with_analysis_with_analysis(self, repo, conn):
        """Test get_all_with_analysis returns images with joined analysis data."""
        from db.repositories import AnalysisRepository
        from db.repositories.metadata_repo import MetadataRepository

        # Arrange - register image and add analysis
        img_id = repo.register("/test/img3.png", "h3", "/test", "img3.png", 100, 123.0)

        # Create analysis entry with new signature
        analysis_repo = AnalysisRepository(conn)
        analysis_id = analysis_repo.save(
            image_file_id=img_id,
            provider_name="test_provider",
            model_name="test_model",
            prompt_text="Extract metadata",
            response_text='{"document_type": "Invoice", "company": "ACME Corp"}',
            confidence_score=0.95,
            processing_time_ms=1500,
        )

        # Create metadata entry
        metadata_repo = MetadataRepository(conn)
        metadata_repo.create_from_analysis(
            image_file_id=img_id,
            analysis_result_id=analysis_id,
            normalized_metadata={
                "document_type": "Invoice",
                "company": "ACME Corp",
                "document_date": "2024-01-15",
                "confidence_score": 0.95,
            },
        )

        # Update status
        repo.update_status("/test/img3.png", "analyzed")

        # Act
        results = repo.get_all_with_analysis()

        # Assert
        assert len(results) == 1
        result = results[0]
        assert result["file_path"] == "/test/img3.png"
        assert result["status"] == "analyzed"
        # Joined metadata should be present
        assert result["document_type"] == "Invoice"
        assert result["company"] == "ACME Corp"
        assert result["document_date"] == "2024-01-15"
        assert result["confidence_score"] == 0.95
        assert result["provider_name"] == "test_provider"
        assert result["model_name"] == "test_model"

    def test_get_all_with_analysis_mixed(self, repo, conn):
        """Test get_all_with_analysis returns both analyzed and unanalyzed images."""
        from db.repositories import AnalysisRepository
        from db.repositories.metadata_repo import MetadataRepository

        # Arrange - register multiple images, analyze only one
        img4_id = repo.register("/test/img4.png", "h4", "/test", "img4.png", 100, 123.0)
        _ = repo.register("/test/img5.png", "h5", "/test", "img5.png", 200, 124.0)

        # Analyze only img4
        analysis_repo = AnalysisRepository(conn)
        analysis_id = analysis_repo.save(
            image_file_id=img4_id,
            provider_name="test_provider",
            model_name="test_model",
            prompt_text="Extract metadata",
            response_text='{"document_type": "Receipt", "company": "Store"}',
            confidence_score=0.88,
            processing_time_ms=1000,
        )

        # Create metadata for img4
        metadata_repo = MetadataRepository(conn)
        metadata_repo.create_from_analysis(
            image_file_id=img4_id,
            analysis_result_id=analysis_id,
            normalized_metadata={"document_type": "Receipt", "company": "Store"},
        )

        repo.update_status("/test/img4.png", "analyzed")

        # Act
        results = repo.get_all_with_analysis()

        # Assert
        assert len(results) == 2

        # Find each result
        img4 = next((r for r in results if r["file_path"] == "/test/img4.png"), None)
        img5 = next((r for r in results if r["file_path"] == "/test/img5.png"), None)

        assert img4 is not None
        assert img5 is not None

        # img4 should have metadata
        assert img4["document_type"] == "Receipt"
        assert img4["company"] == "Store"

        # img5 should NOT have metadata (no metadata record created)
        assert img5["document_type"] is None
        assert img5["company"] is None

    def test_get_all_with_analysis_filters(self, repo, conn):
        """Test get_all_with_analysis respects directory and provider filters."""
        from db.repositories import AnalysisRepository
        from db.repositories.metadata_repo import MetadataRepository

        # Arrange - register images in different directories with different providers
        img1_id = repo.register("/test1/img1.png", "h1", "/test1", "img1.png", 100, 123.0)
        img2_id = repo.register("/test2/img2.png", "h2", "/test2", "img2.png", 200, 124.0)

        analysis_repo = AnalysisRepository(conn)
        metadata_repo = MetadataRepository(conn)

        # Analyze both with different providers
        analysis1_id = analysis_repo.save(
            image_file_id=img1_id,
            provider_name="provider_a",
            model_name="model",
            prompt_text="Extract",
            response_text="{}",
            confidence_score=0.9,
            processing_time_ms=1000,
        )
        analysis2_id = analysis_repo.save(
            image_file_id=img2_id,
            provider_name="provider_b",
            model_name="model",
            prompt_text="Extract",
            response_text="{}",
            confidence_score=0.9,
            processing_time_ms=1000,
        )

        # Create metadata records
        metadata_repo.create_from_analysis(img1_id, analysis1_id, {})
        metadata_repo.create_from_analysis(img2_id, analysis2_id, {})

        repo.update_status("/test1/img1.png", "analyzed")
        repo.update_status("/test2/img2.png", "analyzed")

        # Act & Assert - filter by directory
        results_dir1 = repo.get_all_with_analysis(directory_filter="/test1")
        assert len(results_dir1) == 1
        assert results_dir1[0]["file_path"] == "/test1/img1.png"

        # Act & Assert - filter by provider
        results_provider_b = repo.get_all_with_analysis(provider_filter="provider_b")
        assert len(results_provider_b) == 1
        assert results_provider_b[0]["file_path"] == "/test2/img2.png"
        assert results_provider_b[0]["provider_name"] == "provider_b"


class TestPdfFilesRepository:
    """Tests for PdfFilesRepository"""

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
        from db.repositories.pdf_files_repo import PdfFilesRepository

        return PdfFilesRepository(conn)

    @pytest.fixture
    def bundle_id(self, conn):
        """Create a test bundle and return its ID."""
        from db.repositories.bundle_repo import BundleRepository

        bundle_repo = BundleRepository(conn)
        return bundle_repo.save_suggestion(
            {"company": "Test Co", "document_type": "Invoice"},
            0.95,
        )

    def test_register_new_pdf(self, repo, bundle_id):
        # Act
        pdf_id = repo.register(
            pdf_path="/output/test_doc.pdf",
            pdf_filename="test_doc.pdf",
            bundle_id=bundle_id,
            page_count=3,
            file_hash="hash123",
            file_size=102400,
        )

        # Assert
        assert pdf_id > 0
        pdf = repo.get_by_path("/output/test_doc.pdf")
        assert pdf is not None
        assert pdf["pdf_filename"] == "test_doc.pdf"
        assert pdf["bundle_id"] == bundle_id
        assert pdf["page_count"] == 3
        assert pdf["file_hash"] == "hash123"
        assert pdf["file_size"] == 102400
        assert pdf["generation_status"] == "completed"

    def test_register_replaces_existing(self, repo, bundle_id):
        # Arrange - register first time
        repo.register("/output/test.pdf", "test.pdf", bundle_id, 2, "hash1", 1000)

        # Act - register again with different data
        repo.register("/output/test.pdf", "test.pdf", bundle_id, 3, "hash2", 2000)

        # Assert - should be replaced
        pdf = repo.get_by_path("/output/test.pdf")
        assert pdf["page_count"] == 3
        assert pdf["file_hash"] == "hash2"

    def test_register_without_optional_fields(self, repo, bundle_id):
        # Act
        pdf_id = repo.register(
            pdf_path="/output/doc.pdf",
            pdf_filename="doc.pdf",
            bundle_id=bundle_id,
            page_count=1,
        )

        # Assert
        assert pdf_id > 0
        pdf = repo.get_by_path("/output/doc.pdf")
        assert pdf["file_hash"] is None
        assert pdf["file_size"] is None

    def test_get_by_path_nonexistent(self, repo):
        # Act
        pdf = repo.get_by_path("/nonexistent.pdf")

        # Assert
        assert pdf is None

    def test_get_by_bundle(self, repo, bundle_id):
        # Arrange
        repo.register("/out/doc.pdf", "doc.pdf", bundle_id, 2)

        # Act
        pdf = repo.get_by_bundle(bundle_id)

        # Assert
        assert pdf is not None
        assert pdf["bundle_id"] == bundle_id

    def test_get_by_bundle_nonexistent(self, repo):
        # Act
        pdf = repo.get_by_bundle(99999)

        # Assert
        assert pdf is None

    def test_update_generation_status(self, repo, bundle_id):
        # Arrange
        repo.register("/out/doc.pdf", "doc.pdf", bundle_id, 1)

        # Act
        repo.update_generation_status("/out/doc.pdf", "failed")

        # Assert
        pdf = repo.get_by_path("/out/doc.pdf")
        assert pdf["generation_status"] == "failed"

    def test_get_all(self, repo, bundle_id, conn):
        # Arrange
        from db.repositories.bundle_repo import BundleRepository

        bundle_repo = BundleRepository(conn)
        bundle_id2 = bundle_repo.save_suggestion({"company": "Other Co"}, 0.8)

        repo.register("/out/doc1.pdf", "doc1.pdf", bundle_id, 2)
        repo.register("/out/doc2.pdf", "doc2.pdf", bundle_id2, 1)

        # Act
        all_pdfs = repo.get_all()

        # Assert
        assert len(all_pdfs) == 2
        # Should be ordered by generated_at DESC (most recent first)

    def test_get_stats(self, repo, bundle_id):
        # Arrange
        repo.register("/out/doc1.pdf", "doc1.pdf", bundle_id, 1)
        repo.register("/out/doc2.pdf", "doc2.pdf", bundle_id, 1)
        repo.register("/out/doc3.pdf", "doc3.pdf", bundle_id, 1)

        repo.update_generation_status("/out/doc1.pdf", "generating")
        repo.update_generation_status("/out/doc2.pdf", "failed")
        # doc3 remains "completed"

        # Act
        stats = repo.get_stats()

        # Assert
        assert stats["total"] == 3
        assert stats["status_generating"] == 1
        assert stats["status_failed"] == 1
        assert stats["status_completed"] == 1
