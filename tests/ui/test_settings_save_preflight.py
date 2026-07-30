"""Tests for the settings-save readiness preflight routing.

These exercise ``EnhancedSettingsWindow._run_save_preflight`` as an unbound
method against a mock ``self`` so no Qt widgets are constructed. The readiness
service and the theme dialog helpers are patched; the download path is stubbed
via the mocked ``self._download_model_with_progress``.
"""

from unittest.mock import MagicMock, patch

import pytest

from services.llm_readiness_service import ReadinessResult
from ui.settings.settings_window_enhanced import EnhancedSettingsWindow


def _result(**kw):
    base = {
        "provider_name": "ollama",
        "reachable": True,
        "model": "qwen2.5-vl",
        "model_available": True,
        "can_download": True,
        "ok": True,
        "message": "ready",
    }
    base.update(kw)
    return ReadinessResult(**base)


def make_self(*, verify_on_save=True, policy="prompt"):
    s = MagicMock()
    s.config_manager.get_bool.return_value = verify_on_save
    s.config_manager.get_setting.return_value = policy
    s._get_logger.return_value = MagicMock()
    return s


def run_preflight(mock_self, result):
    with patch("services.llm_readiness_service.LLMReadinessService") as mock_service_cls:
        mock_service_cls.return_value.check_readiness.return_value = result
        EnhancedSettingsWindow._run_save_preflight(mock_self)
        return mock_service_cls


# ---------------------------------------------------------------------------


def test_disabled_skips_entirely():
    s = make_self(verify_on_save=False)
    with patch("services.llm_readiness_service.LLMReadinessService") as mock_service_cls:
        EnhancedSettingsWindow._run_save_preflight(s)
        mock_service_cls.assert_not_called()


def test_ready_is_silent():
    s = make_self()
    with patch("ui.theme.styles.show_warning") as warn:
        run_preflight(s, _result(ok=True, model_available=True))
    warn.assert_not_called()
    s._download_model_with_progress.assert_not_called()


def test_unreachable_warns():
    s = make_self()
    with patch("ui.theme.styles.show_warning") as warn:
        run_preflight(s, _result(reachable=False, model_available=False, ok=False))
    warn.assert_called_once()
    assert "Reachable" in warn.call_args[0][1]


def test_cli_missing_warns_no_download():
    s = make_self()
    with patch("ui.theme.styles.show_warning") as warn:
        run_preflight(
            s,
            _result(
                provider_name="claude_cli",
                can_download=False,
                model_available=False,
                ok=False,
            ),
        )
    warn.assert_called_once()
    s._download_model_with_progress.assert_not_called()


def test_policy_off_warns_no_download():
    s = make_self(policy="off")
    with patch("ui.theme.styles.show_warning") as warn:
        run_preflight(s, _result(model_available=False, ok=False))
    warn.assert_called_once()
    s._download_model_with_progress.assert_not_called()


def test_policy_prompt_declined_no_download():
    s = make_self(policy="prompt")
    from PyQt6.QtWidgets import QMessageBox

    with (
        patch("ui.theme.styles.show_warning") as warn,
        patch(
            "PyQt6.QtWidgets.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ),
    ):
        run_preflight(s, _result(model_available=False, ok=False))
    warn.assert_called_once()
    s._download_model_with_progress.assert_not_called()


def test_policy_prompt_approved_downloads_and_reports_ready():
    s = make_self(policy="prompt")
    s._download_model_with_progress.return_value = _result(ok=True, model_available=True)
    from PyQt6.QtWidgets import QMessageBox

    with (
        patch("ui.theme.styles.show_information") as info,
        patch(
            "PyQt6.QtWidgets.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ),
    ):
        run_preflight(s, _result(model_available=False, ok=False))
    s._download_model_with_progress.assert_called_once_with("qwen2.5-vl")
    info.assert_called_once()


def test_policy_auto_downloads_immediately():
    s = make_self(policy="auto")
    s._download_model_with_progress.return_value = _result(ok=True, model_available=True)
    with patch("ui.theme.styles.show_information") as info:
        run_preflight(s, _result(model_available=False, ok=False))
    s._download_model_with_progress.assert_called_once_with("qwen2.5-vl")
    info.assert_called_once()


def test_download_failure_reports_critical():
    s = make_self(policy="auto")
    s._download_model_with_progress.return_value = _result(
        ok=False, model_available=False, message="Failed to download model"
    )
    with patch("ui.theme.styles.show_critical") as crit:
        run_preflight(s, _result(model_available=False, ok=False))
    crit.assert_called_once()
    assert "Failed" in crit.call_args[0][2]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
