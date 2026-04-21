"""Convert a DB row dict returned by StatusEventsRepository into a StatusEvent."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.status_event import StatusEvent, StatusLevel


def _parse_occurred_at(raw: Any) -> datetime:
    """Parse the string timestamp stored in status_events.occurred_at.

    Accepts both the microsecond-precision format used by the repo
    (``'%Y-%m-%d %H:%M:%S.%f'``) and the seconds-precision format SQLite's
    ``CURRENT_TIMESTAMP`` default produces.
    """
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if not isinstance(raw, str):
        return datetime.now(timezone.utc)
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def row_to_status_event(row: dict[str, Any]) -> StatusEvent:
    """Rehydrate a StatusEvent from a ``status_events`` row dict."""
    level: StatusLevel = row.get("level", "info")  # type: ignore[assignment]
    context = row.get("context_json") or {}
    if not isinstance(context, dict):
        context = {}
    return StatusEvent(
        level=level,
        feature=row.get("feature", ""),
        title=row.get("title", ""),
        detail=row.get("detail") or "",
        source=row.get("source"),
        traceback=row.get("traceback"),
        context=context,
        file_path=row.get("file_path"),
        correlation_id=row.get("correlation_id"),
        occurred_at=_parse_occurred_at(row.get("occurred_at")),
        event_id=row.get("event_id") or "",
    )
