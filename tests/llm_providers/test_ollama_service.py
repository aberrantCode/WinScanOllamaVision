"""
Tests for OllamaService — thin wrapper around the ollama SDK client.

Target: cover list_models() pass-through and pull_model()'s post-pull
verification, in particular against the real SDK's response shape (items
keyed "model", not "name").
"""

from unittest.mock import MagicMock, patch

import pytest

from llm_providers.ollama_service import OllamaService


class TestOllamaService:
    """Test suite for OllamaService"""

    @pytest.fixture
    def service(self):
        with patch("llm_providers.ollama_service.ollama.Client"):
            return OllamaService(base_url="http://localhost:11434", timeout=60)

    def test_list_models_returns_models_from_response(self, service):
        # Arrange
        service.client.list.return_value = {"models": [{"model": "qwen2.5vl:latest"}]}

        # Act
        result = service.list_models()

        # Assert
        assert result == [{"model": "qwen2.5vl:latest"}]

    def test_list_models_raises_connection_error_on_failure(self, service):
        # Arrange
        service.client.list.side_effect = Exception("host unreachable")

        # Act & Assert
        with pytest.raises(ConnectionError):
            service.list_models()

    def test_pull_model_verifies_against_real_sdk_response_shape(self, service):
        """Regression: the SDK keys the tag under 'model', not 'name'. A ['name']
        lookup here would raise on every real pull and mask success as failure."""
        # Arrange
        service.client.pull.return_value = iter([{"status": "success"}])
        service.client.list.return_value = {"models": [{"model": "qwen2.5vl:latest"}]}

        # Act & Assert — must not raise
        service.pull_model("qwen2.5vl:latest")

    def test_pull_model_raises_when_model_truly_missing_after_pull(self, service):
        # Arrange
        service.client.pull.return_value = iter([{"status": "success"}])
        service.client.list.return_value = {"models": [{"model": "llava:latest"}]}

        # Act & Assert
        with pytest.raises(Exception, match="did not appear in list_models"):
            service.pull_model("qwen2.5vl:latest")

    def test_pull_model_streams_progress(self, service):
        # Arrange
        service.client.pull.return_value = iter(
            [
                {"status": "downloading", "completed": 50, "total": 100},
                {"status": "success"},
            ]
        )
        service.client.list.return_value = {"models": [{"model": "qwen2.5vl:latest"}]}
        progress = MagicMock()

        # Act
        service.pull_model("qwen2.5vl:latest", progress_callback=progress)

        # Assert
        progress.assert_any_call("downloading: 50%")
