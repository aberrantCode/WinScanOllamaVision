"""
Database connection management and utilities.

Provides shared infrastructure for all database repositories.

Thread-safety:
    DatabaseConnection uses ``check_same_thread=False`` so a single
    connection can be shared across Qt worker threads.  All public
    methods that touch the underlying ``sqlite3.Connection`` are
    serialised with a ``threading.RLock`` so concurrent callers are
    safe.  The lock is re-entrant, allowing higher-level helpers
    (e.g. ``fetch_one``) to call ``execute`` without deadlocking.
"""

import contextlib
import json
import os
import sqlite3
import threading
from typing import Any, cast

from services.logging_service import get_logger

logger = get_logger()


class DatabaseConnection:
    """Manages SQLite connection lifecycle with helper methods.

    Thread-safety
    -------------
    All public methods that access the underlying ``sqlite3.Connection``
    are protected by a re-entrant lock (``threading.RLock``).  The
    connection is opened with ``check_same_thread=False`` so it can be
    used from any thread; the lock ensures only one thread executes a
    database operation at a time.
    """

    def __init__(self, db_path: str):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.connection: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        self._connect()

    def _connect(self):
        """Establish database connection with row factory and enable foreign keys."""
        self.connection = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30.0,
        )
        self.connection.row_factory = sqlite3.Row
        # Enable foreign key constraints
        self.connection.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def from_appdata(cls, filename: str = "metadata.db") -> "DatabaseConnection":
        """
        Create connection to database in AppData directory.

        Args:
            filename: Database filename

        Returns:
            DatabaseConnection instance
        """
        db_path = get_appdata_db_path(filename)
        return cls(db_path)

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Execute query and return cursor.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Cursor with results
        """
        # Log SQL statement at DEBUG level
        if params:
            logger.debug(f"SQL: {query} | Params: {params}")
        else:
            logger.debug(f"SQL: {query}")

        with self._lock:
            if self.connection is None:
                raise RuntimeError("Database connection not initialized")
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            return cursor

    def execute_many(self, query: str, params_list: list[tuple]) -> None:
        """
        Execute query with multiple parameter sets.

        Args:
            query: SQL query string
            params_list: List of parameter tuples
        """
        # Log SQL statement at DEBUG level
        logger.debug(f"SQL (batch): {query} | Batch size: {len(params_list)}")

        with self._lock:
            if self.connection is None:
                raise RuntimeError("Database connection not initialized")
            cursor = self.connection.cursor()
            cursor.executemany(query, params_list)

    def fetch_one(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        """
        Fetch single row.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Row object or None
        """
        with self._lock:
            cursor = self.execute(query, params)
            return cast(sqlite3.Row | None, cursor.fetchone())

    def fetch_all(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """
        Fetch all rows.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of Row objects
        """
        with self._lock:
            cursor = self.execute(query, params)
            return cursor.fetchall()

    def fetch_one_dict(
        self, query: str, params: tuple = (), json_fields: list[str] | None = None
    ) -> dict[str, Any] | None:
        """
        Fetch single row as dictionary with optional JSON parsing.

        Args:
            query: SQL query string
            params: Query parameters
            json_fields: List of field names to parse as JSON

        Returns:
            Dictionary or None
        """
        with self._lock:
            row = self.fetch_one(query, params)
            if not row:
                return None

            result = dict(row)

        # Parse JSON fields outside the lock (pure dict manipulation)
        if json_fields:
            for field in json_fields:
                if result.get(field):
                    with contextlib.suppress(json.JSONDecodeError, TypeError):
                        result[field] = json.loads(result[field])

        return result

    def fetch_all_dicts(
        self, query: str, params: tuple = (), json_fields: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """
        Fetch all rows as dictionaries with optional JSON parsing.

        Args:
            query: SQL query string
            params: Query parameters
            json_fields: List of field names to parse as JSON

        Returns:
            List of dictionaries
        """
        with self._lock:
            rows = self.fetch_all(query, params)
            raw_results = [dict(row) for row in rows]

        # Parse JSON fields outside the lock (pure dict manipulation)
        results = []
        for result in raw_results:
            if json_fields:
                for field in json_fields:
                    if result.get(field):
                        with contextlib.suppress(json.JSONDecodeError, TypeError):
                            result[field] = json.loads(result[field])
            results.append(result)

        return results

    def commit(self):
        """Commit current transaction."""
        with self._lock:
            if self.connection is None:
                raise RuntimeError("Database connection not initialized")
            self.connection.commit()

    def rollback(self):
        """Rollback current transaction."""
        with self._lock:
            if self.connection is None:
                raise RuntimeError("Database connection not initialized")
            self.connection.rollback()

    def close(self):
        """Close database connection."""
        with self._lock:
            if self.connection:
                self.connection.close()
                self.connection = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic commit/rollback."""
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()


def get_appdata_db_path(filename: str = "metadata.db") -> str:
    """
    Get standard AppData database path.

    Args:
        filename: Database filename

    Returns:
        Full path to database file in AppData/WinScanLLM
    """
    appdata_root = os.getenv("APPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Roaming"))
    appdata_dir = os.path.join(appdata_root, "WinScanLLM")

    # Ensure directory exists
    os.makedirs(appdata_dir, exist_ok=True)

    return os.path.join(appdata_dir, filename)


def parse_json_fields(row_dict: dict, field_names: list[str]) -> dict:
    """
    Parse JSON fields in a row dictionary (immutable - returns new dict).

    Args:
        row_dict: Dictionary with potential JSON fields
        field_names: List of field names to parse as JSON

    Returns:
        New dictionary with parsed JSON fields
    """
    result = dict(row_dict)

    for field in field_names:
        if result.get(field):
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                result[field] = json.loads(result[field])

    return result
