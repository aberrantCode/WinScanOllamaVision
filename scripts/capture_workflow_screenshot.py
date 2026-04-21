"""
Capture a screenshot of the bundle workflow prototype window.

Run directly from the repo root:
    python scripts/capture_workflow_screenshot.py

Produces: assets/images/workflow_final.png
"""

import logging
import sys
import time
from pathlib import Path

from PIL import ImageGrab

# Add <repo>/src to sys.path so ``from services...`` / ``from ui...`` imports
# resolve when this script is invoked directly (not via run_tests.py).
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from PyQt6.QtCore import QTimer  # noqa: E402  (import-after-sys-path is intentional)
from PyQt6.QtWidgets import QApplication  # noqa: E402

from services.logging_service import LoggingService  # noqa: E402
from ui.bundle.bundle_review_widget import (  # noqa: E402
    BundleReviewWidget as GuidedBundleWorkflow,
)


def capture() -> None:
    time.sleep(0.5)
    ImageGrab.grab().save(_REPO_ROOT / "assets" / "images" / "workflow_final.png")
    print("Captured")
    QApplication.quit()


if __name__ == "__main__":
    LoggingService().initialize(log_level=logging.INFO, console_output=False)
    app = QApplication(sys.argv)
    window = GuidedBundleWorkflow(
        bundles=None,
        start_index=0,
        prototype_mode=True,
        analysis_db=None,
        metadata_db=None,
        config_manager=None,
        parent=None,
    )
    window.show()
    QTimer.singleShot(2000, capture)
    sys.exit(app.exec())
