"""Metadata repository for managing page metadata persistence."""

import hashlib
import json
import os
from datetime import datetime
from typing import Any

from db.connection import DatabaseConnection


class MetadataRepository:
    """Manages metadata persistence operations."""

    def __init__(self, conn: DatabaseConnection):
        """Initialize metadata repository."""
        self.conn = conn

    def save_metadata(
        self,
        file_path: str,
        metadata: dict[str, Any],
        model_used: str | None = None,
        processing_time_ms: int | None = None,
    ) -> None:
        """Save or update metadata for a file."""
        file_hash = self._compute_file_hash(file_path)
        file_size = os.path.getsize(file_path)
        file_mtime = os.path.getmtime(file_path)

        exclude_keys = {
            "belongs",
            "page_number",
            "total_pages",
            "page_position",
            "confidence",
            "company",
            "document_type",
            "document_date",
        }
        additional_fields = {k: v for k, v in metadata.items() if k not in exclude_keys}
        additional_data = json.dumps(additional_fields) if additional_fields else None

        self.conn.execute(
            "INSERT OR REPLACE INTO active_metadata (file_path, file_hash, file_size, file_mtime, belongs_to_same_doc, page_number, total_pages, page_position, confidence, company, document_type, document_date, additional_data, updated_at, model_used, processing_time_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)",
            (
                file_path,
                file_hash,
                file_size,
                file_mtime,
                metadata.get("belongs", False),
                metadata.get("page_number"),
                metadata.get("total_pages"),
                metadata.get("page_position"),
                metadata.get("confidence"),
                metadata.get("company"),
                metadata.get("document_type"),
                metadata.get("document_date"),
                additional_data,
                model_used,
                processing_time_ms,
            ),
        )
        self.conn.commit()

    def get_metadata(self, file_path: str) -> dict[str, Any] | None:
        """Retrieve metadata for a file if it exists and is current."""
        if not os.path.exists(file_path):
            return None

        metadata = self.conn.fetch_one_dict(
            "SELECT * FROM active_metadata WHERE file_path = ?",
            (file_path,),
            json_fields=["additional_data"],
        )
        if not metadata:
            return None

        current_mtime = os.path.getmtime(file_path)
        current_size = os.path.getsize(file_path)
        if metadata["file_mtime"] != current_mtime or metadata["file_size"] != current_size:
            self.delete_metadata(file_path)
            return None
        return metadata

    def delete_metadata(self, file_path: str) -> None:
        """Delete metadata for a file."""
        self.conn.execute("DELETE FROM active_metadata WHERE file_path = ?", (file_path,))
        self.conn.commit()

    def archive_document(
        self, pdf_path: str, source_files: list[str], document_metadata: dict[str, Any]
    ) -> None:
        """Archive metadata for a completed document."""
        pages_metadata = []
        for file_path in source_files:
            page_meta = self.get_metadata(file_path)
            if page_meta:
                for key in ["id", "created_at", "updated_at"]:
                    page_meta.pop(key, None)
                pages_metadata.append(page_meta)

        self.conn.execute(
            "INSERT INTO archived_metadata (pdf_path, pdf_filename, pdf_created_at, company, document_type, document_date, total_pages, source_files, pages_metadata, additional_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
        self.conn.commit()

    def get_archived_document(self, pdf_path: str) -> dict[str, Any] | None:
        """Retrieve archived metadata for a PDF."""
        return self.conn.fetch_one_dict(
            "SELECT * FROM archived_metadata WHERE pdf_path = ?",
            (pdf_path,),
            json_fields=["source_files", "pages_metadata", "additional_data"],
        )

    def get_statistics(self) -> dict[str, Any]:
        """Get database statistics."""
        active_row = self.conn.fetch_one("SELECT COUNT(*) FROM active_metadata")
        active_count = active_row[0] if active_row else 0
        archived_row = self.conn.fetch_one("SELECT COUNT(*) FROM archived_metadata")
        archived_count = archived_row[0] if archived_row else 0
        pages_row = self.conn.fetch_one("SELECT SUM(total_pages) FROM archived_metadata")
        total_archived_pages = (pages_row[0] if pages_row else 0) or 0
        db_size = os.path.getsize(self.conn.db_path) if os.path.exists(self.conn.db_path) else 0

        return {
            "active_metadata_count": active_count,
            "archived_documents_count": archived_count,
            "total_archived_pages": total_archived_pages,
            "database_path": self.conn.db_path,
            "database_size_bytes": db_size,
        }

    def cleanup_orphaned_metadata(self) -> int:
        """Remove metadata for files that no longer exist."""
        rows = self.conn.fetch_all("SELECT file_path FROM active_metadata")
        removed = 0
        for row in rows:
            if not os.path.exists(row["file_path"]):
                self.delete_metadata(row["file_path"])
                removed += 1
        return removed

    def create_backup(self, backup_path: str | None = None) -> str:
        """Create a backup of the database."""
        import shutil

        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{self.conn.db_path}.backup_{timestamp}"
        shutil.copy2(self.conn.db_path, backup_path)
        return backup_path

    @staticmethod
    def _compute_file_hash(file_path: str) -> str:
        """Compute SHA-256 hash of file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
