"""Tests for BundleRepository"""

import sqlite3
from unittest.mock import patch

import pytest

from db.connection import DatabaseConnection
from db.repositories.bundle_repo import BundleRepository
from db.schema import create_all_tables


@pytest.fixture
def db_conn(tmp_path):
    """Create a temporary database connection for testing."""
    db_path = tmp_path / "test_bundle.db"
    conn = DatabaseConnection(str(db_path))
    create_all_tables(conn)
    conn.connection.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def repo(db_conn):
    """Create a BundleRepository instance for testing."""
    return BundleRepository(db_conn)


class TestBundleRepositoryBasics:
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


class TestSaveSuggestion:
    """Test save_suggestion() method for creating bundles."""

    def test_save_suggestion_creates_bundle_with_high_confidence(self, repo):
        """Test saving bundle with high confidence score."""
        bundle_id = repo.save_suggestion(
            bundle_metadata={"bundle_name": "Tax Documents 2023"},
            confidence_score=0.95,
        )

        assert bundle_id is not None
        assert bundle_id > 0

        # Verify record was created
        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT * FROM document_bundles WHERE id = ?", (bundle_id,))
        record = cursor.fetchone()

        assert record is not None
        assert record[1] == "Tax Documents 2023"  # bundle_name
        assert record[2] == 0.95  # confidence_score
        assert record[3] == "high"  # confidence_level
        assert record[4] == "suggested"  # status

    def test_save_suggestion_creates_bundle_with_medium_confidence(self, repo):
        """Test saving bundle with medium confidence score."""
        bundle_id = repo.save_suggestion(
            bundle_metadata={"bundle_name": "Invoices"},
            confidence_score=0.65,
        )

        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT confidence_level FROM document_bundles WHERE id = ?", (bundle_id,))
        confidence_level = cursor.fetchone()[0]

        assert confidence_level == "medium"

    def test_save_suggestion_creates_bundle_with_low_confidence(self, repo):
        """Test saving bundle with low confidence score."""
        bundle_id = repo.save_suggestion(
            bundle_metadata={"bundle_name": "Misc Documents"},
            confidence_score=0.35,
        )

        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT confidence_level FROM document_bundles WHERE id = ?", (bundle_id,))
        confidence_level = cursor.fetchone()[0]

        assert confidence_level == "low"

    def test_save_suggestion_confidence_thresholds(self, repo):
        """Test confidence level thresholds are correct."""
        # Test boundary values
        id_high = repo.save_suggestion({"bundle_name": "High"}, confidence_score=0.8)
        id_medium_upper = repo.save_suggestion(
            {"bundle_name": "Medium Upper"}, confidence_score=0.79
        )
        id_medium_lower = repo.save_suggestion(
            {"bundle_name": "Medium Lower"}, confidence_score=0.5
        )
        id_low = repo.save_suggestion({"bundle_name": "Low"}, confidence_score=0.49)

        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT confidence_level FROM document_bundles WHERE id = ?", (id_high,))
        assert cursor.fetchone()[0] == "high"

        cursor.execute(
            "SELECT confidence_level FROM document_bundles WHERE id = ?", (id_medium_upper,)
        )
        assert cursor.fetchone()[0] == "medium"

        cursor.execute(
            "SELECT confidence_level FROM document_bundles WHERE id = ?", (id_medium_lower,)
        )
        assert cursor.fetchone()[0] == "medium"

        cursor.execute("SELECT confidence_level FROM document_bundles WHERE id = ?", (id_low,))
        assert cursor.fetchone()[0] == "low"

    def test_save_suggestion_with_empty_bundle_name(self, repo):
        """Test saving bundle with None bundle_name."""
        bundle_id = repo.save_suggestion(
            bundle_metadata={},  # No bundle_name
            confidence_score=0.9,
        )

        assert bundle_id > 0

        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT bundle_name FROM document_bundles WHERE id = ?", (bundle_id,))
        bundle_name = cursor.fetchone()[0]
        assert bundle_name is None

    def test_save_suggestion_handles_operational_error(self, repo):
        """Test save_suggestion handles OperationalError."""
        with patch.object(
            repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
        ), pytest.raises(sqlite3.OperationalError, match="Database is locked"):
            repo.save_suggestion({"bundle_name": "Test"}, confidence_score=0.9)

    def test_save_suggestion_handles_generic_error(self, repo):
        """Test save_suggestion handles generic sqlite3.Error."""
        with patch.object(repo.conn, "commit", side_effect=sqlite3.Error("Generic database error")):
            with pytest.raises(sqlite3.Error, match="Failed to save bundle suggestion"):
                repo.save_suggestion({"bundle_name": "Test"}, confidence_score=0.9)


