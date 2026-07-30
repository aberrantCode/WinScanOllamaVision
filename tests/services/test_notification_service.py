"""
Tests for NotificationService
"""

import logging
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def initialize_logging():
    """Initialize logging service for notification service tests."""
    from services.logging_service import LoggingService

    LoggingService().initialize(log_level=logging.WARNING, console_output=False)
    yield


@patch("services.notification_service.sys.platform", "win32")
@patch("services.notification_service.WINDOWS_TOASTS_AVAILABLE", True)
def test_notification_service_initialization_success():
    """Test NotificationService initializes when windows-toasts is available"""
    from services.notification_service import NotificationService

    notifier = NotificationService()

    assert notifier._toasts_available is True


@patch("services.notification_service.sys.platform", "linux")
def test_notification_service_initialization_non_windows():
    """Test NotificationService disables toasts on non-Windows platforms"""
    from services.notification_service import NotificationService

    notifier = NotificationService()

    assert notifier._toasts_available is False


@patch("services.notification_service.sys.platform", "win32")
@patch("services.notification_service.WINDOWS_TOASTS_AVAILABLE", False)
def test_notification_service_initialization_import_error():
    """Test NotificationService handles missing windows-toasts gracefully"""
    from services.notification_service import NotificationService

    notifier = NotificationService()

    # Should disable toasts when import fails
    assert notifier._toasts_available is False


@patch("services.notification_service.sys.platform", "win32")
@patch("services.notification_service.WINDOWS_TOASTS_AVAILABLE", True)
@patch("services.notification_service.InteractableWindowsToaster")
@patch("services.notification_service.Toast")
def test_show_discovery_toast_zero_files(mock_toast_class, mock_toaster_class):
    """Test showing toast with zero new files"""
    from services.notification_service import NotificationService

    # Setup mocks
    mock_toaster = MagicMock()
    mock_toast = MagicMock()
    mock_toaster_class.return_value = mock_toaster
    mock_toast_class.return_value = mock_toast

    notifier = NotificationService()
    result = notifier.show_discovery_toast(0)

    assert result is True

    # Verify toast was created and shown
    mock_toaster_class.assert_called_once_with("WinScanLLM")
    mock_toast_class.assert_called_once()
    mock_toaster.show_toast.assert_called_once()

    # Verify message for zero files
    assert mock_toast.text_fields == ["WinScanLLM Discovery", "No new images found"]


@patch("services.notification_service.sys.platform", "win32")
@patch("services.notification_service.WINDOWS_TOASTS_AVAILABLE", True)
@patch("services.notification_service.InteractableWindowsToaster")
@patch("services.notification_service.Toast")
def test_show_discovery_toast_one_file(mock_toast_class, mock_toaster_class):
    """Test showing toast with one new file"""
    from services.notification_service import NotificationService

    # Setup mocks
    mock_toaster = MagicMock()
    mock_toast = MagicMock()
    mock_toaster_class.return_value = mock_toaster
    mock_toast_class.return_value = mock_toast

    notifier = NotificationService()
    result = notifier.show_discovery_toast(1)

    assert result is True

    # Verify message for one file (singular)
    assert mock_toast.text_fields == ["WinScanLLM Discovery", "1 new image discovered"]


@patch("services.notification_service.sys.platform", "win32")
@patch("services.notification_service.WINDOWS_TOASTS_AVAILABLE", True)
@patch("services.notification_service.InteractableWindowsToaster")
@patch("services.notification_service.Toast")
def test_show_discovery_toast_multiple_files(mock_toast_class, mock_toaster_class):
    """Test showing toast with multiple new files"""
    from services.notification_service import NotificationService

    # Setup mocks
    mock_toaster = MagicMock()
    mock_toast = MagicMock()
    mock_toaster_class.return_value = mock_toaster
    mock_toast_class.return_value = mock_toast

    notifier = NotificationService()
    result = notifier.show_discovery_toast(5)

    assert result is True

    # Verify message for multiple files (plural)
    assert mock_toast.text_fields == ["WinScanLLM Discovery", "5 new images discovered"]


