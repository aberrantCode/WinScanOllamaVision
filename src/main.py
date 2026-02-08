import argparse
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
from ui.theme_manager import ThemeManager

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="WinScanLLM - Document scanning and analysis with LLM integration"
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Enable console logging output (shows all log messages in terminal)",
    )
    parser.add_argument(
        "--console-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="DEBUG",
        help="Set console logging level (default: DEBUG). Only used when --console is enabled.",
    )
    args = parser.parse_args()

    # Convert console level string to logging constant
    console_level = getattr(logging, args.console_level) if args.console else None

    # Initialize logging service
    logging_service = LoggingService()
    logging_service.initialize(
        log_level=logging.DEBUG,  # File logging always at DEBUG
        console_output=args.console,  # Enable console if --console flag provided
        console_level=console_level,  # Use specified console level
    )
    logger = get_logger()

    try:
        logger.info("=" * 80)
        logger.info("NEW SESSION STARTED")
        logger.info("=" * 80)
        logger.info("Application starting...")

        # Initialize AppData directory (settings and database)
        logger.info("Initializing AppData directory...")
        settings_path, db_path = initialize_appdata()
        logger.info(f"AppData initialized - Settings: {settings_path}, Database: {db_path}")

        # Initialize config to get theme preference
        logger.info("Loading configuration...")
        config_manager = ConfigManager()
        theme = config_manager.get_setting("Theme", "theme", "dark")
        is_dark_mode = theme == "dark"
        logger.info(f"Theme preference: {theme}")

        app = QApplication(sys.argv)
        logger.info("QApplication instance created.")

        # Apply centralized theme stylesheet
        app.setStyleSheet(ThemeManager.get_stylesheet(is_dark_mode))
        logger.info(f"ThemeManager stylesheet applied (dark_mode={is_dark_mode}).")

        logger.info("Creating StartupWindow...")
        startup_window = StartupWindow()
        logger.info("StartupWindow instance created.")

        # Initialize analysis service
        logger.info("Initializing AnalysisService...")
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
