"""
Gemini CLI Provider
Uses Google Gemini CLI tool for vision analysis via subprocess.
"""

import json
import shlex
import subprocess
import sys
import time
from typing import Any, cast

from services.logging_service import get_logger

from .base_provider import BaseLLMProvider
from .command_builder import CommandBuilder

logger = get_logger()


class GeminiCliProvider(BaseLLMProvider):
    """Gemini CLI provider implementation"""

    def __init__(self, config: dict[str, Any]):
        """
        Initialize Gemini CLI provider.

        Args:
            config: Configuration dict with keys:
                - command_template: CLI command template with variables
                - timeout: Command timeout in seconds
                - default_model: Default model name
                - models: List of available models
        """
        super().__init__(config)
        self.command_template = config.get("command_template", "")
        self.timeout = config.get("timeout", 300)
        self.default_model = config.get("default_model", "gemini-2.0-flash-exp")
        self.available_models = config.get("models", [])

    def analyze_images(
        self, image_paths: list[str], prompt: str, model: str | None = None
    ) -> dict[str, Any]:
        """
        Analyze images using Gemini CLI.

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
            # Build command from template
            command = CommandBuilder.build_command(
                template=self.command_template,
                model=model_to_use,
                image_paths=image_paths,
                prompt=prompt,
            )

            logger.debug(
                "Gemini CLI Request - Command: %s, Model: %s, Images: %d",
                command,
                model_to_use,
                len(image_paths),
            )

            # Parse command into argument list to avoid shell injection
            args = shlex.split(command, posix=(sys.platform != "win32"))

            result = subprocess.run(
                args,
                shell=False,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            processing_time_ms = int((time.time() - start_time) * 1000)

            if result.returncode != 0:
                return {
                    "response": result.stderr,
                    "metadata": {},
                    "processing_time_ms": processing_time_ms,
                    "model_used": model_to_use,
                    "success": False,
                    "error": f"CLI returned error code {result.returncode}: {result.stderr}",
                }

            # Parse response
            response_text = result.stdout.strip()

            # Try to parse as JSON
            try:
                metadata = json.loads(response_text)
            except json.JSONDecodeError:
                # If not valid JSON, return raw content
                metadata = {"raw_content": response_text}

            logger.debug(
                "Gemini CLI Response - Length: %d chars, Processing time: %dms",
                len(response_text),
                processing_time_ms,
            )

            return {
                "response": response_text,
                "metadata": metadata,
                "processing_time_ms": processing_time_ms,
                "model_used": model_to_use,
                "success": True,
                "error": None,
            }

        except subprocess.TimeoutExpired:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"[GEMINI CLI] Timeout after {self.timeout}s")
            return {
                "response": "",
                "metadata": {},
                "processing_time_ms": processing_time_ms,
                "model_used": model_to_use,
                "success": False,
                "error": f"Gemini CLI timed out after {self.timeout}s. Try increasing timeout in settings.",
            }
        except FileNotFoundError:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error("[GEMINI CLI] Command not found - Gemini CLI may not be installed")
            return {
                "response": "",
                "metadata": {},
                "processing_time_ms": processing_time_ms,
                "model_used": model_to_use,
                "success": False,
                "error": "Gemini CLI not found. Install Gemini CLI and ensure it's in your PATH.",
            }
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"[GEMINI CLI] Unexpected error: {e}", exc_info=True)
            return {
                "response": "",
                "metadata": {},
                "processing_time_ms": processing_time_ms,
                "model_used": model_to_use,
                "success": False,
                "error": f"Gemini CLI error: {e}",
            }

    def get_available_models(self) -> list[str]:
        """
        Get list of available Gemini models.

        Returns:
            List of model names from config
        """
        return cast(list[str], self.available_models)

    def test_connection(self) -> bool:
        """
        Test Gemini CLI availability with error handling.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to run 'gemini --version' or similar check
            result = subprocess.run(
                ["gemini", "--version"],
                shell=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except FileNotFoundError:
            logger.warning("[GEMINI CLI] Connection test failed: command not found")
            return False
        except subprocess.TimeoutExpired:
            logger.warning("[GEMINI CLI] Connection test failed: timeout")
            return False
        except Exception as e:
            logger.error(f"[GEMINI CLI] Unexpected error during connection test: {e}")
            return False

    def validate_config(self) -> tuple[bool, str | None]:
        """
        Validate Gemini CLI configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        is_valid, error = super().validate_config()
        if not is_valid:
            return is_valid, error

        # Validate command template
        template_valid, template_error = CommandBuilder.validate_template(self.command_template)
        if not template_valid:
            return False, f"Invalid command template: {template_error}"

        # Check if default model is in available models
        if (
            self.default_model
            and self.available_models
            and self.default_model not in self.available_models
        ):
            return False, f"Default model '{self.default_model}' not in available models list"

        return True, None
