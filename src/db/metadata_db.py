"""
Metadata Database Manager
Handles persistent storage of page metadata with SQLite for caching and archival.
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime
from typing import Any


class MetadataDB:
    """Manages SQLite database for page metadata caching and archival"""

    def __init__(self, db_path: str = None):
        """
        Initialize metadata database connection.

        Args:
            db_path: Path to SQLite database file. If None, uses AppData directory.
        """
        # If no db_path specified, use AppData directory
        if db_path is None:
            appdata_root = os.getenv(
                "APPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
            )
            appdata_dir = os.path.join(appdata_root, "WinScanLLM")
            db_path = os.path.join(appdata_dir, "metadata.db")

        self.db_path = db_path
        self.connection = None
        self._connect()
        self._create_tables()

        # Initialize field history cache
        self._companies_cache = None
        self._titles_cache = None

    def _connect(self):
        """Establish database connection"""
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row  # Enable column access by name

    def _create_tables(self):
        """Create database tables if they don't exist"""
        cursor = self.connection.cursor()

        # Database version tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            )
        """)

        # Active metadata table (for current processing)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_hash TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_mtime REAL NOT NULL,

                -- Extracted metadata
                belongs_to_same_doc BOOLEAN,
                page_number INTEGER,
                total_pages INTEGER,
                page_position TEXT,
                confidence TEXT,

                company TEXT,
                document_type TEXT,
                document_date TEXT,

                -- Additional metadata (stored as JSON for flexibility)
                additional_data TEXT,

                -- Timestamps
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                -- Processing info
                model_used TEXT,
                processing_time_ms INTEGER
            )
        """)

        # Archived metadata table (for completed documents)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS archived_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_path TEXT NOT NULL,
                pdf_filename TEXT NOT NULL,
                pdf_created_at TIMESTAMP NOT NULL,

                -- Document-level metadata
                company TEXT,
                document_type TEXT,
                document_date TEXT,
                total_pages INTEGER,

                -- Source files (stored as JSON array)
                source_files TEXT NOT NULL,

                -- Page metadata (stored as JSON array)
                pages_metadata TEXT NOT NULL,

                -- Timestamps
                archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                -- Additional info
                additional_data TEXT
            )
        """)

        # Create indices for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_active_file_path
            ON active_metadata(file_path)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_active_file_hash
            ON active_metadata(file_hash)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_archived_pdf_path
            ON archived_metadata(pdf_path)
        """)

        self.connection.commit()

        # Run migrations if needed
        self._run_migrations()

    def _run_migrations(self):
        """Run database migrations to latest version"""
        cursor = self.connection.cursor()

        # Check current version
        cursor.execute("SELECT MAX(version) FROM schema_version")
        result = cursor.fetchone()
        current_version = result[0] if result[0] is not None else 0

        # Migration 1: Initial schema (already exists)
        if current_version < 1:
            cursor.execute("""
                INSERT INTO schema_version (version, description)
                VALUES (1, 'Initial metadata schema with active and archived tables')
            """)
            self.connection.commit()
            current_version = 1

        # Migration 2: Add rotation_degrees column (Phase 8)
        if current_version < 2:
            cursor.execute("""
                ALTER TABLE active_metadata
                ADD COLUMN rotation_degrees INTEGER DEFAULT 0
            """)
            cursor.execute("""
                INSERT INTO schema_version (version, description)
                VALUES (2, 'Phase 8: Add rotation_degrees column for display-only rotation')
            """)
            self.connection.commit()
            current_version = 2

    def get_schema_version(self) -> int:
        """Get current database schema version"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT MAX(version) FROM schema_version")
        result = cursor.fetchone()
        return result[0] if result[0] is not None else 0

    @staticmethod
    def compute_file_hash(file_path: str) -> str:
        """
        Compute SHA-256 hash of file for change detection.

        Args:
            file_path: Path to file

        Returns:
            Hex string of file hash
        """
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def get_metadata(self, file_path: str) -> dict[str, Any] | None:
        """
        Retrieve metadata for a file if it exists and is current.

        Args:
            file_path: Path to file

        Returns:
            Metadata dict if found and current, None otherwise
        """
        if not os.path.exists(file_path):
            return None

        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM active_metadata WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()

        if not row:
            return None

        # Check if file has changed since metadata was stored
        current_mtime = os.path.getmtime(file_path)
        current_size = os.path.getsize(file_path)

        if row["file_mtime"] != current_mtime or row["file_size"] != current_size:
            # File has changed, metadata is stale
            self.delete_metadata(file_path)
            return None

        # Optionally verify hash for extra safety (slower but more accurate)
        # current_hash = self.compute_file_hash(file_path)
        # if row['file_hash'] != current_hash:
        #     self.delete_metadata(file_path)
        #     return None

        # Convert row to dict
        metadata = dict(row)

        # Parse JSON fields
        if metadata.get("additional_data"):
            metadata["additional_data"] = json.loads(metadata["additional_data"])

        return metadata

    def save_metadata(
        self,
        file_path: str,
        metadata: dict[str, Any],
        model_used: str = None,
        processing_time_ms: int = None,
    ) -> None:
        """
        Save or update metadata for a file.

        Args:
            file_path: Path to file
            metadata: Metadata dictionary
            model_used: Name of Ollama model used
            processing_time_ms: Processing time in milliseconds
        """
        # Compute file properties
        file_hash = self.compute_file_hash(file_path)
        file_size = os.path.getsize(file_path)
        file_mtime = os.path.getmtime(file_path)

        # Extract standard fields
        belongs_to_same_doc = metadata.get("belongs", False)
        page_number = metadata.get("page_number")
        total_pages = metadata.get("total_pages")
        page_position = metadata.get("page_position")  # e.g., "4 of 6"
        confidence = metadata.get("confidence")
        company = metadata.get("company")
        document_type = metadata.get("document_type")
        document_date = metadata.get("document_date")

        # Store remaining fields as JSON
        additional_fields = {
            k: v
            for k, v in metadata.items()
            if k
            not in [
                "belongs",
                "page_number",
                "total_pages",
                "page_position",
                "confidence",
                "company",
                "document_type",
                "document_date",
            ]
        }
        additional_data = json.dumps(additional_fields) if additional_fields else None

        cursor = self.connection.cursor()

        # Use INSERT OR REPLACE to handle updates
        cursor.execute(
            """
            INSERT OR REPLACE INTO active_metadata (
                file_path, file_hash, file_size, file_mtime,
                belongs_to_same_doc, page_number, total_pages, page_position, confidence,
                company, document_type, document_date,
                additional_data, updated_at, model_used, processing_time_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
            (
                file_path,
                file_hash,
                file_size,
                file_mtime,
                belongs_to_same_doc,
                page_number,
                total_pages,
                page_position,
                confidence,
                company,
                document_type,
                document_date,
                additional_data,
                model_used,
                processing_time_ms,
            ),
        )

        self.connection.commit()

    def delete_metadata(self, file_path: str) -> None:
        """
        Delete metadata for a file.

        Args:
            file_path: Path to file
        """
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM active_metadata WHERE file_path = ?", (file_path,))
        self.connection.commit()

    def archive_document(
        self, pdf_path: str, source_files: list[str], document_metadata: dict[str, Any]
    ) -> None:
        """
        Archive metadata for a completed document.

        Args:
            pdf_path: Path to created PDF
            source_files: List of source file paths
            document_metadata: Document-level metadata
        """
        # Gather metadata for all source files
        pages_metadata = []
        for file_path in source_files:
            page_meta = self.get_metadata(file_path)
            if page_meta:
                # Remove binary/large fields before archiving
                page_meta.pop("id", None)
                page_meta.pop("created_at", None)
                page_meta.pop("updated_at", None)
                pages_metadata.append(page_meta)

        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO archived_metadata (
                pdf_path, pdf_filename, pdf_created_at,
                company, document_type, document_date, total_pages,
                source_files, pages_metadata, additional_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                pdf_path,
                os.path.basename(pdf_path),
                datetime.now().isoformat(),
                document_metadata.get("company"),
                document_metadata.get("title"),
                document_metadata.get("date"),
                len(source_files),
                json.dumps(source_files),
                json.dumps(pages_metadata),
                json.dumps(document_metadata.get("additional", {})),
            ),
        )

        # Invalidate field history cache after archiving
        self.invalidate_field_history_cache()

        self.connection.commit()

        # Optionally delete active metadata for archived files
        # (keeping them allows re-processing if needed)
        # for file_path in source_files:
        #     self.delete_metadata(file_path)

    def get_archived_document(self, pdf_path: str) -> dict[str, Any] | None:
        """
        Retrieve archived metadata for a PDF.

        Args:
            pdf_path: Path to PDF

        Returns:
            Archived metadata dict if found, None otherwise
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM archived_metadata WHERE pdf_path = ?", (pdf_path,))
        row = cursor.fetchone()

        if not row:
            return None

        metadata = dict(row)

        # Parse JSON fields
        if metadata.get("source_files"):
            metadata["source_files"] = json.loads(metadata["source_files"])
        if metadata.get("pages_metadata"):
            metadata["pages_metadata"] = json.loads(metadata["pages_metadata"])
        if metadata.get("additional_data"):
            metadata["additional_data"] = json.loads(metadata["additional_data"])

        return metadata

    def get_statistics(self) -> dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Statistics dictionary
        """
        cursor = self.connection.cursor()

        cursor.execute("SELECT COUNT(*) FROM active_metadata")
        active_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM archived_metadata")
        archived_count = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(total_pages) FROM archived_metadata")
        total_archived_pages = cursor.fetchone()[0] or 0

        return {
            "active_metadata_count": active_count,
            "archived_documents_count": archived_count,
            "total_archived_pages": total_archived_pages,
            "database_path": self.db_path,
            "database_size_bytes": os.path.getsize(self.db_path)
            if os.path.exists(self.db_path)
            else 0,
        }

    def cleanup_orphaned_metadata(self) -> int:
        """
        Remove metadata for files that no longer exist.

        Returns:
            Number of entries removed
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT file_path FROM active_metadata")
        rows = cursor.fetchall()

        removed = 0
        for row in rows:
            file_path = row["file_path"]
            if not os.path.exists(file_path):
                self.delete_metadata(file_path)
                removed += 1

        return removed

    def create_backup(self, backup_path: str | None = None) -> str:
        """
        Create a backup of the database.

        Args:
            backup_path: Optional custom backup path

        Returns:
            Path to backup file
        """
        import shutil

        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{self.db_path}.backup_{timestamp}"

        shutil.copy2(self.db_path, backup_path)
        return backup_path

    def save_rotation(self, file_path: str, rotation_degrees: int) -> None:
        """
        Save rotation angle for a file (Phase 8).
        Rotation is display-only and never modifies the source file.

        Args:
            file_path: Absolute path to the image file
            rotation_degrees: Rotation angle (0, 90, 180, 270)
        """
        cursor = self.connection.cursor()

        # Normalize rotation to 0-359 range
        rotation_degrees = rotation_degrees % 360

        # Update or insert rotation
        cursor.execute(
            """
            INSERT INTO active_metadata (file_path, file_hash, file_size, file_mtime, rotation_degrees)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                rotation_degrees = ?,
                updated_at = CURRENT_TIMESTAMP
        """,
            (
                file_path,
                self.compute_file_hash(file_path),
                os.path.getsize(file_path),
                os.path.getmtime(file_path),
                rotation_degrees,
                rotation_degrees,
            ),
        )

        self.connection.commit()

    def get_rotation(self, file_path: str) -> int:
        """
        Get stored rotation angle for a file (Phase 8).

        Args:
            file_path: Absolute path to the image file

        Returns:
            Rotation angle in degrees (0, 90, 180, or 270), or 0 if not found
        """
        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT rotation_degrees
            FROM active_metadata
            WHERE file_path = ?
        """,
            (file_path,),
        )

        result = cursor.fetchone()

        if result and result[0] is not None:
            return result[0]

        return 0  # Default: no rotation

    def get_unique_companies(self, use_cache: bool = True) -> list[str]:
        """
        Get list of unique company names from archived documents.

        Args:
            use_cache: If True, use cached results if available

        Returns:
            Alphabetically sorted list of unique company names
        """
        if use_cache and self._companies_cache:
            return self._companies_cache

        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT DISTINCT company
            FROM archived_metadata
            WHERE company IS NOT NULL AND company != ''
            ORDER BY company COLLATE NOCASE
        """)

        companies = [row[0] for row in cursor.fetchall()]

        if use_cache:
            self._companies_cache = companies

        return companies

    def get_unique_titles(self, use_cache: bool = True) -> list[str]:
        """
        Get list of unique document titles from archived documents.

        Args:
            use_cache: If True, use cached results if available

        Returns:
            Alphabetically sorted list of unique document titles
        """
        if use_cache and self._titles_cache:
            return self._titles_cache

        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT DISTINCT document_type
            FROM archived_metadata
            WHERE document_type IS NOT NULL AND document_type != ''
            ORDER BY document_type COLLATE NOCASE
        """)

        titles = [row[0] for row in cursor.fetchall()]

        if use_cache:
            self._titles_cache = titles

        return titles

    def invalidate_field_history_cache(self) -> None:
        """Invalidate cached field history results after archiving new documents."""
        self._companies_cache = None
        self._titles_cache = None

    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Example usage
if __name__ == "__main__":
    # Test the metadata database
    db = MetadataDB("test_metadata.db")

    # Test saving metadata
    test_metadata = {
        "belongs": True,
        "page_number": 3,
        "total_pages": 6,
        "page_position": "3 of 6",
        "confidence": "high",
        "company": "Acme Corp",
        "document_type": "Invoice",
        "document_date": "2026-02-01",
        "custom_field": "test value",
    }

    print("Database statistics:", db.get_statistics())

    db.close()
    print("Test completed successfully!")
