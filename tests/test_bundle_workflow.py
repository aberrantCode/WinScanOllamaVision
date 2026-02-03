"""
Test for Phase 5 Step 0: Bundle Suggestions Workflow
Tests the new bundle suggestions view and workflow transitions
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PyQt6.QtWidgets import QApplication


def test_bundle_suggestions_workflow():
    """Test bundle suggestions view workflow"""
    print("\n[TEST] Bundle Suggestions Workflow")

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from gui import ConvertImagesWindow, WorkflowStep

        # Create window
        window = ConvertImagesWindow()

        # Verify initial state
        assert window.current_step == WorkflowStep.BUNDLE_SUGGESTIONS, \
            f"Initial step should be BUNDLE_SUGGESTIONS, got {window.current_step}"

        # Verify bundle view exists
        assert hasattr(window, 'bundle_suggestions_view'), \
            "Window should have bundle_suggestions_view"

        assert hasattr(window, 'content_splitter'), \
            "Window should have content_splitter for three-column layout"

        # Test helper methods exist
        assert hasattr(window, '_show_bundle_view'), \
            "Should have _show_bundle_view method"

        assert hasattr(window, '_show_manual_view'), \
            "Should have _show_manual_view method"

        # Test bundle action handlers exist
        assert hasattr(window, '_on_bundle_accepted'), \
            "Should have _on_bundle_accepted handler"

        assert hasattr(window, '_on_bundle_modified'), \
            "Should have _on_bundle_modified handler"

        assert hasattr(window, '_on_bundle_rejected'), \
            "Should have _on_bundle_rejected handler"

        assert hasattr(window, '_on_accept_all_high_confidence'), \
            "Should have _on_accept_all_high_confidence handler"

        assert hasattr(window, '_on_skip_to_manual_workflow'), \
            "Should have _on_skip_to_manual_workflow handler"

        # Test view switching methods
        # Note: We need to show the window first for visibility tests to work properly
        window.show()

        print("  Testing _show_bundle_view()...")
        initial_bundle_visibility = window.bundle_suggestions_view.isVisible()
        window._show_bundle_view()

        # Check that the method was called (step changed)
        assert window.current_step == WorkflowStep.BUNDLE_SUGGESTIONS, \
            f"Current step should be BUNDLE_SUGGESTIONS after _show_bundle_view(), got {window.current_step}"

        print("  Testing _show_manual_view()...")
        window._show_manual_view()

        # Check workflow state changes
        assert window.current_step == WorkflowStep.STITCHING, \
            f"Current step should be STITCHING after _show_manual_view(), got {window.current_step}"

        window.close()

        print("  [OK] Bundle suggestions workflow working correctly")
        return True

    except Exception as e:
        print(f"  [FAIL] Bundle suggestions workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bundle_view_integration():
    """Test BundleSuggestionsView integration with ConvertImagesWindow"""
    print("\n[TEST] Bundle View Integration")

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from gui import ConvertImagesWindow
        from bundle_widgets import BundleSuggestionsView

        window = ConvertImagesWindow()

        # Verify bundle view is properly connected
        bundle_view = window.bundle_suggestions_view
        assert isinstance(bundle_view, BundleSuggestionsView), \
            "bundle_suggestions_view should be BundleSuggestionsView instance"

        # Test signal connections exist (they should be connected in __init__)
        # We can't directly test signal connections, but we can verify the slots exist
        assert hasattr(bundle_view, 'bundle_accepted'), \
            "BundleSuggestionsView should have bundle_accepted signal"
        assert hasattr(bundle_view, 'bundle_modified'), \
            "BundleSuggestionsView should have bundle_modified signal"
        assert hasattr(bundle_view, 'bundle_rejected'), \
            "BundleSuggestionsView should have bundle_rejected signal"
        assert hasattr(bundle_view, 'accept_all_high'), \
            "BundleSuggestionsView should have accept_all_high signal"
        assert hasattr(bundle_view, 'skip_to_manual'), \
            "BundleSuggestionsView should have skip_to_manual signal"

        # Test bundle view methods
        assert hasattr(bundle_view, 'set_bundles'), \
            "BundleSuggestionsView should have set_bundles method"
        assert hasattr(bundle_view, 'get_bundle_count'), \
            "BundleSuggestionsView should have get_bundle_count method"
        assert hasattr(bundle_view, 'get_high_confidence_bundles'), \
            "BundleSuggestionsView should have get_high_confidence_bundles method"

        # Test with empty bundle list
        bundle_view.set_bundles([])
        assert bundle_view.get_bundle_count() == 0, \
            "Bundle count should be 0 for empty list"

        # Test with sample bundles
        sample_bundles = [
            {
                'document_type': 'Invoice',
                'company': 'Acme Corp',
                'document_date': '2024-01-15',
                'confidence_score': 0.92,
                'file_paths': ['test1.png', 'test2.png']
            },
            {
                'document_type': 'Statement',
                'company': 'Beta Inc',
                'document_date': '2024-01-10',
                'confidence_score': 0.65,
                'file_paths': ['test3.png']
            }
        ]

        bundle_view.set_bundles(sample_bundles)
        assert bundle_view.get_bundle_count() == 2, \
            f"Bundle count should be 2, got {bundle_view.get_bundle_count()}"

        high_conf_bundles = bundle_view.get_high_confidence_bundles()
        assert len(high_conf_bundles) == 1, \
            f"Should have 1 high confidence bundle (>= 0.8), got {len(high_conf_bundles)}"
        assert high_conf_bundles[0]['confidence_score'] >= 0.8, \
            "High confidence bundle should have score >= 0.8"

        window.close()

        print("  [OK] Bundle view integration working correctly")
        return True

    except Exception as e:
        print(f"  [FAIL] Bundle view integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_workflow_step_values():
    """Test that workflow step enum has correct values for Step 0"""
    print("\n[TEST] Workflow Step Values")

    try:
        from gui import WorkflowStep

        # Verify Step 0 is BUNDLE_SUGGESTIONS
        assert WorkflowStep.BUNDLE_SUGGESTIONS.value == 0, \
            f"BUNDLE_SUGGESTIONS should be step 0, got {WorkflowStep.BUNDLE_SUGGESTIONS.value}"

        # Verify other steps shifted correctly
        assert WorkflowStep.STITCHING.value == 1, \
            f"STITCHING should be step 1, got {WorkflowStep.STITCHING.value}"
        assert WorkflowStep.ANALYSIS.value == 2, \
            f"ANALYSIS should be step 2, got {WorkflowStep.ANALYSIS.value}"
        assert WorkflowStep.ORDERING.value == 3, \
            f"ORDERING should be step 3, got {WorkflowStep.ORDERING.value}"
        assert WorkflowStep.FINALIZATION.value == 4, \
            f"FINALIZATION should be step 4, got {WorkflowStep.FINALIZATION.value}"

        print("  [OK] Workflow step values correct")
        return True

    except Exception as e:
        print(f"  [FAIL] Workflow step values test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all bundle workflow tests"""
    print("\n" + "="*70)
    print("PHASE 5 STEP 0 TESTS: Bundle Suggestions Workflow")
    print("="*70)

    tests = [
        ("Workflow Step Values", test_workflow_step_values),
        ("Bundle Suggestions Workflow", test_bundle_suggestions_workflow),
        ("Bundle View Integration", test_bundle_view_integration),
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
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("="*70 + "\n")

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
