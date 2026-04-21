"""Tests for the GitHub issue URL builder."""

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from services.issue_template import (
    GITHUB_ISSUE_BASE_URL,
    build_github_issue_url,
    build_issue_body,
    build_issue_template,
    derive_labels,
)
from services.status_event import StatusEvent


def _event(**overrides):
    base = {
        "level": "error",
        "feature": "Analyze → Re-analyze Files",
        "title": "Re-analysis failed: provider unreachable",
        "detail": "HTTPSConnectionPool: Max retries exceeded",
        "source": "analysis_worker.py:155",
        "traceback": "Traceback (most recent call last):\n  ...\nRuntimeError: boom",
        "context": {"provider": "claude_cli", "model": "claude-3-5-sonnet"},
        "file_path": "C:/scans/page_042.png",
        "correlation_id": "job-9b2d",
        "occurred_at": datetime(2026, 4, 20, 14, 22, 8, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return StatusEvent(**base)


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


def test_labels_include_area_severity_and_auto_filed():
    labels = derive_labels(_event())
    assert "auto-filed" in labels
    assert "area:analyze" in labels
    assert "severity:error" in labels


def test_labels_for_unknown_feature_area_omit_area_label():
    labels = derive_labels(_event(feature="Mystery → Thing"))
    assert "auto-filed" in labels
    assert "severity:error" in labels
    assert all(not lbl.startswith("area:") for lbl in labels)


# ---------------------------------------------------------------------------
# Body rendering
# ---------------------------------------------------------------------------


def test_body_redacts_paths_by_default():
    body = build_issue_body(_event(), app_version="0.3.2")
    assert "C:/scans/page_042.png" not in body
    assert "<redacted>/page_042.png" in body


def test_body_includes_full_path_when_redaction_disabled():
    body = build_issue_body(_event(), app_version="0.3.2", redact_paths=False)
    assert "C:/scans/page_042.png" in body


def test_body_renders_context_as_markdown_table():
    body = build_issue_body(_event(), app_version="0.3.2")
    assert "| Key | Value |" in body
    assert "| provider | claude_cli |" in body
    # model value rendered (JSON-serialized since non-string)
    assert "model" in body


def test_body_includes_system_info_when_requested():
    body = build_issue_body(_event(), app_version="0.3.2", include_system_info=True)
    assert "app_version" in body
    assert "0.3.2" in body
    assert "python" in body


def test_body_can_omit_system_info():
    body = build_issue_body(_event(), app_version="0.3.2", include_system_info=False)
    assert "app_version" not in body


def test_body_can_omit_traceback():
    body = build_issue_body(_event(), app_version="0.3.2", include_traceback=False)
    assert "Traceback" not in body


def test_body_handles_missing_file_path_gracefully():
    body = build_issue_body(_event(file_path=None), app_version="0.3.2")
    assert "**File:** `_(none)_`" in body


def test_body_uses_utc_timestamp():
    body = build_issue_body(_event(), app_version="0.3.2")
    assert "2026-04-20 14:22:08 UTC" in body


# ---------------------------------------------------------------------------
# URL building
# ---------------------------------------------------------------------------


def test_url_uses_default_github_base():
    url = build_github_issue_url(_event(), app_version="0.3.2")
    assert url.startswith(GITHUB_ISSUE_BASE_URL + "?")


def test_url_encodes_title_body_and_labels():
    url = build_github_issue_url(_event(), app_version="0.3.2")
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert query["title"][0] == "Re-analysis failed: provider unreachable"
    assert "Feature:" in query["body"][0]
    labels = query["labels"][0].split(",")
    assert set(labels) >= {"auto-filed", "area:analyze", "severity:error"}


def test_url_accepts_custom_base():
    url = build_github_issue_url(
        _event(),
        app_version="0.3.2",
        base_url="https://example.com/issues/new",
    )
    assert url.startswith("https://example.com/issues/new?")


def test_template_returns_matching_fields():
    tmpl = build_issue_template(_event(), app_version="0.3.2")
    assert tmpl.title == "Re-analysis failed: provider unreachable"
    assert "auto-filed" in tmpl.labels
    assert tmpl.body  # non-empty