class TestGetSuggestions:
    """Test get_suggestions() retrieval method."""

    def test_get_suggestions_returns_suggested_bundles(self, repo):
        """Test retrieving bundles with default status filter."""
        # Create bundles with different statuses
        repo.save_suggestion({"bundle_name": "Bundle 1"}, confidence_score=0.9)
        repo.save_suggestion({"bundle_name": "Bundle 2"}, confidence_score=0.8)

        suggestions = repo.get_suggestions()

        assert len(suggestions) == 2
        assert all(s["status"] == "suggested" for s in suggestions)

    def test_get_suggestions_filters_by_status(self, repo):
        """Test filtering bundles by status."""
        # Create and update bundles
        id1 = repo.save_suggestion({"bundle_name": "Bundle 1"}, confidence_score=0.9)
        id2 = repo.save_suggestion({"bundle_name": "Bundle 2"}, confidence_score=0.8)

        # Update one to accepted
        repo.update_status(id1, "accepted")

        # Get suggested only
        suggested = repo.get_suggestions(status_filter="suggested")
        assert len(suggested) == 1
        assert suggested[0]["id"] == id2

        # Get accepted only
        accepted = repo.get_suggestions(status_filter="accepted")
        assert len(accepted) == 1
        assert accepted[0]["id"] == id1

    def test_get_suggestions_filters_by_min_confidence(self, repo):
        """Test filtering bundles by minimum confidence score."""
        repo.save_suggestion({"bundle_name": "High Conf"}, confidence_score=0.95)
        repo.save_suggestion({"bundle_name": "Medium Conf"}, confidence_score=0.65)
        repo.save_suggestion({"bundle_name": "Low Conf"}, confidence_score=0.35)

        # Get only high confidence
        high_conf = repo.get_suggestions(min_confidence=0.8)
        assert len(high_conf) == 1
        assert high_conf[0]["bundle_name"] == "High Conf"

        # Get medium and high
        medium_plus = repo.get_suggestions(min_confidence=0.5)
        assert len(medium_plus) == 2

    def test_get_suggestions_orders_by_confidence_then_date(self, repo):
        """Test that results are ordered by confidence DESC, then created_at DESC."""
        # Create bundles with different confidence scores
        repo.save_suggestion({"bundle_name": "Low"}, confidence_score=0.3)
        repo.save_suggestion({"bundle_name": "High"}, confidence_score=0.9)
        repo.save_suggestion({"bundle_name": "Medium"}, confidence_score=0.6)

        suggestions = repo.get_suggestions()

        # Should be ordered by confidence DESC
        assert suggestions[0]["bundle_name"] == "High"
        assert suggestions[1]["bundle_name"] == "Medium"
        assert suggestions[2]["bundle_name"] == "Low"

    def test_get_suggestions_returns_empty_when_no_matches(self, repo):
        """Test get_suggestions returns empty list when no matches."""
        repo.save_suggestion({"bundle_name": "Bundle"}, confidence_score=0.5)

        # Filter for high confidence (none exist)
        high_conf = repo.get_suggestions(min_confidence=0.9)
        assert high_conf == []


class TestUpdateStatus:
    """Test update_status() method for updating bundle status."""

    def test_update_status_changes_status(self, repo):
        """Test updating bundle status."""
        bundle_id = repo.save_suggestion({"bundle_name": "Test"}, confidence_score=0.9)

        # Update to accepted
        repo.update_status(bundle_id, "accepted", user_action="User approved")

        cursor = repo.conn.connection.cursor()
        cursor.execute(
            "SELECT status, user_action, action_timestamp FROM document_bundles WHERE id = ?",
            (bundle_id,),
        )
        record = cursor.fetchone()

        assert record[0] == "accepted"  # status
        assert record[1] == "User approved"  # user_action
        assert record[2] is not None  # action_timestamp

    def test_update_status_without_user_action(self, repo):
        """Test updating status without user action description."""
        bundle_id = repo.save_suggestion({"bundle_name": "Test"}, confidence_score=0.9)

        repo.update_status(bundle_id, "rejected")

        cursor = repo.conn.connection.cursor()
        cursor.execute(
            "SELECT status, user_action FROM document_bundles WHERE id = ?", (bundle_id,)
        )
        record = cursor.fetchone()

        assert record[0] == "rejected"
        assert record[1] is None  # user_action

    def test_update_status_updates_timestamp(self, repo):
        """Test that update_status updates the updated_at timestamp."""
        bundle_id = repo.save_suggestion({"bundle_name": "Test"}, confidence_score=0.9)

        # Get original timestamp
        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT updated_at FROM document_bundles WHERE id = ?", (bundle_id,))
        original_timestamp = cursor.fetchone()[0]

        # Update status
        repo.update_status(bundle_id, "modified")

        # Get new timestamp
        cursor.execute("SELECT updated_at FROM document_bundles WHERE id = ?", (bundle_id,))
        new_timestamp = cursor.fetchone()[0]

        # Timestamps should be different (new >= original)
        assert new_timestamp >= original_timestamp

    def test_update_status_handles_operational_error(self, repo):
        """Test update_status handles OperationalError."""
        bundle_id = repo.save_suggestion({"bundle_name": "Test"}, confidence_score=0.9)

        with patch.object(
            repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
        ), pytest.raises(sqlite3.OperationalError, match="Database is locked"):
            repo.update_status(bundle_id, "accepted")

    def test_update_status_handles_generic_error(self, repo):
        """Test update_status handles generic sqlite3.Error."""
        bundle_id = repo.save_suggestion({"bundle_name": "Test"}, confidence_score=0.9)

        with patch.object(repo.conn, "commit", side_effect=sqlite3.Error("Generic database error")):
            with pytest.raises(sqlite3.Error, match="Failed to update bundle status"):
                repo.update_status(bundle_id, "accepted")


