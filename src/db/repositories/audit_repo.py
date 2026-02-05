"""
Audit repository for managing audit trail logging.

Simplified CRUD operations for user action tracking.
"""

from db.connection import DatabaseConnection


class AuditRepository:
    """Manages audit trail logging."""

    def __init__(self, conn: DatabaseConnection):
        """
        Initialize audit repository.

        Args:
            conn: Database connection
        """
        self.conn = conn

    def log_action(
        self,
        action_type: str,
        action_details: str,
        file_path: str | None = None,
        bundle_id: int | None = None,
    ) -> None:
        """
        Log user action to audit trail.

        Args:
            action_type: Type of action
            action_details: Detailed description
            file_path: Related file path
            bundle_id: Related bundle ID
        """
        self.conn.execute(
            """
            INSERT INTO audit_trail (
                action_type, action_details, file_path, bundle_id
            ) VALUES (?, ?, ?, ?)
        """,
            (action_type, action_details, file_path, bundle_id),
        )
        self.conn.commit()
