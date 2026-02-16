"""Tests for AuditRepository"""

import sqlite3
from unittest.mock import patch

import pytest

from db.connection import DatabaseConnection
from db.repositories.audit_repo import AuditRepository
from db.schema import create_all_tables


@pytest.fixture
def db_conn(tmp_path):
    """Create a temporary database connection for testing."""
    db_path = tmp_path / "test_audit.db"
    conn = DatabaseConnection(str(db_path))
    create_all_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def repo(db_conn):
    """Create an AuditRepository instance for testing."""
    return AuditRepository(db_conn)


class TestAuditRepositoryBasics:
    """Test basic repository initialization."""

    def test_repository_initialization(self, repo, db_conn):
        """Test that repository initializes with correct connection."""
        assert repo.conn == db_conn
        assert repo.conn.connection is not None

    def test_repository_has_logger(self, repo):
        """Test that repository has logger initialized."""
        logger = repo._get_logger()
        assert logger is not None
        assert hasattr(logger, "info")


class TestLogAction:
    """Test log_action() method for audit logging."""

    def test_log_action_creates_audit_record(self, repo):
        """Test logging an action to audit trail."""
        repo.log_action(
            action_type="file_analyzed",
            action_details="Analyzed document.pdf with ollama",
            file_path="/test/document.pdf",
            bundle_id=123,
        )

        # Verify record was created
        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT * FROM audit_trail")
        record = cursor.fetchone()

        assert record is not None
        assert record[1] == "file_analyzed"  # action_type
        assert record[2] == "Analyzed document.pdf with ollama"  # action_details
        assert record[3] == "/test/document.pdf"  # file_path
        assert record[4] == 123  # bundle_id

    def test_log_action_with_minimal_fields(self, repo):
        """Test logging action with only required fields."""
        repo.log_action(
            action_type="app_started",
            action_details="Application initialized",
            file_path=None,
            bundle_id=None,
        )

        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT * FROM audit_trail")
        record = cursor.fetchone()

        assert record is not None
        assert record[1] == "app_started"
        assert record[2] == "Application initialized"
        assert record[3] is None  # file_path
        assert record[4] is None  # bundle_id

    def test_log_action_with_file_path_only(self, repo):
        """Test logging action with file_path but no bundle_id."""
        repo.log_action(
            action_type="file_deleted",
            action_details="User deleted file",
            file_path="/test/removed.pdf",
            bundle_id=None,
        )

        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT file_path, bundle_id FROM audit_trail")
        record = cursor.fetchone()

        assert record[0] == "/test/removed.pdf"
        assert record[1] is None

    def test_log_action_with_bundle_id_only(self, repo):
        """Test logging action with bundle_id but no file_path."""
        repo.log_action(
            action_type="bundle_accepted",
            action_details="User accepted bundle",
            file_path=None,
            bundle_id=456,
        )

        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT file_path, bundle_id FROM audit_trail")
        record = cursor.fetchone()

        assert record[0] is None
        assert record[1] == 456

    def test_log_action_multiple_entries(self, repo):
        """Test logging multiple actions creates multiple records."""
        repo.log_action("action1", "Details 1")
        repo.log_action("action2", "Details 2")
        repo.log_action("action3", "Details 3")

        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM audit_trail")
        count = cursor.fetchone()[0]

        assert count == 3

    def test_log_action_handles_operational_error(self, repo):
        """Test log_action handles OperationalError."""
        with patch.object(
            repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
        ), pytest.raises(sqlite3.OperationalError, match="Database is locked"):
            repo.log_action("test", "Test details")

    def test_log_action_handles_generic_error(self, repo):
        """Test log_action handles generic sqlite3.Error."""
        with patch.object(repo.conn, "commit", side_effect=sqlite3.Error("Generic database error")):
            with pytest.raises(sqlite3.Error, match="Failed to save audit log"):
                repo.log_action("test", "Test details")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_log_action_with_very_long_details(self, repo):
        """Test logging action with very long details."""
        long_details = "x" * 10000
        repo.log_action("test", long_details)

        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT action_details FROM audit_trail")
        details = cursor.fetchone()[0]

        assert len(details) == 10000

    def test_log_action_with_special_characters(self, repo):
        """Test logging action with special characters in details."""
        special_details = "Test with special chars: @#$%^&*()[]{}|\\\"'<>?/"
        repo.log_action("test", special_details, file_path="/test/file with spaces.pdf")

        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT action_details, file_path FROM audit_trail")
        record = cursor.fetchone()

        assert record[0] == special_details
        assert record[1] == "/test/file with spaces.pdf"

    def test_log_action_preserves_timestamp(self, repo):
        """Test that log_action creates timestamp automatically."""
        repo.log_action("test", "Test")

        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT created_at FROM audit_trail")
        timestamp = cursor.fetchone()[0]

        # Timestamp should be set automatically
        assert timestamp is not None

    def test_log_action_with_empty_action_type(self, repo):
        """Test logging with empty action_type string."""
        repo.log_action("", "Details")

        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT action_type FROM audit_trail")
        action_type = cursor.fetchone()[0]

        assert action_type == ""


class TestIntegration:
    """Test integration scenarios."""

    def test_audit_trail_workflow(self, repo):
        """Test complete audit logging workflow."""
        # Log file analysis
        repo.log_action(
            action_type="file_analyzed",
            action_details="Analyzed invoice.pdf with Claude",
            file_path="/docs/invoice.pdf",
        )

        # Log bundle creation
        repo.log_action(
            action_type="bundle_created",
            action_details="AI suggested bundle for tax documents",
            bundle_id=1,
        )

        # Log bundle acceptance
        repo.log_action(
            action_type="bundle_accepted",
            action_details="User accepted tax bundle",
            bundle_id=1,
        )

        # Log PDF generation
        repo.log_action(
            action_type="pdf_generated",
            action_details="Generated tax_2023.pdf",
            file_path="/output/tax_2023.pdf",
            bundle_id=1,
        )

        # Verify all 4 actions logged
        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM audit_trail")
        count = cursor.fetchone()[0]
        assert count == 4

        # Verify correct action types
        cursor.execute("SELECT action_type FROM audit_trail ORDER BY id")
        actions = [row[0] for row in cursor.fetchall()]
        assert actions == [
            "file_analyzed",
            "bundle_created",
            "bundle_accepted",
            "pdf_generated",
        ]

    def test_query_audit_trail_by_bundle(self, repo):
        """Test querying audit trail for specific bundle."""
        # Log actions for multiple bundles
        repo.log_action("action1", "Bundle 1 action", bundle_id=1)
        repo.log_action("action2", "Bundle 1 action", bundle_id=1)
        repo.log_action("action3", "Bundle 2 action", bundle_id=2)

        # Query for bundle 1
        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM audit_trail WHERE bundle_id = ?", (1,))
        count = cursor.fetchone()[0]

        assert count == 2

    def test_query_audit_trail_by_file_path(self, repo):
        """Test querying audit trail for specific file."""
        # Log actions for multiple files
        repo.log_action("action1", "File 1 action", file_path="/test/file1.pdf")
        repo.log_action("action2", "File 1 action", file_path="/test/file1.pdf")
        repo.log_action("action3", "File 2 action", file_path="/test/file2.pdf")

        # Query for file1
        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM audit_trail WHERE file_path = ?", ("/test/file1.pdf",))
        count = cursor.fetchone()[0]

        assert count == 2
