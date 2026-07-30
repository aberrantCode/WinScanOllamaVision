"""
Background worker for LLM readiness preflight.

Wraps ``LLMReadinessService.ensure_model`` in a ``QThread`` so the reachability
probe and any (multi-GB) model pull never block the Qt main thread. Used by:

- startup preflight (``main.py``): policy from config, ``approve_callback=None``
  so a missing model is surfaced non-blockingly rather than downloaded behind a
  modal.
- settings save (``settings_window_enhanced.py``): the dialog collects the
  user's approval on the main thread first, then runs this worker with
  ``policy="auto"`` to perform the already-approved download, wiring ``progress``
  to a ``QProgressDialog``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal


class LLMPreflightWorker(QThread):
    """Runs an LLM readiness check (and gated download) off the main thread."""

    # Emitted with the ReadinessResult on completion.
    finished = pyqtSignal(object)
    # Emitted with streamed progress strings during a model pull.
    progress = pyqtSignal(str)
    # Emitted with an error string if the worker itself raises unexpectedly.
    error = pyqtSignal(str)

    def __init__(
        self,
        config_manager: Any,
        policy: str,
        *,
        approve_callback: Callable[[str], bool] | None = None,
    ) -> None:
        super().__init__()
        self._config_manager = config_manager
        self._policy = policy
        self._approve_callback = approve_callback

    def run(self) -> None:
        """Execute the readiness check/download on the worker thread."""
        try:
            # Import inside run() so provider/SDK construction happens on this
            # thread, and to avoid import cost when the worker is never started.
            from services.llm_readiness_service import LLMReadinessService

            service = LLMReadinessService(self._config_manager)
            result = service.ensure_model(
                self._policy,
                approve_callback=self._approve_callback,
                progress_callback=self.progress.emit,
            )
            self.finished.emit(result)
        except Exception as exc:  # pragma: no cover - defensive
            self.error.emit(str(exc))
