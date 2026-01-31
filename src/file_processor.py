import os
import shutil
import fitz  # PyMuPDF
from PIL import Image
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta

class FileProcessor:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.scan_folder = self.config_manager.get_setting('DocumentProcessing', 'scan_folder')
        self.organized_folder = os.path.join(self.scan_folder, 
                                             self.config_manager.get_setting('DocumentProcessing', 'organized_subfolder'))
        
        os.makedirs(self.scan_folder, exist_ok=True)
        os.makedirs(self.organized_folder, exist_ok=True)

    def _get_image_files(self) -> List[str]:
        """Scans the scan_folder for PNG and TIFF files."""
        image_files = []
        for f in os.listdir(self.scan_folder):
            file_path = os.path.join(self.scan_folder, f)
            if os.path.isfile(file_path):
                if f.lower().endswith(('.png')):
                    image_files.append(file_path)
                elif f.lower().endswith(('.tiff', '.tif')):
                    # Convert TIFF to PNG and then add to list
                    png_path = self._convert_tiff_to_png(file_path)
                    if png_path:
                        image_files.append(png_path)
        return image_files

    def _convert_tiff_to_png(self, tiff_path: str) -> Optional[str]:
        """Converts a TIFF file to PNG and returns the new PNG path. Deletes original TIFF."""
        try:
            with Image.open(tiff_path) as img:
                png_path = os.path.splitext(tiff_path)[0] + '.png'
                img.save(png_path, 'PNG')
            os.remove(tiff_path) # Delete original TIFF after conversion
            return png_path
        except Exception as e:
            print(f"Error converting TIFF {tiff_path} to PNG: {e}")
            return None

    def group_files_by_timestamp(self, files: List[str], time_delta_seconds: int = 5) -> List[List[str]]:
        """
        Groups files by their creation/modification timestamp, assuming consecutive scans.
        Files must be in chronological order for best results.
        """
        if not files:
            return []

        # Get file stats including creation/modification time
        file_data = []
        for f in files:
            try:
                # Use st_mtime as it's often more reliable for 'last modified' by scanner
                m_time = os.path.getmtime(f)
                file_data.append({'path': f, 'mtime': m_time})
            except Exception as e:
                print(f"Warning: Could not get mtime for {f}: {e}. Skipping file.")
                continue
        
        # Sort files by modification time
        file_data.sort(key=lambda x: x['mtime'])

        grouped_files: List[List[str]] = []
        current_group: List[str] = []
        last_mtime: Optional[float] = None

        for item in file_data:
            if not current_group:
                current_group.append(item['path'])
                last_mtime = item['mtime']
            else:
                if (item['mtime'] - last_mtime) < time_delta_seconds:
                    current_group.append(item['path'])
                else:
                    grouped_files.append(current_group)
                    current_group = [item['path']]
                last_mtime = item['mtime']
        
        if current_group:
            grouped_files.append(current_group)
            
        return grouped_files
    
    def create_searchable_pdf(self, 
                              image_paths: List[str], 
                              output_filename: str, 
                              extracted_text_coords: Dict[str, Any],
                              is_searchable: bool = True
                              ) -> Optional[str]:
        """
        Creates a PDF from a list of image paths, optionally adding a text layer for searchability.
        extracted_text_coords should be a dict like {"pages": [{"page_number": 1, "elements": [{"text": "...", "bbox": [...]}]}]}
        """
        if not image_paths:
            return None

        output_path = os.path.join(self.organized_folder, output_filename)
        doc = fitz.open() # New PDF document

        for i, img_path in enumerate(image_paths):
            try:
                img_page_number = i + 1 # Assuming pages are ordered 1 to N
                
                # Create a new page the size of the image, ensuring file handle is closed
                with Image.open(img_path) as img:
                    img_rect = fitz.Rect(0, 0, img.width, img.height)

                page = doc.new_page(-1, width=img_rect.width, height=img_rect.height)
                
                # Add the image to the page
                page.insert_image(img_rect, filename=img_path)

                if is_searchable and extracted_text_coords and "pages" in extracted_text_coords:
                    # Find the corresponding text/coords for this image_path's page number
                    page_coords = next((p for p in extracted_text_coords["pages"] if p.get("page_number") == img_page_number), None)
                    
                    if page_coords and "elements" in page_coords:
                        for element in page_coords["elements"]:
                            text = element.get("text")
                            bbox = element.get("bbox") # [x_min, y_min, x_max, y_max]
                            if text and bbox and len(bbox) == 4:
                                text_rect = fitz.Rect(bbox)
                                # Insert text with a transparent color
                                page.insert_textbox(text_rect, text,
                                                    fontname="helv",  # Standard font
                                                    fontsize=max(5, (text_rect.height * 0.8)), # Estimate font size
                                                    # Adjust color based on page background etc, but making it invisible
                                                    # alpha=0 for fully invisible
                                                    oc=0) # oc=0 makes text invisible but searchable. 
                                # An alternative might be fill=None, stroke=None, but oc is cleaner for searchability
                                
                print(f"Added {img_path} to PDF.")
            except Exception as e:
                print(f"Error processing image {img_path} for PDF: {e}")
                # Decide if we want to fail the whole PDF or just skip the page
                # For now, print error and continue, will result in fewer pages
                
        if not doc.page_count:
            print("Warning: No pages were added to the PDF document.")
            return None

        doc.save(output_path)
        doc.close()
        print(f"PDF created: {output_path}")
        return output_path

    def delete_files(self, file_paths: List[str]):
        """Deletes a list of files."""
        for f_path in file_paths:
            try:
                os.remove(f_path)
                print(f"Deleted: {f_path}")
            except Exception as e:
                print(f"Error deleting file {f_path}: {e}")

    def move_pdf_to_organized(self, pdf_path: str, new_filename: str) -> Optional[str]:
        """Moves the created PDF to the organized folder with the new filename."""
        final_path = os.path.join(self.organized_folder, new_filename)
        try:
            shutil.move(pdf_path, final_path)
            print(f"Moved PDF to {final_path}")
            return final_path
        except Exception as e:
            print(f"Error moving PDF {pdf_path} to {final_path}: {e}")
            return None

