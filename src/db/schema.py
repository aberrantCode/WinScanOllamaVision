"""
Database schema creation and migrations.

Unified schema (Migration 1) - Clean slate representing the final data model.
All legacy migrations removed for simplicity and maintainability.
"""

import sqlite3

from db.connection import DatabaseConnection
from services.logging_service import get_logger

logger = get_logger()

# Cache to track which database files have been initialized
# Key: database file path, Value: schema version
_schema_initialized: dict[str, int] = {}


def _execute_sql(cursor: sqlite3.Cursor, query: str, params: tuple = ()) -> sqlite3.Cursor:
    """
    Execute SQL with debug logging.

    Args:
        cursor: Database cursor
        query: SQL query string
        params: Query parameters

    Returns:
        Cursor with results
    """
    # Log SQL statement at DEBUG level
    if params:
        logger.debug(f"SQL (schema): {query.strip()[:200]}... | Params: {params}")
    else:
        # Truncate long CREATE TABLE statements for readability
        log_query = query.strip()
        if len(log_query) > 200:
            log_query = log_query[:200] + "..."
        logger.debug(f"SQL (schema): {log_query}")

    return cursor.execute(query, params)


def create_all_tables(conn: DatabaseConnection, force: bool = False) -> None:
    """
    Create all database tables and indices.

    Uses caching to avoid redundant schema checks per database file.
    Schema initialization is only run once per database file per application session.

    Args:
        conn: Database connection
        force: Force schema initialization even if cached (default: False)
    """
    global _schema_initialized

    # Get database file path for cache key
    db_path = conn.db_path

    # Check if schema is already initialized for this database
    if not force and db_path in _schema_initialized:
        logger.debug(
            f"Schema already initialized for {db_path} (version {_schema_initialized[db_path]})"
        )
        return

    logger.debug(f"Initializing schema for {db_path}")

    # Run full schema initialization
    _create_core_tables(conn)
    _create_junction_tables(conn)
    _create_indices(conn)
    _run_migrations(conn)
    conn.commit()

    # Cache the schema version to prevent redundant initialization
    current_version = get_schema_version(conn)
    _schema_initialized[db_path] = current_version
    logger.debug(f"Schema initialized for {db_path} (version {current_version})")


