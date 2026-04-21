# Feature Spec: Status History

**Status:** Draft
**Author:** Erik (with Claude)
**Target area:** Cross-cutting — replaces the single-line `status_lbl` throughout the app
**Motivation:** Two concrete bugs — [silent "Start Analysis" flash](#bug-context-start-analysis-silence) and [swallowed re-analyze errors](#bug-context-re-analyze-errors) — both stem from the same root cause: ephemeral status. This spec turns status into a durable, queryable artifact the user can browse, inspect, and file issues from.

---

## 1. Goals

1. **No status is lost.** Every status event the backend emits is durable (SQLite-persisted), retrievable after a session restart, and reviewable after the event scrolls off-screen.
2. **Every status can become a bug report.** A user who sees a confusing or failing event can, in three clicks, file a GitHub issue pre-filled with enough context that a developer can fix the issue without re-asking.
3. **Users see feature names, not code paths.** The primary label on every event is the user-visible feature — "Analyze → Re-analyze Files", not `analysis_worker.py::_process_job`. The code path is still captured, but kept behind a developer-details collapsible.
4. **Errors are surfaced proactively, not on demand.** Errors count, error titles, and a "view now" affordance are visible without any user action.
5. **Backward compatible.** The existing `analysis_errors` table stays; this feature adds a parallel `status_events` table. Existing callers of `save_error()` keep working; new code emits richer `StatusEvent`s that wrap both.

---

## 2. Bug contexts this spec resolves

### Bug context: Start Analysis silence

`scan_all_directories()` returns immediately in three scenarios, each with a meaningful `stats["message"]`:

| Condition | Current behavior | Desired behavior |
|---|---|---|
| `AutoAnalysis.enabled = False` | UI flashes, shows "Analysis complete." | Event: **warn** — "Auto-analysis is disabled → open Settings" |
| `get_active_directories() = []` | UI flashes, shows "Analysis complete." | Event: **warn** — "No source directories configured → open Settings" |
| All files cache-hit | UI flashes, shows "Analysis complete." | Event: **info** — "N files already analyzed, 0 new" |

### Bug context: Re-analyze errors

`analysis_worker.py` `ANALYZE_FILES` path silently discards `result["error"]`. Desired: for each failed file, emit an **error** event capturing file path, provider, model, error message, and traceback — plus a summary event at job end — so every failure is one click away from a filed issue.

---

## 3. Data Model

### 3.1 `status_events` table

```sql
CREATE TABLE IF NOT EXISTS status_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    session_id      TEXT        NOT NULL,    -- uuid4, stable for one app run
    level           TEXT        NOT NULL,    -- 'info' | 'warn' | 'error' | 'debug'
    feature         TEXT        NOT NULL,    -- 'Analyze → Start Analysis'
    source          TEXT,                    -- 'analysis_worker.py:155'
    title           TEXT        NOT NULL,    -- one-line summary (shown in dropdown)
    detail          TEXT,                    -- multi-line expanded detail
    traceback       TEXT,                    -- optional Python traceback
    context_json    TEXT,                    -- structured JSON blob (provider/model/file/etc.)
    file_path       TEXT,                    -- the file the event concerns, if any
    correlation_id  TEXT,                    -- job_id or similar, to cluster related events
    starred         INTEGER     NOT NULL DEFAULT 0,   -- user-pinned; exempt from retention
    acknowledged    INTEGER     NOT NULL DEFAULT 0    -- user has "seen" this event
);

CREATE INDEX IF NOT EXISTS idx_status_events_occurred ON status_events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_status_events_level    ON status_events(level);
CREATE INDEX IF NOT EXISTS idx_status_events_feature  ON status_events(feature);
CREATE INDEX IF NOT EXISTS idx_status_events_session  ON status_events(session_id);
```

**Retention:** Default 30 days; purged on app startup by `StatusEventsDB.purge_expired()`. `starred=1` rows are exempt.

### 3.2 Python dataclass

```python
# src/services/status_event.py
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

StatusLevel = Literal["debug", "info", "warn", "error"]

@dataclass(frozen=True, slots=True)
class StatusEvent:
    level: StatusLevel
    feature: str                           # user-visible: "Analyze → Re-analyze"
    title: str                             # one-line: "Re-analysis failed: provider unreachable"
    detail: str = ""                       # multi-line expanded text
    source: str | None = None              # "analysis_worker.py:155"
    traceback: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    file_path: str | None = None
    correlation_id: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
```

---

## 4. Service: `StatusReporter`

A process-wide singleton (`services/status_reporter.py`) both UI and backend emit to. Thread-safe. Emits a Qt signal so UI widgets can subscribe for live updates.

### 4.1 Public API

```python
class StatusReporter(QObject):
    event_recorded = pyqtSignal(object)  # StatusEvent

    def info (self, feature: str, title: str, **kw) -> StatusEvent: ...
    def warn (self, feature: str, title: str, **kw) -> StatusEvent: ...
    def error(self, feature: str, title: str, exc: BaseException | None = None, **kw) -> StatusEvent: ...

    # Low-level — use when you already have a StatusEvent
    def emit(self, event: StatusEvent) -> None: ...

    # Query
    def recent(self, limit: int = 50, level: StatusLevel | None = None,
               feature_prefix: str | None = None, since_session: bool = False) -> list[StatusEvent]: ...
    def by_correlation(self, correlation_id: str) -> list[StatusEvent]: ...
```

The `.error()` helper auto-captures `traceback.format_exception(exc)` when `exc` is passed, so call sites stay one-liners:

```python
try:
    result = provider.analyze_images(...)
except Exception as e:
    reporter.error(
        feature="Analyze → Re-analyze",
        title=f"Failed to analyze {os.path.basename(path)}",
        exc=e,
        file_path=path,
        context={"provider": provider.provider_name, "model": model},
        correlation_id=job.job_id,
    )
```

### 4.2 Source auto-capture

When `source` is not supplied, the reporter walks `inspect.stack()` to capture the caller's `file:line`. This is opt-outable via `StatusEvent(source=None)` — e.g., when the caller already did the capture.

### 4.3 Deduplication

If two events are emitted within 60 s with identical `(feature, title, level, file_path)`, the second increments a `coalesced_count` on the first rather than creating a new row. The DB row gains `coalesced_count INTEGER DEFAULT 1`. Dropdown shows `"Re-analysis failed: provider unreachable (×5)"`.

This prevents log-flood when e.g. 100 files fail the same way.

---

## 5. UI: `StatusHistoryBar`

Replaces the current `self.status_lbl = QLabel(...)` in `AnalyzePanel` and any other panel using the same pattern.

### 5.1 Collapsed state (default)

```
┌───────────────────────────────────────────────────────────────────────┐
│  ⚠  Re-analysis failed: provider unreachable                ⓘ  3 ▾   │
└───────────────────────────────────────────────────────────────────────┘
       ^ level icon     ^ most recent event title       ^ unread error count, click-to-open
```

- **Level icon:** ✅ info (green), ⚠ warn (amber), ⛔ error (red), · debug (gray, only shown if dev mode)
- **Title:** most-recent event. Color-coded to match level.
- **Badge:** count of unacknowledged events at `warn` or `error` level since panel last focused. Clicking the badge opens the dropdown.
- **Chevron:** explicit "open dropdown" affordance.
- Clicking the body anywhere (not just the chevron) opens the dropdown — the whole bar is a button.

### 5.2 Expanded dropdown

```
┌──────────────────────────────────────────────────────────────────────┐
│  [All ▾] [🔍 Search...]                                          [⚙] │
├──────────────────────────────────────────────────────────────────────┤
│ ⛔  14:22  Analyze → Re-analyze   Failed: provider unreachable (×3) │
│ ⚠   14:22  Analyze → Re-analyze   0 of 3 files re-analyzed          │
│ ⛔  14:21  Analyze → Re-analyze   Failed: file not found             │
│ ⚠   14:18  Analyze → Start        No source directories configured   │
│ ✅  14:05  Bundle → Export        Wrote 12 pages to bundle-001.pdf  │
│ ·   14:00  App                     Session started                   │
├──────────────────────────────────────────────────────────────────────┤
│                                        Showing 6 of 42  • [View All] │
└──────────────────────────────────────────────────────────────────────┘
```

- **Severity filter** dropdown (top-left): `All`, `Errors`, `Warnings & errors`, `This feature only`.
- **Search** (top-center): live-filters by title/feature/detail.
- **Settings gear** (top-right): opens Settings → Status History section.
- **Row hover:** shows a compact action row: `[Details]` `[Copy]` `[File issue]` `[★]` `[✕]`.
- **Row click:** opens full `StatusEventDialog`.
- **View All** link: opens a full-window history with pagination + date filter (phase 2).

### 5.3 `StatusEventDialog`

The detail popup. Structured for both users and developers.

```
┌────────────────────────────────────────────────────────────────────┐
│  ⛔  Re-analysis failed: provider unreachable                   ✕ │
├────────────────────────────────────────────────────────────────────┤
│  Feature          Analyze → Re-analyze Files                       │
│  When             2026-04-20 14:22:08 local (18:22:08 UTC)         │
│  File             C:\scans\incoming\page_042.png        [Open 📂] │
│                                                                    │
│  Details                                                           │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ HTTPSConnectionPool(host='api.anthropic.com', port=443):     │ │
│  │ Max retries exceeded with url: /v1/messages (Caused by       │ │
│  │ NewConnectionError('Failed to establish connection'))         │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  Context                                                           │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ provider:     claude_cli                                     │ │
│  │ model:        claude-3-5-sonnet-20241022                     │ │
│  │ job_id:       7f3c…                                          │ │
│  │ processing_time_ms: 30012                                    │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  ▸ Developer Details   ←—  expandable section                     │
│  ▸ Traceback          ←—  expandable section, monospace           │
│                                                                    │
├────────────────────────────────────────────────────────────────────┤
│ [★ Star] [📋 Copy as Markdown] [🔁 Retry] [🐙 File GitHub Issue]  │
└────────────────────────────────────────────────────────────────────┘
```

**Fields explicitly requested by the user:**
- ✓ component invoking the status — shown as **Feature** (user-facing, not a code path)
- ✓ date/time — both local and UTC
- ✓ file generating the status — shown as **File** with "Open containing folder" button
- ✓ more details — the **Details** block is the expanded event detail
- ✓ File GitHub issue button — see §6

**Additional fields worth including:**
- **Context** block — structured JSON rendered as a key-value table (provider, model, job_id, etc.)
- **Developer Details** — source code location (`analysis_worker.py:155`) and session/correlation IDs, behind a collapsible to keep the dialog approachable for non-technical users
- **Traceback** — full Python traceback in a monospace block, also collapsible
- **Retry button** — only shown when the event was produced by a re-runnable action (re-analyze single file, re-run bundle export). Wired via `event.context["retry_action"]`.
- **Copy as Markdown** — emits a formatted block suitable for pasting into Slack / notes

---

## 6. GitHub Issue Filing

Clicking **File GitHub Issue** builds a URL like:

```
https://github.com/aberrantCode/WinScanOllamaVision/issues/new
  ?title=<urlencoded title>
  &labels=<urlencoded labels>
  &body=<urlencoded body>
```

GitHub's "new issue" form pre-populates from these parameters — no API call, no auth required.

### 6.1 Issue template (body)

```markdown
<!-- Auto-generated by WinScanLLM Status History -->

## What I was doing
*(Please describe what you clicked or were trying to accomplish.)*

## What happened
Re-analysis failed: provider unreachable

## Event details
- **Feature:** Analyze → Re-analyze Files
- **When:** 2026-04-20 14:22:08 UTC
- **Severity:** error
- **File:** `page_042.png`
- **Event ID:** `7f3c4a1e-…`
- **Correlation ID:** `job-9b2d…`

## Context
| Key | Value |
|---|---|
| provider | claude_cli |
| model | claude-3-5-sonnet-20241022 |
| processing_time_ms | 30012 |

## Details
```
HTTPSConnectionPool(host='api.anthropic.com', port=443):
Max retries exceeded with url: /v1/messages
```

<details>
<summary>Traceback</summary>

```python
Traceback (most recent call last):
  File "analysis_service.py", line 287, in _analyze_single_page
    ...
```

</details>

## System
- **App version:** 0.3.2
- **OS:** Windows 11 Pro 10.0.26200
- **Python:** 3.12.10
- **Active provider:** claude_cli
- **Source directory count:** 2
- **AutoAnalysis enabled:** True

---
*Filed from WinScanLLM Status History. Edit the "What I was doing" section above, then click **Submit**.*
```

### 6.2 Auto-applied labels

Derived from `event.feature` prefix:

| Feature prefix | Label |
|---|---|
| `Analyze → …` | `area:analyze` |
| `Bundle → …` | `area:bundle` |
| `Export → …` | `area:export` |
| `Import → …` | `area:import` |
| `Settings → …` | `area:settings` |
| *(any)* | `severity:<level>` |
| *(any)* | `auto-filed` |

A maintainer can filter on `auto-filed` to triage these separately from hand-filed issues.

### 6.3 Privacy

- File paths may be sensitive. Before opening the browser, the app shows a preview dialog with:
  - the exact title, labels, and body that will be submitted
  - a checkbox `[✓] Redact file paths to basenames` (default on)
  - a checkbox `[ ] Include traceback` (default on)
  - `[Continue to GitHub]` / `[Cancel]`
- Redaction replaces full paths with `<redacted>/<basename>`.

---

## 7. Emission policy — which backends report what

| Call site | Level | Feature | Title pattern |
|---|---|---|---|
| `scan_all_directories` — disabled | warn | `Analyze → Start Analysis` | `Auto-analysis is disabled in Settings` |
| `scan_all_directories` — no dirs | warn | `Analyze → Start Analysis` | `No source directories configured` |
| `scan_all_directories` — all cached | info | `Analyze → Start Analysis` | `Nothing to analyze — {N} files already up to date` |
| `scan_all_directories` — completed | info | `Analyze → Start Analysis` | `Analyzed {N}, cached {M}, errors {K}` |
| per-file failure in `SCAN_ALL` | error | `Analyze → Start Analysis` | `Failed to analyze {basename}` |
| per-file failure in `ANALYZE_FILES` | error | `Analyze → Re-analyze Files` | `Re-analysis failed: {basename}` |
| `ANALYZE_FILES` summary if `errors > 0` | error | `Analyze → Re-analyze Files` | `{K} of {N} files failed re-analysis` |
| Worker caught exception | error | `Analyze → Worker` | `Job failed: {short}` + full traceback |
| Provider unreachable | error | `Analyze → Provider` | `Provider '{name}' unreachable` |
| Bundle export success | info | `Bundle → Export` | `Wrote {N} pages to {filename}` |
| Bundle export failure | error | `Bundle → Export` | `Bundle export failed: {short}` |
| Settings save | info | `Settings → Save` | `Settings saved` |
| Settings validation fail | warn | `Settings → Save` | `{section} setting invalid: {field}` |

---

## 8. Settings

New section in Settings → **Appearance / Status History**:

| Key | Type | Default | Description |
|---|---|---|---|
| `StatusHistory.enabled` | bool | `true` | Master switch |
| `StatusHistory.display_count` | int | `20` | Rows visible in dropdown |
| `StatusHistory.retention_days` | int | `30` | DB purge threshold (starred events exempt) |
| `StatusHistory.min_level` | enum | `info` | Drop events below this level at emission time |
| `StatusHistory.auto_popup_errors` | bool | `false` | Auto-open StatusEventDialog on any `error` event |
| `StatusHistory.show_developer_details` | bool | `false` | Default-expand the Developer Details section |
| `StatusHistory.dedup_window_seconds` | int | `60` | Time window for title-level deduplication |
| `StatusHistory.redact_paths_in_issues` | bool | `true` | Default state of the redaction checkbox |
| `StatusHistory.github_issue_base_url` | string | `https://github.com/aberrantCode/WinScanOllamaVision/issues/new` | Overridable for forks |

---

## 9. File layout (new / modified)

### New files
- `src/db/status_events_repo.py` — `StatusEventsRepo` (insert, query, purge, star, acknowledge)
- `src/db/schema.py` — `CREATE TABLE status_events` block + indexes
- `src/services/status_event.py` — `StatusEvent` dataclass + `StatusLevel` literal
- `src/services/status_reporter.py` — `StatusReporter` singleton with Qt signal
- `src/services/issue_template.py` — `build_github_issue_url(event, app_version, redact=True)` pure function
- `src/ui/status_history/__init__.py`
- `src/ui/status_history/history_bar.py` — `StatusHistoryBar` widget
- `src/ui/status_history/history_dropdown.py` — popup dropdown
- `src/ui/status_history/event_dialog.py` — `StatusEventDialog`
- `src/ui/status_history/issue_preview_dialog.py` — pre-submit preview

### Modified files
- `src/services/analysis_service.py` — emit events at the three early-return branches; emit per-file error events
- `src/services/analysis_worker.py` — emit error event + call `save_error()` in `ANALYZE_FILES` path; emit summary event
- `src/ui/pipeline/analyze_panel.py` — replace `self.status_lbl` with `StatusHistoryBar`
- `src/ui/settings/settings_tab_appearance.py` — new Status History subsection

### Test files
- `tests/services/test_status_reporter.py` — singleton, dedup, source auto-capture
- `tests/services/test_issue_template.py` — URL building, redaction, label derivation
- `tests/db/test_status_events_repo.py` — insert/query/purge/star
- `tests/ui/status_history/test_history_bar.py` — Qt signal wiring, filter, search
- `tests/ui/status_history/test_event_dialog.py` — renders all sections

---

## 10. Rollout phases

### Phase 0 — Immediate patches (no dependencies)
Ship ahead of the spec to unblock the two bugs:
1. `analysis_worker.py` `ANALYZE_FILES` path — call `save_error()` and capture `error_details: list[dict]` in stats (mirrors `SCAN_ALL`).
2. `analyze_panel.py` `_on_job_finished` / `_on_queue_empty` — honor `stats["message"]` and `stats["error_details"]`; if `errors > 0`, render status as a button that pops a `QMessageBox` with the error list.

Forward-compatible: the same `error_details` list becomes the input to `StatusReporter.error(...)` calls in Phase 2.

### Phase 1 — Foundation
- Schema migration (add `status_events`)
- `StatusEvent`, `StatusReporter`, `StatusEventsRepo`
- `build_github_issue_url` function
- Unit tests for all three

### Phase 2 — Backend emission
Wire every emission point from §7. Keep `analysis_errors` writes in place. Verify all three bug scenarios now produce durable, correct events.

### Phase 3 — UI
- `StatusHistoryBar` + dropdown + `StatusEventDialog` + issue preview
- Replace `status_lbl` in `AnalyzePanel` (and inventory other panels for the same pattern)
- Settings subsection

### Phase 4 — Polish
- Deduplication logic
- Starring / acknowledging
- Retry button for re-runnable events
- Export to JSON (for advanced bug reports)
- "View All" full-window history

---

## 11. Open questions

1. **Should `debug`-level events be persisted at all?** Lean: only if dev mode is on (keeps DB small).
2. **Session boundaries in the dropdown:** show a horizontal rule labeled `— Previous session —` when crossing session_id? Likely yes — strong visual cue.
3. **System info in the issue body** — include? The §6.1 template includes it. Worth a redaction checkbox too (some users on managed hardware won't want OS build disclosed).
4. **`StatusReporter` global vs. per-window** — global singleton is simpler and matches `get_logger()`. Per-window would allow fully independent windows. Lean: **global**, documented as such.
5. **Interaction with `analysis_errors`** — keep both tables forever, or migrate legacy rows into `status_events`? Lean: **keep both**; `status_events` is the canonical surface going forward and the only one the UI reads. `analysis_errors` stays as a lightweight denormalized index for "files currently in error state."

---

## 12. Success criteria

A user hits **Start Analysis** on a fresh install with no directories configured. Within 500 ms:

1. A warning-level event appears in `StatusHistoryBar` with title `No source directories configured` and feature `Analyze → Start Analysis`.
2. The badge shows `1`.
3. Clicking the bar opens the dropdown; clicking the row opens `StatusEventDialog`.
4. The dialog shows: feature, local+UTC timestamp, detail `Open Settings → Directories to add a scan source`, and a `File GitHub Issue` button.
5. Clicking **File GitHub Issue** shows a preview with the exact title `No source directories configured`, labels `area:analyze severity:warn auto-filed`, body including system info, and a `Continue to GitHub` button.
6. Clicking continue opens `github.com/aberrantCode/WinScanOllamaVision/issues/new?...` with all fields pre-filled.

All three original bugs are resolved by the same piece of infrastructure.
