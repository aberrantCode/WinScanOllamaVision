"""Capture screenshot"""

import logging
import sys
import time
from pathlib import Path

from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).parent / "src"))
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from services.logging_service import LoggingService
from ui.verify_documents_window import BundleReviewWindow


def capture():
    time.sleep(0.5)
    ImageGrab.grab().save("assets/images/workflow_final.png")
    print("Captured")
    QApplication.quit()


if __name__ == "__main__":
    LoggingService().initialize(log_level=logging.INFO, console_output=False)
    app = QApplication(sys.argv)
    window = BundleReviewWindow(
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
