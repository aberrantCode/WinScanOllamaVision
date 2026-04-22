# Status History Backlog

Follow-up work deferred from the initial Status History feature (PR #26,
spec `_project_specs/status_history.md`). Each task is self-contained and
sized to ship as its own PR against `dev`.

Format: one heading per task, followed by an executable checklist covering
scope, design, implementation, tests, and acceptance.

---

## 1. Cross-thread integration test for `StatusReporter`

**Why it matters:** the production crash we already fixed — worker-thread
events silently lost because Python `sqlite3.connect()` defaults to
`check_same_thread=True` — was not caught by the existing unit tests.
Those tests all run on a single thread with a `MagicMock` repo. If
someone removes the `check_same_thread=False` flag or re-introduces a
cross-thread pattern in another repo, we'd regress silently again.

**Target file:** `tests/services/test_status_reporter_threading.py` (new)

### Checklist

- [ ] **Scope (before writing any code)**
  - [ ] Decide on the exact assertion: a write from a background
        `threading.Thread` must produce a row readable from the main
        thread within a bounded time (≤ 500 ms).
  - [ ] Decide whether to exercise `get_reporter()` (the real singleton
        bootstrap that opens the AppData DB) or to construct a reporter
        with a temp-DB repo. Strong lean: **temp-DB repo** — otherwise
        the test pollutes real user state and order-dependency between
        tests creeps in. `get_reporter()` coverage is already provided
        by `test_status_reporter.py`.

- [ ] **Fixtures**
  - [ ] Add a `threaded_reporter` fixture that:
    - [ ] Creates a `tempfile.NamedTemporaryFile(suffix=".db")` path.
    - [ ] Opens a thread-safe `sqlite3.Connection` (`check_same_thread=False`),
          wraps it in a `DatabaseConnection`, runs `create_all_tables`,
          constructs a `StatusEventsRepository`, and passes it to a
          fresh `StatusReporter`.
    - [ ] Yields `(reporter, repo)` so tests can assert against the
          repo directly.
    - [ ] Cleans up the temp file and closes the connection on teardown.

