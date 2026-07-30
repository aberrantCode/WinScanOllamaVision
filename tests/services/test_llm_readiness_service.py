"""Tests for LLMReadinessService — reachability, model presence, and the
policy-gated download path. Providers and OllamaService are mocked; no real
network call or model pull is ever made.
"""

from unittest.mock import MagicMock

import pytest

from services.llm_readiness_service import (
    LLMReadinessService,
    ReadinessResult,
    _model_is_available,
    _normalize_policy,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def make_config(active="ollama", base_url="http://localhost:11434"):
    cfg = MagicMock()
    cfg.get_active_provider.return_value = active

    def _get_setting(section, key, default=None):
        if section == "Ollama" and key == "base_url":
            return base_url
        return default

    cfg.get_setting.side_effect = _get_setting
    return cfg


def make_provider(
    *, name="ollama", reachable=True, model="qwen2.5-vl", available=None, downloadable=True
):
    """Build a mock provider. If downloadable, attach a mock .service.pull_model."""
    provider = MagicMock()
    provider.test_connection.return_value = reachable
    provider.get_default_model.return_value = model
    provider.get_available_models.return_value = list(available or [])
    if downloadable:
        provider.service = MagicMock()
    else:
        # CLI providers have no usable download service.
        del provider.service
    return provider


@pytest.fixture
def reporter():
    return MagicMock()


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_model_is_available_exact_and_tagged():
    assert _model_is_available("qwen2.5-vl", ["qwen2.5-vl:latest"]) is True
    assert _model_is_available("qwen2.5-vl", ["qwen2.5-vl"]) is True
    assert _model_is_available("qwen2.5-vl:latest", ["qwen2.5-vl"]) is True
    assert _model_is_available("llava", ["qwen2.5-vl:latest"]) is False
    assert _model_is_available("", ["qwen2.5-vl"]) is False


def test_normalize_policy_defaults_to_prompt():
    assert _normalize_policy("off") == "off"
    assert _normalize_policy("AUTO") == "auto"
    assert _normalize_policy("  Prompt ") == "prompt"
    assert _normalize_policy("garbage") == "prompt"
    assert _normalize_policy(None) == "prompt"


# ---------------------------------------------------------------------------
# check_readiness
# ---------------------------------------------------------------------------


def test_check_readiness_reachable_and_present(reporter):
    provider = make_provider(available=["qwen2.5-vl:latest"])
    svc = LLMReadinessService(make_config(), provider=provider, reporter=reporter)

    result = svc.check_readiness()

    assert isinstance(result, ReadinessResult)
    assert result.reachable is True
    assert result.model_available is True
    assert result.ok is True
    assert result.can_download is True
    # Pure check must not emit.
    reporter.warn.assert_not_called()
    reporter.error.assert_not_called()


def test_check_readiness_reachable_but_missing(reporter):
    provider = make_provider(available=["llava:latest"])
    svc = LLMReadinessService(make_config(), provider=provider, reporter=reporter)

    result = svc.check_readiness()

    assert result.reachable is True
    assert result.model_available is False
    assert result.ok is False
    reporter.error.assert_not_called()


def test_check_readiness_unreachable(reporter):
    provider = make_provider(reachable=False)
    svc = LLMReadinessService(make_config(), provider=provider, reporter=reporter)

    result = svc.check_readiness()

    assert result.reachable is False
    assert result.ok is False
    assert result.model_available is False


def test_check_readiness_cli_provider_missing_cannot_download(reporter):
    provider = make_provider(
        name="claude_cli", model="claude-3-5-sonnet-20241022", available=[], downloadable=False
    )
    svc = LLMReadinessService(
        make_config(active="claude_cli"), provider=provider, reporter=reporter
    )

    result = svc.check_readiness()

    assert result.can_download is False
    assert result.ok is False
    assert "cannot be auto-downloaded" in result.message


def test_check_readiness_provider_construction_failure(reporter):
    """When the factory can't build a provider, return a not-ok result."""
    cfg = make_config(active="bogus")
    svc = LLMReadinessService(cfg, reporter=reporter)
    # No provider injected and factory will raise for 'bogus'.
    result = svc.check_readiness()

    assert result.reachable is False
    assert result.ok is False


# ---------------------------------------------------------------------------
# ensure_model — download policy
# ---------------------------------------------------------------------------


def test_ensure_model_present_no_download(reporter):
    provider = make_provider(available=["qwen2.5-vl:latest"])
    svc = LLMReadinessService(make_config(), provider=provider, reporter=reporter)

    result = svc.ensure_model("auto")

    assert result.ok is True
    provider.service.pull_model.assert_not_called()


def test_ensure_model_auto_downloads_then_ok(reporter):
    """Missing → auto policy pulls, then a re-check finds it present."""
    provider = make_provider(available=[])

    # First get_available_models (check) returns empty; after pull it returns model.
    provider.get_available_models.side_effect = [[], ["qwen2.5-vl:latest"], ["qwen2.5-vl:latest"]]

    svc = LLMReadinessService(make_config(), provider=provider, reporter=reporter)
    result = svc.ensure_model("auto")

    provider.service.pull_model.assert_called_once()
    assert provider.service.pull_model.call_args[0][0] == "qwen2.5-vl"
    assert result.ok is True
    reporter.warn.assert_called()  # "downloading" warn emitted


def test_ensure_model_prompt_approved_downloads(reporter):
    provider = make_provider(available=[])
    provider.get_available_models.side_effect = [[], ["qwen2.5-vl:latest"]]
    svc = LLMReadinessService(make_config(), provider=provider, reporter=reporter)

    approve = MagicMock(return_value=True)
    result = svc.ensure_model("prompt", approve_callback=approve)

    approve.assert_called_once_with("qwen2.5-vl")
    provider.service.pull_model.assert_called_once()
    assert result.ok is True


def test_ensure_model_prompt_denied_no_download(reporter):
    provider = make_provider(available=[])
    svc = LLMReadinessService(make_config(), provider=provider, reporter=reporter)

    approve = MagicMock(return_value=False)
    result = svc.ensure_model("prompt", approve_callback=approve)

    approve.assert_called_once_with("qwen2.5-vl")
    provider.service.pull_model.assert_not_called()
    assert result.ok is False


def test_ensure_model_prompt_no_callback_does_not_download(reporter):
    """Non-blocking startup passes no callback → never downloads on prompt."""
    provider = make_provider(available=[])
    svc = LLMReadinessService(make_config(), provider=provider, reporter=reporter)

    result = svc.ensure_model("prompt", approve_callback=None)

    provider.service.pull_model.assert_not_called()
    assert result.ok is False
    reporter.warn.assert_called()  # nudge, not error
    reporter.error.assert_not_called()


def test_ensure_model_off_never_downloads(reporter):
    provider = make_provider(available=[])
    svc = LLMReadinessService(make_config(), provider=provider, reporter=reporter)

    result = svc.ensure_model("off")

    provider.service.pull_model.assert_not_called()
    assert result.ok is False
    assert "disabled" in result.message


def test_ensure_model_unreachable_emits_error(reporter):
    provider = make_provider(reachable=False)
    svc = LLMReadinessService(make_config(), provider=provider, reporter=reporter)

    result = svc.ensure_model("auto")

    provider.service.pull_model.assert_not_called()
    assert result.ok is False
    reporter.error.assert_called_once()


def test_ensure_model_cli_missing_emits_error_no_download(reporter):
    provider = make_provider(
        name="claude_cli", model="claude-3-5-sonnet-20241022", available=[], downloadable=False
    )
    svc = LLMReadinessService(
        make_config(active="claude_cli"), provider=provider, reporter=reporter
    )

    result = svc.ensure_model("auto")

    assert result.ok is False
    assert result.can_download is False
    reporter.error.assert_called_once()


def test_ensure_model_download_failure_emits_error(reporter):
    provider = make_provider(available=[])
    provider.service.pull_model.side_effect = RuntimeError("network died")
    svc = LLMReadinessService(make_config(), provider=provider, reporter=reporter)

    result = svc.ensure_model("auto")

    provider.service.pull_model.assert_called_once()
    assert result.ok is False
    assert "network died" in result.message
    reporter.error.assert_called_once()


def test_ensure_model_download_succeeds_but_still_missing(reporter):
    """Pull returns but the model still doesn't resolve → error."""
    provider = make_provider(available=[])
    # check (empty) → pull → recheck still empty
    provider.get_available_models.side_effect = [[], [], []]
    svc = LLMReadinessService(make_config(), provider=provider, reporter=reporter)

    result = svc.ensure_model("auto")

    assert result.ok is False
    reporter.error.assert_called_once()
