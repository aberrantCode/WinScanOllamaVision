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

    def test_extract_document_info_does_not_raise_on_valid_input(self, service):
        """Regression: extract_document_info used to crash with unescaped braces in f-string.
        This test verifies it can now successfully extract document metadata from JSON response."""
        # Arrange
        service.client.chat.return_value = {
            "message": {
                "content": '{"company": "Acme Corp", "title": "Invoice", "date": "2024-01-15"}'
            }
        }

        # Act
        result = service.extract_document_info("qwen2.5vl:latest", ["a.png"], "Invoice,Receipt")

        # Assert — must not raise
        assert result["company"] == "Acme Corp"
        assert result["title"] == "Invoice"
        assert result["date"] == "2024-01-15"

    def test_infer_page_order_from_content_does_not_raise_on_valid_input(self, service):
        """Regression: infer_page_order_from_content used to crash with unescaped braces in f-string.
        This test verifies it can now successfully infer page order from JSON response."""
        # Arrange
        service.client.chat.return_value = {
            "message": {"content": '{"ordered_indices": [1, 0], "confidence": "high"}'}
        }

        # Act
        result = service.infer_page_order_from_content("qwen2.5vl:latest", ["a.png", "b.png"])

        # Assert — must not raise
        assert result["ordered_indices"] == [1, 0]
        assert result["confidence"] == "high"

    def test_init_sets_connect_timeout_shorter_than_total_timeout(self):
        """__init__ must set connect_timeout to min(CONNECT_TIMEOUT_SECONDS, timeout)."""
        # Arrange & Act
        with patch("llm_providers.ollama_service.ollama.Client"):
            service = OllamaService(timeout=300.0)

        # Assert
        from llm_providers.ollama_service import CONNECT_TIMEOUT_SECONDS

        assert service.connect_timeout == CONNECT_TIMEOUT_SECONDS
        assert service.connect_timeout < service.timeout

    def test_init_connect_timeout_never_exceeds_total_timeout(self):
        """connect_timeout must be clamped to not exceed total timeout."""
        # Arrange & Act
        with patch("llm_providers.ollama_service.ollama.Client"):
            service = OllamaService(timeout=3.0)

        # Assert
        assert service.connect_timeout == 3.0
        assert service.connect_timeout <= service.timeout

    def test_init_passes_split_timeout_to_httpx(self):
        """__init__ must pass both timeout and connect timeout to httpx.Timeout()."""
        # Arrange
        with (
            patch("llm_providers.ollama_service.httpx.Timeout") as mock_timeout,
            patch("llm_providers.ollama_service.ollama.Client"),
        ):
            OllamaService(timeout=300.0)

        # Assert
        from llm_providers.ollama_service import CONNECT_TIMEOUT_SECONDS

        mock_timeout.assert_called_once_with(300.0, connect=CONNECT_TIMEOUT_SECONDS)

    def test_init_default_timeout_is_600(self):
        """Default timeout must be 600s so a cold CPU vision load (~405s measured)
        completes instead of firing the old 300s ceiling mid-load."""
        with patch("llm_providers.ollama_service.ollama.Client"):
            service = OllamaService()

        assert service.timeout == 600.0

    def test_init_default_keep_alive_is_30m(self):
        """Default keep_alive keeps the model resident so files after the first in
        a batch run warm (~28s) instead of re-paying the ~405s cold load."""
        with patch("llm_providers.ollama_service.ollama.Client"):
            service = OllamaService()

        assert service.keep_alive == "30m"

    def test_chat_with_vision_model_passes_keep_alive_to_client(self):
        """chat_with_vision_model must forward keep_alive to client.chat so the
        model stays warm between analyses."""
        with patch("llm_providers.ollama_service.ollama.Client"):
            service = OllamaService(keep_alive="45m")
        service.client.chat.return_value = {"message": {"content": "{}"}}

        service.chat_with_vision_model("qwen2.5vl:latest", ["a.png"], "prompt")

        _, kwargs = service.client.chat.call_args
        assert kwargs["keep_alive"] == "45m"

    def test_chat_with_vision_model_error_includes_base_url_model_and_elapsed(self, service):
        """chat_with_vision_model exception must include base_url, model_name, and elapsed time."""
        # Arrange
        service.client.chat.side_effect = Exception("timed out")

        # Act & Assert
        with pytest.raises(ConnectionError) as exc_info:
            service.chat_with_vision_model("qwen2.5vl:latest", ["test.png"], "test prompt")

        error_msg = str(exc_info.value)
        assert "http://localhost:11434" in error_msg
        assert "qwen2.5vl:latest" in error_msg
        assert "elapsed" in error_msg
