"""
Repository for archived PDF metadata.

After schema refactoring, archived metadata is tracked via pdf_files table
and metadata is linked via bundle_id.
"""

from typing import Any

from db.connection import DatabaseConnection


class ArchivedMetadataRepository:
    """Manages archived PDF metadata using pdf_files and metadata tables."""

    def __init__(self, conn: DatabaseConnection):
        """
        Initialize archived metadata repository.

        Args:
            conn: Database connection
        """
        self.conn = conn

    def archive_document(
        self,
        pdf_path: str,
        source_files: list[str],
        document_metadata: dict[str, Any],
    ) -> None:
        """
        Archive document metadata.

        Creates a bundle and PDF record for backward compatibility with tests.

        Args:
            pdf_path: Path to generated PDF
            source_files: List of source image paths
            document_metadata: Document metadata dict
        """
        import os

        # Create a bundle for the document
        bundle_name = document_metadata.get("title") or os.path.basename(pdf_path)
        self.conn.execute(
            """
            INSERT INTO document_bundles (bundle_name, status)
            VALUES (?, 'completed')
        """,
            (bundle_name,),
        )
        bundle_id_result = self.conn.fetch_one("SELECT last_insert_rowid()")
        bundle_id = bundle_id_result[0] if bundle_id_result else None

        if not bundle_id:
            raise RuntimeError("Failed to create bundle for archived document")

        # Link source images to bundle
        for file_path in source_files:
            # Get image_file_id
            image_result = self.conn.fetch_one(
                "SELECT id FROM image_files WHERE file_path = ?",
                (file_path,),
            )
            if image_result:
                image_file_id = image_result[0]
                # Insert into bundle_images
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO bundle_images (bundle_id, image_file_id, sequence_order)
                    VALUES (?, ?, 0)
                """,
                    (bundle_id, image_file_id),
                )

        # Extract pdf filename
        pdf_filename = os.path.basename(pdf_path)

        # Insert into pdf_files table with bundle link
        self.conn.execute(
            """
            INSERT INTO pdf_files (
                pdf_path, pdf_filename, page_count, bundle_id, generation_status, generated_at
            ) VALUES (?, ?, ?, ?, 'completed', CURRENT_TIMESTAMP)
            ON CONFLICT(pdf_path) DO UPDATE SET
                page_count = excluded.page_count,
                bundle_id = excluded.bundle_id,
                generation_status = 'completed',
                generated_at = CURRENT_TIMESTAMP
        """,
            (pdf_path, pdf_filename, len(source_files), bundle_id),
        )
        self.conn.commit()

    def get_archived_document(self, pdf_path: str) -> dict[str, Any] | None:
        """
        Get archived document by PDF path, including metadata from source images.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Document metadata dict if found, None otherwise
        """
        # Query pdf_files table
        pdf_result = self.conn.fetch_one_dict(
            """
            SELECT
                p.pdf_path,
                p.pdf_filename,
                p.page_count,
                p.generated_at,
                p.bundle_id,
                b.bundle_name,
                b.confidence_score,
                b.status
            FROM pdf_files p
            LEFT JOIN document_bundles b ON p.bundle_id = b.id
            WHERE p.pdf_path = ?
        """,
            (pdf_path,),
        )

        if not pdf_result:
            return None

        result = dict(pdf_result)

        # Try to get metadata from first source image if bundle exists
        if result.get("bundle_id"):
            metadata_result = self.conn.fetch_one_dict(
                """
                SELECT m.company, m.document_type
                FROM metadata m
                JOIN bundle_images bi ON m.image_file_id = bi.image_file_id
                WHERE bi.bundle_id = ?
                LIMIT 1
            """,
                (result["bundle_id"],),
            )
            if metadata_result:
                result.update(metadata_result)

        return result

    def get_statistics(self) -> dict[str, int]:
        """
        Get archived document statistics.

        Returns:
            Statistics dict with counts
        """
        cursor = self.conn.execute("""
            SELECT
                COUNT(*) as total_pdfs,
                SUM(page_count) as total_pages
            FROM pdf_files
            WHERE generation_status = 'completed'
        """)
        row = cursor.fetchone()

        # COUNT(*) always returns a row, even if no matches (returns 0)
        return {
            "total_pdfs": row[0] or 0,
            "total_pages": row[1] or 0,
        }
