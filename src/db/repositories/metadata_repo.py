"""Repository for normalized user-approved metadata."""

import logging
import os
import sqlite3
from typing import Any

from db.connection import DatabaseConnection
from services.metadata_normalizer import MetadataNormalizer

logger: logging.Logger | None = None


class MetadataRepository:
    """Repository for normalized user-approved metadata."""

    def __init__(self, conn: DatabaseConnection):
        """
        Initialize metadata repository.

        Args:
            conn: Database connection
        """
        self.conn = conn

    def _get_logger(self) -> logging.Logger:
        """Get logger instance (lazy initialization).

        Kept lazy rather than pulled into __init__ so that instantiating the
        repository before LoggingService.initialize() has run (e.g. in unit
        tests that exercise the connection layer in isolation) does not raise.
        """
        global logger
        if logger is None:
            from services.logging_service import get_logger as _get_logger

            logger = _get_logger()
        return logger

    # ------------------------------------------------------------------
    # Internal transaction helpers
    # ------------------------------------------------------------------
    #
    # Every public write method must guard BOTH ``execute`` and ``commit``
    # in the same try/except. Execute-time errors (IntegrityError,
    # OperationalError on a locked DB, DataError) would otherwise bypass
    # the rollback branch entirely and leak an uncommitted transaction up
    # the call stack — meaning callers have no way to know whether the
    # operation partially applied.
    #
    # Use ``_run_write(op_name, fn)`` inside each public write method to
    # run the execute + commit sequence atomically and surface a uniform
    # error message.

    def _run_write(self, op_name: str, fn: Any) -> Any:
        """Execute a unit-of-work callable and commit, rolling back on failure.

        Args:
            op_name: Human-readable operation name for log messages and
                the user-facing error text.
            fn: Zero-argument callable that performs ``self.conn.execute(...)``
                calls. Return value is passed through to the caller so the
                method can retrieve ``cursor.lastrowid`` etc.

        Raises:
            sqlite3.OperationalError: Database is locked or unavailable.
            sqlite3.Error: Any other sqlite-layer failure.
        """
        try:
            result = fn()
            self.conn.commit()
            return result
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[METADATA REPO] {op_name} — DB locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            self._get_logger().error(f"[METADATA REPO] {op_name} — DB error: {e}")
            self.conn.rollback()
            # Preserve original casing on op_name so callers and tests can
            # match specific phrases like "Failed to link images to PDF".
            raise sqlite3.Error(f"Failed to {op_name}: {e}") from e

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def create_from_analysis(
        self,
        image_file_id: int,
        analysis_result_id: int | None,
        normalized_metadata: dict[str, Any],
        output_filename: str | None = None,
        document_category: str | None = None,
    ) -> int:
        """
        Create metadata record from normalized analysis.

        Uses ON CONFLICT DO UPDATE rather than INSERT OR REPLACE — the
        latter compiles to DELETE + INSERT in SQLite, which cascades
        through ON DELETE CASCADE foreign keys and silently prunes any
        child rows that reference the metadata row's primary key.
        UPSERT updates in-place and preserves referential integrity.

        Args:
            image_file_id: Image file ID
            analysis_result_id: Analysis result ID (None if metadata created without analysis)
            normalized_metadata: Normalized metadata dictionary
            output_filename: Optional desired output filename
            document_category: Optional document category

        Returns:
            Metadata record ID (id of the row that was inserted or updated).
        """
        params = (
            image_file_id,
            analysis_result_id,
            normalized_metadata.get("company"),
            normalized_metadata.get("document_type"),
            normalized_metadata.get("document_date"),
            normalized_metadata.get("page_number"),
            normalized_metadata.get("total_pages"),
            normalized_metadata.get("belongs_to_same_doc"),
            normalized_metadata.get("rotation"),
            normalized_metadata.get("confidence_score"),
            normalized_metadata.get("tax_related"),
            normalized_metadata.get("is_blank"),
            output_filename,
            document_category,
        )

        def _op() -> sqlite3.Cursor:
            return self.conn.execute(
                """
                INSERT INTO metadata (
                    image_file_id, analysis_result_id,
                    company, document_type, document_date,
                    page_number, total_pages, belongs_to_same_doc,
                    rotation, confidence_score, tax_related, is_blank,
                    output_filename, document_category,
                    auto_approved, last_edited_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'ai')
                ON CONFLICT(image_file_id) DO UPDATE SET
                    analysis_result_id = excluded.analysis_result_id,
                    company            = excluded.company,
                    document_type      = excluded.document_type,
                    document_date      = excluded.document_date,
                    page_number        = excluded.page_number,
                    total_pages        = excluded.total_pages,
                    belongs_to_same_doc = excluded.belongs_to_same_doc,
                    rotation           = excluded.rotation,
                    confidence_score   = excluded.confidence_score,
                    tax_related        = excluded.tax_related,
                    is_blank           = excluded.is_blank,
                    output_filename    = excluded.output_filename,
                    document_category  = excluded.document_category,
                    auto_approved      = 1,
                    last_edited_by     = 'ai',
                    updated_at         = CURRENT_TIMESTAMP
            """,
                params,
            )

        cursor = self._run_write("create metadata record", _op)

        # For an INSERT path, cursor.lastrowid holds the new row id. For
        # the UPDATE path (ON CONFLICT), lastrowid can be 0 or None
        # depending on SQLite version; in that case look up the existing
        # row by the unique image_file_id.
        metadata_id: int | None = cursor.lastrowid
        if not metadata_id:
            row = self.conn.fetch_one(
                "SELECT id FROM metadata WHERE image_file_id = ?", (image_file_id,)
            )
            if row is None:
                raise RuntimeError("Failed to retrieve inserted metadata ID")
            metadata_id = int(row[0])
        return metadata_id

    def update_from_user(self, image_file_id: int, updates: dict[str, Any]) -> None:
        """
        Update metadata after user edit (creates if not exists).

        Args:
            image_file_id: Image file ID
            updates: Dictionary of fields to update
        """
        # Build dynamic UPSERT query
        allowed_fields = {
            "company",
            "document_type",
            "document_date",
            "page_number",
            "total_pages",
            "belongs_to_same_doc",
            "rotation",
            "confidence_score",
            "tax_related",
            "is_blank",
            "output_filename",
            "document_category",
        }

        # Filter to only allowed fields
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not filtered_updates:
            return

        # Normalize each field using MetadataNormalizer
        normalizer = MetadataNormalizer()
        field_normalizers = {
            "company": normalizer.normalize_company,
            "document_type": normalizer.normalize_document_type,
            "document_category": normalizer.normalize_document_type,
            "document_date": normalizer.normalize_date,
            "rotation": normalizer.normalize_rotation,
            "is_blank": normalizer.normalize_boolean,
            "tax_related": normalizer.normalize_boolean,
            "belongs_to_same_doc": normalizer.normalize_boolean,
            "page_number": normalizer.normalize_page_number,
            "total_pages": normalizer.normalize_page_number,
            "confidence_score": normalizer.normalize_confidence,
        }
        for field, normalize_fn in field_normalizers.items():
            if field in filtered_updates:
                filtered_updates[field] = normalize_fn(filtered_updates[field])

        # Build INSERT columns and values
        columns = ["image_file_id"] + list(filtered_updates.keys())
        placeholders = ["?"] * len(columns)
        values = [image_file_id] + list(filtered_updates.values())

        # Build ON CONFLICT DO UPDATE clause
        update_clauses = [f"{field} = excluded.{field}" for field in filtered_updates]
        update_clause = ", ".join(update_clauses)
        update_clause += (
            ", user_verified = 1, last_edited_by = 'user', updated_at = CURRENT_TIMESTAMP"
        )

        query = f"""
            INSERT INTO metadata ({", ".join(columns)})
            VALUES ({", ".join(placeholders)})
            ON CONFLICT(image_file_id) DO UPDATE SET {update_clause}
        """

        self._run_write(
            "update metadata",
            lambda: self.conn.execute(query, tuple(values)),
        )

    def get_by_image_file_id(self, image_file_id: int) -> dict[str, Any] | None:
        """
        Get current metadata for image.

        Args:
            image_file_id: Image file ID

        Returns:
            Metadata dictionary or None
        """
        return self.conn.fetch_one_dict(
            "SELECT * FROM metadata WHERE image_file_id = ?",
            (image_file_id,),
        )

    def get_by_image_path(self, file_path: str) -> dict[str, Any] | None:
        """
        Get metadata by image file path.

        Args:
            file_path: Image file path

        Returns:
            Metadata dictionary or None
        """
        file_path = os.path.normpath(file_path)
        return self.conn.fetch_one_dict(
            """
            SELECT m.*
            FROM metadata m
            INNER JOIN image_files img ON m.image_file_id = img.id
            WHERE img.file_path = ?
        """,
            (file_path,),
        )

    def link_to_pdf(self, image_file_ids: list[int], pdf_file_id: int) -> None:
        """
        Link images to PDF via bundle.

        In the new schema, PDFs are linked to bundles, not directly to images.
        This method adds images to the bundle that the PDF belongs to.

        Args:
            image_file_ids: List of image file IDs
            pdf_file_id: PDF file ID
        """
        if not image_file_ids:
            return

        # Get the bundle_id for this PDF
        result = self.conn.fetch_one_dict(
            "SELECT bundle_id FROM pdf_files WHERE id = ?",
            (pdf_file_id,),
        )

        if not result or not result["bundle_id"]:
            return

        bundle_id = result["bundle_id"]

        def _op() -> None:
            # Add images to bundle via bundle_images table
            for sequence, image_file_id in enumerate(image_file_ids, start=1):
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO bundle_images (bundle_id, image_file_id, sequence_order)
                    VALUES (?, ?, ?)
                """,
                    (bundle_id, image_file_id, sequence),
                )

        # Case preserved for caller-visible error text.
        self._run_write("link images to PDF", _op)

    def get_analysis_history(self, image_file_id: int) -> list[dict[str, Any]]:
        """
        Get all analysis_results for this image (for comparison).

        Args:
            image_file_id: Image file ID

        Returns:
            List of analysis result dictionaries
        """
        # Get all analyses for this image_file_id. fetch_all_dicts already
        # returns [] on empty — no post-hoc "or []" needed.
        return self.conn.fetch_all_dicts(
            """
            SELECT *
            FROM analysis_results
            WHERE image_file_id = ?
            ORDER BY analyzed_at DESC
        """,
            (image_file_id,),
            json_fields=["extracted_metadata", "model_options"],
        )

    def get_all(
        self, status_filter: str | None = None, directory_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get all metadata records with optional filters.

        Args:
            status_filter: Optional image status filter
            directory_filter: Optional directory path filter

        Returns:
            List of metadata dictionaries with joined image info
        """
        query = """
            SELECT
                m.*,
                img.file_path,
                img.filename,
                img.directory_path,
                img.status as image_status
            FROM metadata m
            INNER JOIN image_files img ON m.image_file_id = img.id
            WHERE 1=1
        """

        params: list[Any] = []

        if status_filter:
            query += " AND img.status = ?"
            params.append(status_filter)

        if directory_filter:
            query += " AND img.directory_path = ?"
            params.append(os.path.normpath(directory_filter))

        query += " ORDER BY m.updated_at DESC"

        return self.conn.fetch_all_dicts(query, tuple(params))

    def delete_by_image_file_id(self, image_file_id: int) -> None:
        """
        Delete metadata record.

        Args:
            image_file_id: Image file ID
        """
        self._run_write(
            "delete metadata record",
            lambda: self.conn.execute(
                "DELETE FROM metadata WHERE image_file_id = ?", (image_file_id,)
            ),
        )

    def get_unique_companies(self) -> list[str]:
        """
        Get unique company names for autocomplete.

        Returns:
            List of company names
        """
        results = self.conn.fetch_all(
            """
            SELECT DISTINCT company
            FROM metadata
            WHERE company IS NOT NULL AND company != ''
            ORDER BY company
        """
        )
        return [row[0] for row in results]

    def get_unique_document_types(self) -> list[str]:
        """
        Get unique document types for autocomplete.

        Returns:
            List of document types
        """
        results = self.conn.fetch_all(
            """
            SELECT DISTINCT document_type
            FROM metadata
            WHERE document_type IS NOT NULL AND document_type != ''
            ORDER BY document_type
        """
        )
        return [row[0] for row in results]

    def get_unique_categories(self) -> list[str]:
        """
        Get unique document categories for autocomplete.

        Returns:
            List of document categories
        """
        results = self.conn.fetch_all(
            """
            SELECT DISTINCT document_category
            FROM metadata
            WHERE document_category IS NOT NULL AND document_category != ''
            ORDER BY document_category
        """
        )
        return [row[0] for row in results]

    def get_stats(self) -> dict[str, int]:
        """
        Get metadata statistics.

        Returns:
            Dictionary with statistics
        """
        if self.conn.connection is None:
            raise RuntimeError("Database connection not initialized")

        cursor = self.conn.connection.cursor()

        # Total metadata records
        cursor.execute("SELECT COUNT(*) FROM metadata")
        total = cursor.fetchone()[0]

        # User-verified count
        cursor.execute("SELECT COUNT(*) FROM metadata WHERE user_verified = 1")
        user_verified = cursor.fetchone()[0]

        # Auto-approved count
        cursor.execute("SELECT COUNT(*) FROM metadata WHERE auto_approved = 1")
        auto_approved = cursor.fetchone()[0]

        # Linked to PDFs (via bundle_images -> pdf_files)
        cursor.execute("""
            SELECT COUNT(DISTINCT m.id)
            FROM metadata m
            INNER JOIN bundle_images bi ON m.image_file_id = bi.image_file_id
            INNER JOIN document_bundles b ON bi.bundle_id = b.id
            INNER JOIN pdf_files p ON b.id = p.bundle_id
        """)
        linked_to_pdf = cursor.fetchone()[0]

        return {
            "total": total,
            "user_verified": user_verified,
            "auto_approved": auto_approved,
            "linked_to_pdf": linked_to_pdf,
        }