class TestUpdateBundleName:
    """Test update_bundle_name() method."""

    def test_update_bundle_name_changes_name(self, repo):
        """Test updating bundle name."""
        bundle_id = repo.save_suggestion({"bundle_name": "Old Name"}, confidence_score=0.9)

        repo.update_bundle_name(bundle_id, "New Name")

        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT bundle_name FROM document_bundles WHERE id = ?", (bundle_id,))
        bundle_name = cursor.fetchone()[0]

        assert bundle_name == "New Name"

    def test_update_bundle_name_updates_timestamp(self, repo):
        """Test that update_bundle_name updates the updated_at timestamp."""
        bundle_id = repo.save_suggestion({"bundle_name": "Test"}, confidence_score=0.9)

        # Get original timestamp
        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT updated_at FROM document_bundles WHERE id = ?", (bundle_id,))
        original_timestamp = cursor.fetchone()[0]

        # Update name
        repo.update_bundle_name(bundle_id, "Updated")

        # Get new timestamp
        cursor.execute("SELECT updated_at FROM document_bundles WHERE id = ?", (bundle_id,))
        new_timestamp = cursor.fetchone()[0]

        assert new_timestamp >= original_timestamp

    def test_update_bundle_name_handles_operational_error(self, repo):
        """Test update_bundle_name handles OperationalError."""
        bundle_id = repo.save_suggestion({"bundle_name": "Test"}, confidence_score=0.9)

        with patch.object(
            repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
        ), pytest.raises(sqlite3.OperationalError, match="Database is locked"):
            repo.update_bundle_name(bundle_id, "Updated")

    def test_update_bundle_name_handles_generic_error(self, repo):
        """Test update_bundle_name handles generic sqlite3.Error."""
        bundle_id = repo.save_suggestion({"bundle_name": "Test"}, confidence_score=0.9)

        with patch.object(repo.conn, "commit", side_effect=sqlite3.Error("Generic database error")):
            with pytest.raises(sqlite3.Error, match="Failed to update bundle name"):
                repo.update_bundle_name(bundle_id, "Updated")


