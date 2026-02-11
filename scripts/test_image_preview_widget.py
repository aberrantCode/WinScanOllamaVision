"""
Simple test for ImagePreviewWidget to verify overlay toolbar appears.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from ui.image_preview_widget import ImagePreviewWidget, ToolbarPosition, ToolbarSize


def main():
    """Test ImagePreviewWidget standalone."""
    app = QApplication(sys.argv)

    # Create main window
    window = QMainWindow()
    window.setWindowTitle("ImagePreviewWidget Test")
    window.resize(800, 600)

    # Create central widget
    central = QWidget()
    layout = QVBoxLayout(central)

    # Create image preview widget
    preview = ImagePreviewWidget(
        toolbar_size=ToolbarSize.COMPACT, toolbar_position=ToolbarPosition.TOP_CENTER
    )
    layout.addWidget(preview)

    window.setCentralWidget(central)

    # Create a test pixmap
    pixmap = QPixmap(600, 800)
    pixmap.fill(QColor(220, 230, 245))
    painter = QPainter(pixmap)
    painter.drawText(pixmap.rect(), 0x0004 | 0x0080, "Test Image\n\nToolbar should appear at top")
    painter.end()

    # Load the pixmap
    preview.set_pixmap(pixmap, apply_fit="width")

    print("\n=== ImagePreviewWidget Test ===")
    print(f"Widget size: {preview.size()}")
    print(f"Overlay exists: {preview.overlay_controls is not None}")
    if preview.overlay_controls:
        print(f"Overlay visible: {preview.overlay_controls.isVisible()}")
        print(f"Overlay size: {preview.overlay_controls.size()}")
        print(f"Overlay position: {preview.overlay_controls.pos()}")
    print("===\n")

    window.show()

    # Force overlay to show after window is visible
    if preview.overlay_controls:
        preview.overlay_controls.show()
        preview.overlay_controls.raise_()
        preview._position_overlay_controls()
        print("After force show:")
        print(f"  Overlay visible: {preview.overlay_controls.isVisible()}")
        print(f"  Overlay position: {preview.overlay_controls.pos()}")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
