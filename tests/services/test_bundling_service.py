"""
Comprehensive tests for BundlingService.

Tests bundle recommendation generation, confidence scoring, and bundle management.
"""

from unittest.mock import MagicMock, patch

import pytest

from services.bundling_service import BundlingService


class TestBundlingServiceInitialization:
    """Tests for BundlingService initialization"""

    def test_init_stores_analysis_db(self):
        # Arrange
        mock_db = MagicMock()

        # Act
        service = BundlingService(mock_db)

        # Assert
        assert service.analysis_db is mock_db


class TestGenerateBundleRecommendations:
    """Tests for generate_bundle_recommendations method"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return BundlingService(mock_db)

    def test_generate_returns_empty_when_no_analyses(self, service, mock_db):
        # Arrange
        mock_db.get_analyzed_pages.return_value = []

        # Act
        result = service.generate_bundle_recommendations()

        # Assert
        assert result == []

    def test_generate_uses_file_paths_when_provided(self, service, mock_db):
        # Arrange
        file_paths = ["file1.png", "file2.png"]
        mock_db.get_analysis.return_value = {
            "file_path": "file1.png",
            "company": "TestCo",
            "document_type": "invoice",
        }

        # Act
        service.generate_bundle_recommendations(file_paths=file_paths)

        # Assert
        assert mock_db.get_analysis.call_count == 2
        mock_db.get_analyzed_pages.assert_not_called()

    def test_generate_uses_analyzed_pages_when_no_file_paths(self, service, mock_db):
        # Arrange
        mock_db.get_analyzed_pages.return_value = []

        # Act
        service.generate_bundle_recommendations()

        # Assert
        mock_db.get_analyzed_pages.assert_called_once()

    def test_generate_filters_by_min_confidence(self, service, mock_db):
        # Arrange
        analyses = [
            {
                "file_path": "file1.png",
                "company": "TestCo",
                "document_type": "invoice",
                "document_date": "2024-01-01",
                "page_number": 1,
                "confidence_score": 0.9,
            },
            {
                "file_path": "file2.png",
                "company": "TestCo",
                "document_type": "invoice",
                "document_date": "2024-01-01",
                "page_number": 2,
                "confidence_score": 0.9,
            },
        ]
        mock_db.get_analyzed_pages.return_value = analyses
        mock_db.save_bundle_suggestion.return_value = 1

        # Act
        result = service.generate_bundle_recommendations(min_confidence=0.9)

        # Assert - bundle should have high confidence due to explicit page numbers
        assert len(result) > 0

    def test_generate_saves_bundles_to_database(self, service, mock_db):
        # Arrange
        analyses = [
            {
                "file_path": "file1.png",
                "company": "TestCo",
                "document_type": "invoice",
                "document_date": "2024-01-01",
                "page_number": 1,
                "confidence_score": 0.9,
            },
            {
                "file_path": "file2.png",
                "company": "TestCo",
                "document_type": "invoice",
                "document_date": "2024-01-01",
                "page_number": 2,
                "confidence_score": 0.9,
            },
        ]
        mock_db.get_analyzed_pages.return_value = analyses
        mock_db.save_bundle_suggestion.return_value = 123

        # Act
        result = service.generate_bundle_recommendations()

        # Assert
        mock_db.save_bundle_suggestion.assert_called_once()
        assert result[0]["id"] == 123

    def test_generate_sorts_by_confidence_descending(self, service, mock_db):
        # Arrange
        analyses = [
            {
                "file_path": "file1.png",
                "company": "CompanyA",
                "document_type": "invoice",
                "document_date": "2024-01-01",
                "page_number": 1,
                "confidence_score": 0.9,
            },
            {
                "file_path": "file2.png",
                "company": "CompanyA",
                "document_type": "invoice",
                "document_date": "2024-01-01",
                "page_number": 2,
                "confidence_score": 0.9,
            },
            {
                "file_path": "file3.png",
                "company": "CompanyB",
                "document_type": "receipt",
                "document_date": "2024-01-02",
                "confidence_score": 0.8,
            },
            {
                "file_path": "file4.png",
                "company": "CompanyB",
                "document_type": "receipt",
                "document_date": "2024-01-02",
                "confidence_score": 0.8,
            },
        ]
        mock_db.get_analyzed_pages.return_value = analyses
        mock_db.save_bundle_suggestion.side_effect = [1, 2]

        # Act
        result = service.generate_bundle_recommendations()

        # Assert - bundles should be sorted by confidence (page numbers > metadata)
        assert len(result) == 2
        assert result[0]["confidence_score"] > result[1]["confidence_score"]
        assert result[0]["grouping_method"] == "explicit_page_numbers"
        assert result[1]["grouping_method"] == "metadata_matching"


class TestGroupByPageNumbers:
    """Tests for _group_by_page_numbers method"""

    @pytest.fixture
    def service(self):
        return BundlingService(MagicMock())

    def test_group_by_page_numbers_groups_matching_metadata(self, service):
        # Arrange
        analyses = [
            {
                "file_path": "file1.png",
                "company": "TestCo",
                "document_type": "invoice",
                "document_date": "2024-01-01",
                "page_number": 1,
            },
            {
                "file_path": "file2.png",
                "company": "TestCo",
                "document_type": "invoice",
                "document_date": "2024-01-01",
                "page_number": 2,
            },
        ]

        # Act
        result = service._group_by_page_numbers(analyses)

        # Assert
        assert len(result) == 1
        assert result[0]["total_pages"] == 2
        assert result[0]["grouping_method"] == "explicit_page_numbers"

    def test_group_by_page_numbers_skips_files_without_page_numbers(self, service):
        # Arrange
        analyses = [
            {"file_path": "file1.png", "company": "TestCo"},
            {"file_path": "file2.png", "company": "TestCo"},
        ]

        # Act
        result = service._group_by_page_numbers(analyses)

        # Assert
        assert result == []

    def test_group_by_page_numbers_requires_minimum_2_pages(self, service):
        # Arrange
        analyses = [
            {
                "file_path": "file1.png",
                "company": "TestCo",
                "document_type": "invoice",
                "page_number": 1,
            }
        ]

        # Act
        result = service._group_by_page_numbers(analyses)

        # Assert
        assert result == []

    def test_group_by_page_numbers_sorts_by_page_number(self, service):
        # Arrange
        analyses = [
            {
                "file_path": "file3.png",
                "company": "TestCo",
                "document_type": "invoice",
                "page_number": 3,
            },
            {
                "file_path": "file1.png",
                "company": "TestCo",
                "document_type": "invoice",
                "page_number": 1,
            },
            {
                "file_path": "file2.png",
                "company": "TestCo",
                "document_type": "invoice",
                "page_number": 2,
            },
        ]

        # Act
        result = service._group_by_page_numbers(analyses)

        # Assert
        assert result[0]["file_paths"][0] == "file1.png"
        assert result[0]["file_paths"][1] == "file2.png"
        assert result[0]["file_paths"][2] == "file3.png"

    def test_group_by_page_numbers_handles_case_insensitive_matching(self, service):
        # Arrange
        analyses = [
            {
                "file_path": "file1.png",
                "company": "TestCo",
                "document_type": "Invoice",
                "page_number": 1,
            },
            {
                "file_path": "file2.png",
                "company": "TESTCO",
                "document_type": "invoice",
                "page_number": 2,
            },
        ]

        # Act
        result = service._group_by_page_numbers(analyses)

        # Assert
        assert len(result) == 1
        assert result[0]["total_pages"] == 2

    def test_group_by_page_numbers_handles_missing_metadata(self, service):
        # Arrange
        analyses = [
            {"file_path": "file1.png", "page_number": 1},
            {"file_path": "file2.png", "page_number": 2},
        ]

        # Act
        result = service._group_by_page_numbers(analyses)

        # Assert
        assert len(result) == 1


class TestGroupByMetadata:
    """Tests for _group_by_metadata method"""

    @pytest.fixture
    def service(self):
        return BundlingService(MagicMock())

    def test_group_by_metadata_groups_matching_files(self, service):
        # Arrange
        analyses = [
            {"file_path": "file1.png", "company": "TestCo", "document_type": "invoice"},
            {"file_path": "file2.png", "company": "TestCo", "document_type": "invoice"},
        ]

        # Act
        result = service._group_by_metadata(analyses)

        # Assert
        assert len(result) == 1
        assert result[0]["total_pages"] == 2
        assert result[0]["grouping_method"] == "metadata_matching"

    def test_group_by_metadata_skips_empty_metadata(self, service):
        # Arrange
        analyses = [
            {"file_path": "file1.png"},
            {"file_path": "file2.png"},
        ]

        # Act
        result = service._group_by_metadata(analyses)

        # Assert
        assert result == []

    def test_group_by_metadata_requires_minimum_2_files(self, service):
        # Arrange
        analyses = [{"file_path": "file1.png", "company": "TestCo"}]

        # Act
        result = service._group_by_metadata(analyses)

        # Assert
        assert result == []

    def test_group_by_metadata_sorts_by_filename(self, service):
        # Arrange
        analyses = [
            {"file_path": "/path/c.png", "company": "TestCo"},
            {"file_path": "/path/a.png", "company": "TestCo"},
            {"file_path": "/path/b.png", "company": "TestCo"},
        ]

        # Act
        result = service._group_by_metadata(analyses)

        # Assert
        assert result[0]["file_paths"][0] == "/path/a.png"
        assert result[0]["file_paths"][1] == "/path/b.png"
        assert result[0]["file_paths"][2] == "/path/c.png"

    def test_group_by_metadata_handles_partial_metadata(self, service):
        # Arrange
        analyses = [
            {"file_path": "file1.png", "company": "TestCo"},
            {"file_path": "file2.png", "company": "TestCo"},
        ]

        # Act
        result = service._group_by_metadata(analyses)

        # Assert
        assert len(result) == 1


class TestCalculateBundleConfidence:
    """Tests for _calculate_bundle_confidence method"""

    @pytest.fixture
    def service(self):
        return BundlingService(MagicMock())

    def test_calculate_returns_zero_for_empty_analyses(self, service):
        # Arrange
        bundle = {"analyses": []}

        # Act
        result = service._calculate_bundle_confidence(bundle)

        # Assert
        assert result == 0.0

    def test_calculate_gives_higher_score_for_explicit_page_numbers(self, service):
        # Arrange
        bundle_pages = {
            "grouping_method": "explicit_page_numbers",
            "company": "TestCo",
            "document_type": "invoice",
            "document_date": "2024-01-01",
            "analyses": [
                {"page_number": 1, "confidence_score": 0.9},
                {"page_number": 2, "confidence_score": 0.9},
            ],
        }
        bundle_metadata = {
            "grouping_method": "metadata_matching",
            "company": "TestCo",
            "document_type": "invoice",
            "document_date": "2024-01-01",
            "analyses": [
                {"confidence_score": 0.9},
                {"confidence_score": 0.9},
            ],
        }

        # Act
        score_pages = service._calculate_bundle_confidence(bundle_pages)
        score_metadata = service._calculate_bundle_confidence(bundle_metadata)

        # Assert
        assert score_pages > score_metadata

    def test_calculate_rewards_complete_metadata(self, service):
        # Arrange
        bundle_complete = {
            "grouping_method": "metadata_matching",
            "company": "TestCo",
            "document_type": "invoice",
            "document_date": "2024-01-01",
            "analyses": [{"confidence_score": 0.5}, {"confidence_score": 0.5}],
        }
        bundle_partial = {
            "grouping_method": "metadata_matching",
            "company": "TestCo",
            "document_type": None,
            "document_date": None,
            "analyses": [{"confidence_score": 0.5}, {"confidence_score": 0.5}],
        }

        # Act
        score_complete = service._calculate_bundle_confidence(bundle_complete)
        score_partial = service._calculate_bundle_confidence(bundle_partial)

        # Assert
        assert score_complete > score_partial

    def test_calculate_rewards_continuous_page_numbers(self, service):
        # Arrange
        bundle_continuous = {
            "grouping_method": "explicit_page_numbers",
            "company": "TestCo",
            "analyses": [
                {"page_number": 1, "confidence_score": 0.9},
                {"page_number": 2, "confidence_score": 0.9},
                {"page_number": 3, "confidence_score": 0.9},
            ],
        }
        bundle_gaps = {
            "grouping_method": "explicit_page_numbers",
            "company": "TestCo",
            "analyses": [
                {"page_number": 1, "confidence_score": 0.9},
                {"page_number": 3, "confidence_score": 0.9},
                {"page_number": 5, "confidence_score": 0.9},
            ],
        }

        # Act
        score_continuous = service._calculate_bundle_confidence(bundle_continuous)
        score_gaps = service._calculate_bundle_confidence(bundle_gaps)

        # Assert
        assert score_continuous > score_gaps

    def test_calculate_uses_analysis_confidence_scores(self, service):
        # Arrange
        bundle_high = {
            "grouping_method": "metadata_matching",
            "company": "TestCo",
            "analyses": [{"confidence_score": 1.0}, {"confidence_score": 1.0}],
        }
        bundle_low = {
            "grouping_method": "metadata_matching",
            "company": "TestCo",
            "analyses": [{"confidence_score": 0.1}, {"confidence_score": 0.1}],
        }

        # Act
        score_high = service._calculate_bundle_confidence(bundle_high)
        score_low = service._calculate_bundle_confidence(bundle_low)

        # Assert
        assert score_high > score_low

    def test_calculate_clamps_to_zero_and_one(self, service):
        # Arrange
        bundle = {
            "grouping_method": "metadata_matching",
            "company": "TestCo",
            "analyses": [{"confidence_score": 0.5}],
        }

        # Act
        result = service._calculate_bundle_confidence(bundle)

        # Assert
        assert 0.0 <= result <= 1.0


class TestGetBundleById:
    """Tests for get_bundle_by_id method"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return BundlingService(mock_db)

    def test_get_bundle_by_id_returns_matching_bundle(self, service, mock_db):
        # Arrange
        bundles = [
            {"id": 1, "company": "TestCo"},
            {"id": 2, "company": "OtherCo"},
        ]
        mock_db.get_bundle_suggestions.return_value = bundles

        # Act
        result = service.get_bundle_by_id(2)

        # Assert
        assert result["id"] == 2
        assert result["company"] == "OtherCo"

    def test_get_bundle_by_id_returns_none_when_not_found(self, service, mock_db):
        # Arrange
        mock_db.get_bundle_suggestions.return_value = [{"id": 1}]

        # Act
        result = service.get_bundle_by_id(999)

        # Assert
        assert result is None


