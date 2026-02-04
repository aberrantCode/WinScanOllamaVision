"""
Test ImageGalleryWidget functionality
"""
import sys
import os
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gui import ImageGalleryWidget
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
    images = []
    for i in range(5):
        img_path = tmp_path / f"test_image_{i:03d}.png"
        # Create empty file (in real test, would create actual image)
        img_path.touch()
        images.append(str(img_path))
    return images


def test_image_gallery_creation(app, temp_db):
    """Test that ImageGalleryWidget can be created"""
    gallery = ImageGalleryWidget(analysis_db=temp_db)
    assert gallery is not None
    assert gallery.image_list is not None
    assert gallery.search_box is not None
    assert gallery.sort_combo is not None


def test_set_images(app, temp_db, sample_images):
    """Test setting images in the gallery"""
    gallery = ImageGalleryWidget(analysis_db=temp_db)
    gallery.set_images(sample_images)

    assert len(gallery.all_images) == 5
    assert len(gallery.filtered_images) == 5
    assert gallery.image_list.count() == 5


def test_search_filter(app, temp_db, sample_images):
    """Test search filtering"""
    gallery = ImageGalleryWidget(analysis_db=temp_db)
    gallery.set_images(sample_images)

    # Search for '001'
    gallery.search_box.setText("001")

    # Should only show one image
    assert len(gallery.filtered_images) == 1
    assert '001' in gallery.filtered_images[0]['filename']


def test_sort_by_name(app, temp_db, sample_images):
    """Test sorting by name"""
    gallery = ImageGalleryWidget(analysis_db=temp_db)
    gallery.set_images(sample_images)

    # Sort by name
    gallery.sort_combo.setCurrentText("Name")

    # Check that images are sorted
    filenames = [img['filename'] for img in gallery.filtered_images]
    assert filenames == sorted(filenames)


def test_checkbox_toggle(app, temp_db, sample_images):
    """Test checkbox toggling"""
    gallery = ImageGalleryWidget(analysis_db=temp_db)
    gallery.set_images(sample_images)

    # Connect signal to capture emitted values
    toggled_files = []
    toggled_states = []

    def on_toggle(file_path, checked):
        toggled_files.append(file_path)
        toggled_states.append(checked)

    gallery.image_toggled.connect(on_toggle)

    # Check first image
    first_file = sample_images[0]
    gallery.checked_files.add(first_file)
    gallery.image_toggled.emit(first_file, True)

    assert len(toggled_files) == 1
    assert toggled_files[0] == first_file
    assert toggled_states[0] is True


def test_select_all(app, temp_db, sample_images):
    """Test Select All button"""
    gallery = ImageGalleryWidget(analysis_db=temp_db)
    gallery.set_images(sample_images)

    # Click Select All
    gallery._on_select_all()

    # All images should be checked
    assert len(gallery.checked_files) == 5


def test_clear_selection(app, temp_db, sample_images):
    """Test Clear Selection button"""
    gallery = ImageGalleryWidget(analysis_db=temp_db)
    gallery.set_images(sample_images)

    # Select all first
    gallery._on_select_all()
    assert len(gallery.checked_files) == 5

    # Clear selection
    gallery._on_clear_selection()
    assert len(gallery.checked_files) == 0


def test_image_selection(app, temp_db, sample_images):
    """Test image selection signal"""
    gallery = ImageGalleryWidget(analysis_db=temp_db)
    gallery.set_images(sample_images)

    # Connect signal
    selected_files = []

    def on_select(file_path):
        selected_files.append(file_path)

    gallery.image_selected.connect(on_select)

    # Simulate clicking first item
    first_item = gallery.image_list.item(0)
    gallery._on_item_clicked(first_item)

    assert len(selected_files) == 1
    assert selected_files[0] == sample_images[0]


def test_count_label(app, temp_db, sample_images):
    """Test count label updates"""
    gallery = ImageGalleryWidget(analysis_db=temp_db)
    gallery.set_images(sample_images)

    # Check initial count
    assert "Showing: 5 of 5" in gallery.count_label.text()

    # Apply filter
    gallery.search_box.setText("001")

    # Check filtered count
    assert "Showing: 1 of 5" in gallery.count_label.text()


def test_set_current_file(app, temp_db, sample_images):
    """Test setting current file externally"""
    gallery = ImageGalleryWidget(analysis_db=temp_db)
    gallery.set_images(sample_images)

    # Set current file
    target_file = sample_images[2]
    gallery.set_current_file(target_file)

    assert gallery.current_file == target_file


def test_get_checked_files(app, temp_db, sample_images):
    """Test getting checked files"""
    gallery = ImageGalleryWidget(analysis_db=temp_db)
    gallery.set_images(sample_images)

    # Check some files
    gallery.checked_files.add(sample_images[0])
    gallery.checked_files.add(sample_images[2])

    checked = gallery.get_checked_files()
    assert len(checked) == 2
    assert sample_images[0] in checked
    assert sample_images[2] in checked


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
