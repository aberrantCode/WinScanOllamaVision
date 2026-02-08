"""
Test script for BundleReviewWindow prototype.

Run this to launch the Bundle Review Window with mock data.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.verify_documents_window import BundleReviewWindow  # noqa: E402


def main():
    """Launch Bundle Review Window with mock data."""
    app = QApplication(sys.argv)

    # Create window with default mock data
    window = BundleReviewWindow(prototype_mode=True)

    # Connect signals for testing
    def on_confirmed(bundle_data):
        print("\n=== BUNDLE CONFIRMED ===")
        print(f"Bundle ID: {bundle_data['bundle_id']}")
        print(f"Remaining pages: {len(bundle_data['file_paths'])}")
        print(f"User edits: {bundle_data['user_edits']}")

    def on_rejected(bundle_data):
        print("\n=== BUNDLE REJECTED ===")
        print(f"Bundle ID: {bundle_data['bundle_id']}")

    window.bundle_confirmed.connect(on_confirmed)
    window.bundle_rejected.connect(on_rejected)

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
