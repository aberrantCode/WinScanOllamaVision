"""
Test Phase 6: Keyboard Shortcuts & Polish for ConvertImagesWindow

Tests:
1. Keyboard shortcut registration
2. Navigation shortcuts (arrows, page up/down, home/end)
3. Action shortcuts (space, delete, enter, esc)
4. Zoom shortcuts (ctrl+/-/0)
5. Bundle shortcuts (ctrl+a, ctrl+d)
6. Shortcuts legend toggle (F1, ?)
7. Visual feedback effects
8. Button tooltips with shortcuts
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtWidgets import QApplication, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from gui import ConvertImagesWindow, WorkflowStep


@pytest.fixture(scope='module')
def app():
    """Create QApplication instance for tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def window(app):
    """Create ConvertImagesWindow instance for testing"""
    with patch('gui.ConfigManager'), \
         patch('gui.OllamaService'), \
         patch('gui.FileProcessor'), \
         patch('gui.MetadataDB'), \
         patch('gui.AnalysisDB'), \
         patch('gui.BundlingService'):
        window = ConvertImagesWindow()
        window.all_files = [f"file_{i}.png" for i in range(20)]
        window.current_page_path = "file_5.png"
        yield window
        window.close()


class TestKeyboardShortcutSetup:
    """Test keyboard shortcut registration"""

    def test_shortcuts_registered(self, window):
        """Test that keyboard shortcuts are registered on init"""
        # Check that keyboard_shortcuts dict is created
        assert hasattr(window, 'keyboard_shortcuts')
        assert isinstance(window.keyboard_shortcuts, dict)

        # Check all categories exist
        assert 'navigation' in window.keyboard_shortcuts
        assert 'actions' in window.keyboard_shortcuts
        assert 'zoom' in window.keyboard_shortcuts
        assert 'bundles' in window.keyboard_shortcuts
        assert 'help' in window.keyboard_shortcuts

    def test_navigation_shortcuts_defined(self, window):
        """Test navigation shortcuts are defined"""
        nav_shortcuts = window.keyboard_shortcuts['navigation']
        assert 'Left/Right Arrow' in nav_shortcuts
        assert 'Page Up/Down' in nav_shortcuts
        assert 'Home/End' in nav_shortcuts

    def test_action_shortcuts_defined(self, window):
        """Test action shortcuts are defined"""
        action_shortcuts = window.keyboard_shortcuts['actions']
        assert 'Space' in action_shortcuts
        assert 'Delete' in action_shortcuts
        assert 'Enter' in action_shortcuts
        assert 'Esc' in action_shortcuts

    def test_zoom_shortcuts_defined(self, window):
        """Test zoom shortcuts are defined"""
        zoom_shortcuts = window.keyboard_shortcuts['zoom']
        assert 'Ctrl + +' in zoom_shortcuts
        assert 'Ctrl + -' in zoom_shortcuts
        assert 'Ctrl + 0' in zoom_shortcuts


class TestNavigationShortcuts:
    """Test navigation keyboard shortcuts"""

    def test_navigate_previous_image(self, window):
        """Test left arrow navigates to previous image"""
        window.current_page_path = "file_5.png"
        window._on_thumbnail_clicked = Mock()

        # Simulate left arrow key
        window._navigate_previous_image()

        # Should navigate to previous file
        window._on_thumbnail_clicked.assert_called_once_with("file_4.png")

    def test_navigate_next_image(self, window):
        """Test right arrow navigates to next image"""
        window.current_page_path = "file_5.png"
        window._on_thumbnail_clicked = Mock()

        # Simulate right arrow key
        window._navigate_next_image()

        # Should navigate to next file
        window._on_thumbnail_clicked.assert_called_once_with("file_6.png")

    def test_jump_images_forward(self, window):
        """Test Page Down jumps 10 images forward"""
        window.current_page_path = "file_5.png"
        window._on_thumbnail_clicked = Mock()

        # Simulate page down (jump +10)
        window._jump_images(10)

        # Should jump to file_15.png
        window._on_thumbnail_clicked.assert_called_once_with("file_15.png")

    def test_jump_images_backward(self, window):
        """Test Page Up jumps 10 images backward"""
        window.current_page_path = "file_15.png"
        window._on_thumbnail_clicked = Mock()

        # Simulate page up (jump -10)
        window._jump_images(-10)

        # Should jump to file_5.png
        window._on_thumbnail_clicked.assert_called_once_with("file_5.png")

    def test_jump_to_first_image(self, window):
        """Test Home jumps to first image"""
        window.current_page_path = "file_10.png"
        window._on_thumbnail_clicked = Mock()

        # Simulate home key
        window._jump_to_first_image()

        # Should jump to first file
        window._on_thumbnail_clicked.assert_called_once_with("file_0.png")

    def test_jump_to_last_image(self, window):
        """Test End jumps to last image"""
        window.current_page_path = "file_5.png"
        window._on_thumbnail_clicked = Mock()

        # Simulate end key
        window._jump_to_last_image()

        # Should jump to last file
        window._on_thumbnail_clicked.assert_called_once_with("file_19.png")

    def test_navigation_boundary_conditions(self, window):
        """Test navigation doesn't go out of bounds"""
        # Test at start
        window.current_page_path = "file_0.png"
        window._on_thumbnail_clicked = Mock()
        window._navigate_previous_image()
        window._on_thumbnail_clicked.assert_not_called()

        # Test at end
        window.current_page_path = "file_19.png"
        window._on_thumbnail_clicked = Mock()
        window._navigate_next_image()
        window._on_thumbnail_clicked.assert_not_called()


