"""
Rotation repository for managing image rotation preferences.

Simplified CRUD operations for rotation tracking across metadata and analysis databases.
"""

from typing import cast

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

        # Get or create image_file entry
        image_file_id = self.conn.fetch_one(
            "SELECT id FROM image_files WHERE file_path = ?",
            (file_path,),
        )

        if not image_file_id:
            # Register the file first
            file_hash = self._compute_file_hash(file_path)
            file_size = os.path.getsize(file_path)
            file_mtime = os.path.getmtime(file_path)
            directory_path = os.path.dirname(file_path)
            filename = os.path.basename(file_path)

            self.conn.execute(
                """
                INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (file_path, file_hash, directory_path, filename, file_size, file_mtime),
            )
            image_file_id_result = self.conn.fetch_one("SELECT last_insert_rowid()")
            image_file_id = image_file_id_result[0] if image_file_id_result else None
        else:
            image_file_id = image_file_id[0]

        # Insert or update metadata with rotation
        self.conn.execute(
            """
            INSERT INTO metadata (image_file_id, rotation)
            VALUES (?, ?)
            ON CONFLICT(image_file_id) DO UPDATE SET
                rotation = ?,
                updated_at = CURRENT_TIMESTAMP
        """,
            (image_file_id, rotation_degrees, rotation_degrees),
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
            """
            SELECT m.rotation
            FROM metadata m
            JOIN image_files img ON m.image_file_id = img.id
            WHERE img.file_path = ?
        """,
            (file_path,),
        )

        if result and result[0] is not None:
            return cast(int, result[0])

        return 0

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
