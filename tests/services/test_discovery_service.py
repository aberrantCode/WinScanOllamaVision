"""
Tests for DiscoveryService
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from config.config_manager import ConfigManager
from db.analysis_db import AnalysisDB
from services.discovery_service import DiscoveryService


@pytest.fixture(autouse=True)
def patch_discovery_service_logger():
    """Prevent DiscoveryService from calling LoggingService (whose singleton may be reset by
    test_logging_service.py tests). Patching the module-level logger makes _get_logger()
    return the mock directly without touching the singleton."""
    with patch("services.discovery_service.logger", MagicMock()):
        yield


@pytest.fixture
def temp_image_dir():
    """Create temporary directory with test images"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some test image files
        image_dir = Path(tmpdir)
        (image_dir / "test1.png").write_bytes(b"fake png")
        (image_dir / "test2.jpg").write_bytes(b"fake jpg")
        (image_dir / "test3.JPEG").write_bytes(b"fake jpeg")
        (image_dir / "not_image.txt").write_bytes(b"text file")

        # Create subdirectory with more images
        subdir = image_dir / "subdir"
        subdir.mkdir()
        (subdir / "test4.png").write_bytes(b"fake png in subdir")

        yield str(image_dir)


@pytest.fixture
def mock_config():
    """Mock ConfigManager"""
    config = MagicMock(spec=ConfigManager)
    config.get_directories.return_value = []
    return config


@pytest.fixture
def mock_analysis_db():
    """Mock AnalysisDB"""
    db = MagicMock(spec=AnalysisDB)
    db.get_active_directories.return_value = []
    # Add mock connection for ImageFilesRepository
    db.connection = MagicMock()
    return db


def test_discovery_service_initialization(mock_config, mock_analysis_db):
    """Test DiscoveryService initializes correctly"""
    service = DiscoveryService(mock_config, mock_analysis_db)

    assert service.config == mock_config
    assert service.analysis_db == mock_analysis_db


def test_discover_images_empty_directories(mock_config, mock_analysis_db):
    """Test discover_images with no directories configured"""
    service = DiscoveryService(mock_config, mock_analysis_db)

    count = service.discover_images([])

    assert count == 0


def test_discover_images_nonexistent_directory(mock_config, mock_analysis_db):
    """Test discover_images with non-existent directory"""
    service = DiscoveryService(mock_config, mock_analysis_db)

    count = service.discover_images(["/nonexistent/path"])

    assert count == 0


@patch("services.discovery_service.ImageFilesRepository")
def test_discover_images_finds_and_registers_files(
    mock_repo_class, temp_image_dir, mock_config, mock_analysis_db
):
    """Test discover_images finds image files and registers them"""
    # Setup mock repository
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo

    # Mock register to return new file count (simulate all files are new)
    mock_repo.get_by_path.return_value = None  # No existing files
    mock_repo.register.return_value = 1  # Each registration returns an ID

    service = DiscoveryService(mock_config, mock_analysis_db)

    count = service.discover_images([temp_image_dir])

    # Should find 4 image files (test1.png, test2.jpg, test3.JPEG, test4.png)
    # not_image.txt should be ignored
    assert count == 4

    # Verify register was called 4 times
    assert mock_repo.register.call_count == 4


@patch("services.discovery_service.ImageFilesRepository")
def test_discover_images_skips_existing_files(
    mock_repo_class, temp_image_dir, mock_config, mock_analysis_db
):
    """Test discover_images skips files that are already registered"""
    # Setup mock repository
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo

    # Mock get_by_path to simulate 2 files already exist
    def mock_get_by_path(file_path):
        if "test1.png" in file_path or "test2.jpg" in file_path:
            return {"id": 1, "file_path": file_path, "file_hash": "existing_hash"}
        return None

    mock_repo.get_by_path.side_effect = mock_get_by_path
    mock_repo.register.return_value = 1

    service = DiscoveryService(mock_config, mock_analysis_db)

    count = service.discover_images([temp_image_dir])

    # Should only count new files (test3.JPEG and test4.png)
    assert count == 2

    # Verify register was only called for new files
    assert mock_repo.register.call_count == 2


