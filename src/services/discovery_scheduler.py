"""
Discovery Scheduler
Manages periodic discovery execution using QTimer.
"""

from datetime import datetime

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from config.config_manager import ConfigManager
from db.analysis_db import AnalysisDB
from services.discovery_worker import DiscoveryWorker
from services.logging_service import get_logger

logger = get_logger()


class DiscoveryScheduler(QObject):
    """Scheduler for periodic file discovery"""

    # Signals
    discovery_started = pyqtSignal()  # Discovery job started
    discovery_finished = pyqtSignal(int)  # Discovery job finished (count of new files)
    discovery_error = pyqtSignal(str)  # Discovery job error

    def __init__(self, config_manager: ConfigManager):
        """
        Initialize discovery scheduler.

        Args:
            config_manager: Configuration manager instance
        """
        super().__init__()
        self.config_manager = config_manager
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer_tick)
        self.worker: DiscoveryWorker | None = None
        self.logger = get_logger()

    def start(self):
        """
        Start periodic discovery based on config settings.

        Reads interval from Discovery.interval_minutes config setting.
        """
        # Check if discovery is enabled
        enabled = self.config_manager.get_bool("Discovery", "enabled", True)
        if not enabled:
            self.logger.info("[DISCOVERY SCHEDULER] Discovery is disabled in settings")
            return

        # Get interval from config (in minutes)
        interval_minutes = self.config_manager.get_int("Discovery", "interval_minutes", 60)

        if interval_minutes <= 0:
            self.logger.warning(
                f"[DISCOVERY SCHEDULER] Invalid interval: {interval_minutes} minutes"
            )
            return

        # Convert to milliseconds
        interval_ms = interval_minutes * 60 * 1000

        # Start timer
        self.timer.start(interval_ms)
        self.logger.info(f"[DISCOVERY SCHEDULER] Started with interval: {interval_minutes} minutes")

    def stop(self):
        """Stop periodic discovery"""
        self.timer.stop()
        self.logger.info("[DISCOVERY SCHEDULER] Stopped")

        # Stop worker if running
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)  # Wait up to 2 seconds

    def run_now(self):
        """
        Run discovery immediately (manual trigger).

        This does not affect the periodic schedule.
        """
        self.logger.info("[DISCOVERY SCHEDULER] Manual discovery triggered")
        self._execute_discovery()

    def _on_timer_tick(self):
        """Handle timer tick event"""
        self.logger.info("[DISCOVERY SCHEDULER] Timer tick - starting discovery")
        self._execute_discovery()

    def _execute_discovery(self):
        """Execute discovery job"""
        # Don't start new discovery if one is already running
        if self.worker and self.worker.isRunning():
            self.logger.warning("[DISCOVERY SCHEDULER] Discovery already running, skipping")
            return

        # Get directories from database
        analysis_db = AnalysisDB()
        try:
            directories = analysis_db.get_active_directories()
        finally:
            analysis_db.close()

        if not directories:
            self.logger.warning("[DISCOVERY SCHEDULER] No active directories configured")
            return

        # Create worker
        self.worker = DiscoveryWorker(self.config_manager, directories)

        # Connect signals
        self.worker.finished.connect(self._on_discovery_finished)
        self.worker.error.connect(self._on_discovery_error)

        # Emit started signal
        self.discovery_started.emit()

        # Start worker
        self.worker.start()

    def _on_discovery_finished(self, count: int):
        """
        Handle discovery finished.

        Args:
            count: Number of new files discovered
        """
        self.logger.info(f"[DISCOVERY SCHEDULER] Discovery finished - {count} new files")

        # Update last run timestamp in config
        timestamp = datetime.now().isoformat()
        self.config_manager.set_setting("Discovery", "last_run", timestamp)

        # Emit finished signal
        self.discovery_finished.emit(count)

    def _on_discovery_error(self, error: str):
        """
        Handle discovery error.

        Args:
            error: Error message
        """
        self.logger.error(f"[DISCOVERY SCHEDULER] Discovery error: {error}")

        # Emit error signal
        self.discovery_error.emit(error)


# Example usage
if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    config = ConfigManager()
    scheduler = DiscoveryScheduler(config)

    def on_started():
        print("Discovery started")

    def on_finished(count):
        print(f"Discovery finished: {count} new files")

    def on_error(error):
        print(f"Error: {error}")

    scheduler.discovery_started.connect(on_started)
    scheduler.discovery_finished.connect(on_finished)
    scheduler.discovery_error.connect(on_error)

    # Start periodic discovery
    scheduler.start()

    # Run manual discovery after 2 seconds
    QTimer.singleShot(2000, scheduler.run_now)

    print("Scheduler started. Press Ctrl+C to exit.")
    sys.exit(app.exec())
