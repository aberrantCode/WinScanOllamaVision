"""Tests for AnalysisRepository"""

import json
import sqlite3
from datetime import datetime
from unittest.mock import patch

import pytest

from db.connection import DatabaseConnection
from db.repositories.analysis_repo import AnalysisRepository
from db.schema import create_all_tables


@pytest.fixture
def db_conn(tmp_path):
    """Create a temporary database connection for testing."""
    db_path = tmp_path / "test_analysis.db"
    conn = DatabaseConnection(str(db_path))
    create_all_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def repo(db_conn):
    """Create an AnalysisRepository instance for testing."""
    return AnalysisRepository(db_conn)


@pytest.fixture
def sample_image_file_id(db_conn):
    """Create a sample image file record and return its ID."""
    cursor = db_conn.connection.cursor()
    cursor.execute(
        """
        INSERT INTO image_files (
            file_path, file_hash, directory_path, filename,
            file_size, file_mtime, discovered_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/test/image.png",
            "abc123",
            "/test",
            "image.png",
            1024,
            1234567890.0,
            datetime.now().isoformat(),
        ),
    )
    db_conn.connection.commit()
    return cursor.lastrowid


class TestAnalysisRepositoryBasics:
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


class TestAnalysisSave:
    """Test save() method for creating analysis records."""

    def test_save_creates_new_record(self, repo, sample_image_file_id):
        """Test saving a new analysis record."""
        analysis_id = repo.save(
            image_file_id=sample_image_file_id,
            provider_name="ollama",
            model_name="qwen2.5-vl",
            prompt_text="Analyze this document",
            response_text="This is a test document",
            confidence_score=0.95,
            processing_time_ms=1500,
            had_error=False,
            extracted_metadata={"title": "Test Doc", "date": "2024-01-01"},
            model_options={"temperature": 0.7},
        )

        assert analysis_id > 0

        # Verify record was created
        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT * FROM analysis_results WHERE id = ?", (analysis_id,))
        record = cursor.fetchone()

        assert record is not None
        # Column order: id, image_file_id, provider_name, model_name, model_options,
        #               prompt_text, response_text, extracted_metadata,
        #               confidence_score, had_error, analyzed_at, processing_time_ms
        assert record[1] == sample_image_file_id  # image_file_id
        assert record[2] == "ollama"  # provider_name
        assert record[3] == "qwen2.5-vl"  # model_name
        assert json.loads(record[4]) == {"temperature": 0.7}  # model_options
        assert record[5] == "Analyze this document"  # prompt_text
        assert record[6] == "This is a test document"  # response_text
        assert json.loads(record[7]) == {
            "title": "Test Doc",
            "date": "2024-01-01",
        }  # extracted_metadata
        assert record[8] == 0.95  # confidence_score
        assert record[9] == 0  # had_error (False = 0)
        # record[10] is analyzed_at timestamp
        assert record[11] == 1500  # processing_time_ms

    def test_save_with_null_optional_fields(self, repo, sample_image_file_id):
        """Test saving with None for optional fields."""
        analysis_id = repo.save(
            image_file_id=sample_image_file_id,
            provider_name="claude_cli",
            model_name="claude-3-5-sonnet",
            prompt_text="Analyze",
            response_text="Result",
            confidence_score=None,
            processing_time_ms=500,
            had_error=False,
            extracted_metadata=None,
            model_options=None,
        )

        assert analysis_id > 0

        # Verify NULL fields
        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT * FROM analysis_results WHERE id = ?", (analysis_id,))
        record = cursor.fetchone()

        # Column order: id, image_file_id, provider_name, model_name, model_options,
        #               prompt_text, response_text, extracted_metadata,
        #               confidence_score, had_error, analyzed_at, processing_time_ms
        assert record[4] is None  # model_options
        assert record[7] is None  # extracted_metadata
        assert record[8] is None  # confidence_score

    def test_save_with_error_flag(self, repo, sample_image_file_id):
        """Test saving an analysis with error flag set."""
        analysis_id = repo.save(
            image_file_id=sample_image_file_id,
            provider_name="gemini_cli",
            model_name="gemini-2.0-flash",
            prompt_text="Analyze",
            response_text="Error: Failed to process",
            confidence_score=0.0,
            processing_time_ms=100,
            had_error=True,
        )

        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT had_error FROM analysis_results WHERE id = ?", (analysis_id,))
        had_error = cursor.fetchone()[0]

        assert had_error == 1  # True = 1

    def test_save_handles_integrity_error(self, repo, db_conn):
        """Test save handles IntegrityError for invalid foreign key."""
        # Enable foreign key constraints for this test
        db_conn.connection.execute("PRAGMA foreign_keys = ON")
        db_conn.commit()

        with pytest.raises(ValueError, match="Invalid image_file_id"):
            repo.save(
                image_file_id=99999,  # Non-existent image_file_id
                provider_name="ollama",
                model_name="test",
                prompt_text="test",
                response_text="test",
                confidence_score=0.5,
                processing_time_ms=100,
            )

    def test_save_handles_operational_error(self, repo, sample_image_file_id):
        """Test save handles OperationalError by attempting to insert with read-only database."""
        # Mock execute to raise OperationalError
        with patch.object(
            repo.conn, "execute", side_effect=sqlite3.OperationalError("database is locked")
        ), pytest.raises(sqlite3.OperationalError, match="Database operation failed"):
            repo.save(
                image_file_id=sample_image_file_id,
                provider_name="ollama",
                model_name="test",
                prompt_text="test",
                response_text="test",
                confidence_score=0.5,
                processing_time_ms=100,
            )

    def test_save_handles_generic_error(self, repo, sample_image_file_id):
        """Test save handles generic sqlite3.Error."""
        # Mock execute to raise generic Error
        with patch.object(
            repo.conn, "execute", side_effect=sqlite3.Error("Generic database error")
        ), pytest.raises(sqlite3.Error, match="Failed to save analysis"):
            repo.save(
                image_file_id=sample_image_file_id,
                provider_name="ollama",
                model_name="test",
                prompt_text="test",
                response_text="test",
                confidence_score=0.5,
                processing_time_ms=100,
            )


class TestAnalysisRetrieval:
    """Test retrieval methods for analysis records."""

    def test_get_by_image_file_id_returns_all_analyses(self, repo, sample_image_file_id):
        """Test retrieving all analyses for an image file."""
        # Create multiple analyses for same image
        id1 = repo.save(
            image_file_id=sample_image_file_id,
            provider_name="ollama",
            model_name="qwen2.5-vl",
            prompt_text="First analysis",
            response_text="Result 1",
            confidence_score=0.8,
            processing_time_ms=1000,
        )

        id2 = repo.save(
            image_file_id=sample_image_file_id,
            provider_name="claude_cli",
            model_name="claude-3-5-sonnet",
            prompt_text="Second analysis",
            response_text="Result 2",
            confidence_score=0.9,
            processing_time_ms=1500,
        )

        analyses = repo.get_by_image_file_id(sample_image_file_id)

        assert len(analyses) == 2
        # Verify both IDs are present
        ids = [a["id"] for a in analyses]
        assert id1 in ids
        assert id2 in ids
        # Verify both provider names are present
        providers = [a["provider_name"] for a in analyses]
        assert "ollama" in providers
        assert "claude_cli" in providers

    def test_get_by_image_file_id_returns_empty_for_no_analyses(self, repo, sample_image_file_id):
        """Test retrieving analyses for image with no analyses."""
        analyses = repo.get_by_image_file_id(sample_image_file_id)
        assert analyses == []

    def test_get_latest_by_image_file_id_returns_newest(self, repo, sample_image_file_id):
        """Test retrieving the latest analysis for an image file."""
        # Create multiple analyses
        old_id = repo.save(
            image_file_id=sample_image_file_id,
            provider_name="ollama",
            model_name="old-model",
            prompt_text="Old analysis",
            response_text="Old result",
            confidence_score=0.7,
            processing_time_ms=1000,
        )

        latest_id = repo.save(
            image_file_id=sample_image_file_id,
            provider_name="claude_cli",
            model_name="new-model",
            prompt_text="Latest analysis",
            response_text="Latest result",
            confidence_score=0.95,
            processing_time_ms=1500,
        )

        latest = repo.get_latest_by_image_file_id(sample_image_file_id)

        assert latest is not None
        # Should return one of the two records (both valid if timestamps are identical)
        assert latest["id"] in [old_id, latest_id]
        assert latest["provider_name"] in ["ollama", "claude_cli"]
        assert latest["model_name"] in ["old-model", "new-model"]

    def test_get_latest_by_image_file_id_returns_none_for_no_analyses(
        self, repo, sample_image_file_id
    ):
        """Test retrieving latest analysis when none exist."""
        latest = repo.get_latest_by_image_file_id(sample_image_file_id)
        assert latest is None

    def test_get_by_id_returns_correct_record(self, repo, sample_image_file_id):
        """Test retrieving analysis by specific ID."""
        analysis_id = repo.save(
            image_file_id=sample_image_file_id,
            provider_name="gemini_cli",
            model_name="gemini-2.0-flash",
            prompt_text="Test prompt",
            response_text="Test response",
            confidence_score=0.88,
            processing_time_ms=1200,
            extracted_metadata={"key": "value"},
        )

        analysis = repo.get_by_id(analysis_id)

        assert analysis is not None
        assert analysis["id"] == analysis_id
        assert analysis["provider_name"] == "gemini_cli"
        assert analysis["model_name"] == "gemini-2.0-flash"
        assert analysis["extracted_metadata"] == {"key": "value"}

    def test_get_by_id_returns_none_for_nonexistent(self, repo):
        """Test retrieving analysis by non-existent ID."""
        analysis = repo.get_by_id(99999)
        assert analysis is None

    def test_get_all_returns_all_analyses(self, repo, sample_image_file_id):
        """Test retrieving all analyses without filters."""
        # Create multiple analyses
        repo.save(
            image_file_id=sample_image_file_id,
            provider_name="ollama",
            model_name="model1",
            prompt_text="prompt1",
            response_text="response1",
            confidence_score=0.8,
            processing_time_ms=1000,
        )

        repo.save(
            image_file_id=sample_image_file_id,
            provider_name="claude_cli",
            model_name="model2",
            prompt_text="prompt2",
            response_text="response2",
            confidence_score=0.9,
            processing_time_ms=1500,
        )

        all_analyses = repo.get_all()

        assert len(all_analyses) >= 2

    def test_get_all_filters_by_provider(self, repo, sample_image_file_id):
        """Test filtering analyses by provider name."""
        repo.save(
            image_file_id=sample_image_file_id,
            provider_name="ollama",
            model_name="model1",
            prompt_text="prompt",
            response_text="response",
            confidence_score=0.8,
            processing_time_ms=1000,
        )

        repo.save(
            image_file_id=sample_image_file_id,
            provider_name="claude_cli",
            model_name="model2",
            prompt_text="prompt",
            response_text="response",
            confidence_score=0.9,
            processing_time_ms=1500,
        )

        ollama_analyses = repo.get_all(provider_filter="ollama")

        assert len(ollama_analyses) == 1
        assert ollama_analyses[0]["provider_name"] == "ollama"

    def test_get_all_filters_by_error_status(self, repo, sample_image_file_id):
        """Test filtering analyses by error status."""
        repo.save(
            image_file_id=sample_image_file_id,
            provider_name="ollama",
            model_name="model1",
            prompt_text="prompt",
            response_text="success",
            confidence_score=0.8,
            processing_time_ms=1000,
            had_error=False,
        )

        repo.save(
            image_file_id=sample_image_file_id,
            provider_name="ollama",
            model_name="model1",
            prompt_text="prompt",
            response_text="error result",
            confidence_score=0.0,
            processing_time_ms=100,
            had_error=True,
        )

        error_analyses = repo.get_all(had_error=True)
        success_analyses = repo.get_all(had_error=False)

        assert len(error_analyses) == 1
        assert error_analyses[0]["had_error"] == 1  # SQLite stores booleans as integers
        assert len(success_analyses) == 1
        assert success_analyses[0]["had_error"] == 0

    def test_get_all_respects_limit(self, repo, sample_image_file_id):
        """Test limiting number of results returned."""
        # Create 5 analyses
        for i in range(5):
            repo.save(
                image_file_id=sample_image_file_id,
                provider_name="ollama",
                model_name=f"model{i}",
                prompt_text="prompt",
                response_text="response",
                confidence_score=0.8,
                processing_time_ms=1000,
            )

        limited_analyses = repo.get_all(limit=3)

        assert len(limited_analyses) == 3

    def test_get_all_combines_filters(self, repo, sample_image_file_id):
        """Test using multiple filters together."""
        # Create ollama success
        repo.save(
            image_file_id=sample_image_file_id,
            provider_name="ollama",
            model_name="model1",
            prompt_text="prompt",
            response_text="success",
            confidence_score=0.8,
            processing_time_ms=1000,
            had_error=False,
        )

        # Create ollama error
        repo.save(
            image_file_id=sample_image_file_id,
            provider_name="ollama",
            model_name="model1",
            prompt_text="prompt",
            response_text="error",
            confidence_score=0.0,
            processing_time_ms=100,
            had_error=True,
        )

        # Create claude success
        repo.save(
            image_file_id=sample_image_file_id,
            provider_name="claude_cli",
            model_name="model2",
            prompt_text="prompt",
            response_text="success",
            confidence_score=0.9,
            processing_time_ms=1500,
            had_error=False,
        )

        filtered = repo.get_all(provider_filter="ollama", had_error=False)

        assert len(filtered) == 1
        assert filtered[0]["provider_name"] == "ollama"
        assert filtered[0]["had_error"] == 0  # SQLite stores False as 0


class TestAnalysisStatistics:
    """Test statistics methods for analysis data."""

    def test_count_by_status_returns_correct_counts(self, repo, sample_image_file_id):
        """Test counting analyses by success/error status."""
        # Create 3 successful analyses
        for i in range(3):
            repo.save(
                image_file_id=sample_image_file_id,
                provider_name="ollama",
                model_name=f"model{i}",
                prompt_text="prompt",
                response_text="success",
                confidence_score=0.8,
                processing_time_ms=1000,
                had_error=False,
            )

        # Create 2 error analyses
        for i in range(2):
            repo.save(
                image_file_id=sample_image_file_id,
                provider_name="ollama",
                model_name=f"model{i}",
                prompt_text="prompt",
                response_text="error",
                confidence_score=0.0,
                processing_time_ms=100,
                had_error=True,
            )

        counts = repo.count_by_status()

        assert counts["successful"] == 3
        assert counts["errors"] == 2
        assert counts["total"] == 5

    def test_count_by_status_returns_zero_for_empty_table(self, repo):
        """Test counting when no analyses exist."""
        counts = repo.count_by_status()

        assert counts["successful"] == 0
        assert counts["errors"] == 0
        assert counts["total"] == 0


class TestAnalysisDeletion:
    """Test deletion methods for analysis records."""

    def test_delete_by_image_file_id_removes_all_analyses(self, repo, sample_image_file_id):
        """Test deleting all analyses for an image file."""
        # Create multiple analyses
        repo.save(
            image_file_id=sample_image_file_id,
            provider_name="ollama",
            model_name="model1",
            prompt_text="prompt",
            response_text="response",
            confidence_score=0.8,
            processing_time_ms=1000,
        )

        repo.save(
            image_file_id=sample_image_file_id,
            provider_name="claude_cli",
            model_name="model2",
            prompt_text="prompt",
            response_text="response",
            confidence_score=0.9,
            processing_time_ms=1500,
        )

        # Verify analyses exist
        before_delete = repo.get_by_image_file_id(sample_image_file_id)
        assert len(before_delete) == 2

        # Delete
        repo.delete_by_image_file_id(sample_image_file_id)

        # Verify analyses are gone
        after_delete = repo.get_by_image_file_id(sample_image_file_id)
        assert len(after_delete) == 0

    def test_delete_by_image_file_id_handles_operational_error(self, repo, sample_image_file_id):
        """Test delete handles OperationalError."""
        # Mock execute to raise OperationalError
        with patch.object(
            repo.conn, "execute", side_effect=sqlite3.OperationalError("database is locked")
        ), pytest.raises(sqlite3.OperationalError, match="database is locked"):
            repo.delete_by_image_file_id(sample_image_file_id)

    def test_delete_by_image_file_id_handles_generic_error(self, repo, sample_image_file_id):
        """Test delete handles generic sqlite3.Error."""
        # Mock execute to raise generic Error
        with patch.object(repo.conn, "execute", side_effect=sqlite3.Error("Generic delete error")):
            with pytest.raises(sqlite3.Error, match="Generic delete error"):
                repo.delete_by_image_file_id(sample_image_file_id)


class TestAnalysisEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_save_with_very_long_text_fields(self, repo, sample_image_file_id):
        """Test saving with very long text fields."""
        long_text = "x" * 10000  # 10KB text

        analysis_id = repo.save(
            image_file_id=sample_image_file_id,
            provider_name="ollama",
            model_name="model",
            prompt_text=long_text,
            response_text=long_text,
            confidence_score=0.5,
            processing_time_ms=5000,
        )

        assert analysis_id > 0

        # Verify it was saved correctly
        analysis = repo.get_by_id(analysis_id)
        assert len(analysis["prompt_text"]) == 10000
        assert len(analysis["response_text"]) == 10000

    def test_save_with_complex_nested_json(self, repo, sample_image_file_id):
        """Test saving with deeply nested JSON metadata."""
        complex_metadata = {
            "level1": {
                "level2": {
                    "level3": {
                        "array": [1, 2, 3],
                        "nested_obj": {"key": "value"},
                    }
                }
            }
        }

        analysis_id = repo.save(
            image_file_id=sample_image_file_id,
            provider_name="ollama",
            model_name="model",
            prompt_text="prompt",
            response_text="response",
            confidence_score=0.5,
            processing_time_ms=1000,
            extracted_metadata=complex_metadata,
        )

        # Verify JSON was preserved
        analysis = repo.get_by_id(analysis_id)
        assert analysis["extracted_metadata"] == complex_metadata

    def test_get_all_with_no_results(self, repo):
        """Test get_all when filters match no records."""
        analyses = repo.get_all(provider_filter="nonexistent_provider")
        assert analyses == []

    def test_delete_nonexistent_image_file_id(self, repo):
        """Test deleting analyses for non-existent image file (should not error)."""
        # Should not raise error
        repo.delete_by_image_file_id(99999)

    def test_save_with_zero_processing_time(self, repo, sample_image_file_id):
        """Test saving with zero processing time."""
        analysis_id = repo.save(
            image_file_id=sample_image_file_id,
            provider_name="ollama",
            model_name="model",
            prompt_text="prompt",
            response_text="response",
            confidence_score=0.5,
            processing_time_ms=0,  # Zero processing time
        )

        analysis = repo.get_by_id(analysis_id)
        assert analysis["processing_time_ms"] == 0

    def test_save_with_negative_confidence_score(self, repo, sample_image_file_id):
        """Test saving with negative confidence score (edge case)."""
        analysis_id = repo.save(
            image_file_id=sample_image_file_id,
            provider_name="ollama",
            model_name="model",
            prompt_text="prompt",
            response_text="response",
            confidence_score=-0.5,  # Negative score
            processing_time_ms=1000,
        )

        analysis = repo.get_by_id(analysis_id)
        assert analysis["confidence_score"] == -0.5

    def test_save_with_confidence_score_above_one(self, repo, sample_image_file_id):
        """Test saving with confidence score > 1.0 (edge case)."""
        analysis_id = repo.save(
            image_file_id=sample_image_file_id,
            provider_name="ollama",
            model_name="model",
            prompt_text="prompt",
            response_text="response",
            confidence_score=1.5,  # > 1.0
            processing_time_ms=1000,
        )

        analysis = repo.get_by_id(analysis_id)
        assert analysis["confidence_score"] == 1.5

    def test_save_raises_error_when_lastrowid_is_none(
        self, repo, sample_image_file_id, monkeypatch
    ):
        """Test save raises error when cursor.lastrowid is None."""

        # Mock execute to return a cursor with lastrowid = None
        class MockCursor:
            lastrowid = None

        def mock_execute(*args, **kwargs):
            return MockCursor()

        monkeypatch.setattr(repo.conn, "execute", mock_execute)
        monkeypatch.setattr(repo.conn, "commit", lambda: None)

        with pytest.raises(sqlite3.Error, match="INSERT did not return row ID"):
            repo.save(
                image_file_id=sample_image_file_id,
                provider_name="ollama",
                model_name="model",
                prompt_text="prompt",
                response_text="response",
                confidence_score=0.5,
                processing_time_ms=1000,
            )

    def test_delete_commit_handles_operational_error(self, repo, sample_image_file_id):
        """Test delete handles OperationalError during commit."""
        # Create an analysis first
        repo.save(
            image_file_id=sample_image_file_id,
            provider_name="ollama",
            model_name="model",
            prompt_text="prompt",
            response_text="response",
            confidence_score=0.5,
            processing_time_ms=1000,
        )

        # Mock commit to raise OperationalError
        with patch.object(
            repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
        ), pytest.raises(sqlite3.OperationalError, match="Database is locked"):
            repo.delete_by_image_file_id(sample_image_file_id)

    def test_delete_commit_handles_generic_error(self, repo, sample_image_file_id):
        """Test delete handles generic sqlite3.Error during commit."""
        # Create an analysis first
        repo.save(
            image_file_id=sample_image_file_id,
            provider_name="ollama",
            model_name="model",
            prompt_text="prompt",
            response_text="response",
            confidence_score=0.5,
            processing_time_ms=1000,
        )

        # Mock commit to raise generic Error
        with patch.object(repo.conn, "commit", side_effect=sqlite3.Error("Generic commit error")):
            with pytest.raises(sqlite3.Error, match="Failed to delete analysis records"):
                repo.delete_by_image_file_id(sample_image_file_id)
