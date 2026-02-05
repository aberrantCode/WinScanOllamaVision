"""
Tests for ClaudeCliProvider.

Target: 90%+ coverage with mocked subprocess calls
"""

import json
import subprocess
from unittest.mock import Mock, patch

import pytest

from llm_providers.claude_cli_provider import ClaudeCliProvider


class TestClaudeCliProvider:
    """Test suite for ClaudeCliProvider"""

    @pytest.fixture
    def config(self):
        """Provide default test configuration"""
        return {
            "command_template": "claude --model %MODEL% --prompt %PROMPT% %IMAGE_PATHS%",
            "timeout": 60,
            "default_model": "claude-3-5-sonnet-20241022",
            "models": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
        }

    @pytest.fixture
    def provider(self, config):
        """Create ClaudeCliProvider instance"""
        return ClaudeCliProvider(config)

    def test_init_sets_config_values(self, config):
        # Act
        provider = ClaudeCliProvider(config)

        # Assert
        assert provider.command_template == config["command_template"]
        assert provider.timeout == 60
        assert provider.default_model == "claude-3-5-sonnet-20241022"
        assert provider.available_models == config["models"]

    def test_init_uses_defaults_when_not_provided(self):
        # Arrange
        config = {}

        # Act
        provider = ClaudeCliProvider(config)

        # Assert
        assert provider.command_template == ""
        assert provider.timeout == 300
        assert provider.default_model == "claude-3-5-sonnet-20241022"
        assert provider.available_models == []

    @patch("llm_providers.claude_cli_provider.subprocess.run")
    def test_analyze_images_success_with_json(self, mock_run, provider):
        # Arrange
        image_paths = ["/path/to/image.jpg"]
        prompt = "Analyze this"
        model = "claude-3-5-sonnet-20241022"

        metadata = {"title": "Test Doc", "date": "2024-01-01"}
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(metadata)
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Act
        result = provider.analyze_images(image_paths, prompt, model)

        # Assert
        assert result["success"] is True
        assert result["response"] == json.dumps(metadata)
        assert result["metadata"] == metadata
        assert result["model_used"] == model
        assert result["processing_time_ms"] >= 0
        assert result["error"] is None
        mock_run.assert_called_once()

    @patch("llm_providers.claude_cli_provider.subprocess.run")
    def test_analyze_images_uses_default_model(self, mock_run, provider):
        # Arrange
        image_paths = ["/path/to/image.jpg"]
        prompt = "Test"
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "{}"
        mock_run.return_value = mock_result

        # Act
        result = provider.analyze_images(image_paths, prompt)

        # Assert
        assert result["model_used"] == "claude-3-5-sonnet-20241022"

    @patch("llm_providers.claude_cli_provider.subprocess.run")
    def test_analyze_images_handles_non_json_response(self, mock_run, provider):
        # Arrange
        image_paths = ["/path/to/image.jpg"]
        prompt = "Test"
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "This is plain text"
        mock_run.return_value = mock_result

        # Act
        result = provider.analyze_images(image_paths, prompt)

        # Assert
        assert result["success"] is True
        assert result["metadata"] == {"raw_content": "This is plain text"}

    @patch("llm_providers.claude_cli_provider.subprocess.run")
    def test_analyze_images_handles_cli_error(self, mock_run, provider):
        # Arrange
        image_paths = ["/path/to/image.jpg"]
        prompt = "Test"
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "CLI error occurred"
        mock_run.return_value = mock_result

        # Act
        result = provider.analyze_images(image_paths, prompt)

        # Assert
        assert result["success"] is False
        assert "CLI returned error code 1" in result["error"]
        assert "CLI error occurred" in result["error"]
        assert result["response"] == "CLI error occurred"
        assert result["metadata"] == {}

    @patch("llm_providers.claude_cli_provider.subprocess.run")
    def test_analyze_images_handles_timeout(self, mock_run, provider):
        # Arrange
        image_paths = ["/path/to/image.jpg"]
        prompt = "Test"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=60)

        # Act
        result = provider.analyze_images(image_paths, prompt)

        # Assert
        assert result["success"] is False
        assert "TimeoutExpired" in result["error"] or "timed out" in result["error"].lower()

    @patch("llm_providers.claude_cli_provider.subprocess.run")
    def test_analyze_images_handles_subprocess_error(self, mock_run, provider):
        # Arrange
        image_paths = ["/path/to/image.jpg"]
        prompt = "Test"
        mock_run.side_effect = Exception("Subprocess failed")

        # Act
        result = provider.analyze_images(image_paths, prompt)

        # Assert
        assert result["success"] is False
        assert "Subprocess failed" in result["error"]

    def test_get_default_model_returns_configured_model(self, provider):
        # Act
        result = provider.get_default_model()

        # Assert
        assert result == "claude-3-5-sonnet-20241022"

    def test_get_available_models_returns_model_list(self, provider):
        # Act
        result = provider.get_available_models()

        # Assert
        assert result == ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]

    @patch("llm_providers.claude_cli_provider.subprocess.run")
    def test_test_connection_runs_version_check(self, mock_run, provider):
        # Arrange
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # Act
        result = provider.test_connection()

        # Assert
        assert result is True
        # Should call 'claude --version'
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "claude --version" in str(call_args)

    @patch("llm_providers.claude_cli_provider.subprocess.run")
    def test_test_connection_returns_true_on_success(self, mock_run, provider):
        # Arrange
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "OK"
        mock_run.return_value = mock_result

        # Act
        result = provider.test_connection()

        # Assert
        assert result is True

    @patch("llm_providers.claude_cli_provider.subprocess.run")
    def test_test_connection_returns_false_on_failure(self, mock_run, provider):
        # Arrange
        mock_run.side_effect = Exception("Connection failed")

        # Act
        result = provider.test_connection()

        # Assert
        assert result is False

    def test_validate_config_succeeds_with_valid_config(self, provider):
        # Act
        is_valid, error = provider.validate_config()

        # Assert
        assert is_valid is True
        assert error is None

    def test_validate_config_fails_without_command_template(self):
        # Arrange
        config = {"command_template": ""}
        provider = ClaudeCliProvider(config)

        # Act
        is_valid, error = provider.validate_config()

        # Assert
        assert is_valid is False
        assert "Template is empty" in error

    def test_validate_config_fails_when_default_model_not_in_list(self):
        # Arrange
        config = {
            "command_template": "claude --model %MODEL% --prompt %PROMPT% %IMAGE_PATHS%",
            "default_model": "unknown-model",
            "models": ["model1", "model2"],
        }
        provider = ClaudeCliProvider(config)

        # Act
        is_valid, error = provider.validate_config()

        # Assert
        assert is_valid is False
        assert "not in available models list" in error
