"""
Demo launcher for the Guided Bundle Review Workflow.

This script demonstrates the new unified UX for reviewing bundle suggestions
and converting them to PDFs.

Usage:
    python scripts/demo_guided_workflow.py
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from PyQt6.QtWidgets import QApplication

from ui.verify_documents_window import BundleReviewWindow


def main():
    """Launch the guided bundle workflow demo."""
    app = QApplication(sys.argv)

    # Create window in prototype mode with mock data
    window = BundleReviewWindow(
        bundles=None,  # Will use mock data
        start_index=0,
        prototype_mode=True,
        parent=None,
    )

    # Connect signals for demo
    def on_bundle_accepted(bundle):
        print(f"✓ Accepted: {bundle.get('document_type')} - {bundle.get('company')}")

    def on_bundle_rejected(bundle):
        print(f"✗ Rejected: {bundle.get('document_type')} - {bundle.get('company')}")

    def on_workflow_completed(stats):
        print("\n" + "=" * 50)
        print("WORKFLOW COMPLETED")
        print("=" * 50)
        print(f"Accepted: {stats['accepted']}")
        print(f"Rejected: {stats['rejected']}")
        print(f"Skipped: {stats['skipped']}")
        print(f"Total: {stats['total']}")
        print("=" * 50)

    window.bundle_accepted.connect(on_bundle_accepted)
    window.bundle_rejected.connect(on_bundle_rejected)
    window.workflow_completed.connect(on_workflow_completed)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
