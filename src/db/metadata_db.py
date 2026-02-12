"""
Refactored MetadataDB - thin wrapper around repositories.

Maintains existing API while delegating to focused repository classes.
"""

import hashlib
from typing import Any

from db.connection import DatabaseConnection, get_appdata_db_path
from db.repositories.archived_metadata_repo import ArchivedMetadataRepository
from db.repositories.image_files_repo import ImageFilesRepository
from db.repositories.metadata_repo import MetadataRepository as NormalizedMetadataRepository
from db.schema import create_all_tables
from services.logging_service import get_logger

logger = get_logger()


class MetadataDB:
    """Manages SQLite database for page metadata caching and archival."""

    def __init__(self, db_path: str | None = None):
        """
        Initialize metadata database connection.

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
        self._archived_metadata = ArchivedMetadataRepository(
            self.connection
        )  # For archived_metadata
        self._normalized_metadata = NormalizedMetadataRepository(
            self.connection
        )  # For metadata table
        self._image_files = ImageFilesRepository(self.connection)  # For image file tracking

        # Field history cache
        self._companies_cache: list[str] | None = None
        self._titles_cache: list[str] | None = None

    @staticmethod
    def compute_file_hash(file_path: str) -> str:
        """
        Compute SHA-256 hash of file.

        Args:
            file_path: Path to file

        Returns:
            Hexadecimal hash string

        Raises:
            FileNotFoundError: If file does not exist
            PermissionError: If file cannot be accessed
            OSError: If file cannot be read
        """
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except FileNotFoundError as e:
            logger.error(f"[FILE HASH] File not found: {file_path}")
            raise FileNotFoundError(
                f"Cannot compute hash - file does not exist: {file_path}"
            ) from e
        except PermissionError as e:
            logger.error(f"[FILE HASH] Permission denied: {file_path}")
            raise PermissionError(f"Cannot access file for hashing: {file_path}") from e
        except OSError as e:
            logger.error(f"[FILE HASH] OS error: {file_path} - {e}")
            raise OSError(f"Failed to read file for hashing: {e}") from e

    # ==================== Archived Document Methods ====================

    def archive_document(
        self, pdf_path: str, source_files: list[str], document_metadata: dict[str, Any]
    ) -> None:
        """
        Archive metadata for a completed PDF document.

        Args:
            pdf_path: Path to generated PDF
            source_files: List of source image file paths
            document_metadata: Metadata extracted from the document
        """
        self._archived_metadata.archive_document(pdf_path, source_files, document_metadata)
        self.invalidate_field_history_cache()

    def get_archived_document(self, pdf_path: str) -> dict[str, Any] | None:
        """
        Retrieve archived metadata for a PDF.

        Args:
            pdf_path: Path to PDF

        Returns:
            Archived metadata dictionary or None
        """
        result = self._archived_metadata.get_archived_document(pdf_path)
        return dict(result) if result else None

    def get_archived_statistics(self) -> dict[str, Any]:
        """
        Get statistics about archived documents.

        Returns:
            Dictionary with archived document counts
        """
        stats = self._archived_metadata.get_statistics()
        return dict(stats)

    def get_unique_companies(self, use_cache: bool = True) -> list[str]:
        """
        Get list of unique companies from metadata table.

        Args:
            use_cache: Whether to use cached results

        Returns:
            List of company names
        """
        if use_cache and self._companies_cache is not None:
            return self._companies_cache

        if self.connection.connection is None:
            raise RuntimeError("Database connection not initialized")
        cursor = self.connection.connection.cursor()

        # Query metadata table
        cursor.execute("""
            SELECT DISTINCT company
            FROM metadata
            WHERE company IS NOT NULL AND company != ''
            ORDER BY company
        """)
        companies = [row[0] for row in cursor.fetchall()]

        if use_cache:
            self._companies_cache = companies

        return companies

    def get_unique_titles(self, use_cache: bool = True) -> list[str]:
        """
        Get list of unique document types from metadata table.

        Args:
            use_cache: Whether to use cached results

        Returns:
            List of document types
        """
        if use_cache and self._titles_cache is not None:
            return self._titles_cache

        if self.connection.connection is None:
            raise RuntimeError("Database connection not initialized")
        cursor = self.connection.connection.cursor()

        # Query metadata table
        cursor.execute("""
            SELECT DISTINCT document_type
            FROM metadata
            WHERE document_type IS NOT NULL AND document_type != ''
            ORDER BY document_type
        """)
        titles = [row[0] for row in cursor.fetchall()]

        if use_cache:
            self._titles_cache = titles

        return titles

    def get_unique_categories(self) -> list[str]:
        """
        Get list of unique document categories from metadata table.

        Returns:
            List of document categories
        """
        if self.connection.connection is None:
            raise RuntimeError("Database connection not initialized")
        cursor = self.connection.connection.cursor()

        cursor.execute("""
            SELECT DISTINCT document_category
            FROM metadata
            WHERE document_category IS NOT NULL AND document_category != ''
            ORDER BY document_category
        """)
        return [row[0] for row in cursor.fetchall()]

    # ==================== Normalized Metadata Methods ====================

    def create_normalized_metadata(
        self,
        image_file_id: int,
        analysis_result_id: int | None,
        normalized_metadata: dict[str, Any],
    ) -> int:
        """
        Create normalized metadata from analysis.

        Args:
            image_file_id: Image file ID
            analysis_result_id: Analysis result ID (optional)
            normalized_metadata: Normalized metadata dictionary
                Can include output_filename and document_category

        Returns:
            Metadata record ID
        """
        # Extract optional fields that are separate parameters
        output_filename = normalized_metadata.get("output_filename")
        document_category = normalized_metadata.get("document_category")

        return self._normalized_metadata.create_from_analysis(
            image_file_id,
            analysis_result_id,
            normalized_metadata,
            output_filename=output_filename,
            document_category=document_category,
        )

    def update_normalized_metadata(self, image_file_id: int, updates: dict[str, Any]) -> None:
        """
        Update normalized metadata (user edit).

        Args:
            image_file_id: Image file ID
            updates: Dictionary of fields to update
        """
        self._normalized_metadata.update_from_user(image_file_id, updates)

    def get_normalized_metadata_by_image_id(self, image_file_id: int) -> dict[str, Any] | None:
        """
        Get normalized metadata by image file ID.

        Args:
            image_file_id: Image file ID

        Returns:
            Metadata dictionary or None
        """
        return self._normalized_metadata.get_by_image_file_id(image_file_id)

    def get_normalized_metadata_by_path(self, file_path: str) -> dict[str, Any] | None:
        """
        Get normalized metadata by image file path.

        Args:
            file_path: Image file path

        Returns:
            Metadata dictionary or None
        """
        return self._normalized_metadata.get_by_image_path(file_path)

    # ==================== Image File Methods ====================

    def get_image_file(self, file_path: str) -> dict[str, Any] | None:
        """
        Get image file record by path.

        Args:
            file_path: Image file path

        Returns:
            Image file dictionary or None
        """
        return self._image_files.get_by_path(file_path)

    def register_image_file(
        self,
        file_path: str,
        file_hash: str,
        directory_path: str,
        filename: str,
        file_size: int,
        file_mtime: float,
    ) -> int:
        """
        Register a new image file.

        Args:
            file_path: Full file path
            file_hash: File hash (SHA-256)
            directory_path: Directory containing the file
            filename: Filename only
            file_size: File size in bytes
            file_mtime: File modification time

        Returns:
            Image file ID
        """
        return self._image_files.register(
            file_path, file_hash, directory_path, filename, file_size, file_mtime
        )

    def update_image_rotation(self, file_path: str, rotation: int) -> None:
        """
        Update image rotation.

        Args:
            file_path: Image file path
            rotation: Rotation in degrees (0, 90, 180, 270)
        """
        self._image_files.update_rotation(file_path, rotation)

    def get_image_rotation(self, file_path: str) -> int:
        """
        Get image rotation.

        Args:
            file_path: Image file path

        Returns:
            Rotation in degrees
        """
        return self._image_files.get_rotation(file_path)

    def update_image_status(
        self, file_path: str, status: str, analysis_id: int | None = None
    ) -> None:
        """
        Update image file status.

        Args:
            file_path: Image file path
            status: New status
            analysis_id: Optional analysis ID (deprecated, ignored)
        """
        self._image_files.update_status(file_path, status)

    def invalidate_field_history_cache(self) -> None:
        """Clear field history cache."""
        self._companies_cache = None
        self._titles_cache = None

    def get_schema_version(self) -> int:
        """Get current database schema version."""
        from db.schema import get_schema_version

        return get_schema_version(self.connection)

    def close(self):
        """Close database connection."""
        self.connection.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
