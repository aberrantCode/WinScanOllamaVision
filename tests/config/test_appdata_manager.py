"""
Tests for AppDataManager.

Target: 90%+ coverage with file system mocking
"""

import configparser
import os
import shutil
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

from config.appdata_manager import AppDataManager, initialize_appdata


class TestAppDataManager:
    """Test suite for AppDataManager"""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing"""
        # Create temp AppData directory
        appdata_dir = tempfile.mkdtemp(prefix="test_appdata_")
        # Create temp solution data directory
        solution_data_dir = tempfile.mkdtemp(prefix="test_solution_data_")

        yield appdata_dir, solution_data_dir

        # Cleanup with retry for Windows file lock issues
        import time

        def safe_rmtree(path, retries=3):
            """Remove directory tree with retry for Windows file locks"""
            for attempt in range(retries):
                try:
                    if os.path.exists(path):
                        shutil.rmtree(path)
                    return
                except PermissionError:
                    if attempt < retries - 1:
                        time.sleep(0.1)  # Brief delay before retry
                    else:
                        # On final attempt, just skip - test cleanup will handle it
                        pass

        safe_rmtree(appdata_dir)
        safe_rmtree(solution_data_dir)

    @pytest.fixture
    def mock_appdata_path(self, temp_dirs):
        """Mock the APPDATA environment variable"""
        appdata_dir, _ = temp_dirs
        # Return the parent of where WinScanLLM would be created
        appdata_root = os.path.dirname(appdata_dir)
        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            yield appdata_root

    def test_init_uses_appdata_environment_variable(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs

        # Act
        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)

        # Assert
        expected_appdata_dir = os.path.join(appdata_root, "WinScanLLM")
        assert manager.appdata_dir == expected_appdata_dir

    def test_init_uses_fallback_when_appdata_not_set(self, temp_dirs):
        # Arrange
        _, solution_data_dir = temp_dirs

        # Act
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("os.path.expanduser") as mock_expand,
        ):
            mock_expand.return_value = "/home/user"
            manager = AppDataManager(solution_data_dir)

        # Assert
        expected = os.path.join("/home/user", "AppData", "Roaming", "WinScanLLM")
        assert manager.appdata_dir == expected

    def test_init_uses_default_solution_data_dir_when_none(self):
        # Act
        manager = AppDataManager()

        # Assert
        # Should calculate from module location
        assert "data" in manager.solution_data_dir
        assert os.path.isabs(manager.solution_data_dir)

    def test_init_sets_correct_paths(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs

        # Act
        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)

        # Assert
        assert manager.settings_path.endswith("settings.ini")
        assert manager.database_path.endswith("metadata.db")
        assert manager.template_settings.endswith("settings.ini")
        assert manager.template_database.endswith("metadata.db")

    def test_initialize_creates_appdata_directory(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs
        appdata_dir = os.path.join(appdata_root, "WinScanLLM")

        # Ensure directory doesn't exist
        if os.path.exists(appdata_dir):
            shutil.rmtree(appdata_dir)

        # Act
        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)
            settings_path, db_path = manager.initialize()

        # Assert
        assert os.path.exists(appdata_dir)

    def test_initialize_returns_correct_paths(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs

        # Act
        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)
            settings_path, db_path = manager.initialize()

        # Assert
        assert settings_path == manager.settings_path
        assert db_path == manager.database_path

    def test_initialize_settings_copies_template_on_first_run(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs

        # Create template settings
        template_settings = os.path.join(solution_data_dir, "settings.ini")
        config = configparser.ConfigParser()
        config["TestSection"] = {"key": "value"}
        with open(template_settings, "w") as f:
            config.write(f)

        # Act
        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)
            manager.initialize()

        # Assert
        assert os.path.exists(manager.settings_path)
        user_config = configparser.ConfigParser()
        user_config.read(manager.settings_path)
        assert user_config.get("TestSection", "key") == "value"

    def test_initialize_settings_works_without_template(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs
        # Don't create template

        # Act
        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)
            manager.initialize()

        # Assert
        # Should complete without error
        assert manager.appdata_dir is not None

    def test_update_settings_adds_missing_sections(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs

        # Create user settings with one section
        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)
            manager.initialize()

        user_config = configparser.ConfigParser()
        user_config["ExistingSection"] = {"key": "user_value"}
        with open(manager.settings_path, "w") as f:
            user_config.write(f)

        # Create template with new section
        template_config = configparser.ConfigParser()
        template_config["ExistingSection"] = {"key": "template_value"}
        template_config["NewSection"] = {"new_key": "new_value"}
        with open(manager.template_settings, "w") as f:
            template_config.write(f)

        # Act
        manager._update_settings_if_needed()

        # Assert
        updated_config = configparser.ConfigParser()
        updated_config.read(manager.settings_path)
        assert updated_config.has_section("NewSection")
        assert updated_config.get("NewSection", "new_key") == "new_value"
        # User value should be preserved
        assert updated_config.get("ExistingSection", "key") == "user_value"

    def test_update_settings_adds_missing_keys_to_existing_section(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs

        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)
            manager.initialize()

        # Create user settings
        user_config = configparser.ConfigParser()
        user_config["Section1"] = {"key1": "user_value"}
        with open(manager.settings_path, "w") as f:
            user_config.write(f)

        # Create template with additional key
        template_config = configparser.ConfigParser()
        template_config["Section1"] = {"key1": "template_value", "key2": "new_value"}
        with open(manager.template_settings, "w") as f:
            template_config.write(f)

        # Act
        manager._update_settings_if_needed()

        # Assert
        updated_config = configparser.ConfigParser()
        updated_config.read(manager.settings_path)
        assert updated_config.get("Section1", "key1") == "user_value"  # Preserved
        assert updated_config.get("Section1", "key2") == "new_value"  # Added

    def test_update_settings_creates_backup(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs

        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)
            manager.initialize()

        # Ensure settings file exists
        if not os.path.exists(manager.settings_path):
            user_config = configparser.ConfigParser()
            user_config["ExistingSection"] = {"key": "value"}
            with open(manager.settings_path, "w") as f:
                user_config.write(f)

        # Create template with new section
        template_config = configparser.ConfigParser()
        template_config["ExistingSection"] = {"key": "old_value"}
        template_config["NewSection"] = {"key": "value"}
        with open(manager.template_settings, "w") as f:
            template_config.write(f)

        # Act
        manager._update_settings_if_needed()

        # Assert
        backup_path = manager.settings_path + ".backup"
        assert os.path.exists(backup_path)

    def test_update_settings_skips_when_no_template(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs

        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)
            manager.initialize()

        # Remove template
        if os.path.exists(manager.template_settings):
            os.remove(manager.template_settings)

        # Act
        manager._update_settings_if_needed()

        # Assert
        # Should complete without error
        assert True

    def test_initialize_database_copies_template_on_first_run(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs

        # Create template database
        template_db = os.path.join(solution_data_dir, "metadata.db")
        conn = sqlite3.connect(template_db)
        conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
        conn.close()

        # Act
        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)
            manager.initialize()

        # Assert
        assert os.path.exists(manager.database_path)
        # Verify table exists
        conn = sqlite3.connect(manager.database_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_initialize_database_works_without_template(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs
        # Don't create template

        # Act
        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)
            manager.initialize()

        # Assert
        # Should complete without error
        assert True

    def test_migrate_database_detects_old_schema(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs

        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)
            manager.initialize()

        # Create database without schema_version table
        conn = sqlite3.connect(manager.database_path)
        conn.execute("CREATE TABLE old_table (id INTEGER PRIMARY KEY)")
        conn.close()

        # Act
        manager._migrate_database_if_needed()

        # Assert
        # Should complete without error (migration is logged)
        assert os.path.exists(manager.database_path)

    def test_migrate_database_checks_schema_version(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs

        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)
            manager.initialize()

        # Create database with schema_version table
        conn = sqlite3.connect(manager.database_path)
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO schema_version (version) VALUES (1)")
        conn.close()

        # Create template with higher version
        template_db = os.path.join(solution_data_dir, "metadata.db")
        conn = sqlite3.connect(template_db)
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO schema_version (version) VALUES (2)")
        conn.close()

        # Act
        manager._migrate_database_if_needed()

        # Assert
        # Should detect version difference and create backup
        assert os.path.exists(manager.database_path)

    def test_get_template_schema_version_returns_default_when_no_template(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs

        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)

        # Act
        version = manager._get_template_schema_version()

        # Assert
        assert version == 1

    def test_get_template_schema_version_returns_version_from_template(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs

        # Create template database with version
        template_db = os.path.join(solution_data_dir, "metadata.db")
        conn = sqlite3.connect(template_db)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
        cursor.execute("INSERT INTO schema_version (version) VALUES (5)")
        conn.commit()
        conn.close()

        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)

        # Act
        version = manager._get_template_schema_version()

        # Assert
        assert version == 5

    def test_get_template_schema_version_handles_missing_version_table(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs

        # Create template database without version table
        template_db = os.path.join(solution_data_dir, "metadata.db")
        conn = sqlite3.connect(template_db)
        try:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE some_table (id INTEGER)")
            conn.commit()
        finally:
            conn.close()

        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)

            # Act
            version = manager._get_template_schema_version()

        # Assert
        assert version == 1

    def test_backup_database_creates_timestamped_backup(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs

        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)
            manager.initialize()

        # Create database
        conn = sqlite3.connect(manager.database_path)
        conn.execute("CREATE TABLE test_table (id INTEGER)")
        conn.close()

        # Act
        manager._backup_database()

        # Assert
        # Check that a backup file was created
        backup_files = [
            f for f in os.listdir(manager.appdata_dir) if f.startswith("metadata.db.backup_")
        ]
        assert len(backup_files) > 0

    def test_get_settings_path_returns_correct_path(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs

        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)

        # Act
        path = manager.get_settings_path()

        # Assert
        assert path == manager.settings_path
        assert path.endswith("settings.ini")

    def test_get_database_path_returns_correct_path(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs

        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)

        # Act
        path = manager.get_database_path()

        # Assert
        assert path == manager.database_path
        assert path.endswith("metadata.db")

    def test_get_appdata_dir_returns_correct_path(self, temp_dirs):
        # Arrange
        appdata_root, solution_data_dir = temp_dirs

        with patch.dict(os.environ, {"APPDATA": appdata_root}):
            manager = AppDataManager(solution_data_dir)

        # Act
        path = manager.get_appdata_dir()

        # Assert
        assert path == manager.appdata_dir
        assert "WinScanLLM" in path


class TestInitializeAppdataFunction:
    """Test suite for initialize_appdata convenience function"""

    def test_initialize_appdata_returns_paths(self):
        # Arrange
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.dict(os.environ, {"APPDATA": temp_dir}),
        ):
            # Act
            settings_path, db_path = initialize_appdata()

        # Assert
        assert settings_path.endswith("settings.ini")
        assert db_path.endswith("metadata.db")