@patch("services.discovery_service.ImageFilesRepository")
def test_discover_images_handles_registration_errors(
    mock_repo_class, temp_image_dir, mock_config, mock_analysis_db
):
    """Test discover_images handles registration errors gracefully"""
    # Setup mock repository
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo

    # Mock register to raise an error for one file
    # register() is called with: file_path, file_hash, directory_path, filename, file_size, file_mtime
    def mock_register(file_path, *args, **kwargs):
        if "test1.png" in file_path:
            raise Exception("Database error")
        return 1

    mock_repo.get_by_path.return_value = None
    mock_repo.register.side_effect = mock_register

    service = DiscoveryService(mock_config, mock_analysis_db)

    # Should not crash, should continue processing other files
    count = service.discover_images([temp_image_dir])

    # Should count successfully registered files (3 out of 4)
    assert count == 3


@patch("services.discovery_service.ImageFilesRepository")
def test_discover_images_with_progress_callback(
    mock_repo_class, temp_image_dir, mock_config, mock_analysis_db
):
    """Test discover_images calls progress callback"""
    # Setup mock repository
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_repo.get_by_path.return_value = None
    mock_repo.register.return_value = 1

    service = DiscoveryService(mock_config, mock_analysis_db)

    # Mock progress callback
    progress_callback = MagicMock()

    count = service.discover_images([temp_image_dir], progress_callback=progress_callback)

    assert count == 4

    # Verify progress callback was called
    assert progress_callback.call_count > 0

    # Verify progress callback receives correct arguments (status_text, current, total)
    first_call = progress_callback.call_args_list[0]
    assert len(first_call[0]) == 3  # Three positional arguments


@patch("services.discovery_service.ImageFilesRepository")
def test_discover_images_handles_permission_errors(mock_repo_class, mock_config, mock_analysis_db):
    """Test discover_images handles permission errors when scanning directories"""
    # Create a directory path that will raise PermissionError
    restricted_dir = "/restricted/path"

    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo

    service = DiscoveryService(mock_config, mock_analysis_db)

    # Should handle error gracefully and return 0
    count = service.discover_images([restricted_dir])

    assert count == 0


def test_discover_images_filters_extensions_correctly(
    temp_image_dir, mock_config, mock_analysis_db
):
    """Test that only image extensions are processed"""
    # Create additional files with various extensions
    image_dir = Path(temp_image_dir)
    (image_dir / "document.pdf").write_bytes(b"fake pdf")
    (image_dir / "data.json").write_bytes(b"fake json")
    (image_dir / "script.py").write_bytes(b"fake python")

    with patch("services.discovery_service.ImageFilesRepository") as mock_repo_class:
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        mock_repo.get_by_path.return_value = None
        mock_repo.register.return_value = 1

        service = DiscoveryService(mock_config, mock_analysis_db)
        count = service.discover_images([temp_image_dir])

        # Should still only find 4 image files (PNG, JPG, JPEG)
        assert count == 4


@patch("services.discovery_service.ImageFilesRepository")
def test_discover_images_multiple_directories(
    mock_repo_class, temp_image_dir, mock_config, mock_analysis_db
):
    """Test discover_images with multiple directories"""
    # Create second temp directory
    with tempfile.TemporaryDirectory() as tmpdir2:
        image_dir2 = Path(tmpdir2)
        (image_dir2 / "test5.png").write_bytes(b"fake png")
        (image_dir2 / "test6.jpg").write_bytes(b"fake jpg")

        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        mock_repo.get_by_path.return_value = None
        mock_repo.register.return_value = 1

        service = DiscoveryService(mock_config, mock_analysis_db)

        count = service.discover_images([temp_image_dir, str(image_dir2)])

        # Should find 4 files from first dir + 2 from second dir = 6 total
        assert count == 6


