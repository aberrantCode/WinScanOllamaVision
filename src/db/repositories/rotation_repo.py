"""
Rotation repository for managing image rotation preferences.

Simplified CRUD operations for rotation tracking across metadata and analysis databases.
"""

from db.connection import DatabaseConnection


class RotationRepository:
    """Manages rotation preference persistence."""

    def __init__(self, conn: DatabaseConnection):
        """
        Initialize rotation repository.

        Args:
            conn: Database connection
        """
        self.conn = conn

    def save(self, file_path: str, rotation_degrees: int) -> None:
        """
        Save rotation angle for a file in metadata table.

        Rotation is display-only and never modifies the source file.

        Args:
            file_path: Absolute path to the image file
            rotation_degrees: Rotation angle (0, 90, 180, 270)
        """
        import os

        # Normalize rotation to 0-359 range
        rotation_degrees = rotation_degrees % 360

        # Compute file properties
        file_hash = self._compute_file_hash(file_path)
        file_size = os.path.getsize(file_path)
        file_mtime = os.path.getmtime(file_path)

        self.conn.execute(
            """
            INSERT INTO active_metadata (file_path, file_hash, file_size, file_mtime, rotation_degrees)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                rotation_degrees = ?,
                updated_at = CURRENT_TIMESTAMP
        """,
            (
                file_path,
                file_hash,
                file_size,
                file_mtime,
                rotation_degrees,
                rotation_degrees,
            ),
        )
        self.conn.commit()

    def get(self, file_path: str) -> int:
        """
        Get stored rotation angle for a file.

        Args:
            file_path: Absolute path to the image file

        Returns:
            Rotation angle in degrees (0, 90, 180, or 270), or 0 if not found
        """
        result = self.conn.fetch_one(
            "SELECT rotation_degrees FROM active_metadata WHERE file_path = ?",
            (file_path,),
        )

        if result and result[0] is not None:
            return result[0]

        return 0

    def save_preference(self, file_path: str, rotation_degrees: int, rotation_source: str) -> None:
        """
        Save rotation preference for a file in analysis table.

        Args:
            file_path: Path to file
            rotation_degrees: Rotation in degrees (90, 180, 270)
            rotation_source: Source of rotation (ai_suggestion, manual)
        """
        self.conn.execute(
            """
            INSERT OR REPLACE INTO rotation_preferences (
                file_path, rotation_degrees, rotation_source, applied_at
            ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (file_path, rotation_degrees, rotation_source),
        )
        self.conn.commit()

    @staticmethod
    def _compute_file_hash(file_path: str) -> str:
        """
        Compute SHA-256 hash of file.

        Args:
            file_path: Path to file

        Returns:
            Hex string of file hash
        """
        import hashlib

        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
