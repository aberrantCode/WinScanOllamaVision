"""
Ollama Provider
Wraps the existing OllamaService to conform to BaseLLMProvider interface.
"""

import json
import time
from typing import Any, cast

# Import the existing OllamaService
from llm_providers.ollama_service import OllamaService

from .base_provider import BaseLLMProvider


def _get_logger():
    """Lazy logger initialization to avoid circular imports"""
    from services.logging_service import get_logger

    return get_logger()


class OllamaProvider(BaseLLMProvider):
    """Ollama LLM provider implementation"""

    def __init__(self, config: dict[str, Any]):
        """
        Initialize Ollama provider.

        Args:
            config: Configuration dict with keys:
                - base_url: Ollama server URL
                - timeout: Request timeout in seconds
                - model: Default model name
        """
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.timeout = config.get("timeout", 300)
        self.default_model = config.get("model", "qwen2.5vl:latest")

        # Create OllamaService instance
        self.service = OllamaService(base_url=self.base_url, timeout=float(self.timeout))

    def analyze_images(
        self, image_paths: list[str], prompt: str, model: str | None = None
    ) -> dict[str, Any]:
        """
        Analyze images using Ollama vision model.

        Args:
            image_paths: List of image file paths
            prompt: Analysis prompt
            model: Model override (uses default if not specified)

        Returns:
            Dictionary with analysis results
        """
        start_time = time.time()
        model_to_use = model or self.default_model

        try:
            # Use the existing chat_with_vision_model method
            response = self.service.chat_with_vision_model(
                model_name=model_to_use, image_paths=image_paths, prompt=prompt, format_json=True
            )

            processing_time_ms = int((time.time() - start_time) * 1000)

            # Parse response content
            content = response.get("content", "{}")

            # Clean JSON if needed
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(line for line in lines if not line.strip().startswith("```"))
                content = content.strip()

            # Try to parse as JSON
            try:
                metadata = json.loads(content)
            except json.JSONDecodeError:
                # If not valid JSON, return raw content
                metadata = {"raw_content": content}

            return {
                "response": content,
                "metadata": metadata,
                "processing_time_ms": processing_time_ms,
                "model_used": model_to_use,
                "provider_name": "ollama",
                "success": True,
                "error": None,
            }

        except ConnectionError as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            _get_logger().error(f"[OLLAMA PROVIDER] Connection error during analysis: {e}")
            return {
                "response": "",
                "metadata": {},
                "processing_time_ms": processing_time_ms,
                "model_used": model_to_use,
                "provider_name": "ollama",
                "success": False,
                "error": str(e),
            }
        except TimeoutError as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            _get_logger().error(f"[OLLAMA PROVIDER] Timeout during analysis: {e}")
            return {
                "response": "",
                "metadata": {},
                "processing_time_ms": processing_time_ms,
                "model_used": model_to_use,
                "provider_name": "ollama",
                "success": False,
                "error": str(e),
            }
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            _get_logger().error(f"[OLLAMA PROVIDER] Unexpected error during analysis: {e}")
            return {
                "response": "",
                "metadata": {},
                "processing_time_ms": processing_time_ms,
                "model_used": model_to_use,
                "provider_name": "ollama",
                "success": False,
                "error": str(e),
            }

    def get_default_model(self) -> str:
        """
        Get the default model for Ollama.

        Returns:
            Default model name
        """
        return cast(str, self.default_model)

    def get_available_models(self) -> list[str]:
        """
        Get list of available Ollama models.

        Returns:
            List of model names
        """
        try:
            models = self.service.list_models()
            # The ollama SDK's list() items key the tag under "model", not
            # "name" — fall back to "name" for callers/tests that pass plain
            # {"name": ...} dicts.
            return [
                str(model.get("name") or model.get("model") or "")
                for model in models
                if model.get("name") or model.get("model")
            ]
        except ConnectionError as e:
            _get_logger().error(f"[OLLAMA PROVIDER] Connection error listing models: {e}")
            return []
        except Exception as e:
            _get_logger().error(f"[OLLAMA PROVIDER] Unexpected error listing models: {e}")
            return []

    def test_connection(self) -> bool:
        """
        Test Ollama server connection with error handling.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.service.list_models()
            return True
        except ConnectionError as e:
            _get_logger().warning(f"[OLLAMA] Connection test failed: {e}")
            return False
        except Exception as e:
            _get_logger().error(f"[OLLAMA] Unexpected error during connection test: {e}")
            return False

    def validate_config(self) -> tuple[bool, str | None]:
        """
        Validate Ollama configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        is_valid, error = super().validate_config()
        if not is_valid:
            return is_valid, error

        # Check if model is specified
        if not self.default_model:
            return False, "Model name is required"

        # Check if base_url is valid
        if not self.base_url or not self.base_url.startswith("http"):
            return False, "Invalid base_url (must start with http:// or https://)"

        return True, None

    # Convenience methods that wrap existing OllamaService functionality
    def validate_grouping(self, image_paths: list[str], custom_prompt: str | None = None) -> bool:
        """Check if images belong to same document"""
        return self.service.validate_grouping(self.default_model, image_paths, custom_prompt)

    def validate_grouping_with_page_number(
        self, image_paths: list[str], custom_prompt: str | None = None
    ) -> dict[str, Any]:
        """Validate grouping and extract metadata"""
        return self.service.validate_grouping_with_page_number(
            self.default_model, image_paths, custom_prompt
        )

    def extract_document_info(
        self, image_paths: list[str], title_keywords: str
    ) -> dict[str, str | None]:
        """Extract document metadata"""
        return self.service.extract_document_info(self.default_model, image_paths, title_keywords)
