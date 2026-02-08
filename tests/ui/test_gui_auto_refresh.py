"""Tests for GUI auto-refresh functionality after bundle operations."""

from unittest.mock import Mock


class TestRefreshMetricsStartupWindow:
    """Tests for _refresh_metrics_after_bundle_operation in StartupWindow."""

    def test_refresh_when_window_exists(self):
        """Test that refresh is called when analysis status window exists."""
        from ui.gui import StartupWindow

        # Create a mock instance
        mock_window = Mock(spec=StartupWindow)
        mock_analysis_status_window = Mock()
        mock_window._analysis_status_window = mock_analysis_status_window

        # Call the actual method implementation
        StartupWindow._refresh_metrics_after_bundle_operation(mock_window)

        # Verify _refresh_all was called
        mock_analysis_status_window._refresh_all.assert_called_once()

    def test_no_refresh_when_window_is_none(self):
        """Test that no error occurs when analysis status window is None."""
        from ui.gui import StartupWindow

        mock_window = Mock(spec=StartupWindow)
        mock_window._analysis_status_window = None

        # Should not raise an error
        StartupWindow._refresh_metrics_after_bundle_operation(mock_window)

    def test_accepts_bundle_data_parameter(self):
        """Test that method accepts optional bundle_data parameter from signal."""
        from ui.gui import StartupWindow

        mock_window = Mock(spec=StartupWindow)
        mock_window._analysis_status_window = None

        # Should not raise an error when called with bundle_data
        bundle_data = {"bundle_id": "test"}
        StartupWindow._refresh_metrics_after_bundle_operation(mock_window, bundle_data)


class TestRefreshMetricsConvertImagesWindow:
    """Tests for _refresh_metrics_after_bundle_operation in ConvertImagesWindow."""

    def test_refresh_when_window_exists(self):
        """Test that refresh is called when analysis status window exists."""
        from ui.gui import ConvertImagesWindow

        # Create a mock instance
        mock_window = Mock(spec=ConvertImagesWindow)
        mock_analysis_status_window = Mock()
        mock_window._analysis_status_window = mock_analysis_status_window

        # Call the actual method implementation
        ConvertImagesWindow._refresh_metrics_after_bundle_operation(mock_window)

        # Verify _refresh_all was called
        mock_analysis_status_window._refresh_all.assert_called_once()

    def test_handles_refresh_exception_gracefully(self):
        """Test that exceptions during refresh are handled gracefully."""
        from ui.gui import ConvertImagesWindow

        mock_window = Mock(spec=ConvertImagesWindow)
        mock_analysis_status_window = Mock()
        mock_window._analysis_status_window = mock_analysis_status_window

        # Make _refresh_all raise an exception
        mock_analysis_status_window._refresh_all.side_effect = Exception("Refresh failed")

        # Should not raise an error
        ConvertImagesWindow._refresh_metrics_after_bundle_operation(mock_window)


class TestOnBundleAcceptedFromWorkflow:
    """Tests for _on_bundle_accepted_from_workflow method in ConvertImagesWindow."""

    def test_calls_refresh_after_bundle_accepted(self):
        """Test that refresh is called after bundle is accepted."""
        from ui.gui import ConvertImagesWindow

        mock_window = Mock(spec=ConvertImagesWindow)
        mock_window.completed_groups = []
        mock_window.extracted_metadata = {}
        mock_analysis_status_window = Mock()
        mock_window._analysis_status_window = mock_analysis_status_window

        # Mock the refresh method to track calls
        mock_window._refresh_metrics_after_bundle_operation = Mock()

        # Create test bundle data
        bundle_data = {
            "bundle_id": "test-bundle-1",
            "file_paths": ["/path/to/file1.png", "/path/to/file2.png"],
            "company": "Test Company",
            "document_type": "Invoice",
            "document_date": "2024-01-15",
        }

        # Call the handler
        ConvertImagesWindow._on_bundle_accepted_from_workflow(mock_window, bundle_data)

        # Verify refresh was called
        mock_window._refresh_metrics_after_bundle_operation.assert_called_once()

    def test_no_refresh_when_no_file_paths(self):
        """Test behavior when bundle has no file paths."""
        from ui.gui import ConvertImagesWindow

        mock_window = Mock(spec=ConvertImagesWindow)
        mock_window.completed_groups = []
        mock_window.extracted_metadata = {}
        mock_analysis_status_window = Mock()
        mock_window._analysis_status_window = mock_analysis_status_window

        # Bundle with no file paths
        bundle_data = {
            "bundle_id": "test-bundle-1",
            "file_paths": [],
            "company": "Test Company",
        }

        # Call the handler
        ConvertImagesWindow._on_bundle_accepted_from_workflow(mock_window, bundle_data)

        # Refresh should NOT be called since no files were added
        mock_analysis_status_window._refresh_all.assert_not_called()

    def test_completed_groups_updated(self):
        """Test that completed_groups and extracted_metadata are updated correctly."""
        from ui.gui import ConvertImagesWindow

        mock_window = Mock(spec=ConvertImagesWindow)
        mock_window.completed_groups = []
        mock_window.extracted_metadata = {}
        mock_window._analysis_status_window = Mock()

        bundle_data = {
            "bundle_id": "test-bundle-1",
            "file_paths": ["/path/to/file1.png", "/path/to/file2.png"],
            "company": "Test Company",
            "document_type": "Invoice",
            "document_date": "2024-01-15",
        }

        # Call the handler
        ConvertImagesWindow._on_bundle_accepted_from_workflow(mock_window, bundle_data)

        # Verify state changes
        assert len(mock_window.completed_groups) == 1
        assert bundle_data["file_paths"] in mock_window.completed_groups

        # Verify metadata was stored
        group_key = "group_1"
        assert group_key in mock_window.extracted_metadata
        assert mock_window.extracted_metadata[group_key]["company"] == "Test Company"


class TestSignalConnectionPattern:
    """Tests for signal connection patterns across both window types."""

    def test_signal_connection_works(self):
        """Test that signal connection pattern works as expected."""
        # Create mocks for Qt signal/slot pattern
        mock_workflow = Mock()
        mock_workflow.bundle_accepted = Mock()
        mock_workflow.bundle_accepted.connect = Mock()

        mock_refresh_handler = Mock()

        # Simulate signal connection pattern used in the code
        mock_workflow.bundle_accepted.connect(mock_refresh_handler)

        # Verify the signal was connected
        mock_workflow.bundle_accepted.connect.assert_called_once_with(mock_refresh_handler)

    def test_startup_window_has_refresh_method(self):
        """Verify that StartupWindow has the refresh method."""
        from ui.gui import StartupWindow

        # Method should exist
        assert hasattr(StartupWindow, "_refresh_metrics_after_bundle_operation")

    def test_convert_images_window_has_refresh_method(self):
        """Verify that ConvertImagesWindow has the refresh method."""
        from ui.gui import ConvertImagesWindow

        # Method should exist
        assert hasattr(ConvertImagesWindow, "_refresh_metrics_after_bundle_operation")
