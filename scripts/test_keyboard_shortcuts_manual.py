"""
Manual test script for Phase 6: Keyboard Shortcuts & Polish

This script opens the ConvertImagesWindow with test data to manually verify:
1. All keyboard shortcuts work correctly
2. Visual feedback appears when including/excluding pages
3. Shortcuts legend can be toggled with F1
4. Button tooltips show keyboard shortcuts
5. Tab order is correct for accessibility

Instructions:
1. Run this script: python scripts/test_keyboard_shortcuts_manual.py
2. Try the following keyboard shortcuts:
   - Left/Right Arrow: Navigate between images
   - Page Up/Down: Jump 10 images
   - Home/End: Jump to first/last image
   - Space: Include current page (when available)
   - Delete: Exclude current page (when available)
   - Enter: Approve/Continue
   - Esc: Cancel/Back
   - Ctrl+Plus: Zoom in
   - Ctrl+Minus: Zoom out
   - Ctrl+0: Fit to window
   - F1 or ?: Toggle shortcuts legend
3. Verify visual feedback (green flash on include, red flash on exclude)
4. Check that button tooltips show shortcuts
5. Press Tab to verify tab order through controls
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PyQt6.QtWidgets import QApplication, QMessageBox
from gui import ConvertImagesWindow
import tempfile
from PIL import Image

def create_test_images(count=20):
    """Create test images in a temporary directory"""
    temp_dir = tempfile.mkdtemp(prefix="keyboard_test_")

    for i in range(count):
        # Create a simple test image
        img = Image.new('RGB', (800, 1000), color=(200, 200, 200))
        img_path = os.path.join(temp_dir, f"test_page_{i:03d}.png")
        img.save(img_path)

    return temp_dir

def main():
    app = QApplication(sys.argv)

    # Create test images
    print("Creating test images...")
    test_dir = create_test_images(20)
    print(f"Test images created in: {test_dir}")

    # Create window
    window = ConvertImagesWindow()

    # Populate with test files
    test_files = [os.path.join(test_dir, f"test_page_{i:03d}.png") for i in range(20)]
    window.all_files = test_files
    window.current_page_path = test_files[0]
    window.current_step = window.WorkflowStep.STITCHING

    # Setup UI for manual testing
    window.show()

    # Show instructions
    QMessageBox.information(
        window,
        "Keyboard Shortcuts Manual Test",
        "Test the following shortcuts:\n\n"
        "NAVIGATION:\n"
        "  ← → : Previous/Next image\n"
        "  PgUp/PgDn : Jump 10 images\n"
        "  Home/End : First/Last image\n\n"
        "ACTIONS:\n"
        "  Space : Include page\n"
        "  Delete : Exclude page\n"
        "  Enter : Approve/Continue\n"
        "  Esc : Cancel/Back\n\n"
        "ZOOM:\n"
        "  Ctrl + + : Zoom in\n"
        "  Ctrl + - : Zoom out\n"
        "  Ctrl + 0 : Fit to window\n\n"
        "HELP:\n"
        "  F1 or ? : Toggle shortcuts legend\n\n"
        "Watch for visual feedback:\n"
        "  - Green flash when including\n"
        "  - Red flash when excluding\n\n"
        "Hover over buttons to see tooltips!"
    )

    sys.exit(app.exec())

if __name__ == '__main__':
    main()
