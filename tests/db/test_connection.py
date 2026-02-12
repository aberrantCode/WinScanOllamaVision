"""
Tests for DatabaseConnection helper methods.
"""

import json
import os
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

from db.connection import DatabaseConnection, get_appdata_db_path, parse_json_fields


class TestDatabaseConnection:
    """Tests for DatabaseConnection class"""

    @pytest.fixture
    def temp_db_path(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.remove(db_path)

    @pytest.fixture
    def conn(self, temp_db_path):
        connection = DatabaseConnection(temp_db_path)
        # Create test table
        connection.execute("""
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT,
                data TEXT
            )
        """)
        connection.commit()
        yield connection
        connection.close()

    def test_from_appdata_creates_connection(self):
        # Act
        conn = DatabaseConnection.from_appdata("test.db")

        # Assert
        assert conn.connection is not None
        assert "WinScanLLM" in conn.db_path
        conn.close()

        # Cleanup
        if os.path.exists(conn.db_path):
            os.remove(conn.db_path)

    def test_execute_runs_query(self, conn):
        # Act
        cursor = conn.execute("INSERT INTO test_table (name) VALUES (?)", ("Test",))

        # Assert
        assert cursor is not None
        conn.commit()

    def test_execute_many_inserts_multiple(self, conn):
        # Arrange
        data = [("Name1",), ("Name2",), ("Name3",)]

        # Act
        conn.execute_many("INSERT INTO test_table (name) VALUES (?)", data)
        conn.commit()

        # Assert
        cursor = conn.execute("SELECT COUNT(*) FROM test_table")
        count = cursor.fetchone()[0]
        assert count == 3

    def test_fetch_one_returns_single_row(self, conn):
        # Arrange
        conn.execute("INSERT INTO test_table (name) VALUES (?)", ("Test",))
        conn.commit()

        # Act
        row = conn.fetch_one("SELECT name FROM test_table WHERE name = ?", ("Test",))

        # Assert
        assert row is not None
        assert row["name"] == "Test"

    def test_fetch_one_returns_none_when_empty(self, conn):
        # Act
        row = conn.fetch_one("SELECT name FROM test_table WHERE name = ?", ("Missing",))

        # Assert
        assert row is None

    def test_fetch_all_returns_all_rows(self, conn):
        # Arrange
        conn.execute_many("INSERT INTO test_table (name) VALUES (?)", [("A",), ("B",), ("C",)])
        conn.commit()

        # Act
        rows = conn.fetch_all("SELECT name FROM test_table ORDER BY name")

        # Assert
        assert len(rows) == 3
        assert rows[0]["name"] == "A"

    def test_fetch_one_dict_with_json_parsing(self, conn):
        # Arrange
        json_data = json.dumps({"key": "value"})
        conn.execute("INSERT INTO test_table (name, data) VALUES (?, ?)", ("Test", json_data))
        conn.commit()

        # Act
        row = conn.fetch_one_dict(
            "SELECT * FROM test_table WHERE name = ?", ("Test",), json_fields=["data"]
        )

        # Assert
        assert row["data"] == {"key": "value"}

    def test_fetch_one_dict_handles_invalid_json(self, conn):
        # Arrange
        conn.execute("INSERT INTO test_table (name, data) VALUES (?, ?)", ("Test", "invalid json"))
        conn.commit()

        # Act
        row = conn.fetch_one_dict(
            "SELECT * FROM test_table WHERE name = ?", ("Test",), json_fields=["data"]
        )

        # Assert - should keep as string when JSON parsing fails
        assert row["data"] == "invalid json"

    def test_fetch_all_dicts_with_json_parsing(self, conn):
        # Arrange
        conn.execute_many(
            "INSERT INTO test_table (name, data) VALUES (?, ?)",
            [
                ("Test1", json.dumps({"key": "value1"})),
                ("Test2", json.dumps({"key": "value2"})),
            ],
        )
        conn.commit()

        # Act
        rows = conn.fetch_all_dicts("SELECT * FROM test_table ORDER BY name", json_fields=["data"])

        # Assert
        assert len(rows) == 2
        assert rows[0]["data"] == {"key": "value1"}
        assert rows[1]["data"] == {"key": "value2"}

    def test_commit_saves_changes(self, conn):
        # Arrange
        conn.execute("INSERT INTO test_table (name) VALUES (?)", ("Test",))

        # Act
        conn.commit()

        # Assert - create new connection to verify persistence
        new_conn = DatabaseConnection(conn.db_path)
        row = new_conn.fetch_one("SELECT name FROM test_table WHERE name = ?", ("Test",))
        assert row is not None
        new_conn.close()

    def test_rollback_cancels_changes(self, conn):
        # Arrange
        conn.execute("INSERT INTO test_table (name) VALUES (?)", ("Test",))

        # Act
        conn.rollback()

        # Assert
        row = conn.fetch_one("SELECT name FROM test_table WHERE name = ?", ("Test",))
        assert row is None

    def test_context_manager_commits_on_success(self, temp_db_path):
        # Act
        with DatabaseConnection(temp_db_path) as conn:
            conn.execute("""
                CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)
            """)
            conn.execute("INSERT INTO test (name) VALUES (?)", ("Test",))

        # Assert - verify data was committed
        verify_conn = DatabaseConnection(temp_db_path)
        row = verify_conn.fetch_one("SELECT name FROM test WHERE name = ?", ("Test",))
        assert row is not None
        verify_conn.close()

    def test_context_manager_rollbacks_on_error(self, temp_db_path):
        # Arrange & Act
        try:
            with DatabaseConnection(temp_db_path) as conn:
                conn.execute("""
                    CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)
                """)
                conn.execute("INSERT INTO test (name) VALUES (?)", ("Test",))
                # Force error
                raise ValueError("Test error")
        except ValueError:
            pass

        # Assert - verify data was rolled back (table might exist but no data)
        verify_conn = DatabaseConnection(temp_db_path)
        try:
            row = verify_conn.fetch_one("SELECT COUNT(*) FROM test")
            # Table exists but should be empty
            assert row[0] == 0
        except sqlite3.OperationalError:
            # Table doesn't exist - also acceptable
            pass
        verify_conn.close()

    def test_connection_handles_locked_database(self):
        """Test that connection handles locked database error"""
        # Arrange
        with patch("sqlite3.connect") as mock_connect:
            mock_connect.side_effect = sqlite3.OperationalError("database is locked")

            # Act & Assert
            with pytest.raises(sqlite3.OperationalError, match="Database is locked"):
                DatabaseConnection("/test/locked.db")

    def test_connection_handles_readonly_directory(self):
        """Test that connection handles permission errors on database file"""
        # Arrange
        with patch("sqlite3.connect") as mock_connect:
            mock_connect.side_effect = sqlite3.OperationalError("unable to open database file")

            # Act & Assert
            with pytest.raises(sqlite3.OperationalError, match="Cannot open database"):
                DatabaseConnection("/readonly/test.db")

    def test_connection_handles_general_database_error(self):
        """Test that connection handles general database errors"""
        # Arrange
        with patch("sqlite3.connect") as mock_connect:
            mock_connect.side_effect = sqlite3.Error("Some database error")

            # Act & Assert
            with pytest.raises(sqlite3.Error, match="Failed to connect to database"):
                DatabaseConnection("/test/error.db")


def test_get_appdata_db_path_creates_directory():
    # Act
    path = get_appdata_db_path()

    # Assert
    assert "WinScanLLM" in path
    assert path.endswith("metadata.db")
    assert os.path.exists(os.path.dirname(path))


def test_get_appdata_db_path_accepts_custom_filename():
    # Act
    path = get_appdata_db_path("custom.db")

    # Assert
    assert path.endswith("custom.db")


def test_parse_json_fields():
    # Arrange
    row_dict = {
        "id": 1,
        "name": "Test",
        "data": json.dumps({"key": "value"}),
        "other": "plain text",
    }

    # Act
    result = parse_json_fields(row_dict, ["data"])

    # Assert
    assert result["data"] == {"key": "value"}
    assert result["other"] == "plain text"
    # Original should be unchanged (immutable)
    assert isinstance(row_dict["data"], str)


def test_parse_json_fields_handles_invalid_json():
    # Arrange
    row_dict = {"data": "invalid json"}

    # Act
    result = parse_json_fields(row_dict, ["data"])

    # Assert - should keep as-is
    assert result["data"] == "invalid json"
