import configparser
import json
import os
import shutil
from typing import Any, cast


def _get_logger():
    """Lazy logger initialization to avoid circular imports"""
    try:
        from services.logging_service import get_logger

        return get_logger()
    except Exception:
        # Fallback to basic logging if service not initialized
        import logging

        return logging.getLogger(__name__)


class ConfigManager:
    def __init__(self, config_file=None):
        # If no config file specified, use AppData directory
        if config_file is None:
            appdata_root = os.getenv(
                "APPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
            )
            appdata_dir = os.path.join(appdata_root, "WinScanLLM")
            config_file = os.path.join(appdata_dir, "settings.ini")

        self.config_file = config_file
        # Disable interpolation to allow % characters in prompts
        self.config = configparser.ConfigParser(interpolation=None)
        self._load_config()

    def _check_disk_space(self, file_path: str, required_bytes: int) -> bool:
        """
        Check if sufficient disk space is available.

        Args:
            file_path: Path to check disk space for
            required_bytes: Minimum bytes required

        Returns:
            True if sufficient space (with 2x safety margin), False otherwise
        """
        try:
            dir_path = os.path.dirname(file_path) or "."
            usage = shutil.disk_usage(dir_path)
            available = usage.free
            return available > required_bytes * 2  # 2x safety margin
        except Exception:
            # If check fails, assume sufficient space (fail open)
            return True

    def _load_config(self):
        """
        Load configuration from file, handling corrupted files gracefully.

        If config file is corrupted, backs it up and creates defaults.
        """
        if os.path.exists(self.config_file):
            try:
                self.config.read(self.config_file)
                _get_logger().info(f"Loaded config from {self.config_file}")
            except configparser.Error as e:
                _get_logger().error(f"[CONFIG] Malformed config: {self.config_file} - {e}")
                # Backup corrupted file
                backup = f"{self.config_file}.corrupted"
                shutil.copy2(self.config_file, backup)
                _get_logger().info(f"[CONFIG] Backed up corrupted config to: {backup}")
                # Create defaults
                self._create_default_config()
                _get_logger().info("[CONFIG] Created new default configuration")
                self._save_config()
                return

            # Ensure all default sections exist (for config files created before new providers added)
            self._create_default_config()
            self._save_config()
        else:
            self._create_default_config()
            self._save_config()

    def _create_default_config(self):
        # Default LLM Provider settings
        if "LLMProvider" not in self.config:
            self.config["LLMProvider"] = {"active_provider": "ollama", "default_model": ""}

        # Default Ollama settings
        if "Ollama" not in self.config:
            self.config["Ollama"] = {
                "model": "qwen2.5-vl",  # Default vision model
                "base_url": "http://localhost:11434",
                "timeout": "300",  # Timeout in seconds (5 minutes default for vision models)
            }

        # Claude CLI settings
        if "ClaudeCLI" not in self.config:
            self.config["ClaudeCLI"] = {
                "command_template": "claude --model %%MODEL%% --image %%IMAGE_PATHS%% --prompt %%PROMPT%%",
                "timeout": "300",
                "models": "claude-3-5-sonnet-20241022,claude-3-5-haiku-20241022",
                "default_model": "claude-3-5-sonnet-20241022",
            }

        # Gemini CLI settings
        if "GeminiCLI" not in self.config:
            self.config["GeminiCLI"] = {
                "command_template": "gemini --model %%MODEL%% --image %%IMAGE_PATHS%% --prompt %%PROMPT%%",
                "timeout": "300",
                "models": "gemini-2.0-flash-exp,gemini-1.5-pro",
                "default_model": "gemini-2.0-flash-exp",
            }

        # Default Document Processing settings
        if "DocumentProcessing" not in self.config:
            self.config["DocumentProcessing"] = {
                "scan_folder": os.path.join(os.path.expanduser("~"), "Pictures", "Scans"),
                "organized_subfolder": "ORGANIZED",
                "title_keywords": "Invoice, Statement, Bill, Receipt, Report, Contract, Agreement",
                "auto_approval": "false",
            }

        # Source directories configuration
        if "SourceDirectories" not in self.config:
            default_scan_folder = os.path.join(os.path.expanduser("~"), "Pictures", "Scans")
            self.config["SourceDirectories"] = {
                "directories": json.dumps([default_scan_folder]),
                "scan_on_startup": "true",
            }

        # Auto-analysis settings
        if "AutoAnalysis" not in self.config:
            self.config["AutoAnalysis"] = {
                "enabled": "true",
                "incremental": "true",
                "batch_size": "10",
            }

        # Discovery and scheduling settings
        if "Discovery" not in self.config:
            self.config["Discovery"] = {
                "enabled": "true",
                "interval_minutes": "60",
                "auto_analyze_after_discovery": "false",
                "last_run": "",
            }

        # Theme and appearance settings
        if "Theme" not in self.config:
            self.config["Theme"] = {
                "theme": "light",
                "default_zoom_mode_png": "fit_to_width",
                "default_zoom_mode_pdf": "fit_to_width",
                "default_zoom_percent_png": "100",
                "default_zoom_percent_pdf": "100",
            }

        # Output directory settings
        if "OutputDirectory" not in self.config:
            self.config["OutputDirectory"] = {
                "strategy": "same_as_source",
                "subdirectory_name": "ORGANIZED",
                "global_custom_path": "",
            }

        # System tray settings
        if "SystemTray" not in self.config:
            self.config["SystemTray"] = {"minimize_to_tray": "false", "close_to_tray": "false"}

        # Audit trail settings
        if "AuditTrail" not in self.config:
            self.config["AuditTrail"] = {"enabled": "false"}

        # Default GUI settings (can be expanded later)
        if "GUI" not in self.config:
            self.config["GUI"] = {
                "app_name": "WinScanLLM",
                "window_width": "1024",
                "window_height": "768",
                "auto_start_analysis": "false",
                "confirm_before_exit": "true",
            }

    def _save_config(self):
        """
        Save configuration to file with atomic write and backup.

        Raises:
            PermissionError: If config file cannot be written
            OSError: If file operations fail or disk is full
        """
        # Estimate config file size (typically <10KB, use 50KB as safe estimate)
        estimated_size = 50 * 1024  # 50KB

        # Check disk space before writing
        if not self._check_disk_space(self.config_file, estimated_size):
            _get_logger().error(
                f"[CONFIG] Insufficient disk space to save config: {self.config_file}"
            )
            raise OSError(
                f"Insufficient disk space to save configuration. "
                f"At least {estimated_size * 2} bytes required."
            )

        try:
            # Atomic write: write to temp file first
            temp_file = f"{self.config_file}.tmp"
            with open(temp_file, "w") as configfile:
                self.config.write(configfile)

            # Create backup if original exists
            if os.path.exists(self.config_file):
                shutil.copy2(self.config_file, f"{self.config_file}.backup")

            # Move temp to actual location
            shutil.move(temp_file, self.config_file)
            _get_logger().debug(f"[CONFIG] Saved configuration to {self.config_file}")
        except PermissionError as e:
            _get_logger().error(f"[CONFIG] Permission denied: {self.config_file}")
            raise PermissionError(f"Cannot save configuration: {self.config_file}") from e
        except OSError as e:
            _get_logger().error(f"[CONFIG] Failed to save: {e}")
            raise OSError(f"Failed to save configuration: {e}") from e

    def _reload_config(self):
        """Reload configuration from disk to pick up external changes"""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)

    def get_setting(self, section, key, default=None):
        # Reload config to ensure we have the latest values
        self._reload_config()
        if section in self.config and key in self.config[section]:
            return self.config[section][key]
        return default  # If not found, return the provided default

    def set_setting(self, section, key, value):
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = str(value)  # Ensure value is string
        self._save_config()

    # ==================== Extended Helper Methods ====================

    def get_directories(self) -> list[str]:
        """Get list of source directories from JSON array"""
        directories_json = self.get_setting("SourceDirectories", "directories", "[]")
        try:
            return cast(list[str], json.loads(directories_json))
        except json.JSONDecodeError:
            return []

    def set_directories(self, directories: list[str]) -> None:
        """Set source directories as JSON array"""
        self.set_setting("SourceDirectories", "directories", json.dumps(directories))

    def add_directory(self, directory_path: str) -> None:
        """Add a directory to the source directories list"""
        directories = self.get_directories()
        if directory_path not in directories:
            directories.append(directory_path)
            self.set_directories(directories)

    def remove_directory(self, directory_path: str) -> None:
        """Remove a directory from the source directories list"""
        directories = self.get_directories()
        if directory_path in directories:
            directories.remove(directory_path)
            self.set_directories(directories)

    def get_active_provider(self) -> str:
        """Get the currently active LLM provider"""
        return cast(str, self.get_setting("LLMProvider", "active_provider", "ollama"))

    def set_active_provider(self, provider_name: str) -> None:
        """Set the active LLM provider"""
        self.set_setting("LLMProvider", "active_provider", provider_name)

    def get_provider_models(self, provider_name: str) -> list[str]:
        """Get available models for a provider as list"""
        if provider_name == "ollama":
            # For Ollama, return single model as list
            model = self.get_setting("Ollama", "model", "qwen2.5-vl")
            return [model]
        elif provider_name == "claude_cli":
            models_str = self.get_setting("ClaudeCLI", "models", "")
            return [m.strip() for m in models_str.split(",") if m.strip()]
        elif provider_name == "gemini_cli":
            models_str = self.get_setting("GeminiCLI", "models", "")
            return [m.strip() for m in models_str.split(",") if m.strip()]
        return []

    def get_provider_config(self, provider_name: str) -> dict[str, Any]:
        """Get full configuration for a provider"""
        if provider_name == "ollama":
            return {
                "model": self.get_setting("Ollama", "model"),
                "base_url": self.get_setting("Ollama", "base_url"),
                "timeout": int(self.get_setting("Ollama", "timeout", "300")),
            }
        elif provider_name == "claude_cli":
            return {
                "command_template": self.get_setting("ClaudeCLI", "command_template"),
                "timeout": int(self.get_setting("ClaudeCLI", "timeout", "300")),
                "models": self.get_provider_models("claude_cli"),
                "default_model": self.get_setting("ClaudeCLI", "default_model"),
            }
        elif provider_name == "gemini_cli":
            return {
                "command_template": self.get_setting("GeminiCLI", "command_template"),
                "timeout": int(self.get_setting("GeminiCLI", "timeout", "300")),
                "models": self.get_provider_models("gemini_cli"),
                "default_model": self.get_setting("GeminiCLI", "default_model"),
            }
        return {}

    def get_bool(self, section: str, key: str, default: bool = False) -> bool:
        """Get a boolean setting"""
        value = self.get_setting(section, key, str(default).lower())
        return value.lower() in ("true", "1", "yes", "on")

    def get_int(self, section: str, key: str, default: int = 0) -> int:
        """
        Get an integer setting with validation.

        Args:
            section: Config section name
            key: Setting key
            default: Default value if not found or invalid

        Returns:
            Integer value or default if invalid
        """
        value = self.get_setting(section, key, str(default))
        try:
            return int(value)
        except ValueError:
            _get_logger().warning(
                f"[CONFIG] Invalid integer [{section}] {key}='{value}', using default {default}"
            )
            return default

    def get_float(self, section: str, key: str, default: float = 0.0) -> float:
        """
        Get a float setting with validation.

        Args:
            section: Config section name
            key: Setting key
            default: Default value if not found or invalid

        Returns:
            Float value or default if invalid
        """
        value = self.get_setting(section, key, str(default))
        try:
            return float(value)
        except ValueError:
            _get_logger().warning(
                f"[CONFIG] Invalid float [{section}] {key}='{value}', using default {default}"
            )
            return default
