"""
Shared fixtures for GUI tests.

Provides QApplication, mock services, and common test utilities.
"""

import sys
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for the test session.

    PyQt6 requires a QApplication instance before creating any widgets.
    This fixture ensures one exists for all GUI tests.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    # Don't quit - other tests may need it


@pytest.fixture
def mock_config_manager():
    """Mock ConfigManager for GUI tests."""
    config = MagicMock()
    config.get_setting.side_effect = lambda section, key, default=None: {
        ("DocumentProcessing", "scan_folder"): "C:\\test\\scan",
        ("DocumentProcessing", "organized_subfolder"): "organized",
        ("LLMProvider", "active_provider"): "ollama",
        ("AutoAnalysis", "enabled"): True,
        ("AutoAnalysis", "batch_size"): 10,
    }.get((section, key), default)
    config.get_bool.return_value = True
    config.get_int.return_value = 10
    config.get_directories.return_value = ["C:\\test\\scan"]
    config.get_active_provider.return_value = "ollama"
    return config


@pytest.fixture
def mock_analysis_db():
    """Mock AnalysisDB for GUI tests."""
    db = MagicMock()
    db.get_all_analyses.return_value = []
    db.get_analysis.return_value = None
    db.get_active_directories.return_value = ["C:\\test\\scan"]
    db.save_analysis.return_value = None
    db.close.return_value = None
    return db


@pytest.fixture
def mock_metadata_db():
    """Mock MetadataDB for GUI tests."""
    db = MagicMock()
    db.get_metadata.return_value = None
    db.save_metadata.return_value = None
    db.get_all_metadata.return_value = []
    db.close.return_value = None
    return db


@pytest.fixture
def mock_analysis_service():
    """Mock AnalysisService for GUI tests."""
    service = MagicMock()
    service.scan_all_directories.return_value = {
        "total_files": 10,
        "analyzed": 8,
        "cached": 2,
        "errors": 0,
        "skipped": 0,
    }
    service.analyze_specific_files.return_value = {
        "total_files": 5,
        "analyzed": 5,
        "cached": 0,
        "errors": 0,
        "skipped": 0,
    }
    return service


@pytest.fixture
def mock_bundling_service():
    """Mock BundlingService for GUI tests."""
    service = MagicMock()
    service.generate_bundle_recommendations.return_value = []
    service.get_all_bundles.return_value = []
    service.create_bundle.return_value = 1
    service.delete_bundle.return_value = None
    return service


@pytest.fixture
def mock_file_service():
    """Mock FileService for GUI tests."""
    service = MagicMock()
    service.scan_folder = "C:\\test\\scan"
    service.organized_folder = "C:\\test\\scan\\organized"
    service.create_searchable_pdf.return_value = "C:\\test\\output.pdf"
    service.move_pdf_to_organized.return_value = "C:\\test\\scan\\organized\\output.pdf"
    return service


@pytest.fixture
def sample_analysis_data():
    """Sample analysis data for testing."""
    return {
        "file_path": "C:\\test\\scan\\page1.png",
        "file_hash": "abc123",
        "provider_name": "ollama",
        "model_name": "qwen2.5-vl",
        "analysis_data": {
            "company": "TestCo",
            "document_type": "invoice",
            "document_date": "2024-01-15",
            "page_number": 1,
            "confidence_score": 0.95,
        },
        "raw_response": '{"company": "TestCo"}',
        "processing_time_ms": 150,
        "analyzed_at": "2024-01-15 10:30:00",
    }


@pytest.fixture
def sample_bundle_data():
    """Sample bundle data for testing."""
    return {
        "bundle_id": 1,
        "company": "TestCo",
        "document_type": "invoice",
        "document_date": "2024-01-15",
        "total_pages": 3,
        "file_paths": [
            "C:\\test\\scan\\page1.png",
            "C:\\test\\scan\\page2.png",
            "C:\\test\\scan\\page3.png",
        ],
        "confidence_score": 0.92,
        "grouping_method": "explicit_page_numbers",
        "created_at": "2024-01-15 10:35:00",
    }