# Example Usage (for testing during development)
if __name__ == "__main__":
    # Assuming config_manager.py and settings.ini exist and are functional
    from config_manager import ConfigManager
    
    # Setup dummy environment
    test_scan_folder = "test_scans"
    test_organized_folder = os.path.join(test_scan_folder, "ORGANIZED")
    os.makedirs(test_scan_folder, exist_ok=True)
    os.makedirs(test_organized_folder, exist_ok=True)

    # Create dummy config
    temp_config_file = 'temp_settings.ini'
    config_mgr = ConfigManager(temp_config_file)
    config_mgr.set_setting('DocumentProcessing', 'scan_folder', test_scan_folder)
    config_mgr.set_setting('DocumentProcessing', 'organized_subfolder', 'ORGANIZED')

    file_processor = FileProcessor(config_mgr)

    # Create dummy image files
    dummy_png1 = os.path.join(test_scan_folder, "scan_1.png")
    dummy_png2 = os.path.join(test_scan_folder, "scan_2.png")
    dummy_tiff = os.path.join(test_scan_folder, "scan_3.tif")

    Image.new('RGB', (100, 100), color='red').save(dummy_png1)
    # Simulate time difference for grouping
    import time
    time.sleep(1) 
    Image.new('RGB', (100, 100), color='blue').save(dummy_png2)
    time.sleep(10) # Longer gap for separate group
    Image.new('RGB', (100, 100), color='green').save(dummy_tiff)

    print("\n--- Testing TIFF conversion and file scanning ---")
    scanned_files = file_processor._get_image_files()
    print(f"Scanned files after conversion: {scanned_files}")
    assert os.path.exists(os.path.splitext(dummy_tiff)[0] + '.png') # Check if TIFF converted

    print("\n--- Testing file grouping ---")
    grouped = file_processor.group_files_by_timestamp(scanned_files, time_delta_seconds=5)
    print(f"Grouped files: {grouped}")
    assert len(grouped) == 2 # Expect two groups

    print("\n--- Testing PDF creation ---")
    # Simulate Ollama text and coords output
    dummy_extracted_coords = {
        "pages": [
            {
                "page_number": 1,
                "elements": [{"text": "Hello World 1", "bbox": [10, 10, 90, 20]}]
            },
            {
                "page_number": 2,
                "elements": [{"text": "Hello World 2", "bbox": [10, 10, 90, 20]}]
            }
        ]
    }
    
    # Create a dummy PDF with searchable text
    output_pdf_name = "Test Document - Example - 2026-01-30.pdf"
    created_pdf_path = file_processor.create_searchable_pdf(grouped[0], output_pdf_name, dummy_extracted_coords, is_searchable=True)
    print(f"Created PDF: {created_pdf_path}")
    assert created_pdf_path is not None
    assert os.path.exists(created_pdf_path)

    # Clean up
    print("\n--- Cleaning up test files ---")
    file_processor.delete_files([dummy_png1, dummy_png2, os.path.splitext(dummy_tiff)[0] + '.png'])
    if created_pdf_path and os.path.exists(created_pdf_path):
        os.remove(created_pdf_path)
    if os.path.exists(test_scan_folder):
        shutil.rmtree(test_scan_folder)
    if os.path.exists(temp_config_file):
        os.remove(temp_config_file)
    print("Cleanup complete.")
