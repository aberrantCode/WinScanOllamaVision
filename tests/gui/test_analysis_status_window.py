"""
Tests for AnalysisStatusWindow.

TODO: Implement tests for:
- Window initialization
- Tab switching (Collection Status, File Analysis Grid)
- Auto-start analysis functionality
- Retry failed analysis signal
- Theme switching (light/dark mode)
- Data loading and refresh
- Analysis worker thread handling
- Close event cleanup
"""

from unittest.mock import MagicMock


class TestAnalysisStatusWindow:
    """Tests for AnalysisStatusWindow class"""

    def test_placeholder(self):
        """Placeholder test - remove when real tests are implemented"""
        pass

    def test_calculate_collection_statistics_includes_pdfs_generated(
        self, qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
    ):
        """Test that _calculate_collection_statistics includes pdfs_generated metric"""
        from ui.analysis_status_window import AnalysisStatusWindow

        # Mock database connection and cursor
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.connection.cursor.return_value = mock_cursor

        # Configure mock analysis_db
        mock_analysis_db.connection = mock_connection
        mock_analysis_db.get_bundle_suggestions.return_value = []
        mock_analysis_db.get_document_type_breakdown.return_value = {}

        # Configure mock config_manager
        mock_config_manager.get_setting.return_value = "light"
        mock_config_manager.get_directories.return_value = []

        # Create window with mocked dependencies
        window = AnalysisStatusWindow(
            analysis_db=mock_analysis_db,
            metadata_db=mock_metadata_db,
            config_manager=mock_config_manager,
        )

        # Set up cursor.fetchone() to return mock data for each query
        # The queries are called in this order:
        # 1. files_analyzed
        # 2. high_confidence
        # 3. pages_bundled
        # 4. documents_archived
        # 5. pdfs_generated (NEW)
        # 6. cached_count
        # 7. missing_metadata_count
        # 8. avg_confidence
        # 9. error_count
        # 10-13. metadata_completeness (4 fields)
        # 14. accepted_count
        # 15. reviewed_count
        # 16. total_archived_pages
        # 17. avg_processing_time_ms (non-cached)
        # 18. tax_related_count
        mock_cursor.fetchone.side_effect = [
            (100,),  # files_analyzed
            (80,),  # high_confidence
            (50,),  # pages_bundled
            (10,),  # documents_archived
            (7,),  # pdfs_generated
            (20,),  # cached_count
            (5,),  # missing_metadata_count
            (0.85,),  # avg_confidence
            (2,),  # error_count
            (90,),  # metadata_completeness: company
            (85,),  # metadata_completeness: document_type
            (80,),  # metadata_completeness: document_date
            (75,),  # metadata_completeness: page_number
            (8,),  # accepted_count
            (10,),  # reviewed_count
            (45,),  # total_archived_pages
            (2500,),  # avg_processing_time_ms
            (15,),  # tax_related_count
        ]

        # Mock fetchall for recent_analyses and company_distribution
        mock_cursor.fetchall.side_effect = [
            [],  # recent_analyses (empty - processing speed will be 0)
            [],  # company_distribution (empty)
        ]

        # Call the method
        stats = window._calculate_collection_statistics()

        # Verify pdfs_generated is included and has correct value
        assert "pdfs_generated" in stats
        assert stats["pdfs_generated"] == 7

        # Cleanup
        window.close()

    def test_calculate_collection_statistics_pdfs_generated_query(
        self, qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
    ):
        """Test that the correct SQL query is executed for pdfs_generated"""
        from ui.analysis_status_window import AnalysisStatusWindow

        # Mock database connection and cursor
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.connection.cursor.return_value = mock_cursor

        # Configure mock analysis_db
        mock_analysis_db.connection = mock_connection
        mock_analysis_db.get_bundle_suggestions.return_value = []
        mock_analysis_db.get_document_type_breakdown.return_value = {}

        # Configure mock config_manager
        mock_config_manager.get_setting.return_value = "light"
        mock_config_manager.get_directories.return_value = []

        # Create window with mocked dependencies
        window = AnalysisStatusWindow(
            analysis_db=mock_analysis_db,
            metadata_db=mock_metadata_db,
            config_manager=mock_config_manager,
        )

        # Set up cursor.fetchone() to return mock data
        mock_cursor.fetchone.return_value = (5,)
        mock_cursor.fetchall.return_value = []

        # Call the method
        window._calculate_collection_statistics()

        # Verify the PDFs generated query was called
        # The query should select COUNT(*) from document_bundles WHERE status = 'completed' AND pdf_path IS NOT NULL
        execute_calls = [str(call) for call in mock_cursor.execute.call_args_list]

        # Find the PDFs generated query
        pdfs_query_found = any(
            "status = 'completed'" in str(call) and "pdf_path IS NOT NULL" in str(call)
            for call in execute_calls
        )

        assert pdfs_query_found, "PDFs generated query not found in execute calls"

        # Cleanup
        window.close()