@patch("services.notification_service.sys.platform", "win32")
@patch("services.notification_service.WINDOWS_TOASTS_AVAILABLE", True)
@patch("services.notification_service.InteractableWindowsToaster")
@patch("services.notification_service.Toast")
def test_show_preflight_toast(mock_toast_class, mock_toaster_class):
    """Test showing a preflight readiness toast."""
    from services.notification_service import NotificationService

    mock_toaster = MagicMock()
    mock_toast = MagicMock()
    mock_toaster_class.return_value = mock_toaster
    mock_toast_class.return_value = mock_toast

    notifier = NotificationService()
    result = notifier.show_preflight_toast("Model 'qwen2.5-vl' is not installed on ollama.")

    assert result is True
    mock_toaster.show_toast.assert_called_once()
    assert mock_toast.text_fields == [
        "WinScanLLM — LLM not ready",
        "Model 'qwen2.5-vl' is not installed on ollama.",
    ]


@patch("services.notification_service.sys.platform", "linux")
def test_show_preflight_toast_unavailable():
    """Preflight toast returns False when toasts are unavailable."""
    from services.notification_service import NotificationService

    notifier = NotificationService()
    assert notifier.show_preflight_toast("anything") is False


@patch("services.notification_service.sys.platform", "linux")
def test_show_discovery_toast_unavailable():
    """Test showing toast when toasts are unavailable returns False"""
    from services.notification_service import NotificationService

    notifier = NotificationService()
    result = notifier.show_discovery_toast(5)

    assert result is False


@patch("services.notification_service.sys.platform", "win32")
@patch("services.notification_service.WINDOWS_TOASTS_AVAILABLE", True)
@patch("services.notification_service.InteractableWindowsToaster")
def test_show_discovery_toast_handles_exceptions(mock_toaster_class):
    """Test showing toast handles exceptions gracefully"""
    from services.notification_service import NotificationService

    # Setup mocks to raise exception
    mock_toaster_class.side_effect = Exception("Toast error")

    notifier = NotificationService()
    result = notifier.show_discovery_toast(5)

    # Should return False on error
    assert result is False


@patch("services.notification_service.sys.platform", "win32")
@patch("services.notification_service.WINDOWS_TOASTS_AVAILABLE", True)
@patch("services.notification_service.InteractableWindowsToaster")
@patch("services.notification_service.Toast")
@patch("services.notification_service.ToastDisplayImage")
@patch("services.notification_service.os.path.exists")
def test_show_discovery_toast_with_icon(
    mock_exists, mock_image_class, mock_toast_class, mock_toaster_class
):
    """Test showing toast with app icon"""
    from services.notification_service import NotificationService

    # Setup mocks
    mock_toaster = MagicMock()
    mock_toast = MagicMock()
    mock_image = MagicMock()
    mock_toaster_class.return_value = mock_toaster
    mock_toast_class.return_value = mock_toast
    mock_image_class.fromPath.return_value = mock_image

    # Simulate icon file exists
    mock_exists.return_value = True

    notifier = NotificationService()
    result = notifier.show_discovery_toast(3)

    assert result is True

    # Verify icon was added
    mock_toast.AddImage.assert_called_once_with(mock_image)


@patch("services.notification_service.sys.platform", "win32")
@patch("services.notification_service.WINDOWS_TOASTS_AVAILABLE", True)
@patch("services.notification_service.InteractableWindowsToaster")
@patch("services.notification_service.Toast")
@patch("services.notification_service.os.path.exists")
def test_show_discovery_toast_without_icon(mock_exists, mock_toast_class, mock_toaster_class):
    """Test showing toast when icon file doesn't exist"""
    from services.notification_service import NotificationService

    # Setup mocks
    mock_toaster = MagicMock()
    mock_toast = MagicMock()
    mock_toaster_class.return_value = mock_toaster
    mock_toast_class.return_value = mock_toast

    # Simulate icon file doesn't exist
    mock_exists.return_value = False

    notifier = NotificationService()
    result = notifier.show_discovery_toast(3)

    assert result is True

    # Verify icon was NOT added
    mock_toast.AddImage.assert_not_called()
