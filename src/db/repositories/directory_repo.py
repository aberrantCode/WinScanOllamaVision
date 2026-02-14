"""
Directory repository for managing source directory configuration.

Simplified CRUD operations for scan directory tracking.
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


class DirectoryRepository:
    """Manages source directory configuration persistence."""

    def __init__(self, conn: DatabaseConnection):
        """
        Initialize directory repository.

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

    def add(self, directory_path: str, scan_on_startup: bool = True) -> None:
        """
        Add a source directory for scanning.

        Args:
            directory_path: Absolute path to directory
            scan_on_startup: Whether to scan on application startup
        """
        self.conn.execute(
            """
            INSERT OR REPLACE INTO source_directories (
                directory_path, is_active, scan_on_startup
            ) VALUES (?, 1, ?)
        """,
            (directory_path, scan_on_startup),
        )
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[DIRECTORY REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            self._get_logger().error(f"[DIRECTORY REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to add directory: {e}") from e

    def get_active(self) -> list[str]:
        """
        Get list of active source directories.

        Returns:
            List of directory paths
        """
        rows = self.conn.fetch_all(
            "SELECT directory_path FROM source_directories WHERE is_active = 1"
        )
        return [row["directory_path"] for row in rows]

    def remove(self, directory_path: str) -> None:
        """
        Remove a source directory.

        Args:
            directory_path: Path to directory to remove
        """
        self.conn.execute(
            "DELETE FROM source_directories WHERE directory_path = ?",
            (directory_path,),
        )
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[DIRECTORY REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            self._get_logger().error(f"[DIRECTORY REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to remove directory: {e}") from e

    def update_scan_info(self, directory_path: str, file_count: int) -> None:
        """
        Update directory scan information.

        Args:
            directory_path: Path to directory
            file_count: Number of files found in directory
        """
        self.conn.execute(
            """
            UPDATE source_directories
            SET last_scanned_at = CURRENT_TIMESTAMP, file_count = ?
            WHERE directory_path = ?
        """,
            (file_count, directory_path),
        )
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[DIRECTORY REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            self._get_logger().error(f"[DIRECTORY REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to update scan info: {e}") from e
