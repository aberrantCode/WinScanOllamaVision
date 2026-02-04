from services.file_processor import *  # noqa: F401,F403

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
