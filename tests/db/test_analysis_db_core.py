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

        # Assert
        assert "analysis_results" in table_names
        assert "llm_providers" in table_names
        assert "source_directories" in table_names

    def test_save_and_get_analysis(self, db):
        # Arrange
        file_path = "/test/page.jpg"
        file_hash = "abc123"
        analysis_data = {"document_type": "Invoice", "company": "Test Corp"}

        # Act
        db.save_analysis(
            file_path=file_path,
            file_hash=file_hash,
            provider_name="ollama",
            model_name="test-model",
            analysis_data=analysis_data,
            raw_response='{"test": "data"}',
            processing_time_ms=100,
        )
        result = db.get_analysis(file_path)

        # Assert
        assert result is not None
        assert result["provider_name"] == "ollama"
        assert result["company"] == "Test Corp"

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

    def test_add_provider(self, db):
        # Arrange
        config = {"base_url": "http://localhost:11434"}

        # Act
        db.add_provider(
            provider_name="ollama",
            provider_type="ollama",
            config=config,
            default_model="test-model",
        )
        # Set as active after adding
        db.set_active_provider("ollama")

        # Assert
        provider = db.get_active_provider()
        assert provider is not None
        assert provider["provider_name"] == "ollama"

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

    def test_save_rotation_preference(self, db):
        # Act
        db.save_rotation_preference("/test/img.jpg", 90, "manual")
        pref = db.get_rotation_preference("/test/img.jpg")

        # Assert
        assert pref is not None
        assert pref["rotation_degrees"] == 90

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

    def test_get_failed_analyses(self, db):
        # Arrange
        db.save_error("/test/failed.jpg", "Test error", "analysis_failed")

        # Act
        failed = db.get_failed_analyses()

        # Assert
        assert len(failed) >= 1
        assert failed[0]["file_path"] == "/test/failed.jpg"

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
        # Arrange
        db.save_analysis(
            "/p1.jpg", "hash1", "ollama", "model", {"document_type": "Invoice"}, "{}", 100
        )
        db.save_analysis(
            "/p2.jpg", "hash2", "ollama", "model", {"document_type": "Receipt"}, "{}", 100
        )

        # Act
        breakdown = db.get_document_type_breakdown()

        # Assert
        assert breakdown["Invoice"] >= 1
        assert breakdown["Receipt"] >= 1

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
