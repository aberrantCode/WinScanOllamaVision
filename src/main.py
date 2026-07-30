import argparse
import logging
import os
import sys
from pathlib import Path

from __version__ import __version__ as _app_version

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
    from services.notification_service import NotificationService

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
        toast_notifier = NotificationService()

        import_panel = getattr(window, "import_panel", None)
        if import_panel is not None:
            # Give the Import view the same visible "scanning…" state and
            # control lock the manual "Discover Images" button uses, so a
            # startup scan doesn't run invisibly while the user can still
            # click into a race with a second worker.
            import_panel.lock_for_external_scan(discovery_worker)

        def on_discovery_finished(count: int) -> None:
            get_logger().info("Startup discovery finished – %s new files registered", count)
            toast_notifier.show_discovery_toast(count)
            import_panel = getattr(window, "import_panel", None)
            if import_panel is not None:
                import_panel.maybe_show_analyze_nudge_after_discovery(count)

        def on_discovery_error(error: str) -> None:
            get_logger().error("Startup discovery error: %s", error)

        discovery_worker.finished.connect(on_discovery_finished)
        discovery_worker.error.connect(on_discovery_error)
        discovery_worker.start()
        get_logger().info("Startup discovery worker started")

        # Prevent garbage collection by attaching to the window
        window._startup_discovery_worker = discovery_worker  # type: ignore[attr-defined]

    # Delay by 500 ms so the window finishes rendering first
    QTimer.singleShot(500, start_discovery)


def _start_llm_preflight_if_enabled(window, config_manager) -> None:
    """Run a deferred, non-blocking LLM readiness check shortly after the UI is up.

    Verifies the active provider is reachable and its configured model is present
    *before* the user triggers analysis. Runs off the main thread on a QThread so
    the reachability probe (and any auto-download) never blocks the event loop.

    Non-blocking contract: startup NEVER pops a modal and NEVER prompts inline.
    ``approve_callback=None`` means a missing model on ``prompt`` policy is
    surfaced via a StatusEvent + toast (the user resolves it in Settings); only
    ``auto`` policy performs a download here, and even that runs on the worker.
    """
    if not config_manager.get_bool("LLMPreflight", "verify_on_startup", True):
        get_logger().info("LLM preflight on startup disabled")
        return

    from PyQt6.QtCore import QTimer

    from services.llm_readiness_worker import LLMPreflightWorker
    from services.notification_service import NotificationService

    policy = config_manager.get_setting("LLMPreflight", "model_download_policy", "prompt")

    def start_preflight() -> None:
        worker = LLMPreflightWorker(config_manager, policy, approve_callback=None)

        def on_preflight_finished(result: object) -> None:
            ok = getattr(result, "ok", False)
            message = getattr(result, "message", "")
            if ok:
                get_logger().info("LLM preflight OK: %s", message)
                return
            get_logger().warning("LLM preflight not ready: %s", message)
            # StatusEvent already emitted inside the service; add a toast.
            try:
                NotificationService().show_preflight_toast(message)
            except Exception as exc:  # pragma: no cover - defensive
                get_logger().debug("Preflight toast failed: %s", exc)

        def on_preflight_error(error: str) -> None:
            get_logger().error("LLM preflight worker error: %s", error)

        worker.result_ready.connect(on_preflight_finished)
        worker.error.connect(on_preflight_error)
        worker.start()
        get_logger().info("LLM preflight worker started (policy=%s)", policy)

        # Prevent garbage collection by attaching to the window.
        window._llm_preflight_worker = worker  # type: ignore[attr-defined]

    # Delay so the window finishes rendering before any network I/O begins.
    QTimer.singleShot(1500, start_preflight)


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


