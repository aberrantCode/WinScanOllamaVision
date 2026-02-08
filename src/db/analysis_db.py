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
    BundleRepository,
    DirectoryRepository,
    ErrorRepository,
    ImageFilesRepository,
    PdfFilesRepository,
    ProviderRepository,
    RotationRepository,
)
from db.schema import create_all_tables


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
        self._errors = ErrorRepository(self.connection)
        self._rotation = RotationRepository(self.connection)
        self._audit = AuditRepository(self.connection)
        self._image_files = ImageFilesRepository(self.connection)
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
        self._analysis.save(
            file_path,
            file_hash,
            provider_name,
            model_name,
            analysis_data,
            raw_response,
            processing_time_ms,
        )

    def get_analysis(self, file_path: str) -> dict[str, Any] | None:
        """Retrieve analysis results for a file."""
        return self._analysis.get_by_path(file_path)

    def update_analysis_metadata(self, file_path: str, metadata: dict[str, Any]) -> None:
        """Update metadata fields for an existing analysis."""
        self._analysis.update_metadata(file_path, metadata)

    def get_analyzed_pages(
        self, directory_filter: str | None = None, provider_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Get list of analyzed pages with optional filters."""
        return self._analysis.get_all(directory_filter, provider_filter)

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
        self._providers.add(provider_name, provider_type, config, default_model, available_models)

    def get_active_provider(self) -> dict[str, Any] | None:
        """Get currently active LLM provider."""
        return self._providers.get_active()

    def set_active_provider(self, provider_name: str) -> None:
        """Set active LLM provider."""
        self._providers.set_active(provider_name)

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
        return self._bundles.save_suggestion(file_paths, bundle_metadata, confidence_score)

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
        self._bundles.update_metadata(
            bundle_id,
            company=metadata.get("company"),
            document_type=metadata.get("document_type"),
            document_date=metadata.get("document_date"),
            bundle_name=metadata.get("bundle_name"),
        )

    def get_bundled_file_paths(self) -> set[str]:
        """Get all file paths that are part of accepted or completed bundles."""
        return self._bundles.get_bundled_file_paths()

    def update_bundle_pdf_path(self, bundle_id: int, pdf_path: str) -> None:
        """Update bundle with generated PDF path."""
        self._bundles.update_pdf_path(bundle_id, pdf_path)

    # ==================== Rotation Methods ====================

    def save_rotation_preference(
        self, file_path: str, rotation_degrees: int, rotation_source: str
    ) -> None:
        """Save rotation preference for a file."""
        self._rotation.save_preference(file_path, rotation_degrees, rotation_source)

    def get_rotation_preference(self, file_path: str) -> dict[str, Any] | None:
        """Get rotation preference for a file."""
        if self.connection.connection is None:
            raise RuntimeError("Database connection not initialized")
        cursor = self.connection.connection.cursor()
        cursor.execute("SELECT * FROM rotation_preferences WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        return dict(row) if row else None

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
        if self.connection.connection is None:
            raise RuntimeError("Database connection not initialized")
        cursor = self.connection.connection.cursor()

        # Total analyzed pages
        cursor.execute("SELECT COUNT(*) FROM analysis_results")
        total_analyzed = cursor.fetchone()[0]

        # Cached analyses
        cursor.execute("SELECT COUNT(*) FROM analysis_results WHERE is_cached = 1")
        cached_count = cursor.fetchone()[0]

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

        # Provider count
        cursor.execute("SELECT COUNT(*) FROM llm_providers")
        total_providers = cursor.fetchone()[0]

        # Active provider
        active_provider = self.get_active_provider()

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
        if self.connection.connection is None:
            raise RuntimeError("Database connection not initialized")
        cursor = self.connection.connection.cursor()

        # Total analyses
        cursor.execute("SELECT COUNT(*) FROM analysis_results")
        total = cursor.fetchone()[0]

        # Average processing time
        cursor.execute("SELECT AVG(processing_time_ms) FROM analysis_results")
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
        if self.connection.connection is None:
            raise RuntimeError("Database connection not initialized")
        cursor = self.connection.connection.cursor()
        cursor.execute("""
            SELECT document_type, COUNT(*) as count
            FROM analysis_results
            WHERE document_type IS NOT NULL
            GROUP BY document_type
        """)
        return {row[0]: row[1] for row in cursor.fetchall()}

    # ==================== Image Files Methods ====================

    def register_image_file(
        self,
        file_path: str,
        file_hash: str,
        directory_path: str,
        filename: str,
        file_size: int,
        file_mtime: float,
    ) -> int:
        """Register a discovered image file."""
        return self._image_files.register(
            file_path, file_hash, directory_path, filename, file_size, file_mtime
        )

    def get_image_file(self, file_path: str) -> dict[str, Any] | None:
        """Get image file record by path."""
        return self._image_files.get_by_path(file_path)

    def get_images_by_directory(self, directory_path: str) -> list[dict[str, Any]]:
        """Get all images in a directory."""
        return self._image_files.get_by_directory(directory_path)

    def get_images_by_status(self, status: str) -> list[dict[str, Any]]:
        """Get images by status (registered, analyzed, etc)."""
        return self._image_files.get_by_status(status)

    def get_registered_images(self) -> list[dict[str, Any]]:
        """Get all registered (pending analysis) images."""
        return self._image_files.get_by_status("registered")

    def get_all_image_files(self) -> list[dict[str, Any]]:
        """Get all image files (excluding deleted)."""
        return self._image_files.get_all()

    def update_image_status(
        self, file_path: str, status: str, analysis_id: int | None = None
    ) -> None:
        """Update image file status."""
        self._image_files.update_status(file_path, status, analysis_id)

    def update_image_last_seen(self, file_path: str) -> None:
        """Update last_seen_at timestamp."""
        self._image_files.update_last_seen(file_path)

    def update_image_hash(self, file_path: str, file_hash: str) -> None:
        """Update file hash (used when file changes detected)."""
        self._image_files.update_hash(file_path, file_hash)

    def mark_image_deleted(self, file_path: str) -> None:
        """Mark image as deleted (soft delete)."""
        self._image_files.mark_deleted(file_path)

    def mark_images_deleted_batch(self, file_paths: list[str]) -> int:
        """Mark multiple images as deleted (batch operation)."""
        return self._image_files.mark_deleted_batch(file_paths)

    def set_image_output_filename(self, file_path: str, output_filename: str) -> None:
        """Set proposed output filename for image."""
        self._image_files.set_output_filename(file_path, output_filename)

    def get_image_files_stats(self) -> dict[str, int]:
        """Get image files statistics."""
        return self._image_files.get_stats()

    # ==================== PDF Files Methods ====================

    def register_pdf_file(
        self,
        pdf_path: str,
        pdf_filename: str,
        bundle_id: int,
        source_image_ids: list[int],
        page_count: int,
        file_hash: str | None = None,
        file_size: int | None = None,
    ) -> int:
        """Register a generated PDF."""
        return self._pdf_files.register(
            pdf_path, pdf_filename, bundle_id, source_image_ids, page_count, file_hash, file_size
        )

    def get_pdf_file(self, pdf_path: str) -> dict[str, Any] | None:
        """Get PDF record by path."""
        return self._pdf_files.get_by_path(pdf_path)

    def get_pdf_by_bundle(self, bundle_id: int) -> dict[str, Any] | None:
        """Get PDF by bundle ID."""
        return self._pdf_files.get_by_bundle(bundle_id)

    def update_pdf_generation_status(self, pdf_path: str, status: str) -> None:
        """Update PDF generation status."""
        self._pdf_files.update_generation_status(pdf_path, status)

    def update_pdf_searchability(self, pdf_path: str, is_searchable: bool) -> None:
        """Update PDF searchability flag."""
        self._pdf_files.update_searchability(pdf_path, is_searchable)

    def get_all_pdf_files(self) -> list[dict[str, Any]]:
        """Get all generated PDFs."""
        return self._pdf_files.get_all()

    def get_pdf_files_stats(self) -> dict[str, int]:
        """Get PDF files statistics."""
        return self._pdf_files.get_stats()

    # ==================== Utility Methods ====================

    def close(self):
        """Close database connection."""
        self.connection.close()
