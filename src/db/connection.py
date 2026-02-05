"""
Database connection management and utilities.

Provides shared infrastructure for all database repositories.
"""

import contextlib
import json
import os
import sqlite3
from typing import Any


class DatabaseConnection:
    """Manages SQLite connection lifecycle with helper methods."""

    def __init__(self, db_path: str):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.connection = None
        self._connect()

    def _connect(self):
        """Establish database connection with row factory."""
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row

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
        cursor = self.execute(query, params)
        return cursor.fetchone()

    def fetch_all(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """
        Fetch all rows.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of Row objects
        """
        cursor = self.execute(query, params)
        return cursor.fetchall()

    def fetch_one_dict(
        self, query: str, params: tuple = (), json_fields: list[str] = None
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
        row = self.fetch_one(query, params)
        if not row:
            return None

        result = dict(row)

        # Parse JSON fields
        if json_fields:
            for field in json_fields:
                if result.get(field):
                    with contextlib.suppress(json.JSONDecodeError, TypeError):
                        result[field] = json.loads(result[field])

        return result

    def fetch_all_dicts(
        self, query: str, params: tuple = (), json_fields: list[str] = None
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
        rows = self.fetch_all(query, params)
        results = []

        for row in rows:
            result = dict(row)

            # Parse JSON fields
            if json_fields:
                for field in json_fields:
                    if result.get(field):
                        with contextlib.suppress(json.JSONDecodeError, TypeError):
                            result[field] = json.loads(result[field])

            results.append(result)

        return results

    def commit(self):
        """Commit current transaction."""
        self.connection.commit()

    def rollback(self):
        """Rollback current transaction."""
        self.connection.rollback()

    def close(self):
        """Close database connection."""
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
