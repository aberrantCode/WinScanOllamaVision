"""
Comprehensive tests for AnalysisService.

Tests analysis orchestration, caching, error handling, and run tracking.
"""

from unittest.mock import MagicMock, patch

import pytest

from services.analysis_service import AnalysisService


# Mock get_logger at module level to avoid LoggingService initialization
@pytest.fixture(autouse=True)
def mock_get_logger():
    with patch("services.analysis_service.get_logger") as mock:
        mock.return_value = MagicMock()
        yield mock


class TestAnalysisServiceInitialization:
    """Tests for AnalysisService initialization"""

    @pytest.fixture
    def mock_config(self):
        return MagicMock()

    @pytest.fixture
    def mock_analysis_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_metadata_db(self):
        return MagicMock()

    def test_init_stores_dependencies(self, mock_config, mock_analysis_db, mock_metadata_db):
        # Act
        service = AnalysisService(mock_config, mock_analysis_db, mock_metadata_db)

        # Assert
        assert service.config is mock_config
        assert service.analysis_db is mock_analysis_db
        assert service.metadata_db is mock_metadata_db

    def test_init_provider_is_none(self, mock_config, mock_analysis_db, mock_metadata_db):
        # Act
        service = AnalysisService(mock_config, mock_analysis_db, mock_metadata_db)

        # Assert
        assert service.provider is None

    def test_init_gets_logger(
        self, mock_get_logger, mock_config, mock_analysis_db, mock_metadata_db
    ):
        # Arrange
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Act
        service = AnalysisService(mock_config, mock_analysis_db, mock_metadata_db)

        # Assert
        assert service.logger is not None


class TestGetProvider:
    """Tests for _get_provider method"""

    @pytest.fixture
    def mock_config(self):
        return MagicMock()

    @pytest.fixture
    def mock_analysis_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_metadata_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_config, mock_analysis_db, mock_metadata_db):
        return AnalysisService(mock_config, mock_analysis_db, mock_metadata_db)

    @patch("services.analysis_service.ProviderFactory")
    def test_get_provider_creates_provider_on_first_call(self, mock_factory, service, mock_config):
        # Arrange
        mock_provider = MagicMock()
        mock_factory.create_from_config_manager.return_value = mock_provider

        # Act
        result = service._get_provider()

        # Assert
        mock_factory.create_from_config_manager.assert_called_once_with(mock_config)
        assert result is mock_provider
        assert service.provider is mock_provider

    @patch("services.analysis_service.ProviderFactory")
    def test_get_provider_returns_cached_provider(self, mock_factory, service, mock_config):
        # Arrange
        mock_provider = MagicMock()
        service.provider = mock_provider

        # Act
        result = service._get_provider()

        # Assert
        mock_factory.create_from_config_manager.assert_not_called()
        assert result is mock_provider


