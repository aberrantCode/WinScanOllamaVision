"""
PDF files repository for tracking generated PDFs.

Manages PDF file registration, generation status, and metadata.
"""

import json
from typing import Any

from db.connection import DatabaseConnection


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
        source_image_ids: list[int],
        page_count: int,
        file_hash: str | None = None,
        file_size: int | None = None,
    ) -> int:
        """
        Register a generated PDF.

        Args:
            pdf_path: Full path to PDF file
            pdf_filename: PDF filename without path
            bundle_id: Reference to document bundle
            source_image_ids: List of image_files.id values
            page_count: Number of pages in PDF
            file_hash: Optional SHA-256 hash of PDF
            file_size: Optional file size in bytes

        Returns:
            ID of registered PDF file
        """
        source_ids_json = json.dumps(source_image_ids)

        self.conn.execute(
            """
            INSERT OR REPLACE INTO pdf_files (
                pdf_path, pdf_filename, bundle_id, source_image_ids,
                page_count, file_hash, file_size, generation_status, generated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', CURRENT_TIMESTAMP)
        """,
            (
                pdf_path,
                pdf_filename,
                bundle_id,
                source_ids_json,
                page_count,
                file_hash,
                file_size,
            ),
        )
        self.conn.commit()

        # Get the ID of the inserted/updated record
        result = self.conn.fetch_one_dict(
            "SELECT id FROM pdf_files WHERE pdf_path = ?", (pdf_path,)
        )
        return result["id"] if result else 0

    def get_by_path(self, pdf_path: str) -> dict[str, Any] | None:
        """
        Get PDF record by path.

        Args:
            pdf_path: Path to PDF file

        Returns:
            PDF file dict if found, None otherwise (with source_image_ids parsed from JSON)
        """
        result = self.conn.fetch_one_dict("SELECT * FROM pdf_files WHERE pdf_path = ?", (pdf_path,))

        if result and "source_image_ids" in result:
            # Parse source_image_ids JSON
            result["source_image_ids"] = json.loads(result["source_image_ids"])

        return result

    def get_by_bundle(self, bundle_id: int) -> dict[str, Any] | None:
        """
        Get PDF by bundle ID.

        Args:
            bundle_id: Bundle ID to look up

        Returns:
            PDF file dict if found, None otherwise
        """
        result = self.conn.fetch_one_dict(
            "SELECT * FROM pdf_files WHERE bundle_id = ?", (bundle_id,)
        )

        if result and "source_image_ids" in result:
            # Parse source_image_ids JSON
            result["source_image_ids"] = json.loads(result["source_image_ids"])

        return result

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
        self.conn.commit()

    def update_searchability(self, pdf_path: str, is_searchable: bool) -> None:
        """
        Update PDF searchability flag.

        Args:
            pdf_path: Path to PDF file
            is_searchable: Whether PDF contains searchable text
        """
        # Check if column exists (for future migration)
        cursor = self.conn.connection.cursor() if self.conn.connection else None
        if cursor:
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
                self.conn.commit()

    def get_all(self) -> list[dict[str, Any]]:
        """
        Get all generated PDFs.

        Returns:
            List of PDF file dicts
        """
        results = self.conn.fetch_all_dicts("SELECT * FROM pdf_files ORDER BY generated_at DESC")

        # Parse source_image_ids JSON for all results
        for result in results:
            if "source_image_ids" in result:
                result["source_image_ids"] = json.loads(result["source_image_ids"])

        return results

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
