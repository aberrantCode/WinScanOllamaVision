"""
Refactored AnalysisDB - thin wrapper around repositories.

Maintains existing API while delegating to focused repository classes.
"""

import os
from typing import Any

from db.connection import DatabaseConnection, get_appdata_db_path
from db.repositories import (
    AnalysisRepository,
    AuditRepository,
    BundleImagesRepository,
    BundleRepository,
    DirectoryRepository,
    ErrorRepository,
    ImageFilesRepository,
    MetadataRepository,
    PdfFilesRepository,
    ProviderRepository,
    RotationRepository,
)
from db.schema import create_all_tables
from services.metadata_normalizer import MetadataNormalizer


class AnalysisDB:
    """Manages extended SQLite database for analysis results and bundling."""

    def __init__(self, db_path: str | None = None):
        """
        Initialize analysis database connection.

        Args:
            db_path: Path to SQLite database file. If None, uses AppData directory.
        """
        if db_path is None:
            db_path = get_appdata_db_path()

        self.db_path = db_path
        self.connection = DatabaseConnection(db_path)

        # Create tables
        create_all_tables(self.connection)

        # Initialize repositories
        self._analysis = AnalysisRepository(self.connection)
        self._providers = ProviderRepository(self.connection)
        self._directories = DirectoryRepository(self.connection)
        self._bundles = BundleRepository(self.connection)
        self._bundle_images = BundleImagesRepository(self.connection)
        self._errors = ErrorRepository(self.connection)
        self._rotation = RotationRepository(self.connection)
        self._audit = AuditRepository(self.connection)
        self._image_files = ImageFilesRepository(self.connection)
        self._metadata = MetadataRepository(self.connection)
        self._pdf_files = PdfFilesRepository(self.connection)

    # ==================== Analysis Results Methods ====================

    def save_analysis(
        self,
        file_path: str,
        file_hash: str,
        provider_name: str,
        model_name: str,
        analysis_data: dict[str, Any],
        raw_response: str,
        processing_time_ms: int,
    ) -> None:
        """Save comprehensive page analysis results."""
        # Get or create image_file record
        image_file = self._image_files.get_by_path(file_path)
        if not image_file:
            # Register new image file
            directory_path = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            file_mtime = os.path.getmtime(file_path) if os.path.exists(file_path) else 0.0

            image_file_id = self._image_files.register(
                file_path, file_hash, directory_path, filename, file_size, file_mtime
            )
        else:
            image_file_id = image_file["id"]

        # Save analysis result to analysis_results table
        analysis_id = self._analysis.save(
            image_file_id=image_file_id,
            provider_name=provider_name,
            model_name=model_name,
            prompt_text=analysis_data.get("prompt", ""),
            response_text=raw_response,
            confidence_score=analysis_data.get("confidence_score"),
            processing_time_ms=processing_time_ms,
            had_error=False,
            extracted_metadata=analysis_data,
            model_options=None,
        )

        # Normalize and save metadata to metadata table
        normalizer = MetadataNormalizer()
        normalized_metadata = normalizer.normalize(analysis_data)
        self._metadata.create_from_analysis(
            image_file_id=image_file_id,
            analysis_result_id=analysis_id,
            normalized_metadata=normalized_metadata,
            output_filename=analysis_data.get("output_filename"),
            document_category=analysis_data.get("document_category"),
        )

    def get_analysis(self, file_path: str) -> dict[str, Any] | None:
        """Retrieve analysis results for a file."""
        # Get image_file_id from file_path
        image_file = self._image_files.get_by_path(file_path)
        if not image_file:
            return None

        # Get latest analysis result
        return self._analysis.get_latest_by_image_file_id(image_file["id"])

    def get_analysis_with_metadata(self, file_path: str) -> dict[str, Any] | None:
        """Retrieve analysis results with normalized metadata for a file."""
        # Get all data in one query using the efficient join
        results = self._image_files.get_batch_with_analysis([file_path])
        return results.get(os.path.normpath(file_path))

    def update_analysis_metadata(self, file_path: str, metadata: dict[str, Any]) -> None:
        """Update metadata fields for an existing analysis."""
        # Get image_file_id from file_path
        image_file = self._image_files.get_by_path(file_path)
        if not image_file:
            return

        # Update metadata table (not analysis_results)
        self._metadata.update_from_user(image_file["id"], metadata)

    def get_analyzed_pages(
        self, directory_filter: str | None = None, provider_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Get list of analyzed pages with optional filters."""
        # Use image_files repository to get all images with their analysis data
        return self._image_files.get_all_with_analysis(directory_filter, provider_filter)

    # ==================== Provider Methods ====================

    def add_provider(
        self,
        provider_name: str,
        provider_type: str,
        config: dict[str, Any],
        default_model: str | None = None,
        available_models: list[str] | None = None,
    ) -> None:
        """Add or update LLM provider configuration."""
        self._providers.add(
            provider_name, provider_type, config, default_model, available_models
        )  # pragma: no cover

    def get_active_provider(self) -> dict[str, Any] | None:
        """Get currently active LLM provider."""
        return self._providers.get_active()

    def set_active_provider(self, provider_name: str) -> None:
        """Set active LLM provider."""
        self._providers.set_active(provider_name)  # pragma: no cover

    # ==================== Directory Methods ====================

    def add_source_directory(self, directory_path: str, scan_on_startup: bool = True) -> None:
        """Add a source directory."""
        self._directories.add(directory_path, scan_on_startup)

    def get_active_directories(self) -> list[str]:
        """Get list of active source directories."""
        return self._directories.get_active()

    def remove_source_directory(self, directory_path: str) -> None:
        """Remove a source directory."""
        self._directories.remove(directory_path)

    def update_directory_scan_info(self, directory_path: str, file_count: int) -> None:
        """Update directory scan information."""
        self._directories.update_scan_info(directory_path, file_count)

    # ==================== Bundle Methods ====================

    def save_bundle_suggestion(
        self, file_paths: list[str], bundle_metadata: dict[str, Any], confidence_score: float
    ) -> int | None:
        """Save a document bundle suggestion."""
        # Create bundle record (without file_paths - that's in junction table)
        bundle_id = self._bundles.save_suggestion(bundle_metadata, confidence_score)

        if bundle_id and file_paths:
            # Add images to bundle via junction table
            for sequence, file_path in enumerate(file_paths, start=1):
                image_file = self._image_files.get_by_path(file_path)
                if image_file:
                    self._bundle_images.add_image(bundle_id, image_file["id"], sequence)

        return bundle_id

    def get_bundle_suggestions(
        self, status_filter: str = "suggested", min_confidence: float | None = None
    ) -> list[dict[str, Any]]:
        """Get bundle suggestions with optional filters."""
        return self._bundles.get_suggestions(status_filter, min_confidence)

    def update_bundle_status(
        self, bundle_id: int, status: str, user_action: str | None = None
    ) -> None:
        """Update bundle status after user action."""
        self._bundles.update_status(bundle_id, status, user_action)

    def update_bundle_metadata(self, bundle_id: int, metadata: dict[str, Any]) -> None:
        """Update bundle metadata fields."""
        # Update bundle_name if present
        if "bundle_name" in metadata:
            self._bundles.update_bundle_name(bundle_id, metadata["bundle_name"])

        # Note: company, document_type, document_date are stored in metadata table,
        # not in document_bundles table. They are per-image metadata.

    def get_bundled_file_paths(self) -> set[str]:
        """Get all file paths that are part of accepted or completed bundles."""
        return self._bundles.get_bundled_file_paths()

    def update_bundle_pdf_path(self, bundle_id: int, pdf_path: str) -> None:
        """Update bundle with generated PDF path."""
        # Register PDF file in pdf_files table (linked to bundle)
        pdf_filename = os.path.basename(pdf_path)
        file_hash = None
        file_size = os.path.getsize(pdf_path) if os.path.exists(pdf_path) else None

        # Count pages would need PDF parsing - for now use 0 as placeholder
        # This should be passed in or calculated by the caller
        page_count = 0

        self._pdf_files.register(
            pdf_path=pdf_path,
            pdf_filename=pdf_filename,
            bundle_id=bundle_id,
            page_count=page_count,
            file_hash=file_hash,
            file_size=file_size,
        )

    # ==================== Image Status Methods ====================

    def update_image_status(self, file_path: str, status: str) -> None:
        """Update image file status."""
        self._image_files.update_status(file_path, status)

    def update_analysis_status(self, file_path: str, status: str) -> None:
        """Update image status (alias for update_image_status for backward compat)."""
        self._image_files.update_status(file_path, status)

    def mark_image_deleted(self, file_path: str) -> None:
        """Soft-delete an image file record (sets status to 'deleted')."""
        self._image_files.mark_deleted(file_path)

    def delete_metadata_by_path(self, file_path: str) -> None:
        """Delete metadata record for the given file path."""
        image_file = self._image_files.get_by_path(file_path)
        if image_file:
            self._metadata.delete_by_image_file_id(image_file["id"])

    def get_distinct_field_values(self, field_name: str) -> list[str]:
        """
        Get distinct non-empty values for a validated field from the database.

        Only fields in a strict whitelist are accepted to prevent SQL injection.
        Field routing to the correct table is determined internally.

        Args:
            field_name: Column name to query (must be in the allowed whitelist).

        Returns:
            Sorted list of distinct non-empty string values, or [] on error/invalid field.
        """
        allowed_columns: dict[str, str] = {
            "provider_name": "analysis_results",
            "model_name": "analysis_results",
            "company": "metadata",
            "document_type": "metadata",
            "document_date": "metadata",
            "document_category": "metadata",
            "page_number": "metadata",
            "total_pages": "metadata",
            "confidence_score": "metadata",
            "file_path": "image_files",
        }

        if field_name not in allowed_columns:
            return []

        table = allowed_columns[field_name]
        assert self.connection.connection is not None
        try:
            query = (
                f"SELECT DISTINCT {field_name} FROM {table}"
                f" WHERE {field_name} IS NOT NULL AND {field_name} != ''"
                f" ORDER BY {field_name}"
            )
            result = self.connection.connection.execute(query).fetchall()
            return [row[0] for row in result if row[0]]
        except Exception:
            return []

    # ==================== Rotation Methods ====================
    # Note: Rotation is now stored in metadata.rotation column
    # Use RotationRepository for rotation operations

    def get_image_rotation(self, file_path: str) -> int:
        """
        Get rotation angle for an image file.

        Args:
            file_path: Absolute path to image file

        Returns:
            Rotation angle in degrees (0, 90, 180, 270)
        """
        return self._rotation.get(file_path)

    def save_image_rotation(self, file_path: str, rotation_degrees: int) -> None:
        """
        Save rotation angle for an image file.

        Args:
            file_path: Absolute path to image file
            rotation_degrees: Rotation angle in degrees (0, 90, 180, 270)
        """
        self._rotation.save(file_path, rotation_degrees)

    # ==================== Audit Trail Methods ====================

    def log_action(
        self,
        action_type: str,
        action_details: str,
        file_path: str | None = None,
        bundle_id: int | None = None,
    ) -> None:
        """Log user action to audit trail."""
        self._audit.log_action(action_type, action_details, file_path, bundle_id)

    # ==================== Error Management Methods ====================

    def get_failed_analyses(self) -> list[dict[str, Any]]:
        """Get list of failed analyses."""
        return self._errors.get_all_errors()

    def save_error(
        self, file_path: str, error_message: str, error_type: str = "analysis_failed"
    ) -> None:
        """Save an analysis error record."""
        self._errors.save_error(file_path, error_message, error_type)

    def get_all_errors(self) -> list[dict[str, Any]]:
        """Get all error records."""
        return self._errors.get_all_errors()

    def get_error_count(self) -> int:
        """Get total count of errors."""
        return self._errors.get_error_count()

    def clear_error(self, file_path: str) -> None:
        """Clear error record for a specific file."""
        self._errors.clear_error(file_path)

    # ==================== Statistics Methods ====================

    def get_extended_statistics(self) -> dict[str, Any]:
        """Get extended analysis statistics."""
        assert self.connection.connection is not None
        cursor = self.connection.connection.cursor()

        # Total analyzed pages
        cursor.execute("SELECT COUNT(*) FROM analysis_results")
        total_analyzed = cursor.fetchone()[0]

        # Cached analyses (files with multiple analysis results)
        cursor.execute("""
            SELECT COUNT(DISTINCT image_file_id)
            FROM analysis_results
            GROUP BY image_file_id
            HAVING COUNT(*) > 1
        """)
        cached_count = len(cursor.fetchall())

        # Average processing time
        cursor.execute(
            "SELECT AVG(processing_time_ms) FROM analysis_results WHERE processing_time_ms IS NOT NULL"
        )
        avg_time = cursor.fetchone()[0] or 0

        # Bundle counts
        cursor.execute("SELECT COUNT(*) FROM document_bundles WHERE status = 'suggested'")
        pending_bundles = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM document_bundles WHERE status = 'accepted'")
        accepted_bundles = cursor.fetchone()[0]

        # Provider count (distinct providers used in analyses)
        cursor.execute("SELECT COUNT(DISTINCT provider_name) FROM analysis_results")
        total_providers = cursor.fetchone()[0]

        # Active provider (from config, not database)
        try:
            active_provider = self.get_active_provider()
        except Exception:
            # llm_providers table may not exist in older schemas
            active_provider = None

        # Active directories
        cursor.execute("SELECT COUNT(*) FROM source_directories WHERE is_active = 1")
        active_dirs = cursor.fetchone()[0]

        # Audit entries
        cursor.execute("SELECT COUNT(*) FROM audit_trail")
        audit_count = cursor.fetchone()[0]

        # Database size
        db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0

        return {
            "total_analyzed_pages": total_analyzed,
            "cached_analyses": cached_count,
            "avg_processing_time_ms": avg_time,
            "pending_bundles": pending_bundles,
            "accepted_bundles": accepted_bundles,
            "total_providers": total_providers,
            "active_provider": active_provider["provider_name"] if active_provider else None,
            "active_directories": active_dirs,
            "total_actions_logged": audit_count,
            "database_size_bytes": db_size,
        }

    def get_analysis_statistics(self) -> dict[str, Any]:
        """Get comprehensive analysis statistics."""
        assert self.connection.connection is not None
        cursor = self.connection.connection.cursor()

        # Total analyses
        cursor.execute("SELECT COUNT(*) FROM analysis_results")
        total = cursor.fetchone()[0]

        # Average processing time (exclude cache hits < 1000ms)
        cursor.execute(
            """
            SELECT AVG(processing_time_ms)
            FROM analysis_results
            WHERE processing_time_ms >= 1000
        """
        )
        avg_time = cursor.fetchone()[0] or 0

        # Provider breakdown
        cursor.execute("""
            SELECT provider_name, COUNT(*) as count
            FROM analysis_results
            GROUP BY provider_name
        """)
        provider_breakdown = {row[0]: row[1] for row in cursor.fetchall()}

        return {
            "total_analyses": total,
            "avg_processing_time_ms": avg_time,
            "provider_breakdown": provider_breakdown,
        }

    def get_document_type_breakdown(self) -> dict[str, int]:
        """Get count of documents by type."""
        assert self.connection.connection is not None
        cursor = self.connection.connection.cursor()
        # document_type is stored in metadata table, not analysis_results
        cursor.execute("""
            SELECT document_type, COUNT(*) as count
            FROM metadata
            WHERE document_type IS NOT NULL
            GROUP BY document_type
        """)
        return {row[0]: row[1] for row in cursor.fetchall()}

    # ==================== Utility Methods ====================

    def purge_all_data(self) -> None:
        """
        Delete all data from all tables (preserves schema).

        WARNING: This is destructive and cannot be undone!
        """
        assert self.connection.connection is not None
        cursor = self.connection.connection.cursor()

        # Delete data from all tables in dependency order (child tables first)
        tables_to_purge = [
            "bundle_images",  # References document_bundles and image_files
            "pdf_image_pages",  # References pdf_files and image_files
            "analysis_errors",  # References image_files
            "analysis_results",  # References image_files
            "document_bundles",  # No foreign key dependencies
            "pdf_files",  # No foreign key dependencies
            "image_files",  # Referenced by many tables
            "audit_trail",  # No foreign key dependencies
            "source_directories",  # No foreign key dependencies
        ]

        for table in tables_to_purge:
            cursor.execute(f"DELETE FROM {table}")

        self.connection.commit()

    def purge_analysis_results(self) -> None:
        """
        Delete all rows from the analysis_results table (preserves schema).

        WARNING: This is destructive and cannot be undone!
        """
        assert self.connection.connection is not None
        cursor = self.connection.connection.cursor()
        cursor.execute("DELETE FROM analysis_results")
        self.connection.commit()

    def purge_bundles(self) -> None:
        """
        Delete all rows from document_bundles and the bundle_images junction table.

        WARNING: This is destructive and cannot be undone!
        """
        assert self.connection.connection is not None
        cursor = self.connection.connection.cursor()
        # Remove junction rows first to satisfy foreign-key constraints
        cursor.execute("DELETE FROM bundle_images")
        cursor.execute("DELETE FROM document_bundles")
        self.connection.commit()

    def close(self):
        """Close database connection."""
        self.connection.close()
