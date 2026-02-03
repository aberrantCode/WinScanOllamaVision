"""
Visual test for MetadataDisplayWidget
Shows the widget with sample data to verify styling and layout
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt
from unittest.mock import Mock
from gui import MetadataDisplayWidget
from analysis_db import AnalysisDB


def create_mock_analysis_db():
    """Create a mock AnalysisDB with sample data"""
    db = Mock(spec=AnalysisDB)

    # Sample high confidence analysis
    high_confidence_analysis = {
        'confidence_score': 0.92,
        'document_type': 'Invoice',
        'company': 'Acme Corporation',
        'document_date': '2024-01-15',
        'page_number': 1,
        'total_pages': 6,
        'rotation_needed': False,
        'suggested_rotation': 0
    }

    # Sample medium confidence analysis
    medium_confidence_analysis = {
        'confidence_score': 0.65,
        'document_type': 'Statement',
        'company': 'Beta Inc',
        'document_date': '2024-01-12',
        'page_number': 2,
        'total_pages': 3,
        'rotation_needed': False
    }

    # Sample low confidence analysis
    low_confidence_analysis = {
        'confidence_score': 0.35,
        'document_type': 'Receipt',
        'company': 'Charlie Co',
        'rotation_needed': True,
        'suggested_rotation': 90
    }

    # Return different data based on file path
    def get_analysis(file_path):
        if 'invoice' in file_path.lower():
            return high_confidence_analysis
        elif 'statement' in file_path.lower():
            return medium_confidence_analysis
        elif 'receipt' in file_path.lower():
            return low_confidence_analysis
        else:
            return None

    db.get_analysis.side_effect = get_analysis
    return db


def main():
    """Run visual test"""
    app = QApplication(sys.argv)

    # Create main window
    window = QMainWindow()
    window.setWindowTitle("MetadataDisplayWidget Visual Test")
    window.setGeometry(100, 100, 400, 700)

    # Create central widget
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    layout = QVBoxLayout(central_widget)
    layout.setContentsMargins(10, 10, 10, 10)

    # Create mock database
    mock_db = create_mock_analysis_db()

    # Create metadata display widget
    metadata_widget = MetadataDisplayWidget(analysis_db=mock_db)
    layout.addWidget(metadata_widget)

    # Connect signals for testing
    metadata_widget.re_analyze_requested.connect(
        lambda path: print(f"Re-analyze requested for: {path}")
    )
    metadata_widget.thumbnail_clicked.connect(
        lambda path: print(f"Thumbnail clicked: {path}")
    )

    # Set sample data
    print("\n=== Testing High Confidence Display ===")
    metadata_widget.set_current_file("invoice_001.png")
    metadata_widget.set_bundle_files([
        "invoice_001.png",
        "invoice_002.png",
        "invoice_003.png"
    ])

    # Show window
    window.show()

    print("\n=== Visual Test Instructions ===")
    print("1. Check that confidence badge is GREEN and shows 'HIGH CONFIDENCE (92%)'")
    print("2. Verify metadata fields display correctly:")
    print("   - Document Type: Invoice")
    print("   - Company: Acme Corporation")
    print("   - Date: 2024-01-15")
    print("   - Page: 1 of 6")
    print("   - Rotation: None needed ✓")
    print("3. Check bundle section shows '3 pages included'")
    print("4. Verify re-analyze button is visible")
    print("\nPress Ctrl+C to switch to medium confidence test...")
    print("(Or close window to exit)")

    # Set up timer to cycle through examples
    from PyQt6.QtCore import QTimer

    def cycle_examples():
        """Cycle through different confidence levels"""
        import time

        # After 5 seconds, show medium confidence
        QTimer.singleShot(5000, lambda: (
            print("\n=== Switching to Medium Confidence ==="),
            metadata_widget.set_current_file("statement_001.png"),
            metadata_widget.set_bundle_files(["statement_001.png", "statement_002.png"]),
            print("Badge should be YELLOW: 'MEDIUM CONFIDENCE (65%)'")
        ))

        # After 10 seconds, show low confidence with rotation
        QTimer.singleShot(10000, lambda: (
            print("\n=== Switching to Low Confidence with Rotation ==="),
            metadata_widget.set_current_file("receipt_001.png"),
            metadata_widget.set_bundle_files(["receipt_001.png"]),
            print("Badge should be RED: 'LOW CONFIDENCE (35%)'"),
            print("Rotation should show: '90° suggested'")
        ))

        # After 15 seconds, show no analysis
        QTimer.singleShot(15000, lambda: (
            print("\n=== Switching to No Analysis ==="),
            metadata_widget.set_current_file("unknown_file.png"),
            metadata_widget.set_bundle_files([]),
            print("Badge should be GRAY: 'No Analysis Data'"),
            print("All fields should show '--'")
        ))

    cycle_examples()

    # Run application
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
