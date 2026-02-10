"""
Repository for bundle_images junction table.

Manages the many-to-many relationship between bundles and images.
"""

from typing import Any

from db.connection import DatabaseConnection


class BundleImagesRepository:
    """Manages bundle-to-image mappings."""

    def __init__(self, conn: DatabaseConnection):
        """
        Initialize repository.

        Args:
            conn: Database connection
        """
        self.conn = conn

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
        self.conn.commit()
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
        self.conn.commit()

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
        self.conn.commit()

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
        self.conn.commit()

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
