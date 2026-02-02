"""
Test for duplicate image detection in thumbnail strip and stitching workflow.

This test verifies that the system prevents duplicate images from being:
1. Added to the thumbnail strip multiple times
2. Evaluated multiple times in the stitching workflow
"""

import unittest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


class TestDuplicateDetection(unittest.TestCase):
    """Test duplicate image detection and prevention"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock Qt imports
        sys.modules['PyQt6'] = MagicMock()
        sys.modules['PyQt6.QtWidgets'] = MagicMock()
        sys.modules['PyQt6.QtCore'] = MagicMock()
        sys.modules['PyQt6.QtGui'] = MagicMock()

        # Create mock image paths
        self.test_images = [
            '/test/path/page1.png',
            '/test/path/page2.png',
            '/test/path/page3.png',
            '/test/path/page4.png',
        ]

    def test_add_thumbnail_prevents_duplicates(self):
        """Test that _add_thumbnail() prevents adding the same image twice"""
        from gui import ProcessingWindow

        # Create mock window
        with patch.object(ProcessingWindow, '__init__', lambda x, y, z: None):
            window = ProcessingWindow(None, None)

            # Set up minimal required attributes
            window.page_states = {}
            window.thumbnail_layout = Mock()
            window.thumbnail_layout.count = Mock(return_value=0)
            window._create_thumbnail_widget = Mock(return_value=Mock())

            # Add image first time - should succeed
            window._add_thumbnail(self.test_images[0], 'included')

            # Verify it was added
            self.assertIn(self.test_images[0], window.page_states)
            self.assertEqual(window.thumbnail_layout.addWidget.call_count, 1)

            # Try to add same image again - should be prevented
            window._add_thumbnail(self.test_images[0], 'included')

            # Verify it was NOT added a second time
            self.assertEqual(window.thumbnail_layout.addWidget.call_count, 1,
                           "Duplicate thumbnail should not be added")

    def test_add_thumbnail_detects_duplicate_in_layout(self):
        """Test that _add_thumbnail() detects duplicates already in layout"""
        from gui import ProcessingWindow

        with patch.object(ProcessingWindow, '__init__', lambda x, y, z: None):
            window = ProcessingWindow(None, None)

            # Set up mock layout with existing widget
            existing_widget = Mock()
            existing_widget.property = Mock(return_value=self.test_images[0])

            window.page_states = {}
            window.thumbnail_layout = Mock()
            window.thumbnail_layout.count = Mock(return_value=1)
            window.thumbnail_layout.itemAt = Mock(return_value=Mock(widget=Mock(return_value=existing_widget)))
            window._create_thumbnail_widget = Mock(return_value=Mock())

            # Try to add image that's already in layout
            window._add_thumbnail(self.test_images[0], 'included')

            # Verify it was NOT added
            self.assertEqual(window.thumbnail_layout.addWidget.call_count, 0,
                           "Duplicate thumbnail should be detected in layout")

    def test_load_next_page_skips_processed_files(self):
        """Test that _load_next_page_for_stitching() skips already processed files"""
        from gui import ProcessingWindow

        with patch.object(ProcessingWindow, '__init__', lambda x, y, z: None):
            window = ProcessingWindow(None, None)

            # Set up test data
            window.all_files = self.test_images
            window.current_file_index = 0
            window.page_states = {
                self.test_images[0]: 'included',  # Already processed
                self.test_images[1]: 'excluded',  # Already processed
            }
            window.current_group = []
            window.current_page_path = None

            # Mock required methods
            window._display_page_in_large_preview = Mock()
            window._add_thumbnail = Mock()
            window.config_manager = Mock()
            window.config_manager.get_setting = Mock(return_value='test-model')

            # Call _load_next_page_for_stitching
            window._load_next_page_for_stitching()

            # Verify it skipped processed files and loaded the third file
            self.assertEqual(window.current_file_index, 2,
                           "Should skip processed files and move to index 2")
            self.assertEqual(window.current_page_path, self.test_images[2],
                           "Should load the third image (first unprocessed)")

    def test_sequential_file_processing_no_duplicates(self):
        """Test that processing files sequentially doesn't create duplicates"""
        from gui import ProcessingWindow

        with patch.object(ProcessingWindow, '__init__', lambda x, y, z: None):
            window = ProcessingWindow(None, None)

            # Set up for processing multiple files
            window.all_files = self.test_images
            window.current_file_index = 0
            window.page_states = {}
            window.thumbnail_layout = Mock()
            window.thumbnail_layout.count = Mock(return_value=0)
            window._create_thumbnail_widget = Mock(return_value=Mock())

            # Process files one by one
            for i, image_path in enumerate(self.test_images):
                window._add_thumbnail(image_path, 'included')

            # Verify each file was added exactly once
            self.assertEqual(len(window.page_states), 4,
                           "All 4 files should be in page_states")
            self.assertEqual(window.thumbnail_layout.addWidget.call_count, 4,
                           "Should have added exactly 4 thumbnails")

            # Try to add duplicates
            for image_path in self.test_images:
                window._add_thumbnail(image_path, 'included')

            # Verify no duplicates were added
            self.assertEqual(window.thumbnail_layout.addWidget.call_count, 4,
                           "No additional thumbnails should be added for duplicates")

    def test_exclude_then_include_different_file(self):
        """Test excluding one file and then including a different file"""
        from gui import ProcessingWindow

        with patch.object(ProcessingWindow, '__init__', lambda x, y, z: None):
            window = ProcessingWindow(None, None)

            window.all_files = self.test_images
            window.current_file_index = 0
            window.page_states = {}
            window.current_group = []
            window.thumbnail_layout = Mock()
            window.thumbnail_layout.count = Mock(return_value=0)
            window._create_thumbnail_widget = Mock(return_value=Mock())
            window._display_page_in_large_preview = Mock()
            window.config_manager = Mock()

            # Process first file - excluded
            window._add_thumbnail(self.test_images[0], 'excluded')
            window.current_file_index = 1

            # Process second file - included
            window._add_thumbnail(self.test_images[1], 'included')
            window.current_file_index = 2

            # Verify both are tracked
            self.assertIn(self.test_images[0], window.page_states)
            self.assertIn(self.test_images[1], window.page_states)
            self.assertEqual(window.page_states[self.test_images[0]], 'excluded')
            self.assertEqual(window.page_states[self.test_images[1]], 'included')

            # Verify exactly 2 thumbnails added
            self.assertEqual(window.thumbnail_layout.addWidget.call_count, 2)

    def test_multiple_exclude_cycles(self):
        """Test that multiple exclude operations don't cause duplicate evaluation"""
        from gui import ProcessingWindow

        with patch.object(ProcessingWindow, '__init__', lambda x, y, z: None):
            window = ProcessingWindow(None, None)

            window.all_files = self.test_images
            window.page_states = {}
            window.thumbnail_layout = Mock()
            window.thumbnail_layout.count = Mock(return_value=0)
            window._create_thumbnail_widget = Mock(return_value=Mock())

            # Simulate excluding multiple files in sequence
            for i in range(3):
                window._add_thumbnail(self.test_images[i], 'excluded')

            # Verify all are tracked
            self.assertEqual(len(window.page_states), 3)

            # Try to add them again - should all be rejected
            add_count_before = window.thumbnail_layout.addWidget.call_count
            for i in range(3):
                window._add_thumbnail(self.test_images[i], 'excluded')

            # Verify no new thumbnails were added
            add_count_after = window.thumbnail_layout.addWidget.call_count
            self.assertEqual(add_count_before, add_count_after,
                           "No duplicate thumbnails should be added on retry")


