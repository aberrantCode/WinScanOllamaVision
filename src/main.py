import sys
import os
import traceback
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from gui import StartupWindow
from appdata_manager import initialize_appdata
from analysis_service import AnalysisService
from analysis_db import AnalysisDB
from metadata_db import MetadataDB
from config_manager import ConfigManager

# Import style sheet
from style import stylesheet

log_file_path = "app.log"

def log_message(message):
    """Appends a message to the log file."""
    with open(log_file_path, "a") as log_file:
        log_file.write(f"{message}\n")

if __name__ == "__main__":
    # Clear previous log file
    if os.path.exists(log_file_path):
        os.remove(log_file_path)

    try:
        log_message("Application starting...")

        # Initialize AppData directory (settings and database)
        log_message("Initializing AppData directory...")
        settings_path, db_path = initialize_appdata()
        log_message(f"AppData initialized - Settings: {settings_path}, Database: {db_path}")

        app = QApplication(sys.argv)
        log_message("QApplication instance created.")
        
        app.setStyleSheet(stylesheet)
        log_message("Stylesheet applied.")
        
        log_message("Creating StartupWindow...")
        startup_window = StartupWindow()
        log_message("StartupWindow instance created.")

        # Initialize analysis service
        log_message("Initializing AnalysisService...")
        config_manager = ConfigManager()
        analysis_db = AnalysisDB()
        metadata_db = MetadataDB()
        analysis_service = AnalysisService(config_manager, analysis_db, metadata_db)
        log_message("AnalysisService initialized.")

        log_message("Showing StartupWindow...")
        startup_window.show()
        log_message("StartupWindow.show() called.")

        # Check for unanalyzed files and optionally start analysis
        # Use QTimer to defer this check until after window is fully shown
        def check_unanalyzed():
            try:
                log_message("Checking for unanalyzed files...")
                startup_window.check_for_unanalyzed_files(analysis_service)
                log_message("Unanalyzed files check complete.")
            except Exception as e:
                log_message(f"Error checking for unanalyzed files: {e}")
                import traceback as tb
                log_message(tb.format_exc())

        QTimer.singleShot(1000, check_unanalyzed)  # Increased to 1 second to ensure window is fully rendered

        log_message("Entering QApplication event loop...")
        exit_code = app.exec()

        # Cleanup
        log_message("Cleaning up resources...")
        analysis_db.close()
        metadata_db.close()

        log_message(f"Application exited with code {exit_code}.")
        sys.exit(exit_code)

    except Exception as e:
        log_message("An unhandled exception occurred:")
        log_message(traceback.format_exc())
        sys.exit(1)

