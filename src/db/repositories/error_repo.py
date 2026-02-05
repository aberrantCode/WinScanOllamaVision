"""Error repository for managing analysis errors."""

from typing import Any

from db.connection import DatabaseConnection


class ErrorRepository:
    """Manages analysis error tracking."""

    def __init__(self, conn: DatabaseConnection):
        """Initialize error repository."""
        self.conn = conn

    def save_error(
        self, file_path: str, error_message: str, error_type: str = "analysis_failed"
    ) -> None:
        """Save an analysis error record.

        Args:
            file_path: Path to the file that encountered an error
            error_message: Description of the error
            error_type: Type of error (default: 'analysis_failed')
        """
        self.conn.execute(
            "INSERT INTO analysis_errors (file_path, error_message, error_type) VALUES (?, ?, ?)",
            (file_path, error_message, error_type),
        )
        self.conn.commit()

    def get_all_errors(self) -> list[dict[str, Any]]:
        """Get all error records.

        Returns:
            List of error dictionaries with keys: id, file_path, error_message,
            error_type, error_at
        """
        return self.conn.fetch_all_dicts(
            "SELECT id, file_path, error_message, error_type, error_at FROM analysis_errors ORDER BY error_at DESC"
        )

    def get_error_count(self) -> int:
        """Get total count of errors.

        Returns:
            Total number of error records
        """
        result = self.conn.fetch_one("SELECT COUNT(*) FROM analysis_errors")
        return result[0] if result else 0

    def clear_error(self, file_path: str) -> None:
        """Clear error record for a specific file.

        Args:
            file_path: Path to the file whose error should be cleared
        """
        self.conn.execute("DELETE FROM analysis_errors WHERE file_path = ?", (file_path,))
        self.conn.commit()