class TestScanAllDirectories:
    """Tests for scan_all_directories method"""

    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.get_bool.return_value = True
        config.get_int.return_value = 10
        config.get_setting.return_value = "C:\\test\\scan"
        return config

    @pytest.fixture
    def mock_analysis_db(self):
        db = MagicMock()
        db.get_active_directories.return_value = []
        return db

    @pytest.fixture
    def mock_metadata_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_config, mock_analysis_db, mock_metadata_db):
        return AnalysisService(mock_config, mock_analysis_db, mock_metadata_db)

    def test_scan_returns_disabled_when_auto_analysis_disabled(self, service, mock_config):
        # Arrange
        mock_config.get_bool.return_value = False

        # Act
        result = service.scan_all_directories()

        # Assert
        assert result["total_files"] == 0
        assert result["analyzed"] == 0
        assert result["message"] == "Auto-analysis disabled in settings"
        mock_config.get_bool.assert_called_once_with("AutoAnalysis", "enabled", True)

    @patch("os.path.exists")
    def test_scan_uses_active_directories_from_db(self, mock_exists, service, mock_analysis_db):
        # Arrange
        mock_exists.return_value = True
        mock_analysis_db.get_active_directories.return_value = [
            "C:\\dir1",
            "C:\\dir2",
        ]

        with patch("glob.glob", return_value=[]):
            # Act
            result = service.scan_all_directories()

            # Assert
            assert result["total_files"] == 0

    def test_scan_returns_no_directories_when_none_configured(self, service, mock_analysis_db):
        # Arrange
        mock_analysis_db.get_active_directories.return_value = []

        # Act
        result = service.scan_all_directories()

        # Assert
        assert result["total_files"] == 0
        assert result["message"] == "No source directories configured"

    @patch("glob.glob")
    @patch("os.path.exists")
    def test_scan_processes_all_files_from_multiple_directories(
        self,
        mock_exists,
        mock_glob,
        service,
        mock_analysis_db,
    ):
        # Arrange
        mock_exists.return_value = True
        mock_analysis_db.get_active_directories.return_value = ["C:\\dir1", "C:\\dir2"]

        def glob_side_effect(pattern):
            # Normalize path separators for cross-platform testing
            pattern_normalized = pattern.replace("\\", "/")
            return {
                "C:/dir1/*.png": ["file1.png"],
                "C:/dir2/*.png": ["file2.png"],
            }.get(pattern_normalized, [])

        mock_glob.side_effect = glob_side_effect

        with patch.object(service, "_analyze_single_page") as mock_analyze:
            mock_analyze.return_value = {"success": True, "cached": False, "skipped": False}

            # Act
            result = service.scan_all_directories()

            # Assert
            assert result["total_files"] == 2
            assert mock_analyze.call_count == 2

    @patch("glob.glob")
    @patch("os.path.exists")
    def test_scan_collects_all_image_files(self, mock_exists, mock_glob, service, mock_analysis_db):
        # Arrange
        mock_exists.return_value = True
        mock_analysis_db.get_active_directories.return_value = ["C:\\dir1"]

        def glob_side_effect(pattern):
            # Normalize path separators for cross-platform testing
            pattern_normalized = pattern.replace("\\", "/")
            return {
                "C:/dir1/*.png": ["file1.png", "file2.png"],
                "C:/dir1/*.PNG": [],
                "C:/dir1/*.jpg": ["file3.jpg"],
                "C:/dir1/*.JPG": [],
                "C:/dir1/*.jpeg": [],
                "C:/dir1/*.JPEG": [],
            }.get(pattern_normalized, [])

        mock_glob.side_effect = glob_side_effect

        with patch.object(service, "_analyze_single_page") as mock_analyze:
            mock_analyze.return_value = {"success": True, "cached": False, "skipped": False}

            # Act
            result = service.scan_all_directories()

            # Assert
            assert result["total_files"] == 3
            assert mock_analyze.call_count == 3

    @patch("glob.glob")
    @patch("os.path.exists")
    def test_scan_calls_progress_callback(self, mock_exists, mock_glob, service, mock_analysis_db):
        # Arrange
        mock_exists.return_value = True
        mock_analysis_db.get_active_directories.return_value = ["C:\\dir1"]
        mock_glob.side_effect = lambda pattern: (
            ["file1.png"] if "*.png" in pattern and "*.PNG" not in pattern else []
        )

        progress_callback = MagicMock()

        with patch.object(service, "_analyze_single_page") as mock_analyze:
            mock_analyze.return_value = {"success": True, "cached": False, "skipped": False}

            # Act
            service.scan_all_directories(progress_callback=progress_callback)

            # Assert
            progress_callback.assert_called_once()
            call_args = progress_callback.call_args
            assert "file1.png" in call_args[0][0]
            assert call_args[0][1] == 1
            assert call_args[0][2] == 1

    @patch("glob.glob")
    @patch("os.path.exists")
    def test_scan_tracks_cached_files(self, mock_exists, mock_glob, service, mock_analysis_db):
        # Arrange
        mock_exists.return_value = True
        mock_analysis_db.get_active_directories.return_value = ["C:\\dir1"]
        mock_glob.side_effect = lambda pattern: (
            ["file1.png", "file2.png"] if "*.png" in pattern and "*.PNG" not in pattern else []
        )

        with patch.object(service, "_analyze_single_page") as mock_analyze:
            mock_analyze.side_effect = [
                {"success": True, "cached": True, "skipped": False},
                {"success": True, "cached": False, "skipped": False},
            ]

            # Act
            result = service.scan_all_directories()

            # Assert
            assert result["cached"] == 1
            assert result["analyzed"] == 1

    @patch("glob.glob")
    @patch("os.path.exists")
    def test_scan_tracks_errors(self, mock_exists, mock_glob, service, mock_analysis_db):
        # Arrange
        mock_exists.return_value = True
        mock_analysis_db.get_active_directories.return_value = ["C:\\dir1"]
        mock_glob.side_effect = lambda pattern: (
            ["file1.png"] if "*.png" in pattern and "*.PNG" not in pattern else []
        )

        with patch.object(service, "_analyze_single_page") as mock_analyze:
            mock_analyze.return_value = {
                "success": False,
                "cached": False,
                "skipped": False,
                "error": "Test error",
            }

            # Act
            result = service.scan_all_directories()

            # Assert
            assert result["errors"] == 1
            mock_analysis_db.save_error.assert_called_once()

    @patch("glob.glob")
    @patch("os.path.exists")
    def test_scan_error_event_carries_traceback_and_provider_context(
        self, mock_exists, mock_glob, service, mock_analysis_db
    ):
        """A failed file's status event must forward the traceback + provider
        context so the history UI shows something actionable, not a bare line.
        """
        mock_exists.return_value = True
        mock_analysis_db.get_active_directories.return_value = ["C:\\dir1"]
        mock_glob.side_effect = lambda pattern: (
            ["file1.png"] if "*.png" in pattern and "*.PNG" not in pattern else []
        )

        with (
            patch.object(service, "_analyze_single_page") as mock_analyze,
            patch("services.analysis_service.get_reporter") as mock_get_reporter,
        ):
            reporter = MagicMock()
            mock_get_reporter.return_value = reporter
            mock_analyze.return_value = {
                "success": False,
                "cached": False,
                "skipped": False,
                "error": "boom",
                "error_type": "exception",
                "provider": "claude_cli",
                "model": "sonnet",
                "traceback": "Traceback (most recent call last):\n  RuntimeError: boom",
            }

            # Act
            service.scan_all_directories()

            # Assert — the enriched fields reached reporter.error(...)
            reporter.error.assert_called_once()
            _, kwargs = reporter.error.call_args
            assert kwargs["traceback"].startswith("Traceback")
            assert kwargs["context"]["provider"] == "claude_cli"
            assert kwargs["context"]["model"] == "sonnet"
            assert kwargs["context"]["error_type"] == "exception"
            assert kwargs["context"]["job_type"] == "SCAN_ALL"

    @patch("glob.glob")
    @patch("os.path.exists")
    def test_scan_tracks_skipped_files(self, mock_exists, mock_glob, service, mock_analysis_db):
        # Arrange
        mock_exists.return_value = True
        mock_analysis_db.get_active_directories.return_value = ["C:\\dir1"]
        mock_glob.side_effect = lambda pattern: (
            ["file1.png"] if "*.png" in pattern and "*.PNG" not in pattern else []
        )

        with patch.object(service, "_analyze_single_page") as mock_analyze:
            mock_analyze.return_value = {
                "success": False,
                "cached": False,
                "skipped": True,
            }

            # Act
            result = service.scan_all_directories()

            # Assert
            assert result["skipped"] == 1

    @patch("glob.glob")
    @patch("os.path.exists")
    def test_scan_updates_directory_scan_info(
        self, mock_exists, mock_glob, service, mock_analysis_db
    ):
        # Arrange
        mock_exists.return_value = True
        mock_analysis_db.get_active_directories.return_value = ["C:\\dir1"]
        mock_glob.side_effect = lambda pattern: (
            ["file1.png", "file2.png"] if "*.png" in pattern and "*.PNG" not in pattern else []
        )

        with patch.object(service, "_analyze_single_page") as mock_analyze:
            mock_analyze.return_value = {"success": True, "cached": False, "skipped": False}

            # Act
            service.scan_all_directories()

            # Assert
            mock_analysis_db.update_directory_scan_info.assert_called_once_with("C:\\dir1", 2)

    @patch("glob.glob")
    @patch("os.path.exists")
    def test_scan_completes_successfully_with_valid_files(
        self, mock_exists, mock_glob, service, mock_analysis_db
    ):
        # Arrange
        mock_exists.return_value = True
        mock_analysis_db.get_active_directories.return_value = ["C:\\dir1"]
        mock_glob.side_effect = lambda pattern: (
            ["file1.png"] if "*.png" in pattern and "*.PNG" not in pattern else []
        )

        with patch.object(service, "_analyze_single_page") as mock_analyze:
            mock_analyze.return_value = {"success": True, "cached": False, "skipped": False}

            # Act
            result = service.scan_all_directories()

            # Assert
            assert result["analyzed"] == 1
            assert result["errors"] == 0

    @patch("glob.glob")
    @patch("os.path.exists")
    def test_scan_handles_abort_check(self, mock_exists, mock_glob, service, mock_analysis_db):
        # Arrange
        mock_exists.return_value = True
        mock_analysis_db.get_active_directories.return_value = ["C:\\dir1"]
        mock_glob.side_effect = lambda pattern: (
            ["file1.png"] if "*.png" in pattern and "*.PNG" not in pattern else []
        )

        abort_check = MagicMock(return_value=True)

        with patch.object(service, "_analyze_single_page") as mock_analyze:
            mock_analyze.return_value = {"success": True, "cached": False, "skipped": False}

            # Act & Assert - scan should raise InterruptedError when aborted
            with pytest.raises(InterruptedError, match="Analysis aborted by user"):
                service.scan_all_directories(abort_check=abort_check)

    @patch("glob.glob")
    @patch("os.path.exists")
    def test_scan_uses_incremental_flag(self, mock_exists, mock_glob, service, mock_analysis_db):
        # Arrange
        mock_exists.return_value = True
        mock_analysis_db.get_active_directories.return_value = ["C:\\dir1"]
        mock_glob.side_effect = lambda pattern: (
            ["file1.png"] if "*.png" in pattern and "*.PNG" not in pattern else []
        )

        with patch.object(service, "_analyze_single_page") as mock_analyze:
            mock_analyze.return_value = {"success": True, "cached": False, "skipped": False}

            # Act
            service.scan_all_directories(incremental=False)

            # Assert
            mock_analyze.assert_called_once()
            call_args = mock_analyze.call_args
            # Check the second positional argument (incremental)
            assert call_args[0][1] is False


