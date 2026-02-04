import unittest
import os
import shutil
import time
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from unittest.mock import patch, MagicMock
from services.file_processor import FileProcessor
from config.config_manager import ConfigManager
from PIL import Image

class TestFileProcessor(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_data_processor"
        self.scan_folder = os.path.join(self.test_dir, "scans")
        self.organized_folder = os.path.join(self.scan_folder, "ORGANIZED")
        os.makedirs(self.scan_folder, exist_ok=True)
        os.makedirs(self.organized_folder, exist_ok=True)

        self.mock_config_manager = MagicMock(spec=ConfigManager)
        self.mock_config_manager.get_setting.side_effect = self._mock_get_setting

        self.file_processor = FileProcessor(self.mock_config_manager)

    def _mock_get_setting(self, section, key, default=None):
        if section == 'DocumentProcessing':
            if key == 'scan_folder':
                return self.scan_folder
            elif key == 'organized_subfolder':
                return "ORGANIZED"
        return default

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_dummy_image(self, filename, folder=None, img_type='PNG'):
        if folder is None:
            folder = self.scan_folder
        path = os.path.join(folder, filename)
        Image.new('RGB', (100, 100), color='red').save(path, img_type)
        return path
    
    def test_get_image_files(self):
        png_file = self._create_dummy_image("test.png")
        tiff_file = self._create_dummy_image("test.tif", img_type='TIFF')
        txt_file = os.path.join(self.scan_folder, "test.txt")
        with open(txt_file, 'w') as f: f.write("hello")

        files = self.file_processor._get_image_files()
        self.assertIn(png_file, files)
        self.assertIn(os.path.splitext(tiff_file)[0] + '.png', files)
        self.assertFalse(os.path.exists(tiff_file))
        self.assertNotIn(txt_file, files)

    def test_group_files_by_timestamp(self):
        file1 = self._create_dummy_image("file1.png")
        os.utime(file1, (time.time() - 10, time.time() - 10))
        time.sleep(0.1)
        file2 = self._create_dummy_image("file2.png")
        os.utime(file2, (time.time() - 9, time.time() - 9))
        time.sleep(0.1)
        file3 = self._create_dummy_image("file3.png")
        os.utime(file3, (time.time() - 1, time.time() - 1))

        files_to_group = [file1, file2, file3]
        files_to_group.sort(key=os.path.getmtime) 

        grouped = self.file_processor.group_files_by_timestamp(files_to_group, time_delta_seconds=2)
        
        self.assertEqual(len(grouped), 2)
        self.assertEqual(len(grouped[0]), 2)
        self.assertEqual(len(grouped[1]), 1)

    @patch('services.file_processor.fitz.open')
    def test_create_searchable_pdf(self, mock_fitz_open):
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_doc.new_page.return_value = mock_page
        mock_fitz_open.return_value = mock_doc
        mock_doc.page_count = 1

        img_path1 = self._create_dummy_image("pdf_test1.png")
        img_path2 = self._create_dummy_image("pdf_test2.png")

        extracted_coords = {
            "pages": [
                {"page_number": 1, "elements": [{"text": "Page1", "bbox": [1, 2, 3, 4]}]},
                {"page_number": 2, "elements": [{"text": "Page2", "bbox": [5, 6, 7, 8]}]}
            ]
        }
        
        output_pdf_name = "test_output.pdf"
        self.file_processor.create_searchable_pdf([img_path1, img_path2], output_pdf_name, extracted_coords, is_searchable=True)

        self.assertEqual(mock_doc.new_page.call_count, 2)
        self.assertEqual(mock_page.insert_image.call_count, 2)
        self.assertEqual(mock_page.insert_textbox.call_count, 2)
        mock_doc.save.assert_called_once()

    def test_delete_files(self):
        file1 = self._create_dummy_image("delete1.png")
        self.assertTrue(os.path.exists(file1))
        self.file_processor.delete_files([file1])
        self.assertFalse(os.path.exists(file1))

if __name__ == '__main__':
    unittest.main()
