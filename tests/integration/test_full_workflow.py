"""
Integration tests for full application workflow.

Tests the complete flow: Scan → Analyze → Bundle → Create PDF
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from config.config_manager import ConfigManager
from db.analysis_db import AnalysisDB
from db.metadata_db import MetadataDB
from services.analysis_service import AnalysisService
from services.bundling_service import BundlingService
from services.file_service import FileService


class TestFullWorkflow:
    """Integration tests for complete application workflow"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def temp_db_dir(self):
        """Create temporary directory for test databases"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup
        import shutil

        # Close any open database connections first
        import time

        time.sleep(0.1)  # Give connections time to close
        for attempt in range(3):
            try:
                shutil.rmtree(temp_dir, ignore_errors=False)
                break
            except PermissionError:
                if attempt < 2:
                    time.sleep(0.1)
                else:
                    shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def test_images(self, temp_dir):
        """Create test image files"""
        image_files = []
        for i in range(3):
            img_path = os.path.join(temp_dir, f"page_{i+1}.png")
            Path(img_path).touch()
            image_files.append(img_path)
        return image_files

    @pytest.fixture
    def config_manager(self, temp_dir):
        """Create test ConfigManager"""
        config = MagicMock(spec=ConfigManager)
        config.get_setting.side_effect = lambda section, key: {
            ("DocumentProcessing", "scan_folder"): temp_dir,
            ("DocumentProcessing", "organized_subfolder"): "organized",
            ("Prompts", "document_metadata"): "Analyze this document",
        }.get((section, key))
        config.get_bool.return_value = True
        config.get_int.return_value = 10
        config.get_active_provider.return_value = "ollama"
        config.get_provider_config.return_value = {
            "base_url": "http://localhost:11434",
            "model": "qwen2.5-vl",
            "timeout": 300,
        }
        return config

    @pytest.fixture
    def analysis_db(self, temp_db_dir):
        """Create test AnalysisDB"""
        db_path = os.path.join(temp_db_dir, "analysis.db")
        with patch("config.appdata_manager.AppDataManager") as mock_appdata:
            mock_appdata.return_value.get_analysis_db_path.return_value = db_path
            db = AnalysisDB()
            yield db
            db.close()

    @pytest.fixture
    def metadata_db(self, temp_db_dir):
        """Create test MetadataDB"""
        db_path = os.path.join(temp_db_dir, "metadata.db")
        with patch("config.appdata_manager.AppDataManager") as mock_appdata:
            mock_appdata.return_value.get_metadata_db_path.return_value = db_path
            db = MetadataDB()
            yield db
            db.close()

    @patch("services.analysis_service.get_logger")
    @patch("services.analysis_service.ProviderFactory")
    @patch("glob.glob")
    @patch("os.path.exists")
    def test_scan_and_analyze_workflow(
        self,
        mock_exists,
        mock_glob,
        mock_factory,
        mock_get_logger,
        config_manager,
        analysis_db,
        metadata_db,
        test_images,
        temp_dir,
    ):
        """Test complete scan and analysis workflow"""
        # Arrange
        mock_exists.return_value = True
        mock_glob.side_effect = lambda pattern: (
            test_images if "*.png" in pattern and "*.PNG" not in pattern else []
        )
        mock_get_logger.return_value = MagicMock()

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.provider_name = "ollama"
        mock_provider.analyze_images.return_value = {
            "success": True,
            "response": '{"company": "TestCo", "document_type": "invoice"}',
            "metadata": {"company": "TestCo", "document_type": "invoice"},
            "processing_time_ms": 100,
            "model_used": "qwen2.5-vl",
        }
        mock_factory.create_from_config_manager.return_value = mock_provider

        # Mock database methods
        analysis_db.get_active_directories = MagicMock(return_value=[temp_dir])

        # Create service
        service = AnalysisService(config_manager, analysis_db, metadata_db)

        # Act
        stats = service.scan_all_directories(incremental=False)

        # Assert
        assert stats["total_files"] == 3
        assert stats["analyzed"] == 3
        assert stats["errors"] == 0
        assert mock_provider.analyze_images.call_count == 3

    @patch("services.analysis_service.get_logger")
    @patch("services.analysis_service.ProviderFactory")
    def test_analysis_to_bundling_workflow(
        self,
        mock_factory,
        mock_get_logger,
        config_manager,
        analysis_db,
        metadata_db,
        test_images,
    ):
        """Test workflow from analysis to bundle generation"""
        # Arrange
        mock_get_logger.return_value = MagicMock()

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.provider_name = "ollama"
        mock_provider.analyze_images.return_value = {
            "success": True,
            "response": '{"company": "TestCo", "document_type": "invoice", "page_number": 1}',
            "metadata": {
                "company": "TestCo",
                "document_type": "invoice",
                "page_number": 1,
            },
            "processing_time_ms": 100,
            "model_used": "qwen2.5-vl",
        }
        mock_factory.create_from_config_manager.return_value = mock_provider

        # Create services
        # AnalysisService not needed for this test, only BundlingService
        bundling_service = BundlingService(analysis_db)

        # Manually save analysis results to simulate analysis
        for i, img_path in enumerate(test_images):
            analysis_db.save_analysis(
                file_path=img_path,
                file_hash=f"hash_{i}",
                provider_name="ollama",
                model_name="qwen2.5-vl",
                analysis_data={
                    "company": "TestCo",
                    "document_type": "invoice",
                    "page_number": i + 1,
                    "confidence_score": 0.9,  # Add confidence score to prevent TypeError
                },
                raw_response="{}",
                processing_time_ms=100,
            )

        # Act - Generate bundle recommendations
        bundles = bundling_service.generate_bundle_recommendations(
            file_paths=test_images, min_confidence=0.5
        )

        # Assert
        assert len(bundles) > 0
        assert bundles[0]["total_pages"] == 3
        assert bundles[0]["company"] == "testco"
        assert bundles[0]["document_type"] == "invoice"
        assert bundles[0]["grouping_method"] == "explicit_page_numbers"

    @patch("fitz.open")
    @patch("PIL.Image.open")
    @patch("os.makedirs")
    @patch("os.path.exists")
    def test_bundling_to_pdf_workflow(
        self,
        mock_exists,
        mock_makedirs,
        mock_image_open,
        mock_fitz_open,
        config_manager,
        test_images,
    ):
        """Test workflow from bundle to PDF creation"""
        # Arrange
        mock_exists.return_value = True

        # Mock PIL Image
        mock_image = MagicMock()
        mock_image.width = 800
        mock_image.height = 600
        mock_image_open.return_value.__enter__ = MagicMock(return_value=mock_image)
        mock_image_open.return_value.__exit__ = MagicMock(return_value=False)

        # Mock PyMuPDF
        mock_doc = MagicMock()
        mock_doc.page_count = 3
        mock_page = MagicMock()
        mock_doc.new_page.return_value = mock_page
        mock_fitz_open.return_value = mock_doc

        # Create file service
        file_service = FileService(config_manager)

        # Act - Create PDF from bundle
        output_path = file_service.create_searchable_pdf(
            image_paths=test_images,
            output_filename="test_bundle.pdf",
            extracted_text_coords={"pages": []},
            is_searchable=False,
        )

        # Assert
        assert output_path is not None
        assert "test_bundle.pdf" in output_path
        assert mock_doc.new_page.call_count == 3
        mock_doc.save.assert_called_once()

    @patch("services.analysis_service.get_logger")
    @patch("services.analysis_service.ProviderFactory")
    @patch("glob.glob")
    @patch("os.path.exists")
    def test_incremental_analysis_with_cache(
        self,
        mock_exists,
        mock_glob,
        mock_factory,
        mock_get_logger,
        config_manager,
        analysis_db,
        metadata_db,
        test_images,
        temp_dir,
    ):
        """Test incremental analysis with caching"""
        # Arrange
        mock_exists.return_value = True
        mock_glob.side_effect = lambda pattern: (
            test_images if "*.png" in pattern and "*.PNG" not in pattern else []
        )
        mock_get_logger.return_value = MagicMock()

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.provider_name = "ollama"
        mock_provider.analyze_images.return_value = {
            "success": True,
            "response": '{"company": "TestCo"}',
            "metadata": {"company": "TestCo"},
            "processing_time_ms": 100,
            "model_used": "qwen2.5-vl",
        }
        mock_factory.create_from_config_manager.return_value = mock_provider

        analysis_db.get_active_directories = MagicMock(return_value=[temp_dir])

        # Create service
        service = AnalysisService(config_manager, analysis_db, metadata_db)

        # Act - First analysis
        stats1 = service.scan_all_directories(incremental=False)

        # Act - Second analysis with cache
        stats2 = service.scan_all_directories(incremental=True)

        # Assert
        assert stats1["analyzed"] == 3
        assert stats1["cached"] == 0
        assert stats2["analyzed"] == 0
        assert stats2["cached"] == 3

    @patch("os.makedirs")
    @patch("os.path.exists")
    def test_file_service_initialization_creates_directories(
        self, mock_exists, mock_makedirs, config_manager, temp_dir
    ):
        """Test that FileService creates required directories"""
        # Arrange
        mock_exists.return_value = False

        # Act
        FileService(config_manager)

        # Assert
        assert mock_makedirs.call_count == 2
        calls = [call[0][0] for call in mock_makedirs.call_args_list]
        # Check that both the scan folder (temp_dir) and organized folder were created
        assert temp_dir in calls
        expected_organized = os.path.join(temp_dir, "organized")
        assert expected_organized in calls

    def test_database_integration(self, analysis_db, metadata_db, test_images):
        """Test AnalysisDB and MetadataDB working together"""
        # Arrange
        file_path = test_images[0]
        metadata = {"company": "TestCo", "document_type": "invoice"}

        # Act - Save to both databases
        file_hash = metadata_db.compute_file_hash(file_path)
        analysis_db.save_analysis(
            file_path=file_path,
            file_hash=file_hash,
            provider_name="ollama",
            model_name="qwen2.5-vl",
            analysis_data=metadata,
            raw_response="{}",
            processing_time_ms=100,
        )
        metadata_db.save_metadata(
            file_path=file_path,
            metadata=metadata,
            model_used="qwen2.5-vl",
            processing_time_ms=100,
        )

        # Assert - Retrieve from both databases
        analysis = analysis_db.get_analysis(file_path)
        metadata_result = metadata_db.get_metadata(file_path)

        assert analysis is not None
        assert analysis["file_hash"] == file_hash
        assert metadata_result is not None
        assert metadata_result["company"] == "TestCo"

    @patch("services.analysis_service.get_logger")
    @patch("services.analysis_service.ProviderFactory")
    def test_error_handling_in_workflow(
        self,
        mock_factory,
        mock_get_logger,
        config_manager,
        analysis_db,
        metadata_db,
        test_images,
    ):
        """Test error handling throughout the workflow"""
        # Arrange
        mock_get_logger.return_value = MagicMock()

        # Mock provider that fails on second image
        mock_provider = MagicMock()
        mock_provider.provider_name = "ollama"
        mock_provider.analyze_images.side_effect = [
            {
                "success": True,
                "response": "{}",
                "metadata": {},
                "processing_time_ms": 100,
                "model_used": "qwen2.5-vl",
            },
            {
                "success": False,
                "error": "Analysis failed",
                "response": "",
                "metadata": {},
                "processing_time_ms": 50,
                "model_used": "qwen2.5-vl",
            },
            {
                "success": True,
                "response": "{}",
                "metadata": {},
                "processing_time_ms": 100,
                "model_used": "qwen2.5-vl",
            },
        ]
        mock_factory.create_from_config_manager.return_value = mock_provider

        # Create service
        service = AnalysisService(config_manager, analysis_db, metadata_db)

        # Act
        stats = service.analyze_specific_files(test_images)

        # Assert
        assert stats["total_files"] == 3
        assert stats["analyzed"] == 2
        assert stats["errors"] == 1
