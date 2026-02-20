"""
Image files repository for tracking file discovery and lifecycle.

Manages image file registration, status transitions, and lifecycle tracking.
"""

import logging
import os
import sqlite3
from typing import TYPE_CHECKING, Any

from db.connection import DatabaseConnection

if TYPE_CHECKING:
    from services.logging_service import get_logger
else:
    get_logger = None

logger: logging.Logger | None = None


class ImageFilesRepository:
    """Repository for image file discovery and lifecycle tracking."""

    def __init__(self, conn: DatabaseConnection):
        """
        Initialize image files repository.

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
        # Normalize paths to use consistent separators (backslashes on Windows)
        # This prevents duplicate entries with C:/ vs C:\ paths
        file_path = os.path.normpath(file_path)
        directory_path = os.path.normpath(directory_path)

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
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[IMAGE FILES REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            self._get_logger().error(f"[IMAGE FILES REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to register image file: {e}") from e

        # Get the ID of the inserted/updated record
        result = self.conn.fetch_one_dict(
            "SELECT id FROM image_files WHERE file_path = ?", (file_path,)
        )
        # Use .get() for safe dictionary access
        return result.get("id", 0) if result else 0

    def get_by_path(self, file_path: str) -> dict[str, Any] | None:
        """
        Get image file record by path.

        Args:
            file_path: Path to image file

        Returns:
            Image file dict if found, None otherwise
        """
        # Normalize path for consistent lookups
        file_path = os.path.normpath(file_path)
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
        directory_path = os.path.normpath(directory_path)
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

    def update_status(self, file_path: str, status: str) -> None:
        """
        Update image file status.

        Args:
            file_path: Path to image file
            status: New status (registered, analyzing, analyzed, bundled, deleted)
        """
        # Normalize path for consistent lookups
        file_path = os.path.normpath(file_path)

        self.conn.execute(
            """
            UPDATE image_files
            SET status = ?
            WHERE file_path = ?
        """,
            (status, file_path),
        )
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[IMAGE FILES REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            self._get_logger().error(f"[IMAGE FILES REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to update image status: {e}") from e

    def update_last_seen(self, file_path: str) -> None:
        """
        Update last_seen_at timestamp.

        Args:
            file_path: Path to image file
        """
        file_path = os.path.normpath(file_path)
        self.conn.execute(
            """
            UPDATE image_files
            SET last_seen_at = CURRENT_TIMESTAMP
            WHERE file_path = ?
        """,
            (file_path,),
        )
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[IMAGE FILES REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            self._get_logger().error(f"[IMAGE FILES REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to update last seen timestamp: {e}") from e

    def update_hash(self, file_path: str, file_hash: str) -> None:
        """
        Update file hash (used when file changes detected).

        Args:
            file_path: Path to image file
            file_hash: New SHA-256 hash
        """
        file_path = os.path.normpath(file_path)
        self.conn.execute(
            """
            UPDATE image_files
            SET file_hash = ?
            WHERE file_path = ?
        """,
            (file_hash, file_path),
        )
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[IMAGE FILES REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            self._get_logger().error(f"[IMAGE FILES REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to update file hash: {e}") from e

    def mark_deleted(self, file_path: str) -> None:
        """
        Mark image as deleted (soft delete).

        Args:
            file_path: Path to image file
        """
        file_path = os.path.normpath(file_path)
        self.conn.execute(
            """
            UPDATE image_files
            SET status = 'deleted', deleted_at = CURRENT_TIMESTAMP
            WHERE file_path = ?
        """,
            (file_path,),
        )
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[IMAGE FILES REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            self._get_logger().error(f"[IMAGE FILES REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to mark image as deleted: {e}") from e

    def update_rotation(self, file_path: str, rotation: int) -> None:
        """
        Update user-specified rotation for image file (stored in metadata table).

        Args:
            file_path: Path to image file
            rotation: Rotation in degrees (0, 90, 180, 270)
        """
        # Get image_file_id
        image_file = self.get_by_path(file_path)
        if not image_file:
            return

        # Create metadata record if it doesn't exist, then update rotation
        self.conn.execute(
            """
            INSERT INTO metadata (image_file_id, rotation)
            VALUES (?, ?)
            ON CONFLICT(image_file_id) DO UPDATE SET
                rotation = excluded.rotation,
                updated_at = CURRENT_TIMESTAMP
        """,
            (image_file["id"], rotation),
        )
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[IMAGE FILES REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            self._get_logger().error(f"[IMAGE FILES REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to update rotation: {e}") from e

    def get_rotation(self, file_path: str) -> int:
        """
        Get user-specified rotation for image file (stored in metadata table).

        Args:
            file_path: Path to image file

        Returns:
            Rotation in degrees (0, 90, 180, 270), defaults to 0
        """
        # Get image_file_id
        image_file = self.get_by_path(file_path)
        if not image_file:
            return 0

        # Query metadata table (rotation moved there after schema cleanup)
        result = self.conn.fetch_one_dict(
            "SELECT rotation FROM metadata WHERE image_file_id = ?", (image_file["id"],)
        )
        return result["rotation"] if result and result["rotation"] is not None else 0

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

        file_paths = [os.path.normpath(p) for p in file_paths]
        placeholders = ",".join("?" * len(file_paths))
        # Column names from internal code, values parameterized - safe from injection
        query = f"""
            UPDATE image_files
            SET status = 'deleted', deleted_at = CURRENT_TIMESTAMP
            WHERE file_path IN ({placeholders})
        """  # nosec B608

        cursor = self.conn.execute(query, tuple(file_paths))
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[IMAGE FILES REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            self._get_logger().error(f"[IMAGE FILES REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to mark images as deleted: {e}") from e
        return cursor.rowcount if cursor else 0

    def set_output_filename(self, file_path: str, output_filename: str) -> None:
        """
        Set proposed output filename (stored in metadata table).

        Args:
            file_path: Path to image file
            output_filename: Proposed output PDF filename
        """
        # Get image_file_id
        image_file = self.get_by_path(file_path)
        if not image_file:
            return

        # Update metadata table (output_filename moved there after schema cleanup)
        self.conn.execute(
            """
            UPDATE metadata
            SET output_filename = ?
            WHERE image_file_id = ?
        """,
            (output_filename, image_file["id"]),
        )
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[IMAGE FILES REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            self._get_logger().error(f"[IMAGE FILES REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to set output filename: {e}") from e

    def get_all_with_analysis(
        self, directory_filter: str | None = None, provider_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get all image files with their normalized metadata (if available).

        Uses LEFT OUTER JOIN to include images that haven't been analyzed yet.
        Metadata is normalized and user-approved, while analysis_results contains raw LLM output.

        Args:
            directory_filter: Optional directory path to filter by
            provider_filter: Optional provider name to filter by

        Returns:
            List of image file dicts with normalized metadata merged in
        """
        query = """
            SELECT
                -- Image file fields
                img.id,
                img.file_path,
                img.file_hash,
                img.directory_path,
                img.filename,
                img.file_size,
                img.file_mtime,
                img.status,
                img.discovered_at,
                img.last_seen_at,
                img.deleted_at,

                -- Normalized metadata fields (metadata table is authoritative)
                m.company,
                m.document_type,
                m.document_date,
                m.page_number,
                m.total_pages,
                m.belongs_to_same_doc,
                m.confidence_score,
                m.tax_related,
                m.is_blank,

                -- User preferences (from metadata table)
                m.document_category,
                m.rotation,
                m.output_filename,
                m.user_verified,
                m.last_edited_by,
                m.created_at as metadata_created_at,
                m.updated_at as metadata_updated_at,

                -- Analysis provenance (for history tracking)
                ar.provider_name,
                ar.model_name,
                ar.analyzed_at,
                ar.processing_time_ms,
                ar.had_error,

                -- Raw analysis fields (for debugging/history)
                ar.response_text,
                ar.extracted_metadata,
                ar.prompt_text,

                -- Cache detection (image has multiple analyses)
                (SELECT COUNT(*) FROM analysis_results WHERE image_file_id = img.id) > 1 AS is_cached
            FROM image_files img
            LEFT JOIN metadata m ON img.id = m.image_file_id
            LEFT JOIN analysis_results ar ON m.analysis_result_id = ar.id
            WHERE img.status != 'deleted'
        """
        params = []

        if directory_filter:
            query += " AND img.directory_path = ?"
            params.append(os.path.normpath(directory_filter))

        if provider_filter:
            query += " AND ar.provider_name = ?"
            params.append(provider_filter)

        query += " ORDER BY img.discovered_at DESC"

        return self.conn.fetch_all_dicts(
            query, params=tuple(params), json_fields=["extracted_metadata"]
        )

    def get_batch_with_analysis(self, file_paths: list[str]) -> dict[str, dict[str, Any]]:
        """
        Get analysis data for multiple file paths in a single query (batch operation).

        This is MUCH more efficient than calling get_all_with_analysis() for each file.
        Returns a dict keyed by file_path for O(1) lookup.

        Args:
            file_paths: List of file paths to fetch analysis for

        Returns:
            Dict mapping file_path -> analysis dict (includes files not found as None)
        """
        if not file_paths:
            return {}

        file_paths = [os.path.normpath(p) for p in file_paths]
        # Create placeholders for IN clause
        placeholders = ",".join("?" * len(file_paths))

        # Same query structure as get_all_with_analysis but with IN clause
        # Column names from internal code, values parameterized - safe from injection
        query = f"""
            SELECT
                -- Image file fields
                img.id,
                img.file_path,
                img.file_hash,
                img.directory_path,
                img.filename,
                img.file_size,
                img.file_mtime,
                img.status,
                img.discovered_at,
                img.last_seen_at,
                img.deleted_at,

                -- Normalized metadata fields (metadata table is authoritative)
                m.company,
                m.document_type,
                m.document_date,
                m.page_number,
                m.total_pages,
                m.belongs_to_same_doc,
                m.confidence_score,
                m.tax_related,
                m.is_blank,

                -- User preferences (from metadata table)
                m.document_category,
                m.rotation,
                m.output_filename,
                m.user_verified,
                m.last_edited_by,
                m.created_at as metadata_created_at,
                m.updated_at as metadata_updated_at,

                -- Analysis provenance (for history tracking)
                ar.provider_name,
                ar.model_name,
                ar.analyzed_at,
                ar.processing_time_ms,
                ar.had_error,

                -- Raw analysis fields (for debugging/history)
                ar.response_text,
                ar.extracted_metadata,
                ar.prompt_text,

                -- Cache detection (image has multiple analyses)
                (SELECT COUNT(*) FROM analysis_results WHERE image_file_id = img.id) > 1 AS is_cached
            FROM image_files img
            LEFT JOIN metadata m ON img.id = m.image_file_id
            LEFT JOIN analysis_results ar ON m.analysis_result_id = ar.id
            WHERE img.file_path IN ({placeholders})
            ORDER BY img.discovered_at DESC
        """  # nosec B608

        results = self.conn.fetch_all_dicts(
            query, params=tuple(file_paths), json_fields=["extracted_metadata"]
        )

        # Convert to dict keyed by file_path for O(1) lookup
        return {row["file_path"]: row for row in results}

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

    def set_ignored(self, file_path: str, ignored: bool) -> None:
        """
        Set ignore status for an image.

        Args:
            file_path: Path to image file
            ignored: True to ignore, False to un-ignore
        """
        self.conn.execute(
            "UPDATE image_files SET is_ignored = ? WHERE file_path = ?", (ignored, file_path)
        )
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[IMAGE FILES REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e

    def get_ignored_count(self) -> int:
        """
        Get count of ignored images.

        Returns:
            Number of ignored images
        """
        result = self.conn.fetch_one_dict(
            "SELECT COUNT(*) as count FROM image_files WHERE is_ignored = 1"
        )
        return result.get("count", 0) if result else 0

    def set_ignored_batch(self, file_paths: list[str], ignored: bool) -> int:
        """
        Set ignore status for multiple images (batch operation).

        Args:
            file_paths: List of file paths
            ignored: True to ignore, False to un-ignore

        Returns:
            Number of rows affected
        """
        if not file_paths:
            return 0

        placeholders = ",".join("?" * len(file_paths))
        # Column names from internal code, values parameterized - safe from injection
        query = f"""
            UPDATE image_files
            SET is_ignored = ?
            WHERE file_path IN ({placeholders})
        """  # nosec B608

        params = [ignored] + file_paths
        cursor = self.conn.execute(query, tuple(params))

        try:
            self.conn.commit()
            return cursor.rowcount if cursor else 0
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[IMAGE FILES REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