- [ ] **Test cases**
  - [ ] `test_background_thread_write_visible_to_main_thread_read` — spawn
        a `threading.Thread` that calls `reporter.error("Test → X", "boom")`;
        join the thread with a 1-second timeout; assert `repo.recent()`
        contains the event on the main thread.
  - [ ] `test_concurrent_writes_from_multiple_threads_all_persist` — spawn
        8 threads, each emitting 25 unique events (distinct titles so dedup
        doesn't coalesce them); join all; assert `repo.recent(limit=250)`
        returns exactly 200 rows.
  - [ ] `test_concurrent_writes_with_dedup_collapse_correctly` — spawn 8
        threads each emitting the SAME event 25 times; join; assert exactly
        1 row exists with `coalesced_count == 200`. Validates the write lock
        serializes the dedup check-then-update atomically.
  - [ ] `test_reader_during_writer_does_not_raise` — start a writer thread
        that loops `reporter.warn(...)` for 500 ms; from the main thread,
        call `repo.recent()` repeatedly; assert no exceptions and every
        returned list is a well-formed `list[dict]` (no partial rows).

- [ ] **Documentation**
  - [ ] Add a one-paragraph class-level docstring in the new file stating
        *why* cross-thread behavior needs testing (links back to the bug
        we fixed — include PR #26 hash or a short note).

- [ ] **Validation**
  - [ ] Run the new file: `python run_tests.py tests/services/test_status_reporter_threading.py -v --no-cov` — expect all green.
  - [ ] Run the full status-history suite to confirm no regressions:
        `python run_tests.py tests/services/test_status_event.py tests/services/test_issue_template.py tests/services/test_status_reporter.py tests/db/test_status_events_repo.py tests/ui/test_status_history.py --no-cov`
  - [ ] `mypy tests/services/test_status_reporter_threading.py --ignore-missing-imports` clean.
  - [ ] `ruff check tests/services/test_status_reporter_threading.py` clean.

- [ ] **Acceptance**
  - [ ] Temporarily flip the reporter's connection back to
        `check_same_thread=True` (in a local branch only) and confirm
        the new tests fail with `sqlite3.ProgrammingError`. This proves
        the tests actually catch the regression they were written for.
        Revert the flip before opening the PR.

### Estimate
~100 lines of test code + the deliberate-regression verification step.
One commit.

---

## 2. Adopt `StatusHistoryBar` in Import / Bundle / Export panels

**Why it matters:** today `StatusHistoryBar` only lives on the Analyze
panel. Events emitted by other features (bundle export success/failure,
import discovery counts, export PDF write errors) are still recorded in
the DB and visible via the Analyze panel's dropdown — but users don't
think to go to Analyze to see Bundle errors. The bar should appear
anywhere the user is currently focused.

**Target files:**
- `src/ui/pipeline/import_panel.py`
- `src/ui/pipeline/bundle_panel.py`
- `src/ui/pipeline/export_panel.py`
- Add emission call sites in `src/services/bundling_service.py` and any
  import/export services (audit first to enumerate current `print(...)` /
  silent-error call sites and turn them into StatusReporter calls)

### Checklist

- [ ] **Audit phase (read-only)**
  - [ ] Grep each target panel for `QLabel` status-type widgets and record
        their current placement and styling — the bar needs to drop in
        without disturbing surrounding layout.
  - [ ] Grep for `print(`, `logger.error(`, `show_warning(`, and
        `show_information(` in `bundling_service.py`, `file_service.py`,
        and `discovery_service.py`. Each hit is a candidate to convert
        into a `StatusReporter` emission. Record the list in a scratch
        file before touching code.

- [ ] **Panel-side changes**
  - [ ] Import panel
    - [ ] Instantiate `StatusHistoryBar` in the toolbar, replacing any
          plain status `QLabel`.
    - [ ] Connect `open_requested` → open a `HistoryDropdown` (reuse the
          helper pattern from `AnalyzePanel._on_status_bar_clicked`).
    - [ ] Connect `event_activated` → open `StatusEventDialog` with the
          appropriate `retry_enabled` rule (Retry is meaningful if the
          event carries a `file_path` or a re-runnable correlation_id).
    - [ ] Wire `file_issue_requested` → `IssuePreviewDialog`.
  - [ ] Bundle panel — same four connections; Retry should only be
        enabled for bundle-build-failure events whose context carries a
        `bundle_id` we can re-queue.
  - [ ] Export panel — same four connections; Retry triggers a re-export
        of the same `bundle_id`/output path.

- [ ] **Backend emission — Bundle**
  - [ ] `bundling_service.build_bundle` (or equivalent entry point):
        success → `reporter.info("Bundle → Build", f"Built bundle {id} ({N} pages)", correlation_id=bundle_id)`.
  - [ ] Failure paths inside the same service: `reporter.error("Bundle → Build", title, exc=e, correlation_id=bundle_id, context={"page_count": ..., "strategy": ...})`.
  - [ ] PDF conversion failures (`bundle_pdf_converter.py`): emit with feature `Bundle → PDF Conversion`.

- [ ] **Backend emission — Import**
  - [ ] Directory scan kick-off: `reporter.info("Import → Scan", ...)`.
  - [ ] Per-directory failures (permission denied, path not found):
        `reporter.warn("Import → Scan", title, file_path=directory, context={...})`.
  - [ ] Discovery summary: `reporter.info("Import → Scan", f"Discovered {N} new files, {M} ignored")`.

- [ ] **Backend emission — Export**
  - [ ] Success: `reporter.info("Export → PDF", f"Wrote {filename}", file_path=output_path)`.
  - [ ] Failure: `reporter.error("Export → PDF", ..., file_path=output_path, exc=e)`.

- [ ] **Auto-popup wiring**
  - [ ] Mirror `AnalyzePanel._on_status_event_for_auto_popup` in each
        panel so the `StatusHistory.auto_popup_errors` setting is honored
        consistently across the app.
  - [ ] Consider extracting this into a shared mixin
        (`ui/status_history/panel_mixin.py`) to avoid copy-paste drift;
        decide one way, document in the commit message.

- [ ] **Tests**
  - [ ] Smoke tests for each new panel wiring — construct the panel with
        a mocked reporter (use the pattern in
        `tests/ui/test_status_history.py::isolate_reporter`), emit an
        event, assert the panel's bar renders it.
  - [ ] Backend emission tests for each new call site — mock the
        reporter; assert the right feature/title/level/context.

- [ ] **Validation**
  - [ ] Full pytest sweep across `tests/ui/` and `tests/services/` — no
        regressions.
  - [ ] `mypy` + `ruff check` clean on all modified files.
  - [ ] Manual smoke — launch the app, force a bundle-export failure
        (e.g. readonly output directory), confirm the error appears on
        the Bundle panel's bar, not buried on the Analyze panel.

- [ ] **Acceptance**
  - [ ] Every panel in `src/ui/pipeline/` (except `window.py`) has a
        `StatusHistoryBar` in its toolbar.
  - [ ] The `status_lbl: QLabel` field on each panel is either fully
        removed or marked as a hidden backwards-compat shim (matching
        how `AnalyzePanel` already handles it).
  - [ ] At least three `print(...)` / `show_warning(...)` call sites in
        each service layer are replaced with reporter emissions. Record
        the replacements in the commit message.

### Estimate
~600–900 lines across 6 files + tests. Two commits: one for the panel
wiring, one for the backend emission. Target a single PR.

---

## 3. Resolve open questions from `_project_specs/status_history.md` §11

Three explicit TBDs were left in the spec. Each needs a decision,
implementation, and a line edit to remove the TBD marker.

**Target file:** `_project_specs/status_history.md` §11 (delete the
resolved bullet lines after each sub-task ships).

### 3a. Session markers in the history dropdown

- [ ] **Decision**
  - [ ] Confirm or overrule the spec's lean: render a horizontal rule
        labeled `— Previous session —` whenever the row below crosses a
        different `session_id` than the row above.

- [ ] **Implementation** (`src/ui/status_history/history_dropdown.py`)
  - [ ] Extend `_reload()` to iterate events in display order and inject
        a non-selectable `QListWidgetItem` (flags cleared of
        `Qt.ItemFlag.ItemIsSelectable | ItemIsEnabled`) whose text is
        `— Previous session —` at each session boundary.
  - [ ] Style the marker via `setForeground()` + italic font; ensure it
        doesn't register in the dropdown's "of N events" count.

- [ ] **Tests**
  - [ ] Add `test_history_dropdown_renders_session_marker` — seed the
        mocked `reporter.recent()` with events from two sessions, open
        the dropdown, assert a non-selectable row with the marker text
        sits between them.
  - [ ] Add `test_history_dropdown_no_marker_when_single_session` — all
        events share one session; no marker row should exist.

- [ ] **Acceptance**
  - [ ] Delete the bullet from `_project_specs/status_history.md` §11.
  - [ ] Record the choice in the feature spec so a future reader
        understands why the marker exists.

### 3b. Canonical app-version source

- [ ] **Decision**
  - [ ] Identify the authoritative version string. Candidates in order
        of preference:
        1. `pyproject.toml` `[project].version`
        2. A dedicated `src/__version__.py` module
        3. Git tag (`setuptools_scm` style)
    - [ ] Read `pyproject.toml` to see what's already there; only create
          `__version__.py` if no version string is declared.

- [ ] **Implementation**
  - [ ] Add `src/version.py` exposing `APP_VERSION: str` that reads the
        chosen source at import time (prefer importing from
        `importlib.metadata` if packaging metadata is installed; fall
        back to parsing `pyproject.toml` directly).
  - [ ] Replace the literal `"0.3.2-dev"` fallback in
        `src/ui/pipeline/analyze_panel.py::_on_file_issue` with
        `from services.version import APP_VERSION`.
  - [ ] Replace `APP_VERSION_FALLBACK = "0.0.0-dev"` in
        `src/ui/status_history/issue_preview_dialog.py` with the same
        canonical import (keep the fallback constant name for test
        compatibility, but default it to the imported value).

- [ ] **Tests**
  - [ ] Add `tests/test_version.py` — asserts `APP_VERSION` matches the
        pyproject value exactly (read and parse pyproject.toml in the
        test to verify).
  - [ ] Existing `test_issue_template.py` tests keep passing because
        they inject `app_version` explicitly.

- [ ] **Acceptance**
  - [ ] Delete the bullet from §11.
  - [ ] One call site for the version; next version bump updates
        `pyproject.toml` only.

### 3c. Debug-level event persistence

- [ ] **Decision**
  - [ ] Spec §11 lean: "only persist `debug` events when dev mode is
        on." Confirm or overrule. Strong lean: **persist if a new
        `StatusHistory.persist_debug` setting is enabled** (default
        `false`) — gives developers the switch without coupling to a
        separate dev-mode flag that doesn't exist yet.

- [ ] **Implementation**
  - [ ] Add `StatusHistory.persist_debug` to `settings_tab_appearance.py`
        — a checkbox below `auto_popup_errors`.
  - [ ] Persist in `settings_window_enhanced.py` alongside the other
        StatusHistory settings.
  - [ ] Modify `StatusReporter._record` so that when
        `event.level == "debug"` and the setting is `false`, the event
        is dropped before any repo write (signal still fires so live UI
        sees it transiently if connected — but nothing lands in the DB).
  - [ ] Read the setting in `get_reporter()` alongside `min_level` /
        `retention_days` and pass it to the `StatusReporter` constructor
        as a new kwarg (`persist_debug: bool = False`).

- [ ] **Tests**
  - [ ] `test_debug_event_dropped_from_db_when_persist_debug_false` —
        emit a `debug` event; assert `repo.insert` was not called.
  - [ ] `test_debug_event_persisted_when_persist_debug_true` — same
        event with the setting flipped; assert the row exists.

- [ ] **Acceptance**
  - [ ] Delete the bullet from §11.

### Estimate (combined for 3a + 3b + 3c)
~300 lines across 6 files + tests. Could ship as one PR with three
commits, or as three tiny PRs — author's choice. The overall PR stays
under the 400-line warning threshold.

---

## General acceptance criteria (apply to every task above)

- [ ] Branch name follows `type/short-description` (`test/reporter-threading`, `feat/status-history-panel-wiring`, `feat/status-history-spec-closeouts`, etc.).
- [ ] PR title follows the conventional-commits format from CLAUDE.md (`test: …`, `feat: …`, `fix: …`) with an uppercase first word in the subject.
- [ ] PR body includes the Summary + Test Plan structure from `git-workflow.md`.
- [ ] Pre-commit hooks pass on the first try (watch for `ruff-format`
      re-formatting staged files — re-stage and retry once if so).
- [ ] Tests: 100% of new code under test, plus at least one regression
      test per bug-derived task.
- [ ] `mypy` + `ruff check` clean on all modified files.
- [ ] PR size under the 800-line hard limit where possible; if over,
      justify in the PR body and split into reviewable commits.

---

## Cross-cutting nice-to-haves (do only if pulling a thread touches them)

- [ ] Remove `status_lbl: QLabel | None` shim from `AnalyzePanel` once no
      other panel's initialization still expects it to exist.
- [ ] Consider auto-running `reporter.purge_expired(retention_days)` on
      a 24h timer in addition to the existing startup purge, so very
      long-running sessions don't accumulate stale events.
- [ ] Add a `View All` button in `HistoryDropdown` opening a full
      `QMainWindow`-sized history browser with pagination — the spec
      mentioned it as a Phase-2 stretch item; probably not worth it
      until someone asks.
