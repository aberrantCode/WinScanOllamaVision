"""
Command Builder for CLI-based LLM Providers
Handles template processing with validated, safely-quoted variable substitution.

Security: All substituted values are validated and shell-quoted to prevent
argument boundary issues when the resulting command string is parsed via
shlex.split() in the provider implementations.
"""

import re
import shlex
import sys


class CommandBuilder:
    """Builds CLI commands from templates with validated variable substitution.

    Security considerations:
        - All substituted values are shell-quoted via shlex.quote()
        - Model names are validated against an allowlist pattern
        - Empty/whitespace-only inputs are rejected with ValueError
        - Image paths are individually quoted to preserve argument boundaries
    """

    # Variable placeholders
    VAR_MODEL = "%MODEL%"
    VAR_IMAGE_PATHS = "%IMAGE_PATHS%"
    VAR_PROMPT = "%PROMPT%"

    # Allowlist pattern for model names: alphanumeric, hyphens, underscores,
    # dots, colons, forward slashes (for org/model patterns like "meta/llama3")
    _MODEL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9._:/-]+$")

    @staticmethod
    def _validate_model(model: str) -> None:
        """Validate model name against allowlist pattern.

        Args:
            model: Model name/identifier to validate

        Raises:
            ValueError: If model is empty or contains disallowed characters
        """
        if not model or not model.strip():
            raise ValueError("Model name cannot be empty")

        if not CommandBuilder._MODEL_NAME_PATTERN.match(model):
            raise ValueError(
                f"Model name contains disallowed characters: {model!r}. "
                "Only alphanumeric characters, hyphens, underscores, dots, "
                "colons, and forward slashes are permitted."
            )

    @staticmethod
    def _validate_image_paths(image_paths: list[str]) -> None:
        """Validate image paths are non-empty strings.

        Args:
            image_paths: List of image file paths to validate

        Raises:
            ValueError: If list is empty or contains empty/whitespace-only paths
        """
        if not image_paths:
            raise ValueError("At least one image path is required")

        for i, path in enumerate(image_paths):
            if not path or not path.strip():
                raise ValueError(f"Image path at index {i} is empty")

    @staticmethod
    def _validate_prompt(prompt: str) -> None:
        """Validate prompt is non-empty.

        Args:
            prompt: Prompt text to validate

        Raises:
            ValueError: If prompt is empty or whitespace-only
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")

    @staticmethod
    def _shell_quote(value: str) -> str:
        """Quote a value for safe shell usage, platform-aware.

        On POSIX systems, uses shlex.quote() (single-quote wrapping).
        On Windows, wraps in double quotes with internal double quotes escaped,
        matching the non-POSIX shlex.split() behavior used by providers.

        Args:
            value: The string value to quote

        Returns:
            Shell-quoted string safe for inclusion in a command template
        """
        if sys.platform == "win32":
            escaped = value.replace('"', '\\"')
            return f'"{escaped}"'
        return shlex.quote(value)

    @staticmethod
    def build_command(template: str, model: str, image_paths: list[str], prompt: str) -> str:
        """
        Build command from template with validated, safely-quoted substitutions.

        All substituted values are validated for correctness and shell-quoted
        to prevent argument boundary issues. The resulting command string is
        intended to be parsed via shlex.split() before subprocess execution.

        Args:
            template: Command template string containing placeholder variables
            model: Model name/identifier (must match allowlist pattern)
            image_paths: List of image file paths (must be non-empty)
            prompt: Prompt text (must be non-empty)

        Returns:
            Command string with all placeholders replaced by quoted values

        Raises:
            ValueError: If template is empty, model name is invalid,
                image_paths is empty, or prompt is empty
        """
        # Validate template
        if not template:
            raise ValueError(
                "Command template is not configured. "
                "Please set up the CLI provider command template in settings."
            )

        # Validate all inputs before any substitution
        CommandBuilder._validate_model(model)
        CommandBuilder._validate_image_paths(image_paths)
        CommandBuilder._validate_prompt(prompt)

        # Model names are validated against an allowlist, so quoting is
        # a defense-in-depth measure rather than the primary protection
        safe_model = CommandBuilder._shell_quote(model)
        command_str = template.replace(CommandBuilder.VAR_MODEL, safe_model)

        # Quote each image path individually to preserve argument boundaries
        safe_images = " ".join(CommandBuilder._shell_quote(path) for path in image_paths)
        command_str = command_str.replace(CommandBuilder.VAR_IMAGE_PATHS, safe_images)

        # Quote the prompt to prevent argument boundary breakage
        safe_prompt = CommandBuilder._shell_quote(prompt)
        command_str = command_str.replace(CommandBuilder.VAR_PROMPT, safe_prompt)

        return command_str

    @staticmethod
    def validate_template(template: str) -> tuple[bool, str]:
        """
        Validate command template.

        Args:
            template: Command template string

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not template or not template.strip():
            return False, "Template is empty"

        # Check for required variables
        has_model = CommandBuilder.VAR_MODEL in template
        has_images = CommandBuilder.VAR_IMAGE_PATHS in template
        has_prompt = CommandBuilder.VAR_PROMPT in template

        missing = []
        if not has_model:
            missing.append(CommandBuilder.VAR_MODEL)
        if not has_images:
            missing.append(CommandBuilder.VAR_IMAGE_PATHS)
        if not has_prompt:
            missing.append(CommandBuilder.VAR_PROMPT)

        if missing:
            return False, f"Template missing required variables: {', '.join(missing)}"

        return True, ""

    @staticmethod
    def extract_variables(template: str) -> list[str]:
        """
        Extract all variable placeholders from template.

        Args:
            template: Command template string

        Returns:
            List of variable names found
        """
        pattern = r"%([A-Z_]+)%"
        return re.findall(pattern, template)

    @staticmethod
    def get_example_template() -> str:
        """Get an example command template"""
        return f"my-cli --model {CommandBuilder.VAR_MODEL} --image {CommandBuilder.VAR_IMAGE_PATHS} --prompt {CommandBuilder.VAR_PROMPT}"
