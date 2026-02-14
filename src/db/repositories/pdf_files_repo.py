"""
PDF files repository for tracking generated PDFs.

Manages PDF file registration, generation status, and metadata.
"""

import sqlite3
from typing import Any

from db.connection import DatabaseConnection
from services.logging_service import get_logger

logger = get_logger()


class PdfFilesRepository:
    """Repository for PDF file tracking."""

    def __init__(self, conn: DatabaseConnection):
        """
        Initialize PDF files repository.

        Args:
            conn: Database connection
        """
        self.conn = conn

    def register(
        self,
        pdf_path: str,
        pdf_filename: str,
        bundle_id: int,
        page_count: int,
        file_hash: str | None = None,
        file_size: int | None = None,
    ) -> int:
        """
        Register a generated PDF.

        NOTE: After creating PDF, use PdfImagePagesRepository to link images via junction table.

        Args:
            pdf_path: Full path to PDF file
            pdf_filename: PDF filename without path
            bundle_id: Reference to document bundle
            page_count: Number of pages in PDF
            file_hash: Optional SHA-256 hash of PDF
            file_size: Optional file size in bytes

        Returns:
            ID of registered PDF file
        """
        self.conn.execute(
            """
            INSERT OR REPLACE INTO pdf_files (
                pdf_path, pdf_filename, bundle_id,
                page_count, file_hash, file_size, generation_status, generated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'completed', CURRENT_TIMESTAMP)
        """,
            (
                pdf_path,
                pdf_filename,
                bundle_id,
                page_count,
                file_hash,
                file_size,
            ),
        )
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            logger.error(f"[PDF FILES REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            logger.error(f"[PDF FILES REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to register PDF file: {e}") from e

        # Get the ID of the inserted/updated record
        result = self.conn.fetch_one_dict(
            "SELECT id FROM pdf_files WHERE pdf_path = ?", (pdf_path,)
        )
        return result["id"] if result else 0

    def get_by_path(self, pdf_path: str) -> dict[str, Any] | None:
        """
        Get PDF record by path.

        NOTE: Does not include source images - use PdfImagePagesRepository to fetch them.

        Args:
            pdf_path: Path to PDF file

        Returns:
            PDF file dict if found, None otherwise
        """
        return self.conn.fetch_one_dict("SELECT * FROM pdf_files WHERE pdf_path = ?", (pdf_path,))

    def get_by_bundle(self, bundle_id: int) -> dict[str, Any] | None:
        """
        Get PDF by bundle ID.

        NOTE: Does not include source images - use PdfImagePagesRepository to fetch them.

        Args:
            bundle_id: Bundle ID to look up

        Returns:
            PDF file dict if found, None otherwise
        """
        return self.conn.fetch_one_dict("SELECT * FROM pdf_files WHERE bundle_id = ?", (bundle_id,))

    def update_generation_status(self, pdf_path: str, status: str) -> None:
        """
        Update generation status.

        Args:
            pdf_path: Path to PDF file
            status: New status (generating, completed, failed)
        """
        self.conn.execute(
            """
            UPDATE pdf_files
            SET generation_status = ?
            WHERE pdf_path = ?
        """,
            (status, pdf_path),
        )
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            logger.error(f"[PDF FILES REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            logger.error(f"[PDF FILES REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to update generation status: {e}") from e

    def update_searchability(self, pdf_path: str, is_searchable: bool) -> None:
        """
        Update PDF searchability flag.

        Args:
            pdf_path: Path to PDF file
            is_searchable: Whether PDF contains searchable text
        """
        # Check if column exists (for future migration)
        if self.conn.connection is None:
            return

        cursor = self.conn.connection.cursor()
        cursor.execute("PRAGMA table_info(pdf_files)")
        columns = {col[1] for col in cursor.fetchall()}
        if "is_searchable" in columns:
            self.conn.execute(
                """
                UPDATE pdf_files
                SET is_searchable = ?
                WHERE pdf_path = ?
            """,
                (is_searchable, pdf_path),
            )
            try:
                self.conn.commit()
            except sqlite3.OperationalError as e:
                logger.error(f"[PDF FILES REPO] Database locked: {e}")
                self.conn.rollback()
                raise sqlite3.OperationalError("Database is locked. Try again.") from e
            except sqlite3.Error as e:
                logger.error(f"[PDF FILES REPO] Database error: {e}")
                self.conn.rollback()
                raise sqlite3.Error(f"Failed to update searchability: {e}") from e

    def get_all(self) -> list[dict[str, Any]]:
        """
        Get all generated PDFs.

        NOTE: Does not include source images - use PdfImagePagesRepository to fetch them.

        Returns:
            List of PDF file dicts
        """
        return self.conn.fetch_all_dicts("SELECT * FROM pdf_files ORDER BY generated_at DESC")

    def get_stats(self) -> dict[str, int]:
        """
        Get statistics.

        Returns:
            Dictionary with statistics
        """
        stats: dict[str, int] = {}

        # Total PDFs
        result = self.conn.fetch_one_dict("SELECT COUNT(*) as count FROM pdf_files")
        stats["total"] = result["count"] if result else 0

        # Count by generation status
        results = self.conn.fetch_all_dicts(
            "SELECT generation_status, COUNT(*) as count FROM pdf_files GROUP BY generation_status"
        )
        for row in results:
            stats[f"status_{row['generation_status']}"] = row["count"]

        return stats
