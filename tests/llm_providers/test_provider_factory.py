"""
Tests for ProviderFactory.

Target: 100% coverage of factory logic
"""

from unittest.mock import MagicMock

import pytest

from llm_providers.provider_factory import ProviderFactory


class TestProviderFactory:
    """Test suite for ProviderFactory"""

    def test_create_provider_ollama(self):
        # Arrange
        provider_type = "ollama"
        config = {"base_url": "http://localhost:11434", "model": "test-model"}

        # Act
        from llm_providers.ollama_provider import OllamaProvider

        provider = ProviderFactory.create_provider(provider_type, config)

        # Assert
        assert isinstance(provider, OllamaProvider)

    def test_create_provider_claude_cli(self):
        # Arrange
        provider_type = "claude_cli"
        config = {"command_template": "claude {model} {prompt}", "default_model": "claude-3"}

        # Act
        from llm_providers.claude_cli_provider import ClaudeCliProvider

        provider = ProviderFactory.create_provider(provider_type, config)

        # Assert
        assert isinstance(provider, ClaudeCliProvider)

    def test_create_provider_gemini_cli(self):
        # Arrange
        provider_type = "gemini_cli"
        config = {"command_template": "gemini {model} {prompt}", "default_model": "gemini-pro"}

        # Act
        from llm_providers.gemini_cli_provider import GeminiCliProvider

        provider = ProviderFactory.create_provider(provider_type, config)

        # Assert
        assert isinstance(provider, GeminiCliProvider)

    def test_create_provider_case_insensitive(self):
        # Arrange
        provider_type = "OLLAMA"  # Uppercase
        config = {"base_url": "http://localhost:11434"}

        # Act
        from llm_providers.ollama_provider import OllamaProvider

        provider = ProviderFactory.create_provider(provider_type, config)

        # Assert
        assert isinstance(provider, OllamaProvider)

    def test_create_provider_raises_on_unknown_type(self):
        # Arrange
        provider_type = "unknown_provider"
        config = {}

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            ProviderFactory.create_provider(provider_type, config)

        assert "Unknown provider type" in str(exc_info.value)
        assert "unknown_provider" in str(exc_info.value)
        assert "ollama" in str(exc_info.value)  # Should list available providers

    def test_create_from_config_manager_uses_active_provider(self):
        # Arrange
        config_manager = MagicMock()
        config_manager.get_active_provider.return_value = "ollama"
        config_manager.get_provider_config.return_value = {
            "base_url": "http://localhost:11434",
            "model": "test",
        }

        # Act
        from llm_providers.ollama_provider import OllamaProvider

        provider = ProviderFactory.create_from_config_manager(config_manager)

        # Assert
        assert isinstance(provider, OllamaProvider)
        config_manager.get_active_provider.assert_called_once()
        config_manager.get_provider_config.assert_called_once_with("ollama")

    def test_create_from_config_manager_uses_specified_provider(self):
        # Arrange
        config_manager = MagicMock()
        config_manager.get_provider_config.return_value = {
            "command_template": "claude",
            "default_model": "claude-3",
        }

        # Act
        from llm_providers.claude_cli_provider import ClaudeCliProvider

        provider = ProviderFactory.create_from_config_manager(config_manager, "claude_cli")

        # Assert
        assert isinstance(provider, ClaudeCliProvider)
        config_manager.get_active_provider.assert_not_called()
        config_manager.get_provider_config.assert_called_once_with("claude_cli")

    def test_create_from_config_manager_raises_on_unknown_provider_name(self):
        # Arrange
        config_manager = MagicMock()
        config_manager.get_active_provider.return_value = "unknown"

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            ProviderFactory.create_from_config_manager(config_manager)

        assert "Unknown provider name" in str(exc_info.value)
        assert "unknown" in str(exc_info.value)

    def test_create_from_config_manager_raises_on_missing_config(self):
        # Arrange
        config_manager = MagicMock()
        config_manager.get_active_provider.return_value = "ollama"
        config_manager.get_provider_config.return_value = None

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            ProviderFactory.create_from_config_manager(config_manager)

        assert "No configuration found" in str(exc_info.value)
        assert "ollama" in str(exc_info.value)

    def test_get_available_provider_types_returns_all_types(self):
        # Act
        types = ProviderFactory.get_available_provider_types()

        # Assert
        assert "ollama" in types
        assert "claude_cli" in types
        assert "gemini_cli" in types
        assert len(types) == 3

    def test_validate_provider_type_returns_true_for_valid_types(self):
        # Act & Assert
        assert ProviderFactory.validate_provider_type("ollama") is True
        assert ProviderFactory.validate_provider_type("claude_cli") is True
        assert ProviderFactory.validate_provider_type("gemini_cli") is True

    def test_validate_provider_type_returns_true_case_insensitive(self):
        # Act & Assert
        assert ProviderFactory.validate_provider_type("OLLAMA") is True
        assert ProviderFactory.validate_provider_type("Claude_CLI") is True

    def test_validate_provider_type_returns_false_for_invalid_type(self):
        # Act & Assert
        assert ProviderFactory.validate_provider_type("unknown") is False
        assert ProviderFactory.validate_provider_type("") is False
        assert ProviderFactory.validate_provider_type("gpt4") is False

    def test_provider_classes_dict_contains_all_providers(self):
        # Act
        provider_classes = ProviderFactory.PROVIDER_CLASSES

        # Assert
        assert "ollama" in provider_classes
        assert "claude_cli" in provider_classes
        assert "gemini_cli" in provider_classes
        assert len(provider_classes) == 3

    def test_provider_type_mapping_in_create_from_config_manager(self):
        # Arrange
        config_manager = MagicMock()
        config_manager.get_active_provider.return_value = "ollama"
        config_manager.get_provider_config.return_value = {
            "base_url": "http://localhost:11434",
            "model": "test",
        }

        # Act
        provider = ProviderFactory.create_from_config_manager(config_manager)

        # Assert
        from llm_providers.ollama_provider import OllamaProvider

        assert isinstance(provider, OllamaProvider)

    def test_create_from_config_manager_with_each_provider_name(self):
        # Test ollama
        config_manager = MagicMock()
        config_manager.get_provider_config.return_value = {
            "base_url": "http://localhost:11434",
            "model": "test",
        }
        provider = ProviderFactory.create_from_config_manager(config_manager, "ollama")
        from llm_providers.ollama_provider import OllamaProvider

        assert isinstance(provider, OllamaProvider)

        # Test claude_cli
        config_manager.get_provider_config.return_value = {
            "command_template": "claude --model %MODEL% --prompt %PROMPT% %IMAGE_PATHS%",
            "default_model": "claude-3",
        }
        provider = ProviderFactory.create_from_config_manager(config_manager, "claude_cli")
        from llm_providers.claude_cli_provider import ClaudeCliProvider

        assert isinstance(provider, ClaudeCliProvider)

        # Test gemini_cli
        config_manager.get_provider_config.return_value = {
            "command_template": "gemini --model %MODEL% --prompt %PROMPT% %IMAGE_PATHS%",
            "default_model": "gemini-pro",
        }
        provider = ProviderFactory.create_from_config_manager(config_manager, "gemini_cli")
        from llm_providers.gemini_cli_provider import GeminiCliProvider

        assert isinstance(provider, GeminiCliProvider)
