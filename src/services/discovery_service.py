"""
Discovery Service
Manages file discovery and registration without LLM analysis.
"""

import glob
import logging
import os
import sqlite3
from collections.abc import Callable
from typing import TYPE_CHECKING

from config.config_manager import ConfigManager
from db.analysis_db import AnalysisDB
from db.repositories.image_files_repo import ImageFilesRepository

if TYPE_CHECKING:
    from services.logging_service import get_logger
else:
    get_logger = None

logger: logging.Logger | None = None


class DiscoveryService:
    """Manages automatic file discovery and registration"""

    def __init__(self, config_manager: ConfigManager, analysis_db: AnalysisDB):
        """
        Initialize discovery service.

        Args:
            config_manager: Configuration manager instance
            analysis_db: Analysis database instance
        """
        self.config = config_manager
        self.analysis_db = analysis_db

    def _get_logger(self) -> logging.Logger:
        """Get logger instance (lazy initialization)."""
        global logger
        if logger is None:
            from services.logging_service import get_logger as _get_logger

            logger = _get_logger()
        return logger

    def discover_images(
        self,
        directories: list[str],
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> int:
        """
        Discover and register image files in specified directories.

        This method scans directories for image files (PNG, JPG, JPEG) and registers
        them in the database using ImageFilesRepository. Returns count of newly
        registered files.

        Args:
            directories: List of directory paths to scan
            progress_callback: Optional callback(status_text, current, total)

        Returns:
            Count of newly registered files (not including existing files)
        """
        if not directories:
            self._get_logger().info("[DISCOVERY] No directories provided")
            return 0

        # Count newly registered files
        new_file_count = 0

        # Create repository instance
        image_repo = ImageFilesRepository(self.analysis_db.connection)

        # Collect all files first to get total count
        all_files = []
        for directory in directories:
            if not os.path.exists(directory):
                self._get_logger().warning(f"[DISCOVERY] Directory does not exist: {directory}")
                continue

            try:
                # Find all image files (PNG, JPG, JPEG) - use set to avoid duplicates
                image_files_set = set()
                for ext in ["*.png", "*.PNG", "*.jpg", "*.JPG", "*.jpeg", "*.JPEG"]:
                    try:
                        # Use recursive glob to find files in subdirectories
                        pattern = os.path.join(directory, "**", ext)
                        image_files_set.update(glob.glob(pattern, recursive=True))
                    except PermissionError as e:
                        self._get_logger().error(
                            f"[DISCOVERY] Permission denied scanning for {ext} in {directory}: {e}"
                        )
                        continue
                    except OSError as e:
                        self._get_logger().error(
                            f"[DISCOVERY] OS error scanning for {ext} in {directory}: {e}"
                        )
                        continue
                    except Exception as e:
                        self._get_logger().error(
                            f"[DISCOVERY] Unexpected error scanning for {ext} in {directory}: {e}"
                        )
                        continue

                image_files = sorted(image_files_set)
                all_files.extend(image_files)

            except PermissionError as e:
                self._get_logger().error(
                    f"[DISCOVERY] Permission denied accessing {directory}: {e}"
                )
                continue
            except OSError as e:
                self._get_logger().error(f"[DISCOVERY] OS error scanning {directory}: {e}")
                continue

        total_files = len(all_files)
        self._get_logger().info(f"[DISCOVERY] Found {total_files} image files")

        # Process each file
        for idx, image_path in enumerate(all_files):
            current = idx + 1

            try:
                # Emit progress
                if progress_callback:
                    progress_callback(
                        f"Discovering {os.path.basename(image_path)}...", current, total_files
                    )

                # Check if file already exists
                existing = image_repo.get_by_path(image_path)

                if existing:
                    # File already registered - update last_seen timestamp
                    image_repo.update_last_seen(image_path)
                    self._get_logger().debug(
                        f"[DISCOVERY] Updated last_seen: {os.path.basename(image_path)}"
                    )
                else:
                    # Register new file
                    try:
                        # Get file stats
                        file_stats = os.stat(image_path)
                        file_size = file_stats.st_size
                        file_mtime = file_stats.st_mtime

                        # Compute file hash
                        from db.metadata_db import MetadataDB

                        file_hash = MetadataDB.compute_file_hash(image_path)

                        # Extract directory and filename
                        directory_path = os.path.dirname(image_path)
                        filename = os.path.basename(image_path)

                        # Register file
                        image_repo.register(
                            file_path=image_path,
                            file_hash=file_hash,
                            directory_path=directory_path,
                            filename=filename,
                            file_size=file_size,
                            file_mtime=file_mtime,
                        )

                        new_file_count += 1
                        self._get_logger().info(f"[DISCOVERY] Registered new file: {filename}")

                    except FileNotFoundError as e:
                        self._get_logger().error(
                            f"[DISCOVERY] File not found during registration "
                            f"{os.path.basename(image_path)}: {e}"
                        )
                        # Continue with next file
                    except PermissionError as e:
                        self._get_logger().error(
                            f"[DISCOVERY] Permission denied registering {os.path.basename(image_path)}: {e}"
                        )
                        # Continue with next file
                    except OSError as e:
                        self._get_logger().error(
                            f"[DISCOVERY] OS error registering {os.path.basename(image_path)}: {e}"
                        )
                        # Continue with next file
                    except sqlite3.Error as e:
                        self._get_logger().error(
                            f"[DISCOVERY] Database error registering {os.path.basename(image_path)}: {e}"
                        )
                        # Continue with next file
                    except Exception as e:
                        self._get_logger().error(
                            f"[DISCOVERY] Unexpected error registering {os.path.basename(image_path)}: {e}"
                        )
                        # Continue with next file

            except sqlite3.Error as e:
                self._get_logger().error(
                    f"[DISCOVERY] Database error processing {os.path.basename(image_path)}: {e}"
                )
                # Continue with next file
            except Exception as e:
                self._get_logger().error(
                    f"[DISCOVERY] Unexpected error processing {os.path.basename(image_path)}: {e}"
                )
                # Continue with next file

        self._get_logger().info(f"[DISCOVERY] Completed - {new_file_count} new files registered")
        return new_file_count


# Example usage
if __name__ == "__main__":
    import logging

    from services.logging_service import LoggingService, get_logger

    LoggingService().initialize(log_level=logging.DEBUG, console_output=True)
    _logger = get_logger()

    # Create instances
    config = ConfigManager()
    analysis_db_instance = AnalysisDB()

    # Create service
    service = DiscoveryService(config, analysis_db_instance)

    # Get directories from config
    directories = analysis_db_instance.get_active_directories()

    # Test discovery
    def progress(status, current, total):
        _logger.info("[%s/%s] %s", current, total, status)

    _logger.info("Testing discovery service...")
    count = service.discover_images(directories, progress_callback=progress)
    _logger.info("Discovery complete: %s new files registered", count)

    # Cleanup
    analysis_db_instance.close()