def _start_update_check_if_enabled(window, config_manager) -> None:
    """Start a one-shot self-update check ~10s after the UI is ready.

    Polls GitHub Releases, emits a signal when a newer version exists.
    The banner on the main window subscribes to UpdateService signals.
    """
    if not config_manager.get_bool("Updates", "check_on_startup", True):
        get_logger().info("Update-on-startup disabled")
        return

    from pathlib import Path

    from PyQt6.QtCore import QTimer

    from config.appdata_manager import AppDataManager
    from services.update_service_qt import UpdateService

    owner, repo = "aberrantCode", "WinScanOllamaVision"
    cache_path = Path(AppDataManager().get_appdata_dir()) / "update_cache.json"
    ua = f"WinScanLLM-updater/{_app_version} (+https://github.com/{owner}/{repo})"

    update_service = UpdateService(
        owner=owner,
        repo=repo,
        current_version=_app_version,
        cache_path=cache_path,
        include_prereleases=config_manager.get_bool("Updates", "include_prereleases", False),
        skipped_version=config_manager.get_setting("Updates", "skipped_version", ""),
        user_agent=ua,
    )

    def _on_update_available(info) -> None:  # type: ignore[no-untyped-def]
        get_logger().info("Update available: v%s", info.version)
        if hasattr(window, "update_banner"):
            window.update_banner.show_for(info, current_version=_app_version)

    update_service.update_available.connect(_on_update_available)

    # Attach to the window to prevent GC
    window._update_service = update_service  # type: ignore[attr-defined]

    QTimer.singleShot(10_000, update_service.check_for_updates)
    get_logger().info("Update check scheduled for 10s after UI ready")


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
    from ui.theme.theme_manager import ThemeManager

    try:
        logger.info("=" * 80)
        logger.info("NEW SESSION STARTED")
        logger.info("=" * 80)
        logger.info("Application starting (WinScanLLM %s)...", _app_version)

        # Initialize AppData directory (settings and database)
        logger.info("Initializing AppData directory...")
        settings_path, db_path = initialize_appdata()
        logger.info("AppData initialized - Settings: %s, Database: %s", settings_path, db_path)

        # Initialize config to get theme preference and app name
        logger.info("Loading configuration...")
        config_manager = ConfigManager()
        _seed_default_source_directory(config_manager)
        theme = config_manager.get_setting("Theme", "theme", "dark")
        is_dark_mode = theme == "dark"
        app_name = config_manager.get_setting("GUI", "app_name", "WinScanLLM")
        logger.info("Theme preference: %s", theme)

        app = QApplication(sys.argv)
        logger.info("QApplication instance created.")

        # Apply centralized theme stylesheet
        app.setStyleSheet(ThemeManager.get_stylesheet(is_dark_mode))
        logger.info("ThemeManager stylesheet applied (dark_mode=%s).", is_dark_mode)

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

            # Keep a strong reference so the window is not garbage-collected;
            # attaching to app ties GC lifetime to the QApplication instance.
            app.pipeline_window = pipeline_window  # type: ignore[attr-defined]

            # ── Step 7: image scan if enabled ─────────────────────────────
            _start_discovery_if_enabled(pipeline_window, config_manager)

            # Start periodic background discovery scheduler if enabled
            _start_periodic_scheduler(pipeline_window, config_manager)

            # LLM readiness preflight (deferred, non-blocking, off-thread)
            _start_llm_preflight_if_enabled(pipeline_window, config_manager)

            # Close splash and show the pipeline
            splash.close()
            pipeline_window.show()
            logger.info("DocumentPipelineWindow shown.")

            # ── Step 8: self-update check if enabled ──────────────────────
            _start_update_check_if_enabled(pipeline_window, config_manager)

        worker = InitializationWorker(config_manager)
        worker.status_changed.connect(splash.update_status)
        # The splash gates on both init completion AND one full animation loop.
        worker.init_complete.connect(splash.mark_init_done)
        splash.ready_to_close.connect(_on_init_complete)
        worker.start()
        logger.info("Initialization worker started.")

        # Keep a strong reference to the worker; attaching to app ties GC
        # lifetime to the QApplication instance.
        app.worker = worker  # type: ignore[attr-defined]

        # ── Event loop ────────────────────────────────────────────────────────
        logger.info("Entering QApplication event loop...")
        exit_code = app.exec()

        # DB connections are owned and closed by DocumentPipelineWindow.closeEvent()
        logger.info("Application exited with code %s.", exit_code)
        sys.exit(exit_code)

    except Exception:
        logger.exception("An unhandled exception occurred")
        sys.exit(1)
