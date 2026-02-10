"""
Bundle repository for managing document bundle suggestions.

Simplified CRUD operations for AI-generated document bundles.
"""

from typing import Any

from db.connection import DatabaseConnection


class BundleRepository:
    """Manages document bundle suggestion persistence."""

    def __init__(self, conn: DatabaseConnection):
        """
        Initialize bundle repository.

        Args:
            conn: Database connection
        """
        self.conn = conn

    def save_suggestion(
        self,
        bundle_metadata: dict[str, Any],
        confidence_score: float,
        total_pages: int,
    ) -> int | None:
        """
        Save a document bundle suggestion.

        NOTE: After creating bundle, use BundleImagesRepository to add images via junction table.

        Args:
            bundle_metadata: Bundle metadata (company, type, date, etc.)
            confidence_score: Confidence score (0.0 to 1.0)
            total_pages: Number of pages in bundle

        Returns:
            Bundle ID
        """
        # Determine confidence level
        if confidence_score >= 0.8:
            confidence_level = "high"
        elif confidence_score >= 0.5:
            confidence_level = "medium"
        else:
            confidence_level = "low"

        cursor = self.conn.execute(
            """
            INSERT INTO document_bundles (
                bundle_name, company, document_type, document_date,
                total_pages, confidence_score, confidence_level, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'suggested')
        """,
            (
                bundle_metadata.get("bundle_name"),
                bundle_metadata.get("company"),
                bundle_metadata.get("document_type"),
                bundle_metadata.get("document_date"),
                total_pages,
                confidence_score,
                confidence_level,
            ),
        )

        self.conn.commit()
        return cursor.lastrowid

    def get_suggestions(
        self, status_filter: str = "suggested", min_confidence: float | None = None
    ) -> list[dict[str, Any]]:
        """
        Get bundle suggestions with optional filtering.

        NOTE: Does not include file_paths - use BundleImagesRepository to fetch images.

        Args:
            status_filter: Bundle status filter (default: 'suggested')
            min_confidence: Minimum confidence score

        Returns:
            List of bundle dicts (without file_paths)
        """
        query = "SELECT * FROM document_bundles WHERE status = ?"
        params: list[str | float] = [status_filter]

        if min_confidence is not None:
            query += " AND confidence_score >= ?"
            params.append(min_confidence)

        query += " ORDER BY confidence_score DESC, created_at DESC"

        return self.conn.fetch_all_dicts(query, params=tuple(params))

    def update_status(self, bundle_id: int, status: str, user_action: str | None = None) -> None:
        """
        Update bundle status after user action.

        Args:
            bundle_id: Bundle ID
            status: New status (accepted, rejected, modified, completed)
            user_action: Description of user action
        """
        self.conn.execute(
            """
            UPDATE document_bundles
            SET status = ?, user_action = ?, action_timestamp = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (status, user_action, bundle_id),
        )
        self.conn.commit()

    def update_metadata(
        self,
        bundle_id: int,
        company: str | None = None,
        document_type: str | None = None,
        document_date: str | None = None,
        bundle_name: str | None = None,
    ) -> None:
        """
        Update bundle metadata fields.

        Args:
            bundle_id: Bundle ID
            company: Updated company name
            document_type: Updated document type
            document_date: Updated document date
            bundle_name: Updated bundle name
        """
        updates: list[str] = []
        params: list[str | int] = []

        if company is not None:
            updates.append("company = ?")
            params.append(company)

        if document_type is not None:
            updates.append("document_type = ?")
            params.append(document_type)

        if document_date is not None:
            updates.append("document_date = ?")
            params.append(document_date)

        if bundle_name is not None:
            updates.append("bundle_name = ?")
            params.append(bundle_name)

        if not updates:
            return

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(bundle_id)

        query = f"""
            UPDATE document_bundles
            SET {", ".join(updates)}
            WHERE id = ?
        """

        self.conn.execute(query, tuple(params))
        self.conn.commit()

    def get_bundled_file_paths(self) -> set[str]:
        """
        Get all file paths that are part of accepted or completed bundles.

        Uses bundle_images junction table to find bundled images.

        Returns:
            Set of file paths already in processed bundles
        """
        cursor = self.conn.execute("""
            SELECT DISTINCT img.file_path
            FROM document_bundles b
            INNER JOIN bundle_images bi ON b.id = bi.bundle_id
            INNER JOIN image_files img ON bi.image_file_id = img.id
            WHERE b.status IN ('accepted', 'completed')
        """)
        return {row[0] for row in cursor.fetchall()}

    def update_pdf_path(self, bundle_id: int, pdf_path: str) -> None:
        """
        Update bundle with generated PDF path.

        Args:
            bundle_id: Bundle ID
            pdf_path: Full path to generated PDF
        """
        self.conn.execute(
            """
            UPDATE document_bundles
            SET pdf_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (pdf_path, bundle_id),
        )
        self.conn.commit()
