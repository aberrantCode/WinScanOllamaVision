"""
Bundle repository for managing document bundle suggestions.

Simplified CRUD operations for AI-generated document bundles.
"""

import json
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
        file_paths: list[str],
        bundle_metadata: dict[str, Any],
        confidence_score: float,
    ) -> int:
        """
        Save a document bundle suggestion.

        Args:
            file_paths: List of file paths in bundle
            bundle_metadata: Bundle metadata (company, type, date, etc.)
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
                bundle_name, company, document_type, document_date,
                total_pages, confidence_score, confidence_level,
                file_paths, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'suggested')
        """,
            (
                bundle_metadata.get("bundle_name"),
                bundle_metadata.get("company"),
                bundle_metadata.get("document_type"),
                bundle_metadata.get("document_date"),
                len(file_paths),
                confidence_score,
                confidence_level,
                json.dumps(file_paths),
            ),
        )

        self.conn.commit()
        return cursor.lastrowid

    def get_suggestions(
        self, status_filter: str = "suggested", min_confidence: float | None = None
    ) -> list[dict[str, Any]]:
        """
        Get bundle suggestions with optional filtering.

        Args:
            status_filter: Bundle status filter (default: 'suggested')
            min_confidence: Minimum confidence score

        Returns:
            List of bundle dicts
        """
        query = "SELECT * FROM document_bundles WHERE status = ?"
        params = [status_filter]

        if min_confidence is not None:
            query += " AND confidence_score >= ?"
            params.append(min_confidence)

        query += " ORDER BY confidence_score DESC, created_at DESC"

        return self.conn.fetch_all_dicts(query, params=tuple(params), json_fields=["file_paths"])

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
