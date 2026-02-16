"""Tests for RotationRepository"""

import tempfile

import pytest

from db.connection import DatabaseConnection
from db.repositories.rotation_repo import RotationRepository
from db.schema import create_all_tables


@pytest.fixture
def db_conn(tmp_path):
    """Create a temporary database connection for testing."""
    db_path = tmp_path / "test_rotation.db"
    conn = DatabaseConnection(str(db_path))
    create_all_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def repo(db_conn):
    """Create a RotationRepository instance for testing."""
    return RotationRepository(db_conn)


@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"test image data")
        file_path = f.name
    yield file_path
    import os

    if os.path.exists(file_path):
        os.remove(file_path)


class TestRotationRepositoryBasics:
    """Test basic repository initialization."""

    def test_repository_initialization(self, repo, db_conn):
        """Test that repository initializes with correct connection."""
        assert repo.conn == db_conn
        assert repo.conn.connection is not None


class TestSave:
    """Test save() method for saving rotation angles."""

    def test_save_creates_rotation_record(self, repo, temp_file):
        """Test saving rotation for a new file."""
        repo.save(temp_file, 90)

        # Verify metadata was created with rotation
        cursor = repo.conn.connection.cursor()
        cursor.execute(
            """
            SELECT m.rotation
            FROM metadata m
            JOIN image_files img ON m.image_file_id = img.id
            WHERE img.file_path = ?
        """,
            (temp_file,),
        )
        rotation = cursor.fetchone()[0]

        assert rotation == 90

    def test_save_normalizes_rotation_to_360_range(self, repo, temp_file):
        """Test that rotation is normalized to 0-359 range."""
        repo.save(temp_file, 450)  # 450 % 360 = 90

        result = repo.get(temp_file)
        assert result == 90

    def test_save_updates_existing_rotation(self, repo, temp_file):
        """Test updating rotation for existing file."""
        # Save initial rotation
        repo.save(temp_file, 90)

        # Update rotation
        repo.save(temp_file, 180)

        result = repo.get(temp_file)
        assert result == 180

    def test_save_handles_zero_rotation(self, repo, temp_file):
        """Test saving zero rotation."""
        repo.save(temp_file, 0)

        result = repo.get(temp_file)
        assert result == 0

    def test_save_handles_270_rotation(self, repo, temp_file):
        """Test saving 270-degree rotation."""
        repo.save(temp_file, 270)

        result = repo.get(temp_file)
        assert result == 270

    def test_save_handles_negative_rotation(self, repo, temp_file):
        """Test normalizing negative rotation."""
        repo.save(temp_file, -90)  # -90 % 360 = 270

        result = repo.get(temp_file)
        assert result == 270

    def test_save_registers_image_file_if_not_exists(self, repo, temp_file):
        """Test that save auto-registers image file."""
        repo.save(temp_file, 90)

        # Verify image_file was registered
        cursor = repo.conn.connection.cursor()
        cursor.execute("SELECT file_path FROM image_files WHERE file_path = ?", (temp_file,))
        record = cursor.fetchone()

        assert record is not None
        assert record[0] == temp_file

    def test_save_uses_existing_image_file_if_registered(self, repo, temp_file, db_conn):
        """Test that save uses existing image_file_id if file is already registered."""
        import os

        # Pre-register the file in image_files
        file_hash = repo._compute_file_hash(temp_file)
        file_size = os.path.getsize(temp_file)
        file_mtime = os.path.getmtime(temp_file)
        directory_path = os.path.dirname(temp_file)
        filename = os.path.basename(temp_file)

        db_conn.execute(
            """
            INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (temp_file, file_hash, directory_path, filename, file_size, file_mtime),
        )
        db_conn.commit()

        # Now save rotation (should use existing image_file_id - line 63)
        repo.save(temp_file, 90)

        # Verify only one image_file record exists
        cursor = db_conn.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM image_files WHERE file_path = ?", (temp_file,))
        count = cursor.fetchone()[0]

        assert count == 1

        # Verify rotation was saved
        result = repo.get(temp_file)
        assert result == 90


class TestGet:
    """Test get() method for retrieving rotation angles."""

    def test_get_returns_saved_rotation(self, repo, temp_file):
        """Test retrieving saved rotation."""
        repo.save(temp_file, 90)

        result = repo.get(temp_file)
        assert result == 90

    def test_get_returns_zero_when_not_found(self, repo):
        """Test get returns 0 for non-existent file."""
        result = repo.get("/nonexistent/file.jpg")
        assert result == 0

    def test_get_returns_zero_when_rotation_is_null(self, repo, temp_file, db_conn):
        """Test get returns 0 when rotation field is NULL."""
        import os

        # Register file without rotation (NULL)
        file_hash = repo._compute_file_hash(temp_file)
        file_size = os.path.getsize(temp_file)
        file_mtime = os.path.getmtime(temp_file)
        directory_path = os.path.dirname(temp_file)
        filename = os.path.basename(temp_file)

        db_conn.execute(
            """
            INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (temp_file, file_hash, directory_path, filename, file_size, file_mtime),
        )
        image_file_id = db_conn.fetch_one("SELECT last_insert_rowid()")[0]

        # Insert metadata with NULL rotation
        db_conn.execute(
            "INSERT INTO metadata (image_file_id, rotation) VALUES (?, NULL)",
            (image_file_id,),
        )
        db_conn.commit()

        result = repo.get(temp_file)
        assert result == 0