class TestUpdateBundleStatus:
    """Tests for update_bundle_status and related methods"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return BundlingService(mock_db)

    def test_update_bundle_status_calls_database(self, service, mock_db):
        # Act
        service.update_bundle_status(123, "accepted", "User approved")

        # Assert
        mock_db.update_bundle_status.assert_called_once_with(123, "accepted", "User approved")

    def test_accept_bundle_updates_with_accepted_status(self, service, mock_db):
        # Act
        service.accept_bundle(123)

        # Assert
        mock_db.update_bundle_status.assert_called_once()
        call_args = mock_db.update_bundle_status.call_args
        assert call_args[0][0] == 123
        assert call_args[0][1] == "accepted"

    def test_reject_bundle_updates_with_rejected_status(self, service, mock_db):
        # Act
        service.reject_bundle(123)

        # Assert
        mock_db.update_bundle_status.assert_called_once()
        call_args = mock_db.update_bundle_status.call_args
        assert call_args[0][0] == 123
        assert call_args[0][1] == "rejected"

    def test_modify_bundle_updates_with_modified_status(self, service, mock_db):
        # Act
        service.modify_bundle(123, ["file1.png", "file2.png", "file3.png"])

        # Assert
        mock_db.update_bundle_status.assert_called_once()
        call_args = mock_db.update_bundle_status.call_args
        assert call_args[0][0] == 123
        assert call_args[0][1] == "modified"
        assert "3 files" in call_args[0][2]


class TestGetHighConfidenceBundles:
    """Tests for get_high_confidence_bundles method"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return BundlingService(mock_db)

    def test_get_high_confidence_bundles_calls_database(self, service, mock_db):
        # Arrange
        mock_db.get_bundle_suggestions.return_value = []

        # Act
        service.get_high_confidence_bundles(min_confidence=0.8)

        # Assert
        mock_db.get_bundle_suggestions.assert_called_once_with(min_confidence=0.8)

    def test_get_high_confidence_bundles_returns_database_results(self, service, mock_db):
        # Arrange
        bundles = [{"id": 1, "confidence_score": 0.9}]
        mock_db.get_bundle_suggestions.return_value = bundles

        # Act
        result = service.get_high_confidence_bundles()

        # Assert
        assert result == bundles


