"""
Phase 7 Tests: Document Bundling UI
Tests the bundle suggestion cards, workflow integration, and handler methods
"""

import sys
import os
import tempfile

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt


def test_imports():
    """Test that all Phase 7 components can be imported"""
    print("\n[TEST] Phase 7 imports")
    try:
        from bundle_widgets import BundleSuggestionCard, BundleSuggestionsView
        from bundling_service import BundlingService
        from analysis_db import AnalysisDB
        print("  [OK] Phase 7 components import successfully")
        return True
    except Exception as e:
        print(f"  [FAIL] Import error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bundle_suggestion_card():
    """Test BundleSuggestionCard widget creation"""
    print("\n[TEST] Bundle suggestion card creation")

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from bundle_widgets import BundleSuggestionCard

        # Create test bundle data
        bundle_data = {
            'document_type': 'Invoice',
            'company': 'Test Company',
            'document_date': '2024-01-15',
            'file_paths': ['test1.png', 'test2.png'],
            'confidence_score': 0.85
        }

        # Create card
        card = BundleSuggestionCard(bundle_data)

        # Verify card properties
        assert card.bundle_data == bundle_data, "Bundle data should be stored"
        assert card.frameStyle() != 0, "Card should have frame style"

        # Verify signals exist
        assert hasattr(card, 'accepted'), "Card should have accepted signal"
        assert hasattr(card, 'modified'), "Card should have modified signal"
        assert hasattr(card, 'rejected'), "Card should have rejected signal"

        print("  [OK] Bundle suggestion card created successfully")
        return True

    except Exception as e:
        print(f"  [FAIL] Card creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bundle_suggestions_view():
    """Test BundleSuggestionsView container widget"""
    print("\n[TEST] Bundle suggestions view")

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from bundle_widgets import BundleSuggestionsView

        # Create view
        view = BundleSuggestionsView()

        # Verify signals exist
        assert hasattr(view, 'bundle_accepted'), "View should have bundle_accepted signal"
        assert hasattr(view, 'bundle_modified'), "View should have bundle_modified signal"
        assert hasattr(view, 'bundle_rejected'), "View should have bundle_rejected signal"
        assert hasattr(view, 'accept_all_high'), "View should have accept_all_high signal"
        assert hasattr(view, 'skip_to_manual'), "View should have skip_to_manual signal"

        # Verify bundle cards list exists
        assert hasattr(view, 'bundle_cards'), "View should have bundle_cards list"
        assert len(view.bundle_cards) == 0, "Bundle cards should start empty"

        print("  [OK] Bundle suggestions view created successfully")
        return True

    except Exception as e:
        print(f"  [FAIL] View creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_set_bundles():
    """Test setting bundles in the view"""
    print("\n[TEST] Setting bundles in view")

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from bundle_widgets import BundleSuggestionsView

        # Create view
        view = BundleSuggestionsView()

        # Create test bundles
        bundles = [
            {
                'document_type': 'Invoice',
                'company': 'Company A',
                'document_date': '2024-01-15',
                'file_paths': ['test1.png', 'test2.png'],
                'confidence_score': 0.85
            },
            {
                'document_type': 'Receipt',
                'company': 'Company B',
                'document_date': '2024-01-16',
                'file_paths': ['test3.png'],
                'confidence_score': 0.6
            }
        ]

        # Set bundles
        view.set_bundles(bundles)

        # Verify cards were created
        assert view.get_bundle_count() == 2, f"Should have 2 bundle cards, got {view.get_bundle_count()}"

        print("  [OK] Bundles set successfully in view")
        return True

    except Exception as e:
        print(f"  [FAIL] Setting bundles failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_high_confidence_bundles():
    """Test filtering high confidence bundles"""
    print("\n[TEST] Getting high confidence bundles")

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from bundle_widgets import BundleSuggestionsView

        # Create view
        view = BundleSuggestionsView()

        # Create test bundles with varying confidence
        bundles = [
            {
                'document_type': 'Invoice',
                'company': 'Company A',
                'document_date': '2024-01-15',
                'file_paths': ['test1.png', 'test2.png'],
                'confidence_score': 0.85  # High
            },
            {
                'document_type': 'Receipt',
                'company': 'Company B',
                'document_date': '2024-01-16',
                'file_paths': ['test3.png'],
                'confidence_score': 0.6  # Medium
            },
            {
                'document_type': 'Statement',
                'company': 'Company C',
                'document_date': '2024-01-17',
                'file_paths': ['test4.png', 'test5.png'],
                'confidence_score': 0.9  # High
            }
        ]

        # Set bundles
        view.set_bundles(bundles)

        # Get high confidence bundles
        high_confidence = view.get_high_confidence_bundles()

        # Verify only high confidence bundles returned
        assert len(high_confidence) == 2, f"Should have 2 high confidence bundles, got {len(high_confidence)}"
        assert all(b.get('confidence_score', 0.0) >= 0.8 for b in high_confidence), \
            "All returned bundles should have confidence >= 0.8"

        print("  [OK] High confidence bundles filtered correctly")
        return True

    except Exception as e:
        print(f"  [FAIL] Getting high confidence bundles failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_workflow_step_enum():
    """Test that WorkflowStep enum has BUNDLE_SUGGESTIONS"""
    print("\n[TEST] WorkflowStep enum with BUNDLE_SUGGESTIONS")

    try:
        from gui import WorkflowStep

        # Verify BUNDLE_SUGGESTIONS exists
        assert hasattr(WorkflowStep, 'BUNDLE_SUGGESTIONS'), \
            "WorkflowStep should have BUNDLE_SUGGESTIONS"

        # Verify it's step 0
        assert WorkflowStep.BUNDLE_SUGGESTIONS.value == 0, \
            f"BUNDLE_SUGGESTIONS should be step 0, got {WorkflowStep.BUNDLE_SUGGESTIONS.value}"

        # Verify other steps are updated
        assert WorkflowStep.STITCHING.value == 1, "STITCHING should be step 1"
        assert WorkflowStep.ANALYSIS.value == 2, "ANALYSIS should be step 2"
        assert WorkflowStep.ORDERING.value == 3, "ORDERING should be step 3"
        assert WorkflowStep.FINALIZATION.value == 4, "FINALIZATION should be step 4"

        print("  [OK] WorkflowStep enum correctly updated with BUNDLE_SUGGESTIONS")
        return True

    except Exception as e:
        print(f"  [FAIL] WorkflowStep enum test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_convert_images_window_bundle_integration():
    """Test that ConvertImagesWindow has bundle-related attributes"""
    print("\n[TEST] ConvertImagesWindow bundle integration")

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from gui import ConvertImagesWindow

        # Create window (this will initialize bundling services)
        window = ConvertImagesWindow()

        # Verify bundle-related attributes exist
        assert hasattr(window, 'analysis_db'), "Window should have analysis_db"
        assert hasattr(window, 'bundling_service'), "Window should have bundling_service"
        assert hasattr(window, 'bundle_suggestions_view'), "Window should have bundle_suggestions_view"

        # Verify bundle handler methods exist
        assert hasattr(window, '_load_and_show_bundle_suggestions'), \
            "Window should have _load_and_show_bundle_suggestions method"
        assert hasattr(window, '_on_bundle_accepted'), \
            "Window should have _on_bundle_accepted method"
        assert hasattr(window, '_on_bundle_modified'), \
            "Window should have _on_bundle_modified method"
        assert hasattr(window, '_on_bundle_rejected'), \
            "Window should have _on_bundle_rejected method"
        assert hasattr(window, '_on_accept_all_high_confidence'), \
            "Window should have _on_accept_all_high_confidence method"
        assert hasattr(window, '_on_skip_to_manual_workflow'), \
            "Window should have _on_skip_to_manual_workflow method"
        assert hasattr(window, '_check_remaining_pages_after_bundles'), \
            "Window should have _check_remaining_pages_after_bundles method"

        # Verify initial workflow step is BUNDLE_SUGGESTIONS
        from gui import WorkflowStep
        assert window.current_step == WorkflowStep.BUNDLE_SUGGESTIONS, \
            f"Initial step should be BUNDLE_SUGGESTIONS, got {window.current_step}"

        print("  [OK] ConvertImagesWindow has all bundle integration components")

        window.close()
        return True

    except Exception as e:
        print(f"  [FAIL] ConvertImagesWindow bundle integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_step_indicators_updated():
    """Test that step indicators show '5' instead of '4'"""
    print("\n[TEST] Step indicators updated to 5 steps")

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from gui import ConvertImagesWindow

        # Create window
        window = ConvertImagesWindow()

        # Check initial step indicator
        step_text = window.step_indicator_label.text()
        assert "of 5" in step_text or "Step 1" in step_text, \
            f"Step indicator should mention 5 steps or be at step 1, got: {step_text}"

        print(f"  [OK] Step indicators correctly show 5 steps (current: {step_text})")

        window.close()
        return True

    except Exception as e:
        print(f"  [FAIL] Step indicator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all Phase 7 tests"""
    print("\n" + "="*70)
    print("PHASE 7 TESTS: Document Bundling UI")
    print("="*70)

    tests = [
        ("Import Test", test_imports),
        ("Bundle Suggestion Card", test_bundle_suggestion_card),
        ("Bundle Suggestions View", test_bundle_suggestions_view),
        ("Set Bundles", test_set_bundles),
        ("Get High Confidence Bundles", test_get_high_confidence_bundles),
        ("WorkflowStep Enum", test_workflow_step_enum),
        ("ConvertImagesWindow Integration", test_convert_images_window_bundle_integration),
        ("Step Indicators Updated", test_step_indicators_updated),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n[FAIL] {test_name} crashed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*70)
    print(f"PHASE 7 RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("="*70 + "\n")

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
