"""
Refactored MetadataDB - thin wrapper around repositories.

Maintains existing API while delegating to focused repository classes.
"""

import hashlib
import logging
from typing import TYPE_CHECKING, Any

from db.connection import DatabaseConnection, get_appdata_db_path
from db.repositories import (
    ArchivedMetadataRepository,
    ImageFilesRepository,
    MetadataRepository,
    RotationRepository,
)
from db.schema import create_all_tables

if TYPE_CHECKING:
    from services.logging_service import get_logger
else:
    get_logger = None

logger: logging.Logger | None = None


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
        self._metadata = MetadataRepository(self.connection)
        self._rotation = RotationRepository(self.connection)
        self._archived = ArchivedMetadataRepository(self.connection)
        self._image_files = ImageFilesRepository(self.connection)

        # Field history cache
        self._companies_cache: list[str] | None = None
        self._titles_cache: list[str] | None = None

    def _get_logger(self) -> logging.Logger:
        """Get logger instance (lazy initialization)."""
        global logger
        if logger is None:
            from services.logging_service import get_logger as _get_logger

            logger = _get_logger()
        return logger

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
            OSError: If file read fails
        """
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except FileNotFoundError as e:
            # Lazy initialization for static method
            from services.logging_service import get_logger as _get_logger

            _get_logger().error(f"[FILE HASH] File not found: {file_path}")
            raise FileNotFoundError(
                f"Cannot compute hash - file does not exist: {file_path}"
            ) from e
        except PermissionError as e:
            from services.logging_service import get_logger as _get_logger

            _get_logger().error(f"[FILE HASH] Permission denied: {file_path}")
            raise PermissionError(f"Cannot access file for hashing: {file_path}") from e
        except OSError as e:
            from services.logging_service import get_logger as _get_logger

            _get_logger().error(f"[FILE HASH] OS error: {file_path} - {e}")
            raise OSError(f"Failed to read file for hashing: {e}") from e

    def save_metadata(
        self,
        file_path: str,
        metadata: dict[str, Any],
        model_used: str | None = None,
        processing_time_ms: int | None = None,
    ) -> None:
        """Save or update metadata for a file."""
        import os

        # Get or register image file
        image_file = self._image_files.get_by_path(file_path)
        if not image_file:
            # Auto-register the file if it doesn't exist
            if not os.path.exists(file_path):
                return

            file_hash = self.compute_file_hash(file_path)
            file_size = os.path.getsize(file_path)
            file_mtime = os.path.getmtime(file_path)
            directory_path = os.path.dirname(file_path)
            filename = os.path.basename(file_path)

            image_file_id = self._image_files.register(
                file_path, file_hash, directory_path, filename, file_size, file_mtime
            )
            # Use the returned ID directly
            image_file = {"id": image_file_id}

        # Update metadata via repository
        self._metadata.update_from_user(image_file["id"], metadata)
        self.invalidate_field_history_cache()

    def get_metadata(self, file_path: str) -> dict[str, Any] | None:
        """Retrieve metadata for a file."""
        return self._metadata.get_by_image_path(file_path)

    def delete_metadata(self, file_path: str) -> None:
        """Delete metadata for a file."""
        image_file = self._image_files.get_by_path(file_path)
        if image_file:
            self._metadata.delete_by_image_file_id(image_file["id"])
            self.invalidate_field_history_cache()

    def archive_document(
        self, pdf_path: str, source_files: list[str], document_metadata: dict[str, Any]
    ) -> None:
        """Archive metadata for a completed document."""
        self._archived.archive_document(pdf_path, source_files, document_metadata)
        self.invalidate_field_history_cache()

    def get_archived_document(self, pdf_path: str) -> dict[str, Any] | None:
        """Retrieve archived metadata for a PDF."""
        return self._archived.get_archived_document(pdf_path)

    def get_statistics(self) -> dict[str, Any]:
        """Get database statistics."""
        import os

        # Combine statistics from both metadata and archived repositories
        metadata_stats = self._metadata.get_stats()
        archived_stats = self._archived.get_statistics()

        # Calculate database size
        database_size_mb = 0.0
        if os.path.exists(self.db_path):
            database_size_mb = os.path.getsize(self.db_path) / (1024 * 1024)

        # Map to expected keys for UI and test compatibility
        return {
            **metadata_stats,
            **archived_stats,
            # Aliases for backward compatibility
            "active_count": metadata_stats.get("total", 0),
            "archived_count": archived_stats.get("total_pdfs", 0),
            "active_metadata_count": metadata_stats.get("total", 0),  # Test compatibility
            "archived_documents_count": archived_stats.get("total_pdfs", 0),  # Test compatibility
            "database_size_mb": database_size_mb,
        }

    def cleanup_orphaned_metadata(self) -> int:
        """Remove metadata for files that no longer exist."""
        # Get all metadata records
        all_metadata = self._metadata.get_all()

        deleted_count = 0
        for meta in all_metadata:
            file_path = meta.get("file_path")
            if file_path:
                import os

                if not os.path.exists(file_path):
                    image_file = self._image_files.get_by_path(file_path)
                    if image_file:
                        self._metadata.delete_by_image_file_id(image_file["id"])
                        deleted_count += 1

        self.invalidate_field_history_cache()
        return deleted_count

    def create_backup(self, backup_path: str | None = None) -> str:
        """Create database backup."""
        import shutil

        if backup_path is None:
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.db_path.replace(".db", f"_backup_{timestamp}.db")

        shutil.copy2(self.db_path, backup_path)
        return backup_path

    def save_rotation(self, file_path: str, rotation_degrees: int) -> None:
        """Save rotation angle for a file."""
        self._rotation.save(file_path, rotation_degrees)

    def get_rotation(self, file_path: str) -> int:
        """Get rotation angle for a file."""
        return self._rotation.get(file_path)

    def get_unique_companies(self, use_cache: bool = True) -> list[str]:
        """Get list of unique companies."""
        if use_cache and self._companies_cache is not None:
            return self._companies_cache

        assert self.connection.connection is not None
        cursor = self.connection.connection.cursor()
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
        """Get list of unique document types."""
        if use_cache and self._titles_cache is not None:
            return self._titles_cache

        assert self.connection.connection is not None
        cursor = self.connection.connection.cursor()
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
