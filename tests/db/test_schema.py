"""
Tests for unified database schema (Migration 1).

Tests the clean schema with 8 core tables and 2 junction tables.
All legacy migration tests removed.
"""

import pytest

from db.connection import DatabaseConnection
from db.schema import clear_schema_cache, create_all_tables, get_schema_version


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = str(tmp_path / "test.db")
    conn = DatabaseConnection(db_path)
    # Clear cache to ensure fresh schema creation
    clear_schema_cache(db_path)
    yield conn
    conn.close()


# ==================== Schema Version Tests ====================


def test_schema_version_table_exists(temp_db):
    """Test that schema_version table is created."""
    create_all_tables(temp_db)

    cursor = temp_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    )
    assert cursor.fetchone() is not None


def test_migration_1_applied(temp_db):
    """Test that Migration 1 is applied."""
    create_all_tables(temp_db)

    version = get_schema_version(temp_db)
    assert version == 1

    # Check migration record
    cursor = temp_db.execute("SELECT version, description FROM schema_version WHERE version = 1")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == 1
    assert "Unified schema" in row[1]


# ==================== Core Tables Tests ====================


def test_image_files_table_exists(temp_db):
    """Test that image_files table is created with correct schema."""
    create_all_tables(temp_db)

    # Check table exists
    cursor = temp_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='image_files'"
    )
    assert cursor.fetchone() is not None

    # Check columns
    cursor = temp_db.execute("PRAGMA table_info(image_files)")
    columns = {row[1] for row in cursor.fetchall()}

    expected_columns = {
        "id",
        "file_path",
        "file_hash",
        "directory_path",
        "filename",
        "file_size",
        "file_mtime",
        "status",
        "discovered_at",
        "last_seen_at",
        "deleted_at",
    }
    assert expected_columns.issubset(columns)

    # Verify removed columns are NOT present
    removed_columns = {"analysis_id", "rotation", "output_filename"}
    assert not removed_columns.intersection(columns), "Legacy columns should be removed"


def test_analysis_results_table_exists(temp_db):
    """Test that analysis_results table is created with correct schema."""
    create_all_tables(temp_db)

    cursor = temp_db.execute("PRAGMA table_info(analysis_results)")
    columns = {row[1] for row in cursor.fetchall()}

    expected_columns = {
        "id",
        "image_file_id",
        "provider_name",
        "model_name",
        "model_options",
        "prompt_text",
        "response_text",
        "extracted_metadata",
        "confidence_score",
        "had_error",
        "analyzed_at",
        "processing_time_ms",
    }
    assert expected_columns.issubset(columns)

    # Verify legacy columns are NOT present
    removed_columns = {
        "file_path",
        "file_hash",
        "company",
        "document_type",
        "raw_response",
        "is_cached",
    }
    assert not removed_columns.intersection(columns), "Legacy metadata columns should be removed"


def test_metadata_table_exists(temp_db):
    """Test that metadata table is created with correct schema."""
    create_all_tables(temp_db)

    cursor = temp_db.execute("PRAGMA table_info(metadata)")
    columns = {row[1] for row in cursor.fetchall()}

    expected_columns = {
        "id",
        "image_file_id",
        "analysis_result_id",
        "company",
        "document_type",
        "document_date",
        "page_number",
        "total_pages",
        "belongs_to_same_doc",
        "confidence_score",
        "tax_related",
        "document_category",
        "rotation",
        "output_filename",
        "user_verified",
        "auto_approved",
        "last_edited_by",
        "created_at",
        "updated_at",
    }
    assert expected_columns.issubset(columns)

    # Verify removed column is NOT present
    assert "pdf_file_id" not in columns, "pdf_file_id should be removed (use junction table)"


def test_document_bundles_table_exists(temp_db):
    """Test that document_bundles table is created with correct schema."""
    create_all_tables(temp_db)

    cursor = temp_db.execute("PRAGMA table_info(document_bundles)")
    columns = {row[1] for row in cursor.fetchall()}

    expected_columns = {
        "id",
        "bundle_name",
        "confidence_score",
        "confidence_level",
        "status",
        "user_action",
        "action_timestamp",
        "created_at",
        "updated_at",
    }
    assert expected_columns.issubset(columns)

    # Verify removed columns are NOT present
    removed_columns = {"company", "document_type", "file_paths", "pdf_path", "total_pages"}
    assert not removed_columns.intersection(
        columns
    ), "Duplicate metadata and JSON columns should be removed"


