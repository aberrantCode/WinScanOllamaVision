import unittest
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from config_manager import ConfigManager

class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.test_config_file = 'test_settings.ini'
        if os.path.exists(self.test_config_file):
            os.remove(self.test_config_file)
        self.config_manager = ConfigManager(self.test_config_file)

    def tearDown(self):
        if os.path.exists(self.test_config_file):
            os.remove(self.test_config_file)

    def test_default_config_creation(self):
        self.assertTrue(os.path.exists(self.test_config_file))
        self.assertIn('Ollama', self.config_manager.config)
        self.assertIn('model', self.config_manager.config['Ollama'])
        self.assertIn('DocumentProcessing', self.config_manager.config)
        self.assertIn('title_keywords', self.config_manager.config['DocumentProcessing'])

    def test_get_and_set_setting(self):
        self.config_manager.set_setting('Ollama', 'model', 'llava:latest')
        self.assertEqual(self.config_manager.get_setting('Ollama', 'model'), 'llava:latest')
        
        new_config_manager = ConfigManager(self.test_config_file)
        self.assertEqual(new_config_manager.get_setting('Ollama', 'model'), 'llava:latest')

    def test_get_default_value(self):
        self.assertIsNone(self.config_manager.get_setting('NonExistentSection', 'key'))
        self.assertEqual(self.config_manager.get_setting('NonExistentSection', 'key', 'default_val'), 'default_val')

if __name__ == '__main__':
    unittest.main()
