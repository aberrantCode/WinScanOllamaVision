"""
Repository for bundle_images junction table.

Manages the many-to-many relationship between bundles and images.
"""

import logging
import sqlite3
from typing import TYPE_CHECKING, Any

from db.connection import DatabaseConnection

if TYPE_CHECKING:
    from services.logging_service import get_logger
else:
    get_logger = None

logger: logging.Logger | None = None


class BundleImagesRepository:
    """Manages bundle-to-image mappings."""

    def __init__(self, conn: DatabaseConnection):
        """
        Initialize repository.

        Args:
            conn: Database connection
        """
        self.conn = conn

    def _get_logger(self) -> logging.Logger:
        """Get logger instance (lazy initialization)."""
        global logger
        if logger is None:
            from services.logging_service import get_logger as _get_logger

            logger = _get_logger()
        return logger

    def add_image(self, bundle_id: int, image_file_id: int, sequence_order: int) -> int:
        """
        Add an image to a bundle at a specific sequence position.

        Args:
            bundle_id: Bundle ID
            image_file_id: Image file ID
            sequence_order: Sequence position in the bundle (1-indexed)

        Returns:
            ID of the created record
        """
        cursor = self.conn.execute(
            """
            INSERT INTO bundle_images (bundle_id, image_file_id, sequence_order)
            VALUES (?, ?, ?)
            """,
            (bundle_id, image_file_id, sequence_order),
        )
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[BUNDLE IMAGES REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            self._get_logger().error(f"[BUNDLE IMAGES REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to add image to bundle: {e}") from e
        return cursor.lastrowid if cursor.lastrowid else 0

    def add_images_bulk(self, bundle_id: int, image_file_ids: list[int]) -> None:
        """
        Add multiple images to a bundle in order.

        Args:
            bundle_id: Bundle ID
            image_file_ids: List of image file IDs in desired order
        """
        for idx, image_file_id in enumerate(image_file_ids, start=1):
            self.conn.execute(
                """
                INSERT INTO bundle_images (bundle_id, image_file_id, sequence_order)
                VALUES (?, ?, ?)
                """,
                (bundle_id, image_file_id, idx),
            )
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[BUNDLE IMAGES REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            self._get_logger().error(f"[BUNDLE IMAGES REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to add images to bundle: {e}") from e

    def get_images_for_bundle(self, bundle_id: int) -> list[dict[str, Any]]:
        """
        Get all images in a bundle, ordered by sequence.

        Args:
            bundle_id: Bundle ID

        Returns:
            List of image records with sequence order
        """
        return self.conn.fetch_all_dicts(
            """
            SELECT
                bi.id,
                bi.sequence_order,
                img.*
            FROM bundle_images bi
            INNER JOIN image_files img ON bi.image_file_id = img.id
            WHERE bi.bundle_id = ?
            ORDER BY bi.sequence_order
            """,
            (bundle_id,),
        )

    def get_bundles_for_image(self, image_file_id: int) -> list[dict[str, Any]]:
        """
        Get all bundles that contain a specific image.

        Args:
            image_file_id: Image file ID

        Returns:
            List of bundle records
        """
        return self.conn.fetch_all_dicts(
            """
            SELECT
                b.*,
                bi.sequence_order
            FROM bundle_images bi
            INNER JOIN document_bundles b ON bi.bundle_id = b.id
            WHERE bi.image_file_id = ?
            ORDER BY b.created_at DESC
            """,
            (image_file_id,),
        )

    def remove_image(self, bundle_id: int, image_file_id: int) -> None:
        """
        Remove an image from a bundle.

        Args:
            bundle_id: Bundle ID
            image_file_id: Image file ID to remove
        """
        self.conn.execute(
            "DELETE FROM bundle_images WHERE bundle_id = ? AND image_file_id = ?",
            (bundle_id, image_file_id),
        )
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[BUNDLE IMAGES REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            self._get_logger().error(f"[BUNDLE IMAGES REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to remove image from bundle: {e}") from e

    def remove_all_images(self, bundle_id: int) -> None:
        """
        Remove all images from a bundle.

        Args:
            bundle_id: Bundle ID
        """
        self.conn.execute(
            "DELETE FROM bundle_images WHERE bundle_id = ?",
            (bundle_id,),
        )
        try:
            self.conn.commit()
        except sqlite3.OperationalError as e:
            self._get_logger().error(f"[BUNDLE IMAGES REPO] Database locked: {e}")
            self.conn.rollback()
            raise sqlite3.OperationalError("Database is locked. Try again.") from e
        except sqlite3.Error as e:
            self._get_logger().error(f"[BUNDLE IMAGES REPO] Database error: {e}")
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to remove all images from bundle: {e}") from e

    def reorder_images(self, bundle_id: int, image_file_ids: list[int]) -> None:
        """
        Reorder images in a bundle.

        Args:
            bundle_id: Bundle ID
            image_file_ids: List of image file IDs in new order
        """
        # Remove existing mappings
        self.remove_all_images(bundle_id)

        # Add back in new order
        self.add_images_bulk(bundle_id, image_file_ids)

    def get_image_count(self, bundle_id: int) -> int:
        """
        Get the number of images in a bundle.

        Args:
            bundle_id: Bundle ID

        Returns:
            Number of images
        """
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM bundle_images WHERE bundle_id = ?",
            (bundle_id,),
        )
        result = cursor.fetchone()
        return int(result[0]) if result else 0
