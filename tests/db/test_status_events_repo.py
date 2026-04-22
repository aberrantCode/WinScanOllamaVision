"""Tests for StatusEventsRepository (schema + insert + dedup + retention)."""

import os
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from db.connection import DatabaseConnection
from db.repositories.status_events_repo import StatusEventsRepository
from db.schema import create_all_tables
from services.status_event import StatusEvent


@pytest.fixture
def repo():
    """Temporary DB + repository for a single test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    conn = DatabaseConnection(path)
    create_all_tables(conn)
    try:
        yield StatusEventsRepository(conn)
    finally:
        conn.close()
        os.unlink(path)


def _event(**overrides):
    base = {
        "level": "error",
        "feature": "Analyze → Re-analyze",
        "title": "Boom",
        "detail": "detail text",
        "source": "analysis_worker.py:155",
        "context": {"k": "v"},
        "file_path": "/path/foo.png",
    }
    base.update(overrides)
    return StatusEvent(**base)


def test_insert_creates_row(repo):
    row_id = repo.insert(_event(), session_id="s1")
    assert row_id > 0
    rows = repo.recent()
    assert len(rows) == 1
    assert rows[0]["title"] == "Boom"
    assert rows[0]["coalesced_count"] == 1
    assert rows[0]["session_id"] == "s1"


def test_context_json_roundtrips_as_dict(repo):
    repo.insert(_event(context={"a": 1, "b": [2, 3]}), session_id="s1")
    rows = repo.recent()
    assert rows[0]["context_json"] == {"a": 1, "b": [2, 3]}


def test_dedup_bumps_coalesced_count_on_same_title(repo):
    repo.insert(_event(), session_id="s1")
    repo.insert(_event(), session_id="s1")
    repo.insert(_event(), session_id="s1")
    rows = repo.recent()
    assert len(rows) == 1
    assert rows[0]["coalesced_count"] == 3


def test_dedup_does_not_coalesce_different_titles(repo):
    repo.insert(_event(title="A"), session_id="s1")
    repo.insert(_event(title="B"), session_id="s1")
    assert len(repo.recent()) == 2


def test_dedup_does_not_coalesce_different_levels(repo):
    repo.insert(_event(level="warn"), session_id="s1")
    repo.insert(_event(level="error"), session_id="s1")
    assert len(repo.recent()) == 2


def test_dedup_window_expires(repo):
    """An event outside the dedup window inserts as a new row."""
    repo.insert(_event(), session_id="s1", dedup_seconds=0)
    time.sleep(1.1)
    repo.insert(_event(), session_id="s1", dedup_seconds=1)
    rows = repo.recent()
    # A 1-second window after a 1.1s gap should NOT coalesce — two rows.
    assert len(rows) == 2


def test_recent_honors_limit(repo):
    for i in range(10):
        repo.insert(_event(title=f"T{i}"), session_id="s1")
    rows = repo.recent(limit=5)
    assert len(rows) == 5


def test_recent_filters_by_min_level(repo):
    repo.insert(_event(level="info", title="I"), session_id="s1")
    repo.insert(_event(level="warn", title="W"), session_id="s1")
    repo.insert(_event(level="error", title="E"), session_id="s1")
    rows = repo.recent(min_level="warn")
    assert {r["title"] for r in rows} == {"W", "E"}


def test_recent_filters_by_feature_prefix(repo):
    repo.insert(_event(feature="Analyze → Start", title="a"), session_id="s1")
    repo.insert(_event(feature="Bundle → Export", title="b"), session_id="s1")
    rows = repo.recent(feature_prefix="Analyze")
    assert len(rows) == 1
    assert rows[0]["title"] == "a"


def test_recent_filters_by_session_id(repo):
    repo.insert(_event(title="old"), session_id="old-session")
    repo.insert(_event(title="new"), session_id="new-session")
    rows = repo.recent(session_id="new-session")
    assert len(rows) == 1
    assert rows[0]["title"] == "new"


def test_by_correlation_returns_all_related(repo):
    cid = str(uuid.uuid4())
    repo.insert(_event(correlation_id=cid, title="a"), session_id="s1")
    repo.insert(_event(correlation_id=cid, title="b"), session_id="s1")
    repo.insert(_event(correlation_id="other", title="c"), session_id="s1")
    rows = repo.by_correlation(cid)
    assert {r["title"] for r in rows} == {"a", "b"}


def test_star_and_unstar(repo):
    rid = repo.insert(_event(), session_id="s1")
    assert repo.recent()[0]["starred"] == 0
    repo.set_starred(rid, True)
    assert repo.recent()[0]["starred"] == 1
    repo.set_starred(rid, False)
    assert repo.recent()[0]["starred"] == 0


def test_acknowledge_all_marks_everything_acknowledged(repo):
    repo.insert(_event(title="a"), session_id="s1")
    repo.insert(_event(title="b"), session_id="s1")
    assert repo.unacknowledged_count(min_level="warn") == 2
    repo.acknowledge_all()
    assert repo.unacknowledged_count(min_level="warn") == 0


def test_unacknowledged_count_respects_min_level(repo):
    repo.insert(_event(level="info", title="i"), session_id="s1")
    repo.insert(_event(level="error", title="e"), session_id="s1")
    assert repo.unacknowledged_count(min_level="warn") == 1
    assert repo.unacknowledged_count(min_level="info") == 2


def test_delete_by_id(repo):
    rid = repo.insert(_event(), session_id="s1")
    repo.delete_by_id(rid)
    assert repo.recent() == []


def test_purge_older_than_removes_old_unstarred(repo):
    # Insert an event, then age its occurred_at by poking the DB directly
    rid = repo.insert(_event(), session_id="s1")
    old = (datetime.now(timezone.utc) - timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
    repo.conn.execute("UPDATE status_events SET occurred_at = ? WHERE id = ?", (old, rid))
    repo.conn.commit()

    # Insert a fresh one
    repo.insert(_event(title="fresh"), session_id="s1")

    purged = repo.purge_older_than(retention_days=30)
    assert purged == 1
    rows = repo.recent()
    assert len(rows) == 1
    assert rows[0]["title"] == "fresh"


def test_purge_preserves_starred_events(repo):
    rid = repo.insert(_event(), session_id="s1")
    repo.set_starred(rid, True)
    old = (datetime.now(timezone.utc) - timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
    repo.conn.execute("UPDATE status_events SET occurred_at = ? WHERE id = ?", (old, rid))
    repo.conn.commit()

    purged = repo.purge_older_than(retention_days=30)
    assert purged == 0
    rows = repo.recent()
    assert len(rows) == 1
