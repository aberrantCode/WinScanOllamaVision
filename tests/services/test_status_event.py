"""Tests for the StatusEvent dataclass."""

from datetime import datetime, timezone

from services.status_event import LEVEL_ORDER, StatusEvent


def test_event_defaults_produce_unique_ids():
    """Two events created with the same payload get distinct event_ids."""
    a = StatusEvent(level="info", feature="X", title="t")
    b = StatusEvent(level="info", feature="X", title="t")
    assert a.event_id != b.event_id


def test_event_default_timestamp_is_utc_aware():
    """occurred_at defaults to a timezone-aware UTC timestamp."""
    e = StatusEvent(level="info", feature="X", title="t")
    assert e.occurred_at.tzinfo is not None
    assert e.occurred_at.tzinfo.utcoffset(e.occurred_at) == timezone.utc.utcoffset(e.occurred_at)


def test_level_order_is_monotonic():
    """debug < info < warn < error."""
    assert LEVEL_ORDER["debug"] < LEVEL_ORDER["info"]
    assert LEVEL_ORDER["info"] < LEVEL_ORDER["warn"]
    assert LEVEL_ORDER["warn"] < LEVEL_ORDER["error"]


def test_is_at_least_respects_ordering():
    """warn event is ≥ info threshold but not ≥ error threshold."""
    warn_event = StatusEvent(level="warn", feature="X", title="t")
    assert warn_event.is_at_least("info") is True
    assert warn_event.is_at_least("warn") is True
    assert warn_event.is_at_least("error") is False


def test_is_frozen():
    """Dataclass is frozen — attribute assignment raises."""
    e = StatusEvent(level="info", feature="X", title="t")
    try:
        e.title = "mutated"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("StatusEvent should be immutable")


def test_context_defaults_to_independent_dict():
    """Two events don't share the same context dict (dataclass field default_factory)."""
    a = StatusEvent(level="info", feature="X", title="A")
    b = StatusEvent(level="info", feature="X", title="B")
    # frozen dataclass forbids mutation via `=` on the event, but mutating
    # the underlying dict is still allowed and must not bleed between events.
    a.context["k"] = "v"
    assert "k" not in b.context


def test_explicit_occurred_at_preserved():
    """Explicit occurred_at is carried through verbatim."""
    ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    e = StatusEvent(level="info", feature="X", title="t", occurred_at=ts)
    assert e.occurred_at == ts
