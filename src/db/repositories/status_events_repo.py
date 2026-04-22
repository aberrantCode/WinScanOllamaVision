"""
Repository for the ``status_events`` table — the durable backing store for
the Status History feature.

Keeps DB access isolated from the ``StatusReporter`` so the reporter stays
easy to test against a MagicMock, and so SQL schema changes only ripple
through here.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from db.connection import DatabaseConnection
from services.status_event import StatusEvent

# Time window for coalescing: if an event with the same (level, feature,
# title, file_path) already exists within this many seconds, we increment
# its coalesced_count instead of inserting a new row. Value is a default;
# StatusReporter may override per-call.
DEFAULT_DEDUP_SECONDS = 60


class StatusEventsRepository:
    """Focused DB access for status_events rows.

    The repository is intentionally thin — no business rules, no Qt. It
    produces and accepts ``StatusEvent`` dataclasses (plus the session_id
    column, which is a per-app-run identifier the reporter owns).
    """

    def __init__(self, conn: DatabaseConnection):
        self.conn = conn

    # ---- Writes ----------------------------------------------------------

    def insert(
        self,
        event: StatusEvent,
        session_id: str,
        *,
        dedup_seconds: int = DEFAULT_DEDUP_SECONDS,
    ) -> int:
        """Insert an event, coalescing near-duplicates.

        Returns the row id of either the newly inserted event or the
        existing row whose ``coalesced_count`` was bumped.

        Deduplication rule: if a row exists with the same level, feature,
        title, and file_path, inserted less than ``dedup_seconds`` ago,
        its ``coalesced_count`` is incremented and its ``occurred_at`` is
        *not* updated (the first timestamp is the interesting one; callers
        see the count to know repetition is occurring).
        """
        # Look up any recent matching row
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=dedup_seconds)
        existing = self.conn.fetch_one(
            """
            SELECT id FROM status_events
             WHERE level     = ?
               AND feature   = ?
               AND title     = ?
               AND COALESCE(file_path,'') = COALESCE(?,'')
               AND occurred_at >= ?
             ORDER BY occurred_at DESC
             LIMIT 1
            """,
            (
                event.level,
                event.feature,
                event.title,
                event.file_path,
                cutoff.strftime("%Y-%m-%d %H:%M:%S.%f"),
            ),
        )
        if existing is not None:
            row_id = int(existing[0])
            self.conn.execute(
                "UPDATE status_events SET coalesced_count = coalesced_count + 1 WHERE id = ?",
                (row_id,),
            )
            self.conn.commit()
            return row_id

        context_json = json.dumps(event.context, default=str) if event.context else None
        occurred = event.occurred_at
        if occurred.tzinfo is None:
            occurred = occurred.replace(tzinfo=timezone.utc)
        occurred_str = occurred.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

        cursor = self.conn.execute(
            """
            INSERT INTO status_events (
                event_id, occurred_at, session_id, level, feature, source,
                title, detail, traceback, context_json, file_path,
                correlation_id, starred, acknowledged, coalesced_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1)
            """,
            (
                event.event_id,
                occurred_str,
                session_id,
                event.level,
                event.feature,
                event.source,
                event.title,
                event.detail or None,
                event.traceback,
                context_json,
                event.file_path,
                event.correlation_id,
            ),
        )
        self.conn.commit()
        return int(cursor.lastrowid or 0)

    def set_starred(self, row_id: int, starred: bool) -> None:
        """Toggle the starred flag on an event row."""
        self.conn.execute(
            "UPDATE status_events SET starred = ? WHERE id = ?",
            (1 if starred else 0, row_id),
        )
        self.conn.commit()

    def set_acknowledged(self, row_id: int, acknowledged: bool = True) -> None:
        """Mark an event as seen/acknowledged."""
        self.conn.execute(
            "UPDATE status_events SET acknowledged = ? WHERE id = ?",
            (1 if acknowledged else 0, row_id),
        )
        self.conn.commit()

    def acknowledge_all(self) -> None:
        """Mark every event as acknowledged (used when dropdown opens)."""
        self.conn.execute("UPDATE status_events SET acknowledged = 1 WHERE acknowledged = 0")
        self.conn.commit()

    def delete_by_id(self, row_id: int) -> None:
        """Remove a single event from history."""
        self.conn.execute("DELETE FROM status_events WHERE id = ?", (row_id,))
        self.conn.commit()

    def purge_older_than(self, retention_days: int) -> int:
        """Delete unstarred events older than ``retention_days``. Returns the row count."""
        if retention_days <= 0:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        cursor = self.conn.execute(
            """
            DELETE FROM status_events
             WHERE starred = 0
               AND occurred_at < ?
            """,
            (cutoff.strftime("%Y-%m-%d %H:%M:%S"),),
        )
        self.conn.commit()
        return int(cursor.rowcount or 0)

    # ---- Reads -----------------------------------------------------------

    def recent(
        self,
        *,
        limit: int = 50,
        min_level: str | None = None,
        feature_prefix: str | None = None,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return recent events (newest first), optionally filtered."""
        clauses: list[str] = []
        params: list[Any] = []
        if min_level:
            rank_map = {"debug": 0, "info": 1, "warn": 2, "error": 3}
            allowed = [lvl for lvl, rank in rank_map.items() if rank >= rank_map[min_level]]
            placeholders = ",".join("?" for _ in allowed)
            clauses.append(f"level IN ({placeholders})")
            params.extend(allowed)
        if feature_prefix:
            clauses.append("feature LIKE ?")
            params.append(f"{feature_prefix}%")
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(int(limit))
        rows = self.conn.fetch_all_dicts(
            f"""
            SELECT id, event_id, occurred_at, session_id, level, feature, source,
                   title, detail, traceback, context_json, file_path,
                   correlation_id, starred, acknowledged, coalesced_count
              FROM status_events
              {where}
              ORDER BY occurred_at DESC, id DESC
              LIMIT ?
            """,
            tuple(params),
            json_fields=["context_json"],
        )
        return rows

    def by_correlation(self, correlation_id: str) -> list[dict[str, Any]]:
        """Return all events sharing a correlation id, oldest first."""
        return self.conn.fetch_all_dicts(
            """
            SELECT id, event_id, occurred_at, session_id, level, feature, source,
                   title, detail, traceback, context_json, file_path,
                   correlation_id, starred, acknowledged, coalesced_count
              FROM status_events
             WHERE correlation_id = ?
             ORDER BY occurred_at ASC, id ASC
            """,
            (correlation_id,),
            json_fields=["context_json"],
        )

    def unacknowledged_count(self, *, min_level: str = "warn") -> int:
        """Count events at ≥ ``min_level`` that haven't been acknowledged yet."""
        rank_map = {"debug": 0, "info": 1, "warn": 2, "error": 3}
        allowed = [lvl for lvl, rank in rank_map.items() if rank >= rank_map[min_level]]
        placeholders = ",".join("?" for _ in allowed)
        row = self.conn.fetch_one(
            f"""
            SELECT COUNT(*) FROM status_events
             WHERE acknowledged = 0
               AND level IN ({placeholders})
            """,
            tuple(allowed),
        )
        return int(row[0]) if row else 0
