"""
Comprehensive tests for BundleReviewWindow.

Tests the guided workflow for bundle review, metadata editing, and PDF generation,
with focus on the mark_bundle_completed() integration.
"""

from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QMessageBox

from ui.verify_documents_window import BundleReviewWindow


@pytest.fixture(autouse=True)
def mock_logging_service():
    """Mock the logging service to prevent initialization errors."""
    with patch("services.logging_service.get_logger") as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        yield mock_logger


class TestBundleReviewWindowPdfCompletion:
    """Tests for PDF generation and bundle completion workflow"""

    @pytest.fixture
    def mock_bundling_service(self):
        """Mock BundlingService for testing."""
        service = MagicMock()
        service.convert_bundle_to_pdf.return_value = "C:\\test\\output\\invoice_2024-01-15.pdf"
        service.update_bundle_metadata.return_value = None
        service.mark_bundle_completed.return_value = None
        return service

    @pytest.fixture
    def mock_config_manager(self):
        """Mock ConfigManager for testing."""
        config = MagicMock()
        config.get_setting.side_effect = lambda section, key, default=None: {
            ("OutputDirectory", "path"): "C:\\test\\output",
            ("OutputDirectory", "strategy"): "single_directory",
        }.get((section, key), default)
        return config

    @pytest.fixture
    def mock_analysis_db(self):
        """Mock AnalysisDB for testing."""
        db = MagicMock()
        db.get_analysis.return_value = {
            "file_path": "C:\\test\\page1.png",
            "company": "TestCo",
            "document_type": "invoice",
            "document_date": "2024-01-15",
        }
        return db

    @pytest.fixture
    def sample_bundle(self):
        """Sample bundle for testing."""
        return {
            "id": 123,
            "company": "TestCo",
            "document_type": "invoice",
            "document_date": "2024-01-15",
            "total_pages": 2,
            "file_paths": [
                "C:\\test\\page1.png",
                "C:\\test\\page2.png",
            ],
            "confidence_score": 0.92,
        }

    @pytest.fixture
    def sample_metadata(self):
        """Sample metadata for testing."""
        return {
            "output_filename": "invoice_2024-01-15.pdf",
            "company": "TestCo",
            "document_type": "invoice",
            "document_date": "2024-01-15",
        }

    @pytest.fixture
    def workflow(self, qapp, mock_config_manager, mock_analysis_db, sample_bundle):
        """Create BundleReviewWindow instance for testing."""
        bundles = [sample_bundle]
        workflow = BundleReviewWindow(
            bundles=bundles,
            analysis_db=mock_analysis_db,
            config_manager=mock_config_manager,
        )
        # Set initial state
        workflow.current_bundle_index = 0
        workflow.page_order = [0, 1]
        workflow.rotation_angle = 0
        workflow.prototype_mode = False  # Ensure real conversion mode
        return workflow

    @patch("ui.guided_bundle_workflow.Path")
    @patch("ui.guided_bundle_workflow.QMessageBox")
    @patch("services.bundling_service.BundlingService")
    def test_complete_pdf_conversion_calls_mark_bundle_completed(
        self,
        mock_bundling_service_class,
        mock_qmessagebox,
        mock_path,
        workflow,
        mock_bundling_service,
        sample_bundle,
        sample_metadata,
    ):
        """Test that _complete_pdf_conversion calls mark_bundle_completed."""
        # Arrange
        mock_bundling_service_class.return_value = mock_bundling_service

        # Mock Path for output directory
        mock_path_instance = MagicMock()
        mock_path_instance.parent.mkdir = MagicMock()
        mock_path.return_value = mock_path_instance

        # Mock the message box to return Ok immediately
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QMessageBox.StandardButton.Ok
        mock_dialog.close = MagicMock()
        mock_qmessagebox.return_value = mock_dialog

        # Mock progress dialog
        progress_dialog = MagicMock()

        # Act
        workflow._complete_pdf_conversion(progress_dialog, sample_bundle, sample_metadata)

        # Assert
        pdf_path = "C:\\test\\output\\invoice_2024-01-15.pdf"
        bundle_id = sample_bundle["id"]

        # Verify mark_bundle_completed was called with correct arguments
        mock_bundling_service.mark_bundle_completed.assert_called_once_with(bundle_id, pdf_path)

    @patch("ui.guided_bundle_workflow.Path")
    @patch("ui.guided_bundle_workflow.QMessageBox")
    @patch("services.bundling_service.BundlingService")
    def test_complete_pdf_conversion_updates_metadata_before_completion(
        self,
        mock_bundling_service_class,
        mock_qmessagebox,
        mock_path,
        workflow,
        mock_bundling_service,
        sample_bundle,
        sample_metadata,
    ):
        """Test that metadata is updated before marking bundle complete."""
        # Arrange
        mock_bundling_service_class.return_value = mock_bundling_service

        # Mock Path
        mock_path_instance = MagicMock()
        mock_path_instance.parent.mkdir = MagicMock()
        mock_path.return_value = mock_path_instance

        # Mock the message box to return Ok immediately
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QMessageBox.StandardButton.Ok
        mock_dialog.close = MagicMock()
        mock_qmessagebox.return_value = mock_dialog

        # Mock progress dialog
        progress_dialog = MagicMock()

        # Track call order
        call_order = []

        def track_update_metadata(*args, **kwargs):
            call_order.append("update_metadata")

        def track_mark_completed(*args, **kwargs):
            call_order.append("mark_completed")

        mock_bundling_service.update_bundle_metadata.side_effect = track_update_metadata
        mock_bundling_service.mark_bundle_completed.side_effect = track_mark_completed

        # Act
        workflow._complete_pdf_conversion(progress_dialog, sample_bundle, sample_metadata)

        # Assert - verify order
        assert call_order == ["update_metadata", "mark_completed"]

        # Verify both were called
        mock_bundling_service.update_bundle_metadata.assert_called_once_with(
            sample_bundle["id"], sample_metadata
        )
        mock_bundling_service.mark_bundle_completed.assert_called_once()

    @patch("ui.guided_bundle_workflow.Path")
    @patch("ui.guided_bundle_workflow.QMessageBox")
    @patch("services.bundling_service.BundlingService")
    def test_complete_pdf_conversion_saves_correct_pdf_path(
        self,
        mock_bundling_service_class,
        mock_qmessagebox,
        mock_path,
        workflow,
        mock_bundling_service,
        sample_bundle,
        sample_metadata,
    ):
        """Test that the correct PDF path is saved to database."""
        # Arrange
        expected_pdf_path = "C:\\test\\output\\invoice_2024-01-15.pdf"
        mock_bundling_service.convert_bundle_to_pdf.return_value = expected_pdf_path
        mock_bundling_service_class.return_value = mock_bundling_service

        # Mock Path
        mock_path_instance = MagicMock()
        mock_path_instance.parent.mkdir = MagicMock()
        mock_path.return_value = mock_path_instance

        # Mock the message box to return Ok immediately
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QMessageBox.StandardButton.Ok
        mock_dialog.close = MagicMock()
        mock_qmessagebox.return_value = mock_dialog

        # Mock progress dialog
        progress_dialog = MagicMock()

        # Act
        workflow._complete_pdf_conversion(progress_dialog, sample_bundle, sample_metadata)

        # Assert
        _, actual_pdf_path = mock_bundling_service.mark_bundle_completed.call_args[0]
        assert actual_pdf_path == expected_pdf_path

    @patch("ui.guided_bundle_workflow.Path")
    @patch("ui.guided_bundle_workflow.QMessageBox")
    @patch("services.bundling_service.BundlingService")
    def test_complete_pdf_conversion_handles_missing_bundle_id(
        self,
        mock_bundling_service_class,
        mock_qmessagebox,
        mock_path,
        workflow,
        mock_bundling_service,
        sample_metadata,
    ):
        """Test that missing bundle_id doesn't crash the workflow."""
        # Arrange
        bundle_without_id = {
            "company": "TestCo",
            "document_type": "invoice",
            "file_paths": ["C:\\test\\page1.png"],
        }
        mock_bundling_service_class.return_value = mock_bundling_service

        # Mock Path
        mock_path_instance = MagicMock()
        mock_path_instance.parent.mkdir = MagicMock()
        mock_path.return_value = mock_path_instance

        # Mock the message box to return Ok immediately
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QMessageBox.StandardButton.Ok
        mock_dialog.close = MagicMock()
        mock_qmessagebox.return_value = mock_dialog

        # Mock progress dialog
        progress_dialog = MagicMock()

        # Act
        workflow._complete_pdf_conversion(progress_dialog, bundle_without_id, sample_metadata)

        # Assert - should not call database methods when bundle_id is missing
        mock_bundling_service.update_bundle_metadata.assert_not_called()
        mock_bundling_service.mark_bundle_completed.assert_not_called()

    @patch("ui.guided_bundle_workflow.Path")
    @patch("ui.guided_bundle_workflow.QMessageBox")
    @patch("services.bundling_service.BundlingService")
    def test_complete_pdf_conversion_applies_page_reordering(
        self,
        mock_bundling_service_class,
        mock_qmessagebox,
        mock_path,
        workflow,
        mock_bundling_service,
        sample_bundle,
        sample_metadata,
    ):
        """Test that page_order is correctly applied to file paths."""
        # Arrange
        workflow.page_order = [1, 0]  # Reverse order
        mock_bundling_service_class.return_value = mock_bundling_service

        # Mock Path
        mock_path_instance = MagicMock()
        mock_path_instance.parent.mkdir = MagicMock()
        mock_path.return_value = mock_path_instance

        # Mock the message box to return Ok immediately
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QMessageBox.StandardButton.Ok
        mock_dialog.close = MagicMock()
        mock_qmessagebox.return_value = mock_dialog

        # Mock progress dialog
        progress_dialog = MagicMock()

        # Act
        workflow._complete_pdf_conversion(progress_dialog, sample_bundle, sample_metadata)

        # Assert - verify convert_bundle_to_pdf received reordered paths
        call_kwargs = mock_bundling_service.convert_bundle_to_pdf.call_args[1]
        expected_order = [
            "C:\\test\\page2.png",  # index 1
            "C:\\test\\page1.png",  # index 0
        ]
        assert call_kwargs["file_paths"] == expected_order

    @patch("ui.guided_bundle_workflow.Path")
    @patch("ui.guided_bundle_workflow.QMessageBox")
    @patch("services.bundling_service.BundlingService")
    def test_complete_pdf_conversion_applies_rotation_angle(
        self,
        mock_bundling_service_class,
        mock_qmessagebox,
        mock_path,
        workflow,
        mock_bundling_service,
        sample_bundle,
        sample_metadata,
    ):
        """Test that rotation_angle is passed to PDF conversion."""
        # Arrange
        workflow.rotation_angle = 90
        mock_bundling_service_class.return_value = mock_bundling_service

        # Mock Path
        mock_path_instance = MagicMock()
        mock_path_instance.parent.mkdir = MagicMock()
        mock_path.return_value = mock_path_instance

        # Mock the message box to return Ok immediately
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QMessageBox.StandardButton.Ok
        mock_dialog.close = MagicMock()
        mock_qmessagebox.return_value = mock_dialog

        # Mock progress dialog
        progress_dialog = MagicMock()

        # Act
        workflow._complete_pdf_conversion(progress_dialog, sample_bundle, sample_metadata)

        # Assert - verify rotation_angle was passed
        call_kwargs = mock_bundling_service.convert_bundle_to_pdf.call_args[1]
        assert call_kwargs["rotation_angle"] == 90

    @patch("ui.guided_bundle_workflow.Path")
    @patch("ui.guided_bundle_workflow.QMessageBox")
    @patch("services.bundling_service.BundlingService")
    def test_complete_pdf_conversion_emits_bundle_accepted_signal(
        self,
        mock_bundling_service_class,
        mock_qmessagebox,
        mock_path,
        workflow,
        mock_bundling_service,
        sample_bundle,
        sample_metadata,
    ):
        """Test that bundle_accepted signal is emitted after PDF creation."""
        # Arrange
        mock_bundling_service_class.return_value = mock_bundling_service
        pdf_path = "C:\\test\\output\\invoice_2024-01-15.pdf"
        mock_bundling_service.convert_bundle_to_pdf.return_value = pdf_path

        # Mock Path
        mock_path_instance = MagicMock()
        mock_path_instance.parent.mkdir = MagicMock()
        mock_path.return_value = mock_path_instance

        # Mock the message box to return Ok immediately
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QMessageBox.StandardButton.Ok
        mock_dialog.close = MagicMock()
        mock_qmessagebox.return_value = mock_dialog

        # Mock progress dialog
        progress_dialog = MagicMock()

        # Track signal emissions
        emitted_bundles = []

        def capture_emission(bundle):
            emitted_bundles.append(bundle)

        workflow.bundle_accepted.connect(capture_emission)

        # Act
        workflow._complete_pdf_conversion(progress_dialog, sample_bundle, sample_metadata)

        # Assert
        assert len(emitted_bundles) == 1
        emitted_bundle = emitted_bundles[0]
        assert emitted_bundle["pdf_path"] == pdf_path
        assert emitted_bundle["company"] == "TestCo"

    @patch("ui.guided_bundle_workflow.Path")
    @patch("ui.guided_bundle_workflow.QMessageBox")
    @patch("services.bundling_service.BundlingService")
    def test_complete_pdf_conversion_adds_to_accepted_bundles(
        self,
        mock_bundling_service_class,
        mock_qmessagebox,
        mock_path,
        workflow,
        mock_bundling_service,
        sample_bundle,
        sample_metadata,
    ):
        """Test that completed bundle is added to accepted_bundles list."""
        # Arrange
        mock_bundling_service_class.return_value = mock_bundling_service
        pdf_path = "C:\\test\\output\\invoice_2024-01-15.pdf"
        mock_bundling_service.convert_bundle_to_pdf.return_value = pdf_path

        # Mock Path
        mock_path_instance = MagicMock()
        mock_path_instance.parent.mkdir = MagicMock()
        mock_path.return_value = mock_path_instance

        # Mock the message box to return Ok immediately
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QMessageBox.StandardButton.Ok
        mock_dialog.close = MagicMock()
        mock_qmessagebox.return_value = mock_dialog

        # Mock progress dialog
        progress_dialog = MagicMock()

        # Verify initial state
        assert len(workflow.accepted_bundles) == 0

        # Act
        workflow._complete_pdf_conversion(progress_dialog, sample_bundle, sample_metadata)

        # Assert
        assert len(workflow.accepted_bundles) == 1
        accepted = workflow.accepted_bundles[0]
        assert accepted["pdf_path"] == pdf_path
        assert accepted["company"] == "TestCo"
        assert accepted["page_order"] == [0, 1]


