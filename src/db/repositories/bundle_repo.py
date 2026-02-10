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
    ) -> int | None:
        """
        Save a document bundle suggestion.

        NOTE: After creating bundle, use BundleImagesRepository to add images via junction table.
        Document metadata (company, type, date) should be stored in metadata table.

        Args:
            bundle_metadata: Bundle metadata (bundle_name, etc.)
            confidence_score: Confidence score (0.0 to 1.0)

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
                bundle_name, confidence_score, confidence_level, status
            ) VALUES (?, ?, ?, 'suggested')
        """,
            (
                bundle_metadata.get("bundle_name"),
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

    def update_bundle_name(
        self,
        bundle_id: int,
        bundle_name: str,
    ) -> None:
        """
        Update bundle name.

        NOTE: Document metadata (company, type, date) is stored in the metadata table,
        not in document_bundles.

        Args:
            bundle_id: Bundle ID
            bundle_name: Updated bundle name
        """
        self.conn.execute(
            """
            UPDATE document_bundles
            SET bundle_name = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (bundle_name, bundle_id),
        )
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
