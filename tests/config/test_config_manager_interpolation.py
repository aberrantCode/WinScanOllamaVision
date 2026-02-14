"""Test that ConfigManager handles % characters in prompts correctly."""

import os
import tempfile

from config.config_manager import ConfigManager


def test_config_manager_handles_percent_in_prompts():
    """Test that prompts containing % characters can be read without interpolation errors."""
    # Create a temporary config file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
        config_path = f.name
        f.write("""[Prompts]
test_prompt = Is this page 100% blank/empty? Please respond.
another_prompt = Use %(variable)s for testing
""")

    try:
        # Initialize ConfigManager with the temp config
        config = ConfigManager(config_file=config_path)

        # Should be able to read prompts with % without InterpolationSyntaxError
        prompt1 = config.get_setting("Prompts", "test_prompt")
        assert prompt1 == "Is this page 100% blank/empty? Please respond."

        prompt2 = config.get_setting("Prompts", "another_prompt")
        assert prompt2 == "Use %(variable)s for testing"

    finally:
        # Clean up
        if os.path.exists(config_path):
            os.remove(config_path)


def test_config_manager_handles_real_prompt_with_percent():
    """Test the actual prompt that was causing the error."""
    # Create a temporary config file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
        config_path = f.name
        f.write("""[Prompts]
metadata = % blank/empty? A page is considered blank if it contains minimal or no text, images, or meaningful content. Set to true if mostly blank, false otherwise.
""")

    try:
        # Initialize ConfigManager with the temp config
        config = ConfigManager(config_file=config_path)

        # Should not raise InterpolationSyntaxError
        prompt = config.get_setting("Prompts", "metadata")
        assert "% blank/empty?" in prompt

    finally:
        # Clean up
        if os.path.exists(config_path):
            os.remove(config_path)