class TestFilterAlreadyBundledFiles:
    """Tests for filtering already-bundled files from recommendations"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return BundlingService(mock_db)

    def test_excludes_files_in_accepted_bundles(self, service, mock_db):
        # Arrange
        analyses = [
            {
                "file_path": "file1.png",
                "company": "TestCo",
                "document_type": "invoice",
                "page_number": 1,
            },
            {
                "file_path": "file2.png",
                "company": "TestCo",
                "document_type": "invoice",
                "page_number": 2,
            },
            {
                "file_path": "file3.png",
                "company": "TestCo",
                "document_type": "invoice",
                "page_number": 3,
            },
        ]
        mock_db.get_analyzed_pages.return_value = analyses
        # file1.png is already in an accepted bundle
        mock_db.get_bundled_file_paths.return_value = {"file1.png"}
        mock_db.save_bundle_suggestion.return_value = 1

        # Act
        result = service.generate_bundle_recommendations()

        # Assert
        mock_db.get_bundled_file_paths.assert_called_once()
        # Should only bundle file2.png and file3.png
        assert len(result) == 1
        assert "file1.png" not in result[0]["file_paths"]
        assert "file2.png" in result[0]["file_paths"]
        assert "file3.png" in result[0]["file_paths"]

    def test_excludes_files_in_completed_bundles(self, service, mock_db):
        # Arrange
        analyses = [
            {"file_path": "file1.png", "company": "TestCo", "document_type": "invoice"},
            {"file_path": "file2.png", "company": "TestCo", "document_type": "invoice"},
        ]
        mock_db.get_analyzed_pages.return_value = analyses
        # Both files are in completed bundles
        mock_db.get_bundled_file_paths.return_value = {"file1.png", "file2.png"}

        # Act
        result = service.generate_bundle_recommendations()

        # Assert
        assert result == []  # All files already bundled

    def test_returns_empty_when_all_files_bundled(self, service, mock_db):
        # Arrange
        analyses = [
            {"file_path": "file1.png", "company": "TestCo"},
            {"file_path": "file2.png", "company": "TestCo"},
        ]
        mock_db.get_analyzed_pages.return_value = analyses
        mock_db.get_bundled_file_paths.return_value = {"file1.png", "file2.png"}

        # Act
        result = service.generate_bundle_recommendations()

        # Assert
        assert result == []
        mock_db.save_bundle_suggestion.assert_not_called()

    def test_generates_bundles_when_no_files_bundled(self, service, mock_db):
        # Arrange
        analyses = [
            {
                "file_path": "file1.png",
                "company": "TestCo",
                "document_type": "invoice",
                "page_number": 1,
                "total_pages": 2,
            },
            {
                "file_path": "file2.png",
                "company": "TestCo",
                "document_type": "invoice",
                "page_number": 2,
                "total_pages": 2,
            },
        ]
        mock_db.get_analyzed_pages.return_value = analyses
        mock_db.get_bundled_file_paths.return_value = set()  # No files bundled yet
        mock_db.save_bundle_suggestion.return_value = 1

        # Act
        result = service.generate_bundle_recommendations()

        # Assert
        assert len(result) == 1
        assert len(result[0]["file_paths"]) == 2


class TestMarkBundleCompleted:
    """Tests for mark_bundle_completed method"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return BundlingService(mock_db)

    @patch("services.logging_service.get_logger")
    def test_updates_pdf_path(self, mock_logger, service, mock_db, tmp_path):
        # Arrange
        pdf_path = str(tmp_path / "test.pdf")
        # Create the file so it exists
        with open(pdf_path, "w") as f:
            f.write("test")

        mock_db.get_bundle_suggestions.return_value = [{"id": 123, "file_paths": ["image1.png"]}]
        mock_db.get_image_file.return_value = {"id": 1}

        # Act
        service.mark_bundle_completed(123, pdf_path)

        # Assert
        mock_db.update_bundle_pdf_path.assert_called_once_with(123, pdf_path)

    @patch("services.logging_service.get_logger")
    def test_sets_status_completed(self, mock_logger, service, mock_db, tmp_path):
        # Arrange
        pdf_path = str(tmp_path / "test.pdf")
        with open(pdf_path, "w") as f:
            f.write("test")

        mock_db.get_bundle_suggestions.return_value = [{"id": 123, "file_paths": ["image1.png"]}]
        mock_db.get_image_file.return_value = {"id": 1}

        # Act
        service.mark_bundle_completed(123, pdf_path)

        # Assert
        mock_db.update_bundle_status.assert_called_once()
        call_args = mock_db.update_bundle_status.call_args
        assert call_args[0][0] == 123
        assert call_args[0][1] == "completed"
        assert "test.pdf" in call_args[0][2]

    @patch("services.logging_service.get_logger")
    def test_handles_nonexistent_pdf_path_gracefully(self, mock_logger, service, mock_db):
        # Arrange
        pdf_path = "/nonexistent/path/test.pdf"
        mock_db.get_bundle_suggestions.return_value = [{"id": 123, "file_paths": ["image1.png"]}]
        mock_db.get_image_file.return_value = {"id": 1}

        # Act - should not raise exception
        service.mark_bundle_completed(123, pdf_path)

        # Assert - still updates database even though file doesn't exist
        mock_db.update_bundle_pdf_path.assert_called_once_with(123, pdf_path)
        mock_db.update_bundle_status.assert_called_once()

    @patch("services.logging_service.get_logger")
    def test_logs_warning_for_nonexistent_pdf(self, mock_logger, service, mock_db):
        # Arrange
        pdf_path = "/nonexistent/path/test.pdf"
        mock_db.get_bundle_suggestions.return_value = [{"id": 123, "file_paths": ["image1.png"]}]
        mock_db.get_image_file.return_value = {"id": 1}

        # Act
        service.mark_bundle_completed(123, pdf_path)

        # Assert
        # Should log warning about nonexistent PDF
        warning_calls = [str(call) for call in mock_logger.return_value.warning.call_args_list]
        assert any(pdf_path in call for call in warning_calls)

    @patch("services.logging_service.get_logger")
    def test_includes_pdf_filename_in_user_action(self, mock_logger, service, mock_db, tmp_path):
        # Arrange
        pdf_path = str(tmp_path / "invoice_2024-01-01.pdf")
        with open(pdf_path, "w") as f:
            f.write("test")

        mock_db.get_bundle_suggestions.return_value = [{"id": 123, "file_paths": ["image1.png"]}]
        mock_db.get_image_file.return_value = {"id": 1}

        # Act
        service.mark_bundle_completed(123, pdf_path)

        # Assert
        call_args = mock_db.update_bundle_status.call_args
        user_action = call_args[0][2]
        assert "invoice_2024-01-01.pdf" in user_action
        assert "PDF generated:" in user_action

    @patch("services.logging_service.get_logger")
    @patch("db.metadata_db.MetadataDB.compute_file_hash")
    def test_registers_pdf_in_database(self, mock_hash, mock_logger, service, mock_db, tmp_path):
        # Arrange
        pdf_path = str(tmp_path / "test.pdf")
        with open(pdf_path, "w") as f:
            f.write("test content")

        mock_hash.return_value = "abc123hash"
        mock_db.get_bundle_suggestions.return_value = [
            {"id": 123, "file_paths": ["image1.png", "image2.png"]}
        ]
        mock_db.get_image_file.side_effect = [
            {"id": 1},
            {"id": 2},
        ]

        # Act
        service.mark_bundle_completed(123, pdf_path)

        # Assert
        mock_db.register_pdf_file.assert_called_once()
        call_args = mock_db.register_pdf_file.call_args
        assert call_args[1]["pdf_path"] == pdf_path
        assert call_args[1]["pdf_filename"] == "test.pdf"
        assert call_args[1]["bundle_id"] == 123
        assert call_args[1]["source_image_ids"] == [1, 2]
        assert call_args[1]["page_count"] == 2
        assert call_args[1]["file_hash"] == "abc123hash"
        assert call_args[1]["file_size"] > 0

    @patch("services.logging_service.get_logger")
    def test_updates_image_status_to_bundled(self, mock_logger, service, mock_db):
        # Arrange
        mock_db.get_bundle_suggestions.return_value = [
            {"id": 123, "file_paths": ["image1.png", "image2.png", "image3.png"]}
        ]
        mock_db.get_image_file.side_effect = [
            {"id": 1},
            {"id": 2},
            {"id": 3},
        ]

        # Act
        service.mark_bundle_completed(123, "/path/to/test.pdf")

        # Assert
        assert mock_db.update_image_status.call_count == 3
        mock_db.update_image_status.assert_any_call("image1.png", "bundled")
        mock_db.update_image_status.assert_any_call("image2.png", "bundled")
        mock_db.update_image_status.assert_any_call("image3.png", "bundled")

    @patch("services.logging_service.get_logger")
    def test_handles_missing_bundle_gracefully(self, mock_logger, service, mock_db):
        # Arrange
        mock_db.get_bundle_suggestions.return_value = []  # Bundle not found

        # Act
        service.mark_bundle_completed(999, "/path/to/test.pdf")

        # Assert
        mock_db.register_pdf_file.assert_not_called()
        mock_db.update_image_status.assert_not_called()
        mock_logger.return_value.warning.assert_called()

    @patch("services.logging_service.get_logger")
    def test_handles_json_string_file_paths(self, mock_logger, service, mock_db):
        # Arrange - file_paths as JSON string instead of list
        import json

        mock_db.get_bundle_suggestions.return_value = [
            {"id": 123, "file_paths": json.dumps(["image1.png", "image2.png"])}
        ]
        mock_db.get_image_file.side_effect = [
            {"id": 1},
            {"id": 2},
        ]

        # Act
        service.mark_bundle_completed(123, "/path/to/test.pdf")

        # Assert
        assert mock_db.update_image_status.call_count == 2

    @patch("services.logging_service.get_logger")
    def test_logs_warning_for_missing_image_files(self, mock_logger, service, mock_db):
        # Arrange
        mock_db.get_bundle_suggestions.return_value = [
            {"id": 123, "file_paths": ["image1.png", "missing.png"]}
        ]
        mock_db.get_image_file.side_effect = [
            {"id": 1},
            None,  # Missing image file
        ]

        # Act
        service.mark_bundle_completed(123, "/path/to/test.pdf")

        # Assert
        mock_logger.return_value.warning.assert_any_call(
            "Image file not found in database: missing.png"
        )

    @patch("services.logging_service.get_logger")
    @patch("db.metadata_db.MetadataDB.compute_file_hash")
    def test_handles_pdf_registration_error(self, mock_hash, mock_logger, service, mock_db):
        # Arrange
        mock_hash.return_value = "hash123"
        mock_db.get_bundle_suggestions.return_value = [{"id": 123, "file_paths": ["image1.png"]}]
        mock_db.get_image_file.return_value = {"id": 1}
        mock_db.register_pdf_file.side_effect = Exception("Database error")

        # Act - should not raise exception
        service.mark_bundle_completed(123, "/path/to/test.pdf")

        # Assert - still completes other operations
        mock_logger.return_value.error.assert_called()
        mock_db.update_bundle_pdf_path.assert_called_once()
        mock_db.update_bundle_status.assert_called_once()


