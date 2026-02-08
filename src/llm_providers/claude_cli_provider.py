"""
Claude CLI Provider
Uses Claude Code CLI tool for vision analysis via subprocess.
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


class ClaudeCliProvider(BaseLLMProvider):
    """Claude CLI provider implementation"""

    def __init__(self, config: dict[str, Any]):
        """
        Initialize Claude CLI provider.

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
        self.default_model = config.get("default_model", "claude-3-5-sonnet-20241022")
        self.available_models = config.get("models", [])

    def analyze_images(
        self, image_paths: list[str], prompt: str, model: str | None = None
    ) -> dict[str, Any]:
        """
        Analyze images using Claude CLI.

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
                "Claude CLI Request - Command: %s, Model: %s, Images: %d",
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
                "Claude CLI Response - Length: %d chars, Processing time: %dms",
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
            return {
                "response": "",
                "metadata": {},
                "processing_time_ms": processing_time_ms,
                "model_used": model_to_use,
                "success": False,
                "error": f"Command timed out after {self.timeout} seconds",
            }
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            return {
                "response": "",
                "metadata": {},
                "processing_time_ms": processing_time_ms,
                "model_used": model_to_use,
                "success": False,
                "error": str(e),
            }

    def get_available_models(self) -> list[str]:
        """
        Get list of available Claude models.

        Returns:
            List of model names from config
        """
        return cast(list[str], self.available_models)

    def test_connection(self) -> bool:
        """
        Test Claude CLI availability.

        Returns:
            True if CLI is available
        """
        try:
            # Try to run 'claude --version' or similar check
            result = subprocess.run(
                ["claude", "--version"],
                shell=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def validate_config(self) -> tuple[bool, str | None]:
        """
        Validate Claude CLI configuration.

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
