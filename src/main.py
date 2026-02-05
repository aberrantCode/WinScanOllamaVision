import logging
import sys

from PyQt6.QtWidgets import QApplication

from config.appdata_manager import initialize_appdata
from config.config_manager import ConfigManager
from db.analysis_db import AnalysisDB
from db.metadata_db import MetadataDB
from services.analysis_service import AnalysisService
from services.logging_service import LoggingService, get_logger
from ui.gui import StartupWindow

# Import style sheet
from ui.style import stylesheet

if __name__ == "__main__":
    # Initialize logging service
    logging_service = LoggingService()
    logging_service.initialize(log_level=logging.INFO)
    logging_service.clear_log_file()  # Clear previous log
    logger = get_logger()

    try:
        logger.info("Application starting...")

        # Initialize AppData directory (settings and database)
        logger.info("Initializing AppData directory...")
        settings_path, db_path = initialize_appdata()
        logger.info(f"AppData initialized - Settings: {settings_path}, Database: {db_path}")

        app = QApplication(sys.argv)
        logger.info("QApplication instance created.")

        app.setStyleSheet(stylesheet)
        logger.info("Stylesheet applied.")

        logger.info("Creating StartupWindow...")
        startup_window = StartupWindow()
        logger.info("StartupWindow instance created.")

        # Initialize analysis service
        logger.info("Initializing AnalysisService...")
        config_manager = ConfigManager()
        analysis_db = AnalysisDB()
        metadata_db = MetadataDB()
        analysis_service = AnalysisService(config_manager, analysis_db, metadata_db)
        logger.info("AnalysisService initialized.")

        # Store analysis_service in window for manual button access
        startup_window.analysis_service = analysis_service

        logger.info("Showing StartupWindow...")
        startup_window.show()
        logger.info("StartupWindow.show() called.")

        # Check for unanalyzed files and optionally start analysis
        # DISABLED: User can now use the "Analyze Documents" button to manually trigger analysis
        # def check_unanalyzed():
        #     try:
        #         logger.info("Checking for unanalyzed files...")
        #         startup_window.check_for_unanalyzed_files(analysis_service)
        #         logger.info("Unanalyzed files check complete.")
        #     except Exception as e:
        #         logger.error(f"Error checking for unanalyzed files: {e}", exc_info=True)
        #
        # QTimer.singleShot(1000, check_unanalyzed)  # Increased to 1 second to ensure window is fully rendered

        logger.info("Entering QApplication event loop...")
        exit_code = app.exec()

        # Cleanup
        logger.info("Cleaning up resources...")
        analysis_db.close()
        metadata_db.close()

        logger.info(f"Application exited with code {exit_code}.")
        sys.exit(exit_code)

    except Exception:
        logger.exception("An unhandled exception occurred")
        sys.exit(1)