def _create_core_tables(conn: DatabaseConnection) -> None:
    """Create core application tables."""
    if conn.connection is None:
        raise RuntimeError("Database connection not initialized")
    cursor = conn.connection.cursor()

    # Schema version tracking
    _execute_sql(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        )
    """,
    )

    # Image files - Central registry of all scanned images
    _execute_sql(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS image_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            file_hash TEXT NOT NULL,

            -- File metadata
            directory_path TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_mtime REAL NOT NULL,

            -- Lifecycle tracking
            status TEXT DEFAULT 'registered',

            -- Timestamps
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMP
        )
    """,
    )

    # Analysis results - LLM analysis audit trail (provenance only, not metadata)
    _execute_sql(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Foreign key
            image_file_id INTEGER NOT NULL,

            -- Provider provenance
            provider_name TEXT NOT NULL,
            model_name TEXT NOT NULL,
            model_options TEXT,

            -- LLM interaction (audit trail)
            prompt_text TEXT,
            response_text TEXT NOT NULL,
            extracted_metadata TEXT,

            -- Analysis quality
            confidence_score REAL,
            had_error BOOLEAN DEFAULT 0,

            -- Performance tracking
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processing_time_ms INTEGER,

            FOREIGN KEY (image_file_id) REFERENCES image_files(id) ON DELETE CASCADE
        )
    """,
    )

    # Metadata - Normalized document metadata (single source of truth)
    _execute_sql(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Foreign Keys
            image_file_id INTEGER NOT NULL UNIQUE,
            analysis_result_id INTEGER,

            -- Document Metadata (user-editable)
            company TEXT,
            document_type TEXT,
            document_date TEXT,
            page_number INTEGER,
            total_pages INTEGER,
            belongs_to_same_doc BOOLEAN DEFAULT 0,
            confidence_score REAL,
            tax_related BOOLEAN DEFAULT 0,
            document_category TEXT,

            -- Display preferences
            rotation INTEGER DEFAULT 0,
            output_filename TEXT,

            -- Provenance
            user_verified BOOLEAN DEFAULT 0,
            auto_approved BOOLEAN DEFAULT 1,
            last_edited_by TEXT DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (image_file_id) REFERENCES image_files(id) ON DELETE CASCADE,
            FOREIGN KEY (analysis_result_id) REFERENCES analysis_results(id) ON DELETE SET NULL
        )
    """,
    )

    # Document bundles - AI-suggested document groupings
    _execute_sql(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS document_bundles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bundle_name TEXT,

            -- AI confidence
            confidence_score REAL,
            confidence_level TEXT,

            -- Workflow status
            status TEXT DEFAULT 'suggested',
            user_action TEXT,
            action_timestamp TIMESTAMP,

            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    )

    # PDF files - Generated PDF tracking
    _execute_sql(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS pdf_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pdf_path TEXT UNIQUE NOT NULL,
            pdf_filename TEXT NOT NULL,
            file_hash TEXT,
            file_size INTEGER,
            page_count INTEGER,
            bundle_id INTEGER,
            generation_status TEXT DEFAULT 'completed',
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (bundle_id) REFERENCES document_bundles(id) ON DELETE SET NULL
        )
    """,
    )

    # Source directories - Scan directory configuration
    _execute_sql(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS source_directories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            directory_path TEXT UNIQUE NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            scan_on_startup BOOLEAN DEFAULT 1,

            -- Directory metadata
            last_scanned_at TIMESTAMP,
            file_count INTEGER DEFAULT 0,
            last_file_count INTEGER DEFAULT 0,

            -- Settings (JSON)
            directory_settings TEXT,

            -- Timestamps
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    )

    # Audit trail - User action tracking
    _execute_sql(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS audit_trail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_type TEXT NOT NULL,
            action_details TEXT,

            -- Context
            file_path TEXT,
            bundle_id INTEGER,

            -- User info (optional)
            user_identifier TEXT,

            -- Timestamp
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    )


def _create_junction_tables(conn: DatabaseConnection) -> None:
    """Create junction tables for many-to-many relationships."""
    if conn.connection is None:
        raise RuntimeError("Database connection not initialized")
    cursor = conn.connection.cursor()

    # PDF-Image relationship (many-to-many: one image can be in multiple PDFs)
    _execute_sql(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS pdf_image_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pdf_file_id INTEGER NOT NULL,
            image_file_id INTEGER NOT NULL,
            page_number INTEGER NOT NULL,

            FOREIGN KEY (pdf_file_id) REFERENCES pdf_files(id) ON DELETE CASCADE,
            FOREIGN KEY (image_file_id) REFERENCES image_files(id) ON DELETE CASCADE,
            UNIQUE(pdf_file_id, page_number)
        )
    """,
    )

    # Bundle-Image relationship (many-to-many: images can be in multiple bundle suggestions)
    _execute_sql(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS bundle_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bundle_id INTEGER NOT NULL,
            image_file_id INTEGER NOT NULL,
            sequence_order INTEGER NOT NULL,

            FOREIGN KEY (bundle_id) REFERENCES document_bundles(id) ON DELETE CASCADE,
            FOREIGN KEY (image_file_id) REFERENCES image_files(id) ON DELETE CASCADE,
            UNIQUE(bundle_id, image_file_id),
            UNIQUE(bundle_id, sequence_order)
        )
    """,
    )


def _create_indices(conn: DatabaseConnection) -> None:
    """Create database indices for performance."""
    if conn.connection is None:
        raise RuntimeError("Database connection not initialized")
    cursor = conn.connection.cursor()

    # Image files indices
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_image_files_path
        ON image_files(file_path)
    """,
    )
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_image_files_status
        ON image_files(status)
    """,
    )
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_image_files_directory
        ON image_files(directory_path)
    """,
    )
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_image_files_hash
        ON image_files(file_hash)
    """,
    )

    # Analysis results indices
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_analysis_image_file
        ON analysis_results(image_file_id)
    """,
    )
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_analysis_provider
        ON analysis_results(provider_name, model_name)
    """,
    )
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_analysis_confidence
        ON analysis_results(confidence_score)
    """,
    )
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_analysis_date
        ON analysis_results(analyzed_at DESC)
    """,
    )
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_analysis_errors
        ON analysis_results(had_error)
    """,
    )

    # Metadata indices
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_metadata_image_file
        ON metadata(image_file_id)
    """,
    )
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_metadata_analysis_result
        ON metadata(analysis_result_id)
    """,
    )
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_metadata_company_type
        ON metadata(company, document_type)
    """,
    )
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_metadata_category
        ON metadata(document_category)
    """,
    )

    # Bundle indices
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_bundles_status
        ON document_bundles(status)
    """,
    )
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_bundles_confidence
        ON document_bundles(confidence_level, confidence_score)
    """,
    )

    # PDF files indices
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_pdf_files_path
        ON pdf_files(pdf_path)
    """,
    )
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_pdf_files_bundle
        ON pdf_files(bundle_id)
    """,
    )

    # Source directories indices
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_source_dirs_active
        ON source_directories(is_active)
    """,
    )

    # Junction table indices
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_pdf_pages_pdf
        ON pdf_image_pages(pdf_file_id)
    """,
    )
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_pdf_pages_image
        ON pdf_image_pages(image_file_id)
    """,
    )
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_bundle_images_bundle
        ON bundle_images(bundle_id)
    """,
    )
    _execute_sql(
        cursor,
        """
        CREATE INDEX IF NOT EXISTS idx_bundle_images_image
        ON bundle_images(image_file_id)
    """,
    )


def _run_migrations(conn: DatabaseConnection) -> None:
    """Run database migrations to latest version."""
    if conn.connection is None:
        raise RuntimeError("Database connection not initialized")
    cursor = conn.connection.cursor()

    # Check current version
    _execute_sql(cursor, "SELECT MAX(version) FROM schema_version")
    result = cursor.fetchone()
    current_version = result[0] if result and result[0] is not None else 0

    # Migration 1: Initial unified schema
    if current_version < 1:
        logger.info("Running Migration 1: Create unified schema")

        _execute_sql(
            cursor,
            """
            INSERT INTO schema_version (version, description)
            VALUES (1, 'Unified schema - clean data model with 8 core tables and 2 junction tables')
        """,
        )
        conn.commit()
        logger.info("Migration 1 completed successfully")
        current_version = 1


def get_schema_version(conn: DatabaseConnection) -> int:
    """
    Get current database schema version.

    Args:
        conn: Database connection

    Returns:
        Schema version number
    """
    if conn.connection is None:
        raise RuntimeError("Database connection not initialized")
    cursor = conn.connection.cursor()
    _execute_sql(cursor, "SELECT MAX(version) FROM schema_version")
    result = cursor.fetchone()
    return result[0] if result and result[0] is not None else 0


def clear_schema_cache(db_path: str | None = None) -> None:
    """
    Clear schema initialization cache.

    Useful for testing or when forcing schema re-initialization.

    Args:
        db_path: Specific database path to clear, or None to clear all
    """
    global _schema_initialized

    if db_path:
        _schema_initialized.pop(db_path, None)
        logger.debug(f"Cleared schema cache for {db_path}")
    else:
        _schema_initialized.clear()
        logger.debug("Cleared all schema cache entries")
