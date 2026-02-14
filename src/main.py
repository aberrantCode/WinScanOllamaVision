import argparse
import logging
import sys

# Import only LoggingService first, before any modules that use it
from services.logging_service import LoggingService, get_logger

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

    # Initialize logging service BEFORE importing other modules
    logging_service = LoggingService()
    logging_service.initialize(
        log_level=logging.DEBUG,  # File logging always at DEBUG
        console_output=args.console,  # Enable console if --console flag provided
        console_level=console_level,  # Use specified console level
    )
    logger = get_logger()

    # Now import modules that depend on logging (after LoggingService is initialized)
    from PyQt6.QtWidgets import QApplication

    from config.appdata_manager import initialize_appdata
    from config.config_manager import ConfigManager
    from db.analysis_db import AnalysisDB
    from db.metadata_db import MetadataDB
    from services.analysis_service import AnalysisService
    from ui.gui import StartupWindow
    from ui.theme_manager import ThemeManager

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

        # Discovery on startup (if enabled)
        scan_on_startup = config_manager.get_bool("SourceDirectories", "scan_on_startup", True)
        if scan_on_startup:
            logger.info("Scan on startup enabled - triggering discovery")
            from PyQt6.QtCore import QTimer

            from services.discovery_scheduler import DiscoveryScheduler
            from services.discovery_worker import DiscoveryWorker
            from ui.toast_notifier import ToastNotifier

            # Get directories from config (not database)
            directories = config_manager.get_directories()

            if directories:

                def start_discovery():
                    """Start discovery after window is fully rendered"""
                    # Show status message on startup window
                    startup_window._show_status_label("🔍 Discovering new files...")

                    # Create discovery worker
                    discovery_worker = DiscoveryWorker(config_manager, directories)
                    toast_notifier = ToastNotifier()

                    def on_discovery_finished(count):
                        """Handle startup discovery completion"""
                        logger.info(f"Startup discovery finished - {count} new files registered")

                        # Update status label with result
                        if count == 0:
                            startup_window._show_status_label(
                                "✓ Discovery complete - No new files found"
                            )
                        elif count == 1:
                            startup_window._show_status_label(
                                "✓ Discovery complete - 1 new file found"
                            )
                        else:
                            startup_window._show_status_label(
                                f"✓ Discovery complete - {count} new files found"
                            )

                        # Show toast notification
                        toast_notifier.show_discovery_toast(count)

                        # Check if auto-analyze is enabled
                        auto_analyze = config_manager.get_bool(
                            "Discovery", "auto_analyze_after_discovery", False
                        )

                        if auto_analyze and count > 0:
                            logger.info("Auto-analyze enabled - launching analysis")
                            # Hide discovery status before launching analysis
                            QTimer.singleShot(2000, startup_window._hide_status_label)
                            # Trigger analysis on newly discovered files
                            startup_window.manual_analyze_documents()
                        else:
                            # Hide status after 5 seconds
                            QTimer.singleShot(5000, startup_window._hide_status_label)

                    def on_discovery_error(error):
                        """Handle startup discovery error"""
                        logger.error(f"Startup discovery error: {error}")
                        startup_window._show_status_label(f"⚠ Discovery error: {error[:50]}")
                        # Hide error message after 10 seconds
                        QTimer.singleShot(10000, startup_window._hide_status_label)

                    # Connect signals
                    discovery_worker.finished.connect(on_discovery_finished)
                    discovery_worker.error.connect(on_discovery_error)

                    # Start discovery worker
                    discovery_worker.start()
                    logger.info("Startup discovery worker started")

                    # Store reference to prevent garbage collection
                    startup_window._startup_discovery_worker = discovery_worker

                # Delay discovery start to ensure window is fully rendered (500ms)
                QTimer.singleShot(500, start_discovery)
            else:
                logger.info("No directories configured for startup discovery")
        else:
            logger.info("Scan on startup disabled")

        # Initialize periodic discovery scheduler (if enabled)
        discovery_enabled = config_manager.get_bool("Discovery", "enabled", True)
        if discovery_enabled:
            logger.info("Periodic discovery enabled - initializing scheduler")
            from services.discovery_scheduler import DiscoveryScheduler

            discovery_scheduler = DiscoveryScheduler(config_manager)

            # Start scheduler
            discovery_scheduler.start()
            logger.info("Discovery scheduler started")

            # Store reference in startup window to prevent garbage collection
            startup_window._discovery_scheduler = discovery_scheduler  # type: ignore[attr-defined]
        else:
            logger.info("Periodic discovery disabled")

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
