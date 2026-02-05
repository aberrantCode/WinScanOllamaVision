"""
Analysis Database Manager
Extended database layer for comprehensive page analysis, bundling suggestions,
and multi-provider LLM support.
"""

import json
import os
import sqlite3
from typing import Any


class AnalysisDB:
    """Manages extended SQLite database for analysis results and bundling"""

    def __init__(self, db_path: str = None):
        """
        Initialize analysis database connection.

        Args:
            db_path: Path to SQLite database file (same as MetadataDB). If None, uses AppData directory.
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
        self._create_extended_tables()

    def _connect(self):
        """Establish database connection"""
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row

    def _create_extended_tables(self):
        """Create new tables for analysis functionality"""
        cursor = self.connection.cursor()

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

        # Analysis runs - track each analysis run
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT UNIQUE NOT NULL,

                -- Run statistics
                total_files INTEGER NOT NULL,
                analyzed INTEGER DEFAULT 0,
                cached INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                skipped INTEGER DEFAULT 0,

                -- Timing
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                duration_ms INTEGER,

                -- Status
                status TEXT DEFAULT 'running'
            )
        """)

        # Analysis errors - track individual file failures
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                file_path TEXT NOT NULL,

                -- Error details
                error_message TEXT,
                error_type TEXT,

                -- Timestamp
                error_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id)
            )
        """)

        # Create indices for performance
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
            CREATE INDEX IF NOT EXISTS idx_bundles_status
            ON document_bundles(status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bundles_confidence
            ON document_bundles(confidence_level, confidence_score)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_dirs_active
            ON source_directories(is_active)
        """)

        # Additional indices for Analysis Status Window transformation
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

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bundle_status
            ON document_bundles(status)
        """)

        self.connection.commit()

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
        """
        Save comprehensive page analysis results.

        Args:
            file_path: Path to analyzed file
            file_hash: SHA-256 hash of file
            provider_name: Name of LLM provider used
            model_name: Model name/identifier
            analysis_data: Extracted metadata dict
            raw_response: Full LLM response text
            processing_time_ms: Processing time in milliseconds
        """
        cursor = self.connection.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO analysis_results (
                file_path, file_hash, provider_name, model_name,
                document_type, company, document_date,
                page_number, total_pages, belongs_to_same_doc,
                confidence_score, rotation_needed, suggested_rotation,
                rotation_confidence, raw_response, extracted_metadata,
                processing_time_ms, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (
                file_path,
                file_hash,
                provider_name,
                model_name,
                analysis_data.get("document_type"),
                analysis_data.get("company"),
                analysis_data.get("document_date"),
                analysis_data.get("page_number"),
                analysis_data.get("total_pages"),
                analysis_data.get("belongs_to_same_doc", False),
                analysis_data.get("confidence_score"),
                analysis_data.get("rotation_needed", False),
                analysis_data.get("suggested_rotation", 0),
                analysis_data.get("rotation_confidence"),
                raw_response,
                json.dumps(analysis_data),
                processing_time_ms,
            ),
        )

        self.connection.commit()

    def get_analysis(self, file_path: str) -> dict[str, Any] | None:
        """
        Retrieve analysis results for a file.

        Args:
            file_path: Path to file

        Returns:
            Analysis dict if found, None otherwise
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM analysis_results WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()

        if not row:
            return None

        analysis = dict(row)

        # Parse JSON fields
        if analysis.get("extracted_metadata"):
            analysis["extracted_metadata"] = json.loads(analysis["extracted_metadata"])

        # Increment cache hit counter
        cursor.execute(
            """
            UPDATE analysis_results
            SET cache_hit_count = cache_hit_count + 1, is_cached = 1
            WHERE file_path = ?
        """,
            (file_path,),
        )
        self.connection.commit()

        return analysis

    def get_analyzed_pages(
        self, directory: str | None = None, provider: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Retrieve all analyzed pages with optional filtering.

        Args:
            directory: Filter by directory path
            provider: Filter by provider name

        Returns:
            List of analysis dicts
        """
        cursor = self.connection.cursor()

        query = "SELECT * FROM analysis_results WHERE 1=1"
        params = []

        if directory:
            query += " AND file_path LIKE ?"
            params.append(f"{directory}%")

        if provider:
            query += " AND provider_name = ?"
            params.append(provider)

        query += " ORDER BY analyzed_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        results = []
        for row in rows:
            analysis = dict(row)
            if analysis.get("extracted_metadata"):
                analysis["extracted_metadata"] = json.loads(analysis["extracted_metadata"])
            results.append(analysis)

        return results

    # ==================== LLM Provider Methods ====================

    def add_provider(
        self,
        provider_name: str,
        provider_type: str,
        config: dict[str, Any],
        default_model: str = None,
        available_models: list[str] = None,
    ) -> None:
        """
        Add or update LLM provider configuration.

        Args:
            provider_name: Unique provider identifier
            provider_type: Type (ollama, claude_cli, gemini_cli)
            config: Provider configuration dict
            default_model: Default model name
            available_models: List of available model names
        """
        cursor = self.connection.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO llm_providers (
                provider_name, provider_type, config,
                default_model, available_models,
                endpoint, timeout, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (
                provider_name,
                provider_type,
                json.dumps(config),
                default_model,
                json.dumps(available_models) if available_models else None,
                config.get("endpoint"),
                config.get("timeout", 300),
            ),
        )

        self.connection.commit()

    def get_active_provider(self) -> dict[str, Any] | None:
        """Get the currently active provider configuration"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM llm_providers WHERE is_active = 1 LIMIT 1")
        row = cursor.fetchone()

        if not row:
            return None

        provider = dict(row)
        if provider.get("config"):
            provider["config"] = json.loads(provider["config"])
        if provider.get("available_models"):
            provider["available_models"] = json.loads(provider["available_models"])

        return provider

    def set_active_provider(self, provider_name: str) -> None:
        """Set the active provider"""
        cursor = self.connection.cursor()

        # Deactivate all providers
        cursor.execute("UPDATE llm_providers SET is_active = 0")

        # Activate specified provider
        cursor.execute(
            """
            UPDATE llm_providers
            SET is_active = 1, last_used_at = CURRENT_TIMESTAMP
            WHERE provider_name = ?
        """,
            (provider_name,),
        )

        self.connection.commit()

    # ==================== Source Directory Methods ====================

    def add_source_directory(self, directory_path: str, scan_on_startup: bool = True) -> None:
        """
        Add a source directory for scanning.

        Args:
            directory_path: Absolute path to directory
            scan_on_startup: Whether to scan on application startup
        """
        cursor = self.connection.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO source_directories (
                directory_path, is_active, scan_on_startup
            ) VALUES (?, 1, ?)
        """,
            (directory_path, scan_on_startup),
        )

        self.connection.commit()

    def get_active_directories(self) -> list[str]:
        """Get list of active source directories"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT directory_path FROM source_directories WHERE is_active = 1")
        return [row["directory_path"] for row in cursor.fetchall()]

    def update_directory_scan_info(self, directory_path: str, file_count: int) -> None:
        """Update directory scan information"""
        cursor = self.connection.cursor()

        cursor.execute(
            """
            UPDATE source_directories
            SET last_scanned_at = CURRENT_TIMESTAMP, file_count = ?
            WHERE directory_path = ?
        """,
            (file_count, directory_path),
        )

        self.connection.commit()

    def remove_source_directory(self, directory_path: str) -> None:
        """Remove a source directory"""
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM source_directories WHERE directory_path = ?", (directory_path,))
        self.connection.commit()

    # ==================== Bundle Methods ====================

    def save_bundle_suggestion(
        self, file_paths: list[str], bundle_metadata: dict[str, Any], confidence_score: float
    ) -> int:
        """
        Save a document bundle suggestion.

        Args:
            file_paths: List of file paths in bundle
            bundle_metadata: Bundle metadata (company, type, date, etc.)
            confidence_score: Confidence score (0.0 to 1.0)

        Returns:
            Bundle ID
        """
        cursor = self.connection.cursor()

        # Determine confidence level
        if confidence_score >= 0.8:
            confidence_level = "high"
        elif confidence_score >= 0.5:
            confidence_level = "medium"
        else:
            confidence_level = "low"

        cursor.execute(
            """
            INSERT INTO document_bundles (
                bundle_name, company, document_type, document_date,
                total_pages, confidence_score, confidence_level,
                file_paths, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'suggested')
        """,
            (
                bundle_metadata.get("bundle_name"),
                bundle_metadata.get("company"),
                bundle_metadata.get("document_type"),
                bundle_metadata.get("document_date"),
                len(file_paths),
                confidence_score,
                confidence_level,
                json.dumps(file_paths),
            ),
        )

        self.connection.commit()
        return cursor.lastrowid

    def get_bundle_suggestions(
        self, min_confidence: float | None = None, status: str = "suggested"
    ) -> list[dict[str, Any]]:
        """
        Get bundle suggestions with optional filtering.

        Args:
            min_confidence: Minimum confidence score
            status: Bundle status filter

        Returns:
            List of bundle dicts
        """
        cursor = self.connection.cursor()

        query = "SELECT * FROM document_bundles WHERE status = ?"
        params = [status]

        if min_confidence is not None:
            query += " AND confidence_score >= ?"
            params.append(min_confidence)

        query += " ORDER BY confidence_score DESC, created_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        bundles = []
        for row in rows:
            bundle = dict(row)
            if bundle.get("file_paths"):
                bundle["file_paths"] = json.loads(bundle["file_paths"])
            bundles.append(bundle)

        return bundles

    def update_bundle_status(
        self, bundle_id: int, status: str, user_action: str | None = None
    ) -> None:
        """
        Update bundle status after user action.

        Args:
            bundle_id: Bundle ID
            status: New status (accepted, rejected, modified, completed)
            user_action: Description of user action
        """
        cursor = self.connection.cursor()

        cursor.execute(
            """
            UPDATE document_bundles
            SET status = ?, user_action = ?, action_timestamp = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (status, user_action, bundle_id),
        )

        self.connection.commit()

    # ==================== Rotation Methods ====================

    def save_rotation_preference(
        self, file_path: str, rotation_degrees: int, rotation_source: str
    ) -> None:
        """
        Save rotation preference for a file.

        Args:
            file_path: Path to file
            rotation_degrees: Rotation in degrees (90, 180, 270)
            rotation_source: Source of rotation (ai_suggestion, manual)
        """
        cursor = self.connection.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO rotation_preferences (
                file_path, rotation_degrees, rotation_source, applied_at
            ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (file_path, rotation_degrees, rotation_source),
        )

        self.connection.commit()

    def get_rotation_preference(self, file_path: str) -> dict[str, Any] | None:
        """Get rotation preference for a file"""
        cursor = self.connection.cursor()
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
        """
        Log user action to audit trail.

        Args:
            action_type: Type of action
            action_details: Detailed description
            file_path: Related file path
            bundle_id: Related bundle ID
        """
        cursor = self.connection.cursor()

        cursor.execute(
            """
            INSERT INTO audit_trail (
                action_type, action_details, file_path, bundle_id
            ) VALUES (?, ?, ?, ?)
        """,
            (action_type, action_details, file_path, bundle_id),
        )

        self.connection.commit()

    # ==================== Statistics & Maintenance ====================

    def get_extended_statistics(self) -> dict[str, Any]:
        """Get comprehensive database statistics"""
        cursor = self.connection.cursor()

        stats = {}

        # Analysis results stats
        cursor.execute("SELECT COUNT(*) FROM analysis_results")
        stats["total_analyzed_pages"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM analysis_results WHERE is_cached = 1")
        stats["cached_analyses"] = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(processing_time_ms) FROM analysis_results")
        stats["avg_processing_time_ms"] = cursor.fetchone()[0] or 0

        # Bundle stats
        cursor.execute("SELECT COUNT(*) FROM document_bundles WHERE status = 'suggested'")
        stats["pending_bundles"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM document_bundles WHERE status = 'accepted'")
        stats["accepted_bundles"] = cursor.fetchone()[0]

        # Provider stats
        cursor.execute("SELECT COUNT(*) FROM llm_providers")
        stats["total_providers"] = cursor.fetchone()[0]

        cursor.execute("SELECT provider_name FROM llm_providers WHERE is_active = 1")
        active_provider = cursor.fetchone()
        stats["active_provider"] = active_provider["provider_name"] if active_provider else None

        # Directory stats
        cursor.execute("SELECT COUNT(*) FROM source_directories WHERE is_active = 1")
        stats["active_directories"] = cursor.fetchone()[0]

        # Audit trail stats
        cursor.execute("SELECT COUNT(*) FROM audit_trail")
        stats["total_actions_logged"] = cursor.fetchone()[0]

        # Database size
        if os.path.exists(self.db_path):
            stats["database_size_bytes"] = os.path.getsize(self.db_path)

        return stats

    def purge_analysis_results(self, older_than_days: int | None = None) -> int:
        """
        Purge old analysis results, runs, and errors.

        Args:
            older_than_days: Delete results older than N days (None = all)

        Returns:
            Number of entries deleted from analysis_results
        """
        cursor = self.connection.cursor()

        if older_than_days:
            # Delete analysis results
            cursor.execute(f"""
                DELETE FROM analysis_results
                WHERE analyzed_at < datetime('now', '-{older_than_days} days')
            """)
            results_deleted = cursor.rowcount

            # Delete analysis runs
            cursor.execute(f"""
                DELETE FROM analysis_runs
                WHERE started_at < datetime('now', '-{older_than_days} days')
            """)

            # Delete analysis errors (orphaned ones will be cleaned up)
            cursor.execute(f"""
                DELETE FROM analysis_errors
                WHERE error_at < datetime('now', '-{older_than_days} days')
            """)
        else:
            # Delete all analysis results
            cursor.execute("DELETE FROM analysis_results")
            results_deleted = cursor.rowcount

            # Delete all analysis runs
            cursor.execute("DELETE FROM analysis_runs")

            # Delete all analysis errors
            cursor.execute("DELETE FROM analysis_errors")

        self.connection.commit()
        return results_deleted

    def purge_completed_bundles(self) -> int:
        """Purge completed/rejected bundles"""
        cursor = self.connection.cursor()

        cursor.execute("""
            DELETE FROM document_bundles
            WHERE status IN ('completed', 'rejected')
        """)

        self.connection.commit()
        return cursor.rowcount

    def purge_audit_trail(self, older_than_days: int | None = None) -> int:
        """
        Purge audit trail entries.

        Args:
            older_than_days: Delete entries older than N days (None = all)

        Returns:
            Number of entries deleted
        """
        cursor = self.connection.cursor()

        if older_than_days:
            cursor.execute(f"""
                DELETE FROM audit_trail
                WHERE created_at < datetime('now', '-{older_than_days} days')
            """)
        else:
            cursor.execute("DELETE FROM audit_trail")

        self.connection.commit()
        return cursor.rowcount

    # ==================== Analysis Status Window Methods ====================

    def get_recent_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get recent analysis runs with aggregated statistics.

        Args:
            limit: Maximum number of runs to return

        Returns:
            List of run dicts with keys:
                - run_id: Unique run identifier
                - timestamp: ISO format timestamp of run start
                - total_files: Number of files in run
                - analyzed: Number of newly analyzed files
                - cached: Number of cached files
                - errors: Number of failed files
                - duration_seconds: Run duration in seconds
                - status: 'success', 'partial', 'failed', or 'running'
        """
        cursor = self.connection.cursor()

        # Get runs from the new analysis_runs table
        cursor.execute(
            """
            SELECT
                run_id,
                total_files,
                analyzed,
                cached,
                errors,
                skipped,
                started_at as timestamp,
                completed_at,
                duration_ms,
                status
            FROM analysis_runs
            ORDER BY started_at DESC
            LIMIT ?
        """,
            (limit,),
        )

        rows = cursor.fetchall()

        runs = []
        for row in rows:
            run = dict(row)

            # Convert duration from ms to seconds
            if run["duration_ms"]:
                run["duration_seconds"] = run["duration_ms"] // 1000
            else:
                run["duration_seconds"] = 0

            # Remove duration_ms as we have duration_seconds
            del run["duration_ms"]

            # Determine status if not explicitly set
            if run["status"] == "running":
                run["status"] = "running"
            elif run["errors"] == 0:
                run["status"] = "success"
            elif run["errors"] == run["total_files"]:
                run["status"] = "failed"
            else:
                run["status"] = "partial"

            runs.append(run)

        return runs

    def get_analysis_statistics(self) -> dict[str, Any]:
        """
        Get comprehensive analysis statistics for the status window.

        Returns:
            Dict with keys:
                - total_files: Total analyzed files
                - total_runs: Total analysis runs
                - success_rate: Percentage of successful analyses
                - cache_hit_rate: Percentage of cached results
                - avg_confidence: Average confidence score
                - avg_processing_time_ms: Average processing time
                - total_processing_time_ms: Total processing time
                - cached_files: Number of cached files
                - failed_files: Number of failed analyses
        """
        cursor = self.connection.cursor()

        stats = {
            "total_files": 0,
            "total_runs": 0,
            "success_rate": 0.0,
            "cache_hit_rate": 0.0,
            "avg_confidence": 0.0,
            "avg_processing_time_ms": 0.0,
            "total_processing_time_ms": 0,
            "cached_files": 0,
            "failed_files": 0,
        }

        # Total files
        cursor.execute("SELECT COUNT(*) as count FROM analysis_results")
        stats["total_files"] = cursor.fetchone()["count"]

        if stats["total_files"] == 0:
            return stats

        # Cached files
        cursor.execute("SELECT COUNT(*) as count FROM analysis_results WHERE is_cached = 1")
        stats["cached_files"] = cursor.fetchone()["count"]

        # Cache hit rate
        stats["cache_hit_rate"] = (
            (stats["cached_files"] / stats["total_files"] * 100)
            if stats["total_files"] > 0
            else 0.0
        )

        # Average confidence (excluding nulls)
        cursor.execute(
            "SELECT AVG(confidence_score) as avg_conf FROM analysis_results WHERE confidence_score IS NOT NULL"
        )
        result = cursor.fetchone()
        stats["avg_confidence"] = result["avg_conf"] if result["avg_conf"] is not None else 0.0

        # Processing time stats
        cursor.execute(
            "SELECT AVG(processing_time_ms) as avg_time, SUM(processing_time_ms) as total_time FROM analysis_results"
        )
        result = cursor.fetchone()
        stats["avg_processing_time_ms"] = (
            result["avg_time"] if result["avg_time"] is not None else 0.0
        )
        stats["total_processing_time_ms"] = (
            result["total_time"] if result["total_time"] is not None else 0
        )

        # Success rate (assuming all records in DB are successful; failed ones would need error tracking)
        # For now, we assume 100% success rate for records that exist
        stats["success_rate"] = 100.0

        # Total runs
        runs = self.get_recent_runs(limit=1000)  # Get all runs
        stats["total_runs"] = len(runs)

        return stats

    def get_document_type_breakdown(self) -> dict[str, int]:
        """
        Get document type breakdown ordered by count.

        Returns:
            Dict mapping document type to count, ordered by count descending.
            Unknown/null types are labeled as "Unknown".
        """
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT
                COALESCE(document_type, 'Unknown') as doc_type,
                COUNT(*) as count
            FROM analysis_results
            GROUP BY doc_type
            ORDER BY count DESC
        """)

        rows = cursor.fetchall()
        breakdown = {row["doc_type"]: row["count"] for row in rows}

        return breakdown

    def get_failed_analyses(self) -> list[dict[str, Any]]:
        """
        Get list of failed analyses with error details.

        Note: Current schema doesn't track failures explicitly.
        This method can be enhanced when error tracking is added.

        Returns:
            List of failed analysis dicts with keys:
                - file_path: Path to failed file
                - error_message: Error description
                - analyzed_at: Timestamp
                - provider_name: LLM provider used
        """
        cursor = self.connection.cursor()

        # For now, we consider analyses with very low confidence or missing data as potential failures
        cursor.execute("""
            SELECT
                file_path,
                raw_response as error_message,
                analyzed_at,
                provider_name,
                confidence_score
            FROM analysis_results
            WHERE confidence_score IS NULL OR confidence_score < 0.3
            ORDER BY analyzed_at DESC
        """)

        rows = cursor.fetchall()
        failed = [dict(row) for row in rows]

        return failed

    # ==================== Analysis Run Tracking Methods ====================

    def start_analysis_run(self, run_id: str, total_files: int) -> None:
        """
        Start tracking a new analysis run.

        Args:
            run_id: Unique identifier for this run
            total_files: Total number of files to analyze
        """
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO analysis_runs (
                run_id, total_files, status
            ) VALUES (?, ?, 'running')
        """,
            (run_id, total_files),
        )
        self.connection.commit()

    def update_analysis_run(
        self,
        run_id: str,
        analyzed: int = 0,
        cached: int = 0,
        errors: int = 0,
        skipped: int = 0,
        status: str = "running",
    ) -> None:
        """
        Update analysis run statistics.

        Args:
            run_id: Run identifier
            analyzed: Number of newly analyzed files
            cached: Number of cached files
            errors: Number of errors
            skipped: Number of skipped files
            status: Run status (running, completed, failed)
        """
        cursor = self.connection.cursor()

        # If status is completed or failed, also set completed_at and duration
        if status in ("completed", "failed"):
            cursor.execute(
                """
                UPDATE analysis_runs
                SET analyzed = ?, cached = ?, errors = ?, skipped = ?,
                    status = ?, completed_at = CURRENT_TIMESTAMP,
                    duration_ms = CAST((julianday(CURRENT_TIMESTAMP) - julianday(started_at)) * 86400000 AS INTEGER)
                WHERE run_id = ?
            """,
                (analyzed, cached, errors, skipped, status, run_id),
            )
        else:
            cursor.execute(
                """
                UPDATE analysis_runs
                SET analyzed = ?, cached = ?, errors = ?, skipped = ?, status = ?
                WHERE run_id = ?
            """,
                (analyzed, cached, errors, skipped, status, run_id),
            )

        self.connection.commit()

    def save_analysis_error(
        self, run_id: str, file_path: str, error_message: str, error_type: str = "analysis_failed"
    ) -> None:
        """
        Save an analysis error record.

        Args:
            run_id: Run identifier
            file_path: Path to file that failed
            error_message: Error message
            error_type: Type of error
        """
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO analysis_errors (
                run_id, file_path, error_message, error_type
            ) VALUES (?, ?, ?, ?)
        """,
            (run_id, file_path, error_message, error_type),
        )
        self.connection.commit()

    def get_run_errors(self, run_id: str) -> list[dict[str, Any]]:
        """
        Get all errors for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            List of error dicts
        """
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT * FROM analysis_errors
            WHERE run_id = ?
            ORDER BY error_at DESC
        """,
            (run_id,),
        )

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    # ==================== Analysis Status Window Transformation Methods ====================

    def get_collection_summary(self) -> dict[str, Any]:
        """
        Get comprehensive collection summary for dashboard.

        Returns:
            Dict with keys:
                - files_detected: Total files in source directories
                - files_analyzed: Count from analysis_results
                - high_confidence_count: Count with confidence >= 0.8
                - pages_bundled: Count of pages in bundles
                - documents_archived: Count from archived_metadata
                - processing_speed: Pages per minute from last 100 analyses
                - eta_minutes: Estimated time remaining
                - avg_confidence: Average confidence score
                - error_rate: Percentage of errors
                - metadata_completeness: Per-field completion percentages
                - cache_hit_rate: Percentage of cached results
        """
        summary = {
            "files_detected": self._count_detected_files(),
            "files_analyzed": 0,
            "high_confidence_count": self._count_high_confidence(),
            "pages_bundled": self._count_bundled_pages(),
            "documents_archived": 0,
            "processing_speed": self._calculate_processing_speed(),
            "eta_minutes": 0,
            "avg_confidence": 0.0,
            "error_rate": 0.0,
            "metadata_completeness": self._get_metadata_completeness(),
            "cache_hit_rate": 0.0,
        }

        cursor = self.connection.cursor()

        # Files analyzed
        cursor.execute("SELECT COUNT(*) as count FROM analysis_results")
        summary["files_analyzed"] = cursor.fetchone()["count"]

        # Documents archived (from MetadataDB - table may not exist in analysis DB)
        try:
            cursor.execute("SELECT COUNT(*) as count FROM archived_metadata")
            summary["documents_archived"] = cursor.fetchone()["count"]
        except sqlite3.OperationalError:
            # Table doesn't exist (separate MetadataDB)
            summary["documents_archived"] = 0

        # Average confidence (excluding nulls)
        cursor.execute("""
            SELECT AVG(confidence_score) as avg_conf
            FROM analysis_results
            WHERE confidence_score IS NOT NULL
        """)
        result = cursor.fetchone()
        summary["avg_confidence"] = result["avg_conf"] if result["avg_conf"] is not None else 0.0

        # Cache hit rate
        if summary["files_analyzed"] > 0:
            cursor.execute("SELECT COUNT(*) as count FROM analysis_results WHERE is_cached = 1")
            cached_count = cursor.fetchone()["count"]
            summary["cache_hit_rate"] = (cached_count / summary["files_analyzed"]) * 100

        # Error rate (from analysis_errors table)
        cursor.execute("SELECT COUNT(DISTINCT file_path) as error_count FROM analysis_errors")
        error_count = cursor.fetchone()["error_count"]
        if summary["files_analyzed"] > 0:
            summary["error_rate"] = (error_count / summary["files_analyzed"]) * 100

        # Calculate ETA
        summary["eta_minutes"] = self._calculate_eta(
            summary["files_detected"], summary["files_analyzed"], summary["processing_speed"]
        )

        return summary

    def get_action_items(self) -> dict[str, int]:
        """
        Get counts for actionable items.

        Returns:
            Dict with keys:
                - pending_analysis: Files detected but not yet analyzed
                - pending_bundles: Bundles in 'suggested' status
                - failed_files: Files with analysis errors
                - unbundled_files: Analyzed files not in any bundle
        """
        cursor = self.connection.cursor()

        action_items = {
            "pending_analysis": 0,
            "pending_bundles": self._count_pending_bundles(),
            "failed_files": 0,
            "unbundled_files": 0,
        }

        # Pending analysis = detected - analyzed
        files_detected = self._count_detected_files()
        cursor.execute("SELECT COUNT(*) as count FROM analysis_results")
        files_analyzed = cursor.fetchone()["count"]
        action_items["pending_analysis"] = max(0, files_detected - files_analyzed)

        # Failed files (distinct file paths from errors)
        cursor.execute("SELECT COUNT(DISTINCT file_path) as count FROM analysis_errors")
        action_items["failed_files"] = cursor.fetchone()["count"]

        # Unbundled files = analyzed - bundled
        action_items["unbundled_files"] = max(0, files_analyzed - self._count_bundled_pages())

        return action_items

    def get_document_insights(self) -> dict[str, Any]:
        """
        Get document-level insights and statistics.

        Returns:
            Dict with keys:
                - total_documents: Total archived documents
                - total_archived_pages: Total pages in archived documents
                - avg_pages_per_doc: Average pages per document
                - bundle_acceptance_rate: Percentage of accepted bundles
                - pending_bundle_count: Number of pending bundles
                - type_distribution: Dict mapping document type to count
                - company_distribution: Dict mapping company to count
        """
        cursor = self.connection.cursor()

        insights = {
            "total_documents": 0,
            "total_archived_pages": 0,
            "avg_pages_per_doc": 0.0,
            "bundle_acceptance_rate": self._calc_bundle_acceptance_rate(),
            "pending_bundle_count": self._count_pending_bundles(),
            "type_distribution": self._get_type_distribution(),
            "company_distribution": self._get_company_distribution(),
        }

        # Total documents and pages from archived_metadata (table may not exist in analysis DB)
        try:
            cursor.execute("""
                SELECT
                    COUNT(*) as doc_count,
                    SUM(total_pages) as page_count
                FROM archived_metadata
            """)
            result = cursor.fetchone()
            insights["total_documents"] = result["doc_count"]
            insights["total_archived_pages"] = (
                result["page_count"] if result["page_count"] is not None else 0
            )
        except sqlite3.OperationalError:
            # Table doesn't exist (separate MetadataDB)
            pass

        # Average pages per document
        if insights["total_documents"] > 0:
            insights["avg_pages_per_doc"] = (
                insights["total_archived_pages"] / insights["total_documents"]
            )

        return insights

    def get_analyzed_pages_detailed(
        self, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Get all analysis results with full metadata for grid display.

        Args:
            filters: Optional filters dict with keys:
                - company: Filter by company name
                - document_type: Filter by document type
                - confidence_min: Minimum confidence score
                - date_from: Filter by analyzed_at >= date
                - date_to: Filter by analyzed_at <= date
                - search_text: Search in file_path
                - status: Filter by status (analyzed, cached, failed)

        Returns:
            List of analysis result dicts with 18 fields:
                - id, file_path, file_hash, provider_name, model_name
                - document_type, company, document_date, page_number, total_pages
                - belongs_to_same_doc, confidence_score, rotation_needed, suggested_rotation
                - rotation_confidence, analyzed_at, processing_time_ms, is_cached
        """
        cursor = self.connection.cursor()

        query = """
            SELECT
                id, file_path, file_hash, provider_name, model_name,
                document_type, company, document_date, page_number, total_pages,
                belongs_to_same_doc, confidence_score, rotation_needed, suggested_rotation,
                rotation_confidence, analyzed_at, processing_time_ms, is_cached
            FROM analysis_results
            WHERE 1=1
        """
        params = []

        if filters:
            if filters.get("company"):
                query += " AND company LIKE ?"
                params.append(f"%{filters['company']}%")

            if filters.get("document_type"):
                query += " AND document_type LIKE ?"
                params.append(f"%{filters['document_type']}%")

            if filters.get("confidence_min") is not None:
                query += " AND confidence_score >= ?"
                params.append(filters["confidence_min"])

            if filters.get("date_from"):
                query += " AND analyzed_at >= ?"
                params.append(filters["date_from"])

            if filters.get("date_to"):
                query += " AND analyzed_at <= ?"
                params.append(filters["date_to"])

            if filters.get("search_text"):
                query += " AND file_path LIKE ?"
                params.append(f"%{filters['search_text']}%")

            if filters.get("status") == "cached":
                query += " AND is_cached = 1"
            elif filters.get("status") == "analyzed":
                query += " AND is_cached = 0"
            elif filters.get("status") == "failed":
                query += " AND id IN (SELECT DISTINCT ae.file_path FROM analysis_errors ae)"

        query += " ORDER BY analyzed_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    # ==================== Helper Methods for Calculations ====================

    def _count_detected_files(self) -> int:
        """
        Count total files detected in all active source directories.

        Returns:
            Total count of image files (.png, .jpg, .jpeg, .tiff, .tif)
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT directory_path FROM source_directories WHERE is_active = 1")
        directories = [row["directory_path"] for row in cursor.fetchall()]

        total_files = 0
        valid_extensions = {".png", ".jpg", ".jpeg", ".tiff", ".tif"}

        for directory in directories:
            if os.path.exists(directory):
                try:
                    for filename in os.listdir(directory):
                        _, ext = os.path.splitext(filename)
                        if ext.lower() in valid_extensions:
                            total_files += 1
                except (PermissionError, OSError):
                    # Skip directories we can't access
                    continue

        return total_files

    def _count_high_confidence(self) -> int:
        """
        Count analysis results with confidence >= 0.8.

        Returns:
            Count of high confidence analyses
        """
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM analysis_results
            WHERE confidence_score >= 0.8
        """)
        return cursor.fetchone()["count"]

    def _count_bundled_pages(self) -> int:
        """
        Count total pages that are part of any bundle.

        Returns:
            Count of bundled pages
        """
        cursor = self.connection.cursor()

        # Sum of total_pages from all bundles (not status='rejected')
        cursor.execute("""
            SELECT SUM(total_pages) as total
            FROM document_bundles
            WHERE status != 'rejected'
        """)
        result = cursor.fetchone()
        return result["total"] if result["total"] is not None else 0

    def _calculate_processing_speed(self) -> float:
        """
        Calculate processing speed from last 100 analyses.

        Returns:
            Pages per minute, or 0 if insufficient data
        """
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT AVG(processing_time_ms) as avg_time
            FROM (
                SELECT processing_time_ms
                FROM analysis_results
                WHERE processing_time_ms IS NOT NULL
                ORDER BY analyzed_at DESC
                LIMIT 100
            )
        """)
        result = cursor.fetchone()

        if result["avg_time"] is None or result["avg_time"] == 0:
            return 0.0

        # Convert ms per page to pages per minute
        avg_time_sec = result["avg_time"] / 1000.0
        pages_per_minute = 60.0 / avg_time_sec if avg_time_sec > 0 else 0.0

        return pages_per_minute

    def _calculate_eta(
        self, files_detected: int, files_analyzed: int, processing_speed: float
    ) -> float:
        """
        Calculate estimated time remaining in minutes.

        Args:
            files_detected: Total files detected
            files_analyzed: Files already analyzed
            processing_speed: Pages per minute

        Returns:
            Estimated minutes remaining, or 0 if N/A
        """
        pending = max(0, files_detected - files_analyzed)

        if pending == 0 or processing_speed == 0:
            return 0.0

        return pending / processing_speed

    def _get_metadata_completeness(self) -> dict[str, float]:
        """
        Calculate metadata completeness percentages per field.

        Returns:
            Dict mapping field name to completion percentage
        """
        cursor = self.connection.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM analysis_results")
        total = cursor.fetchone()["total"]

        if total == 0:
            return {
                "company": 0.0,
                "document_type": 0.0,
                "document_date": 0.0,
                "page_number": 0.0,
                "total_pages": 0.0,
            }

        completeness = {}
        fields = ["company", "document_type", "document_date", "page_number", "total_pages"]

        for field in fields:
            cursor.execute(f"""
                SELECT COUNT(*) as count
                FROM analysis_results
                WHERE {field} IS NOT NULL AND {field} != ''
            """)
            count = cursor.fetchone()["count"]
            completeness[field] = (count / total) * 100

        return completeness

    def _count_pending_bundles(self) -> int:
        """
        Count bundles with status='suggested'.

        Returns:
            Count of pending bundles
        """
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM document_bundles
            WHERE status = 'suggested'
        """)
        return cursor.fetchone()["count"]

    def _calc_bundle_acceptance_rate(self) -> float:
        """
        Calculate percentage of accepted bundles.

        Returns:
            Acceptance rate percentage, or 0 if no bundles
        """
        cursor = self.connection.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM document_bundles")
        total = cursor.fetchone()["total"]

        if total == 0:
            return 0.0

        cursor.execute("""
            SELECT COUNT(*) as accepted
            FROM document_bundles
            WHERE status = 'accepted'
        """)
        accepted = cursor.fetchone()["accepted"]

        return (accepted / total) * 100

    def _get_type_distribution(self) -> dict[str, int]:
        """
        Get document type distribution from analysis results.

        Returns:
            Dict mapping document type to count, ordered by count descending
        """
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT
                COALESCE(document_type, 'Unknown') as doc_type,
                COUNT(*) as count
            FROM analysis_results
            GROUP BY doc_type
            ORDER BY count DESC
        """)

        rows = cursor.fetchall()
        return {row["doc_type"]: row["count"] for row in rows}

    def _get_company_distribution(self) -> dict[str, int]:
        """
        Get company distribution from analysis results.

        Returns:
            Dict mapping company name to count, ordered by count descending
        """
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT
                COALESCE(company, 'Unknown') as company_name,
                COUNT(*) as count
            FROM analysis_results
            GROUP BY company_name
            ORDER BY count DESC
        """)

        rows = cursor.fetchall()
        return {row["company_name"]: row["count"] for row in rows}

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
    # Test the analysis database
    db = AnalysisDB("test_analysis.db")

    # Test adding a provider
    db.add_provider(
        provider_name="ollama",
        provider_type="ollama",
        config={"base_url": "http://localhost:11434", "timeout": 300},
        default_model="qwen3-vl:latest",
        available_models=["qwen3-vl:latest", "llava:latest"],
    )

    db.set_active_provider("ollama")

    # Test adding source directory
    db.add_source_directory("C:\\Users\\test\\Pictures\\Scans")

    # Test saving analysis
    test_analysis = {
        "document_type": "Invoice",
        "company": "Acme Corp",
        "page_number": 1,
        "total_pages": 3,
        "belongs_to_same_doc": True,
        "confidence_score": 0.95,
        "rotation_needed": False,
    }

    db.save_analysis(
        file_path="test.png",
        file_hash="abc123",
        provider_name="ollama",
        model_name="qwen3-vl:latest",
        analysis_data=test_analysis,
        raw_response="Full LLM response here",
        processing_time_ms=1500,
    )

    # Test statistics
    print("Extended statistics:", db.get_extended_statistics())

    db.close()
    print("Test completed successfully!")
