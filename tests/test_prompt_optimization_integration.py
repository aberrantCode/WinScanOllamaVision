"""
Integration Test for Prompt Optimization UI
Tests the complete user flow from button click to prompt update.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog
from PyQt6.QtCore import Qt
from settings_window_enhanced import EnhancedSettingsWindow


class TestPromptOptimizationIntegration(unittest.TestCase):
    """Integration tests for prompt optimization UI"""

    @classmethod
    def setUpClass(cls):
        """Set up QApplication for tests"""
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        """Set up test fixtures"""
        self.window = EnhancedSettingsWindow()

    def tearDown(self):
        """Clean up"""
        self.window.close()

    def test_settings_window_has_prompt_editors(self):
        """Test that settings window has prompt editors"""
        # Navigate to LLM Provider tab (index 1)
        self.window.tab_widget.setCurrentIndex(1)

        # Check that prompt editors exist
        self.assertIsNotNone(self.window.pages_prompt_edit)
        self.assertIsNotNone(self.window.metadata_prompt_edit)

    def test_empty_prompt_shows_warning(self):
        """Test that empty prompt shows warning dialog"""
        # Navigate to LLM Provider tab
        self.window.tab_widget.setCurrentIndex(1)

        # Clear the prompt
        self.window.pages_prompt_edit.setPlainText("")

        # Mock QMessageBox to capture the warning
        with patch.object(QMessageBox, 'warning') as mock_warning:
            self.window._optimize_prompt(self.window.pages_prompt_edit)

            # Verify warning was shown
            mock_warning.assert_called_once()
            call_args = mock_warning.call_args[0]
            self.assertIn("Empty Prompt", call_args[1])

    def test_optimize_prompt_shows_confirmation(self):
        """Test that optimize prompt shows confirmation dialog"""
        # Navigate to LLM Provider tab
        self.window.tab_widget.setCurrentIndex(1)

        # Set a test prompt
        test_prompt = "Extract document metadata"
        self.window.pages_prompt_edit.setPlainText(test_prompt)

        # Mock QMessageBox.question to simulate user clicking "No"
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No):
            # Should not proceed if user clicks No
            with patch('settings_window_enhanced.PromptOptimizationThread') as mock_thread:
                self.window._optimize_prompt(self.window.pages_prompt_edit)

                # Thread should not be created if user cancels
                mock_thread.assert_not_called()

    @patch('settings_window_enhanced.ProviderFactory')
    @patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes)
    @patch.object(QMessageBox, 'information')
    def test_successful_optimization_flow(self, mock_info, mock_question, mock_factory):
        """Test complete successful optimization flow"""
        # Mock provider
        mock_provider = Mock()
        mock_provider.analyze_images.return_value = {
            'success': True,
            'response': 'Improved prompt with better clarity',
            'error': None
        }
        mock_factory.create_from_config_manager.return_value = mock_provider

        # Navigate to LLM Provider tab
        self.window.tab_widget.setCurrentIndex(1)

        # Set a test prompt
        original_prompt = "Extract metadata"
        self.window.pages_prompt_edit.setPlainText(original_prompt)

        # Mock the comparison dialog to auto-accept
        with patch('settings_window_enhanced.PromptComparisonDialog') as mock_dialog_class:
            mock_dialog_instance = Mock()
            mock_dialog_instance.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog_instance.get_final_prompt.return_value = "Improved prompt with better clarity"
            mock_dialog_class.return_value = mock_dialog_instance

            # Start optimization
            self.window._optimize_prompt(self.window.pages_prompt_edit)

            # Wait for thread to complete (simulate by calling handler directly)
            self.window._handle_optimization_result(
                success=True,
                optimized_prompt="Improved prompt with better clarity",
                error_message="",
                progress_dialog=Mock()
            )

            # Verify prompt was updated
            self.assertEqual(
                self.window.pages_prompt_edit.toPlainText(),
                "Improved prompt with better clarity"
            )

    @patch('settings_window_enhanced.ProviderFactory')
    @patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes)
    @patch.object(QMessageBox, 'critical')
    def test_optimization_failure_shows_error(self, mock_critical, mock_question, mock_factory):
        """Test that optimization failure shows error dialog"""
        # Mock provider failure
        mock_provider = Mock()
        mock_provider.analyze_images.return_value = {
            'success': False,
            'response': '',
            'error': 'Connection timeout'
        }
        mock_factory.create_from_config_manager.return_value = mock_provider

        # Navigate to LLM Provider tab
        self.window.tab_widget.setCurrentIndex(1)

        # Set a test prompt
        self.window.pages_prompt_edit.setPlainText("Test prompt")

        # Start optimization and simulate failure
        self.window._optimize_prompt(self.window.pages_prompt_edit)

        # Simulate thread completion with error
        self.window._handle_optimization_result(
            success=False,
            optimized_prompt="",
            error_message="Connection timeout",
            progress_dialog=Mock()
        )

        # Verify error dialog was shown
        mock_critical.assert_called_once()
        call_args = mock_critical.call_args[0]
        self.assertIn("Optimization Failed", call_args[1])

    def test_comparison_dialog_user_can_edit(self):
        """Test that user can edit optimized prompt in comparison dialog"""
        from settings_window_enhanced import PromptComparisonDialog

        original = "Original prompt"
        optimized = "Optimized prompt"

        dialog = PromptComparisonDialog(original, optimized)

        # Simulate user editing the optimized prompt
        edited_prompt = "User edited optimized prompt"
        dialog.optimized_text.setPlainText(edited_prompt)

        # Accept the dialog
        dialog._accept_optimization()

        # Verify the edited prompt is returned
        self.assertEqual(dialog.get_final_prompt(), edited_prompt)
        self.assertTrue(dialog.accepted_optimization)

    def test_all_three_providers_supported(self):
        """Test that all three providers are supported for optimization"""
        providers = ['ollama', 'claude_cli', 'gemini_cli']

        for provider in providers:
            with self.subTest(provider=provider):
                # Set active provider
                self.window.config_manager.set_active_provider(provider)

                # Get active provider
                active = self.window.config_manager.get_active_provider()
                self.assertEqual(active, provider)


if __name__ == '__main__':
    unittest.main()
