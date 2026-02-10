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
    ImageFilesRepository,
    PdfFilesRepository,
    PdfImagePagesRepository,
)
from db.repositories.metadata_repo import MetadataRepository
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
        self._directories = DirectoryRepository(self.connection)
        self._bundles = BundleRepository(self.connection)
        self._bundle_images = BundleImagesRepository(self.connection)
        self._audit = AuditRepository(self.connection)
        self._image_files = ImageFilesRepository(self.connection)
        self._pdf_files = PdfFilesRepository(self.connection)
        self._pdf_image_pages = PdfImagePagesRepository(self.connection)
        self._metadata = MetadataRepository(self.connection)

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
        prompt_text: str | None = None,
        had_error: bool = False,
        model_options: dict[str, Any] | None = None,
    ) -> int:
        """
        Save comprehensive page analysis results.

        After Migration 16, this saves analysis provenance to analysis_results table.
        Metadata should be saved separately to metadata table via create_metadata_from_analysis().

        Args:
            file_path: Path to analyzed file
            file_hash: SHA-256 hash of file
            provider_name: Name of LLM provider used
            model_name: Model name/identifier
            analysis_data: Extracted metadata dict
            raw_response: Full LLM response text
            processing_time_ms: Processing time in milliseconds
            prompt_text: The actual prompt text sent to the LLM (optional)
            had_error: Whether the analysis encountered an error
            model_options: Model parameters (temperature, top_p, etc.)

        Returns:
            The analysis_id of the saved analysis
        """
        import os

        # Ensure image is registered in image_files table first
        # This is critical because get_analyzed_pages() queries from image_files
        existing = self._image_files.get_by_path(file_path)
        if not existing:
            # Register with basic info - get actual file stats if file exists
            directory_path = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            file_size = 0
            file_mtime = 0.0

            if os.path.exists(file_path):
                try:
                    stats = os.stat(file_path)
                    file_size = stats.st_size
                    file_mtime = stats.st_mtime
                except OSError:
                    pass  # Use defaults if stat fails

            self._image_files.register(
                file_path=file_path,
                file_hash=file_hash,
                directory_path=directory_path,
                filename=filename,
                file_size=file_size,
                file_mtime=file_mtime,
            )
            existing = self._image_files.get_by_path(file_path)

        if not existing:
            raise RuntimeError(f"Failed to register image file: {file_path}")

        image_file_id = existing["id"]

        # Save analysis results using new schema
        analysis_id = self._analysis.save(
            image_file_id=image_file_id,
            provider_name=provider_name,
            model_name=model_name,
            prompt_text=prompt_text or "",
            response_text=raw_response,
            confidence_score=analysis_data.get("confidence_score"),
            processing_time_ms=processing_time_ms,
            had_error=had_error,
            extracted_metadata=analysis_data if analysis_data else None,
            model_options=model_options,
        )

        # Update image file status to 'analyzed'
        if analysis_id:
            self._image_files.update_status(file_path, "analyzed")

        # Create metadata record if analysis was successful and has data
        if not had_error and analysis_data and analysis_id:
            # Import here to avoid circular dependency
            from services.metadata_normalizer import MetadataNormalizer

            try:
                normalizer = MetadataNormalizer()
                normalized = normalizer.normalize(analysis_data)

                self.create_metadata_from_analysis(
                    image_file_id=image_file_id,
                    analysis_id=analysis_id,
                    normalized_metadata=normalized,
                )
            except Exception:
                # If metadata normalization fails, continue without it
                # The analysis is still saved, just without metadata record
                pass

        # Update rotation from analysis data (only if not an error)
        if not had_error and analysis_data:
            rotation_needed = analysis_data.get("rotation_needed", "none")
            rotation_degrees = {
                "none": 0,
                "90_cw": 90,
                "90_ccw": 270,
                "180": 180,
            }.get(rotation_needed, 0)
            self.update_image_rotation(file_path, rotation_degrees)

        return analysis_id

    def get_analysis(self, file_path: str) -> dict[str, Any] | None:
        """
        Retrieve the latest analysis results for a file.

        Note: After Migration 16, this returns analysis provenance only.
        For document metadata, use get_analysis_with_metadata() instead.
        """
        image_file = self._image_files.get_by_path(file_path)
        if not image_file:
            return None

        return self._analysis.get_latest_by_image_file_id(image_file["id"])

    def get_analysis_with_metadata(self, file_path: str) -> dict[str, Any] | None:
        """
        Retrieve analysis results WITH normalized metadata for a file.

        Returns a merged dict containing both analysis provenance and document metadata.
        This is the recommended method for UI display after Migration 16.

        Args:
            file_path: Path to image file

        Returns:
            Dict with both analysis and metadata fields, or None if file not found
        """
        # Use get_analyzed_pages to get full joined data
        all_pages = self.get_analyzed_pages()
        for page in all_pages:
            if page.get("file_path") == file_path:
                return page
        return None

    def get_analysis_by_image_file_id(self, image_file_id: int) -> dict[str, Any] | None:
        """Retrieve the latest analysis results for an image file."""
        return self._analysis.get_latest_by_image_file_id(image_file_id)

    def update_analysis_metadata(self, file_path: str, metadata: dict[str, Any]) -> None:
        """
        DEPRECATED: Use update_metadata() to update the metadata table instead.

        This method is kept for backward compatibility but does nothing after Migration 16.
        """
        from services.logging_service import get_logger

        logger = get_logger()
        logger.warning(
            "update_analysis_metadata() is deprecated after Migration 16. "
            "Use update_metadata() to update the metadata table instead."
        )

    def get_analyzed_pages(
        self, directory_filter: str | None = None, provider_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get list of all image files with their analysis data (if available).

        Uses image_files as primary table with LEFT JOIN to analysis_results,
        so unanalyzed images are included in the results.

        Args:
            directory_filter: Optional directory path to filter by
            provider_filter: Optional provider name to filter by

        Returns:
            List of image file dicts with analysis data merged in
        """
        return self._image_files.get_all_with_analysis(directory_filter, provider_filter)

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
        """
        Save a document bundle suggestion.

        Creates bundle and links images via bundle_images junction table.

        Args:
            file_paths: List of image file paths in bundle
            bundle_metadata: Bundle metadata dict
            confidence_score: Confidence score (0.0-1.0)

        Returns:
            Bundle ID
        """
        # Create bundle record
        bundle_id = self._bundles.save_suggestion(
            bundle_metadata=bundle_metadata,
            confidence_score=confidence_score,
        )

        if not bundle_id:
            return None

        # Get image file IDs for the paths
        image_file_ids: list[int] = []
        for file_path in file_paths:
            img = self._image_files.get_by_path(file_path)
            if img:
                image_file_ids.append(img["id"])

        # Add images to bundle via junction table
        if image_file_ids:
            self._bundle_images.add_images_bulk(bundle_id, image_file_ids)

        return bundle_id

    def get_bundle_suggestions(
        self, status_filter: str = "suggested", min_confidence: float | None = None
    ) -> list[dict[str, Any]]:
        """
        Get bundle suggestions with optional filters.

        Enriches results with file_paths from bundle_images junction table.

        Args:
            status_filter: Bundle status filter
            min_confidence: Optional minimum confidence score

        Returns:
            List of bundle dicts with file_paths added
        """
        bundles = self._bundles.get_suggestions(status_filter, min_confidence)

        # Enrich each bundle with file_paths from junction table
        for bundle in bundles:
            bundle_id = bundle["id"]
            images = self._bundle_images.get_images_for_bundle(bundle_id)
            bundle["file_paths"] = [img["file_path"] for img in images]

        return bundles

    def update_bundle_status(
        self, bundle_id: int, status: str, user_action: str | None = None
    ) -> None:
        """Update bundle status after user action."""
        self._bundles.update_status(bundle_id, status, user_action)

    def update_bundle_metadata(self, bundle_id: int, metadata: dict[str, Any]) -> None:
        """
        Update bundle name.

        NOTE: Document metadata (company, type, date) should be updated via
        update_metadata() on the metadata table, not here.
        """
        if "bundle_name" in metadata:
            self._bundles.update_bundle_name(bundle_id, metadata["bundle_name"])

    def get_bundled_file_paths(self) -> set[str]:
        """Get all file paths that are part of accepted or completed bundles."""
        return self._bundles.get_bundled_file_paths()

    def update_bundle_pdf_path(self, bundle_id: int, pdf_path: str) -> None:
        """
        Update bundle with generated PDF path.

        DEPRECATED: PDF paths are now stored in pdf_files table via register_pdf_file().
        This method is kept for backward compatibility but does nothing.
        """
        # No-op: PDF path stored in pdf_files table, not document_bundles
        pass

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

    # ==================== Statistics Methods ====================

    def get_extended_statistics(self) -> dict[str, Any]:
        """Get extended analysis statistics."""
        if self.connection.connection is None:
            raise RuntimeError("Database connection not initialized")
        cursor = self.connection.connection.cursor()

        # Total analyzed pages
        cursor.execute("SELECT COUNT(*) FROM analysis_results")
        total_analyzed = cursor.fetchone()[0]

        # Cached analyses (images with multiple analyses)
        cursor.execute("""
            SELECT COUNT(DISTINCT image_file_id)
            FROM (
                SELECT image_file_id, COUNT(*) as analysis_count
                FROM analysis_results
                GROUP BY image_file_id
                HAVING analysis_count > 1
            )
        """)
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
        """Get count of documents by type from user-approved metadata."""
        if self.connection.connection is None:
            raise RuntimeError("Database connection not initialized")
        cursor = self.connection.connection.cursor()
        cursor.execute("""
            SELECT m.document_type, COUNT(*) as count
            FROM metadata m
            INNER JOIN image_files img ON m.image_file_id = img.id
            WHERE img.status != 'deleted'
            AND m.document_type IS NOT NULL
            GROUP BY m.document_type
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
        """Update image file status. Note: analysis_id parameter is deprecated and ignored."""
        self._image_files.update_status(file_path, status)

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

    def update_image_rotation(self, file_path: str, rotation: int) -> None:
        """Update user-specified rotation for image file."""
        self._image_files.update_rotation(file_path, rotation)

    def get_image_rotation(self, file_path: str) -> int:
        """Get user-specified rotation for image file."""
        return self._image_files.get_rotation(file_path)

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
        """
        Register a generated PDF.

        Creates PDF record and links images via pdf_image_pages junction table.

        Args:
            pdf_path: Full path to PDF
            pdf_filename: PDF filename
            bundle_id: Bundle ID
            source_image_ids: List of image_file IDs
            page_count: Number of pages
            file_hash: Optional SHA-256 hash
            file_size: Optional file size in bytes

        Returns:
            PDF file ID
        """
        # Register PDF
        pdf_file_id = self._pdf_files.register(
            pdf_path, pdf_filename, bundle_id, page_count, file_hash, file_size
        )

        # Link images to PDF via junction table (with page numbers)
        for page_num, image_file_id in enumerate(source_image_ids, start=1):
            self._pdf_image_pages.add_page(pdf_file_id, image_file_id, page_num)

        return pdf_file_id

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

    # ==================== Metadata Methods ====================

    def create_metadata_from_analysis(
        self,
        image_file_id: int,
        analysis_id: int,
        normalized_metadata: dict[str, Any],
        output_filename: str | None = None,
        document_category: str | None = None,
    ) -> int:
        """
        Create metadata from normalized analysis.

        Args:
            image_file_id: Image file ID
            analysis_id: Analysis result ID
            normalized_metadata: Normalized metadata dictionary
            output_filename: Optional desired output filename
            document_category: Optional document category

        Returns:
            Created metadata record ID
        """
        return self._metadata.create_from_analysis(
            image_file_id, analysis_id, normalized_metadata, output_filename, document_category
        )

    def update_metadata(self, image_file_id: int, updates: dict[str, Any]) -> None:
        """
        Update metadata (user edit).

        Args:
            image_file_id: Image file ID
            updates: Dictionary of fields to update
        """
        self._metadata.update_from_user(image_file_id, updates)

    def get_metadata_by_image_id(self, image_file_id: int) -> dict[str, Any] | None:
        """
        Get current metadata for image.

        Args:
            image_file_id: Image file ID

        Returns:
            Metadata dictionary or None
        """
        return self._metadata.get_by_image_file_id(image_file_id)

    def get_metadata_by_path(self, file_path: str) -> dict[str, Any] | None:
        """
        Get metadata by image file path.

        Args:
            file_path: Image file path

        Returns:
            Metadata dictionary or None
        """
        return self._metadata.get_by_image_path(file_path)

    def link_metadata_to_pdf(self, image_file_ids: list[int], pdf_file_id: int) -> None:
        """
        Link metadata to PDF after generation.

        Args:
            image_file_ids: List of image file IDs
            pdf_file_id: PDF file ID
        """
        self._metadata.link_to_pdf(image_file_ids, pdf_file_id)

    def get_metadata_analysis_history(self, image_file_id: int) -> list[dict[str, Any]]:
        """
        Get analysis history for comparison.

        Args:
            image_file_id: Image file ID

        Returns:
            List of analysis result dictionaries
        """
        return self._metadata.get_analysis_history(image_file_id)

    def get_all_metadata(
        self, status_filter: str | None = None, directory_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get all metadata records with optional filters.

        Args:
            status_filter: Optional image status filter
            directory_filter: Optional directory path filter

        Returns:
            List of metadata dictionaries
        """
        return self._metadata.get_all(status_filter, directory_filter)

    def get_metadata_stats(self) -> dict[str, int]:
        """
        Get metadata statistics.

        Returns:
            Dictionary with statistics
        """
        return self._metadata.get_stats()

    def delete_metadata_by_path(self, file_path: str) -> None:
        """
        Delete metadata by image file path.

        Args:
            file_path: Image file path
        """
        # Get image file record to find the ID
        image_file = self._image_files.get_by_path(file_path)
        if image_file:
            self._metadata.delete_by_image_file_id(image_file["id"])

    def get_unique_companies(self) -> list[str]:
        """
        Get unique company names for autocomplete.

        Returns:
            List of company names (normalized, title case)
        """
        return self._metadata.get_unique_companies()

    def get_unique_document_types(self) -> list[str]:
        """
        Get unique document types for autocomplete.

        Returns:
            List of document types (normalized, title case)
        """
        return self._metadata.get_unique_document_types()

    def get_unique_categories(self) -> list[str]:
        """
        Get unique document categories for autocomplete.

        Returns:
            List of document categories
        """
        return self._metadata.get_unique_categories()

    # ==================== Utility Methods ====================

    def close(self):
        """Close database connection."""
        self.connection.close()
