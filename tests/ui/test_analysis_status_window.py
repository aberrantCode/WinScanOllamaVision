"""
Tests for Analysis Status Window enhancements
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QTableWidgetItem

from ui.analysis_status_window import AnalysisStatusWindow


@pytest.fixture
def qapp():
    """QApplication fixture for Qt widgets"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_analysis_db():
    """Mock AnalysisDB for testing"""
    db = MagicMock()
    db.connection = MagicMock()
    db.connection.connection = MagicMock()
    db.get_analyzed_pages = MagicMock(return_value=[])
    db.get_bundle_suggestions = MagicMock(return_value=[])
    return db


@pytest.fixture
def mock_metadata_db():
    """Mock MetadataDB for testing"""
    db = MagicMock()
    return db


@pytest.fixture
def mock_config_manager():
    """Mock ConfigManager for testing"""
    config = MagicMock()
    config.get_setting = MagicMock(return_value="light")
    config.get_directories = MagicMock(return_value=[])
    return config


class TestAnalysisStatusWindowEnhancements:
    """Test suite for Analytics & Details window enhancements"""

    def test_window_title_is_analytics_and_details(
        self, qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
    ):
        """Test window title is 'Analytics & Details'"""
        window = AnalysisStatusWindow(
            analysis_db=mock_analysis_db,
            metadata_db=mock_metadata_db,
            config_manager=mock_config_manager,
        )
        assert window.windowTitle() == "Analytics & Details"

    def test_tab_names_are_correct(
        self, qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
    ):
        """Test tab names are correct"""
        window = AnalysisStatusWindow(
            analysis_db=mock_analysis_db,
            metadata_db=mock_metadata_db,
            config_manager=mock_config_manager,
        )
        assert window.tabs.count() == 3
        assert window.tabs.tabText(0) == "Analytics"
        assert window.tabs.tabText(1) == "Image Details"
        assert window.tabs.tabText(2) == "PDF Details"

    def test_create_document_details_tab_creates_table(
        self, qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
    ):
        """Test _create_document_details_tab() creates table"""
        window = AnalysisStatusWindow(
            analysis_db=mock_analysis_db,
            metadata_db=mock_metadata_db,
            config_manager=mock_config_manager,
        )
        assert hasattr(window, "document_table")
        assert window.document_table is not None
        assert window.document_table.columnCount() == 6

        # Check column headers
        headers = [
            window.document_table.horizontalHeaderItem(i).text()
            for i in range(window.document_table.columnCount())
        ]
        assert headers == [
            "PDF Filename",
            "Company",
            "Document Type",
            "Date",
            "Pages",
            "Created At",
        ]

    def test_refresh_document_details_populates_table(
        self, qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
    ):
        """Test _refresh_document_details() populates table"""
        # Setup mock database response - match actual query column order
        # After Migration 16, query returns: id, pdf_path, created_at, page_count, company, doc_type, doc_date
        mock_cursor = MagicMock()
        test_data = [
            (
                1,  # bundle_id
                "C:/output/Invoice_ABC_2024-01-15.pdf",  # pdf_path
                datetime.now().isoformat(),  # created_at
                2,  # page_count
                "ABC Company",  # company
                "Invoice",  # document_type
                "2024-01-15",  # document_date
            ),
            (
                2,  # bundle_id
                "C:/output/Receipt_XYZ_2024-01-20.pdf",  # pdf_path
                datetime.now().isoformat(),  # created_at
                1,  # page_count
                "XYZ Corp",  # company
                "Receipt",  # document_type
                "2024-01-20",  # document_date
            ),
        ]
        mock_cursor.fetchall.return_value = test_data
        mock_analysis_db.connection.connection.cursor.return_value = mock_cursor

        window = AnalysisStatusWindow(
            analysis_db=mock_analysis_db,
            metadata_db=mock_metadata_db,
            config_manager=mock_config_manager,
        )

        # Refresh document details
        window._refresh_document_details()

        # Verify table has 2 rows
        assert window.document_table.rowCount() == 2

        # Verify first row data
        assert window.document_table.item(0, 0).text() == "Invoice_ABC_2024-01-15.pdf"
        assert window.document_table.item(0, 1).text() == "ABC Company"
        assert window.document_table.item(0, 2).text() == "Invoice"
        assert window.document_table.item(0, 3).text() == "2024-01-15"
        assert window.document_table.item(0, 4).text() == "2"  # 2 pages

        # Verify second row data
        assert window.document_table.item(1, 0).text() == "Receipt_XYZ_2024-01-20.pdf"
        assert window.document_table.item(1, 1).text() == "XYZ Corp"
        assert window.document_table.item(1, 2).text() == "Receipt"
        assert window.document_table.item(1, 3).text() == "2024-01-20"
        assert window.document_table.item(1, 4).text() == "1"  # 1 page

        # Verify PDF path is stored in UserRole data
        pdf_path = window.document_table.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert pdf_path == "C:/output/Invoice_ABC_2024-01-15.pdf"

    @patch("os.path.exists")
    @patch("os.name", "nt")
    @patch("os.startfile")
    def test_double_click_opens_pdf_on_windows(
        self,
        mock_startfile,
        mock_exists,
        qapp,
        mock_analysis_db,
        mock_metadata_db,
        mock_config_manager,
    ):
        """Test double-click opens PDF in default viewer on Windows"""
        mock_exists.return_value = True

        window = AnalysisStatusWindow(
            analysis_db=mock_analysis_db,
            metadata_db=mock_metadata_db,
            config_manager=mock_config_manager,
        )

        # Add a row to the table
        window.document_table.insertRow(0)
        item = QTableWidgetItem("test.pdf")
        item.setData(Qt.ItemDataRole.UserRole, "C:/output/test.pdf")
        window.document_table.setItem(0, 0, item)

        # Simulate double-click
        window._on_document_table_double_click(item)

        # Verify os.startfile was called with the PDF path
        mock_startfile.assert_called_once_with("C:/output/test.pdf")

    @patch("os.path.exists")
    def test_double_click_shows_warning_if_file_not_found(
        self, mock_exists, qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
    ):
        """Test double-click shows warning if PDF file not found"""
        mock_exists.return_value = False

        window = AnalysisStatusWindow(
            analysis_db=mock_analysis_db,
            metadata_db=mock_metadata_db,
            config_manager=mock_config_manager,
        )

        # Add a row to the table
        window.document_table.insertRow(0)
        item = QTableWidgetItem("test.pdf")
        item.setData(Qt.ItemDataRole.UserRole, "C:/output/test.pdf")
        window.document_table.setItem(0, 0, item)

        # Simulate double-click (should show warning dialog)
        with patch("PyQt6.QtWidgets.QMessageBox.warning") as mock_warning:
            window._on_document_table_double_click(item)
            mock_warning.assert_called_once()

    def test_refresh_all_calls_refresh_document_details(
        self, qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
    ):
        """Test _refresh_all() calls _refresh_document_details()"""
        window = AnalysisStatusWindow(
            analysis_db=mock_analysis_db,
            metadata_db=mock_metadata_db,
            config_manager=mock_config_manager,
        )

        # Mock the refresh method
        window._refresh_document_details = Mock()

        # Call refresh_all
        window._refresh_all()

        # Verify document details refresh was called
        window._refresh_document_details.assert_called_once()

    def test_load_all_data_calls_refresh_document_details(
        self, qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
    ):
        """Test _load_all_data() calls _refresh_document_details()"""
        window = AnalysisStatusWindow(
            analysis_db=mock_analysis_db,
            metadata_db=mock_metadata_db,
            config_manager=mock_config_manager,
        )

        # Mock the refresh method
        window._refresh_document_details = Mock()

        # Call load_all_data
        window._load_all_data()

        # Verify document details refresh was called
        window._refresh_document_details.assert_called_once()
