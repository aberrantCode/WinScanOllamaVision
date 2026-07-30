"""
Tests for ConfigManager.

Target: 90%+ coverage with file-based config testing
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from config.config_manager import ConfigManager


class TestConfigManager:
    """Test suite for ConfigManager"""

    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary config file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            config_path = f.name
        yield config_path
        # Cleanup
        if os.path.exists(config_path):
            os.remove(config_path)

    @pytest.fixture
    def config_manager(self, temp_config_file):
        """Create ConfigManager with temporary file"""
        return ConfigManager(temp_config_file)

    def test_init_creates_config_file_if_not_exists(self, temp_config_file):
        # Arrange
        os.remove(temp_config_file)  # Remove the temp file to test creation

        # Act
        config = ConfigManager(temp_config_file)

        # Assert
        assert os.path.exists(temp_config_file)
        assert config.config_file == temp_config_file

    def test_init_loads_existing_config(self, temp_config_file):
        # Arrange
        # First create a config
        config1 = ConfigManager(temp_config_file)
        config1.set_setting("TestSection", "test_key", "test_value")

        # Act
        # Load it again
        config2 = ConfigManager(temp_config_file)

        # Assert
        assert config2.get_setting("TestSection", "test_key") == "test_value"

    def test_init_uses_appdata_path_when_no_config_file_specified(self):
        # Arrange
        with tempfile.TemporaryDirectory() as temp_appdata:
            # Create the WinScanLLM directory that ConfigManager expects
            winscan_dir = os.path.join(temp_appdata, "WinScanLLM")
            os.makedirs(winscan_dir, exist_ok=True)

            # Act
            with patch.dict(os.environ, {"APPDATA": temp_appdata}):
                config = ConfigManager()

            # Assert
            expected_path = os.path.join(temp_appdata, "WinScanLLM", "settings.ini")
            assert config.config_file == expected_path
            assert os.path.exists(expected_path)

    def test_create_default_config_creates_all_sections(self, config_manager):
        # Act
        sections = config_manager.config.sections()

        # Assert
        expected_sections = [
            "LLMProvider",
            "Ollama",
            "ClaudeCLI",
            "GeminiCLI",
            "DocumentProcessing",
            "SourceDirectories",
            "AutoAnalysis",
            "Theme",
            "OutputDirectory",
            "SystemTray",
            "AuditTrail",
            "GUI",
        ]
        for section in expected_sections:
            assert section in sections

    def test_create_default_config_sets_ollama_defaults(self, config_manager):
        # Assert
        assert config_manager.get_setting("Ollama", "model") == "qwen2.5vl:latest"
        assert config_manager.get_setting("Ollama", "base_url") == "http://localhost:11434"
        assert config_manager.get_setting("Ollama", "timeout") == "300"

    def test_migrates_legacy_ollama_model_name(self, temp_config_file):
        # Arrange: a config file written before the qwen2.5-vl -> qwen2.5vl fix
        with open(temp_config_file, "w") as f:
            f.write(
                "[Ollama]\nmodel = qwen2.5-vl\nbase_url = http://localhost:11434\ntimeout = 300\n"
            )

        # Act
        config = ConfigManager(temp_config_file)

        # Assert: upgraded in memory and persisted to disk
        assert config.get_setting("Ollama", "model") == "qwen2.5vl:latest"
        with open(temp_config_file) as f:
            saved = f.read()
        assert "model = qwen2.5vl:latest" in saved
        assert "qwen2.5-vl" not in saved

    def test_migration_is_idempotent_for_already_corrected_model(self, temp_config_file):
        # Arrange
        with open(temp_config_file, "w") as f:
            f.write(
                "[Ollama]\nmodel = qwen2.5vl:latest\nbase_url = http://localhost:11434\ntimeout = 300\n"
            )

        # Act
        config = ConfigManager(temp_config_file)

        # Assert
        assert config.get_setting("Ollama", "model") == "qwen2.5vl:latest"

    def test_migration_does_not_touch_custom_model_name(self, temp_config_file):
        # Arrange: a user-chosen model that happens to differ from the default
        with open(temp_config_file, "w") as f:
            f.write(
                "[Ollama]\nmodel = llava:latest\nbase_url = http://localhost:11434\ntimeout = 300\n"
            )

        # Act
        config = ConfigManager(temp_config_file)

        # Assert
        assert config.get_setting("Ollama", "model") == "llava:latest"

    def test_create_default_config_sets_claude_cli_defaults(self, config_manager):
        # Assert
        # Note: ConfigParser escapes %% to % when reading
        assert "%MODEL%" in config_manager.get_setting("ClaudeCLI", "command_template")
        assert config_manager.get_setting("ClaudeCLI", "timeout") == "300"
        assert (
            config_manager.get_setting("ClaudeCLI", "default_model") == "claude-3-5-sonnet-20241022"
        )

    def test_create_default_config_sets_gemini_cli_defaults(self, config_manager):
        # Assert
        # Note: ConfigParser escapes %% to % when reading
        assert "%MODEL%" in config_manager.get_setting("GeminiCLI", "command_template")
        assert config_manager.get_setting("GeminiCLI", "default_model") == "gemini-2.0-flash-exp"

    def test_get_setting_returns_value_when_exists(self, config_manager):
        # Arrange
        config_manager.set_setting("TestSection", "key", "value")

        # Act
        result = config_manager.get_setting("TestSection", "key")

        # Assert
        assert result == "value"

    def test_get_setting_returns_default_when_not_exists(self, config_manager):
        # Act
        result = config_manager.get_setting("NonExistent", "key", "default_value")

        # Assert
        assert result == "default_value"

    def test_get_setting_returns_none_when_not_exists_and_no_default(self, config_manager):
        # Act
        result = config_manager.get_setting("NonExistent", "key")

        # Assert
        assert result is None

    def test_set_setting_creates_section_if_not_exists(self, config_manager):
        # Act
        config_manager.set_setting("NewSection", "key", "value")

        # Assert
        assert "NewSection" in config_manager.config.sections()
        assert config_manager.get_setting("NewSection", "key") == "value"

    def test_set_setting_converts_value_to_string(self, config_manager):
        # Act
        config_manager.set_setting("TestSection", "int_key", 123)
        config_manager.set_setting("TestSection", "bool_key", True)

        # Assert
        assert config_manager.get_setting("TestSection", "int_key") == "123"
        assert config_manager.get_setting("TestSection", "bool_key") == "True"

    def test_set_setting_saves_to_file(self, temp_config_file):
        # Arrange
        config1 = ConfigManager(temp_config_file)

        # Act
        config1.set_setting("TestSection", "key", "value")

        # Load in new instance
        config2 = ConfigManager(temp_config_file)

        # Assert
        assert config2.get_setting("TestSection", "key") == "value"

    def test_get_directories_returns_empty_list_when_empty(self, config_manager):
        # Arrange
        config_manager.set_setting("SourceDirectories", "directories", "[]")

        # Act
        result = config_manager.get_directories()

        # Assert
        assert result == []

    def test_get_directories_returns_list_of_directories(self, config_manager):
        # Arrange
        directories = ["/path/to/dir1", "/path/to/dir2"]
        config_manager.set_setting("SourceDirectories", "directories", json.dumps(directories))

        # Act
        result = config_manager.get_directories()

        # Assert
        assert result == directories

    def test_get_directories_handles_invalid_json(self, config_manager):
        # Arrange
        config_manager.set_setting("SourceDirectories", "directories", "invalid json")

        # Act
        result = config_manager.get_directories()

        # Assert
        assert result == []

    def test_set_directories_saves_as_json(self, config_manager):
        # Arrange
        directories = ["/path/to/dir1", "/path/to/dir2"]

        # Act
        config_manager.set_directories(directories)

        # Assert
        saved_value = config_manager.get_setting("SourceDirectories", "directories")
        assert json.loads(saved_value) == directories

    def test_add_directory_adds_to_list(self, config_manager):
        # Arrange
        config_manager.set_directories(["/path/to/dir1"])

        # Act
        config_manager.add_directory("/path/to/dir2")

        # Assert
        directories = config_manager.get_directories()
        assert "/path/to/dir1" in directories
        assert "/path/to/dir2" in directories
        assert len(directories) == 2

    def test_add_directory_does_not_duplicate(self, config_manager):
        # Arrange
        config_manager.set_directories(["/path/to/dir1"])

        # Act
        config_manager.add_directory("/path/to/dir1")

        # Assert
        directories = config_manager.get_directories()
        assert directories.count("/path/to/dir1") == 1

    def test_remove_directory_removes_from_list(self, config_manager):
        # Arrange
        config_manager.set_directories(["/path/to/dir1", "/path/to/dir2"])

        # Act
        config_manager.remove_directory("/path/to/dir1")

        # Assert
        directories = config_manager.get_directories()
        assert "/path/to/dir1" not in directories
        assert "/path/to/dir2" in directories

    def test_remove_directory_does_nothing_if_not_in_list(self, config_manager):
        # Arrange
        config_manager.set_directories(["/path/to/dir1"])

        # Act
        config_manager.remove_directory("/path/to/dir2")

        # Assert
        directories = config_manager.get_directories()
        assert directories == ["/path/to/dir1"]

    def test_get_active_provider_returns_default(self, config_manager):
        # Act
        result = config_manager.get_active_provider()

        # Assert
        assert result == "ollama"

    def test_set_active_provider_updates_value(self, config_manager):
        # Act
        config_manager.set_active_provider("claude_cli")

        # Assert
        assert config_manager.get_active_provider() == "claude_cli"

    def test_get_provider_models_ollama_returns_single_model(self, config_manager):
        # Act
        models = config_manager.get_provider_models("ollama")

        # Assert
        assert models == ["qwen2.5vl:latest"]

    def test_get_provider_models_claude_cli_returns_list(self, config_manager):
        # Act
        models = config_manager.get_provider_models("claude_cli")

        # Assert
        assert "claude-3-5-sonnet-20241022" in models
        assert "claude-3-5-haiku-20241022" in models

    def test_get_provider_models_gemini_cli_returns_list(self, config_manager):
        # Act
        models = config_manager.get_provider_models("gemini_cli")

        # Assert
        assert "gemini-2.0-flash-exp" in models
        assert "gemini-1.5-pro" in models

    def test_get_provider_models_unknown_provider_returns_empty(self, config_manager):
        # Act
        models = config_manager.get_provider_models("unknown")

        # Assert
        assert models == []

    def test_get_provider_models_handles_empty_models_string(self, config_manager):
        # Arrange
        config_manager.set_setting("ClaudeCLI", "models", "")

        # Act
        models = config_manager.get_provider_models("claude_cli")

        # Assert
        assert models == []

    def test_get_provider_models_handles_comma_separated_with_spaces(self, config_manager):
        # Arrange
        config_manager.set_setting("ClaudeCLI", "models", " model1 , model2 , model3 ")

        # Act
        models = config_manager.get_provider_models("claude_cli")

        # Assert
        assert models == ["model1", "model2", "model3"]

    def test_get_provider_config_ollama(self, config_manager):
        # Act
        config = config_manager.get_provider_config("ollama")

        # Assert
        assert config["model"] == "qwen2.5vl:latest"
        assert config["base_url"] == "http://localhost:11434"
        assert config["timeout"] == 300

    def test_get_provider_config_claude_cli(self, config_manager):
        # Act
        config = config_manager.get_provider_config("claude_cli")

        # Assert
        assert "command_template" in config
        assert config["timeout"] == 300
        assert "models" in config
        assert config["default_model"] == "claude-3-5-sonnet-20241022"

    def test_get_provider_config_gemini_cli(self, config_manager):
        # Act
        config = config_manager.get_provider_config("gemini_cli")

        # Assert
        assert "command_template" in config
        assert config["timeout"] == 300
        assert "models" in config
        assert config["default_model"] == "gemini-2.0-flash-exp"

    def test_get_provider_config_unknown_returns_empty(self, config_manager):
        # Act
        config = config_manager.get_provider_config("unknown")

        # Assert
        assert config == {}

    def test_get_bool_returns_true_for_truthy_values(self, config_manager):
        # Arrange
        config_manager.set_setting("Test", "key1", "true")
        config_manager.set_setting("Test", "key2", "1")
        config_manager.set_setting("Test", "key3", "yes")
        config_manager.set_setting("Test", "key4", "on")
        config_manager.set_setting("Test", "key5", "True")

        # Act & Assert
        assert config_manager.get_bool("Test", "key1") is True
        assert config_manager.get_bool("Test", "key2") is True
        assert config_manager.get_bool("Test", "key3") is True
        assert config_manager.get_bool("Test", "key4") is True
        assert config_manager.get_bool("Test", "key5") is True

    def test_get_bool_returns_false_for_falsy_values(self, config_manager):
        # Arrange
        config_manager.set_setting("Test", "key1", "false")
        config_manager.set_setting("Test", "key2", "0")
        config_manager.set_setting("Test", "key3", "no")
        config_manager.set_setting("Test", "key4", "off")

        # Act & Assert
        assert config_manager.get_bool("Test", "key1") is False
        assert config_manager.get_bool("Test", "key2") is False
        assert config_manager.get_bool("Test", "key3") is False
        assert config_manager.get_bool("Test", "key4") is False

    def test_get_bool_returns_default_when_not_exists(self, config_manager):
        # Act
        result = config_manager.get_bool("NonExistent", "key", default=True)

        # Assert
        assert result is True

    def test_get_int_returns_integer(self, config_manager):
        # Arrange
        config_manager.set_setting("Test", "key", "123")

        # Act
        result = config_manager.get_int("Test", "key")

        # Assert
        assert result == 123
        assert isinstance(result, int)

    def test_get_int_returns_default_for_invalid_value(self, config_manager):
        # Arrange
        config_manager.set_setting("Test", "key", "not_an_int")

        # Act
        result = config_manager.get_int("Test", "key", default=42)

        # Assert
        assert result == 42

    def test_get_int_returns_default_when_not_exists(self, config_manager):
        # Act
        result = config_manager.get_int("NonExistent", "key", default=99)

        # Assert
        assert result == 99

    def test_get_logger_fallback_when_service_unavailable(self, monkeypatch):
        """Test _get_logger() uses fallback logging when service unavailable (lines 14-18)."""

        # Arrange - make get_logger import fail
        def mock_import_error(*args):
            raise ImportError("Service not available")

        # Patch __import__ to raise error for logging_service
        import builtins

        original_import = builtins.__import__

        def custom_import(name, *args, **kwargs):
            if "logging_service" in name:
                raise ImportError("Service not available")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", custom_import)

        # Act - import config_manager which will trigger _get_logger
        from config.config_manager import _get_logger

        logger = _get_logger()

        # Assert - should get basic logger, not fail
        assert logger is not None
        assert hasattr(logger, "debug")

    def test_check_disk_space_returns_true_on_exception(self, config_manager, monkeypatch):
        """Test _check_disk_space() returns True when disk_usage raises exception (lines 52-54)."""
        # Arrange - make disk_usage raise exception
        import shutil

        def mock_disk_usage(path):
            raise OSError("Disk check failed")

        monkeypatch.setattr(shutil, "disk_usage", mock_disk_usage)

        # Act
        result = config_manager._check_disk_space("/some/path", 1000)

        # Assert - should fail open (return True)
        assert result is True

    def test_load_config_handles_corrupted_file(self, temp_config_file):
        """Test _load_config() handles corrupted config file gracefully (lines 66-76)."""
        # Arrange - create corrupted config file
        with open(temp_config_file, "w") as f:
            f.write("[Invalid\nthis is not valid INI\n{{{}}")

        # Act - should backup corrupted file and create defaults
        config = ConfigManager(temp_config_file)

        # Assert - backup should exist
        backup_file = f"{temp_config_file}.corrupted"
        assert os.path.exists(backup_file)

        # Verify defaults were created
        assert config.get_setting("LLMProvider", "active_provider") is not None

        # Cleanup backup
        if os.path.exists(backup_file):
            os.remove(backup_file)

    def test_save_config_raises_error_on_insufficient_disk_space(self, config_manager, monkeypatch):
        """Test _save_config() raises OSError when disk space insufficient (lines 199-202)."""
        # Arrange - mock _check_disk_space to return False
        monkeypatch.setattr(config_manager, "_check_disk_space", lambda *args: False)

        # Act & Assert
        with pytest.raises(OSError, match="Insufficient disk space"):
            config_manager._save_config()

    def test_save_config_handles_permission_error(self, temp_config_file, monkeypatch):
        """Test _save_config() handles PermissionError gracefully (lines 220-222)."""
        # Arrange
        config = ConfigManager(temp_config_file)

        # Mock open to raise PermissionError
        original_open = open

        def mock_open(file, mode="r", *args, **kwargs):
            if file.endswith(".tmp") and "w" in mode:
                raise PermissionError("Access denied")
            return original_open(file, mode, *args, **kwargs)

        monkeypatch.setattr("builtins.open", mock_open)

        # Act & Assert
        with pytest.raises(PermissionError, match="Cannot save configuration"):
            config._save_config()

    def test_save_config_handles_os_error(self, temp_config_file, monkeypatch):
        """Test _save_config() handles OSError gracefully (lines 223-225)."""
        # Arrange
        config = ConfigManager(temp_config_file)

        # Mock open to raise OSError
        original_open = open

        def mock_open(file, mode="r", *args, **kwargs):
            if file.endswith(".tmp") and "w" in mode:
                raise OSError("Disk full")
            return original_open(file, mode, *args, **kwargs)

        monkeypatch.setattr("builtins.open", mock_open)

        # Act & Assert
        with pytest.raises(OSError, match="Failed to save configuration"):
            config._save_config()

    def test_get_float_returns_float_value(self, config_manager):
        """Test get_float() returns float value."""
        # Arrange
        config_manager.set_setting("Test", "float_key", "3.14")

        # Act
        result = config_manager.get_float("Test", "float_key")

        # Assert
        assert result == 3.14
        assert isinstance(result, float)

    def test_get_float_returns_default_for_invalid_value(self, config_manager):
        """Test get_float() returns default for invalid value (lines 357-364)."""
        # Arrange
        config_manager.set_setting("Test", "float_key", "not_a_float")

        # Act
        result = config_manager.get_float("Test", "float_key", default=9.99)

        # Assert - should return default when value cannot be converted to float
        assert result == 9.99
        assert isinstance(result, float)

    def test_get_float_returns_default_when_not_exists(self, config_manager):
        """Test get_float() returns default when key doesn't exist."""
        # Act
        result = config_manager.get_float("NonExistent", "key", default=7.77)

        # Assert
        assert result == 7.77
