"""
Integration tests for LLM provider integration.

Tests ConfigManager → ProviderFactory → Provider flow
"""

import configparser
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from config.config_manager import ConfigManager
from llm_providers.provider_factory import ProviderFactory


class TestProviderIntegration:
    """Integration tests for provider creation and configuration"""

    @pytest.fixture
    def temp_config_file(self):
        """Create temporary config file"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".ini") as temp_file:
            config = configparser.ConfigParser()

            # Add LLM provider configuration
            config["LLMProvider"] = {"active_provider": "ollama"}

            config["Ollama"] = {
                "base_url": "http://localhost:11434",
                "model": "qwen2.5-vl",
                "timeout": "300",
            }

            config["ClaudeCLI"] = {
                "command_template": "claude --model %%MODEL%% --image %%IMAGE_PATHS%% --prompt %%PROMPT%%",
                "default_model": "claude-3-5-sonnet-20241022",
                "models": '["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]',
                "timeout": "300",
            }

            config["GeminiCLI"] = {
                "command_template": "gemini --model %%MODEL%% --image %%IMAGE_PATHS%% --prompt %%PROMPT%%",
                "default_model": "gemini-2.0-flash-exp",
                "models": '["gemini-2.0-flash-exp", "gemini-1.5-pro"]',
                "timeout": "300",
            }

            config.write(temp_file)
            temp_file_name = temp_file.name

        yield temp_file_name

        # Cleanup
        os.unlink(temp_file_name)

    def test_config_manager_to_provider_factory_ollama(self, temp_config_file):
        """Test creating Ollama provider from ConfigManager"""
        # Arrange
        config_manager = ConfigManager(config_file=temp_config_file)

        # Act
        provider = ProviderFactory.create_from_config_manager(config_manager)

        # Assert
        assert provider.provider_name == "ollama"
        assert provider.default_model == "qwen2.5-vl"
        assert provider.base_url == "http://localhost:11434"

    def test_config_manager_to_provider_factory_claude(self, temp_config_file):
        """Test creating Claude CLI provider from ConfigManager"""
        # Arrange
        config_manager = ConfigManager(config_file=temp_config_file)

        # Act
        provider = ProviderFactory.create_from_config_manager(
            config_manager, provider_name="claude_cli"
        )

        # Assert
        assert provider.provider_name == "claudecli"
        assert provider.default_model == "claude-3-5-sonnet-20241022"
        assert "%MODEL%" in provider.command_template  # ConfigParser converts %% to %

    def test_config_manager_to_provider_factory_gemini(self, temp_config_file):
        """Test creating Gemini CLI provider from ConfigManager"""
        # Arrange
        config_manager = ConfigManager(config_file=temp_config_file)

        # Act
        provider = ProviderFactory.create_from_config_manager(
            config_manager, provider_name="gemini_cli"
        )

        # Assert
        assert provider.provider_name == "geminicli"
        assert provider.default_model == "gemini-2.0-flash-exp"

    def test_provider_validation_with_config_manager(self, temp_config_file):
        """Test provider validation from ConfigManager"""
        # Arrange
        config_manager = ConfigManager(config_file=temp_config_file)

        # Act
        provider = ProviderFactory.create_from_config_manager(config_manager)
        is_valid, error = provider.validate_config()

        # Assert
        assert is_valid is True
        assert error is None

    @patch("llm_providers.ollama_provider.OllamaService")  # Patch where it's used
    def test_provider_analyze_with_mocked_service(self, mock_ollama_service, temp_config_file):
        """Test provider analyze_images with mocked service"""
        # Arrange
        config_manager = ConfigManager(config_file=temp_config_file)

        # Mock OllamaService
        mock_service_instance = MagicMock()
        mock_service_instance.chat_with_vision_model.return_value = {
            "content": '{"company": "TestCo", "document_type": "invoice"}'
        }
        mock_ollama_service.return_value = mock_service_instance

        # Act
        provider = ProviderFactory.create_from_config_manager(config_manager)
        result = provider.analyze_images(image_paths=["test.png"], prompt="Analyze this")

        # Assert
        assert result["success"] is True
        assert result["metadata"]["company"] == "TestCo"
        assert result["metadata"]["document_type"] == "invoice"

    def test_provider_factory_unknown_provider_raises(self):
        """Test that unknown provider raises ValueError"""
        # Act & Assert
        with pytest.raises(ValueError, match="Unknown provider type"):
            ProviderFactory.create_provider("unknown_provider", {})

    @patch("config.appdata_manager.AppDataManager")
    def test_provider_factory_missing_config_raises(self, mock_appdata):
        """Test that missing config raises ValueError"""
        # Arrange
        mock_appdata.return_value.get_config_path.return_value = "nonexistent.ini"
        config_manager = MagicMock(spec=ConfigManager)
        config_manager.get_active_provider.return_value = "ollama"
        config_manager.get_provider_config.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="No configuration found"):
            ProviderFactory.create_from_config_manager(config_manager)

    @patch("subprocess.run")
    def test_claude_cli_provider_subprocess_integration(self, mock_subprocess, temp_config_file):
        """Test Claude CLI provider subprocess execution"""
        # Arrange
        config_manager = ConfigManager(config_file=temp_config_file)

        # Mock subprocess response
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout='{"company": "TestCo"}',
            stderr="",
        )

        # Act
        provider = ProviderFactory.create_from_config_manager(
            config_manager, provider_name="claude_cli"
        )
        result = provider.analyze_images(image_paths=["test.png"], prompt="Analyze this")

        # Assert
        assert mock_subprocess.called
        assert result["success"] is True

    @patch("subprocess.run")
    def test_gemini_cli_provider_subprocess_integration(self, mock_subprocess, temp_config_file):
        """Test Gemini CLI provider subprocess execution"""
        # Arrange
        config_manager = ConfigManager(config_file=temp_config_file)

        # Mock subprocess response
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout='{"company": "TestCo"}',
            stderr="",
        )

        # Act
        provider = ProviderFactory.create_from_config_manager(
            config_manager, provider_name="gemini_cli"
        )
        result = provider.analyze_images(image_paths=["test.png"], prompt="Analyze this")

        # Assert
        assert mock_subprocess.called
        assert result["success"] is True

    @patch("llm_providers.ollama_provider.OllamaService")  # Patch where it's used
    def test_provider_get_available_models(self, mock_ollama_service):
        """Test getting available models from provider"""
        # Arrange
        mock_service_instance = MagicMock()
        mock_service_instance.list_models.return_value = [
            {"name": "model1"},
            {"name": "model2"},
        ]
        mock_ollama_service.return_value = mock_service_instance

        config = {
            "base_url": "http://localhost:11434",
            "model": "qwen2.5-vl",
            "timeout": 300,
        }

        # Act
        provider = ProviderFactory.create_provider("ollama", config)
        models = provider.get_available_models()

        # Assert
        assert models == ["model1", "model2"]

    @patch("llm_providers.ollama_provider.OllamaService")  # Patch where it's used
    def test_provider_test_connection(self, mock_ollama_service):
        """Test provider connection testing"""
        # Arrange
        mock_service_instance = MagicMock()
        mock_service_instance.list_models.return_value = []
        mock_ollama_service.return_value = mock_service_instance

        config = {
            "base_url": "http://localhost:11434",
            "model": "qwen2.5-vl",
            "timeout": 300,
        }

        # Act
        provider = ProviderFactory.create_provider("ollama", config)
        connected = provider.test_connection()

        # Assert
        assert connected is True
        mock_service_instance.list_models.assert_called_once()

    def test_all_provider_types_are_available(self):
        """Test that all provider types are registered"""
        # Act
        types = ProviderFactory.get_available_provider_types()

        # Assert
        assert "ollama" in types
        assert "claude_cli" in types
        assert "gemini_cli" in types
        assert len(types) == 3

    def test_switching_providers_at_runtime(self, temp_config_file):
        """Test switching between providers at runtime"""
        # Arrange
        config_manager = ConfigManager(config_file=temp_config_file)

        # Act - Create different providers
        ollama_provider = ProviderFactory.create_from_config_manager(
            config_manager, provider_name="ollama"
        )
        claude_provider = ProviderFactory.create_from_config_manager(
            config_manager, provider_name="claude_cli"
        )
        gemini_provider = ProviderFactory.create_from_config_manager(
            config_manager, provider_name="gemini_cli"
        )

        # Assert
        assert ollama_provider.provider_name == "ollama"
        assert claude_provider.provider_name == "claudecli"
        assert gemini_provider.provider_name == "geminicli"