class TestProposeOutputFilename:
    """Tests for propose_output_filename method"""

    @pytest.fixture
    def service(self):
        return BundlingService(MagicMock())

    def test_generates_filename_with_all_metadata(self, service):
        # Arrange
        bundle = {
            "company": "Acme Corp",
            "document_type": "Invoice",
            "document_date": "2024-01-15",
        }

        # Act
        result = service.propose_output_filename(bundle)

        # Assert
        assert result == "Acme_Corp_Invoice_2024-01-15.pdf"

    def test_generates_filename_without_date(self, service):
        # Arrange
        bundle = {
            "company": "Test Company",
            "document_type": "Receipt",
            "document_date": "",
        }

        # Act
        result = service.propose_output_filename(bundle)

        # Assert
        assert result == "Test_Company_Receipt.pdf"

    def test_sanitizes_special_characters(self, service):
        # Arrange
        bundle = {
            "company": "Company (Pty) Ltd.",
            "document_type": "Tax/Invoice",
            "document_date": "2024-01-15",
        }

        # Act
        result = service.propose_output_filename(bundle)

        # Assert
        # Special characters should be removed
        assert "(" not in result
        assert ")" not in result
        assert "." not in result.replace(".pdf", "")  # Ignore .pdf extension
        assert "/" not in result

    def test_handles_missing_metadata(self, service):
        # Arrange
        bundle = {}

        # Act
        result = service.propose_output_filename(bundle)

        # Assert
        assert result == "Unknown_Document.pdf"

    def test_replaces_spaces_with_underscores(self, service):
        # Arrange
        bundle = {
            "company": "Multi Word Company",
            "document_type": "Purchase Order",
            "document_date": "2024-01-15",
        }

        # Act
        result = service.propose_output_filename(bundle)

        # Assert
        assert " " not in result
        assert "Multi_Word_Company" in result
        assert "Purchase_Order" in result

    def test_handles_none_values(self, service):
        # Arrange
        bundle = {
            "company": None,
            "document_type": None,
            "document_date": None,
        }

        # Act
        result = service.propose_output_filename(bundle)

        # Assert
        assert result.endswith(".pdf")
        assert "None" not in result  # Should convert None to string properly