class TestGetBundledFilePaths:
    """Test get_bundled_file_paths() method."""

    def test_get_bundled_file_paths_returns_paths_from_accepted_bundles(self, repo, db_conn):
        """Test retrieving file paths from accepted/completed bundles."""
        # Create images
        cursor = db_conn.connection.cursor()
        cursor.execute(
            """
            INSERT INTO image_files (
                file_path, file_hash, directory_path, filename, file_size, file_mtime
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("/test/img1.png", "hash1", "/test", "img1.png", 1024, 123.0),
        )
        img1_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO image_files (
                file_path, file_hash, directory_path, filename, file_size, file_mtime
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("/test/img2.png", "hash2", "/test", "img2.png", 2048, 456.0),
        )
        img2_id = cursor.lastrowid
        db_conn.connection.commit()

        # Create accepted bundle
        bundle_id = repo.save_suggestion({"bundle_name": "Accepted"}, confidence_score=0.9)
        repo.update_status(bundle_id, "accepted")

        # Add images to bundle using bundle_images junction table
        cursor.execute(
            "INSERT INTO bundle_images (bundle_id, image_file_id, sequence_order) VALUES (?, ?, ?)",
            (bundle_id, img1_id, 1),
        )
        cursor.execute(
            "INSERT INTO bundle_images (bundle_id, image_file_id, sequence_order) VALUES (?, ?, ?)",
            (bundle_id, img2_id, 2),
        )
        db_conn.connection.commit()

        paths = repo.get_bundled_file_paths()

        assert len(paths) == 2
        assert "/test/img1.png" in paths
        assert "/test/img2.png" in paths

    def test_get_bundled_file_paths_excludes_suggested_bundles(self, repo, db_conn):
        """Test that suggested bundles are excluded."""
        # Create image
        cursor = db_conn.connection.cursor()
        cursor.execute(
            """
            INSERT INTO image_files (
                file_path, file_hash, directory_path, filename, file_size, file_mtime
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("/test/img.png", "hash", "/test", "img.png", 1024, 123.0),
        )
        img_id = cursor.lastrowid
        db_conn.connection.commit()

        # Create suggested bundle (not accepted)
        bundle_id = repo.save_suggestion({"bundle_name": "Suggested"}, confidence_score=0.9)

        # Add image to bundle
        cursor.execute(
            "INSERT INTO bundle_images (bundle_id, image_file_id, sequence_order) VALUES (?, ?, ?)",
            (bundle_id, img_id, 1),
        )
        db_conn.connection.commit()

        paths = repo.get_bundled_file_paths()

        # Should be empty (suggested bundles excluded)
        assert len(paths) == 0

    def test_get_bundled_file_paths_includes_completed_bundles(self, repo, db_conn):
        """Test that completed bundles are included."""
        # Create image
        cursor = db_conn.connection.cursor()
        cursor.execute(
            """
            INSERT INTO image_files (
                file_path, file_hash, directory_path, filename, file_size, file_mtime
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("/test/img.png", "hash", "/test", "img.png", 1024, 123.0),
        )
        img_id = cursor.lastrowid
        db_conn.connection.commit()

        # Create completed bundle
        bundle_id = repo.save_suggestion({"bundle_name": "Completed"}, confidence_score=0.9)
        repo.update_status(bundle_id, "completed")

        # Add image to bundle
        cursor.execute(
            "INSERT INTO bundle_images (bundle_id, image_file_id, sequence_order) VALUES (?, ?, ?)",
            (bundle_id, img_id, 1),
        )
        db_conn.connection.commit()

        paths = repo.get_bundled_file_paths()

        assert len(paths) == 1
        assert "/test/img.png" in paths

    def test_get_bundled_file_paths_returns_empty_when_no_bundles(self, repo):
        """Test get_bundled_file_paths returns empty set when no bundles exist."""
        paths = repo.get_bundled_file_paths()
        assert paths == set()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_save_suggestion_with_extreme_confidence_scores(self, repo):
        """Test saving bundles with confidence scores at extremes."""
        # Test 0.0
        id_zero = repo.save_suggestion({"bundle_name": "Zero"}, confidence_score=0.0)
        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT confidence_level FROM document_bundles WHERE id = ?", (id_zero,))
        assert cursor.fetchone()[0] == "low"

        # Test 1.0
        id_one = repo.save_suggestion({"bundle_name": "One"}, confidence_score=1.0)
        cursor.execute("SELECT confidence_level FROM document_bundles WHERE id = ?", (id_one,))
        assert cursor.fetchone()[0] == "high"

    def test_update_status_on_nonexistent_bundle(self, repo):
        """Test updating status on non-existent bundle (should not error)."""
        # Should not raise error (UPDATE on non-existent row)
        repo.update_status(99999, "accepted")

    def test_update_bundle_name_on_nonexistent_bundle(self, repo):
        """Test updating name on non-existent bundle (should not error)."""
        # Should not raise error (UPDATE on non-existent row)
        repo.update_bundle_name(99999, "Updated")

    def test_get_bundled_file_paths_deduplicates_paths(self, repo, db_conn):
        """Test that duplicate paths are returned as a set (no duplicates)."""
        # Create one image
        cursor = db_conn.connection.cursor()
        cursor.execute(
            """
            INSERT INTO image_files (
                file_path, file_hash, directory_path, filename, file_size, file_mtime
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("/test/img.png", "hash", "/test", "img.png", 1024, 123.0),
        )
        img_id = cursor.lastrowid

        # Create two accepted bundles both containing the same image
        bundle1_id = repo.save_suggestion({"bundle_name": "Bundle 1"}, confidence_score=0.9)
        repo.update_status(bundle1_id, "accepted")
        cursor.execute(
            "INSERT INTO bundle_images (bundle_id, image_file_id, sequence_order) VALUES (?, ?, ?)",
            (bundle1_id, img_id, 1),
        )

        bundle2_id = repo.save_suggestion({"bundle_name": "Bundle 2"}, confidence_score=0.8)
        repo.update_status(bundle2_id, "accepted")
        cursor.execute(
            "INSERT INTO bundle_images (bundle_id, image_file_id, sequence_order) VALUES (?, ?, ?)",
            (bundle2_id, img_id, 1),
        )
        db_conn.connection.commit()

        paths = repo.get_bundled_file_paths()

        # Should only return one unique path
        assert len(paths) == 1
        assert "/test/img.png" in paths