@patch("services.discovery_service.ImageFilesRepository")
def test_discover_images_updates_last_seen(
    mock_repo_class, temp_image_dir, mock_config, mock_analysis_db
):
    """Test discover_images updates last_seen timestamp for existing files"""
    # Setup mock repository
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo

    # Simulate all files already exist
    mock_repo.get_by_path.return_value = {"id": 1, "file_path": "existing", "file_hash": "hash"}

    service = DiscoveryService(mock_config, mock_analysis_db)

    count = service.discover_images([temp_image_dir])

    # Should count 0 new files
    assert count == 0

    # Verify update_last_seen was called for each existing file
    assert mock_repo.update_last_seen.call_count == 4


# ---------------------------------------------------------------------------
# Exception handlers inside the glob loop (lines 92-106)
# ---------------------------------------------------------------------------


@patch("services.discovery_service.ImageFilesRepository")
def test_discover_images_glob_permission_error_continues(
    mock_repo_class, temp_image_dir, mock_config, mock_analysis_db
):
    """When glob.glob raises PermissionError for an extension, the service continues."""
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_repo.get_by_path.return_value = None
    mock_repo.register.return_value = 1

    service = DiscoveryService(mock_config, mock_analysis_db)

    # Raise PermissionError on the first glob call, succeed on the rest
    original_glob = __import__("glob").glob
    call_count = [0]

    def glob_side_effect(pattern, recursive=False):
        call_count[0] += 1
        if call_count[0] == 1:
            raise PermissionError("no read access")
        return original_glob(pattern, recursive=recursive)

    with patch("services.discovery_service.glob") as mock_glob_module:
        mock_glob_module.glob.side_effect = glob_side_effect
        # Should not raise; should continue processing remaining extensions
        count = service.discover_images([temp_image_dir])

    # Some files may still be found via the other extensions
    assert isinstance(count, int)


@patch("services.discovery_service.ImageFilesRepository")
def test_discover_images_glob_oserror_continues(
    mock_repo_class, temp_image_dir, mock_config, mock_analysis_db
):
    """When glob.glob raises OSError for an extension, the service continues."""
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_repo.get_by_path.return_value = None
    mock_repo.register.return_value = 1

    service = DiscoveryService(mock_config, mock_analysis_db)

    with patch("services.discovery_service.glob") as mock_glob_module:
        mock_glob_module.glob.side_effect = OSError("i/o error")
        count = service.discover_images([temp_image_dir])

    assert count == 0  # All globs failed, no files found


@patch("services.discovery_service.ImageFilesRepository")
def test_discover_images_glob_generic_exception_continues(
    mock_repo_class, temp_image_dir, mock_config, mock_analysis_db
):
    """When glob.glob raises a generic Exception, the service continues."""
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_repo.get_by_path.return_value = None
    mock_repo.register.return_value = 1

    service = DiscoveryService(mock_config, mock_analysis_db)

    with patch("services.discovery_service.glob") as mock_glob_module:
        mock_glob_module.glob.side_effect = RuntimeError("unexpected glob failure")
        count = service.discover_images([temp_image_dir])

    assert count == 0


# ---------------------------------------------------------------------------
# Exception handlers in the file-registration block
# ---------------------------------------------------------------------------


@patch("services.discovery_service.ImageFilesRepository")
def test_discover_images_registration_file_not_found_continues(
    mock_repo_class, temp_image_dir, mock_config, mock_analysis_db
):
    """FileNotFoundError during os.stat() is caught; remaining files are processed."""
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_repo.get_by_path.return_value = None  # All files are new

    call_count = [0]
    original_stat = __import__("os").stat

    def stat_side_effect(path):
        call_count[0] += 1
        if call_count[0] == 1:
            raise FileNotFoundError("file vanished")
        return original_stat(path)

    service = DiscoveryService(mock_config, mock_analysis_db)

    with patch("os.stat", side_effect=stat_side_effect):
        count = service.discover_images([temp_image_dir])

    # First file fails stat, remaining files succeed
    assert count == 3  # 4 files total, 1 fails


