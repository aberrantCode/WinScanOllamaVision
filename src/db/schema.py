"""
Database schema creation and migrations.

Centralizes all table creation and schema versioning logic.
"""

from db.connection import DatabaseConnection


def create_all_tables(conn: DatabaseConnection) -> None:
    """
    Create all database tables and indices.

    Args:
        conn: Database connection
    """
    _create_metadata_tables(conn)
    _create_analysis_tables(conn)
    _create_indices(conn)
    _run_migrations(conn)
    conn.commit()


def _create_metadata_tables(conn: DatabaseConnection) -> None:
    """Create metadata-related tables."""
    if conn.connection is None:
        raise RuntimeError("Database connection not initialized")
    cursor = conn.connection.cursor()

    # Schema version tracking
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
            processing_time_ms INTEGER,

            -- Rotation (added via migration)
            rotation_degrees INTEGER DEFAULT 0
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


def _create_analysis_tables(conn: DatabaseConnection) -> None:
    """Create analysis-related tables."""
    if conn.connection is None:
        raise RuntimeError("Database connection not initialized")
    cursor = conn.connection.cursor()

    # Analysis results - comprehensive page-level metadata
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            file_hash TEXT NOT NULL,

            -- Provider information
            provider_name TEXT NOT NULL,
            model_name TEXT NOT NULL,

            -- Comprehensive analysis fields
            document_type TEXT,
            company TEXT,
            document_date TEXT,
            page_number INTEGER,
            total_pages INTEGER,
            belongs_to_same_doc BOOLEAN,
            confidence_score REAL,

            -- Rotation analysis
            rotation_needed BOOLEAN DEFAULT 0,
            suggested_rotation INTEGER DEFAULT 0,
            rotation_confidence TEXT,

            -- Full LLM response
            raw_response TEXT,

            -- Extracted metadata (JSON)
            extracted_metadata TEXT,

            -- Timestamps
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processing_time_ms INTEGER,

            -- Cache tracking
            is_cached BOOLEAN DEFAULT 0,
            cache_hit_count INTEGER DEFAULT 0
        )
    """)

    # LLM providers configuration
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS llm_providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_name TEXT UNIQUE NOT NULL,
            provider_type TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 0,

            -- Configuration (stored as JSON)
            config TEXT,

            -- Model information
            default_model TEXT,
            available_models TEXT,

            -- Connection info
            endpoint TEXT,
            timeout INTEGER,

            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP
        )
    """)

    # Source directories for multi-directory support
    cursor.execute("""
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
    """)

    # Document bundles - AI-generated suggestions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_bundles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bundle_name TEXT,

            -- Bundle metadata
            company TEXT,
            document_type TEXT,
            document_date TEXT,
            total_pages INTEGER,

            -- Confidence scoring
            confidence_score REAL,
            confidence_level TEXT,

            -- File list (JSON array of file paths)
            file_paths TEXT NOT NULL,

            -- Bundle status
            status TEXT DEFAULT 'suggested',

            -- PDF generation tracking
            pdf_path TEXT,

            -- User action tracking
            user_action TEXT,
            action_timestamp TIMESTAMP,

            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Rotation preferences - per-file rotation tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rotation_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,

            -- Rotation info
            rotation_degrees INTEGER NOT NULL,
            rotation_source TEXT NOT NULL,

            -- Timestamps
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Audit trail - optional user action tracking
    cursor.execute("""
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
    """)

    # Analysis errors - track individual file failures
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,

            -- Error details
            error_message TEXT,
            error_type TEXT,

            -- Timestamp
            error_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def _create_indices(conn: DatabaseConnection) -> None:
    """Create database indices for performance."""
    if conn.connection is None:
        raise RuntimeError("Database connection not initialized")
    cursor = conn.connection.cursor()

    # Metadata indices
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

    # Analysis indices
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_analysis_file_path
        ON analysis_results(file_path)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_analysis_file_hash
        ON analysis_results(file_hash)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_analysis_provider
        ON analysis_results(provider_name, model_name)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_analysis_confidence
        ON analysis_results(confidence_score)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_analysis_company_type
        ON analysis_results(company, document_type)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_analysis_date
        ON analysis_results(analyzed_at DESC)
    """)

    # Bundle indices
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_bundles_status
        ON document_bundles(status)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_bundles_confidence
        ON document_bundles(confidence_level, confidence_score)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_bundle_status
        ON document_bundles(status)
    """)

    # Directory indices
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_source_dirs_active
        ON source_directories(is_active)
    """)


def _run_migrations(conn: DatabaseConnection) -> None:
    """Run database migrations to latest version."""
    if conn.connection is None:
        raise RuntimeError("Database connection not initialized")
    cursor = conn.connection.cursor()

    # Check current version
    cursor.execute("SELECT MAX(version) FROM schema_version")
    result = cursor.fetchone()
    current_version = result[0] if result and result[0] is not None else 0

    # Migration 1: Initial schema
    if current_version < 1:
        cursor.execute("""
            INSERT INTO schema_version (version, description)
            VALUES (1, 'Initial metadata schema with active and archived tables')
        """)
        conn.commit()
        current_version = 1

    # Migration 2: Add rotation_degrees column (if table exists without it)
    if current_version < 2:
        # Check if column exists
        cursor.execute("PRAGMA table_info(active_metadata)")
        columns = [col[1] for col in cursor.fetchall()]
        if "rotation_degrees" not in columns:
            cursor.execute("""
                ALTER TABLE active_metadata
                ADD COLUMN rotation_degrees INTEGER DEFAULT 0
            """)
        cursor.execute("""
            INSERT INTO schema_version (version, description)
            VALUES (2, 'Add rotation_degrees column for display-only rotation')
        """)
        conn.commit()
        current_version = 2

    # Migration 3: Remove run tracking (analysis_runs and run_id from analysis_errors)
    if current_version < 3:
        # Check if analysis_runs table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='analysis_runs'
        """)
        if cursor.fetchone():
            # Drop analysis_runs table
            cursor.execute("DROP TABLE IF EXISTS analysis_runs")

        # Check if analysis_errors has run_id column
        cursor.execute("PRAGMA table_info(analysis_errors)")
        columns = [col[1] for col in cursor.fetchall()]
        if "run_id" in columns:
            # Create new analysis_errors table without run_id
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analysis_errors_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    error_message TEXT,
                    error_type TEXT,
                    error_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Copy existing data (excluding run_id)
            cursor.execute("""
                INSERT INTO analysis_errors_new (id, file_path, error_message, error_type, error_at)
                SELECT id, file_path, error_message, error_type, error_at
                FROM analysis_errors
            """)

            # Drop old table and rename new one
            cursor.execute("DROP TABLE analysis_errors")
            cursor.execute("ALTER TABLE analysis_errors_new RENAME TO analysis_errors")

        cursor.execute("""
            INSERT INTO schema_version (version, description)
            VALUES (3, 'Remove run tracking: drop analysis_runs table and run_id from analysis_errors')
        """)
        conn.commit()
        current_version = 3

    # Migration 4: Add tax_related column to analysis_results
    if current_version < 4:
        # Check if column exists
        cursor.execute("PRAGMA table_info(analysis_results)")
        columns = [col[1] for col in cursor.fetchall()]
        if "tax_related" not in columns:
            cursor.execute("""
                ALTER TABLE analysis_results
                ADD COLUMN tax_related BOOLEAN DEFAULT 0
            """)
        cursor.execute("""
            INSERT INTO schema_version (version, description)
            VALUES (4, 'Add tax_related column for tax document classification')
        """)
        conn.commit()
        current_version = 4

    # Migration 5: Add pdf_path column to document_bundles
    if current_version < 5:
        # Check if column exists
        cursor.execute("PRAGMA table_info(document_bundles)")
        columns = [col[1] for col in cursor.fetchall()]
        if "pdf_path" not in columns:
            cursor.execute("""
                ALTER TABLE document_bundles
                ADD COLUMN pdf_path TEXT
            """)
        cursor.execute("""
            INSERT INTO schema_version (version, description)
            VALUES (5, 'Add pdf_path column to track generated PDF locations')
        """)
        conn.commit()
        current_version = 5


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
    cursor.execute("SELECT MAX(version) FROM schema_version")
    result = cursor.fetchone()
    return result[0] if result and result[0] is not None else 0
