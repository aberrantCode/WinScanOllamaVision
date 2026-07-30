"""
Tests for OllamaProvider.

Target: 90%+ coverage with mocked HTTP calls
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from llm_providers.ollama_provider import OllamaProvider


class TestOllamaProvider:
    """Test suite for OllamaProvider"""

    @pytest.fixture
    def config(self):
        """Provide default test configuration"""
        return {
            "base_url": "http://localhost:11434",
            "timeout": 60,
            "model": "qwen2.5vl:latest",
        }

    @pytest.fixture
    def provider(self, config):
        """Create OllamaProvider instance with mocked service"""
        with patch("llm_providers.ollama_provider.OllamaService"):
            return OllamaProvider(config)

    def test_init_sets_config_values(self, config):
        # Arrange & Act
        with patch("llm_providers.ollama_provider.OllamaService"):
            provider = OllamaProvider(config)

        # Assert
        assert provider.base_url == "http://localhost:11434"
        assert provider.timeout == 60
        assert provider.default_model == "qwen2.5vl:latest"

    def test_init_uses_defaults_when_not_provided(self):
        # Arrange
        config = {}

        # Act
        with patch("llm_providers.ollama_provider.OllamaService"):
            provider = OllamaProvider(config)

        # Assert
        assert provider.base_url == "http://localhost:11434"
        assert provider.timeout == 300
        assert provider.default_model == "qwen2.5vl:latest"

    def test_init_creates_ollama_service(self, config):
        # Arrange & Act
        with patch("llm_providers.ollama_provider.OllamaService") as mock_service:
            provider = OllamaProvider(config)

        # Assert
        mock_service.assert_called_once_with(base_url="http://localhost:11434", timeout=60.0)
        assert provider.service == mock_service.return_value

    def test_analyze_images_success_with_valid_json(self, provider):
        # Arrange
        image_paths = ["/path/to/image1.jpg", "/path/to/image2.jpg"]
        prompt = "Analyze these images"
        model = "test-model"

        metadata = {"title": "Test Document", "date": "2024-01-01"}
        provider.service.chat_with_vision_model = MagicMock(
            return_value={"content": json.dumps(metadata)}
        )

        # Act
        result = provider.analyze_images(image_paths, prompt, model)

        # Assert
        assert result["success"] is True
        assert result["response"] == json.dumps(metadata)
        assert result["metadata"] == metadata
        assert result["model_used"] == "test-model"
        assert result["processing_time_ms"] >= 0
        assert result["error"] is None

        provider.service.chat_with_vision_model.assert_called_once_with(
            model_name="test-model",
            image_paths=image_paths,
            prompt=prompt,
            format_json=True,
        )

    def test_analyze_images_uses_default_model_when_not_specified(self, provider):
        # Arrange
        image_paths = ["/path/to/image.jpg"]
        prompt = "Test prompt"
        provider.service.chat_with_vision_model = MagicMock(return_value={"content": "{}"})

        # Act
        result = provider.analyze_images(image_paths, prompt)

        # Assert
        assert result["model_used"] == "qwen2.5vl:latest"
        provider.service.chat_with_vision_model.assert_called_once_with(
            model_name="qwen2.5vl:latest",
            image_paths=image_paths,
            prompt=prompt,
            format_json=True,
        )

    def test_analyze_images_handles_json_with_markdown_fences(self, provider):
        # Arrange
        image_paths = ["/path/to/image.jpg"]
        prompt = "Test"
        metadata = {"key": "value"}
        response_with_fences = f"```json\n{json.dumps(metadata)}\n```"

        provider.service.chat_with_vision_model = MagicMock(
            return_value={"content": response_with_fences}
        )

        # Act
        result = provider.analyze_images(image_paths, prompt)

        # Assert
        assert result["success"] is True
        assert result["metadata"] == metadata

    def test_analyze_images_handles_malformed_json(self, provider):
        # Arrange
        image_paths = ["/path/to/image.jpg"]
        prompt = "Test"
        invalid_json = "This is not JSON"

        provider.service.chat_with_vision_model = MagicMock(return_value={"content": invalid_json})

        # Act
        result = provider.analyze_images(image_paths, prompt)

        # Assert
        assert result["success"] is True
        assert result["metadata"] == {"raw_content": invalid_json}

    def test_analyze_images_returns_error_on_exception(self, provider):
        # Arrange
        image_paths = ["/path/to/image.jpg"]
        prompt = "Test"
        provider.service.chat_with_vision_model = MagicMock(
            side_effect=ConnectionError("Server unreachable")
        )

        # Act
        result = provider.analyze_images(image_paths, prompt)

        # Assert
        assert result["success"] is False
        assert result["error"] == "Server unreachable"
        assert result["response"] == ""
        assert result["metadata"] == {}
        assert result["processing_time_ms"] >= 0

    def test_get_default_model_returns_configured_model(self, provider):
        # Act
        result = provider.get_default_model()

        # Assert
        assert result == "qwen2.5vl:latest"

    def test_get_available_models_returns_model_list(self, provider):
        # Arrange
        models = [
            {"name": "model1"},
            {"name": "model2"},
            {"name": "model3"},
        ]
        provider.service.list_models = MagicMock(return_value=models)

        # Act
        result = provider.get_available_models()

        # Assert
        assert result == ["model1", "model2", "model3"]
        provider.service.list_models.assert_called_once()

    def test_get_available_models_handles_real_sdk_response_shape(self, provider):
        """The ollama SDK's list() items key the tag under 'model', not 'name'
        (['name'] raises KeyError against a real response). Regression for
        get_available_models() always returning [] against a live server."""
        # Arrange
        models = [
            {"model": "qwen2.5vl:latest"},
            {"model": "llama3.1:8b"},
        ]
        provider.service.list_models = MagicMock(return_value=models)

        # Act
        result = provider.get_available_models()

        # Assert
        assert result == ["qwen2.5vl:latest", "llama3.1:8b"]

    def test_get_available_models_returns_empty_on_error(self, provider):
        # Arrange
        provider.service.list_models = MagicMock(side_effect=ConnectionError("Server down"))

        # Act
        result = provider.get_available_models()

        # Assert
        assert result == []

    def test_test_connection_returns_true_on_success(self, provider):
        # Arrange
        provider.service.list_models = MagicMock(return_value=[])

        # Act
        result = provider.test_connection()

        # Assert
        assert result is True

    def test_test_connection_returns_false_on_failure(self, provider):
        # Arrange
        provider.service.list_models = MagicMock(side_effect=ConnectionError())

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

    def test_validate_config_fails_when_model_missing(self):
        # Arrange
        config = {"base_url": "http://localhost:11434"}

        with patch("llm_providers.ollama_provider.OllamaService"):
            provider = OllamaProvider(config)
            provider.default_model = None

        # Act
        is_valid, error = provider.validate_config()

        # Assert
        assert is_valid is False
        assert error == "Model name is required"

    def test_validate_config_fails_with_invalid_base_url(self):
        # Arrange
        config = {"base_url": "not-a-url", "model": "test"}

        with patch("llm_providers.ollama_provider.OllamaService"):
            provider = OllamaProvider(config)

        # Act
        is_valid, error = provider.validate_config()

        # Assert
        assert is_valid is False
        assert "Invalid base_url" in error

    def test_validate_config_fails_with_empty_base_url(self):
        # Arrange
        config = {"base_url": "", "model": "test"}

        with patch("llm_providers.ollama_provider.OllamaService"):
            provider = OllamaProvider(config)

        # Act
        is_valid, error = provider.validate_config()

        # Assert
        assert is_valid is False
        assert "Invalid base_url" in error

    def test_validate_grouping_delegates_to_service(self, provider):
        # Arrange
        image_paths = ["/path/to/img1.jpg", "/path/to/img2.jpg"]
        custom_prompt = "Custom grouping prompt"
        provider.service.validate_grouping = MagicMock(return_value=True)

        # Act
        result = provider.validate_grouping(image_paths, custom_prompt)

        # Assert
        assert result is True
        provider.service.validate_grouping.assert_called_once_with(
            "qwen2.5vl:latest", image_paths, custom_prompt
        )

    def test_validate_grouping_with_page_number_delegates_to_service(self, provider):
        # Arrange
        image_paths = ["/path/to/img1.jpg"]
        expected_result = {"same_document": True, "metadata": {"page": 1}}
        provider.service.validate_grouping_with_page_number = MagicMock(
            return_value=expected_result
        )

        # Act
        result = provider.validate_grouping_with_page_number(image_paths)

        # Assert
        assert result == expected_result
        provider.service.validate_grouping_with_page_number.assert_called_once_with(
            "qwen2.5vl:latest", image_paths, None
        )

    def test_extract_document_info_delegates_to_service(self, provider):
        # Arrange
        image_paths = ["/path/to/img.jpg"]
        title_keywords = "invoice,receipt"
        expected_result = {"title": "Invoice", "date": "2024-01-01"}
        provider.service.extract_document_info = MagicMock(return_value=expected_result)

        # Act
        result = provider.extract_document_info(image_paths, title_keywords)

        # Assert
        assert result == expected_result
        provider.service.extract_document_info.assert_called_once_with(
            "qwen2.5vl:latest", image_paths, title_keywords
        )
