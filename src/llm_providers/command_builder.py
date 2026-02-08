"""
Command Builder for CLI-based LLM Providers
Handles template processing with variable substitution.
"""

import re


class CommandBuilder:
    """Builds CLI commands from templates with variable substitution"""

    # Variable placeholders
    VAR_MODEL = "%MODEL%"
    VAR_IMAGE_PATHS = "%IMAGE_PATHS%"
    VAR_PROMPT = "%PROMPT%"

    @staticmethod
    def build_command(template: str, model: str, image_paths: list[str], prompt: str) -> str:
        """
        Build command from template with variable substitution.

        Args:
            template: Command template string
            model: Model name/identifier
            image_paths: List of image file paths
            prompt: Prompt text

        Returns:
            Command string (to be parsed via shlex.split for safe subprocess execution)
        """
        # Check if template is valid
        if not template:
            raise ValueError(
                "Command template is not configured. Please set up the CLI provider command template in settings."
            )

        # Replace variables
        command_str = template.replace(CommandBuilder.VAR_MODEL, model)

        # Handle multiple image paths
        # Most CLIs support space-separated paths or repeated flags
        images_str = " ".join(f'"{path}"' for path in image_paths)
        command_str = command_str.replace(CommandBuilder.VAR_IMAGE_PATHS, images_str)

        # Replace prompt (escape quotes)
        prompt_escaped = prompt.replace('"', '\\"')
        command_str = command_str.replace(CommandBuilder.VAR_PROMPT, f'"{prompt_escaped}"')

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
