"""
Analysis repository for managing analysis results persistence.

Simplified CRUD operations for analysis provenance and audit trail.
After Migration 16, this repository focuses solely on LLM analysis tracking,
not document metadata (which goes in metadata table).
"""

import json
import sqlite3
from typing import Any

from db.connection import DatabaseConnection
from services.logging_service import get_logger

logger = get_logger()


class AnalysisRepository:
    """Manages analysis results persistence (provenance and audit trail only)."""

    def __init__(self, conn: DatabaseConnection):
        """
        Initialize analysis repository.

        Args:
            conn: Database connection
        """
        self.conn = conn

    def save(
        self,
        image_file_id: int,
        provider_name: str,
        model_name: str,
        prompt_text: str,
        response_text: str,
        confidence_score: float | None,
        processing_time_ms: int,
        had_error: bool = False,
        extracted_metadata: dict[str, Any] | None = None,
        model_options: dict[str, Any] | None = None,
    ) -> int:
        """
        Save analysis results for provenance tracking.

        After Migration 16, this method no longer saves document metadata fields
        (company, document_type, etc.) - those go in the metadata table.

        Args:
            image_file_id: Foreign key to image_files table
            provider_name: Name of LLM provider used
            model_name: Model name/identifier
            prompt_text: The prompt text sent to the LLM
            response_text: Full LLM response text
            confidence_score: LLM's confidence in the analysis (0.0 to 1.0)
            processing_time_ms: Processing time in milliseconds
            had_error: Whether the analysis encountered an error
            extracted_metadata: Parsed metadata dict (for structured queries)
            model_options: Model parameters (temperature, top_p, etc.)

        Returns:
            The ID of the inserted analysis record

        Raises:
            ValueError: If image_file_id is invalid (foreign key constraint)
            sqlite3.OperationalError: If database is locked
            sqlite3.Error: If database operation fails
        """
        try:
            cursor = self.conn.execute(
                """
                INSERT INTO analysis_results (
                    image_file_id, provider_name, model_name, model_options,
                    prompt_text, response_text, extracted_metadata,
                    confidence_score, had_error, analyzed_at, processing_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            """,
                (
                    image_file_id,
                    provider_name,
                    model_name,
                    json.dumps(model_options) if model_options else None,
                    prompt_text,
                    response_text,
                    json.dumps(extracted_metadata) if extracted_metadata else None,
                    confidence_score,
                    1 if had_error else 0,
                    processing_time_ms,
                ),
            )
            self.conn.commit()

            # Return the ID of the inserted row
            if cursor.lastrowid is None:
                raise sqlite3.Error("INSERT did not return row ID")
            return cursor.lastrowid

        except sqlite3.IntegrityError as e:
            logger.error(f"[ANALYSIS REPO] Foreign key constraint: {e}")
            self.conn.rollback()
            raise ValueError(f"Invalid image_file_id: {image_file_id}") from e
        except sqlite3.OperationalError as e:
            logger.error(f"[ANALYSIS REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError(f"Database operation failed: {e}") from e
        except sqlite3.Error as e:
            logger.error(f"[ANALYSIS REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to save analysis: {e}") from e

    def get_by_image_file_id(self, image_file_id: int) -> list[dict[str, Any]]:
        """
        Retrieve all analysis results for an image file.

        An image file may have multiple analyses (re-analyzed with different providers/models).

        Args:
            image_file_id: Foreign key to image_files table

        Returns:
            List of analysis dicts (may be empty)
        """
        return self.conn.fetch_all_dicts(
            """
            SELECT * FROM analysis_results
            WHERE image_file_id = ?
            ORDER BY analyzed_at DESC
            """,
            (image_file_id,),
            json_fields=["extracted_metadata", "model_options"],
        )

    def get_latest_by_image_file_id(self, image_file_id: int) -> dict[str, Any] | None:
        """
        Retrieve the most recent analysis result for an image file.

        Args:
            image_file_id: Foreign key to image_files table

        Returns:
            Analysis dict if found, None otherwise
        """
        return self.conn.fetch_one_dict(
            """
            SELECT * FROM analysis_results
            WHERE image_file_id = ?
            ORDER BY analyzed_at DESC
            LIMIT 1
            """,
            (image_file_id,),
            json_fields=["extracted_metadata", "model_options"],
        )

    def get_by_id(self, analysis_id: int) -> dict[str, Any] | None:
        """
        Retrieve a specific analysis result by ID.

        Args:
            analysis_id: Analysis result ID

        Returns:
            Analysis dict if found, None otherwise
        """
        return self.conn.fetch_one_dict(
            "SELECT * FROM analysis_results WHERE id = ?",
            (analysis_id,),
            json_fields=["extracted_metadata", "model_options"],
        )

    def get_all(
        self,
        provider_filter: str | None = None,
        had_error: bool | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve all analysis results with optional filtering.

        Args:
            provider_filter: Filter by provider name
            had_error: Filter by error status (True=errors only, False=successful only, None=all)
            limit: Maximum number of results to return

        Returns:
            List of analysis dicts
        """
        query = "SELECT * FROM analysis_results WHERE 1=1"
        params: list[Any] = []

        if provider_filter:
            query += " AND provider_name = ?"
            params.append(provider_filter)

        if had_error is not None:
            query += " AND had_error = ?"
            params.append(1 if had_error else 0)

        query += " ORDER BY analyzed_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        return self.conn.fetch_all_dicts(
            query, params=tuple(params), json_fields=["extracted_metadata", "model_options"]
        )

    def count_by_status(self) -> dict[str, int]:
        """
        Get counts of analysis results by status.

        Returns:
            Dict with 'successful', 'errors', and 'total' counts
        """
        cursor = self.conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN had_error = 0 THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN had_error = 1 THEN 1 ELSE 0 END) as errors
            FROM analysis_results
        """)
        row = cursor.fetchone()

        if row:
            return {
                "total": row[0] or 0,
                "successful": row[1] or 0,
                "errors": row[2] or 0,
            }

        return {"total": 0, "successful": 0, "errors": 0}

    def delete_by_image_file_id(self, image_file_id: int) -> int:
        """
        Delete all analysis results for an image file.

        Args:
            image_file_id: Foreign key to image_files table

        Returns:
            Number of deleted records
        """
        cursor = self.conn.execute(
            "DELETE FROM analysis_results WHERE image_file_id = ?",
            (image_file_id,),
        )
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            logger.error(f"[ANALYSIS REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            logger.error(f"[ANALYSIS REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to delete analysis records: {e}") from e
        return cursor.rowcount