class TestSavePreference:
    """Test save_preference() method for legacy rotation_preferences table."""

    def test_save_preference_creates_record(self, repo, temp_file):
        """Test saving rotation preference to rotation_preferences table."""
        repo.save_preference(temp_file, 90, "manual")

        # Verify record was created
        cursor = repo.conn.connection.cursor()
        cursor.execute(
            "SELECT rotation_degrees, rotation_source FROM rotation_preferences WHERE file_path = ?",
            (temp_file,),
        )
        record = cursor.fetchone()

        assert record is not None
        assert record[0] == 90  # rotation_degrees
        assert record[1] == "manual"  # rotation_source

    def test_save_preference_replaces_existing_record(self, repo, temp_file):
        """Test INSERT OR REPLACE behavior."""
        # Save initial preference
        repo.save_preference(temp_file, 90, "ai_suggestion")

        # Replace with new preference
        repo.save_preference(temp_file, 180, "manual")

        # Verify only one record exists with updated values
        cursor = repo.conn.connection.cursor()
        cursor.execute(
            "SELECT rotation_degrees, rotation_source FROM rotation_preferences WHERE file_path = ?",
            (temp_file,),
        )
        records = cursor.fetchall()

        assert len(records) == 1
        assert records[0][0] == 180
        assert records[0][1] == "manual"

    def test_save_preference_with_ai_suggestion(self, repo, temp_file):
        """Test saving AI-suggested rotation."""
        repo.save_preference(temp_file, 270, "ai_suggestion")

        cursor = repo.conn.connection.cursor()
        cursor.execute(
            "SELECT rotation_source FROM rotation_preferences WHERE file_path = ?",
            (temp_file,),
        )
        source = cursor.fetchone()[0]

        assert source == "ai_suggestion"


class TestComputeFileHash:
    """Test _compute_file_hash() static method."""

    def test_compute_file_hash_returns_sha256(self, temp_file):
        """Test that file hash is SHA-256."""
        hash_result = RotationRepository._compute_file_hash(temp_file)

        assert len(hash_result) == 64  # SHA-256 hex string
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_compute_file_hash_is_consistent(self, temp_file):
        """Test that hash is consistent for same file."""
        hash1 = RotationRepository._compute_file_hash(temp_file)
        hash2 = RotationRepository._compute_file_hash(temp_file)

        assert hash1 == hash2


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_save_with_large_rotation_value(self, repo, temp_file):
        """Test normalizing very large rotation values."""
        repo.save(temp_file, 3690)  # 3690 % 360 = 90

        result = repo.get(temp_file)
        assert result == 90

    def test_multiple_rotations_same_file(self, repo, temp_file):
        """Test multiple rotation updates on same file."""
        repo.save(temp_file, 90)
        repo.save(temp_file, 180)
        repo.save(temp_file, 270)
        repo.save(temp_file, 0)

        result = repo.get(temp_file)
        assert result == 0


class TestIntegration:
    """Test integration scenarios."""

    def test_save_and_retrieve_workflow(self, repo, temp_file):
        """Test complete save and retrieve workflow."""
        # Save rotation
        repo.save(temp_file, 90)

        # Retrieve rotation
        rotation = repo.get(temp_file)
        assert rotation == 90

        # Update rotation
        repo.save(temp_file, 270)

        # Retrieve updated rotation
        updated_rotation = repo.get(temp_file)
        assert updated_rotation == 270

    def test_save_preference_workflow(self, repo):
        """Test rotation preference workflow."""
        file_path = "/test/image.jpg"

        # Save AI suggestion
        repo.save_preference(file_path, 90, "ai_suggestion")

        # User manually overrides
        repo.save_preference(file_path, 180, "manual")

        # Verify final state
        cursor = repo.conn.connection.cursor()
        cursor.execute(
            "SELECT rotation_degrees, rotation_source FROM rotation_preferences WHERE file_path = ?",
            (file_path,),
        )
        record = cursor.fetchone()

        assert record[0] == 180
        assert record[1] == "manual"
