import configparser
import os

class ConfigManager:
    def __init__(self, config_file='settings.ini'):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self._load_config()

    def _load_config(self):
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            self._create_default_config()
            self._save_config()

    def _create_default_config(self):
        # Default Ollama settings
        if 'Ollama' not in self.config:
            self.config['Ollama'] = {
                'model': 'qwen2.5-vl', # Default vision model
                'base_url': 'http://localhost:11434'
            }
        
        # Default Document Processing settings
        if 'DocumentProcessing' not in self.config:
            self.config['DocumentProcessing'] = {
                'scan_folder': os.path.join(os.path.expanduser('~'), 'Pictures', 'Scans'),
                'organized_subfolder': 'ORGANIZED',
                'title_keywords': 'Invoice, Statement, Bill, Receipt, Report, Contract, Agreement'
            }
        
        # Default GUI settings (can be expanded later)
        if 'GUI' not in self.config:
            self.config['GUI'] = {
                'app_name': 'WinScanOllamaVision',
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
