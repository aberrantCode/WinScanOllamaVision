"""
Tests for OllamaService network error handling.

Target: Comprehensive coverage of network exceptions
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from llm_providers.ollama_service import OllamaService


class TestOllamaServiceNetworkErrors:
    """Test suite for OllamaService network error handling"""

    @pytest.fixture
    def service(self):
        """Create OllamaService instance"""
        return OllamaService(base_url="http://localhost:11434", timeout=60.0)

    def test_chat_handles_connect_error(self, service):
        """Test that chat handles connection errors gracefully"""
        # Arrange
        with patch.object(service.client, "chat") as mock_chat:
            mock_chat.side_effect = httpx.ConnectError("Connection refused")

            # Act & Assert
            with pytest.raises(ConnectionError, match="Cannot connect to Ollama"):
                service.chat_with_vision_model(
                    model_name="test-model", image_paths=["/test.jpg"], prompt="Test"
                )

    def test_chat_handles_timeout_error(self, service):
        """Test that chat handles timeout errors gracefully"""
        # Arrange
        with patch.object(service.client, "chat") as mock_chat:
            mock_chat.side_effect = httpx.TimeoutException("Request timed out")

            # Act & Assert
            with pytest.raises(TimeoutError, match="Ollama timed out"):
                service.chat_with_vision_model(
                    model_name="test-model", image_paths=["/test.jpg"], prompt="Test"
                )

    def test_chat_handles_http_status_error(self, service):
        """Test that chat handles HTTP status errors gracefully"""
        # Arrange
        with patch.object(service.client, "chat") as mock_chat:
            # Create a mock response for HTTPStatusError
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_chat.side_effect = httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=mock_response
            )

            # Act & Assert
            with pytest.raises(ConnectionError, match="Ollama error 500"):
                service.chat_with_vision_model(
                    model_name="test-model", image_paths=["/test.jpg"], prompt="Test"
                )

    def test_list_models_handles_connection_error(self, service):
        """Test that list_models handles connection errors"""
        # Arrange
        with patch.object(service.client, "list") as mock_list:
            mock_list.side_effect = httpx.ConnectError("Connection refused")

            # Act & Assert
            with pytest.raises(ConnectionError, match="Failed to connect to Ollama server"):
                service.list_models()