class TestSetOutputFilenameOnBundleCreation:
    """Tests for setting output filename on source images during bundle creation"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return BundlingService(mock_db)

    def test_sets_output_filename_for_bundle_images(self, service, mock_db):
        # Arrange
        analyses = [
            {
                "file_path": "file1.png",
                "company": "TestCo",
                "document_type": "Invoice",
                "document_date": "2024-01-01",
                "page_number": 1,
                "total_pages": 2,
                "confidence_score": 0.9,
            },
            {
                "file_path": "file2.png",
                "company": "TestCo",
                "document_type": "Invoice",
                "document_date": "2024-01-01",
                "page_number": 2,
                "total_pages": 2,
                "confidence_score": 0.9,
            },
        ]
        mock_db.get_analyzed_pages.return_value = analyses
        mock_db.get_bundled_file_paths.return_value = set()
        mock_db.save_bundle_suggestion.return_value = 1

        # Act
        service.generate_bundle_recommendations()

        # Assert
        assert mock_db.set_image_output_filename.call_count == 2
        # Check that it was called with correct filename format
        call_args_list = mock_db.set_image_output_filename.call_args_list
        assert call_args_list[0][0][0] == "file1.png"
        assert call_args_list[1][0][0] == "file2.png"
        # Both should get the same proposed filename
        assert call_args_list[0][0][1] == call_args_list[1][0][1]
        # Filename is lowercase due to bundle metadata normalization
        assert "testco" in call_args_list[0][0][1].lower()
        assert "invoice" in call_args_list[0][0][1].lower()

    def test_handles_set_filename_error_gracefully(self, service, mock_db):
        # Arrange
        analyses = [
            {
                "file_path": "file1.png",
                "company": "TestCo",
                "document_type": "Invoice",
                "page_number": 1,
                "total_pages": 2,
                "confidence_score": 0.9,
            },
            {
                "file_path": "file2.png",
                "company": "TestCo",
                "document_type": "Invoice",
                "page_number": 2,
                "total_pages": 2,
                "confidence_score": 0.9,
            },
        ]
        mock_db.get_analyzed_pages.return_value = analyses
        mock_db.get_bundled_file_paths.return_value = set()
        mock_db.save_bundle_suggestion.return_value = 1
        # Simulate error on first file
        mock_db.set_image_output_filename.side_effect = [Exception("DB error"), None]

        # Act - should not raise exception
        bundles = service.generate_bundle_recommendations()

        # Assert - bundle still created successfully
        assert len(bundles) == 1
        assert mock_db.save_bundle_suggestion.called
