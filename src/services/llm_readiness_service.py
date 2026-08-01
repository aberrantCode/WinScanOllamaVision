"""
LLM readiness preflight — check that the active provider is reachable and its
configured model is present *before* analysis runs, and self-heal by pulling a
missing Ollama model when policy permits.

The service is deliberately synchronous. Network I/O (reachability probe, model
list, and the potentially multi-GB ``pull``) happens on the calling thread, so
callers MUST run it off the Qt main thread (see ``llm_readiness_worker`` for the
startup/settings worker wrapper).

Capability model
----------------
Only Ollama can download models. Claude/Gemini CLI providers expose a static
model list, so their "readiness" is: CLI reachable + configured model in the
available list. For them ``can_download`` is ``False`` and a missing model is a
terminal error the user resolves by installing it CLI-side or picking a valid
model name.

Status reporting
----------------
The service emits StatusEvents through the process-wide ``StatusReporter``:
``warn`` when a model is missing and about to download, ``error`` when the host
is unreachable or a download fails. Success is silent. Emission lives in
``ensure_model`` (the side-effecting path); ``check_readiness`` is pure.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

FEATURE = "llm_preflight"

# Accepted values for the model-download policy.
POLICY_OFF = "off"
POLICY_PROMPT = "prompt"
POLICY_AUTO = "auto"
_VALID_POLICIES = frozenset({POLICY_OFF, POLICY_PROMPT, POLICY_AUTO})


@dataclass(frozen=True)
class ReadinessResult:
    """Immutable snapshot of provider/model readiness.

    Attributes:
        provider_name: Active provider ("ollama" / "claude_cli" / "gemini_cli").
        reachable: True if ``test_connection()`` succeeded.
        model: The configured/default model that analysis will use.
        model_available: True if ``model`` is present in the provider's
            available-model list.
        can_download: True only for providers that can pull models (Ollama).
        ok: True when the provider is reachable and the model is available.
        message: Human-readable summary suitable for a toast/dialog.
    """

    provider_name: str
    reachable: bool
    model: str
    model_available: bool
    can_download: bool
    ok: bool
    message: str


def _model_is_available(model: str, available: list[str]) -> bool:
    """Return True if ``model`` matches any name in ``available``.

    Ollama reports tagged names ("qwen2.5vl:latest") while config may store
    the untagged base ("qwen2.5vl"); match either direction on the
    ``base:tag`` boundary. Mirrors ``OllamaService.pull_model``'s verify logic.
    """
    if not model:
        return False
    for name in available:
        if name == model:
            return True
        if name.startswith(model + ":"):
            return True
        if model.startswith(name + ":"):
            return True
    return False


def _normalize_policy(policy: str | None) -> str:
    """Coerce an arbitrary policy string to a known value (default: prompt)."""
    value = (policy or "").strip().lower()
    return value if value in _VALID_POLICIES else POLICY_PROMPT


class LLMReadinessService:
    """Reusable readiness check + gated model download for the active provider."""

    def __init__(
        self,
        config_manager: Any,
        *,
        provider: Any = None,
        reporter: Any = None,
    ) -> None:
        """Construct the service.

        Args:
            config_manager: ``ConfigManager`` used to resolve the active provider
                and build it via ``ProviderFactory``.
            provider: Optional pre-built provider (tests inject a mock). When
                omitted the provider is created lazily on first use.
            reporter: Optional ``StatusReporter``. When omitted the process-wide
                singleton is used lazily at emit time. Pass one in tests.
        """
        self._config = config_manager
        self._provider = provider
        self._reporter = reporter
        self._provider_error: str | None = None

    # ---- Provider access -------------------------------------------------

    def _get_provider(self) -> Any:
        """Build (once) and return the active provider, or None on failure."""
        if self._provider is not None:
            return self._provider
        try:
            from llm_providers.provider_factory import ProviderFactory

            self._provider = ProviderFactory.create_from_config_manager(self._config)
        except Exception as exc:  # provider misconfigured / unknown
            self._provider_error = str(exc)
            self._provider = None
        return self._provider

    def _provider_name(self) -> str:
        try:
            return str(self._config.get_active_provider())
        except Exception:
            return "unknown"

    def _base_url(self) -> str:
        return str(self._config.get_setting("Ollama", "base_url", "") or "")

    def _reporter_or_none(self) -> Any:
        if self._reporter is not None:
            return self._reporter
        try:
            from services.status_reporter import get_reporter

            self._reporter = get_reporter()
        except Exception:
            self._reporter = None
        return self._reporter

    def _context(self, result: ReadinessResult) -> dict[str, str]:
        return {
            "provider": result.provider_name,
            "model": result.model,
            "base_url": self._base_url(),
        }

    # ---- Pure check ------------------------------------------------------

    def check_readiness(self) -> ReadinessResult:
        """Probe reachability and model presence without side effects.

        Never downloads and never emits StatusEvents — pure inspection so it is
        safe to call repeatedly and cheap to unit-test.
        """
        provider_name = self._provider_name()
        can_download = provider_name == "ollama"

        provider = self._get_provider()
        if provider is None:
            return ReadinessResult(
                provider_name=provider_name,
                reachable=False,
                model="",
                model_available=False,
                can_download=can_download,
                ok=False,
                message=(
                    f"Could not initialize provider '{provider_name}': "
                    f"{self._provider_error or 'unknown error'}"
                ),
            )

        model = ""
        try:
            model = str(provider.get_default_model() or "")
        except Exception:
            model = ""

        reachable = False
        try:
            reachable = bool(provider.test_connection())
        except Exception:
            reachable = False

        if not reachable:
            return ReadinessResult(
                provider_name=provider_name,
                reachable=False,
                model=model,
                model_available=False,
                can_download=can_download,
                ok=False,
                message=(
                    f"{provider_name} is not reachable. Is the server/CLI running and reachable?"
                ),
            )

        available: list[str] = []
        try:
            available = list(provider.get_available_models())
        except Exception:
            available = []

        model_available = _model_is_available(model, available)
        if model_available:
            message = f"Model '{model}' is ready on {provider_name}."
        elif can_download:
            message = f"Model '{model}' is not installed on {provider_name}."
        else:
            message = (
                f"Model '{model}' is not available for {provider_name}. "
                "It cannot be auto-downloaded — install it CLI-side or select a "
                "valid model."
            )

        return ReadinessResult(
            provider_name=provider_name,
            reachable=True,
            model=model,
            model_available=model_available,
            can_download=can_download,
            ok=model_available,
            message=message,
        )

    # ---- Gated ensure ----------------------------------------------------

    def ensure_model(
        self,
        policy: str,
        *,
        approve_callback: Callable[[str], bool] | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> ReadinessResult:
        """Ensure the configured model is present, downloading if policy allows.

        Args:
            policy: ``off`` | ``prompt`` | ``auto``.
            approve_callback: Called with the model name when policy is
                ``prompt``; download proceeds only if it returns True. If None
                under ``prompt``, no download happens (used by non-blocking
                startup, which defers approval to Settings).
            progress_callback: Forwarded to ``OllamaService.pull_model`` for
                streamed progress strings.

        Returns:
            A ``ReadinessResult``. On the download path it reflects the
            post-download re-check.
        """
        policy = _normalize_policy(policy)
        result = self.check_readiness()

        # Reachability failure — always an error the user must resolve.
        if not result.reachable:
            self._emit_error(result, "LLM host unreachable")
            return result

        # Already good.
        if result.model_available:
            return result

        # Missing model on a provider that cannot download (CLI providers).
        if not result.can_download:
            self._emit_error(result, "Model not available")
            return result

        # Missing model on Ollama — apply the download policy.
        if policy == POLICY_OFF:
            blocked = replace(
                result,
                ok=False,
                message=(
                    f"Model '{result.model}' is missing and downloads are "
                    "disabled (policy=off). Enable auto-download or install it "
                    "manually."
                ),
            )
            self._emit_warn(blocked, "Model missing (downloads disabled)")
            return blocked

        if policy == POLICY_PROMPT:
            approved = bool(approve_callback(result.model)) if approve_callback else False
            if not approved:
                declined = replace(
                    result,
                    ok=False,
                    message=(f"Model '{result.model}' is missing. Download was not approved."),
                )
                # Non-blocking startup passes no callback: nudge, don't error.
                self._emit_warn(declined, "Model missing — download not approved")
                return declined

        # policy == auto, or prompt approved → download.
        self._emit_warn(
            replace(result, message=f"Downloading model '{result.model}'…"),
            "Model missing — downloading",
        )
        try:
            self._pull_model(result.model, progress_callback)
        except Exception as exc:
            failed = replace(
                result,
                ok=False,
                message=f"Failed to download model '{result.model}': {exc}",
            )
            self._emit_error(failed, "Model download failed", exc=exc)
            return failed

        # Re-check after the pull to confirm the model now resolves.
        rechecked = self.check_readiness()
        if rechecked.ok:
            return rechecked
        still_missing = replace(
            rechecked,
            ok=False,
            message=(f"Model '{result.model}' still not available after download."),
        )
        self._emit_error(still_missing, "Model still missing after download")
        return still_missing

    def _pull_model(self, model: str, progress_callback: Callable[[str], None] | None) -> None:
        """Pull an Ollama model via the provider's underlying OllamaService."""
        provider = self._get_provider()
        service = getattr(provider, "service", None)
        if service is None or not hasattr(service, "pull_model"):
            raise RuntimeError("Active provider does not support model downloads.")
        service.pull_model(model, progress_callback)

    # ---- Emission helpers ------------------------------------------------

    def _emit_warn(self, result: ReadinessResult, title: str) -> None:
        reporter = self._reporter_or_none()
        if reporter is None:
            return
        with contextlib.suppress(Exception):
            reporter.warn(
                FEATURE,
                title,
                detail=result.message,
                context=self._context(result),
            )

    def _emit_error(
        self, result: ReadinessResult, title: str, *, exc: BaseException | None = None
    ) -> None:
        reporter = self._reporter_or_none()
        if reporter is None:
            return
        with contextlib.suppress(Exception):
            reporter.error(
                FEATURE,
                title,
                detail=result.message,
                context=self._context(result),
                exc=exc,
            )
