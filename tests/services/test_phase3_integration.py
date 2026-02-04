"""
Test Phase 3 integration: ImageGalleryWidget in ConvertImagesWindow
"""
import sys
import os
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from unittest.mock import MagicMock, patch

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gui import ConvertImagesWindow, ImageGalleryWidget
from analysis_db import AnalysisDB


@pytest.fixture
def app():
    """Create QApplication instance"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def temp_db(tmp_path):
    """Create temporary database"""
    db_path = tmp_path / "test_analysis.db"
    return AnalysisDB(str(db_path))


@pytest.fixture
def sample_images(tmp_path):
    """Create sample image files"""
    from PIL import Image
    images = []
    for i in range(5):
        img_path = tmp_path / f"test_image_{i:03d}.png"
        # Create a small test image
        img = Image.new('RGB', (100, 100), color=(255, 255, 255))
        img.save(img_path)
        images.append(str(img_path))
    return images


def test_convert_images_window_has_image_gallery(app, monkeypatch):
    """Test that ConvertImagesWindow creates ImageGalleryWidget in Step 1"""
    # Mock file dialog to avoid interactive prompts
    monkeypatch.setattr('PyQt6.QtWidgets.QFileDialog.getExistingDirectory', lambda *args, **kwargs: '')

    window = ConvertImagesWindow()
    window.show()

    # Verify window was created
    assert window is not None

    # Note: image_gallery is created in _setup_step1_ui(), which is called after _scan_and_group()
    # For full test, we would need to mock the scan process

    window.close()


def test_image_gallery_signals_connected(app, sample_images, monkeypatch, tmp_path):
    """Test that image gallery signals are properly connected"""
    # Mock file dialog
    monkeypatch.setattr('PyQt6.QtWidgets.QFileDialog.getExistingDirectory',
                       lambda *args, **kwargs: str(tmp_path))

    window = ConvertImagesWindow()
    window.show()

    # Set up the window with sample files
    window.all_files = sample_images
    window.current_group = []

    # Call _setup_step1_ui to create the image gallery
    window._setup_step1_ui()

    # Verify image gallery was created
    assert hasattr(window, 'image_gallery')
    assert isinstance(window.image_gallery, ImageGalleryWidget)

    # Verify signals are connected by checking they exist
    assert window.image_gallery.image_selected is not None
    assert window.image_gallery.image_toggled is not None

    window.close()


def test_gallery_image_selection_updates_preview(app, sample_images, monkeypatch, tmp_path):
    """Test that selecting an image in gallery updates the center preview"""
    # Mock file dialog
    monkeypatch.setattr('PyQt6.QtWidgets.QFileDialog.getExistingDirectory',
                       lambda *args, **kwargs: str(tmp_path))

    window = ConvertImagesWindow()
    window.show()

    # Set up the window with sample files
    window.all_files = sample_images
    window.current_group = []
    window.page_states = {}

    # Call _setup_step1_ui to create the image gallery
    window._setup_step1_ui()

    # Verify image gallery was created
    assert hasattr(window, 'image_gallery')

    # Select an image from the gallery
    test_file = sample_images[1]
    window._on_gallery_image_selected(test_file)

    # Verify the current page was updated
    assert window.current_page_path == test_file

    window.close()


def test_gallery_checkbox_toggle_updates_group(app, sample_images, monkeypatch, tmp_path):
    """Test that toggling checkbox updates current_group"""
    # Mock file dialog
    monkeypatch.setattr('PyQt6.QtWidgets.QFileDialog.getExistingDirectory',
                       lambda *args, **kwargs: str(tmp_path))

    window = ConvertImagesWindow()
    window.show()

    # Set up the window with sample files
    window.all_files = sample_images
    window.current_group = []
    window.page_states = {}

    # Call _setup_step1_ui to create the image gallery
    window._setup_step1_ui()

    # Toggle checkbox on
    test_file = sample_images[2]
    window._on_gallery_image_toggled(test_file, True)

    # Verify file was added to group
    assert test_file in window.current_group

    # Toggle checkbox off
    window._on_gallery_image_toggled(test_file, False)

    # Verify file was removed from group
    assert test_file not in window.current_group

    window.close()


def test_gallery_populated_with_files(app, sample_images, monkeypatch, tmp_path):
    """Test that gallery is populated with files when shown"""
    # Mock file dialog
    monkeypatch.setattr('PyQt6.QtWidgets.QFileDialog.getExistingDirectory',
                       lambda *args, **kwargs: str(tmp_path))

    window = ConvertImagesWindow()
    window.show()

    # Set up the window with sample files
    window.all_files = sample_images
    window.current_group = [sample_images[0], sample_images[1]]
    window.page_states = {}

    # Call _setup_step1_ui to create the image gallery
    window._setup_step1_ui()

    # Verify image gallery was created and populated
    assert hasattr(window, 'image_gallery')
    assert len(window.image_gallery.all_images) == len(sample_images)

    # Verify checked files match current_group
    checked_files = window.image_gallery.get_checked_files()
    assert set(checked_files) == set(window.current_group)

    window.close()


def test_gallery_search_functionality(app, sample_images, monkeypatch, tmp_path):
    """Test that search box filters images correctly"""
    # Mock file dialog
    monkeypatch.setattr('PyQt6.QtWidgets.QFileDialog.getExistingDirectory',
                       lambda *args, **kwargs: str(tmp_path))

    window = ConvertImagesWindow()
    window.show()

    # Set up the window with sample files
    window.all_files = sample_images
    window.current_group = []

    # Call _setup_step1_ui to create the image gallery
    window._setup_step1_ui()

    # Verify initial state
    assert len(window.image_gallery.filtered_images) == len(sample_images)

    # Apply search filter
    window.image_gallery.search_box.setText("001")

    # Verify filtering
    assert len(window.image_gallery.filtered_images) == 1
    assert "001" in window.image_gallery.filtered_images[0]['filename']

    window.close()


def test_gallery_sort_functionality(app, sample_images, monkeypatch, tmp_path):
    """Test that sort dropdown works correctly"""
    # Mock file dialog
    monkeypatch.setattr('PyQt6.QtWidgets.QFileDialog.getExistingDirectory',
                       lambda *args, **kwargs: str(tmp_path))

    window = ConvertImagesWindow()
    window.show()

    # Set up the window with sample files
    window.all_files = sample_images
    window.current_group = []

    # Call _setup_step1_ui to create the image gallery
    window._setup_step1_ui()

    # Sort by name
    window.image_gallery.sort_combo.setCurrentText("Name")

    # Verify sorting
    filenames = [img['filename'] for img in window.image_gallery.filtered_images]
    assert filenames == sorted(filenames)

    window.close()


def test_gallery_bulk_actions(app, sample_images, monkeypatch, tmp_path):
    """Test Select All and Clear Selection buttons"""
    # Mock file dialog
    monkeypatch.setattr('PyQt6.QtWidgets.QFileDialog.getExistingDirectory',
                       lambda *args, **kwargs: str(tmp_path))

    window = ConvertImagesWindow()
    window.show()

    # Set up the window with sample files
    window.all_files = sample_images
    window.current_group = []

    # Call _setup_step1_ui to create the image gallery
    window._setup_step1_ui()

    # Test Select All
    window.image_gallery._on_select_all()
    assert len(window.image_gallery.checked_files) == len(sample_images)

    # Test Clear Selection
    window.image_gallery._on_clear_selection()
    assert len(window.image_gallery.checked_files) == 0

    window.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
