"""Tests for BundleReviewWindow UI component."""

import os
from unittest.mock import Mock, patch

import pytest

from ui.verify_documents_window import BundleReviewWindow


@pytest.fixture
def mock_config_manager():
    """Create a mock ConfigManager."""
    mock = Mock()

    # Set up default return values for Theme settings used in __init__
    def get_setting_default(section, key, default=None):
        if section == "Theme" and key == "default_zoom_mode_png":
            return "fit_to_width"
        elif section == "Theme" and key == "default_zoom_percent_png":
            return "100"
        return default

    mock.get_setting = Mock(side_effect=get_setting_default)
    return mock


@pytest.fixture
def workflow_instance(mock_config_manager):
    """
    Create a minimal BundleReviewWindow instance for testing.

    This creates an instance without calling __init__ to avoid Qt dependencies.
    We only need the _determine_output_directory method.
    """
    # Create instance without calling __init__
    workflow = BundleReviewWindow.__new__(BundleReviewWindow)
    workflow.config_manager = mock_config_manager
    return workflow


class TestDetermineOutputDirectory:
    """Tests for _determine_output_directory method."""

    def test_same_as_source_strategy(self, workflow_instance, mock_config_manager):
        """Test output directory with same_as_source strategy."""

        # Configure mock to return same_as_source strategy
        def get_setting_side_effect(section, key, default=None):
            if section == "OutputDirectory" and key == "strategy":
                return "same_as_source"
            elif section == "OutputDirectory" and key == "subdirectory_name":
                return "ORGANIZED"
            return default

        mock_config_manager.get_setting.side_effect = get_setting_side_effect

        bundle = {"file_paths": ["/test/source/dir/file1.png", "/test/source/dir/file2.png"]}

        result = workflow_instance._determine_output_directory(bundle)

        assert result == os.path.join("/test/source/dir", "ORGANIZED")

    def test_same_as_source_custom_subdirectory(self, workflow_instance, mock_config_manager):
        """Test output directory with custom subdirectory name."""

        # Configure mock to return same_as_source strategy with custom subdirectory
        def get_setting_side_effect(section, key, default=None):
            if section == "OutputDirectory" and key == "strategy":
                return "same_as_source"
            elif section == "OutputDirectory" and key == "subdirectory_name":
                return "MY_PDFS"
            return default

        mock_config_manager.get_setting.side_effect = get_setting_side_effect

        bundle = {"file_paths": ["/test/source/dir/file1.png", "/test/source/dir/file2.png"]}

        result = workflow_instance._determine_output_directory(bundle)

        assert result == os.path.join("/test/source/dir", "MY_PDFS")

    def test_global_custom_strategy_valid_path(self, workflow_instance, mock_config_manager):
        """Test output directory with global_custom strategy and valid path."""
        custom_path = "/custom/output/directory"

        # Configure mock to return global_custom strategy
        def get_setting_side_effect(section, key, default=None):
            if section == "OutputDirectory" and key == "strategy":
                return "global_custom"
            elif section == "OutputDirectory" and key == "global_custom_path":
                return custom_path
            return default

        mock_config_manager.get_setting.side_effect = get_setting_side_effect

        bundle = {"file_paths": ["/test/source/dir/file1.png", "/test/source/dir/file2.png"]}

        # Mock os.path.isdir to return True for custom path
        with patch("os.path.isdir") as mock_isdir:
            mock_isdir.return_value = True
            result = workflow_instance._determine_output_directory(bundle)

        assert result == custom_path

    def test_global_custom_strategy_invalid_path_fallback(
        self, workflow_instance, mock_config_manager
    ):
        """Test fallback when global_custom path is invalid."""
        custom_path = "/invalid/custom/path"

        # Configure mock to return global_custom strategy
        def get_setting_side_effect(section, key, default=None):
            if section == "OutputDirectory" and key == "strategy":
                return "global_custom"
            elif section == "OutputDirectory" and key == "global_custom_path":
                return custom_path
            return default

        mock_config_manager.get_setting.side_effect = get_setting_side_effect

        bundle = {"file_paths": ["/test/source/dir/file1.png", "/test/source/dir/file2.png"]}

        # Mock os.path.isdir to return False for custom path
        with patch("os.path.isdir") as mock_isdir:
            mock_isdir.return_value = False
            result = workflow_instance._determine_output_directory(bundle)

        # Should fall back to default
        expected_default = os.path.join(os.path.expanduser("~"), "Documents", "WinScanLLM", "PDFs")
        assert result == expected_default

    def test_global_custom_strategy_empty_path_fallback(
        self, workflow_instance, mock_config_manager
    ):
        """Test fallback when global_custom path is empty."""

        # Configure mock to return global_custom strategy with empty path
        def get_setting_side_effect(section, key, default=None):
            if section == "OutputDirectory" and key == "strategy":
                return "global_custom"
            elif section == "OutputDirectory" and key == "global_custom_path":
                return ""
            return default

        mock_config_manager.get_setting.side_effect = get_setting_side_effect

        bundle = {"file_paths": ["/test/source/dir/file1.png", "/test/source/dir/file2.png"]}

        result = workflow_instance._determine_output_directory(bundle)

        # Should fall back to default
        expected_default = os.path.join(os.path.expanduser("~"), "Documents", "WinScanLLM", "PDFs")
        assert result == expected_default

    def test_unknown_strategy_fallback(self, workflow_instance, mock_config_manager):
        """Test fallback to default with unknown strategy."""

        # Configure mock to return unknown strategy
        def get_setting_side_effect(section, key, default=None):
            if section == "OutputDirectory" and key == "strategy":
                return "unknown_strategy"
            return default

        mock_config_manager.get_setting.side_effect = get_setting_side_effect

        bundle = {"file_paths": ["/test/source/dir/file1.png", "/test/source/dir/file2.png"]}

        result = workflow_instance._determine_output_directory(bundle)

        # Should fall back to default
        expected_default = os.path.join(os.path.expanduser("~"), "Documents", "WinScanLLM", "PDFs")
        assert result == expected_default

    def test_same_as_source_empty_file_paths_fallback(self, workflow_instance, mock_config_manager):
        """Test fallback when bundle has no file_paths."""

        # Configure mock to return same_as_source strategy
        def get_setting_side_effect(section, key, default=None):
            if section == "OutputDirectory" and key == "strategy":
                return "same_as_source"
            return default

        mock_config_manager.get_setting.side_effect = get_setting_side_effect

        bundle = {"file_paths": []}

        result = workflow_instance._determine_output_directory(bundle)

        # Should fall back to default
        expected_default = os.path.join(os.path.expanduser("~"), "Documents", "WinScanLLM", "PDFs")
        assert result == expected_default
