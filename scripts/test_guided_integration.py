"""
Test script to verify guided bundle workflow integration.

This script tests the integration without running the full application.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from db.analysis_db import AnalysisDB
from services.bundling_service import BundlingService


def test_bundle_completeness():
    """Test bundle completeness detection."""
    print("Testing bundle completeness detection...")

    # Create mock bundle data
    complete_bundle = {
        "analyses": [
            {"page_number": 1, "total_pages": 3},
            {"page_number": 2, "total_pages": 3},
            {"page_number": 3, "total_pages": 3},
        ]
    }

    incomplete_bundle = {
        "analyses": [
            {"page_number": 1, "total_pages": 5},
            {"page_number": 2, "total_pages": 5},
            {"page_number": 5, "total_pages": 5},
        ]
    }

    single_page_bundle = {"analyses": [{"page_number": 1, "total_pages": 1}]}

    # Create service instance
    analysis_db = AnalysisDB()
    service = BundlingService(analysis_db)

    # Test completeness detection
    assert service._is_bundle_complete(complete_bundle), "Complete bundle should be detected as complete"
    assert not service._is_bundle_complete(
        incomplete_bundle
    ), "Incomplete bundle should be detected as incomplete"
    assert service._is_bundle_complete(
        single_page_bundle
    ), "Single page bundle should be detected as complete"

    print("[OK] Bundle completeness detection works correctly")

    # Close database
    analysis_db.close()


def test_bundle_sorting():
    """Test bundle sorting by completeness."""
    print("\nTesting bundle sorting...")

    # Create mock bundles
    bundles = [
        {
            "confidence_score": 0.7,
            "analyses": [{"page_number": 1, "total_pages": 3}, {"page_number": 2, "total_pages": 3}],
        },  # Incomplete
        {
            "confidence_score": 0.9,
            "analyses": [
                {"page_number": 1, "total_pages": 2},
                {"page_number": 2, "total_pages": 2},
            ],
        },  # Complete
        {
            "confidence_score": 0.8,
            "analyses": [{"page_number": 1, "total_pages": 1}],
        },  # Complete single page
        {
            "confidence_score": 0.6,
            "analyses": [{"page_number": 1, "total_pages": 5}, {"page_number": 3, "total_pages": 5}],
        },  # Incomplete
    ]

    # Create service instance
    analysis_db = AnalysisDB()
    service = BundlingService(analysis_db)

    # Sort bundles
    sorted_bundles = service._sort_bundles_by_completeness(bundles)

    # Verify order:
    # 1. Complete bundles first (0.9 confidence, then 0.8)
    # 2. Incomplete bundles last (0.7 confidence, then 0.6)
    assert service._is_bundle_complete(sorted_bundles[0]), "First bundle should be complete"
    assert sorted_bundles[0]["confidence_score"] == 0.9, "First complete bundle should have highest confidence"

    assert service._is_bundle_complete(sorted_bundles[1]), "Second bundle should be complete"
    assert sorted_bundles[1]["confidence_score"] == 0.8, "Second complete bundle should have lower confidence"

    assert not service._is_bundle_complete(sorted_bundles[2]), "Third bundle should be incomplete"
    assert sorted_bundles[2]["confidence_score"] == 0.7, "First incomplete bundle should have higher confidence"

    assert not service._is_bundle_complete(sorted_bundles[3]), "Fourth bundle should be incomplete"
    assert sorted_bundles[3]["confidence_score"] == 0.6, "Second incomplete bundle should have lower confidence"

    print("[OK] Bundle sorting works correctly")
    print("  Order: Complete (0.9) -> Complete (0.8) -> Incomplete (0.7) -> Incomplete (0.6)")

    # Close database
    analysis_db.close()


def test_metadata_update():
    """Test bundle metadata update."""
    print("\nTesting bundle metadata update...")

    # This would require actual database, so just verify method exists
    analysis_db = AnalysisDB()
    service = BundlingService(analysis_db)

    # Verify method exists
    assert hasattr(service, "update_bundle_metadata"), "update_bundle_metadata method should exist"
    assert hasattr(service, "convert_bundle_to_pdf"), "convert_bundle_to_pdf method should exist"

    print("[OK] Required methods exist")

    # Close database
    analysis_db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Guided Bundle Workflow Integration")
    print("=" * 60)

    try:
        test_bundle_completeness()
        test_bundle_sorting()
        test_metadata_update()

        print("\n" + "=" * 60)
        print("[SUCCESS] All tests passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
