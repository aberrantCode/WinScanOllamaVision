"""
Audit repository for managing audit trail logging.

Simplified CRUD operations for user action tracking.
"""

import logging
import sqlite3
from typing import TYPE_CHECKING

from db.connection import DatabaseConnection

if TYPE_CHECKING:
    from services.logging_service import get_logger
else:
    get_logger = None

logger: logging.Logger | None = None


class AuditRepository:
    """Manages audit trail logging."""

    def __init__(self, conn: DatabaseConnection):
        """
        Initialize audit repository.

        Args:
            conn: Database connection
        """
        self.conn = conn

    def _get_logger(self) -> logging.Logger:
        """Get logger instance (lazy initialization)."""
        global logger
        if logger is None:
            from services.logging_service import get_logger as _get_logger

            logger = _get_logger()
        return logger

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
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[AUDIT REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            self._get_logger().error(f"[AUDIT REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to save audit log: {e}") from e
