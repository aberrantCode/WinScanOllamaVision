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

        This is now handled by:
        - PdfFilesRepository for PDF tracking
        - MetadataRepository for source image metadata
        - BundleRepository for grouping

        Args:
            pdf_path: Path to generated PDF
            source_files: List of source image paths
            document_metadata: Document metadata dict
        """
        # No-op: Archiving is now handled through proper tables
        # PDFs are tracked in pdf_files table
        # Metadata is tracked in metadata table
        # Relationships are tracked via bundle_id
        pass

    def get_archived_document(self, pdf_path: str) -> dict[str, Any] | None:
        """
        Get archived document by PDF path.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Document metadata dict if found, None otherwise
        """
        # Query pdf_files table
        result = self.conn.fetch_one_dict(
            """
            SELECT
                p.pdf_path,
                p.pdf_filename,
                p.page_count,
                p.generated_at,
                b.bundle_name,
                b.confidence_score,
                b.status
            FROM pdf_files p
            LEFT JOIN document_bundles b ON p.bundle_id = b.id
            WHERE p.pdf_path = ?
        """,
            (pdf_path,),
        )

        if not result:
            return None

        return dict(result)

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

        if not row:
            return {"total_pdfs": 0, "total_pages": 0}

        return {
            "total_pdfs": row[0] or 0,
            "total_pages": row[1] or 0,
        }
