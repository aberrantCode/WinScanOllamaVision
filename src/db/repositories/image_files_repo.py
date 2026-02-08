"""
Image files repository for tracking file discovery and lifecycle.

Manages image file registration, status transitions, and lifecycle tracking.
"""

from typing import Any

from db.connection import DatabaseConnection


class ImageFilesRepository:
    """Repository for image file discovery and lifecycle tracking."""

    def __init__(self, conn: DatabaseConnection):
        """
        Initialize image files repository.

        Args:
            conn: Database connection
        """
        self.conn = conn

    def register(
        self,
        file_path: str,
        file_hash: str,
        directory_path: str,
        filename: str,
        file_size: int,
        file_mtime: float,
    ) -> int:
        """
        Register a discovered image file.

        Args:
            file_path: Full path to image file
            file_hash: SHA-256 hash of file
            directory_path: Parent directory path
            filename: File name without path
            file_size: File size in bytes
            file_mtime: File modification time

        Returns:
            ID of registered image file
        """
        self.conn.execute(
            """
            INSERT OR REPLACE INTO image_files (
                file_path, file_hash, directory_path, filename,
                file_size, file_mtime, status, discovered_at, last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'registered', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
            (file_path, file_hash, directory_path, filename, file_size, file_mtime),
        )
        self.conn.commit()

        # Get the ID of the inserted/updated record
        result = self.conn.fetch_one_dict(
            "SELECT id FROM image_files WHERE file_path = ?", (file_path,)
        )
        return result["id"] if result else 0

    def get_by_path(self, file_path: str) -> dict[str, Any] | None:
        """
        Get image file record by path.

        Args:
            file_path: Path to image file

        Returns:
            Image file dict if found, None otherwise
        """
        return self.conn.fetch_one_dict(
            "SELECT * FROM image_files WHERE file_path = ?", (file_path,)
        )

    def get_by_directory(self, directory_path: str) -> list[dict[str, Any]]:
        """
        Get all images in a directory.

        Args:
            directory_path: Directory path to filter by

        Returns:
            List of image file dicts
        """
        return self.conn.fetch_all_dicts(
            "SELECT * FROM image_files WHERE directory_path = ? ORDER BY filename",
            (directory_path,),
        )

    def get_by_status(self, status: str) -> list[dict[str, Any]]:
        """
        Get images by status (registered, analyzed, etc).

        Args:
            status: Lifecycle status to filter by

        Returns:
            List of image file dicts
        """
        return self.conn.fetch_all_dicts(
            "SELECT * FROM image_files WHERE status = ? ORDER BY discovered_at DESC",
            (status,),
        )

    def get_all(self) -> list[dict[str, Any]]:
        """
        Get all image files (excluding deleted).

        Returns:
            List of image file dicts
        """
        return self.conn.fetch_all_dicts(
            "SELECT * FROM image_files WHERE status != 'deleted' ORDER BY discovered_at DESC"
        )

    def update_status(self, file_path: str, status: str, analysis_id: int | None = None) -> None:
        """
        Update image file status.

        Args:
            file_path: Path to image file
            status: New status (registered, analyzing, analyzed, bundled, deleted)
            analysis_id: Optional analysis result ID reference
        """
        if analysis_id is not None:
            self.conn.execute(
                """
                UPDATE image_files
                SET status = ?, analysis_id = ?
                WHERE file_path = ?
            """,
                (status, analysis_id, file_path),
            )
        else:
            self.conn.execute(
                """
                UPDATE image_files
                SET status = ?
                WHERE file_path = ?
            """,
                (status, file_path),
            )
        self.conn.commit()

    def update_last_seen(self, file_path: str) -> None:
        """
        Update last_seen_at timestamp.

        Args:
            file_path: Path to image file
        """
        self.conn.execute(
            """
            UPDATE image_files
            SET last_seen_at = CURRENT_TIMESTAMP
            WHERE file_path = ?
        """,
            (file_path,),
        )
        self.conn.commit()

    def update_hash(self, file_path: str, file_hash: str) -> None:
        """
        Update file hash (used when file changes detected).

        Args:
            file_path: Path to image file
            file_hash: New SHA-256 hash
        """
        self.conn.execute(
            """
            UPDATE image_files
            SET file_hash = ?
            WHERE file_path = ?
        """,
            (file_hash, file_path),
        )
        self.conn.commit()

    def mark_deleted(self, file_path: str) -> None:
        """
        Mark image as deleted (soft delete).

        Args:
            file_path: Path to image file
        """
        self.conn.execute(
            """
            UPDATE image_files
            SET status = 'deleted', deleted_at = CURRENT_TIMESTAMP
            WHERE file_path = ?
        """,
            (file_path,),
        )
        self.conn.commit()

    def mark_deleted_batch(self, file_paths: list[str]) -> int:
        """
        Mark multiple images as deleted (batch operation).

        Args:
            file_paths: List of file paths to mark as deleted

        Returns:
            Number of rows affected
        """
        if not file_paths:
            return 0

        placeholders = ",".join("?" * len(file_paths))
        # Column names from internal code, values parameterized - safe from injection
        query = f"""
            UPDATE image_files
            SET status = 'deleted', deleted_at = CURRENT_TIMESTAMP
            WHERE file_path IN ({placeholders})
        """  # nosec B608

        cursor = self.conn.execute(query, tuple(file_paths))
        self.conn.commit()
        return cursor.rowcount if cursor else 0

    def set_output_filename(self, file_path: str, output_filename: str) -> None:
        """
        Set proposed output filename.

        Args:
            file_path: Path to image file
            output_filename: Proposed output PDF filename
        """
        self.conn.execute(
            """
            UPDATE image_files
            SET output_filename = ?
            WHERE file_path = ?
        """,
            (output_filename, file_path),
        )
        self.conn.commit()

    def get_stats(self) -> dict[str, int]:
        """
        Get statistics (total, by status, etc).

        Returns:
            Dictionary with statistics
        """
        stats: dict[str, int] = {}

        # Total files (excluding deleted)
        result = self.conn.fetch_one_dict(
            "SELECT COUNT(*) as count FROM image_files WHERE status != 'deleted'"
        )
        stats["total"] = result["count"] if result else 0

        # Count by status
        results = self.conn.fetch_all_dicts(
            "SELECT status, COUNT(*) as count FROM image_files GROUP BY status"
        )
        for row in results:
            stats[f"status_{row['status']}"] = row["count"]

        return stats
