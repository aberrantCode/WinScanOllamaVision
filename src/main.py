import argparse
import logging
import os
import sys
from pathlib import Path

# Import only LoggingService first, before any modules that use it
from services.logging_service import LoggingService, get_logger

# ---------------------------------------------------------------------------
# Helper functions — defined before __main__ so they are available when
# _on_init_complete is called from within app.exec() via Qt signal delivery.
# ---------------------------------------------------------------------------


def _start_discovery_if_enabled(window, config_manager) -> None:
    """
    Start a one-shot startup discovery scan if enabled in settings.

    Runs in the background; results are committed to the database so the
    pipeline's Import panel reflects newly registered files on next refresh.
    """
    from PyQt6.QtCore import QTimer

    from services.discovery_worker import DiscoveryWorker
    from ui.toast_notifier import ToastNotifier

    scan_on_startup = config_manager.get_bool("SourceDirectories", "scan_on_startup", True)
    if not scan_on_startup:
        get_logger().info("Scan on startup disabled")
        return

    directories = config_manager.get_directories()
    if not directories:
        get_logger().info("No directories configured for startup discovery")
        return

    get_logger().info("Scan on startup enabled – triggering discovery")

    def start_discovery() -> None:
        discovery_worker = DiscoveryWorker(config_manager, directories)
        toast_notifier = ToastNotifier()

        def on_discovery_finished(count: int) -> None:
            get_logger().info(f"Startup discovery finished – {count} new files registered")
            toast_notifier.show_discovery_toast(count)

        def on_discovery_error(error: str) -> None:
            get_logger().error(f"Startup discovery error: {error}")

        discovery_worker.finished.connect(on_discovery_finished)
        discovery_worker.error.connect(on_discovery_error)
        discovery_worker.start()
        get_logger().info("Startup discovery worker started")

        # Prevent garbage collection by attaching to the window
        window._startup_discovery_worker = discovery_worker  # type: ignore[attr-defined]

    # Delay by 500 ms so the window finishes rendering first
    QTimer.singleShot(500, start_discovery)


def _start_periodic_scheduler(window, config_manager) -> None:
    """Initialize and start the periodic discovery scheduler if enabled."""
    discovery_enabled = config_manager.get_bool("Discovery", "enabled", True)
    if not discovery_enabled:
        get_logger().info("Periodic discovery disabled")
        return

    get_logger().info("Periodic discovery enabled – initializing scheduler")

    from services.discovery_scheduler import DiscoveryScheduler

    discovery_scheduler = DiscoveryScheduler(config_manager)
    discovery_scheduler.start()
    get_logger().info("Discovery scheduler started")

    # Attach to the window to prevent garbage collection
    window._discovery_scheduler = discovery_scheduler  # type: ignore[attr-defined]


def _seed_default_source_directory(config_manager) -> None:  # type: ignore[no-untyped-def]
    """
    If no source directories are configured, add ~/Pictures/Scans as the default.

    Creates the directory on disk if it does not already exist so the discovery
    scanner can immediately traverse it on first run.
    """
    if config_manager.get_directories():
        return  # already configured — nothing to do

    default_dir = Path.home() / "Pictures" / "Scans"
    default_path = os.path.normpath(str(default_dir))

    try:
        default_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        get_logger().warning("Could not create default scan directory %s: %s", default_path, e)

    config_manager.add_directory(default_path)
    get_logger().info("No source directories configured — added default: %s", default_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

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
    from ui.startup import InitializationWorker, SplashScreen
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

        # Initialize config to get theme preference and app name
        logger.info("Loading configuration...")
        config_manager = ConfigManager()
        _seed_default_source_directory(config_manager)
        theme = config_manager.get_setting("Theme", "theme", "dark")
        is_dark_mode = theme == "dark"
        app_name = config_manager.get_setting("GUI", "app_name", "WinScanLLM")
        logger.info(f"Theme preference: {theme}")

        app = QApplication(sys.argv)
        logger.info("QApplication instance created.")

        # Apply centralized theme stylesheet
        app.setStyleSheet(ThemeManager.get_stylesheet(is_dark_mode))
        logger.info(f"ThemeManager stylesheet applied (dark_mode={is_dark_mode}).")

        # ── Splash screen ──────────────────────────────────────────────────────
        logger.info("Showing splash screen...")
        splash = SplashScreen(app_name, is_dark_mode=is_dark_mode)
        splash.center_on_screen()
        splash.show()
        app.processEvents()  # Ensure the splash is painted before the worker starts

        # ── Initialization worker ──────────────────────────────────────────────
        # Runs steps 1-6 in a background thread so the splash animation stays
        # smooth. When the worker finishes it emits init_complete which triggers
        # the transition to the main window.

        # Mutable container so the nested callback can hold references that
        # survive beyond the function scope.
        _refs: dict = {}

        def _on_init_complete() -> None:
            """
            Called on the main thread when the initialization worker finishes.

            Closes the splash and opens the Document Pipeline window directly.
            """
            logger.info("Initialization complete – opening Document Pipeline")

            from ui.pipeline import DocumentPipelineWindow

            # The pipeline window creates and owns its own DB connections when
            # none are supplied, and closes them automatically on exit.
            pipeline_window = DocumentPipelineWindow(config_manager=config_manager)
            logger.info("DocumentPipelineWindow created.")

            # Keep a strong reference so the window is not garbage-collected
            _refs["pipeline_window"] = pipeline_window

            # ── Step 7: image scan if enabled ─────────────────────────────
            _start_discovery_if_enabled(pipeline_window, config_manager)

            # Start periodic background discovery scheduler if enabled
            _start_periodic_scheduler(pipeline_window, config_manager)

            # Close splash and show the pipeline
            splash.close()
            pipeline_window.show()
            logger.info("DocumentPipelineWindow shown.")

        worker = InitializationWorker(config_manager)
        worker.status_changed.connect(splash.update_status)
        worker.init_complete.connect(_on_init_complete)
        worker.start()
        logger.info("Initialization worker started.")

        # Keep a strong reference to the worker
        _refs["worker"] = worker

        # ── Event loop ────────────────────────────────────────────────────────
        logger.info("Entering QApplication event loop...")
        exit_code = app.exec()

        # DB connections are owned and closed by DocumentPipelineWindow.closeEvent()
        logger.info(f"Application exited with code {exit_code}.")
        sys.exit(exit_code)

    except Exception:
        logger.exception("An unhandled exception occurred")
        sys.exit(1)
