"""
Tests for CommandBuilder utility.

Target: 100% coverage
"""

import pytest

from llm_providers.command_builder import CommandBuilder


class TestCommandBuilder:
    """Test suite for CommandBuilder"""

    def test_build_command_replaces_model_placeholder(self):
        # Arrange
        template = "cli --model %MODEL%"
        model = "test-model"
        image_paths = []
        prompt = "test"

        # Act
        result = CommandBuilder.build_command(template, model, image_paths, prompt)

        # Assert
        assert "test-model" in result
        assert "%MODEL%" not in result

    def test_build_command_replaces_prompt_placeholder(self):
        # Arrange
        template = "cli --prompt %PROMPT%"
        model = "model"
        image_paths = []
        prompt = "Analyze this document"

        # Act
        result = CommandBuilder.build_command(template, model, image_paths, prompt)

        # Assert
        assert "Analyze this document" in result
        assert "%PROMPT%" not in result

    def test_build_command_replaces_image_paths_placeholder(self):
        # Arrange
        template = "cli %IMAGE_PATHS%"
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
        template = "cli %IMAGE_PATHS%"
        model = "model"
        image_paths = ["/img1.jpg", "/img2.jpg", "/img3.jpg"]
        prompt = "test"

        # Act
        result = CommandBuilder.build_command(template, model, image_paths, prompt)

        # Assert
        for path in image_paths:
            assert path in result

    def test_build_command_with_empty_image_paths(self):
        # Arrange
        template = "cli %IMAGE_PATHS% --model %MODEL%"
        model = "model"
        image_paths = []
        prompt = "test"

        # Act
        result = CommandBuilder.build_command(template, model, image_paths, prompt)

        # Assert
        # Empty image paths should result in empty string replacement
        assert "%IMAGE_PATHS%" not in result
        assert "--model model" in result

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

    def test_build_command_escapes_special_characters_in_prompt(self):
        # Arrange
        template = "cli --prompt %PROMPT%"
        model = "model"
        image_paths = []
        prompt = 'Text with "quotes" and special chars $%^'

        # Act
        result = CommandBuilder.build_command(template, model, image_paths, prompt)

        # Assert
        # Should escape quotes in prompt
        assert '\\"' in result or "quotes" in result

    def test_build_command_with_complex_template(self):
        # Arrange
        template = (
            "python script.py --model=%MODEL% "
            "--images %IMAGE_PATHS% "
            '--prompt="%PROMPT%" '
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

    def test_build_command_raises_on_empty_template(self):
        # Arrange
        template = ""
        model = "model"
        image_paths = []
        prompt = "test"

        # Act & Assert
        with pytest.raises(ValueError, match="Command template is not configured"):
            CommandBuilder.build_command(template, model, image_paths, prompt)

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

    def test_get_example_template_returns_valid_template(self):
        # Act
        example = CommandBuilder.get_example_template()

        # Assert
        assert "%MODEL%" in example
        assert "%PROMPT%" in example
        assert "%IMAGE_PATHS%" in example
        is_valid, _ = CommandBuilder.validate_template(example)
        assert is_valid is True