class TestBundleReviewWindowIntegration:
    """Integration tests for the complete workflow"""

    @pytest.fixture
    def workflow_with_multiple_bundles(self, qapp, mock_config_manager, mock_analysis_db):
        """Create workflow with multiple bundles for testing."""
        bundles = [
            {
                "id": 1,
                "company": "CompanyA",
                "document_type": "invoice",
                "file_paths": ["C:\\test\\page1.png"],
            },
            {
                "id": 2,
                "company": "CompanyB",
                "document_type": "invoice",
                "file_paths": ["C:\\test\\page2.png"],
            },
        ]
        wf = BundleReviewWindow(
            bundles=bundles,
            analysis_db=mock_analysis_db,
            config_manager=mock_config_manager,
        )
        wf.prototype_mode = False
        return wf

    @pytest.fixture
    def mock_config_manager(self):
        """Mock ConfigManager for integration tests."""
        config = MagicMock()
        config.get_setting.side_effect = lambda section, key, default=None: {
            ("OutputDirectory", "path"): "C:\\test\\output",
            ("OutputDirectory", "strategy"): "single_directory",
        }.get((section, key), default)
        return config

    @pytest.fixture
    def mock_analysis_db(self):
        """Mock AnalysisDB for integration tests."""
        db = MagicMock()
        db.get_analysis.return_value = {
            "file_path": "C:\\test\\page1.png",
            "company": "TestCo",
            "document_type": "invoice",
        }
        return db

    @patch("ui.guided_bundle_workflow.Path")
    @patch("ui.guided_bundle_workflow.QMessageBox")
    @patch("services.bundling_service.BundlingService")
    def test_full_workflow_marks_all_bundles_completed(
        self,
        mock_bundling_service_class,
        mock_qmessagebox,
        mock_path,
        workflow_with_multiple_bundles,
    ):
        """Integration test: verify all bundles are marked completed after workflow."""
        # Arrange
        mock_bundling_service = MagicMock()
        mock_bundling_service.convert_bundle_to_pdf.side_effect = [
            "C:\\test\\output1.pdf",
            "C:\\test\\output2.pdf",
        ]
        mock_bundling_service_class.return_value = mock_bundling_service

        # Mock Path for output directory
        mock_path_instance = MagicMock()
        mock_path_instance.parent.mkdir = MagicMock()
        mock_path.return_value = mock_path_instance

        # Mock message box
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QMessageBox.StandardButton.Ok
        mock_dialog.close = MagicMock()
        mock_qmessagebox.return_value = mock_dialog

        # Mock progress dialog
        progress_dialog = MagicMock()

        workflow = workflow_with_multiple_bundles
        workflow.current_bundle_index = 0
        workflow.page_order = [0]
        workflow.rotation_angle = 0

        metadata1 = {"output_filename": "output1.pdf", "company": "CompanyA"}
        metadata2 = {"output_filename": "output2.pdf", "company": "CompanyB"}

        # Act
        workflow._complete_pdf_conversion(progress_dialog, workflow.bundles[0], metadata1)
        workflow.current_bundle_index = 1
        workflow._complete_pdf_conversion(progress_dialog, workflow.bundles[1], metadata2)

        # Assert - both bundles should be marked completed
        assert mock_bundling_service.mark_bundle_completed.call_count == 2

        # Verify correct bundle IDs and PDF paths
        calls = mock_bundling_service.mark_bundle_completed.call_args_list
        assert calls[0][0] == (1, "C:\\test\\output1.pdf")
        assert calls[1][0] == (2, "C:\\test\\output2.pdf")
