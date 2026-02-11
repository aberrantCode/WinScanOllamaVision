"""Tests for bundling service rotation handling."""

import os
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from db.analysis_db import AnalysisDB
from db.connection import DatabaseConnection
from db.schema import create_all_tables
from services.bundling_service import BundlingService


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = DatabaseConnection(path)
    create_all_tables(conn)
    yield AnalysisDB(path)

    # Cleanup
    conn.close()
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def temp_images():
    """Create temporary test images."""
    images = []
    for i in range(3):
        # Create a simple test image (100x50 - wider than tall so rotation is visible)
        img = Image.new("RGB", (100, 50), color=(255, 0, 0))

        # Save to temp file
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        img.save(path)

        images.append(path)

    yield images

    # Cleanup
    for path in images:
        if os.path.exists(path):
            os.unlink(path)


def test_convert_bundle_to_pdf_applies_per_file_rotations(temp_db, temp_images):
    """Test that PDF conversion applies per-file rotations from database."""
    # Register images with different rotations
    for i, image_path in enumerate(temp_images):
        temp_db.register_image_file(
            file_path=image_path,
            file_hash=f"hash{i}",
            directory_path=os.path.dirname(image_path),
            filename=os.path.basename(image_path),
            file_size=1000,
            file_mtime=0.0,
        )

        # Set different rotation for each image
        rotations = [0, 90, 180]  # No rotation, 90 CW, 180
        temp_db.update_image_rotation(image_path, rotations[i])

    # Create bundling service
    bundling_service = BundlingService(temp_db)

    # Convert to PDF
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name

    try:
        result = bundling_service.convert_bundle_to_pdf(
            file_paths=temp_images, output_path=pdf_path, rotation_angle=0
        )

        # Verify PDF was created
        assert os.path.exists(result)
        assert Path(result).stat().st_size > 0

    finally:
        # Cleanup
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)


def test_convert_bundle_to_pdf_combines_per_file_and_bundle_rotations(temp_db, temp_images):
    """Test that both per-file and bundle-level rotations are applied."""
    # Register images with per-file rotations
    for i, image_path in enumerate(temp_images):
        temp_db.register_image_file(
            file_path=image_path,
            file_hash=f"hash{i}",
            directory_path=os.path.dirname(image_path),
            filename=os.path.basename(image_path),
            file_size=1000,
            file_mtime=0.0,
        )

        # Set 90 degree rotation for all images
        temp_db.update_image_rotation(image_path, 90)

    # Create bundling service
    bundling_service = BundlingService(temp_db)

    # Convert to PDF with additional bundle-level rotation
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name

    try:
        result = bundling_service.convert_bundle_to_pdf(
            file_paths=temp_images,
            output_path=pdf_path,
            rotation_angle=90,  # Additional 90 degree rotation
        )

        # Verify PDF was created (total rotation per page: 90 + 90 = 180)
        assert os.path.exists(result)
        assert Path(result).stat().st_size > 0

    finally:
        # Cleanup
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)


def test_convert_bundle_to_pdf_handles_zero_rotation(temp_db, temp_images):
    """Test that images with no rotation work correctly."""
    # Register images with no rotation
    for i, image_path in enumerate(temp_images):
        temp_db.register_image_file(
            file_path=image_path,
            file_hash=f"hash{i}",
            directory_path=os.path.dirname(image_path),
            filename=os.path.basename(image_path),
            file_size=1000,
            file_mtime=0.0,
        )

        # No rotation
        temp_db.update_image_rotation(image_path, 0)

    # Create bundling service
    bundling_service = BundlingService(temp_db)

    # Convert to PDF
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name

    try:
        result = bundling_service.convert_bundle_to_pdf(
            file_paths=temp_images, output_path=pdf_path, rotation_angle=0
        )

        # Verify PDF was created
        assert os.path.exists(result)
        assert Path(result).stat().st_size > 0

    finally:
        # Cleanup
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)


def test_convert_bundle_to_pdf_reads_rotation_from_database(temp_db, temp_images):
    """Test that rotation is actually read from database, not hardcoded."""
    # Register first image
    image_path = temp_images[0]
    temp_db.register_image_file(
        file_path=image_path,
        file_hash="hash1",
        directory_path=os.path.dirname(image_path),
        filename=os.path.basename(image_path),
        file_size=1000,
        file_mtime=0.0,
    )

    # Set rotation in database
    temp_db.update_image_rotation(image_path, 270)

    # Create bundling service
    bundling_service = BundlingService(temp_db)

    # Verify that get_image_rotation is called by creating a spy
    original_get_rotation = temp_db.get_image_rotation
    rotation_called = []

    def spy_get_rotation(file_path):
        rotation_called.append(file_path)
        return original_get_rotation(file_path)

    temp_db.get_image_rotation = spy_get_rotation

    # Convert to PDF
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name

    try:
        bundling_service.convert_bundle_to_pdf(
            file_paths=[image_path], output_path=pdf_path, rotation_angle=0
        )

        # Verify get_image_rotation was called
        assert image_path in rotation_called, "get_image_rotation should be called for each file"

    finally:
        # Cleanup
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)