def test_pdf_files_table_exists(temp_db):
    """Test that pdf_files table is created with correct schema."""
    create_all_tables(temp_db)

    cursor = temp_db.execute("PRAGMA table_info(pdf_files)")
    columns = {row[1] for row in cursor.fetchall()}

    expected_columns = {
        "id",
        "pdf_path",
        "pdf_filename",
        "file_hash",
        "file_size",
        "page_count",
        "bundle_id",
        "generation_status",
        "generated_at",
    }
    assert expected_columns.issubset(columns)

    # Verify removed column is NOT present
    assert (
        "source_image_ids" not in columns
    ), "source_image_ids JSON should be removed (use junction table)"


def test_source_directories_table_exists(temp_db):
    """Test that source_directories table is created."""
    create_all_tables(temp_db)

    cursor = temp_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='source_directories'"
    )
    assert cursor.fetchone() is not None


def test_audit_trail_table_exists(temp_db):
    """Test that audit_trail table is created."""
    create_all_tables(temp_db)

    cursor = temp_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_trail'"
    )
    assert cursor.fetchone() is not None


# ==================== Junction Tables Tests ====================


def test_pdf_image_pages_table_exists(temp_db):
    """Test that pdf_image_pages junction table is created."""
    create_all_tables(temp_db)

    cursor = temp_db.execute("PRAGMA table_info(pdf_image_pages)")
    columns = {row[1] for row in cursor.fetchall()}

    expected_columns = {"id", "pdf_file_id", "image_file_id", "page_number"}
    assert expected_columns == columns


def test_bundle_images_table_exists(temp_db):
    """Test that bundle_images junction table is created."""
    create_all_tables(temp_db)

    cursor = temp_db.execute("PRAGMA table_info(bundle_images)")
    columns = {row[1] for row in cursor.fetchall()}

    expected_columns = {"id", "bundle_id", "image_file_id", "sequence_order"}
    assert expected_columns == columns


# ==================== Legacy Tables Removed Tests ====================


def test_legacy_tables_not_created(temp_db):
    """Test that legacy tables are NOT created."""
    create_all_tables(temp_db)

    cursor = temp_db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}

    # Legacy tables that should NOT exist
    legacy_tables = {
        "llm_providers",
        "rotation_preferences",
        "analysis_errors",
        "archived_metadata",
    }
    assert not legacy_tables.intersection(tables), "Legacy tables should not be created"


# ==================== Foreign Keys Tests ====================


def test_foreign_keys_enabled(temp_db):
    """Test that foreign key constraints are enabled."""
    create_all_tables(temp_db)

    cursor = temp_db.execute("PRAGMA foreign_keys")
    # Note: Foreign keys are enabled by default in our connection class
    assert cursor.fetchone()[0] == 1


def test_analysis_results_foreign_key(temp_db):
    """Test that analysis_results has correct foreign key to image_files."""
    create_all_tables(temp_db)

    # Insert image file
    temp_db.execute("""
        INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
        VALUES ('/test.png', 'hash123', '/test', 'test.png', 1000, 123.456)
    """)
    temp_db.commit()

    image_id = temp_db.execute(
        "SELECT id FROM image_files WHERE file_path = '/test.png'"
    ).fetchone()[0]

    # Insert analysis result
    temp_db.execute(
        """
        INSERT INTO analysis_results (image_file_id, provider_name, model_name, response_text)
        VALUES (?, 'ollama', 'llama2', 'test response')
    """,
        (image_id,),
    )
    temp_db.commit()

    # Verify it was inserted
    cursor = temp_db.execute(
        "SELECT COUNT(*) FROM analysis_results WHERE image_file_id = ?", (image_id,)
    )
    assert cursor.fetchone()[0] == 1

    # Test CASCADE delete
    temp_db.execute("DELETE FROM image_files WHERE id = ?", (image_id,))
    temp_db.commit()

    # Analysis should also be deleted
    cursor = temp_db.execute(
        "SELECT COUNT(*) FROM analysis_results WHERE image_file_id = ?", (image_id,)
    )
    assert cursor.fetchone()[0] == 0


