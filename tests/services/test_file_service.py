"""
Comprehensive tests for FileService.

Tests file operations, image conversion, PDF creation, and file management.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from services.file_service import FileService


class TestFileServiceInitialization:
    """Tests for FileService initialization"""

    @pytest.fixture
    def mock_config_manager(self):
        """Create mock ConfigManager"""
        config = MagicMock()
        config.get_setting.side_effect = lambda section, key: {
            ("DocumentProcessing", "scan_folder"): "C:\\test\\scan",
            ("DocumentProcessing", "organized_subfolder"): "organized",
        }.get((section, key), "default_value")
        return config

    def test_init_stores_config_manager(self, mock_config_manager):
        # Act
        service = FileService(mock_config_manager)

        # Assert
        assert service.config_manager is mock_config_manager

    def test_init_sets_scan_folder(self, mock_config_manager):
        # Act
        service = FileService(mock_config_manager)

        # Assert
        assert service.scan_folder == "C:\\test\\scan"

    def test_init_sets_organized_folder(self, mock_config_manager):
        # Act
        service = FileService(mock_config_manager)

        # Assert
        expected_path = os.path.join("C:\\test\\scan", "organized")
        assert service.organized_folder == expected_path

    @patch("os.makedirs")
    def test_init_creates_scan_folder_if_missing(self, mock_makedirs, mock_config_manager):
        # Act
        FileService(mock_config_manager)

        # Assert
        mock_makedirs.assert_any_call("C:\\test\\scan", exist_ok=True)

    @patch("os.makedirs")
    def test_init_creates_organized_folder_if_missing(self, mock_makedirs, mock_config_manager):
        # Act
        FileService(mock_config_manager)

        # Assert
        expected_path = os.path.join("C:\\test\\scan", "organized")
        mock_makedirs.assert_any_call(expected_path, exist_ok=True)

    @patch("os.makedirs")
    def test_init_always_calls_makedirs_with_exist_ok(self, mock_makedirs, mock_config_manager):
        # Act
        FileService(mock_config_manager)

        # Assert - both folders should be created with exist_ok=True
        assert mock_makedirs.call_count == 2
        calls = [
            call("C:\\test\\scan", exist_ok=True),
            call(os.path.join("C:\\test\\scan", "organized"), exist_ok=True),
        ]
        mock_makedirs.assert_has_calls(calls, any_order=False)


class TestGetImageFiles:
    """Tests for _get_image_files method"""

    @pytest.fixture
    def mock_config_manager(self):
        config = MagicMock()
        config.get_setting.side_effect = lambda section, key: {
            ("DocumentProcessing", "scan_folder"): "C:\\test\\scan",
            ("DocumentProcessing", "organized_subfolder"): "organized",
        }.get((section, key), "default_value")
        return config

    @pytest.fixture
    def service(self, mock_config_manager):
        with patch("os.path.exists", return_value=True), patch("os.makedirs"):
            return FileService(mock_config_manager)

    @patch("os.listdir")
    @patch("os.path.isfile")
    def test_get_image_files_returns_png_files(self, mock_isfile, mock_listdir, service):
        # Arrange
        mock_listdir.return_value = ["file1.png", "file2.jpg", "file3.png"]
        mock_isfile.return_value = True

        # Act
        result = service._get_image_files()

        # Assert
        expected = [
            os.path.join(service.scan_folder, "file1.png"),
            os.path.join(service.scan_folder, "file3.png"),
        ]
        assert result == expected

    @patch("os.listdir")
    @patch("os.path.isfile")
    def test_get_image_files_excludes_non_files(self, mock_isfile, mock_listdir, service):
        # Arrange
        mock_listdir.return_value = ["file1.png", "subfolder", "file2.png"]
        mock_isfile.side_effect = lambda path: "file" in os.path.basename(path)

        # Act
        result = service._get_image_files()

        # Assert
        assert len(result) == 2
        assert all("file" in os.path.basename(f) for f in result)

    @patch("os.listdir")
    @patch("os.path.isfile")
    def test_get_image_files_converts_tiff_to_png(self, mock_isfile, mock_listdir, service):
        # Arrange
        mock_listdir.return_value = ["file1.tiff", "file2.png"]
        mock_isfile.return_value = True

        with patch.object(service, "_convert_tiff_to_png") as mock_convert:
            mock_convert.return_value = "C:\\test\\scan\\file1.png"

            # Act
            result = service._get_image_files()

            # Assert
            mock_convert.assert_called_once_with(os.path.join(service.scan_folder, "file1.tiff"))
            assert "file1.png" in result[0]

    @patch("os.listdir")
    def test_get_image_files_returns_empty_for_empty_directory(self, mock_listdir, service):
        # Arrange
        mock_listdir.return_value = []

        # Act
        result = service._get_image_files()

        # Assert
        assert result == []

    @patch("os.listdir")
    @patch("os.path.isfile")
    def test_get_image_files_handles_mixed_extensions(self, mock_isfile, mock_listdir, service):
        # Arrange
        mock_listdir.return_value = [
            "file1.PNG",
            "file2.TIF",
            "file3.jpg",
            "file4.pdf",
        ]
        mock_isfile.return_value = True

        with patch.object(service, "_convert_tiff_to_png") as mock_convert:
            mock_convert.return_value = "C:\\test\\scan\\file2.png"

            # Act
            result = service._get_image_files()

            # Assert
            assert len(result) == 2  # PNG + converted TIFF
            assert any("file1.PNG" in f for f in result)
            assert any("file2.png" in f for f in result)


class TestConvertTiffToPng:
    """Tests for _convert_tiff_to_png method"""

    @pytest.fixture
    def mock_config_manager(self):
        config = MagicMock()
        config.get_setting.side_effect = lambda section, key: {
            ("DocumentProcessing", "scan_folder"): "C:\\test\\scan",
            ("DocumentProcessing", "organized_subfolder"): "organized",
        }.get((section, key), "default_value")
        return config

    @pytest.fixture
    def service(self, mock_config_manager):
        with patch("os.path.exists", return_value=True), patch("os.makedirs"):
            return FileService(mock_config_manager)

    @patch("os.remove")
    @patch("PIL.Image.open")
    def test_convert_tiff_to_png_creates_png_file(self, mock_image_open, mock_remove, service):
        # Arrange
        mock_image = MagicMock()
        mock_image_open.return_value.__enter__ = MagicMock(return_value=mock_image)
        mock_image_open.return_value.__exit__ = MagicMock(return_value=False)
        tiff_path = "C:\\test\\scan\\file.tiff"

        # Act
        result = service._convert_tiff_to_png(tiff_path)

        # Assert
        expected_png = "C:\\test\\scan\\file.png"
        assert result == expected_png
        mock_image.save.assert_called_once_with(expected_png, "PNG")

    @patch("os.remove")
    @patch("PIL.Image.open")
    def test_convert_tiff_to_png_deletes_original(self, mock_image_open, mock_remove, service):
        # Arrange
        mock_image = MagicMock()
        mock_image_open.return_value = mock_image
        tiff_path = "C:\\test\\scan\\file.tiff"

        # Act
        service._convert_tiff_to_png(tiff_path)

        # Assert
        mock_remove.assert_called_once_with(tiff_path)

    @patch("os.remove")
    @patch("PIL.Image.open")
    def test_convert_tiff_to_png_handles_tif_extension(self, mock_image_open, mock_remove, service):
        # Arrange
        mock_image = MagicMock()
        mock_image_open.return_value = mock_image
        tiff_path = "C:\\test\\scan\\file.tif"

        # Act
        result = service._convert_tiff_to_png(tiff_path)

        # Assert
        expected_png = "C:\\test\\scan\\file.png"
        assert result == expected_png

    @patch("os.remove")
    @patch("PIL.Image.open")
    def test_convert_tiff_to_png_handles_uppercase_extension(
        self, mock_image_open, mock_remove, service
    ):
        # Arrange
        mock_image = MagicMock()
        mock_image_open.return_value = mock_image
        tiff_path = "C:\\test\\scan\\file.TIFF"

        # Act
        result = service._convert_tiff_to_png(tiff_path)

        # Assert
        expected_png = "C:\\test\\scan\\file.png"
        assert result == expected_png


class TestGroupFilesByTimestamp:
    """Tests for group_files_by_timestamp method"""

    @pytest.fixture
    def mock_config_manager(self):
        config = MagicMock()
        config.get_setting.side_effect = lambda section, key: {
            ("DocumentProcessing", "scan_folder"): "C:\\test\\scan",
            ("DocumentProcessing", "organized_subfolder"): "organized",
        }.get((section, key), "default_value")
        return config

    @pytest.fixture
    def service(self, mock_config_manager):
        with patch("os.path.exists", return_value=True), patch("os.makedirs"):
            return FileService(mock_config_manager)

    @pytest.fixture
    def temp_files(self):
        """Create temporary test files with known timestamps"""
        temp_dir = tempfile.mkdtemp()
        files = []

        # Create 3 files with different timestamps
        for i in range(3):
            file_path = os.path.join(temp_dir, f"file{i}.png")
            Path(file_path).touch()
            files.append(file_path)

        yield temp_dir, files

        # Cleanup
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_group_files_by_timestamp_returns_list_of_lists(self, service, temp_files):
        # Arrange
        temp_dir, files = temp_files

        # Act
        result = service.group_files_by_timestamp(files, time_delta_seconds=10)

        # Assert
        assert isinstance(result, list)
        assert all(isinstance(group, list) for group in result)

    def test_group_files_by_timestamp_groups_close_timestamps(self, service):
        # Arrange
        with patch("os.path.getmtime") as mock_getmtime:
            # Files with timestamps 0, 1, 10 seconds
            mock_getmtime.side_effect = [0.0, 1.0, 10.0]
            files = ["file1.png", "file2.png", "file3.png"]

            # Act
            result = service.group_files_by_timestamp(files, time_delta_seconds=5)

            # Assert
            assert len(result) == 2  # Two groups
            assert len(result[0]) == 2  # file1 and file2 grouped
            assert len(result[1]) == 1  # file3 separate

    def test_group_files_by_timestamp_single_file(self, service):
        # Arrange
        with patch("os.path.getmtime") as mock_getmtime:
            mock_getmtime.return_value = 0.0
            files = ["file1.png"]

            # Act
            result = service.group_files_by_timestamp(files, time_delta_seconds=5)

            # Assert
            assert len(result) == 1
            assert result[0] == ["file1.png"]

    def test_group_files_by_timestamp_empty_list(self, service):
        # Act
        result = service.group_files_by_timestamp([], time_delta_seconds=5)

        # Assert
        assert result == []

    def test_group_files_by_timestamp_respects_time_delta(self, service):
        # Arrange
        with patch("os.path.getmtime") as mock_getmtime:
            # Files at 0, 3, 6 seconds
            mock_getmtime.side_effect = [0.0, 3.0, 6.0]
            files = ["file1.png", "file2.png", "file3.png"]

            # Act with 2 second delta - should create 3 groups
            result = service.group_files_by_timestamp(files, time_delta_seconds=2)

            # Assert
            assert len(result) == 3

    def test_group_files_by_timestamp_sorts_by_time(self, service):
        # Arrange
        with patch("os.path.getmtime") as mock_getmtime:
            # Files with out-of-order timestamps
            mock_getmtime.side_effect = [10.0, 5.0, 15.0]
            files = ["file1.png", "file2.png", "file3.png"]

            # Act
            result = service.group_files_by_timestamp(files, time_delta_seconds=10)

            # Assert - should be sorted by timestamp
            assert result[0][0] == "file2.png"  # Earliest timestamp (5.0)


class TestCreateSearchablePdf:
    """Tests for create_searchable_pdf method"""

    @pytest.fixture
    def mock_config_manager(self):
        config = MagicMock()
        config.get_setting.side_effect = lambda section, key: {
            ("DocumentProcessing", "scan_folder"): "C:\\test\\scan",
            ("DocumentProcessing", "organized_subfolder"): "organized",
        }.get((section, key), "default_value")
        return config

    @pytest.fixture
    def service(self, mock_config_manager):
        with patch("os.path.exists", return_value=True), patch("os.makedirs"):
            return FileService(mock_config_manager)

    @patch("fitz.open")
    @patch("PIL.Image.open")
    def test_create_searchable_pdf_creates_pdf(self, mock_image_open, mock_fitz_open, service):
        # Arrange
        mock_doc = MagicMock()
        mock_doc.page_count = 2
        mock_fitz_open.return_value = mock_doc

        mock_image = MagicMock()
        mock_image.width = 800
        mock_image.height = 600
        mock_image_open.return_value.__enter__ = MagicMock(return_value=mock_image)
        mock_image_open.return_value.__exit__ = MagicMock(return_value=False)

        image_files = ["file1.png", "file2.png"]
        output_filename = "output.pdf"
        extracted_text_coords = {"pages": []}

        # Act
        result = service.create_searchable_pdf(image_files, output_filename, extracted_text_coords)

        # Assert
        expected_output = os.path.join(service.organized_folder, output_filename)
        mock_fitz_open.assert_called_once()
        mock_doc.save.assert_called_once_with(expected_output)
        mock_doc.close.assert_called_once()
        assert result == expected_output

    @patch("fitz.open")
    @patch("PIL.Image.open")
    def test_create_searchable_pdf_adds_pages_for_each_image(
        self, mock_image_open, mock_fitz_open, service
    ):
        # Arrange
        mock_doc = MagicMock()
        mock_doc.page_count = 3
        mock_page = MagicMock()
        mock_doc.new_page.return_value = mock_page
        mock_fitz_open.return_value = mock_doc

        mock_image = MagicMock()
        mock_image.width = 800
        mock_image.height = 600
        mock_image_open.return_value.__enter__ = MagicMock(return_value=mock_image)
        mock_image_open.return_value.__exit__ = MagicMock(return_value=False)

        image_files = ["file1.png", "file2.png", "file3.png"]
        extracted_text_coords = {"pages": []}

        # Act
        service.create_searchable_pdf(image_files, "output.pdf", extracted_text_coords)

        # Assert
        assert mock_doc.new_page.call_count == 3

    @patch("fitz.open")
    @patch("PIL.Image.open")
    def test_create_searchable_pdf_sets_page_size_from_image(
        self, mock_image_open, mock_fitz_open, service
    ):
        # Arrange
        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_page = MagicMock()
        mock_doc.new_page.return_value = mock_page
        mock_fitz_open.return_value = mock_doc

        mock_image = MagicMock()
        mock_image.width = 800
        mock_image.height = 600
        mock_image_open.return_value.__enter__ = MagicMock(return_value=mock_image)
        mock_image_open.return_value.__exit__ = MagicMock(return_value=False)

        image_files = ["file1.png"]
        extracted_text_coords = {"pages": []}

        # Act
        service.create_searchable_pdf(image_files, "output.pdf", extracted_text_coords)

        # Assert
        # Page size should be set based on image dimensions
        mock_doc.new_page.assert_called_once()
        call_args = mock_doc.new_page.call_args
        assert "width" in call_args.kwargs or len(call_args.args) >= 1

    @patch("fitz.open")
    @patch("PIL.Image.open")
    def test_create_searchable_pdf_inserts_image(self, mock_image_open, mock_fitz_open, service):
        # Arrange
        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_page = MagicMock()
        mock_doc.new_page.return_value = mock_page
        mock_fitz_open.return_value = mock_doc

        mock_image = MagicMock()
        mock_image.width = 800
        mock_image.height = 600
        mock_image_open.return_value.__enter__ = MagicMock(return_value=mock_image)
        mock_image_open.return_value.__exit__ = MagicMock(return_value=False)

        image_files = ["file1.png"]
        extracted_text_coords = {"pages": []}

        # Act
        service.create_searchable_pdf(image_files, "output.pdf", extracted_text_coords)

        # Assert
        mock_page.insert_image.assert_called_once()

    @patch("fitz.open")
    @patch("PIL.Image.open")
    def test_create_searchable_pdf_adds_text_layer_when_provided(
        self, mock_image_open, mock_fitz_open, service
    ):
        # Arrange
        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_page = MagicMock()
        mock_doc.new_page.return_value = mock_page
        mock_fitz_open.return_value = mock_doc

        mock_image = MagicMock()
        mock_image.width = 800
        mock_image.height = 600
        mock_image_open.return_value.__enter__ = MagicMock(return_value=mock_image)
        mock_image_open.return_value.__exit__ = MagicMock(return_value=False)

        image_files = ["file1.png"]
        extracted_text_coords = {
            "pages": [
                {
                    "page_number": 1,
                    "elements": [{"text": "Sample text content", "bbox": [10, 10, 100, 30]}],
                }
            ]
        }

        # Act
        service.create_searchable_pdf(
            image_files, "output.pdf", extracted_text_coords, is_searchable=True
        )

        # Assert
        mock_page.insert_textbox.assert_called_once()
        call_args = mock_page.insert_textbox.call_args
        assert "Sample text content" in str(call_args)

    @patch("fitz.open")
    @patch("PIL.Image.open")
    def test_create_searchable_pdf_skips_text_when_not_searchable(
        self, mock_image_open, mock_fitz_open, service
    ):
        # Arrange
        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_page = MagicMock()
        mock_doc.new_page.return_value = mock_page
        mock_fitz_open.return_value = mock_doc

        mock_image = MagicMock()
        mock_image.width = 800
        mock_image.height = 600
        mock_image_open.return_value.__enter__ = MagicMock(return_value=mock_image)
        mock_image_open.return_value.__exit__ = MagicMock(return_value=False)

        image_files = ["file1.png"]
        extracted_text_coords = {"pages": []}

        # Act
        service.create_searchable_pdf(
            image_files, "output.pdf", extracted_text_coords, is_searchable=False
        )

        # Assert
        mock_page.insert_textbox.assert_not_called()

    @patch("os.remove")
    @patch("tempfile.NamedTemporaryFile")
    @patch("fitz.open")
    @patch("PIL.Image.open")
    def test_create_searchable_pdf_handles_rotation_90(
        self, mock_image_open, mock_fitz_open, mock_tempfile, mock_remove, service
    ):
        # Arrange
        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_page = MagicMock()
        mock_doc.new_page.return_value = mock_page
        mock_fitz_open.return_value = mock_doc

        mock_image = MagicMock()
        mock_image.width = 800
        mock_image.height = 600
        mock_image.rotate.return_value = mock_image
        mock_image_open.return_value.__enter__ = MagicMock(return_value=mock_image)
        mock_image_open.return_value.__exit__ = MagicMock(return_value=False)

        mock_temp = MagicMock()
        mock_temp.name = "C:\\temp\\file.png"
        mock_tempfile.return_value.__enter__ = MagicMock(return_value=mock_temp)
        mock_tempfile.return_value.__exit__ = MagicMock(return_value=False)

        image_files = ["file1.png"]
        extracted_text_coords = {"pages": []}
        rotation_map = {"file1.png": 90}

        # Act
        service.create_searchable_pdf(
            image_files, "output.pdf", extracted_text_coords, rotation_map=rotation_map
        )

        # Assert
        mock_image.rotate.assert_called_once_with(-90, expand=True)

    @patch("os.remove")
    @patch("tempfile.NamedTemporaryFile")
    @patch("fitz.open")
    @patch("PIL.Image.open")
    def test_create_searchable_pdf_handles_rotation_180(
        self, mock_image_open, mock_fitz_open, mock_tempfile, mock_remove, service
    ):
        # Arrange
        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_page = MagicMock()
        mock_doc.new_page.return_value = mock_page
        mock_fitz_open.return_value = mock_doc

        mock_image = MagicMock()
        mock_image.width = 800
        mock_image.height = 600
        mock_image.rotate.return_value = mock_image
        mock_image_open.return_value.__enter__ = MagicMock(return_value=mock_image)
        mock_image_open.return_value.__exit__ = MagicMock(return_value=False)

        mock_temp = MagicMock()
        mock_temp.name = "C:\\temp\\file.png"
        mock_tempfile.return_value.__enter__ = MagicMock(return_value=mock_temp)
        mock_tempfile.return_value.__exit__ = MagicMock(return_value=False)

        image_files = ["file1.png"]
        extracted_text_coords = {"pages": []}
        rotation_map = {"file1.png": 180}

        # Act
        service.create_searchable_pdf(
            image_files, "output.pdf", extracted_text_coords, rotation_map=rotation_map
        )

        # Assert
        mock_image.rotate.assert_called_once_with(180, expand=True)

    @patch("os.remove")
    @patch("tempfile.NamedTemporaryFile")
    @patch("fitz.open")
    @patch("PIL.Image.open")
    def test_create_searchable_pdf_handles_rotation_270(
        self, mock_image_open, mock_fitz_open, mock_tempfile, mock_remove, service
    ):
        # Arrange
        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_page = MagicMock()
        mock_doc.new_page.return_value = mock_page
        mock_fitz_open.return_value = mock_doc

        mock_image = MagicMock()
        mock_image.width = 800
        mock_image.height = 600
        mock_image.rotate.return_value = mock_image
        mock_image_open.return_value.__enter__ = MagicMock(return_value=mock_image)
        mock_image_open.return_value.__exit__ = MagicMock(return_value=False)

        mock_temp = MagicMock()
        mock_temp.name = "C:\\temp\\file.png"
        mock_tempfile.return_value.__enter__ = MagicMock(return_value=mock_temp)
        mock_tempfile.return_value.__exit__ = MagicMock(return_value=False)

        image_files = ["file1.png"]
        extracted_text_coords = {"pages": []}
        rotation_map = {"file1.png": 270}

        # Act
        service.create_searchable_pdf(
            image_files, "output.pdf", extracted_text_coords, rotation_map=rotation_map
        )

        # Assert
        mock_image.rotate.assert_called_once_with(90, expand=True)

    @patch("fitz.open")
    @patch("PIL.Image.open")
    def test_create_searchable_pdf_no_rotation_by_default(
        self, mock_image_open, mock_fitz_open, service
    ):
        # Arrange
        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_page = MagicMock()
        mock_doc.new_page.return_value = mock_page
        mock_fitz_open.return_value = mock_doc

        mock_image = MagicMock()
        mock_image.width = 800
        mock_image.height = 600
        mock_image_open.return_value.__enter__ = MagicMock(return_value=mock_image)
        mock_image_open.return_value.__exit__ = MagicMock(return_value=False)

        image_files = ["file1.png"]
        extracted_text_coords = {"pages": []}

        # Act
        service.create_searchable_pdf(image_files, "output.pdf", extracted_text_coords)

        # Assert
        # Image.rotate should not be called when no rotation_map is provided
        mock_image.rotate.assert_not_called()


class TestDeleteFiles:
    """Tests for delete_files method"""

    @pytest.fixture
    def mock_config_manager(self):
        config = MagicMock()
        config.get_setting.side_effect = lambda section, key: {
            ("DocumentProcessing", "scan_folder"): "C:\\test\\scan",
            ("DocumentProcessing", "organized_subfolder"): "organized",
        }.get((section, key), "default_value")
        return config

    @pytest.fixture
    def service(self, mock_config_manager):
        with patch("os.path.exists", return_value=True), patch("os.makedirs"):
            return FileService(mock_config_manager)

    @patch("os.remove")
    def test_delete_files_removes_all_files(self, mock_remove, service):
        # Arrange
        files = ["file1.png", "file2.png", "file3.png"]

        # Act
        service.delete_files(files)

        # Assert
        assert mock_remove.call_count == 3
        mock_remove.assert_any_call("file1.png")
        mock_remove.assert_any_call("file2.png")
        mock_remove.assert_any_call("file3.png")

    @patch("os.remove")
    def test_delete_files_handles_empty_list(self, mock_remove, service):
        # Act
        service.delete_files([])

        # Assert
        mock_remove.assert_not_called()

    @patch("os.remove")
    def test_delete_files_continues_on_error(self, mock_remove, service):
        # Arrange
        mock_remove.side_effect = [None, OSError("Permission denied"), None]
        files = ["file1.png", "file2.png", "file3.png"]

        # Act - should not raise exception
        service.delete_files(files)

        # Assert - all files attempted
        assert mock_remove.call_count == 3

    @patch("os.remove")
    def test_delete_files_handles_nonexistent_file(self, mock_remove, service):
        # Arrange
        mock_remove.side_effect = FileNotFoundError("File not found")
        files = ["nonexistent.png"]

        # Act - should not raise exception
        service.delete_files(files)

        # Assert
        mock_remove.assert_called_once_with("nonexistent.png")


class TestMovePdfToOrganized:
    """Tests for move_pdf_to_organized method"""

    @pytest.fixture
    def mock_config_manager(self):
        config = MagicMock()
        config.get_setting.side_effect = lambda section, key: {
            ("DocumentProcessing", "scan_folder"): "C:\\test\\scan",
            ("DocumentProcessing", "organized_subfolder"): "organized",
        }.get((section, key), "default_value")
        return config

    @pytest.fixture
    def service(self, mock_config_manager):
        with patch("os.path.exists", return_value=True), patch("os.makedirs"):
            return FileService(mock_config_manager)

    @patch("shutil.move")
    def test_move_pdf_to_organized_moves_file(self, mock_move, service):
        # Arrange
        pdf_path = "C:\\test\\scan\\document.pdf"
        new_filename = "new_document.pdf"

        # Act
        result = service.move_pdf_to_organized(pdf_path, new_filename)

        # Assert
        expected_dest = os.path.join(service.organized_folder, new_filename)
        mock_move.assert_called_once_with(pdf_path, expected_dest)
        assert result == expected_dest

    @patch("shutil.move")
    def test_move_pdf_to_organized_uses_new_filename(self, mock_move, service):
        # Arrange
        pdf_path = "C:\\test\\scan\\old_document.pdf"
        new_filename = "my_special_document.pdf"

        # Act
        result = service.move_pdf_to_organized(pdf_path, new_filename)

        # Assert
        assert "my_special_document.pdf" in result

    @patch("shutil.move")
    def test_move_pdf_to_organized_uses_organized_folder(self, mock_move, service):
        # Arrange
        pdf_path = "C:\\test\\scan\\document.pdf"
        new_filename = "document.pdf"

        # Act
        result = service.move_pdf_to_organized(pdf_path, new_filename)

        # Assert
        assert result.startswith(service.organized_folder)

    @patch("shutil.move")
    def test_move_pdf_to_organized_handles_move_error(self, mock_move, service):
        # Arrange
        mock_move.side_effect = OSError("Permission denied")
        pdf_path = "C:\\test\\scan\\document.pdf"
        new_filename = "document.pdf"

        # Act - should return None on error
        result = service.move_pdf_to_organized(pdf_path, new_filename)

        # Assert
        assert result is None


class TestEdgeCasesAndErrorHandling:
    """Tests for edge cases and error handling"""

    @pytest.fixture
    def mock_config_manager(self):
        config = MagicMock()
        config.get_setting.side_effect = lambda section, key: {
            ("DocumentProcessing", "scan_folder"): "C:\\test\\scan",
            ("DocumentProcessing", "organized_subfolder"): "organized",
        }.get((section, key), "default_value")
        return config

    @pytest.fixture
    def service(self, mock_config_manager):
        with patch("os.path.exists", return_value=True), patch("os.makedirs"):
            return FileService(mock_config_manager)

    @patch("os.remove")
    @patch("PIL.Image.open")
    def test_convert_tiff_to_png_handles_image_open_error(
        self, mock_image_open, mock_remove, service
    ):
        # Arrange
        mock_image_open.side_effect = Exception("Cannot open image")
        tiff_path = "C:\\test\\scan\\corrupted.tiff"

        # Act
        result = service._convert_tiff_to_png(tiff_path)

        # Assert
        assert result is None
        mock_remove.assert_not_called()

    @patch("os.remove")
    @patch("PIL.Image.open")
    def test_convert_tiff_to_png_handles_save_error(self, mock_image_open, mock_remove, service):
        # Arrange
        mock_image = MagicMock()
        mock_image.save.side_effect = Exception("Cannot save image")
        mock_image_open.return_value.__enter__ = MagicMock(return_value=mock_image)
        mock_image_open.return_value.__exit__ = MagicMock(return_value=False)
        tiff_path = "C:\\test\\scan\\file.tiff"

        # Act
        result = service._convert_tiff_to_png(tiff_path)

        # Assert
        assert result is None

    def test_group_files_by_timestamp_handles_getmtime_error(self, service):
        # Arrange
        with patch("os.path.getmtime") as mock_getmtime:
            mock_getmtime.side_effect = [0.0, Exception("Cannot access file"), 5.0]
            files = ["file1.png", "file2.png", "file3.png"]

            # Act
            result = service.group_files_by_timestamp(files, time_delta_seconds=10)

            # Assert
            # file2 should be skipped due to error
            assert len(result) == 1
            assert len(result[0]) == 2
            assert "file2.png" not in result[0]

    @patch("fitz.open")
    def test_create_searchable_pdf_returns_none_for_empty_image_list(self, mock_fitz_open, service):
        # Act
        result = service.create_searchable_pdf([], "output.pdf", {"pages": []})

        # Assert
        assert result is None
        mock_fitz_open.assert_not_called()

    @patch("fitz.open")
    @patch("PIL.Image.open")
    def test_create_searchable_pdf_continues_on_image_error(
        self, mock_image_open, mock_fitz_open, service
    ):
        # Arrange
        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_page = MagicMock()
        mock_doc.new_page.return_value = mock_page
        mock_fitz_open.return_value = mock_doc

        mock_image = MagicMock()
        mock_image.width = 800
        mock_image.height = 600

        # First image fails, second succeeds
        mock_image_open.side_effect = [
            Exception("Cannot open image"),
            MagicMock(
                __enter__=MagicMock(return_value=mock_image),
                __exit__=MagicMock(return_value=False),
            ),
        ]

        image_files = ["bad_file.png", "good_file.png"]
        extracted_text_coords = {"pages": []}

        # Act
        result = service.create_searchable_pdf(image_files, "output.pdf", extracted_text_coords)

        # Assert - should continue and create PDF with the successful image
        assert result is not None
        mock_doc.save.assert_called_once()

    @patch("fitz.open")
    @patch("PIL.Image.open")
    def test_create_searchable_pdf_returns_none_when_no_pages_added(
        self, mock_image_open, mock_fitz_open, service
    ):
        # Arrange
        mock_doc = MagicMock()
        mock_doc.page_count = 0  # No pages added
        mock_fitz_open.return_value = mock_doc

        # All images fail to open
        mock_image_open.side_effect = Exception("Cannot open image")

        image_files = ["file1.png", "file2.png"]
        extracted_text_coords = {"pages": []}

        # Act
        result = service.create_searchable_pdf(image_files, "output.pdf", extracted_text_coords)

        # Assert
        assert result is None
        mock_doc.save.assert_not_called()
