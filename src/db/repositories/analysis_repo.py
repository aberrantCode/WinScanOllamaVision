"""
Analysis repository for managing analysis results persistence.

Simplified CRUD operations for page-level analysis data.
"""

import json
from typing import Any

from db.connection import DatabaseConnection


class AnalysisRepository:
    """Manages analysis results persistence."""

    def __init__(self, conn: DatabaseConnection):
        """
        Initialize analysis repository.

        Args:
            conn: Database connection
        """
        self.conn = conn

    def save(
        self,
        file_path: str,
        file_hash: str,
        provider_name: str,
        model_name: str,
        analysis_data: dict[str, Any],
        raw_response: str,
        processing_time_ms: int,
    ) -> None:
        """
        Save comprehensive page analysis results.

        Args:
            file_path: Path to analyzed file
            file_hash: SHA-256 hash of file
            provider_name: Name of LLM provider used
            model_name: Model name/identifier
            analysis_data: Extracted metadata dict
            raw_response: Full LLM response text
            processing_time_ms: Processing time in milliseconds
        """
        self.conn.execute(
            """
            INSERT OR REPLACE INTO analysis_results (
                file_path, file_hash, provider_name, model_name,
                document_type, company, document_date,
                page_number, total_pages, belongs_to_same_doc,
                confidence_score, rotation_needed, suggested_rotation,
                rotation_confidence, tax_related, raw_response, extracted_metadata,
                processing_time_ms, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (
                file_path,
                file_hash,
                provider_name,
                model_name,
                analysis_data.get("document_type"),
                analysis_data.get("company"),
                analysis_data.get("document_date"),
                analysis_data.get("page_number"),
                analysis_data.get("total_pages"),
                analysis_data.get("belongs_to_same_doc", False),
                analysis_data.get("confidence_score"),
                analysis_data.get("rotation_needed", False),
                analysis_data.get("suggested_rotation", 0),
                analysis_data.get("rotation_confidence"),
                analysis_data.get("tax_related", False),
                raw_response,
                json.dumps(analysis_data),
                processing_time_ms,
            ),
        )
        self.conn.commit()

    def update_metadata(self, file_path: str, metadata: dict[str, Any]) -> None:
        """
        Update metadata fields for an existing analysis.

        Args:
            file_path: Path to file
            metadata: Dictionary with updated metadata fields
        """
        # Build UPDATE query dynamically for provided fields
        update_fields = []
        values = []

        field_mapping = {
            "document_type": "document_type",
            "company": "company",
            "document_date": "document_date",
            "page_number": "page_number",
            "total_pages": "total_pages",
            "rotation_needed": "rotation_needed",
            "confidence_score": "confidence_score",
            "tax_related": "tax_related",
        }

        for meta_key, db_column in field_mapping.items():
            if meta_key in metadata and metadata[meta_key]:
                update_fields.append(f"{db_column} = ?")
                values.append(metadata[meta_key])

        if update_fields:
            # Update extracted_metadata JSON field as well
            update_fields.append("extracted_metadata = ?")
            values.append(json.dumps(metadata))

            # Add file_path for WHERE clause
            values.append(file_path)

            # Column names from internal code, values parameterized - safe from injection
            query = f"""
                UPDATE analysis_results
                SET {", ".join(update_fields)}
                WHERE file_path = ?
            """  # nosec B608

            self.conn.execute(query, tuple(values))
            self.conn.commit()

    def get_by_path(self, file_path: str) -> dict[str, Any] | None:
        """
        Retrieve analysis results for a file.

        Args:
            file_path: Path to file

        Returns:
            Analysis dict if found, None otherwise
        """
        analysis = self.conn.fetch_one_dict(
            "SELECT * FROM analysis_results WHERE file_path = ?",
            (file_path,),
            json_fields=["extracted_metadata"],
        )

        if analysis:
            # Increment cache hit counter
            self.conn.execute(
                """
                UPDATE analysis_results
                SET cache_hit_count = cache_hit_count + 1, is_cached = 1
                WHERE file_path = ?
            """,
                (file_path,),
            )
            self.conn.commit()

        return analysis

    def get_all(
        self, directory_filter: str | None = None, provider_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Retrieve all analyzed pages with optional filtering.

        Args:
            directory_filter: Filter by directory path
            provider_filter: Filter by provider name

        Returns:
            List of analysis dicts
        """
        query = "SELECT * FROM analysis_results WHERE 1=1"
        params = []

        if directory_filter:
            query += " AND file_path LIKE ?"
            params.append(f"{directory_filter}%")

        if provider_filter:
            query += " AND provider_name = ?"
            params.append(provider_filter)

        query += " ORDER BY analyzed_at DESC"

        return self.conn.fetch_all_dicts(
            query, params=tuple(params), json_fields=["extracted_metadata"]
        )
