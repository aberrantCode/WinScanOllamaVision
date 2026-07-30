"""
Notification Service
Windows toast notification utility for discovery events.
"""

import contextlib
import logging
import os
import sys

# Try importing windows-toasts at module level
try:
    from windows_toasts import InteractableWindowsToaster, Toast, ToastDisplayImage

    WINDOWS_TOASTS_AVAILABLE = True
except ImportError:
    WINDOWS_TOASTS_AVAILABLE = False
    # Define dummy classes for type checking
    InteractableWindowsToaster = None  # type: ignore
    Toast = None  # type: ignore
    ToastDisplayImage = None  # type: ignore


class NotificationService:
    """Windows toast notification manager"""

    def __init__(self):
        """Initialize notification service"""
        self._logger: logging.Logger | None = None
        self._toasts_available = self._check_toasts_available()

    @property
    def _get_logger(self) -> logging.Logger:
        """Get logger instance (lazy initialization)."""
        if self._logger is None:
            from services.logging_service import get_logger

            self._logger = get_logger()
        return self._logger

    def _check_toasts_available(self) -> bool:
        """
        Check if windows-toasts is available and Windows 10/11 is running.

        Returns:
            True if toasts are available, False otherwise
        """
        # Check if running on Windows
        if sys.platform != "win32":
            # LoggingService not initialized yet (during tests)
            with contextlib.suppress(RuntimeError):
                self._get_logger.debug("[TOAST] Not running on Windows, toasts disabled")
            return False

        if not WINDOWS_TOASTS_AVAILABLE:
            # LoggingService not initialized yet (during tests)
            with contextlib.suppress(RuntimeError):
                self._get_logger.warning(
                    "[TOAST] windows-toasts not installed, toasts disabled. "
                    "Install with: pip install windows-toasts"
                )
            return False

        return True

    def _show(self, title: str, message: str) -> bool:
        """Build and show a single Windows toast with the given text.

        Shared by all public toast methods so icon handling and error
        suppression live in one place.

        Returns:
            True if the toast was shown, False if unavailable or on error.
        """
        if not self._toasts_available:
            self._get_logger.debug("[TOAST] Toasts not available, skipping notification")
            return False

        try:
            # Create toaster instance
            toaster = InteractableWindowsToaster("WinScanLLM")

            # Create toast
            toast = Toast()
            toast.text_fields = [title, message]

            # Add app icon if available (optional)
            try:
                # Look for icon in assets/images directory
                icon_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "..",
                    "assets",
                    "images",
                    "icon.png",
                )
                if os.path.exists(icon_path):
                    toast.AddImage(ToastDisplayImage.fromPath(icon_path))
            except Exception as e:
                self._get_logger.debug("[TOAST] Could not load icon: %s", e)

            # Show toast
            toaster.show_toast(toast)
            return True

        except Exception as e:
            self._get_logger.error("[TOAST] Failed to show toast notification: %s", e)
            return False

    def show_discovery_toast(self, count: int) -> bool:
        """
        Show Windows toast notification for discovery results.

        Args:
            count: Number of new files discovered

        Returns:
            True if toast was shown successfully, False otherwise
        """
        title = "WinScanLLM Discovery"
        if count == 0:
            message = "No new images found"
        elif count == 1:
            message = "1 new image discovered"
        else:
            message = f"{count} new images discovered"

        shown = self._show(title, message)
        if shown:
            self._get_logger.info("[TOAST] Showed discovery toast: %s new files", count)
        return shown

    def show_preflight_toast(self, message: str) -> bool:
        """
        Show Windows toast notification for an LLM readiness preflight result.

        Args:
            message: Human-readable readiness summary (e.g. "model missing").

        Returns:
            True if toast was shown successfully, False otherwise
        """
        shown = self._show("WinScanLLM — LLM not ready", message)
        if shown:
            self._get_logger.info("[TOAST] Showed preflight toast: %s", message)
        return shown


# Example usage
if __name__ == "__main__":
    import logging
    import time

    from services.logging_service import LoggingService

    LoggingService().initialize(log_level=logging.DEBUG, console_output=True)

    notifier = NotificationService()

    # Test with different counts
    print("Showing toast with 0 files...")
    notifier.show_discovery_toast(0)

    time.sleep(2)

    print("Showing toast with 1 file...")
    notifier.show_discovery_toast(1)

    time.sleep(2)

    print("Showing toast with 5 files...")
    notifier.show_discovery_toast(5)

    print("Done!")