def test_metadata_foreign_keys(temp_db):
    """Test that metadata has correct foreign keys."""
    create_all_tables(temp_db)

    # Insert image file
    temp_db.execute("""
        INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
        VALUES ('/test.png', 'hash123', '/test', 'test.png', 1000, 123.456)
    """)
    temp_db.commit()

    image_id = temp_db.execute(
        "SELECT id FROM image_files WHERE file_path = '/test.png'"
    ).fetchone()[0]

    # Insert metadata
    temp_db.execute(
        """
        INSERT INTO metadata (image_file_id, company, document_type)
        VALUES (?, 'Acme Inc', 'Invoice')
    """,
        (image_id,),
    )
    temp_db.commit()

    # Verify it was inserted
    cursor = temp_db.execute("SELECT COUNT(*) FROM metadata WHERE image_file_id = ?", (image_id,))
    assert cursor.fetchone()[0] == 1


# ==================== Indices Tests ====================


def test_indices_created(temp_db):
    """Test that all necessary indices are created."""
    create_all_tables(temp_db)

    cursor = temp_db.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indices = {row[0] for row in cursor.fetchall()}

    # Sample of expected indices
    expected_indices = {
        "idx_image_files_path",
        "idx_image_files_status",
        "idx_analysis_image_file",
        "idx_analysis_errors",
        "idx_metadata_image_file",
        "idx_bundles_status",
        "idx_pdf_pages_pdf",
        "idx_bundle_images_bundle",
    }

    assert expected_indices.issubset(indices), f"Missing indices: {expected_indices - indices}"


# ==================== Idempotency Tests ====================


def test_create_tables_idempotent(temp_db):
    """Test that create_all_tables can be called multiple times safely."""
    create_all_tables(temp_db)
    version1 = get_schema_version(temp_db)

    # Call again
    create_all_tables(temp_db)
    version2 = get_schema_version(temp_db)

    assert version1 == version2 == 1


# ==================== Data Integrity Tests ====================


def test_image_file_unique_path(temp_db):
    """Test that file_path is unique in image_files."""
    create_all_tables(temp_db)

    # Insert first record
    temp_db.execute("""
        INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
        VALUES ('/test.png', 'hash123', '/test', 'test.png', 1000, 123.456)
    """)
    temp_db.commit()

    # Try to insert duplicate - should fail
    with pytest.raises(Exception):  # sqlite3.IntegrityError
        temp_db.execute("""
            INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
            VALUES ('/test.png', 'hash456', '/test', 'test.png', 2000, 456.789)
        """)
        temp_db.commit()


def test_metadata_unique_per_image(temp_db):
    """Test that each image can have only one metadata record."""
    create_all_tables(temp_db)

    # Insert image file
    temp_db.execute("""
        INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
        VALUES ('/test.png', 'hash123', '/test', 'test.png', 1000, 123.456)
    """)
    temp_db.commit()

    image_id = temp_db.execute(
        "SELECT id FROM image_files WHERE file_path = '/test.png'"
    ).fetchone()[0]

    # Insert first metadata record
    temp_db.execute(
        """
        INSERT INTO metadata (image_file_id, company)
        VALUES (?, 'Acme Inc')
    """,
        (image_id,),
    )
    temp_db.commit()

    # Try to insert duplicate - should fail due to UNIQUE constraint
    with pytest.raises(Exception):  # sqlite3.IntegrityError
        temp_db.execute(
            """
            INSERT INTO metadata (image_file_id, company)
            VALUES (?, 'Another Company')
        """,
            (image_id,),
        )
        temp_db.commit()


def test_junction_table_constraints(temp_db):
    """Test that junction tables enforce uniqueness constraints."""
    create_all_tables(temp_db)

    # Create test data
    temp_db.execute("""
        INSERT INTO image_files (file_path, file_hash, directory_path, filename, file_size, file_mtime)
        VALUES ('/test.png', 'hash123', '/test', 'test.png', 1000, 123.456)
    """)
    temp_db.execute("""
        INSERT INTO document_bundles (bundle_name) VALUES ('Test Bundle')
    """)
    temp_db.commit()

    image_id = temp_db.execute("SELECT id FROM image_files").fetchone()[0]
    bundle_id = temp_db.execute("SELECT id FROM document_bundles").fetchone()[0]

    # Insert into junction table
    temp_db.execute(
        """
        INSERT INTO bundle_images (bundle_id, image_file_id, sequence_order)
        VALUES (?, ?, 1)
    """,
        (bundle_id, image_id),
    )
    temp_db.commit()

    # Try to insert same image in same bundle - should fail
    with pytest.raises(Exception):  # sqlite3.IntegrityError
        temp_db.execute(
            """
            INSERT INTO bundle_images (bundle_id, image_file_id, sequence_order)
            VALUES (?, ?, 2)
        """,
            (bundle_id, image_id),
        )
        temp_db.commit()
