"""Tests for BundlePdfConverter — output directory resolution logic.

Moved from tests/ui/test_guided_bundle_workflow.py as part of the bundle
package refactor.  Tests exercise BundlePdfConverter directly rather than
through GuidedBundleWorkflow.__new__().
"""

import os
from unittest.mock import Mock, patch

import pytest

from ui.bundle.bundle_pdf_converter import BundlePdfConverter


@pytest.fixture
def mock_config_manager():
    """ConfigManager mock with sensible defaults."""
    mock = Mock()
    mock.get_setting.return_value = None
    return mock


@pytest.fixture
def converter(mock_config_manager):
    return BundlePdfConverter(
        config_manager=mock_config_manager,
        analysis_db=None,
    )


class TestDetermineOutputDirectory:
    def test_same_as_source_strategy(self, converter, mock_config_manager):
        def side_effect(section, key, default=None):
            if section == "OutputDirectory" and key == "strategy":
                return "same_as_source"
            if section == "OutputDirectory" and key == "subdirectory_name":
                return "ORGANIZED"
            return default

        mock_config_manager.get_setting.side_effect = side_effect

        bundle = {"file_paths": ["/test/source/dir/file1.png"]}
        result = converter.determine_output_directory(bundle)
        assert result == os.path.join("/test/source/dir", "ORGANIZED")

    def test_same_as_source_custom_subdirectory(self, converter, mock_config_manager):
        def side_effect(section, key, default=None):
            if section == "OutputDirectory" and key == "strategy":
                return "same_as_source"
            if section == "OutputDirectory" and key == "subdirectory_name":
                return "MY_PDFS"
            return default

        mock_config_manager.get_setting.side_effect = side_effect

        bundle = {"file_paths": ["/test/source/dir/file1.png"]}
        result = converter.determine_output_directory(bundle)
        assert result == os.path.join("/test/source/dir", "MY_PDFS")

    def test_global_custom_strategy_valid_path(self, converter, mock_config_manager):
        custom_path = "/custom/output/directory"

        def side_effect(section, key, default=None):
            if section == "OutputDirectory" and key == "strategy":
                return "global_custom"
            if section == "OutputDirectory" and key == "global_custom_path":
                return custom_path
            return default

        mock_config_manager.get_setting.side_effect = side_effect

        bundle = {"file_paths": ["/test/source/dir/file1.png"]}
        with patch("os.path.isdir", return_value=True):
            result = converter.determine_output_directory(bundle)
        assert result == custom_path

    def test_global_custom_strategy_invalid_path_fallback(self, converter, mock_config_manager):
        def side_effect(section, key, default=None):
            if section == "OutputDirectory" and key == "strategy":
                return "global_custom"
            if section == "OutputDirectory" and key == "global_custom_path":
                return "/invalid/custom/path"
            return default

        mock_config_manager.get_setting.side_effect = side_effect

        bundle = {"file_paths": ["/test/source/dir/file1.png"]}
        with patch("os.path.isdir", return_value=False):
            result = converter.determine_output_directory(bundle)

        expected = os.path.join(os.path.expanduser("~"), "Documents", "WinScanLLM", "PDFs")
        assert result == expected

    def test_global_custom_strategy_empty_path_fallback(self, converter, mock_config_manager):
        def side_effect(section, key, default=None):
            if section == "OutputDirectory" and key == "strategy":
                return "global_custom"
            if section == "OutputDirectory" and key == "global_custom_path":
                return ""
            return default

        mock_config_manager.get_setting.side_effect = side_effect

        bundle = {"file_paths": ["/test/source/dir/file1.png"]}
        result = converter.determine_output_directory(bundle)

        expected = os.path.join(os.path.expanduser("~"), "Documents", "WinScanLLM", "PDFs")
        assert result == expected

    def test_unknown_strategy_fallback(self, converter, mock_config_manager):
        def side_effect(section, key, default=None):
            if section == "OutputDirectory" and key == "strategy":
                return "unknown_strategy"
            return default

        mock_config_manager.get_setting.side_effect = side_effect

        bundle = {"file_paths": ["/test/source/dir/file1.png"]}
        result = converter.determine_output_directory(bundle)

        expected = os.path.join(os.path.expanduser("~"), "Documents", "WinScanLLM", "PDFs")
        assert result == expected

    def test_same_as_source_empty_file_paths_fallback(self, converter, mock_config_manager):
        def side_effect(section, key, default=None):
            if section == "OutputDirectory" and key == "strategy":
                return "same_as_source"
            return default

        mock_config_manager.get_setting.side_effect = side_effect

        bundle = {"file_paths": []}
        result = converter.determine_output_directory(bundle)

        expected = os.path.join(os.path.expanduser("~"), "Documents", "WinScanLLM", "PDFs")
        assert result == expected

    def test_beside_source_strategy(self, converter, mock_config_manager):
        def side_effect(section, key, default=None):
            if section == "OutputDirectory" and key == "strategy":
                return "beside_source"
            return default

        mock_config_manager.get_setting.side_effect = side_effect

        bundle = {"file_paths": ["/test/source/dir/file1.png"]}
        result = converter.determine_output_directory(bundle)
        assert result == "/test/source/dir"

    def test_beside_source_empty_paths_fallback(self, converter, mock_config_manager):
        def side_effect(section, key, default=None):
            if section == "OutputDirectory" and key == "strategy":
                return "beside_source"
            return default

        mock_config_manager.get_setting.side_effect = side_effect

        bundle = {"file_paths": []}
        result = converter.determine_output_directory(bundle)

        expected = os.path.join(os.path.expanduser("~"), "Documents", "WinScanLLM", "PDFs")
        assert result == expected


class TestFormatFileSize:
    def test_bytes(self):
        assert BundlePdfConverter.format_file_size(512) == "512.0 B"

    def test_kilobytes(self):
        assert BundlePdfConverter.format_file_size(1024) == "1.0 KB"

    def test_megabytes(self):
        assert BundlePdfConverter.format_file_size(1024 * 1024) == "1.0 MB"

    def test_gigabytes(self):
        assert BundlePdfConverter.format_file_size(1024**3) == "1.0 GB"

    def test_float_input(self):
        result = BundlePdfConverter.format_file_size(1536.0)
        assert "KB" in result
