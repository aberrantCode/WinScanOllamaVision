"""
Logging Service
Centralized logging service using Python's standard logging module.
Logs are stored in the user's AppData directory.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional


class LoggingService:
    """Centralized logging service for the application"""

    _instance: Optional["LoggingService"] = None
    _initialized: bool = False

    def __new__(cls):
        """Singleton pattern to ensure only one logger instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the logging service (only once)"""
        if not LoggingService._initialized:
            self.logger: logging.Logger | None = None
            self.log_file_path: str | None = None
            LoggingService._initialized = True

    def initialize(
        self,
        app_name: str = "WinScanLLM",
        log_level: int = logging.INFO,
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 5,
        console_output: bool = False,
        console_level: int | None = None,
    ):
        """
        Initialize the logging configuration.

        Args:
            app_name: Application name for log directory
            log_level: Logging level for file handler (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            max_bytes: Maximum size of log file before rotation
            backup_count: Number of backup log files to keep
            console_output: If True, enables console logging at console_level
            console_level: Logging level for console handler (defaults to log_level if not specified)
        """
        if self.logger is not None:
            return  # Already initialized

        # Determine log file location in AppData
        appdata_root = os.getenv(
            "APPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
        )
        log_dir = os.path.join(appdata_root, app_name, "logs")

        # Create log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)

        # Set log file path
        self.log_file_path = os.path.join(log_dir, "app.log")

        # Create logger
        self.logger = logging.getLogger(app_name)
        self.logger.setLevel(log_level)

        # Remove any existing handlers
        self.logger.handlers.clear()

        # Create rotating file handler
        file_handler = RotatingFileHandler(
            self.log_file_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setLevel(log_level)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)

        # Add file handler
        self.logger.addHandler(file_handler)

        # Optionally add console handler
        if console_output:
            console_handler = logging.StreamHandler()
            # Use console_level if specified, otherwise use file log_level
            handler_level = console_level if console_level is not None else log_level
            console_handler.setLevel(handler_level)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            self.logger.info(
                f"Console logging enabled at level {logging.getLevelName(handler_level)}"
            )

        # Log initialization
        self.logger.info(f"Logging service initialized. Log file: {self.log_file_path}")

    def get_logger(self) -> logging.Logger:
        """
        Get the logger instance.

        Returns:
            Logger instance

        Raises:
            RuntimeError: If logger is not initialized
        """
        if self.logger is None:
            raise RuntimeError("LoggingService not initialized. Call initialize() first.")
        return self.logger

    def get_log_file_path(self) -> str | None:
        """
        Get the current log file path.

        Returns:
            Path to log file or None if not initialized
        """
        return self.log_file_path

    def debug(self, message: str):
        """Log debug message"""
        self.get_logger().debug(message)

    def info(self, message: str):
        """Log info message"""
        self.get_logger().info(message)

    def warning(self, message: str):
        """Log warning message"""
        self.get_logger().warning(message)

    def error(self, message: str, exc_info: bool = False):
        """
        Log error message.

        Args:
            message: Error message
            exc_info: If True, include exception traceback
        """
        self.get_logger().error(message, exc_info=exc_info)

    def critical(self, message: str, exc_info: bool = False):
        """
        Log critical message.

        Args:
            message: Critical message
            exc_info: If True, include exception traceback
        """
        self.get_logger().critical(message, exc_info=exc_info)

    def exception(self, message: str):
        """
        Log exception with traceback.

        Args:
            message: Exception message
        """
        self.get_logger().exception(message)

    def clear_log_file(self):
        """Clear the current log file"""
        if self.log_file_path and os.path.exists(self.log_file_path):
            try:
                open(self.log_file_path, "w").close()
                self.info("Log file cleared")
            except Exception as e:
                self.error(f"Failed to clear log file: {e}", exc_info=True)


# Convenience function for getting the logging service
def get_logger() -> logging.Logger:
    """
    Get the application logger instance.

    Returns a fallback logger if the LoggingService has not been initialized yet.
    Once LoggingService.initialize() is called, subsequent calls return the
    fully configured logger.

    Returns:
        Logger instance

    Example:
        >>> from services.logging_service import get_logger
        >>> logger = get_logger()
        >>> logger.info("Application started")
    """
    service = LoggingService()
    if service.logger is not None:
        return service.logger
    # Return a fallback logger before LoggingService is initialized.
    # Messages will go to the root logger (typically stderr) until
    # LoggingService.initialize() is called.
    return logging.getLogger("WinScanLLM")


# Example usage
if __name__ == "__main__":
    # Initialize logging service
    logging_service = LoggingService()
    logging_service.initialize(log_level=logging.DEBUG)

    # Get logger
    logger = get_logger()

    # Test logging
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    try:
        raise ValueError("Test exception")
    except Exception:
        logger.exception("An exception occurred")

    logger.info(f"Log file location: {logging_service.get_log_file_path()}")