class TestAnalyzeSinglePage:
    """Tests for _analyze_single_page method"""

    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.get_setting.return_value = "Test prompt"
        return config

    @pytest.fixture
    def mock_analysis_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_metadata_db(self):
        db = MagicMock()
        db.compute_file_hash.return_value = "hash123"
        return db

    @pytest.fixture
    def service(self, mock_config, mock_analysis_db, mock_metadata_db):
        return AnalysisService(mock_config, mock_analysis_db, mock_metadata_db)

    def test_analyze_single_page_computes_file_hash(self, service, mock_metadata_db):
        # Arrange
        image_path = "C:\\test\\file1.png"
        mock_metadata_db.compute_file_hash.return_value = "hash123"

        with patch.object(service, "_get_provider"):
            # Act
            service._analyze_single_page(image_path)

            # Assert
            mock_metadata_db.compute_file_hash.assert_called_once_with(image_path)

    def test_analyze_single_page_returns_cached_when_hash_matches(
        self, service, mock_analysis_db, mock_metadata_db
    ):
        # Arrange
        image_path = "C:\\test\\file1.png"
        mock_metadata_db.compute_file_hash.return_value = "hash123"
        mock_analysis_db.get_analysis.return_value = {
            "file_hash": "hash123",
            "metadata": {"test": "data"},
        }

        # Act
        result = service._analyze_single_page(image_path, incremental=True)

        # Assert
        assert result["success"] is True
        assert result["cached"] is True
        assert result["skipped"] is False

    def test_analyze_single_page_skips_cache_when_not_incremental(self, service, mock_analysis_db):
        # Arrange
        image_path = "C:\\test\\file1.png"
        mock_analysis_db.get_analysis.return_value = {"file_hash": "hash123"}

        with patch.object(service, "_get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.provider_name = "test_provider"
            mock_provider.analyze_images.return_value = {
                "success": True,
                "metadata": {},
                "response": "test",
                "processing_time_ms": 100,
                "model_used": "test_model",
            }
            mock_get_provider.return_value = mock_provider

            # Act
            result = service._analyze_single_page(image_path, incremental=False)

            # Assert
            assert result["cached"] is False
            mock_provider.analyze_images.assert_called_once()

    def test_analyze_single_page_calls_provider_with_prompt(self, service, mock_config):
        # Arrange
        image_path = "C:\\test\\file1.png"
        mock_config.get_setting.return_value = "Custom prompt"

        with patch.object(service, "_get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.provider_name = "test_provider"
            mock_provider.analyze_images.return_value = {
                "success": True,
                "metadata": {},
                "response": "test",
                "processing_time_ms": 100,
                "model_used": "test_model",
            }
            mock_get_provider.return_value = mock_provider

            # Act
            service._analyze_single_page(image_path)

            # Assert
            mock_provider.analyze_images.assert_called_once()
            call_args = mock_provider.analyze_images.call_args
            assert call_args.kwargs["prompt"] == "Custom prompt"

    def test_analyze_single_page_uses_fallback_prompt_when_not_configured(
        self, service, mock_config
    ):
        # Arrange
        image_path = "C:\\test\\file1.png"
        mock_config.get_setting.return_value = None

        with patch.object(service, "_get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.provider_name = "test_provider"
            mock_provider.analyze_images.return_value = {
                "success": True,
                "metadata": {},
                "response": "test",
                "processing_time_ms": 100,
                "model_used": "test_model",
            }
            mock_get_provider.return_value = mock_provider

            # Act
            service._analyze_single_page(image_path)

            # Assert
            call_args = mock_provider.analyze_images.call_args
            assert "Analyze this document" in call_args.kwargs["prompt"]

    def test_analyze_single_page_saves_to_both_databases(
        self, service, mock_analysis_db, mock_metadata_db
    ):
        # Arrange
        image_path = "C:\\test\\file1.png"

        with patch.object(service, "_get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.provider_name = "test_provider"
            mock_provider.analyze_images.return_value = {
                "success": True,
                "metadata": {"test": "data"},
                "response": "test response",
                "processing_time_ms": 100,
                "model_used": "test_model",
            }
            mock_get_provider.return_value = mock_provider

            # Act
            service._analyze_single_page(image_path)

            # Assert
            mock_analysis_db.save_analysis.assert_called_once()
            mock_metadata_db.save_metadata.assert_called_once()

    def test_analyze_single_page_returns_error_when_provider_fails(self, service):
        # Arrange
        image_path = "C:\\test\\file1.png"

        with patch.object(service, "_get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.analyze_images.return_value = {
                "success": False,
                "error": "Provider error",
            }
            mock_get_provider.return_value = mock_provider

            # Act
            result = service._analyze_single_page(image_path)

            # Assert
            assert result["success"] is False
            assert result["error"] == "Provider error"

    def test_analyze_single_page_handles_exception(self, service):
        # Arrange
        image_path = "C:\\test\\file1.png"

        with patch.object(service, "_get_provider") as mock_get_provider:
            mock_get_provider.side_effect = Exception("Test exception")

            # Act
            result = service._analyze_single_page(image_path)

            # Assert
            assert result["success"] is False
            assert "Test exception" in result["error"]

    def test_analyze_single_page_provider_failure_includes_context(self, service):
        """A provider-reported failure should carry provider/model/error_type."""
        image_path = "C:\\test\\file1.png"

        with patch.object(service, "_get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.provider_name = "claude_cli"
            mock_provider.analyze_images.return_value = {
                "success": False,
                "error": "Provider error",
                "model_used": "sonnet",
            }
            mock_get_provider.return_value = mock_provider

            # Act
            result = service._analyze_single_page(image_path)

            # Assert
            assert result["error_type"] == "provider_error"
            assert result["provider"] == "claude_cli"
            assert result["model"] == "sonnet"

    def test_analyze_single_page_exception_includes_traceback(self, service):
        """An exception mid-analysis must surface the traceback + provider."""
        image_path = "C:\\test\\file1.png"

        with patch.object(service, "_get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.provider_name = "ollama"
            mock_provider.analyze_images.side_effect = RuntimeError("kaboom")
            mock_get_provider.return_value = mock_provider

            # Act
            result = service._analyze_single_page(image_path)

            # Assert
            assert result["error_type"] == "exception"
            assert "kaboom" in result["error"]
            assert result["provider"] == "ollama"
            assert "Traceback" in result["traceback"]
            assert "kaboom" in result["traceback"]

    def test_analyze_single_page_calls_save_failed_analysis_when_provider_fails(
        self, service, mock_analysis_db, mock_metadata_db
    ):
        """Test save_failed_analysis is called when provider returns failure (line 368-376)."""
        # Arrange
        image_path = "C:\\test\\file1.png"
        file_hash = "hash123"
        mock_metadata_db.compute_file_hash.return_value = file_hash

        with patch.object(service, "_get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.provider_name = "claude_cli"
            mock_provider.analyze_images.return_value = {
                "success": False,
                "error": "API rate limit",
                "model_used": "sonnet",
                "processing_time_ms": 2000,
            }
            mock_get_provider.return_value = mock_provider

            # Act
            service._analyze_single_page(image_path)

            # Assert - save_failed_analysis called once with correct args
            mock_analysis_db.save_failed_analysis.assert_called_once()
            call_kwargs = mock_analysis_db.save_failed_analysis.call_args.kwargs
            assert call_kwargs["file_path"] == image_path
            assert call_kwargs["file_hash"] == file_hash
            assert call_kwargs["provider_name"] == "claude_cli"
            assert call_kwargs["model_name"] == "sonnet"
            assert call_kwargs["error_message"] == "API rate limit"
            assert call_kwargs["processing_time_ms"] == 2000

    def test_analyze_single_page_calls_save_failed_analysis_when_exception_after_prompt(
        self, service, mock_analysis_db, mock_metadata_db, mock_config
    ):
        """Test save_failed_analysis is called when provider.analyze_images raises exception (after prompt fetch)."""
        # Arrange
        image_path = "C:\\test\\file1.png"
        file_hash = "hash123"
        mock_metadata_db.compute_file_hash.return_value = file_hash
        mock_config.get_setting.return_value = "Custom analyze prompt"

        with patch.object(service, "_get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.provider_name = "ollama"
            # Exception happens during analyze_images call (after prompt was fetched)
            mock_provider.analyze_images.side_effect = RuntimeError("Connection failed")
            mock_get_provider.return_value = mock_provider

            # Act
            service._analyze_single_page(image_path)

            # Assert - save_failed_analysis called with prompt_text set (not None)
            mock_analysis_db.save_failed_analysis.assert_called_once()
            call_kwargs = mock_analysis_db.save_failed_analysis.call_args.kwargs
            assert call_kwargs["file_path"] == image_path
            assert call_kwargs["file_hash"] == file_hash
            assert call_kwargs["provider_name"] == "ollama"
            assert call_kwargs["error_message"] == "Connection failed"
            assert call_kwargs["prompt_text"] == "Custom analyze prompt", (
                "prompt_text should be set when exception occurs after prompt fetch"
            )

    def test_analyze_single_page_calls_save_failed_analysis_when_exception_before_prompt(
        self, service, mock_analysis_db, mock_metadata_db
    ):
        """Test save_failed_analysis is called when _get_provider raises exception (before prompt fetch)."""
        # Arrange
        image_path = "C:\\test\\file1.png"
        file_hash = "hash123"
        mock_metadata_db.compute_file_hash.return_value = file_hash

        with patch.object(service, "_get_provider") as mock_get_provider:
            # Exception happens during _get_provider call (before prompt is fetched)
            mock_get_provider.side_effect = RuntimeError("Provider not configured")

            # Act
            service._analyze_single_page(image_path)

            # Assert - save_failed_analysis called with provider_name/prompt_text as None
            mock_analysis_db.save_failed_analysis.assert_called_once()
            call_kwargs = mock_analysis_db.save_failed_analysis.call_args.kwargs
            assert call_kwargs["file_path"] == image_path
            assert call_kwargs["file_hash"] == file_hash
            assert call_kwargs["provider_name"] is None
            assert call_kwargs["model_name"] is None
            assert call_kwargs["prompt_text"] is None
            assert call_kwargs["error_message"] == "Provider not configured"

    def test_analyze_single_page_does_not_call_save_failed_analysis_on_success(
        self, service, mock_analysis_db, mock_metadata_db
    ):
        """Test save_failed_analysis is NOT called on success path (line 413-418)."""
        # Arrange
        image_path = "C:\\test\\file1.png"

        with patch.object(service, "_get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.provider_name = "ollama"
            mock_provider.analyze_images.return_value = {
                "success": True,
                "metadata": {"company": "Test Corp"},
                "response": "{}",
                "processing_time_ms": 100,
                "model_used": "test-model",
            }
            mock_get_provider.return_value = mock_provider

            # Act
            result = service._analyze_single_page(image_path)

            # Assert
            assert result["success"] is True
            # save_failed_analysis should NOT be called
            mock_analysis_db.save_failed_analysis.assert_not_called()
            # save_analysis SHOULD be called instead
            mock_analysis_db.save_analysis.assert_called_once()


class TestAnalyzeSpecificFiles:
    """Tests for analyze_specific_files method"""

    @pytest.fixture
    def mock_config(self):
        return MagicMock()

    @pytest.fixture
    def mock_analysis_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_metadata_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_config, mock_analysis_db, mock_metadata_db):
        return AnalysisService(mock_config, mock_analysis_db, mock_metadata_db)

    def test_analyze_specific_files_processes_all_files(self, service):
        # Arrange
        file_paths = ["file1.png", "file2.png", "file3.png"]

        with patch.object(service, "_analyze_single_page") as mock_analyze:
            mock_analyze.return_value = {"success": True, "cached": False, "skipped": False}

            # Act
            result = service.analyze_specific_files(file_paths)

            # Assert
            assert result["total_files"] == 3
            assert mock_analyze.call_count == 3

    def test_analyze_specific_files_calls_progress_callback(self, service):
        # Arrange
        file_paths = ["file1.png"]
        progress_callback = MagicMock()

        with patch.object(service, "_analyze_single_page") as mock_analyze:
            mock_analyze.return_value = {"success": True, "cached": False, "skipped": False}

            # Act
            service.analyze_specific_files(file_paths, progress_callback=progress_callback)

            # Assert
            progress_callback.assert_called_once()

    def test_analyze_specific_files_forces_reanalysis_when_requested(self, service):
        # Arrange
        file_paths = ["file1.png"]

        with patch.object(service, "_analyze_single_page") as mock_analyze:
            mock_analyze.return_value = {"success": True, "cached": False, "skipped": False}

            # Act
            service.analyze_specific_files(file_paths, force_reanalysis=True)

            # Assert
            mock_analyze.assert_called_once()
            call_args = mock_analyze.call_args
            assert call_args.kwargs["incremental"] is False

    def test_analyze_specific_files_tracks_stats(self, service):
        # Arrange
        file_paths = ["file1.png", "file2.png", "file3.png"]

        with patch.object(service, "_analyze_single_page") as mock_analyze:
            mock_analyze.side_effect = [
                {"success": True, "cached": True, "skipped": False},
                {"success": True, "cached": False, "skipped": False},
                {"success": False, "cached": False, "skipped": False, "error": "Error"},
            ]

            # Act
            result = service.analyze_specific_files(file_paths)

            # Assert
            assert result["total_files"] == 3
            assert result["cached"] == 1
            assert result["analyzed"] == 1
            assert result["errors"] == 1


class TestGetAnalysisForFiles:
    """Tests for get_analysis_for_files method"""

    @pytest.fixture
    def mock_config(self):
        return MagicMock()

    @pytest.fixture
    def mock_analysis_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_metadata_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_config, mock_analysis_db, mock_metadata_db):
        return AnalysisService(mock_config, mock_analysis_db, mock_metadata_db)

    def test_get_analysis_for_files_returns_all_found_analyses(self, service, mock_analysis_db):
        # Arrange
        file_paths = ["file1.png", "file2.png", "file3.png"]
        mock_analysis_db.get_analysis.side_effect = [
            {"metadata": {"test": "1"}},
            None,
            {"metadata": {"test": "3"}},
        ]

        # Act
        result = service.get_analysis_for_files(file_paths)

        # Assert
        assert len(result) == 2
        assert result[0]["metadata"]["test"] == "1"
        assert result[1]["metadata"]["test"] == "3"

    def test_get_analysis_for_files_returns_empty_when_none_found(self, service, mock_analysis_db):
        # Arrange
        file_paths = ["file1.png"]
        mock_analysis_db.get_analysis.return_value = None

        # Act
        result = service.get_analysis_for_files(file_paths)

        # Assert
        assert result == []


class TestLogging:
    """Tests for _log method"""

    @pytest.fixture
    def mock_config(self):
        return MagicMock()

    @pytest.fixture
    def mock_analysis_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_metadata_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_config, mock_analysis_db, mock_metadata_db):
        service = AnalysisService(mock_config, mock_analysis_db, mock_metadata_db)
        service.logger = MagicMock()
        return service

    def test_log_calls_logger_info(self, service):
        # Act
        service._log("Test message")

        # Assert
        service.logger.info.assert_called_once_with("Test message")

    @patch("builtins.print")
    def test_log_falls_back_to_print_on_error(self, mock_print, service):
        # Arrange
        service.logger.info.side_effect = Exception("Logger error")

        # Act
        service._log("Test message")

        # Assert
        mock_print.assert_called_once_with("Test message")


class TestTaxRelatedFeature:
    """Tests for tax_related field integration"""

    def test_default_analysis_prompt_contains_tax_related(self):
        # Act
        prompt = AnalysisService.DEFAULT_ANALYSIS_PROMPT

        # Assert
        assert "tax_related" in prompt
        assert "true/false" in prompt.lower()
        assert "W-2" in prompt or "1099" in prompt

    def test_default_analysis_prompt_has_tax_examples(self):
        # Act
        prompt = AnalysisService.DEFAULT_ANALYSIS_PROMPT

        # Assert - check for tax document examples
        tax_keywords = ["W-2", "1099", "tax return", "property tax", "IRS", "deductible"]
        found_keywords = [keyword for keyword in tax_keywords if keyword in prompt]
        assert len(found_keywords) >= 3, (
            f"Expected at least 3 tax keywords, found: {found_keywords}"
        )

    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.get_setting.return_value = AnalysisService.DEFAULT_ANALYSIS_PROMPT
        return config

    @pytest.fixture
    def mock_analysis_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_metadata_db(self):
        db = MagicMock()
        db.compute_file_hash.return_value = "hash123"
        return db

    @pytest.fixture
    def service(self, mock_config, mock_analysis_db, mock_metadata_db):
        return AnalysisService(mock_config, mock_analysis_db, mock_metadata_db)

    def test_analysis_saves_tax_related_true(self, service, mock_analysis_db, mock_metadata_db):
        # Arrange
        image_path = "C:\\test\\tax_doc.jpg"

        with patch.object(service, "_get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.provider_name = "test_provider"
            mock_provider.analyze_images.return_value = {
                "success": True,
                "metadata": {
                    "document_type": "W-2",
                    "company": "Test Corp",
                    "tax_related": True,
                    "confidence_score": 0.95,
                },
                "response": "test response",
                "processing_time_ms": 100,
                "model_used": "test_model",
            }
            mock_get_provider.return_value = mock_provider

            # Act
            result = service._analyze_single_page(image_path)

            # Assert
            assert result["success"] is True
            assert result["analysis"]["tax_related"] is True
            # Verify it was saved to both databases
            mock_analysis_db.save_analysis.assert_called_once()
            call_args = mock_analysis_db.save_analysis.call_args
            assert call_args.kwargs["analysis_data"]["tax_related"] is True

    def test_analysis_saves_tax_related_false(self, service, mock_analysis_db, mock_metadata_db):
        # Arrange
        image_path = "C:\\test\\receipt.jpg"

        with patch.object(service, "_get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.provider_name = "test_provider"
            mock_provider.analyze_images.return_value = {
                "success": True,
                "metadata": {
                    "document_type": "Receipt",
                    "company": "Coffee Shop",
                    "tax_related": False,
                    "confidence_score": 0.90,
                },
                "response": "test response",
                "processing_time_ms": 100,
                "model_used": "test_model",
            }
            mock_get_provider.return_value = mock_provider

            # Act
            result = service._analyze_single_page(image_path)

            # Assert
            assert result["success"] is True
            assert result["analysis"]["tax_related"] is False
            mock_metadata_db.save_metadata.assert_called_once()
            call_args = mock_metadata_db.save_metadata.call_args
            # Access metadata from kwargs - save_metadata(file_path=..., metadata=..., ...)
            assert call_args.kwargs["metadata"]["tax_related"] is False

    def test_analysis_handles_missing_tax_related_field(
        self, service, mock_analysis_db, mock_metadata_db
    ):
        # Arrange - simulate legacy response without tax_related field
        image_path = "C:\\test\\legacy_doc.jpg"

        with patch.object(service, "_get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.provider_name = "test_provider"
            mock_provider.analyze_images.return_value = {
                "success": True,
                "metadata": {
                    "document_type": "Letter",
                    "company": "Old Corp",
                    # tax_related field intentionally omitted
                },
                "response": "test response",
                "processing_time_ms": 100,
                "model_used": "test_model",
            }
            mock_get_provider.return_value = mock_provider

            # Act
            result = service._analyze_single_page(image_path)

            # Assert - should still succeed
            assert result["success"] is True
            # Verify metadata was saved (database will default tax_related to False)
            mock_analysis_db.save_analysis.assert_called_once()
            mock_metadata_db.save_metadata.assert_called_once()

    @patch("glob.glob")
    @patch("os.path.exists")
    def test_scan_directories_preserves_tax_related_in_flow(
        self, mock_exists, mock_glob, service, mock_analysis_db
    ):
        # Arrange
        mock_exists.return_value = True
        mock_analysis_db.get_active_directories.return_value = ["C:\\dir1"]
        mock_glob.side_effect = lambda pattern: (
            ["tax_doc.jpg"] if "*.jpg" in pattern and "*.JPG" not in pattern else []
        )

        with patch.object(service, "_get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.provider_name = "ollama"
            mock_provider.analyze_images.return_value = {
                "success": True,
                "metadata": {
                    "document_type": "1099-MISC",
                    "company": "Contractor LLC",
                    "tax_related": True,
                    "document_date": "2024-01-31",
                },
                "response": "Tax document analysis",
                "processing_time_ms": 150,
                "model_used": "qwen2.5-vl",
            }
            mock_get_provider.return_value = mock_provider

            # Act
            result = service.scan_all_directories()

            # Assert
            assert result["analyzed"] == 1
            assert result["errors"] == 0
            # Verify the analysis was saved with tax_related field
            mock_analysis_db.save_analysis.assert_called_once()
            call_args = mock_analysis_db.save_analysis.call_args
            assert "tax_related" in call_args.kwargs["analysis_data"]
            assert call_args.kwargs["analysis_data"]["tax_related"] is True


class TestEdgeCases:
    """Tests for edge cases and error conditions"""

    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.get_bool.return_value = True
        config.get_int.return_value = 10
        config.get_setting.return_value = "C:\\test\\scan"
        return config

    @pytest.fixture
    def mock_analysis_db(self):
        db = MagicMock()
        db.get_active_directories.return_value = []
        return db

    @pytest.fixture
    def mock_metadata_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_config, mock_analysis_db, mock_metadata_db):
        return AnalysisService(mock_config, mock_analysis_db, mock_metadata_db)

    @patch("glob.glob")
    @patch("os.path.exists")
    def test_scan_skips_nonexistent_directory(
        self, mock_exists, mock_glob, service, mock_analysis_db
    ):
        # Arrange
        mock_exists.side_effect = lambda path: path != "C:\\nonexistent"
        mock_analysis_db.get_active_directories.return_value = [
            "C:\\exists",
            "C:\\nonexistent",
        ]
        mock_glob.return_value = []

        # Act
        result = service.scan_all_directories()

        # Assert - should only process existing directory
        assert result["total_files"] == 0

    @patch("glob.glob")
    @patch("os.path.exists")
    def test_scan_handles_interrupted_error(
        self, mock_exists, mock_glob, service, mock_analysis_db
    ):
        # Arrange
        mock_exists.return_value = True
        mock_analysis_db.get_active_directories.return_value = ["C:\\dir1"]
        mock_glob.side_effect = lambda pattern: (
            ["file1.png"] if "*.png" in pattern and "*.PNG" not in pattern else []
        )

        with patch.object(service, "_analyze_single_page") as mock_analyze:
            mock_analyze.side_effect = InterruptedError("User cancelled")

            # Act & Assert
            with pytest.raises(InterruptedError):
                service.scan_all_directories()

    @patch("glob.glob")
    @patch("os.path.exists")
    def test_scan_handles_all_files_with_errors(
        self, mock_exists, mock_glob, service, mock_analysis_db
    ):
        # Arrange
        mock_exists.return_value = True
        mock_analysis_db.get_active_directories.return_value = ["C:\\dir1"]
        mock_glob.side_effect = lambda pattern: (
            ["file1.png", "file2.png"] if "*.png" in pattern and "*.PNG" not in pattern else []
        )

        with patch.object(service, "_analyze_single_page") as mock_analyze:
            mock_analyze.return_value = {
                "success": False,
                "cached": False,
                "skipped": False,
                "error": "All failed",
            }

            # Act
            result = service.scan_all_directories()

            # Assert
            assert result["errors"] == 2
            assert result["analyzed"] == 0
            # Verify errors were saved to database
            assert mock_analysis_db.save_error.call_count == 2

    @patch("glob.glob")
    @patch("os.path.exists")
    def test_scan_removes_duplicate_files_from_glob(
        self, mock_exists, mock_glob, service, mock_analysis_db
    ):
        # Arrange
        mock_exists.return_value = True
        mock_analysis_db.get_active_directories.return_value = ["C:\\dir1"]
        # Simulate duplicate files from different glob patterns
        mock_glob.side_effect = lambda pattern: ["file1.png"] if "*.png" in pattern else []

        with patch.object(service, "_analyze_single_page") as mock_analyze:
            mock_analyze.return_value = {"success": True, "cached": False, "skipped": False}

            # Act
            result = service.scan_all_directories()

            # Assert - should only process unique files
            assert result["total_files"] == 1
            assert mock_analyze.call_count == 1
