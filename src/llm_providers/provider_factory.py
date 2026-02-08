"""
Provider Factory
Creates LLM provider instances based on configuration.
"""

from typing import Any

from .base_provider import BaseLLMProvider
from .claude_cli_provider import ClaudeCliProvider
from .gemini_cli_provider import GeminiCliProvider
from .ollama_provider import OllamaProvider


class ProviderFactory:
    """Factory for creating LLM provider instances"""

    # Provider type mapping
    PROVIDER_CLASSES = {
        "ollama": OllamaProvider,
        "claude_cli": ClaudeCliProvider,
        "gemini_cli": GeminiCliProvider,
    }

    @staticmethod
    def create_provider(provider_type: str, config: dict[str, Any]) -> BaseLLMProvider:
        """
        Create a provider instance based on type.

        Args:
            provider_type: Type of provider (ollama, claude_cli, gemini_cli)
            config: Provider configuration dict

        Returns:
            Instance of BaseLLMProvider subclass

        Raises:
            ValueError: If provider type is unknown
        """
        provider_class = ProviderFactory.PROVIDER_CLASSES.get(provider_type.lower())

        if provider_class is None:
            available = ", ".join(ProviderFactory.PROVIDER_CLASSES.keys())
            raise ValueError(
                f"Unknown provider type: '{provider_type}'. Available providers: {available}"
            )

        return provider_class(config)  # type: ignore[abstract]

    @staticmethod
    def create_from_config_manager(
        config_manager, provider_name: str | None = None
    ) -> BaseLLMProvider:
        """
        Create provider instance from ConfigManager.

        Args:
            config_manager: ConfigManager instance
            provider_name: Optional provider name (uses active if not specified)

        Returns:
            Provider instance

        Raises:
            ValueError: If provider configuration is invalid
        """
        # Get active provider if not specified
        if provider_name is None:
            provider_name = config_manager.get_active_provider()

        # Map provider name to type
        provider_type_mapping = {
            "ollama": "ollama",
            "claude_cli": "claude_cli",
            "gemini_cli": "gemini_cli",
        }

        provider_type = provider_type_mapping.get(provider_name)
        if not provider_type:
            raise ValueError(f"Unknown provider name: '{provider_name}'")

        # Get provider configuration
        config = config_manager.get_provider_config(provider_name)

        if not config:
            raise ValueError(f"No configuration found for provider: '{provider_name}'")

        # Create provider
        return ProviderFactory.create_provider(provider_type, config)

    @staticmethod
    def get_available_provider_types() -> list[str]:
        """Get list of available provider types"""
        return list(ProviderFactory.PROVIDER_CLASSES.keys())

    @staticmethod
    def validate_provider_type(provider_type: str) -> bool:
        """Check if a provider type is valid"""
        return provider_type.lower() in ProviderFactory.PROVIDER_CLASSES


# Example usage
if __name__ == "__main__":
    import logging

    from services.logging_service import LoggingService, get_logger

    LoggingService().initialize(log_level=logging.DEBUG, console_output=True)
    _logger = get_logger()

    # Test creating providers
    ollama_config = {"base_url": "http://localhost:11434", "timeout": 300, "model": "qwen2.5-vl"}

    claude_config = {
        "command_template": "claude --model %MODEL% --image %IMAGE_PATHS% --prompt %PROMPT%",
        "timeout": 300,
        "default_model": "claude-3-5-sonnet-20241022",
        "models": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
    }

    _logger.info("Creating Ollama provider...")
    ollama_provider = ProviderFactory.create_provider("ollama", ollama_config)
    _logger.info(f"Created: {ollama_provider}")
    _logger.info(f"Available models: {ollama_provider.get_available_models()}")

    _logger.info("Creating Claude CLI provider...")
    claude_provider = ProviderFactory.create_provider("claude_cli", claude_config)
    _logger.info(f"Created: {claude_provider}")
    _logger.info(f"Available models: {claude_provider.get_available_models()}")

    _logger.info(f"Available provider types: {ProviderFactory.get_available_provider_types()}")
    _logger.info("Test completed successfully!")
