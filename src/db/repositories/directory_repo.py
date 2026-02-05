"""
Directory repository for managing source directory configuration.

Simplified CRUD operations for scan directory tracking.
"""

from db.connection import DatabaseConnection


class DirectoryRepository:
    """Manages source directory configuration persistence."""

    def __init__(self, conn: DatabaseConnection):
        """
        Initialize directory repository.

        Args:
            conn: Database connection
        """
        self.conn = conn

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
        self.conn.commit()

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
        self.conn.commit()

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
        self.conn.commit()
