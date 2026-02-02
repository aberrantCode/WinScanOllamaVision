"""
Base LLM Provider Abstract Class
Defines the interface that all LLM providers must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from PIL import Image


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize provider with configuration.

        Args:
            config: Provider configuration dictionary
        """
        self.config = config
        self.provider_name = self.__class__.__name__.replace('Provider', '').lower()

    @abstractmethod
    def analyze_images(
        self,
        image_paths: List[str],
        prompt: str,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze one or more images using the LLM provider.

        Args:
            image_paths: List of paths to image files
            prompt: Text prompt for analysis
            model: Optional model override (uses default if not specified)

        Returns:
            Dictionary containing:
                - response: Full LLM response text
                - metadata: Extracted metadata dict
                - processing_time_ms: Processing time in milliseconds
                - model_used: Name of model used
                - success: Boolean indicating success
                - error: Error message if success=False

        Raises:
            Exception: If analysis fails
        """
        pass

    @abstractmethod
    def get_available_models(self) -> List[str]:
        """
        Get list of available models for this provider.

        Returns:
            List of model names/identifiers
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test if provider is accessible and configured correctly.

        Returns:
            True if connection successful, False otherwise
        """
        pass

    def get_default_model(self) -> Optional[str]:
        """
        Get the default model for this provider.

        Returns:
            Default model name or None
        """
        return self.config.get('default_model')

    def get_timeout(self) -> int:
        """
        Get timeout value in seconds.

        Returns:
            Timeout in seconds
        """
        return self.config.get('timeout', 300)

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """
        Validate provider configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.config:
            return False, "Configuration is empty"

        # Subclasses can override for specific validation
        return True, None

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(provider={self.provider_name})"

    def __repr__(self) -> str:
        return self.__str__()