@patch("services.discovery_service.ImageFilesRepository")
def test_discover_images_registration_permission_error_continues(
    mock_repo_class, temp_image_dir, mock_config, mock_analysis_db
):
    """PermissionError during os.stat() is caught; remaining files are processed."""
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_repo.get_by_path.return_value = None

    call_count = [0]
    original_stat = __import__("os").stat

    def stat_side_effect(path):
        call_count[0] += 1
        if call_count[0] == 1:
            raise PermissionError("access denied")
        return original_stat(path)

    service = DiscoveryService(mock_config, mock_analysis_db)

    with patch("os.stat", side_effect=stat_side_effect):
        count = service.discover_images([temp_image_dir])

    assert count == 3


@patch("services.discovery_service.ImageFilesRepository")
def test_discover_images_registration_oserror_continues(
    mock_repo_class, temp_image_dir, mock_config, mock_analysis_db
):
    """OSError during os.stat() is caught; remaining files are processed."""
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_repo.get_by_path.return_value = None

    call_count = [0]
    original_stat = __import__("os").stat

    def stat_side_effect(path):
        call_count[0] += 1
        if call_count[0] == 1:
            raise OSError("i/o error")
        return original_stat(path)

    service = DiscoveryService(mock_config, mock_analysis_db)

    with patch("os.stat", side_effect=stat_side_effect):
        count = service.discover_images([temp_image_dir])

    assert count == 3


@patch("services.discovery_service.ImageFilesRepository")
def test_discover_images_registration_sqlite_error_continues(
    mock_repo_class, temp_image_dir, mock_config, mock_analysis_db
):
    """sqlite3.Error from repo.register() is caught; remaining files are processed."""
    import sqlite3

    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_repo.get_by_path.return_value = None

    call_count = [0]

    def register_side_effect(**kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise sqlite3.Error("constraint violation")
        return 1

    mock_repo.register.side_effect = register_side_effect

    service = DiscoveryService(mock_config, mock_analysis_db)
    count = service.discover_images([temp_image_dir])

    assert count == 3  # 4 files, first registration fails


@patch("services.discovery_service.ImageFilesRepository")
def test_discover_images_registration_generic_exception_continues(
    mock_repo_class, temp_image_dir, mock_config, mock_analysis_db
):
    """Generic Exception from repo.register() is caught; remaining files are processed."""
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_repo.get_by_path.return_value = None

    call_count = [0]

    def register_side_effect(**kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise ValueError("unexpected register error")
        return 1

    mock_repo.register.side_effect = register_side_effect

    service = DiscoveryService(mock_config, mock_analysis_db)
    count = service.discover_images([temp_image_dir])

    assert count == 3


# ---------------------------------------------------------------------------
# Outer file-processing exception handlers (lines 200-206)
# ---------------------------------------------------------------------------


@patch("services.discovery_service.ImageFilesRepository")
def test_discover_images_outer_sqlite_error_continues(
    mock_repo_class, temp_image_dir, mock_config, mock_analysis_db
):
    """sqlite3.Error from get_by_path() is caught; the loop continues with next file."""
    import sqlite3

    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo

    call_count = [0]

    def get_by_path_side_effect(path):
        call_count[0] += 1
        if call_count[0] == 1:
            raise sqlite3.Error("db locked")
        return None  # File is new for the rest

    mock_repo.get_by_path.side_effect = get_by_path_side_effect
    mock_repo.register.return_value = 1

    service = DiscoveryService(mock_config, mock_analysis_db)
    count = service.discover_images([temp_image_dir])

    # First file's get_by_path raises, so it's skipped; the other 3 files are registered
    assert count == 3


@patch("services.discovery_service.ImageFilesRepository")
def test_discover_images_outer_generic_exception_continues(
    mock_repo_class, temp_image_dir, mock_config, mock_analysis_db
):
    """Generic Exception from get_by_path() is caught; the loop continues."""
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo

    call_count = [0]

    def get_by_path_side_effect(path):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("unexpected db error")
        return None

    mock_repo.get_by_path.side_effect = get_by_path_side_effect
    mock_repo.register.return_value = 1

    service = DiscoveryService(mock_config, mock_analysis_db)
    count = service.discover_images([temp_image_dir])

    assert count == 3
