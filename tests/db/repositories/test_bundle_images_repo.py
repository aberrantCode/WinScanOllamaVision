"""Tests for BundleImagesRepository"""

import sqlite3
from datetime import datetime
from unittest.mock import patch

import pytest

from db.connection import DatabaseConnection
from db.repositories.bundle_images_repo import BundleImagesRepository
from db.schema import create_all_tables


@pytest.fixture
def db_conn(tmp_path):
    """Create a temporary database connection for testing."""
    db_path = tmp_path / "test_bundle_images.db"
    conn = DatabaseConnection(str(db_path))
    create_all_tables(conn)
    # Enable foreign key constraints
    conn.connection.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def repo(db_conn):
    """Create a BundleImagesRepository instance for testing."""
    return BundleImagesRepository(db_conn)


@pytest.fixture
def sample_bundle_id(db_conn):
    """Create a sample bundle and return its ID."""
    cursor = db_conn.connection.cursor()
    cursor.execute(
        """
        INSERT INTO document_bundles (bundle_name, status)
        VALUES (?, ?)
        """,
        ("Test Bundle", "suggested"),
    )
    db_conn.connection.commit()
    return cursor.lastrowid


@pytest.fixture
def sample_image_ids(db_conn):
    """Create sample image files and return their IDs."""
    cursor = db_conn.connection.cursor()
    image_ids = []

    for i in range(3):
        cursor.execute(
            """
            INSERT INTO image_files (
                file_path, file_hash, directory_path, filename,
                file_size, file_mtime, discovered_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"/test/image{i}.png",
                f"hash{i}",
                "/test",
                f"image{i}.png",
                1024 * (i + 1),
                1234567890.0 + i,
                datetime.now().isoformat(),
            ),
        )
        image_ids.append(cursor.lastrowid)

    db_conn.connection.commit()
    return image_ids


class TestBundleImagesRepositoryBasics:
    """Test basic repository initialization and setup."""

    def test_repository_initialization(self, repo, db_conn):
        """Test that repository initializes with correct connection."""
        assert repo.conn == db_conn
        assert repo.conn.connection is not None

    def test_repository_has_logger(self, repo):
        """Test that repository has logger initialized."""
        logger = repo._get_logger()
        assert logger is not None
        assert hasattr(logger, "info")


class TestAddImage:
    """Test add_image() method for single image insertion."""

    def test_add_image_creates_mapping(self, repo, sample_bundle_id, sample_image_ids):
        """Test adding a single image to a bundle."""
        record_id = repo.add_image(
            bundle_id=sample_bundle_id, image_file_id=sample_image_ids[0], sequence_order=1
        )

        assert record_id > 0

        # Verify record was created
        cursor = repo.conn.connection.cursor()
        cursor.execute(
            "SELECT * FROM bundle_images WHERE id = ?",
            (record_id,),
        )
        record = cursor.fetchone()

        assert record is not None
        assert record[1] == sample_bundle_id  # bundle_id
        assert record[2] == sample_image_ids[0]  # image_file_id
        assert record[3] == 1  # sequence_order

    def test_add_image_with_different_sequence_orders(
        self, repo, sample_bundle_id, sample_image_ids
    ):
        """Test adding images with different sequence orders."""
        id1 = repo.add_image(
            bundle_id=sample_bundle_id, image_file_id=sample_image_ids[0], sequence_order=1
        )
        id2 = repo.add_image(
            bundle_id=sample_bundle_id, image_file_id=sample_image_ids[1], sequence_order=2
        )

        assert id1 > 0
        assert id2 > 0
        assert id1 != id2

    def test_add_image_handles_operational_error(self, repo, sample_bundle_id, sample_image_ids):
        """Test add_image handles OperationalError."""
        with patch.object(
            repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
        ), pytest.raises(sqlite3.OperationalError, match="Database is locked"):
            repo.add_image(
                bundle_id=sample_bundle_id,
                image_file_id=sample_image_ids[0],
                sequence_order=1,
            )

    def test_add_image_handles_generic_error(self, repo, sample_bundle_id, sample_image_ids):
        """Test add_image handles generic sqlite3.Error."""
        with patch.object(repo.conn, "commit", side_effect=sqlite3.Error("Generic database error")):
            with pytest.raises(sqlite3.Error, match="Failed to add image to bundle"):
                repo.add_image(
                    bundle_id=sample_bundle_id,
                    image_file_id=sample_image_ids[0],
                    sequence_order=1,
                )


class TestAddImagesBulk:
    """Test add_images_bulk() method for multiple image insertion."""

    def test_add_images_bulk_creates_all_mappings(self, repo, sample_bundle_id, sample_image_ids):
        """Test adding multiple images in bulk."""
        repo.add_images_bulk(bundle_id=sample_bundle_id, image_file_ids=sample_image_ids)

        # Verify all images were added
        cursor = repo.conn.connection.cursor()
        cursor.execute(
            "SELECT image_file_id, sequence_order FROM bundle_images WHERE bundle_id = ? ORDER BY sequence_order",
            (sample_bundle_id,),
        )
        records = cursor.fetchall()

        assert len(records) == 3
        assert records[0][0] == sample_image_ids[0]  # First image
        assert records[0][1] == 1  # sequence_order = 1
        assert records[1][0] == sample_image_ids[1]  # Second image
        assert records[1][1] == 2  # sequence_order = 2
        assert records[2][0] == sample_image_ids[2]  # Third image
        assert records[2][1] == 3  # sequence_order = 3

    def test_add_images_bulk_with_empty_list(self, repo, sample_bundle_id):
        """Test adding empty list of images."""
        # Should not raise error
        repo.add_images_bulk(bundle_id=sample_bundle_id, image_file_ids=[])

        # Verify no images were added
        cursor = repo.conn.connection.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM bundle_images WHERE bundle_id = ?", (sample_bundle_id,)
        )
        count = cursor.fetchone()[0]
        assert count == 0

    def test_add_images_bulk_handles_operational_error(
        self, repo, sample_bundle_id, sample_image_ids
    ):
        """Test add_images_bulk handles OperationalError."""
        with patch.object(
            repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
        ), pytest.raises(sqlite3.OperationalError, match="Database is locked"):
            repo.add_images_bulk(bundle_id=sample_bundle_id, image_file_ids=sample_image_ids)

    def test_add_images_bulk_handles_generic_error(self, repo, sample_bundle_id, sample_image_ids):
        """Test add_images_bulk handles generic sqlite3.Error."""
        with patch.object(repo.conn, "commit", side_effect=sqlite3.Error("Generic database error")):
            with pytest.raises(sqlite3.Error, match="Failed to add images to bundle"):
                repo.add_images_bulk(bundle_id=sample_bundle_id, image_file_ids=sample_image_ids)


class TestGetImagesForBundle:
    """Test get_images_for_bundle() retrieval method."""

    def test_get_images_for_bundle_returns_ordered_list(
        self, repo, sample_bundle_id, sample_image_ids
    ):
        """Test retrieving images for a bundle in sequence order."""
        repo.add_images_bulk(bundle_id=sample_bundle_id, image_file_ids=sample_image_ids)

        images = repo.get_images_for_bundle(sample_bundle_id)

        assert len(images) == 3
        # Should be ordered by sequence_order
        assert images[0]["sequence_order"] == 1
        assert images[1]["sequence_order"] == 2
        assert images[2]["sequence_order"] == 3
        # Verify image file IDs
        assert images[0]["id"] == sample_image_ids[0]
        assert images[1]["id"] == sample_image_ids[1]
        assert images[2]["id"] == sample_image_ids[2]

    def test_get_images_for_bundle_returns_empty_for_no_images(self, repo, sample_bundle_id):
        """Test retrieving images for bundle with no images."""
        images = repo.get_images_for_bundle(sample_bundle_id)
        assert images == []

    def test_get_images_for_bundle_returns_empty_for_nonexistent_bundle(self, repo):
        """Test retrieving images for non-existent bundle."""
        images = repo.get_images_for_bundle(99999)
        assert images == []


class TestGetBundlesForImage:
    """Test get_bundles_for_image() retrieval method."""

    def test_get_bundles_for_image_returns_bundles(self, repo, db_conn, sample_image_ids):
        """Test retrieving all bundles containing a specific image."""
        # Create two bundles
        cursor = db_conn.connection.cursor()

        cursor.execute(
            "INSERT INTO document_bundles (bundle_name, status) VALUES (?, ?)",
            ("Bundle 1", "suggested"),
        )
        bundle1_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO document_bundles (bundle_name, status) VALUES (?, ?)",
            ("Bundle 2", "suggested"),
        )
        bundle2_id = cursor.lastrowid
        db_conn.connection.commit()

        # Add same image to both bundles
        repo.add_image(bundle_id=bundle1_id, image_file_id=sample_image_ids[0], sequence_order=1)
        repo.add_image(bundle_id=bundle2_id, image_file_id=sample_image_ids[0], sequence_order=1)

        bundles = repo.get_bundles_for_image(sample_image_ids[0])

        assert len(bundles) == 2
        bundle_ids = [b["id"] for b in bundles]
        assert bundle1_id in bundle_ids
        assert bundle2_id in bundle_ids

    def test_get_bundles_for_image_returns_empty_for_no_bundles(self, repo, sample_image_ids):
        """Test retrieving bundles for image not in any bundle."""
        bundles = repo.get_bundles_for_image(sample_image_ids[0])
        assert bundles == []

    def test_get_bundles_for_image_returns_empty_for_nonexistent_image(self, repo):
        """Test retrieving bundles for non-existent image."""
        bundles = repo.get_bundles_for_image(99999)
        assert bundles == []


class TestRemoveImage:
    """Test remove_image() method for removing single image."""

    def test_remove_image_removes_mapping(self, repo, sample_bundle_id, sample_image_ids):
        """Test removing a single image from a bundle."""
        # Add images first
        repo.add_images_bulk(bundle_id=sample_bundle_id, image_file_ids=sample_image_ids)

        # Remove middle image
        repo.remove_image(bundle_id=sample_bundle_id, image_file_id=sample_image_ids[1])

        # Verify only 2 images remain
        images = repo.get_images_for_bundle(sample_bundle_id)
        assert len(images) == 2
        image_ids = [img["id"] for img in images]
        assert sample_image_ids[0] in image_ids
        assert sample_image_ids[1] not in image_ids
        assert sample_image_ids[2] in image_ids

    def test_remove_image_handles_nonexistent_mapping(
        self, repo, sample_bundle_id, sample_image_ids
    ):
        """Test removing image that's not in bundle (should not error)."""
        # Should not raise error
        repo.remove_image(bundle_id=sample_bundle_id, image_file_id=sample_image_ids[0])

    def test_remove_image_handles_operational_error(self, repo, sample_bundle_id, sample_image_ids):
        """Test remove_image handles OperationalError."""
        repo.add_image(
            bundle_id=sample_bundle_id, image_file_id=sample_image_ids[0], sequence_order=1
        )

        with patch.object(
            repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
        ), pytest.raises(sqlite3.OperationalError, match="Database is locked"):
            repo.remove_image(bundle_id=sample_bundle_id, image_file_id=sample_image_ids[0])

    def test_remove_image_handles_generic_error(self, repo, sample_bundle_id, sample_image_ids):
        """Test remove_image handles generic sqlite3.Error."""
        repo.add_image(
            bundle_id=sample_bundle_id, image_file_id=sample_image_ids[0], sequence_order=1
        )

        with patch.object(repo.conn, "commit", side_effect=sqlite3.Error("Generic database error")):
            with pytest.raises(sqlite3.Error, match="Failed to remove image from bundle"):
                repo.remove_image(bundle_id=sample_bundle_id, image_file_id=sample_image_ids[0])


class TestRemoveAllImages:
    """Test remove_all_images() method for clearing bundle."""

    def test_remove_all_images_clears_bundle(self, repo, sample_bundle_id, sample_image_ids):
        """Test removing all images from a bundle."""
        # Add images first
        repo.add_images_bulk(bundle_id=sample_bundle_id, image_file_ids=sample_image_ids)

        # Remove all
        repo.remove_all_images(sample_bundle_id)

        # Verify bundle is empty
        images = repo.get_images_for_bundle(sample_bundle_id)
        assert len(images) == 0

    def test_remove_all_images_on_empty_bundle(self, repo, sample_bundle_id):
        """Test removing all images from already empty bundle (should not error)."""
        # Should not raise error
        repo.remove_all_images(sample_bundle_id)

        images = repo.get_images_for_bundle(sample_bundle_id)
        assert len(images) == 0

    def test_remove_all_images_handles_operational_error(
        self, repo, sample_bundle_id, sample_image_ids
    ):
        """Test remove_all_images handles OperationalError."""
        repo.add_images_bulk(bundle_id=sample_bundle_id, image_file_ids=sample_image_ids)

        with patch.object(
            repo.conn, "commit", side_effect=sqlite3.OperationalError("database is locked")
        ), pytest.raises(sqlite3.OperationalError, match="Database is locked"):
            repo.remove_all_images(sample_bundle_id)

    def test_remove_all_images_handles_generic_error(
        self, repo, sample_bundle_id, sample_image_ids
    ):
        """Test remove_all_images handles generic sqlite3.Error."""
        repo.add_images_bulk(bundle_id=sample_bundle_id, image_file_ids=sample_image_ids)

        with patch.object(repo.conn, "commit", side_effect=sqlite3.Error("Generic database error")):
            with pytest.raises(sqlite3.Error, match="Failed to remove all images from bundle"):
                repo.remove_all_images(sample_bundle_id)


class TestReorderImages:
    """Test reorder_images() method for changing sequence."""

    def test_reorder_images_changes_sequence(self, repo, sample_bundle_id, sample_image_ids):
        """Test reordering images in a bundle."""
        # Add in original order
        repo.add_images_bulk(bundle_id=sample_bundle_id, image_file_ids=sample_image_ids)

        # Reverse the order
        new_order = [sample_image_ids[2], sample_image_ids[1], sample_image_ids[0]]
        repo.reorder_images(bundle_id=sample_bundle_id, image_file_ids=new_order)

        # Verify new order
        images = repo.get_images_for_bundle(sample_bundle_id)
        assert len(images) == 3
        # Check sequence_order values
        assert images[0]["sequence_order"] == 1
        assert images[1]["sequence_order"] == 2
        assert images[2]["sequence_order"] == 3
        # Verify file paths match expected order (reversed)
        assert images[0]["file_path"] == "/test/image2.png"
        assert images[1]["file_path"] == "/test/image1.png"
        assert images[2]["file_path"] == "/test/image0.png"

    def test_reorder_images_with_subset(self, repo, sample_bundle_id, sample_image_ids):
        """Test reordering with subset of images (effectively removes some)."""
        # Add all three images
        repo.add_images_bulk(bundle_id=sample_bundle_id, image_file_ids=sample_image_ids)

        # Reorder to only include two images
        new_order = [sample_image_ids[0], sample_image_ids[2]]
        repo.reorder_images(bundle_id=sample_bundle_id, image_file_ids=new_order)

        # Verify only two images remain
        images = repo.get_images_for_bundle(sample_bundle_id)
        assert len(images) == 2
        # Verify by file path (more reliable than ID which might be ambiguous)
        assert images[0]["file_path"] == "/test/image0.png"
        assert images[1]["file_path"] == "/test/image2.png"


class TestGetImageCount:
    """Test get_image_count() method for counting images."""

    def test_get_image_count_returns_correct_count(self, repo, sample_bundle_id, sample_image_ids):
        """Test counting images in a bundle."""
        # Initially 0
        assert repo.get_image_count(sample_bundle_id) == 0

        # Add images
        repo.add_images_bulk(bundle_id=sample_bundle_id, image_file_ids=sample_image_ids)

        # Should be 3
        assert repo.get_image_count(sample_bundle_id) == 3

    def test_get_image_count_after_removal(self, repo, sample_bundle_id, sample_image_ids):
        """Test count after removing images."""
        repo.add_images_bulk(bundle_id=sample_bundle_id, image_file_ids=sample_image_ids)
        assert repo.get_image_count(sample_bundle_id) == 3

        # Remove one
        repo.remove_image(bundle_id=sample_bundle_id, image_file_id=sample_image_ids[0])
        assert repo.get_image_count(sample_bundle_id) == 2

        # Remove all
        repo.remove_all_images(sample_bundle_id)
        assert repo.get_image_count(sample_bundle_id) == 0

    def test_get_image_count_for_nonexistent_bundle(self, repo):
        """Test count for non-existent bundle."""
        assert repo.get_image_count(99999) == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_add_image_enforces_unique_bundle_image_constraint(
        self, repo, sample_bundle_id, sample_image_ids
    ):
        """Test that same image can't be added to same bundle twice."""
        repo.add_image(
            bundle_id=sample_bundle_id, image_file_id=sample_image_ids[0], sequence_order=1
        )

        # Attempting to add same image again should fail
        with pytest.raises(sqlite3.IntegrityError):
            repo.add_image(
                bundle_id=sample_bundle_id, image_file_id=sample_image_ids[0], sequence_order=2
            )

    def test_add_image_enforces_unique_sequence_order_constraint(
        self, repo, sample_bundle_id, sample_image_ids
    ):
        """Test that same sequence order can't be used twice in same bundle."""
        repo.add_image(
            bundle_id=sample_bundle_id, image_file_id=sample_image_ids[0], sequence_order=1
        )

        # Attempting to add different image with same sequence order should fail
        with pytest.raises(sqlite3.IntegrityError):
            repo.add_image(
                bundle_id=sample_bundle_id, image_file_id=sample_image_ids[1], sequence_order=1
            )

    def test_get_images_includes_image_file_details(self, repo, sample_bundle_id, sample_image_ids):
        """Test that get_images_for_bundle includes full image file details via JOIN."""
        repo.add_image(
            bundle_id=sample_bundle_id, image_file_id=sample_image_ids[0], sequence_order=1
        )

        images = repo.get_images_for_bundle(sample_bundle_id)

        assert len(images) == 1
        # Should include fields from image_files table
        assert "file_path" in images[0]
        assert "file_hash" in images[0]
        assert images[0]["file_path"] == "/test/image0.png"

    def test_cascade_delete_on_bundle_deletion(
        self, repo, db_conn, sample_bundle_id, sample_image_ids
    ):
        """Test that deleting a bundle cascades to bundle_images."""
        # Add images to bundle
        repo.add_images_bulk(bundle_id=sample_bundle_id, image_file_ids=sample_image_ids)

        # Verify images are present
        assert repo.get_image_count(sample_bundle_id) == 3

        # Delete the bundle
        cursor = db_conn.connection.cursor()
        cursor.execute("DELETE FROM document_bundles WHERE id = ?", (sample_bundle_id,))
        db_conn.connection.commit()

        # Verify bundle_images records were cascade deleted
        cursor.execute(
            "SELECT COUNT(*) FROM bundle_images WHERE bundle_id = ?", (sample_bundle_id,)
        )
        count = cursor.fetchone()[0]
        assert count == 0

    def test_cascade_delete_on_image_file_deletion(
        self, repo, db_conn, sample_bundle_id, sample_image_ids
    ):
        """Test that deleting an image file cascades to bundle_images."""
        # Add images to bundle
        repo.add_images_bulk(bundle_id=sample_bundle_id, image_file_ids=sample_image_ids)

        # Verify images are present
        assert repo.get_image_count(sample_bundle_id) == 3

        # Delete one image file
        cursor = db_conn.connection.cursor()
        cursor.execute("DELETE FROM image_files WHERE id = ?", (sample_image_ids[0],))
        db_conn.connection.commit()

        # Verify bundle_images record was cascade deleted
        assert repo.get_image_count(sample_bundle_id) == 2
