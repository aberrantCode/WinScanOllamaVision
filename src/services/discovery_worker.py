"""
Discovery Worker Thread
Background worker for running file discovery without blocking UI.
"""

import sqlite3

from PyQt6.QtCore import QThread, pyqtSignal

from config.config_manager import ConfigManager
from db.analysis_db import AnalysisDB
from services.discovery_service import DiscoveryService
from services.logging_service import get_logger

logger = get_logger()


class DiscoveryWorker(QThread):
    """Background worker thread for file discovery"""

    # Signals
    progress = pyqtSignal(str, int, int)  # (status_text, current, total)
    finished = pyqtSignal(int)  # (count_of_new_files)
    error = pyqtSignal(str)  # (error_message)

    def __init__(self, config_manager: ConfigManager, directories: list[str]):
        """
        Initialize discovery worker.

        Args:
            config_manager: Configuration manager instance
            directories: List of directories to scan
        """
        super().__init__()
        self.config_manager = config_manager
        self.directories = directories
        self._stop_requested = False

    def run(self):
        """Execute discovery in background thread"""
        # Create thread-local database connection
        thread_analysis_db = None

        try:
            logger.info("[DISCOVERY WORKER] Starting discovery worker")

            # Create new database instance for this thread
            thread_analysis_db = AnalysisDB()
            thread_discovery_service = DiscoveryService(self.config_manager, thread_analysis_db)

            def progress_callback(status_text: str, current: int, total: int):
                """Progress callback that emits signal and checks for cancellation"""
                if self._stop_requested:
                    raise InterruptedError("Discovery cancelled by user")
                self.progress.emit(status_text, current, total)

            # Run discovery
            count = thread_discovery_service.discover_images(
                self.directories, progress_callback=progress_callback
            )

            # Emit finished signal with count
            self.finished.emit(count)
            logger.info(f"[DISCOVERY WORKER] Completed - {count} new files")

        except InterruptedError:
            # Discovery was cancelled
            logger.info("[DISCOVERY WORKER] Discovery cancelled by user")
            self.finished.emit(0)

        except sqlite3.Error as e:
            import traceback

            error_msg = f"Database error: {str(e)}\n{traceback.format_exc()}"
            logger.error(f"[DISCOVERY WORKER] {error_msg}")
            self.error.emit(error_msg)

        except OSError as e:
            import traceback

            error_msg = f"File system error: {str(e)}\n{traceback.format_exc()}"
            logger.error(f"[DISCOVERY WORKER] {error_msg}")
            self.error.emit(error_msg)

        except Exception as e:
            import traceback

            error_msg = f"Unexpected discovery error: {str(e)}\n{traceback.format_exc()}"
            logger.error(f"[DISCOVERY WORKER] {error_msg}")
            self.error.emit(error_msg)

        finally:
            # Clean up thread-local connection
            if thread_analysis_db:
                thread_analysis_db.close()

    def stop(self):
        """Request worker to stop"""
        self._stop_requested = True
        logger.info("[DISCOVERY WORKER] Stop requested")


# Example usage
if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    from config.config_manager import ConfigManager

    app = QApplication(sys.argv)

    config = ConfigManager()
    analysis_db_instance = AnalysisDB()
    directories = analysis_db_instance.get_active_directories()

    worker = DiscoveryWorker(config, directories)

    def on_progress(status, current, total):
        print(f"[{current}/{total}] {status}")

    def on_finished(count):
        print(f"Discovery finished: {count} new files")
        app.quit()

    def on_error(error):
        print(f"Error: {error}")
        app.quit()

    worker.progress.connect(on_progress)
    worker.finished.connect(on_finished)
    worker.error.connect(on_error)

    worker.start()

    sys.exit(app.exec())
