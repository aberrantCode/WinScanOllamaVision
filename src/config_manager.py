import configparser
import os
import json
from typing import List, Dict, Any, Optional

class ConfigManager:
    def __init__(self, config_file=None):
        # If no config file specified, use AppData directory
        if config_file is None:
            appdata_root = os.getenv('APPDATA', os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming'))
            appdata_dir = os.path.join(appdata_root, 'WinScanLLM')
            config_file = os.path.join(appdata_dir, 'settings.ini')

        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self._load_config()

    def _load_config(self):
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
            # Ensure all default sections exist (for config files created before new providers added)
            self._create_default_config()
            self._save_config()
        else:
            self._create_default_config()
            self._save_config()

    def _create_default_config(self):
        # Default LLM Provider settings
        if 'LLMProvider' not in self.config:
            self.config['LLMProvider'] = {
                'active_provider': 'ollama',
                'default_model': ''
            }

        # Default Ollama settings
        if 'Ollama' not in self.config:
            self.config['Ollama'] = {
                'model': 'qwen2.5-vl', # Default vision model
                'base_url': 'http://localhost:11434',
                'timeout': '300'  # Timeout in seconds (5 minutes default for vision models)
            }

        # Claude CLI settings
        if 'ClaudeCLI' not in self.config:
            self.config['ClaudeCLI'] = {
                'command_template': 'claude --model %%MODEL%% --image %%IMAGE_PATHS%% --prompt %%PROMPT%%',
                'timeout': '300',
                'models': 'claude-3-5-sonnet-20241022,claude-3-5-haiku-20241022',
                'default_model': 'claude-3-5-sonnet-20241022'
            }

        # Gemini CLI settings
        if 'GeminiCLI' not in self.config:
            self.config['GeminiCLI'] = {
                'command_template': 'gemini --model %%MODEL%% --image %%IMAGE_PATHS%% --prompt %%PROMPT%%',
                'timeout': '300',
                'models': 'gemini-2.0-flash-exp,gemini-1.5-pro',
                'default_model': 'gemini-2.0-flash-exp'
            }

        # Default Document Processing settings
        if 'DocumentProcessing' not in self.config:
            self.config['DocumentProcessing'] = {
                'scan_folder': os.path.join(os.path.expanduser('~'), 'Pictures', 'Scans'),
                'organized_subfolder': 'ORGANIZED',
                'title_keywords': 'Invoice, Statement, Bill, Receipt, Report, Contract, Agreement',
                'auto_approval': 'false'
            }

        # Source directories configuration
        if 'SourceDirectories' not in self.config:
            default_scan_folder = os.path.join(os.path.expanduser('~'), 'Pictures', 'Scans')
            self.config['SourceDirectories'] = {
                'directories': json.dumps([default_scan_folder]),
                'scan_on_startup': 'true'
            }

        # Auto-analysis settings
        if 'AutoAnalysis' not in self.config:
            self.config['AutoAnalysis'] = {
                'enabled': 'true',
                'incremental': 'true',
                'batch_size': '10'
            }

        # Theme and appearance settings
        if 'Theme' not in self.config:
            self.config['Theme'] = {
                'theme': 'light',
                'default_zoom_mode_png': 'fit_to_width',
                'default_zoom_mode_pdf': 'fit_to_width',
                'default_zoom_percent_png': '100',
                'default_zoom_percent_pdf': '100'
            }

        # Output directory settings
        if 'OutputDirectory' not in self.config:
            self.config['OutputDirectory'] = {
                'strategy': 'same_as_source',
                'subdirectory_name': 'ORGANIZED',
                'global_custom_path': ''
            }

        # System tray settings
        if 'SystemTray' not in self.config:
            self.config['SystemTray'] = {
                'minimize_to_tray': 'false',
                'close_to_tray': 'false'
            }

        # Audit trail settings
        if 'AuditTrail' not in self.config:
            self.config['AuditTrail'] = {
                'enabled': 'false'
            }

        # Default GUI settings (can be expanded later)
        if 'GUI' not in self.config:
            self.config['GUI'] = {
                'app_name': 'WinScanLLM',
                'window_width': '1024',
                'window_height': '768'
            }

    def _save_config(self):
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)

    def get_setting(self, section, key, default=None):
        if section in self.config and key in self.config[section]:
            return self.config[section][key]
        return default # If not found, return the provided default

    def set_setting(self, section, key, value):
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = str(value) # Ensure value is string
        self._save_config()

    # ==================== Extended Helper Methods ====================

    def get_directories(self) -> List[str]:
        """Get list of source directories from JSON array"""
        directories_json = self.get_setting('SourceDirectories', 'directories', '[]')
        try:
            return json.loads(directories_json)
        except json.JSONDecodeError:
            return []

    def set_directories(self, directories: List[str]) -> None:
        """Set source directories as JSON array"""
        self.set_setting('SourceDirectories', 'directories', json.dumps(directories))

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
        return self.get_setting('LLMProvider', 'active_provider', 'ollama')

    def set_active_provider(self, provider_name: str) -> None:
        """Set the active LLM provider"""
        self.set_setting('LLMProvider', 'active_provider', provider_name)

    def get_provider_models(self, provider_name: str) -> List[str]:
        """Get available models for a provider as list"""
        if provider_name == 'ollama':
            # For Ollama, return single model as list
            model = self.get_setting('Ollama', 'model', 'qwen2.5-vl')
            return [model]
        elif provider_name == 'claude_cli':
            models_str = self.get_setting('ClaudeCLI', 'models', '')
            return [m.strip() for m in models_str.split(',') if m.strip()]
        elif provider_name == 'gemini_cli':
            models_str = self.get_setting('GeminiCLI', 'models', '')
            return [m.strip() for m in models_str.split(',') if m.strip()]
        return []

    def get_provider_config(self, provider_name: str) -> Dict[str, Any]:
        """Get full configuration for a provider"""
        if provider_name == 'ollama':
            return {
                'model': self.get_setting('Ollama', 'model'),
                'base_url': self.get_setting('Ollama', 'base_url'),
                'timeout': int(self.get_setting('Ollama', 'timeout', '300'))
            }
        elif provider_name == 'claude_cli':
            return {
                'command_template': self.get_setting('ClaudeCLI', 'command_template'),
                'timeout': int(self.get_setting('ClaudeCLI', 'timeout', '300')),
                'models': self.get_provider_models('claude_cli'),
                'default_model': self.get_setting('ClaudeCLI', 'default_model')
            }
        elif provider_name == 'gemini_cli':
            return {
                'command_template': self.get_setting('GeminiCLI', 'command_template'),
                'timeout': int(self.get_setting('GeminiCLI', 'timeout', '300')),
                'models': self.get_provider_models('gemini_cli'),
                'default_model': self.get_setting('GeminiCLI', 'default_model')
            }
        return {}

    def get_bool(self, section: str, key: str, default: bool = False) -> bool:
        """Get a boolean setting"""
        value = self.get_setting(section, key, str(default).lower())
        return value.lower() in ('true', '1', 'yes', 'on')

    def get_int(self, section: str, key: str, default: int = 0) -> int:
        """Get an integer setting"""
        value = self.get_setting(section, key, str(default))
        try:
            return int(value)
        except ValueError:
            return default

# Example Usage (for testing during development)
if __name__ == "__main__":
    # Create a temporary config file for testing
    temp_config_file = 'temp_settings.ini'
    config_manager = ConfigManager(temp_config_file)

    print("Initial config (default or loaded):")
    print(f"Ollama Model: {config_manager.get_setting('Ollama', 'model')}")
    print(f"Scan Folder: {config_manager.get_setting('DocumentProcessing', 'scan_folder')}")
    
    config_manager.set_setting('Ollama', 'model', 'llava:latest')
    config_manager.set_setting('DocumentProcessing', 'scan_folder', 'C:\\MyScans')
    config_manager.set_setting('DocumentProcessing', 'title_keywords', 'Invoice,Receipt')

    print("\nConfig after setting new values:")
    print(f"Ollama Model: {config_manager.get_setting('Ollama', 'model')}")
    print(f"Scan Folder: {config_manager.get_setting('DocumentProcessing', 'scan_folder')}")
    print(f"Title Keywords: {config_manager.get_setting('DocumentProcessing', 'title_keywords')}")

    # Clean up temporary file
    if os.path.exists(temp_config_file):
        os.remove(temp_config_file)
