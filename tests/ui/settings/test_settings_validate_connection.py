"""
Tests for _SettingsActionsMixin._validate_ollama_connection in ui.settings.settings_actions.

Covers:
- Empty base URL is rejected before attempting a connection
- Unreachable server surfaces a clear failure message
- Reachable server but missing model surfaces a clear failure message
- Reachable server with the model present surfaces success
- Unexpected exceptions during validation are caught and surfaced, not raised
"""

import types
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QApplication, QLabel


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestableActions:
    """Minimal host for _SettingsActionsMixin, binding only what
    _validate_ollama_connection needs — mirrors the TestableModelLoader
    pattern used for _ModelLoaderMixin."""

    def __init__(self, qapp):
        from ui.settings.settings_actions import _SettingsActionsMixin

        self._validate_ollama_connection = types.MethodType(
            _SettingsActionsMixin._validate_ollama_connection, self
        )

        self.ollama_url_edit = MagicMock()
        self.ollama_url_edit.text.return_value = "http://localhost:11434"

        self.ollama_model_combo = MagicMock()
        self.ollama_model_combo.currentData.return_value = "qwen2.5vl:latest"

        self.ollama_timeout_spin = MagicMock()
        self.ollama_timeout_spin.value.return_value = 300

        self.ollama_validate_status_label = QLabel()


@pytest.fixture
def actions(qapp):
    return TestableActions(qapp)


def test_validate_rejects_empty_base_url(actions):
    actions.ollama_url_edit.text.return_value = "   "

    actions._validate_ollama_connection()

    assert "Enter a base URL" in actions.ollama_validate_status_label.text()


def test_validate_reports_unreachable_server(actions):
    with patch("llm_providers.ollama_provider.OllamaProvider") as mock_provider_cls:
        mock_provider_cls.return_value.test_connection.return_value = False

        actions._validate_ollama_connection()

    text = actions.ollama_validate_status_label.text()
    assert "Could not reach" in text
    assert "http://localhost:11434" in text


def test_validate_reports_missing_model_when_reachable(actions):
    with patch("llm_providers.ollama_provider.OllamaProvider") as mock_provider_cls:
        mock_provider_cls.return_value.test_connection.return_value = True
        mock_provider_cls.return_value.get_available_models.return_value = ["llava:latest"]

        actions._validate_ollama_connection()

    text = actions.ollama_validate_status_label.text()
    assert "not downloaded" in text
    assert "qwen2.5vl:latest" in text


def test_validate_reports_success_when_model_present(actions):
    with patch("llm_providers.ollama_provider.OllamaProvider") as mock_provider_cls:
        mock_provider_cls.return_value.test_connection.return_value = True
        mock_provider_cls.return_value.get_available_models.return_value = [
            "qwen2.5vl:latest",
            "llava:latest",
        ]

        actions._validate_ollama_connection()

    text = actions.ollama_validate_status_label.text()
    assert text.startswith("✓")
    assert "qwen2.5vl:latest" in text


def test_validate_success_skips_model_check_when_no_model_selected(actions):
    actions.ollama_model_combo.currentData.return_value = ""

    with patch("llm_providers.ollama_provider.OllamaProvider") as mock_provider_cls:
        mock_provider_cls.return_value.test_connection.return_value = True

        actions._validate_ollama_connection()

        mock_provider_cls.return_value.get_available_models.assert_not_called()

    assert actions.ollama_validate_status_label.text().startswith("✓")


def test_validate_catches_unexpected_exceptions(actions):
    with patch("llm_providers.ollama_provider.OllamaProvider") as mock_provider_cls:
        mock_provider_cls.side_effect = RuntimeError("boom")

        # Must not raise — the button click handler cannot propagate.
        actions._validate_ollama_connection()

    text = actions.ollama_validate_status_label.text()
    assert "Validation failed" in text
    assert "boom" in text
