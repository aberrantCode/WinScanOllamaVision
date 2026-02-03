"""Test Phase 2: Three-Column Layout for ConvertImagesWindow"""

import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from gui import ConvertImagesWindow


def test_three_column_layout():
    """Test that three-column layout is properly configured"""
    app = QApplication(sys.argv)
    window = ConvertImagesWindow()
    window.show()
    app.processEvents()  # Process pending events

    # Manually trigger splitter sizing for test
    window._apply_initial_splitter_sizes()
    app.processEvents()  # Process any layout changes

    # Verify minimum window size
    min_size = window.minimumSize()
    print(f"✓ Minimum window size: {min_size.width()}x{min_size.height()}")
    assert min_size.width() == 1200, f"Expected minimum width 1200, got {min_size.width()}"
    assert min_size.height() == 700, f"Expected minimum height 700, got {min_size.height()}"

    # Verify content_splitter exists
    assert hasattr(window, 'content_splitter'), "content_splitter not found"
    print("✓ Content splitter exists")

    # Verify three panels exist
    assert hasattr(window, 'left_panel'), "left_panel not found"
    assert hasattr(window, 'right_panel'), "right_panel not found"
    assert hasattr(window, 'large_preview_label'), "large_preview_label not found"
    print("✓ Three panels exist")

    # Verify splitter has 3 widgets
    splitter_count = window.content_splitter.count()
    assert splitter_count == 3, f"Expected 3 splitter widgets, got {splitter_count}"
    print(f"✓ Splitter has {splitter_count} widgets")

    # Verify center panel minimum width
    center_min_width = window.large_preview_label.minimumWidth()
    assert center_min_width == 600, f"Expected center minimum width 600, got {center_min_width}"
    print(f"✓ Center panel minimum width: {center_min_width}px")

    # Verify handle width
    handle_width = window.content_splitter.handleWidth()
    assert handle_width == 8, f"Expected handle width 8, got {handle_width}"
    print(f"✓ Splitter handle width: {handle_width}px")

    # Verify panels are not collapsible
    assert not window.content_splitter.childrenCollapsible(), "Panels should not be collapsible"
    print("✓ Panels are not collapsible")

    # Verify fixed widths are set
    assert window.left_panel.width() == 250, f"Left panel fixed width should be 250, got {window.left_panel.width()}"
    assert window.right_panel.width() == 350, f"Right panel fixed width should be 350, got {window.right_panel.width()}"
    print(f"✓ Fixed widths set: left={window.left_panel.width()}px, right={window.right_panel.width()}px")

    print("\n✅ All Phase 2 layout tests passed!")
    print("\nNote: Run main.py to visually verify the three-column layout.")


if __name__ == '__main__':
    test_three_column_layout()