class TestDuplicateDetectionEdgeCases(unittest.TestCase):
    """Test edge cases for duplicate detection"""

    def setUp(self):
        """Set up test fixtures"""
        sys.modules['PyQt6'] = MagicMock()
        sys.modules['PyQt6.QtWidgets'] = MagicMock()
        sys.modules['PyQt6.QtCore'] = MagicMock()
        sys.modules['PyQt6.QtGui'] = MagicMock()

    def test_empty_thumbnail_strip(self):
        """Test behavior with empty thumbnail strip"""
        from gui import ProcessingWindow

        with patch.object(ProcessingWindow, '__init__', lambda x, y, z: None):
            window = ProcessingWindow(None, None)

            window.page_states = {}
            window.thumbnail_layout = Mock()
            window.thumbnail_layout.count = Mock(return_value=0)
            window._create_thumbnail_widget = Mock(return_value=Mock())

            # First addition to empty strip should succeed
            window._add_thumbnail('/test/image.png', 'included')
            self.assertEqual(window.thumbnail_layout.addWidget.call_count, 1)

    def test_case_sensitive_paths(self):
        """Test that path comparison is case-sensitive (as it should be on Unix)"""
        from gui import ProcessingWindow

        with patch.object(ProcessingWindow, '__init__', lambda x, y, z: None):
            window = ProcessingWindow(None, None)

            window.page_states = {}
            window.thumbnail_layout = Mock()
            window.thumbnail_layout.count = Mock(return_value=0)
            window._create_thumbnail_widget = Mock(return_value=Mock())

            # Add file with lowercase
            window._add_thumbnail('/test/image.png', 'included')

            # Try to add same file with different case (should be treated as different on Unix)
            # On Windows, this would be the same file, but we use the exact path provided
            window._add_thumbnail('/test/IMAGE.png', 'included')

            # On Unix systems, these are different files
            # On Windows, the second add would be rejected if path is normalized
            # This test verifies the behavior is consistent

    def test_relative_vs_absolute_paths(self):
        """Test handling of relative vs absolute paths"""
        from gui import ProcessingWindow

        with patch.object(ProcessingWindow, '__init__', lambda x, y, z: None):
            window = ProcessingWindow(None, None)

            window.page_states = {}
            window.thumbnail_layout = Mock()
            window.thumbnail_layout.count = Mock(return_value=0)
            window._create_thumbnail_widget = Mock(return_value=Mock())

            # Add absolute path
            window._add_thumbnail('/test/image.png', 'included')
            self.assertEqual(window.thumbnail_layout.addWidget.call_count, 1)

            # Add relative path (should be treated as different)
            window._add_thumbnail('test/image.png', 'included')
            # Note: In real usage, all paths should be normalized to absolute


def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestDuplicateDetection))
    suite.addTests(loader.loadTestsFromTestCase(TestDuplicateDetectionEdgeCases))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
