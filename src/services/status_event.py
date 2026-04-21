"""
StatusEvent dataclass — immutable record of a single status event.

One event per status-producing occurrence: job started, file failed, setting
saved, etc. Events are the durable unit behind the status history UI spec
at _project_specs/status_history.md.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

StatusLevel = Literal["debug", "info", "warn", "error"]

LEVEL_ORDER: dict[StatusLevel, int] = {
    "debug": 0,
    "info": 1,
    "warn": 2,
    "error": 3,
}


@dataclass(frozen=True, slots=True)
class StatusEvent:
    """An immutable status event.

    Attributes that travel from backend emitters to the UI/DB without
    mutation. The ``feature`` field is the user-facing component name
    ("Analyze → Re-analyze Files"); ``source`` is the developer-facing
    code location ("analysis_worker.py:155"). Both flow into GitHub
    issues but the UI shows ``feature`` prominently and hides ``source``
    behind an "Developer Details" disclosure.
    """

    level: StatusLevel
    feature: str
    title: str
    detail: str = ""
    source: str | None = None
    traceback: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    file_path: str | None = None
    correlation_id: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def level_rank(self) -> int:
        """Integer rank of this event's level; higher is more severe."""
        return LEVEL_ORDER[self.level]

    def is_at_least(self, min_level: StatusLevel) -> bool:
        """Return True if this event's level is ≥ the supplied minimum."""
        return self.level_rank() >= LEVEL_ORDER[min_level]
