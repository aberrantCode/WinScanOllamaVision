"""Backward-compatibility shim for guided_bundle_workflow.

Import BundleReviewWidget under the old GuidedBundleWorkflow name so that
code written before the Phase 5 cleanup continues to work unchanged.
"""

from ui.bundle.bundle_review_widget import BundleReviewWidget as GuidedBundleWorkflow

__all__ = ["GuidedBundleWorkflow"]