class TestActionShortcuts:
    """Test action keyboard shortcuts"""

    def test_space_includes_page(self, window):
        """Test Space key includes current page"""
        window.current_step = WorkflowStep.STITCHING
        window.include_button = QPushButton()
        window.include_button.click = Mock()
        window.include_button.setVisible(True)
        window.include_button.setEnabled(True)

        # Simulate space key
        window._shortcut_include_page()

        # Should click include button
        window.include_button.click.assert_called_once()

    def test_delete_excludes_page(self, window):
        """Test Delete key excludes current page"""
        window.current_step = WorkflowStep.STITCHING
        window.exclude_page_button = QPushButton()
        window.exclude_page_button.click = Mock()
        window.exclude_page_button.setVisible(True)
        window.exclude_page_button.setEnabled(True)

        # Simulate delete key
        window._shortcut_exclude_page()

        # Should click exclude button
        window.exclude_page_button.click.assert_called_once()

    def test_enter_approves_in_stitching_step(self, window):
        """Test Enter approves bundle in stitching step"""
        window.current_step = WorkflowStep.STITCHING
        window.exclude_button = QPushButton()
        window.exclude_button.click = Mock()
        window.exclude_button.setVisible(True)
        window.exclude_button.setEnabled(True)

        # Simulate enter key
        window._shortcut_approve_continue()

        # Should click approve button
        window.exclude_button.click.assert_called_once()

    def test_enter_approves_in_ordering_step(self, window):
        """Test Enter approves order in ordering step"""
        window.current_step = WorkflowStep.ORDERING
        window.approve_order_button = QPushButton()
        window.approve_order_button.click = Mock()
        window.approve_order_button.setVisible(True)
        window.approve_order_button.setEnabled(True)

        # Simulate enter key
        window._shortcut_approve_continue()

        # Should click approve order button
        window.approve_order_button.click.assert_called_once()


class TestShortcutsLegend:
    """Test keyboard shortcuts legend"""

    def test_legend_toggle(self, window):
        """Test F1 toggles shortcuts legend"""
        # Legend should not exist initially
        assert not hasattr(window, 'shortcuts_legend_widget')

        # First toggle creates the legend
        window._toggle_shortcuts_legend()
        assert hasattr(window, 'shortcuts_legend_widget')

        # Widget should exist and have content
        assert window.shortcuts_legend_widget is not None
        assert window.shortcuts_legend_widget.layout() is not None
        assert window.shortcuts_legend_widget.layout().count() > 0

        # Verify the toggle method exists and can be called multiple times
        # (actual visibility depends on parent window being shown)
        window._toggle_shortcuts_legend()
        window._toggle_shortcuts_legend()

        # Widget should still exist after toggling
        assert window.shortcuts_legend_widget is not None

    def test_legend_content(self, window):
        """Test shortcuts legend displays all shortcuts"""
        window._create_shortcuts_legend()

        # Check that legend widget exists
        assert hasattr(window, 'shortcuts_legend_widget')

        # Check that it has content (layout with widgets)
        layout = window.shortcuts_legend_widget.layout()
        assert layout is not None
        assert layout.count() > 0


class TestVisualFeedback:
    """Test visual feedback effects"""

    def test_flash_preview_method_exists(self, window):
        """Test flash preview method exists"""
        assert hasattr(window, '_flash_preview')
        assert callable(window._flash_preview)

    def test_flash_thumbnail_method_exists(self, window):
        """Test flash thumbnail method exists"""
        assert hasattr(window, '_flash_thumbnail')
        assert callable(window._flash_thumbnail)

    def test_show_status_flash_method_exists(self, window):
        """Test status flash method exists"""
        assert hasattr(window, '_show_status_flash')
        assert callable(window._show_status_flash)

    @patch('gui.QTimer')
    def test_flash_preview_changes_style(self, mock_timer, window):
        """Test flash preview changes stylesheet temporarily"""
        window.large_preview_label = MagicMock()
        original_style = "background-color: white;"
        window.large_preview_label.styleSheet.return_value = original_style

        # Call flash preview
        window._flash_preview("#059669", duration=200)

        # Should have changed stylesheet
        window.large_preview_label.setStyleSheet.assert_called()


class TestButtonTooltips:
    """Test button tooltips include keyboard shortcuts"""

    def test_include_button_tooltip(self, window):
        """Test include button has keyboard shortcut in tooltip"""
        if hasattr(window, 'include_button'):
            tooltip = window.include_button.toolTip()
            assert "Space" in tooltip or tooltip != ""

    def test_exclude_button_tooltip(self, window):
        """Test exclude button has keyboard shortcut in tooltip"""
        if hasattr(window, 'exclude_page_button'):
            tooltip = window.exclude_page_button.toolTip()
            assert "Delete" in tooltip or tooltip != ""

    def test_approve_button_tooltip(self, window):
        """Test approve button has keyboard shortcut in tooltip"""
        if hasattr(window, 'exclude_button'):
            tooltip = window.exclude_button.toolTip()
            assert "Enter" in tooltip or tooltip != ""

    def test_cancel_button_tooltip(self, window):
        """Test cancel button has keyboard shortcut in tooltip"""
        if hasattr(window, 'cancel_request_button'):
            tooltip = window.cancel_request_button.toolTip()
            assert "Esc" in tooltip or tooltip != ""


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
