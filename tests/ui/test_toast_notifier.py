"""
Tests for ToastNotifier
"""

from unittest.mock import MagicMock, patch


@patch("ui.toast_notifier.sys.platform", "win32")
@patch("ui.toast_notifier.WINDOWS_TOASTS_AVAILABLE", True)
def test_toast_notifier_initialization_success():
    """Test ToastNotifier initializes when windows-toasts is available"""
    from ui.toast_notifier import ToastNotifier

    notifier = ToastNotifier()

    assert notifier._toasts_available is True


@patch("ui.toast_notifier.sys.platform", "linux")
def test_toast_notifier_initialization_non_windows():
    """Test ToastNotifier disables toasts on non-Windows platforms"""
    from ui.toast_notifier import ToastNotifier

    notifier = ToastNotifier()

    assert notifier._toasts_available is False


@patch("ui.toast_notifier.sys.platform", "win32")
@patch("ui.toast_notifier.WINDOWS_TOASTS_AVAILABLE", False)
def test_toast_notifier_initialization_import_error():
    """Test ToastNotifier handles missing windows-toasts gracefully"""
    from ui.toast_notifier import ToastNotifier

    notifier = ToastNotifier()

    # Should disable toasts when import fails
    assert notifier._toasts_available is False


@patch("ui.toast_notifier.sys.platform", "win32")
@patch("ui.toast_notifier.WINDOWS_TOASTS_AVAILABLE", True)
@patch("ui.toast_notifier.InteractableWindowsToaster")
@patch("ui.toast_notifier.Toast")
def test_show_discovery_toast_zero_files(mock_toast_class, mock_toaster_class):
    """Test showing toast with zero new files"""
    from ui.toast_notifier import ToastNotifier

    # Setup mocks
    mock_toaster = MagicMock()
    mock_toast = MagicMock()
    mock_toaster_class.return_value = mock_toaster
    mock_toast_class.return_value = mock_toast

    notifier = ToastNotifier()
    result = notifier.show_discovery_toast(0)

    assert result is True

    # Verify toast was created and shown
    mock_toaster_class.assert_called_once_with("WinScanLLM")
    mock_toast_class.assert_called_once()
    mock_toaster.show_toast.assert_called_once()

    # Verify message for zero files
    assert mock_toast.text_fields == ["WinScanLLM Discovery", "No new images found"]


@patch("ui.toast_notifier.sys.platform", "win32")
@patch("ui.toast_notifier.WINDOWS_TOASTS_AVAILABLE", True)
@patch("ui.toast_notifier.InteractableWindowsToaster")
@patch("ui.toast_notifier.Toast")
def test_show_discovery_toast_one_file(mock_toast_class, mock_toaster_class):
    """Test showing toast with one new file"""
    from ui.toast_notifier import ToastNotifier

    # Setup mocks
    mock_toaster = MagicMock()
    mock_toast = MagicMock()
    mock_toaster_class.return_value = mock_toaster
    mock_toast_class.return_value = mock_toast

    notifier = ToastNotifier()
    result = notifier.show_discovery_toast(1)

    assert result is True

    # Verify message for one file (singular)
    assert mock_toast.text_fields == ["WinScanLLM Discovery", "1 new image discovered"]


@patch("ui.toast_notifier.sys.platform", "win32")
@patch("ui.toast_notifier.WINDOWS_TOASTS_AVAILABLE", True)
@patch("ui.toast_notifier.InteractableWindowsToaster")
@patch("ui.toast_notifier.Toast")
def test_show_discovery_toast_multiple_files(mock_toast_class, mock_toaster_class):
    """Test showing toast with multiple new files"""
    from ui.toast_notifier import ToastNotifier

    # Setup mocks
    mock_toaster = MagicMock()
    mock_toast = MagicMock()
    mock_toaster_class.return_value = mock_toaster
    mock_toast_class.return_value = mock_toast

    notifier = ToastNotifier()
    result = notifier.show_discovery_toast(5)

    assert result is True

    # Verify message for multiple files (plural)
    assert mock_toast.text_fields == ["WinScanLLM Discovery", "5 new images discovered"]


@patch("ui.toast_notifier.sys.platform", "linux")
def test_show_discovery_toast_unavailable():
    """Test showing toast when toasts are unavailable returns False"""
    from ui.toast_notifier import ToastNotifier

    notifier = ToastNotifier()
    result = notifier.show_discovery_toast(5)

    assert result is False


@patch("ui.toast_notifier.sys.platform", "win32")
@patch("ui.toast_notifier.WINDOWS_TOASTS_AVAILABLE", True)
@patch("ui.toast_notifier.InteractableWindowsToaster")
def test_show_discovery_toast_handles_exceptions(mock_toaster_class):
    """Test showing toast handles exceptions gracefully"""
    from ui.toast_notifier import ToastNotifier

    # Setup mocks to raise exception
    mock_toaster_class.side_effect = Exception("Toast error")

    notifier = ToastNotifier()
    result = notifier.show_discovery_toast(5)

    # Should return False on error
    assert result is False


@patch("ui.toast_notifier.sys.platform", "win32")
@patch("ui.toast_notifier.WINDOWS_TOASTS_AVAILABLE", True)
@patch("ui.toast_notifier.InteractableWindowsToaster")
@patch("ui.toast_notifier.Toast")
@patch("ui.toast_notifier.ToastDisplayImage")
@patch("ui.toast_notifier.os.path.exists")
def test_show_discovery_toast_with_icon(
    mock_exists, mock_image_class, mock_toast_class, mock_toaster_class
):
    """Test showing toast with app icon"""
    from ui.toast_notifier import ToastNotifier

    # Setup mocks
    mock_toaster = MagicMock()
    mock_toast = MagicMock()
    mock_image = MagicMock()
    mock_toaster_class.return_value = mock_toaster
    mock_toast_class.return_value = mock_toast
    mock_image_class.fromPath.return_value = mock_image

    # Simulate icon file exists
    mock_exists.return_value = True

    notifier = ToastNotifier()
    result = notifier.show_discovery_toast(3)

    assert result is True

    # Verify icon was added
    mock_toast.AddImage.assert_called_once_with(mock_image)


@patch("ui.toast_notifier.sys.platform", "win32")
@patch("ui.toast_notifier.WINDOWS_TOASTS_AVAILABLE", True)
@patch("ui.toast_notifier.InteractableWindowsToaster")
@patch("ui.toast_notifier.Toast")
@patch("ui.toast_notifier.os.path.exists")
def test_show_discovery_toast_without_icon(mock_exists, mock_toast_class, mock_toaster_class):
    """Test showing toast when icon file doesn't exist"""
    from ui.toast_notifier import ToastNotifier

    # Setup mocks
    mock_toaster = MagicMock()
    mock_toast = MagicMock()
    mock_toaster_class.return_value = mock_toaster
    mock_toast_class.return_value = mock_toast

    # Simulate icon file doesn't exist
    mock_exists.return_value = False

    notifier = ToastNotifier()
    result = notifier.show_discovery_toast(3)

    assert result is True

    # Verify icon was NOT added
    mock_toast.AddImage.assert_not_called()
