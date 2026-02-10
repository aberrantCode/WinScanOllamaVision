"""
Repository for pdf_image_pages junction table.

Manages the many-to-many relationship between PDFs and images.
"""

from typing import Any

from db.connection import DatabaseConnection


class PdfImagePagesRepository:
    """Manages PDF-to-image page mappings."""

    def __init__(self, conn: DatabaseConnection):
        """
        Initialize repository.

        Args:
            conn: Database connection
        """
        self.conn = conn

    def add_page(self, pdf_file_id: int, image_file_id: int, page_number: int) -> int:
        """
        Add an image to a PDF at a specific page number.

        Args:
            pdf_file_id: PDF file ID
            image_file_id: Image file ID
            page_number: Page number in the PDF (1-indexed)

        Returns:
            ID of the created record
        """
        cursor = self.conn.execute(
            """
            INSERT INTO pdf_image_pages (pdf_file_id, image_file_id, page_number)
            VALUES (?, ?, ?)
            """,
            (pdf_file_id, image_file_id, page_number),
        )
        self.conn.commit()
        return cursor.lastrowid if cursor.lastrowid else 0

    def get_images_for_pdf(self, pdf_file_id: int) -> list[dict[str, Any]]:
        """
        Get all images in a PDF, ordered by page number.

        Args:
            pdf_file_id: PDF file ID

        Returns:
            List of image records with page numbers
        """
        return self.conn.fetch_all_dicts(
            """
            SELECT
                pip.id,
                pip.page_number,
                img.*
            FROM pdf_image_pages pip
            INNER JOIN image_files img ON pip.image_file_id = img.id
            WHERE pip.pdf_file_id = ?
            ORDER BY pip.page_number
            """,
            (pdf_file_id,),
        )

    def get_pdfs_for_image(self, image_file_id: int) -> list[dict[str, Any]]:
        """
        Get all PDFs that contain a specific image.

        Args:
            image_file_id: Image file ID

        Returns:
            List of PDF records
        """
        return self.conn.fetch_all_dicts(
            """
            SELECT
                pdf.*,
                pip.page_number
            FROM pdf_image_pages pip
            INNER JOIN pdf_files pdf ON pip.pdf_file_id = pdf.id
            WHERE pip.image_file_id = ?
            ORDER BY pdf.generated_at DESC
            """,
            (image_file_id,),
        )

    def remove_page(self, pdf_file_id: int, page_number: int) -> None:
        """
        Remove a page from a PDF.

        Args:
            pdf_file_id: PDF file ID
            page_number: Page number to remove
        """
        self.conn.execute(
            "DELETE FROM pdf_image_pages WHERE pdf_file_id = ? AND page_number = ?",
            (pdf_file_id, page_number),
        )
        self.conn.commit()

    def remove_all_pages(self, pdf_file_id: int) -> None:
        """
        Remove all pages from a PDF.

        Args:
            pdf_file_id: PDF file ID
        """
        self.conn.execute(
            "DELETE FROM pdf_image_pages WHERE pdf_file_id = ?",
            (pdf_file_id,),
        )
        self.conn.commit()

    def get_page_count(self, pdf_file_id: int) -> int:
        """
        Get the number of pages in a PDF.

        Args:
            pdf_file_id: PDF file ID

        Returns:
            Number of pages
        """
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM pdf_image_pages WHERE pdf_file_id = ?",
            (pdf_file_id,),
        )
        result = cursor.fetchone()
        return int(result[0]) if result else 0
