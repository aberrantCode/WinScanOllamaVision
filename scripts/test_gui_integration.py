"""Test GUI integration without running full app."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

print("Testing GUI integration imports...")

# Test that gui.py can import workflow
from ui.verify_documents_window import BundleReviewWindow

print("[OK] All GUI integration imports work")

# Test workflow instantiation with minimal params
print("\nTesting workflow instantiation...")
mock_bundles = [
    {
        "bundle_id": "test_1",
        "company": "Test Corp",
        "document_type": "Invoice",
        "document_date": "2024-01-01",
        "confidence_score": 0.9,
        "file_paths": ["test1.png", "test2.png"],
        "analyses": [{"page_number": 1, "total_pages": 2}, {"page_number": 2, "total_pages": 2}],
    }
]

# Try to create workflow instance (don't show it)
try:
    # Note: This will fail without PyQt application context
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    workflow = BundleReviewWindow(
        bundles=mock_bundles,
        start_index=0,
        prototype_mode=True,
        analysis_db=None,
        metadata_db=None,
        config_manager=None,
        parent=None,
    )
    print("[OK] Workflow instantiation works")
    print(f"[OK] Workflow has {len(workflow.bundles)} bundle(s)")
    print(f"[OK] Current bundle index: {workflow.current_bundle_index}")

    # Don't exec() - just verify it instantiates
    app.quit()

except Exception as e:
    print(f"[ERROR] Workflow instantiation failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print("\n[SUCCESS] GUI integration test PASSED")
