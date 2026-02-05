"""
Tests for BaseLLMProvider abstract base class.

Target: 100% coverage of non-abstract methods
"""

import pytest

from llm_providers.base_provider import BaseLLMProvider


# Concrete implementation for testing
class TestProvider(BaseLLMProvider):
    """Test implementation of BaseLLMProvider"""

    def analyze_images(self, image_paths, prompt, model=None):
        return {"success": True}

    def get_available_models(self):
        return ["model1", "model2"]

    def test_connection(self):
        return True


class TestBaseLLMProvider:
    """Test suite for BaseLLMProvider"""

    def test_init_sets_config(self):
        # Arrange
        config = {"model": "test-model", "timeout": 60}

        # Act
        provider = TestProvider(config)

        # Assert
        assert provider.config == config

    def test_init_sets_provider_name_from_class(self):
        # Arrange
        config = {}

        # Act
        provider = TestProvider(config)

        # Assert
        assert provider.provider_name == "test"

    def test_get_default_model_returns_from_config(self):
        # Arrange
        config = {"default_model": "gpt-4"}
        provider = TestProvider(config)

        # Act
        result = provider.get_default_model()

        # Assert
        assert result == "gpt-4"

    def test_get_default_model_returns_none_when_not_set(self):
        # Arrange
        config = {}
        provider = TestProvider(config)

        # Act
        result = provider.get_default_model()

        # Assert
        assert result is None

    def test_get_timeout_returns_from_config(self):
        # Arrange
        config = {"timeout": 120}
        provider = TestProvider(config)

        # Act
        result = provider.get_timeout()

        # Assert
        assert result == 120

    def test_get_timeout_returns_default_when_not_set(self):
        # Arrange
        config = {}
        provider = TestProvider(config)

        # Act
        result = provider.get_timeout()

        # Assert
        assert result == 300  # Default timeout

    def test_validate_config_fails_when_empty(self):
        # Arrange
        provider = TestProvider({})
        provider.config = None

        # Act
        is_valid, error = provider.validate_config()

        # Assert
        assert is_valid is False
        assert error == "Configuration is empty"

    def test_validate_config_succeeds_with_config(self):
        # Arrange
        config = {"model": "test"}
        provider = TestProvider(config)

        # Act
        is_valid, error = provider.validate_config()

        # Assert
        assert is_valid is True
        assert error is None

    def test_str_returns_class_name_and_provider(self):
        # Arrange
        provider = TestProvider({})

        # Act
        result = str(provider)

        # Assert
        assert result == "TestProvider(provider=test)"

    def test_repr_returns_same_as_str(self):
        # Arrange
        provider = TestProvider({})

        # Act
        result = repr(provider)

        # Assert
        assert result == str(provider)

    def test_cannot_instantiate_base_class_directly(self):
        # Arrange & Act & Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseLLMProvider({})
