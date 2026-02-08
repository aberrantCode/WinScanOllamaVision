"""
Tests for CommandBuilder utility.

Target: 100% coverage
Covers: input validation, shell quoting, placeholder substitution, template validation
"""

import sys
from unittest.mock import patch

import pytest

from llm_providers.command_builder import CommandBuilder


class TestCommandBuilder:
    """Test suite for CommandBuilder"""

    # -------------------------------------------------------------------------
    # build_command: basic placeholder substitution
    # -------------------------------------------------------------------------

    def test_build_command_replaces_model_placeholder(self):
        # Arrange
        template = "cli --model %MODEL% --images %IMAGE_PATHS% --prompt %PROMPT%"
        model = "test-model"
        image_paths = ["/img.jpg"]
        prompt = "test"

        # Act
        result = CommandBuilder.build_command(template, model, image_paths, prompt)

        # Assert
        assert "test-model" in result
        assert "%MODEL%" not in result

    def test_build_command_replaces_prompt_placeholder(self):
        # Arrange
        template = "cli --model %MODEL% --images %IMAGE_PATHS% --prompt %PROMPT%"
        model = "model"
        image_paths = ["/img.jpg"]
        prompt = "Analyze this document"

        # Act
        result = CommandBuilder.build_command(template, model, image_paths, prompt)

        # Assert
        assert "Analyze this document" in result
        assert "%PROMPT%" not in result

    def test_build_command_replaces_image_paths_placeholder(self):
        # Arrange
        template = "cli --model %MODEL% %IMAGE_PATHS% --prompt %PROMPT%"
        model = "model"
        image_paths = ["/path/to/img1.jpg", "/path/to/img2.jpg"]
        prompt = "test"

        # Act
        result = CommandBuilder.build_command(template, model, image_paths, prompt)

        # Assert
        assert "/path/to/img1.jpg" in result
        assert "/path/to/img2.jpg" in result
        assert "%IMAGE_PATHS%" not in result

    def test_build_command_with_multiple_images(self):
        # Arrange
        template = "cli --model %MODEL% %IMAGE_PATHS% --prompt %PROMPT%"
        model = "model"
        image_paths = ["/img1.jpg", "/img2.jpg", "/img3.jpg"]
        prompt = "test"

        # Act
        result = CommandBuilder.build_command(template, model, image_paths, prompt)

        # Assert
        for path in image_paths:
            assert path in result

    def test_build_command_with_all_placeholders(self):
        # Arrange
        template = "cli --model %MODEL% --prompt %PROMPT% --images %IMAGE_PATHS%"
        model = "my-model"
        image_paths = ["/test.jpg"]
        prompt = "Analyze"

        # Act
        result = CommandBuilder.build_command(template, model, image_paths, prompt)

        # Assert
        assert "my-model" in result
        assert "Analyze" in result
        assert "/test.jpg" in result
        assert "%MODEL%" not in result
        assert "%PROMPT%" not in result
        assert "%IMAGE_PATHS%" not in result

    def test_build_command_with_complex_template(self):
        # Arrange
        template = (
            "python script.py --model=%MODEL% "
            "--images %IMAGE_PATHS% "
            "--prompt %PROMPT% "
            "--format=json"
        )
        model = "vision-model"
        image_paths = ["/img1.jpg", "/img2.jpg"]
        prompt = "Extract metadata"

        # Act
        result = CommandBuilder.build_command(template, model, image_paths, prompt)

        # Assert
        assert "vision-model" in result
        assert "Extract metadata" in result
        assert "/img1.jpg" in result
        assert "/img2.jpg" in result
        assert "--format=json" in result

    # -------------------------------------------------------------------------
    # build_command: input validation
    # -------------------------------------------------------------------------

    def test_build_command_raises_on_empty_template(self):
        # Arrange
        template = ""
        model = "model"
        image_paths = ["/img.jpg"]
        prompt = "test"

        # Act & Assert
        with pytest.raises(ValueError, match="Command template is not configured"):
            CommandBuilder.build_command(template, model, image_paths, prompt)

    def test_build_command_raises_on_empty_model(self):
        # Arrange
        template = "cli --model %MODEL% --images %IMAGE_PATHS% --prompt %PROMPT%"
        model = ""
        image_paths = ["/img.jpg"]
        prompt = "test"

        # Act & Assert
        with pytest.raises(ValueError, match="Model name cannot be empty"):
            CommandBuilder.build_command(template, model, image_paths, prompt)

    def test_build_command_raises_on_whitespace_model(self):
        # Arrange
        template = "cli --model %MODEL% --images %IMAGE_PATHS% --prompt %PROMPT%"
        model = "   "
        image_paths = ["/img.jpg"]
        prompt = "test"

        # Act & Assert
        with pytest.raises(ValueError, match="Model name cannot be empty"):
            CommandBuilder.build_command(template, model, image_paths, prompt)

    def test_build_command_raises_on_empty_image_paths(self):
        # Arrange
        template = "cli --model %MODEL% --images %IMAGE_PATHS% --prompt %PROMPT%"
        model = "model"
        image_paths = []
        prompt = "test"

        # Act & Assert
        with pytest.raises(ValueError, match="At least one image path is required"):
            CommandBuilder.build_command(template, model, image_paths, prompt)

    def test_build_command_raises_on_empty_path_in_list(self):
        # Arrange
        template = "cli --model %MODEL% --images %IMAGE_PATHS% --prompt %PROMPT%"
        model = "model"
        image_paths = ["/valid.jpg", ""]
        prompt = "test"

        # Act & Assert
        with pytest.raises(ValueError, match="Image path at index 1 is empty"):
            CommandBuilder.build_command(template, model, image_paths, prompt)

    def test_build_command_raises_on_whitespace_path_in_list(self):
        # Arrange
        template = "cli --model %MODEL% --images %IMAGE_PATHS% --prompt %PROMPT%"
        model = "model"
        image_paths = ["   "]
        prompt = "test"

        # Act & Assert
        with pytest.raises(ValueError, match="Image path at index 0 is empty"):
            CommandBuilder.build_command(template, model, image_paths, prompt)

    def test_build_command_raises_on_empty_prompt(self):
        # Arrange
        template = "cli --model %MODEL% --images %IMAGE_PATHS% --prompt %PROMPT%"
        model = "model"
        image_paths = ["/img.jpg"]
        prompt = ""

        # Act & Assert
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            CommandBuilder.build_command(template, model, image_paths, prompt)

    def test_build_command_raises_on_whitespace_prompt(self):
        # Arrange
        template = "cli --model %MODEL% --images %IMAGE_PATHS% --prompt %PROMPT%"
        model = "model"
        image_paths = ["/img.jpg"]
        prompt = "   "

        # Act & Assert
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            CommandBuilder.build_command(template, model, image_paths, prompt)

    # -------------------------------------------------------------------------
    # build_command: model name allowlist validation
    # -------------------------------------------------------------------------

    def test_build_command_rejects_model_with_spaces(self):
        # Spaces could break argument boundaries
        template = "cli --model %MODEL% --images %IMAGE_PATHS% --prompt %PROMPT%"

        with pytest.raises(ValueError, match="disallowed characters"):
            CommandBuilder.build_command(template, "model with spaces", ["/img.jpg"], "test")

    def test_build_command_rejects_model_with_shell_metacharacters(self):
        # Shell metacharacters should be rejected
        dangerous_models = [
            "model; rm -rf /",
            "model && cat /etc/passwd",
            "model | grep secret",
            "$(whoami)",
            "model`id`",
            "model\ninjected",
        ]
        template = "cli --model %MODEL% --images %IMAGE_PATHS% --prompt %PROMPT%"

        for dangerous_model in dangerous_models:
            with pytest.raises(ValueError, match="disallowed characters"):
                CommandBuilder.build_command(template, dangerous_model, ["/img.jpg"], "test")

    def test_build_command_accepts_valid_model_names(self):
        # These are all legitimate model name patterns
        valid_models = [
            "gpt-4",
            "claude-3-5-sonnet-20241022",
            "qwen2.5-vl",
            "meta/llama3",
            "org/model:latest",
            "model_v2",
            "gemini-2.0-flash-exp",
        ]
        template = "cli --model %MODEL% --images %IMAGE_PATHS% --prompt %PROMPT%"

        for model_name in valid_models:
            result = CommandBuilder.build_command(template, model_name, ["/img.jpg"], "test")
            assert model_name in result

    # -------------------------------------------------------------------------
    # build_command: shell quoting / special character handling
    # -------------------------------------------------------------------------

    def test_build_command_quotes_prompt_with_special_characters(self):
        # Arrange
        template = "cli --model %MODEL% --images %IMAGE_PATHS% --prompt %PROMPT%"
        model = "model"
        image_paths = ["/img.jpg"]
        prompt = 'Text with "quotes" and special chars $%^'

        # Act
        result = CommandBuilder.build_command(template, model, image_paths, prompt)

        # Assert - prompt content should be present and quoted
        assert "quotes" in result
        assert "special chars" in result

    def test_build_command_quotes_image_paths_with_spaces(self):
        # Arrange
        template = "cli --model %MODEL% --images %IMAGE_PATHS% --prompt %PROMPT%"
        model = "model"
        image_paths = ["/path with spaces/img.jpg"]
        prompt = "test"

        # Act
        result = CommandBuilder.build_command(template, model, image_paths, prompt)

        # Assert - path should be present and quoted to preserve as single arg
        assert "/path with spaces/img.jpg" in result
        # The path must be quoted (either single or double quotes)
        assert '"/path with spaces/img.jpg"' in result or "'/path with spaces/img.jpg'" in result

    def test_build_command_quotes_prompt_with_newlines(self):
        # Arrange
        template = "cli --model %MODEL% --images %IMAGE_PATHS% --prompt %PROMPT%"
        model = "model"
        image_paths = ["/img.jpg"]
        prompt = "line1\nline2\nline3"

        # Act
        result = CommandBuilder.build_command(template, model, image_paths, prompt)

        # Assert - newlines should be preserved within quotes
        assert "line1" in result
        assert "line2" in result

    # -------------------------------------------------------------------------
    # _shell_quote: platform-aware quoting
    # -------------------------------------------------------------------------

    def test_shell_quote_posix(self):
        """On POSIX, shlex.quote wraps in single quotes."""
        with patch.object(sys, "platform", "linux"):
            result = CommandBuilder._shell_quote("hello world")
            assert result == "'hello world'"

    def test_shell_quote_posix_handles_single_quotes(self):
        """On POSIX, shlex.quote handles embedded single quotes."""
        with patch.object(sys, "platform", "linux"):
            result = CommandBuilder._shell_quote("it's a test")
            # shlex.quote escapes single quotes
            assert "it" in result
            assert "a test" in result

    def test_shell_quote_windows(self):
        """On Windows, wraps in double quotes with escaped inner quotes."""
        with patch.object(sys, "platform", "win32"):
            result = CommandBuilder._shell_quote("hello world")
            assert result == '"hello world"'

    def test_shell_quote_windows_escapes_double_quotes(self):
        """On Windows, inner double quotes are escaped."""
        with patch.object(sys, "platform", "win32"):
            result = CommandBuilder._shell_quote('say "hello"')
            assert result == '"say \\"hello\\""'

    # -------------------------------------------------------------------------
    # _validate_model: unit tests for model validation
    # -------------------------------------------------------------------------

    def test_validate_model_accepts_valid_names(self):
        # Should not raise for valid model names
        CommandBuilder._validate_model("gpt-4")
        CommandBuilder._validate_model("claude-3-5-sonnet-20241022")
        CommandBuilder._validate_model("org/model:tag")
        CommandBuilder._validate_model("model.v2")

    def test_validate_model_rejects_empty(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            CommandBuilder._validate_model("")

    def test_validate_model_rejects_whitespace(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            CommandBuilder._validate_model("  \t  ")

    def test_validate_model_rejects_semicolons(self):
        with pytest.raises(ValueError, match="disallowed characters"):
            CommandBuilder._validate_model("model;echo pwned")

    # -------------------------------------------------------------------------
    # _validate_image_paths: unit tests
    # -------------------------------------------------------------------------

    def test_validate_image_paths_accepts_valid_paths(self):
        # Should not raise
        CommandBuilder._validate_image_paths(["/path/to/file.jpg"])
        CommandBuilder._validate_image_paths(["/a.jpg", "/b.png", "/c.jpeg"])

    def test_validate_image_paths_rejects_empty_list(self):
        with pytest.raises(ValueError, match="At least one image path"):
            CommandBuilder._validate_image_paths([])

    def test_validate_image_paths_rejects_empty_string_in_list(self):
        with pytest.raises(ValueError, match="index 0 is empty"):
            CommandBuilder._validate_image_paths([""])

    def test_validate_image_paths_rejects_whitespace_in_list(self):
        with pytest.raises(ValueError, match="index 1 is empty"):
            CommandBuilder._validate_image_paths(["/valid.jpg", "   "])

    # -------------------------------------------------------------------------
    # _validate_prompt: unit tests
    # -------------------------------------------------------------------------

    def test_validate_prompt_accepts_valid_text(self):
        # Should not raise
        CommandBuilder._validate_prompt("Analyze this document")
        CommandBuilder._validate_prompt("a")

    def test_validate_prompt_rejects_empty(self):
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            CommandBuilder._validate_prompt("")

    def test_validate_prompt_rejects_whitespace(self):
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            CommandBuilder._validate_prompt("   ")

    # -------------------------------------------------------------------------
    # validate_template
    # -------------------------------------------------------------------------

    def test_validate_template_succeeds_with_all_variables(self):
        # Arrange
        template = "cli --model %MODEL% --prompt %PROMPT% %IMAGE_PATHS%"

        # Act
        is_valid, error = CommandBuilder.validate_template(template)

        # Assert
        assert is_valid is True
        assert error == ""

    def test_validate_template_fails_on_empty(self):
        # Arrange
        template = ""

        # Act
        is_valid, error = CommandBuilder.validate_template(template)

        # Assert
        assert is_valid is False
        assert "Template is empty" in error

    def test_validate_template_fails_without_model(self):
        # Arrange
        template = "cli --prompt %PROMPT% %IMAGE_PATHS%"

        # Act
        is_valid, error = CommandBuilder.validate_template(template)

        # Assert
        assert is_valid is False
        assert "%MODEL%" in error

    def test_validate_template_fails_without_prompt(self):
        # Arrange
        template = "cli --model %MODEL% %IMAGE_PATHS%"

        # Act
        is_valid, error = CommandBuilder.validate_template(template)

        # Assert
        assert is_valid is False
        assert "%PROMPT%" in error

    def test_validate_template_fails_without_image_paths(self):
        # Arrange
        template = "cli --model %MODEL% --prompt %PROMPT%"

        # Act
        is_valid, error = CommandBuilder.validate_template(template)

        # Assert
        assert is_valid is False
        assert "%IMAGE_PATHS%" in error

    # -------------------------------------------------------------------------
    # extract_variables
    # -------------------------------------------------------------------------

    def test_extract_variables_returns_all_variables(self):
        # Arrange
        template = "cli --model %MODEL% --prompt %PROMPT% %IMAGE_PATHS% --custom %CUSTOM%"

        # Act
        variables = CommandBuilder.extract_variables(template)

        # Assert
        assert "MODEL" in variables
        assert "PROMPT" in variables
        assert "IMAGE_PATHS" in variables
        assert "CUSTOM" in variables

    def test_extract_variables_returns_empty_for_no_variables(self):
        # Arrange
        template = "cli --no-variables-here"

        # Act
        variables = CommandBuilder.extract_variables(template)

        # Assert
        assert variables == []

    # -------------------------------------------------------------------------
    # get_example_template
    # -------------------------------------------------------------------------

    def test_get_example_template_returns_valid_template(self):
        # Act
        example = CommandBuilder.get_example_template()

        # Assert
        assert "%MODEL%" in example
        assert "%PROMPT%" in example
        assert "%IMAGE_PATHS%" in example
        is_valid, _ = CommandBuilder.validate_template(example)
        assert is_valid is True
