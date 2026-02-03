"""
Test Prompt Optimization Feature
Tests the AI-powered prompt optimization in settings window.
"""

import os
import sys
import unittest
from unittest.mock import Mock, MagicMock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PyQt6.QtWidgets import QApplication, QPlainTextEdit
from PyQt6.QtCore import QThread
from config_manager import ConfigManager
from settings_window_enhanced import (
    PromptOptimizationThread,
    PromptComparisonDialog
)


class TestPromptOptimization(unittest.TestCase):
    """Test prompt optimization feature"""

    @classmethod
    def setUpClass(cls):
        """Set up QApplication for tests"""
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        """Set up test fixtures"""
        self.config_manager = ConfigManager()

    def test_optimization_thread_creation(self):
        """Test that optimization thread can be created"""
        test_prompt = "Extract document metadata"

        thread = PromptOptimizationThread(
            self.config_manager,
            test_prompt
        )

        self.assertIsInstance(thread, QThread)
        self.assertEqual(thread.current_prompt, test_prompt)

    def test_comparison_dialog_creation(self):
        """Test that comparison dialog can be created"""
        original = "Original prompt text"
        optimized = "Optimized prompt text with improvements"

        dialog = PromptComparisonDialog(original, optimized)

        self.assertEqual(dialog.original_prompt, original)
        self.assertEqual(dialog.optimized_prompt, optimized)
        self.assertFalse(dialog.accepted_optimization)

    def test_comparison_dialog_get_final_prompt(self):
        """Test getting final prompt from dialog"""
        original = "Original prompt"
        optimized = "Optimized prompt"

        dialog = PromptComparisonDialog(original, optimized)
        final = dialog.get_final_prompt()

        self.assertEqual(final, optimized)

    @patch('settings_window_enhanced.ProviderFactory')
    def test_optimization_thread_success(self, mock_factory):
        """Test successful optimization"""
        # Mock provider
        mock_provider = Mock()
        mock_provider.analyze_images.return_value = {
            'success': True,
            'response': 'Improved prompt text',
            'error': None
        }
        mock_factory.create_from_config_manager.return_value = mock_provider

        # Mock config manager
        mock_config = Mock()
        mock_config.get_active_provider.return_value = 'claude_cli'

        thread = PromptOptimizationThread(mock_config, "Test prompt")

        # Capture signal
        results = []
        thread.finished.connect(lambda success, prompt, error: results.append((success, prompt, error)))

        # Run thread
        thread.run()

        # Verify results
        self.assertEqual(len(results), 1)
        success, prompt, error = results[0]
        self.assertTrue(success)
        self.assertEqual(prompt, 'Improved prompt text')
        self.assertEqual(error, '')

    @patch('settings_window_enhanced.ProviderFactory')
    def test_optimization_thread_failure(self, mock_factory):
        """Test optimization failure handling"""
        # Mock provider with failure
        mock_provider = Mock()
        mock_provider.analyze_images.return_value = {
            'success': False,
            'response': '',
            'error': 'Connection failed'
        }
        mock_factory.create_from_config_manager.return_value = mock_provider

        # Mock config manager
        mock_config = Mock()
        mock_config.get_active_provider.return_value = 'claude_cli'

        thread = PromptOptimizationThread(mock_config, "Test prompt")

        # Capture signal
        results = []
        thread.finished.connect(lambda success, prompt, error: results.append((success, prompt, error)))

        # Run thread
        thread.run()

        # Verify results
        self.assertEqual(len(results), 1)
        success, prompt, error = results[0]
        self.assertFalse(success)
        self.assertEqual(prompt, '')
        self.assertEqual(error, 'Connection failed')

    @patch('subprocess.run')
    @patch('settings_window_enhanced.ProviderFactory')
    def test_optimization_ollama_provider(self, mock_factory, mock_subprocess_run):
        """Test optimization with Ollama provider (uses subprocess)"""
        # Mock provider
        mock_provider = Mock()
        mock_provider.get_default_model.return_value = 'qwen2.5-vl'
        mock_provider.get_timeout.return_value = 300
        mock_factory.create_from_config_manager.return_value = mock_provider

        # Mock subprocess
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = 'Optimized prompt from Ollama'
        mock_subprocess_run.return_value = mock_result

        # Mock config manager
        mock_config = Mock()
        mock_config.get_active_provider.return_value = 'ollama'

        thread = PromptOptimizationThread(mock_config, "Test prompt")

        # Capture signal
        results = []
        thread.finished.connect(lambda success, prompt, error: results.append((success, prompt, error)))

        # Run thread
        thread.run()

        # Verify subprocess was called
        mock_subprocess_run.assert_called_once()

        # Verify results
        self.assertEqual(len(results), 1)
        success, prompt, error = results[0]
        self.assertTrue(success)
        self.assertEqual(prompt, 'Optimized prompt from Ollama')
        self.assertEqual(error, '')

    def test_comparison_dialog_ui_elements(self):
        """Test that comparison dialog has required UI elements"""
        dialog = PromptComparisonDialog("Original", "Optimized")

        # Check that text widgets exist
        self.assertIsNotNone(dialog.original_text)
        self.assertIsNotNone(dialog.optimized_text)

        # Check read-only states
        self.assertTrue(dialog.original_text.isReadOnly())
        self.assertFalse(dialog.optimized_text.isReadOnly())  # User can edit optimized

        # Check content
        self.assertEqual(dialog.original_text.toPlainText(), "Original")
        self.assertEqual(dialog.optimized_text.toPlainText(), "Optimized")


if __name__ == '__main__':
    unittest.main()
