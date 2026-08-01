"""Manual dev utility: launch the bundle review widget and screenshot it.

Not a test — lives in scripts/ so pytest does not collect it. Run directly:
    python scripts/capture_workflow_screenshot.py
"""

import logging
import sys
import time
from pathlib import Path

from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from services.logging_service import LoggingService
from ui.bundle.bundle_review_widget import BundleReviewWidget as GuidedBundleWorkflow


def capture():
    time.sleep(0.5)
    ImageGrab.grab().save("assets/images/workflow_final.png")
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
