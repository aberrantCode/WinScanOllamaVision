# Task: Unblock queued fix, then fix analysis-pipeline reliability/diagnostics + several UX gaps

You are an unattended session. Treat "State already established" as ground truth — it was verified
this session by reading code and, in several cases, running commands against the live app/DB/Ollama
server. Do not re-derive it. You have no prior conversation history.

## 0. Orientation

- Follow `C:\development\scan_organization\CLAUDE.md` exactly (test runner, file placement, package
  imports, pre-commit, PR title format, PR size limits — warn at 400 lines changed, hard limit 800).
  Defer to it; do not restate its rules.
- **Your worktree and branch already exist. Work in them. Do NOT create another worktree.**
  - Worktree: `C:\development\scan_organization\.worktrees\fix-ollama-model-name`
  - Branch: `fix/ollama-model-list-keyerror` (branched from `origin/dev @ 89ac70e`, which already
    contains the `qwen2.5-vl` → `qwen2.5vl:latest` model-name fix, PR #62)
  - This branch already has one real commit on it (`f3a6213`): a fix for `OllamaProvider.get_available_models()`
    and `OllamaService.pull_model()`'s post-pull verification, both of which indexed `model["name"]`
    when the real `ollama` Python SDK keys the tag as `model["model"]` — every model showed as
    "missing" regardless of whether it was actually installed. Verified directly against the live
    Ollama server this session (`get_available_models()` went from returning `[]` to returning all
    10 installed tags including `qwen2.5vl:latest`). Tests pass (1063 passed via the exact pre-push
    gate). **Do not redo this work** — it is done and correct, just not pushed yet (see Task 1).
- PyQt6 desktop app (WinScanLLM). Active provider = Ollama at `http://localhost:11434`, model
  `qwen2.5vl:latest` (already installed on this machine, confirmed via `ollama.Client().list()`).

## 1. Hard constraints

1. **Never trigger a real multi-GB model pull in tests.** Mock `OllamaService.pull_model` /
   `ollama.Client`. Do not run `ollama pull` yourself.
2. **Never push directly to `main`/`dev`; never delete `main`/`dev`.** Land everything through PRs.
3. **A local pre-push hook runs an automated code review that blocks the push on any *Critical*
   finding, regardless of whether that finding is in your diff or pre-existing.** This is not a bug
   in the hook you should route around — if it flags a real Critical bug, fix it before pushing
   (see Task 2 for one already found this session). If it flags something you believe is a false
   positive, do not bypass with `--no-verify`; stop and report it instead.
4. **This repo's CI is pre-existing red on every branch** (Linux: `winrt-runtime` wheel build
   fails; Windows: `tests/test_workflow.py` collection fails with `LoggingService not initialized`).
   Both unrelated to any work here. Every PR from this session will show `mergeStateStatus:
   BLOCKED` because of this — that is expected. Merge via
   `gh pr merge <branch> --merge --admin --delete-branch` (repo owner is admin). Do not treat the
   red CI itself as something to fix.
5. **PR size.** The full task list below is large. Split it into multiple PRs along the boundaries
   given in "Tasks, in order" — do not land it as one 1500-line PR. Each PR must leave the app in a
   working, better-than-before state; don't let a later task's PR depend on an earlier one still
   being open on GitHub (open the next PR's branch off `dev` only after the prior one is merged and
   you've synced local `dev`).
6. If a task seems to require a forbidden/irreversible action you can't resolve from this prompt,
   **stop and report it** in your final numbered list — no human is watching mid-run.

## 2. State already established (verified this session — do not re-verify, do not redo)

**Reported symptoms (from the user, with screenshots), in their own words:**
- App starts on Import, auto-switches to Analyze, shows a status-panel error: model missing.
- Settings → LLM Provider tab shows the model as already downloaded (checkmark).
- User forced a re-analysis of one file; UI showed it start; progress bar sat at "100% — Analyzing
  Scan_X.png" for **several minutes**, then flipped to an Error status with no further detail.
- The file's row still showed "Error" in the grid, but the file-details dialog's LLM Prompt / LLM
  Response sections were empty, and the Analysis Information section had no provider, model, or
  processing time.
- The Analytics panel above the grid still showed 0 errors even after this failure.
- On startup, the initial folder-scan (discovery) runs with no visible "scanning" indicator, and if
  it finds nothing it silently flips to the Analyze tab.

**Root cause of the "model missing" symptom:** exactly the bug already fixed by commit `f3a6213`
on this branch (the `["name"]` vs `["model"]` SDK key mismatch) — not yet pushed. Task 1 ships it.

**Root cause of the empty-diagnostics symptoms (verified by reading the code, not guessed) — this
is the single highest-value fix in this prompt, do it early (Task 3):**
- `AnalysisService.re_analyze_file()` (`src/services/analysis_service.py:501-550`) and
  `AnalysisService.analyze_specific_files()` (`:441-482`) **never persist an error to the database
  at all** on failure — unlike the bulk `scan_all_directories()` path, which does call
  `self.analysis_db.save_error(...)` (`:233-238`), but only with `file_path`, `error_message`,
  `error_type` — dropping `provider`, `model`, `processing_time_ms`, `prompt`, and the raw response
  even though they're available on the `result` dict at that call site (built at `:362-377` and
  `:410-431`).
- The re-analysis the user ran goes through `re_analyze_file()` — so **nothing was written to the
  DB for that failure at all.** The "Error" status the user saw in the grid was a live, in-memory UI
  update from the worker's `file_status_changed` signal, not something a fresh DB query would find —
  which is also why the Analytics panel (a DB query) still showed 0 errors.
- The `analysis_errors` table (`src/db/schema.py:357-364`) that `save_error()` writes to only has
  columns `file_path, error_message, error_type, error_at` — it structurally cannot hold provider,
  model, prompt, or response even if you did call it consistently.
- **The fix already exists in the schema, unused:** `analysis_results` (`src/db/schema.py:177-201`)
  already has a `had_error BOOLEAN DEFAULT 0` column plus an index on it (`:479-480`), and
  `AnalysisRepository.save()` (`src/db/repositories/analysis_repo.py:45-117`) already accepts
  `had_error: bool = False` as a real parameter and writes it. `AnalysisRepository.count_by_status()`
  (`:241-262`) already computes `{"total", "successful", "errors"}` straight from this column.
  **Verified via grep: `count_by_status()` has zero callers anywhere in `src/`.** This is a
  fully-built, entirely unused error-tracking path — the write side (error branches) just never
  calls it, only the poorer `analysis_errors.save_error()`.
- One real obstacle when wiring this up: the grid's data source,
  `ImageFilesRepository.get_all_with_analysis()` (`src/db/repositories/image_files_repo.py:393-477`),
  reaches `analysis_results` by `LEFT JOIN metadata m ON img.id = m.image_file_id` then
  `LEFT JOIN analysis_results ar ON m.analysis_result_id = ar.id` (`:459-460`) — i.e. it goes
  *through* the `metadata` table, and `metadata` rows are currently only created on the success path
  (`AnalysisDB.save_analysis()`, `src/db/analysis_db.py:62-107`, calls
  `self._metadata.create_from_analysis(...)` after saving). An `analysis_results` row with
  `had_error=1` and no matching `metadata` row **will not surface through this query.** You'll need
  to either also create a (mostly-empty) `metadata` row for the failed attempt pointing at the new
  `analysis_result_id`, or change the query to join `analysis_results` directly off `image_file_id`
  as a fallback when no `metadata` row exists. Verify `MetadataNormalizer().normalize()` and
  `MetadataRepository.create_from_analysis()` tolerate a mostly-empty/error input before assuming
  the first approach works cleanly.
- Also note: `analysis_results.response_text` is `NOT NULL` (`schema.py:190`) — on a real
  connection/timeout failure there is no response text, so the new error-save path must pass
  something non-null (e.g. the error message itself, or an empty string) for that column.
- `analyze_panel.py`'s `_transform_data_for_grid()` (`src/ui/pipeline/analyze_panel.py:426-499`)
  hardcodes `error_message` to `""` at line 489 — **never sourced from anywhere**, independent of
  the DB-write gap above. Fix this too once the DB actually has the data to source it from.
- The provider layer is already contract-clean and does NOT need fixing: `OllamaProvider.analyze_images()`
  (`src/llm_providers/ollama_provider.py:44-131`) already returns `processing_time_ms`, `model_used`,
  `provider_name` on all three error branches (`ConnectionError`/`TimeoutError`/generic `Exception`,
  lines 96-131) — matching the documented provider contract in `CLAUDE.md`. The gap is entirely on
  the `AnalysisService`/DB side, not the provider side. Note the documented contract has no `prompt`
  key at all — `AnalysisService._analyze_single_page` holds the prompt text locally and must thread
  it into whatever you build for the error-save call itself.

**Root cause hypothesis for "couldn't communicate with Ollama" despite the model being installed and
Ollama being reachable (grounded, not yet confirmed live — confirm before fixing, Task 4):**
- `OllamaService.__init__` (`src/llm_providers/ollama_service.py:10,22`) builds ONE
  `httpx.Timeout(timeout)` (default 300s) shared across connect/read/write/pool, and this same
  client is used for both `pull_model()` (long-running by design) and `chat_with_vision_model()`
  (the per-image analysis call). A genuinely-unreachable host and a genuinely-slow first
  vision-model load/generate (plausible for an ~8B model on modest hardware) currently look
  identical: both wait the full configured timeout (300s = "many minutes", matching what the user
  saw) before failing.
- `chat_with_vision_model`'s exception handling wraps failures as a bare
  `ConnectionError(f"Failed to communicate with Ollama: {e}")` with no `base_url`, model name, or
  elapsed time attached — so neither the Status Event toast nor (once Task 3 lands) the persisted
  error record can tell the user *what* address/model it tried or *how long* it waited before
  giving up.
- This is a hypothesis grounded in reading the code, not a confirmed live repro. Ollama itself was
  confirmed reachable and the model confirmed installed via a direct Python check this session
  (`ollama.Client(host="http://localhost:11434").list()` returned 10 models including
  `qwen2.5vl:latest`) — so the failure is very unlikely to be "Ollama is actually down." Reproduce
  the real failure live (re-run analysis against this same running Ollama instance) before assuming
  the timeout-conflation theory is the whole story.

**Settings tab button pattern (for Tasks 6 and 7):**
`src/ui/settings/settings_tab_provider.py:108-123` — `model_buttons = QHBoxLayout()` (line 108)
holds Refresh (`:109-115`) and Download (`:117-121`), both plain `QPushButton(text)` with
`.setObjectName("compactButton")` and `.setToolTip(...)`, added via `model_buttons.addWidget(...)`
and placed into the grid layout at `layout.addLayout(model_buttons, 0, 2)` (`:123`). No icons used
anywhere in this file today — check `src/resources.py` and existing app icon assets for a
consistent set before inventing new ones for Task 7.

**Analyze-tab UI locations (for Tasks 5, 8):**
- Grid widget: `src/ui/pipeline/analyze_panel.py:213-217` (`FileDetailsGrid`), toolbar to add a
  button to: `:125-193` (`toolbar = QHBoxLayout()` ... `root.addLayout(toolbar)` at `:195`).
  Fully-wired reload method already exists: `refresh()` at `:412-424` (re-queries DB, transforms,
  calls `file_grid.refresh_data()`, then `_refresh_analytics_section()`) — already called on init
  and via a 500ms debounce timer on `file_status_changed`. A new refresh button is just
  `toolbar.addWidget(btn)` + `btn.clicked.connect(self.refresh)`.
- Progress bar: created `:198-204` (`setRange(0, 100)`). Worker emits `progress = pyqtSignal(str,
  int, int)` (`src/services/analysis_worker.py:29`, emitted `:133`). The `current`/`total` values
  originate in `AnalysisService.scan_all_directories()` (`src/services/analysis_service.py:201-215`):
  `current = idx + 1` is computed and the callback fires **before** `_analyze_single_page` runs for
  that file (`:218`) — so on the last file, the bar legitimately reads 100% while that file is
  still in flight, for as long as the request takes (which, per Task 4, can be minutes). UI slot:
  `_on_progress` at `:581-591`, `QueuedConnection` at `:504`.
- Analytics panel refresh: `_refresh_analytics_section()` at `:341-410`, called from `refresh()`
  (`:424`) and from `_on_job_finished` (`:674`) — but NOT called directly from the per-file
  `_on_file_status_changed` handler (`:593-596`, which only restarts the debounce timer). Once
  Task 3 makes errors actually reach the DB, verify whether the existing debounced `refresh()` path
  is sufficient or whether `_on_file_status_changed` should call `_refresh_analytics_section()`
  directly for snappier feedback.

**Import-view startup scan (for Task 9):**
- Startup scan kicked off from `src/main.py:18-65` (`_start_discovery_if_enabled`), deferred via
  `QTimer.singleShot(500, start_discovery)` (`:65`), running a `DiscoveryWorker`
  (`src/services/discovery_worker.py:24`, a `QThread` with `progress`/`finished`/`error` signals).
  **This worker's `progress` signal is never connected to anything**, and it's a separate instance
  from the one the Import panel's own manual "Discover Images" button uses. The panel *does* have
  working scan-progress UI for its own button flow: `scan_progress_bar`
  (`src/ui/pipeline/import_panel.py:178-182`), driven by `_on_scan_progress`/`_on_scan_finished`
  (`:636-651`), wired at `:631-633` for the manual path only. Auto-advance-when-empty logic:
  `maybe_show_analyze_nudge_after_discovery()` (`:405-458`), reachable both from the panel's own
  scan completion (`:651`) and from the startup worker's completion (`main.py:51`).

## 3. Tasks, in dependency order — split into separate PRs as marked

### PR 1 — Unblock and ship the already-committed fix (small, do first)

1. **Fix 2 pre-existing Critical bugs found by the push-review hook**, both in
   `src/llm_providers/ollama_service.py`: `extract_document_info()` (around lines 282-291) and
   `infer_page_order_from_content()` (around lines 400-410) each build a prompt with an f-string
   containing a literal, unescaped `{"company": ..., ...}`-style JSON block — Python's f-string
   parser treats the `{`/`}` as a replacement field and raises `ValueError` before the method's own
   `try` block is reached. Reproduced directly by the review tool. **Verified this session: neither
   method has any caller anywhere else in `src/`** (dead code today), so this isn't the cause of the
   user's reported failure — but it's a real crash-on-first-use bug and it's what's blocking the
   push. Fix: double the literal braces (`{{`/`}}`) or stop using an f-string for the static JSON
   template and `.format()`/concatenate only the two dynamic values in. Add a unit test for each
   (call the method with a minimal valid input, assert it doesn't raise) — this is why they shipped
   unnoticed. Commit as an atomic `fix:` commit on the existing branch (same branch as the SDK-key
   fix already there — no need to split into a separate PR for this one, it's what's unblocking the
   push).
2. Run the exact pre-push gate:
   `python run_tests.py tests/services tests/db tests/config tests/llm_providers --no-cov -x`
   (prefix `PATH` with `/c/development/scan_organization/venv/Scripts` — the worktree has no venv
   of its own). Push, open the PR into `dev`, admin-merge past the known-red CI (constraint #4).
3. In the **main checkout** (`C:\development\scan_organization`), `git checkout dev && git pull`.
4. Correct the user's live config if needed: `%APPDATA%/WinScanLLM/settings.ini` → `[Ollama]
   model` should read `qwen2.5vl:latest` (surgical edit of that one key only if it's somehow
   reverted — it was already correct as of this session's end).

### PR 2 — Error persistence + diagnostics (the load-bearing fix; do this before touching UI)

5. Wire error paths to the already-built `had_error` machinery described in State §2: add an
   `AnalysisDB` method (e.g. `save_failed_analysis(...)`, mirroring `save_analysis()` at
   `src/db/analysis_db.py:62-107`) that calls `AnalysisRepository.save(..., had_error=True,
   response_text=<error text or "">, prompt_text=<the prompt that was sent>, provider_name=...,
   model_name=..., processing_time_ms=...)`, and creates the accompanying `metadata` row (or fixes
   the grid query's join) so the failed attempt actually surfaces through
   `ImageFilesRepository.get_all_with_analysis()`. Call this from all three places that currently
   don't persist correctly: `scan_all_directories()`'s existing but field-dropping `save_error()`
   call (`analysis_service.py:233-238`), and the two paths that don't persist at all,
   `re_analyze_file()` (`:501-550`) and `analyze_specific_files()` (`:441-482`). Thread the actual
   prompt text through (currently held locally, never passed to the error path — see State §2).
6. Fix `_transform_data_for_grid()`'s hardcoded `error_message: ""` (`analyze_panel.py:489`) to
   read the now-real value.
7. Verify end to end: force a re-analysis of a file against a *deliberately* unreachable Ollama
   (e.g. wrong port) or a mocked failure, confirm the file-details dialog now shows the prompt, the
   error response/message, provider, model, and processing time; confirm the Analytics panel's
   error count updates without requiring a full app restart.
8. Add/update tests in `tests/services/test_analysis_service.py` and `tests/db/` for the new
   error-persistence path (mock the provider failure, assert the DB row and its fields).

### PR 3 — Fail-fast connectivity + honest progress (do after PR 2, same subsystem)

9. **Reproduce the "couldn't communicate with Ollama" failure live first** (constraint: don't just
   apply the hypothesis in State §2 blind — confirm it). Then split the timeout: a short
   connect-timeout (e.g. 5-10s) distinct from the long timeout used for actual generation/pull, so
   a genuinely-unreachable host fails in seconds (user's ask #3), while a slow-but-working
   generation still gets the full budget. `httpx.Timeout(timeout, connect=<short>)` at the client
   construction in `ollama_service.py:22` is the fix point — verify whether `chat_with_vision_model`
   needs its own client/timeout distinct from `pull_model`'s.
10. Enrich the error path so the exception/message includes the target `base_url`, model name, and
    elapsed time (user's ask #7's second half) — this flows into both the Status Event toast and,
    now that PR 2 landed, the persisted error record shown in the file-details dialog.
11. Fix the progress bar (user's ask #2): the "100%" during an in-flight file is a real but
    misleading value (State §2 explains why). Recommend switching to indeterminate/busy mode
    (`progress_bar.setRange(0, 0)`) while a single file's HTTP call is in flight, since there's no
    real sub-file progress available from a blocking request — but this is a UX call, not a
    correctness one; pick whichever avoids a "stuck-looking" bar during a legitimately multi-minute
    wait and say which you chose and why in the PR description.

### PR 4 — Independent UI additions (small, can go in one PR)

12. Refresh button for the Analyze grid (user's ask #1): add to the existing toolbar
    (`analyze_panel.py:125-193`), wire to the already-fully-built `self.refresh()` (`:412-424`).
    Trivial — no new logic needed.
13. Import-view scan-in-progress lock (user's ask #6): the startup `DiscoveryWorker`
    (`main.py:18-65`) has no UI feedback at all today (State §2). Either route it through the
    Import panel's existing scan-progress machinery (`import_panel.py:178-182, 614-651`) by
    connecting its `progress`/`finished`/`error` signals the same way the manual button flow does,
    or add an equivalent visible "scanning…" state. Must visually disable/lock the Import view's
    interactive elements while the startup scan runs, per the user's explicit ask.

### PR 5 — Settings LLM tab additions (do last — task 15 depends on task 14 existing)

14. Add a "Validate" button (user's ask #8) to `settings_tab_provider.py`'s `model_buttons` layout
    (`:108-123`), same construction pattern as Refresh/Download. On click, test the
    *currently-entered* (not necessarily saved) base URL + model combination — reuse the
    short-connect-timeout probe from PR 3 if applicable — and show success/failure inline (a status
    label next to the buttons, or similar; must not require Save first, since the point is
    validating before committing).
15. Convert Refresh, Download, and the new Validate buttons to icon-only with the label moved into
    the tooltip (user's ask #9) — `.setToolTip(...)` already exists on Refresh/Download, so this is
    mostly replacing `QPushButton("text")` with an icon-bearing constructor while keeping the
    existing tooltips (and adding one for Validate). Check `src/resources.py` and existing app
    icon assets first for a consistent icon set before adding new image files (file placement:
    `/assets` per `CLAUDE.md`).

## 4. Delegation (required)

Use `model: "haiku"` subagents, dispatched in parallel in one message where independent, for
mechanical work: writing the two f-string regression tests (Task 1), locating/confirming existing
icon assets before Task 15, drafting the DB migration/test scaffolding for Task 5's new
`AnalysisDB` method once its shape is decided, and any repo-wide grep sweeps needed along the way.
**Keep in the main session:** the schema/join design decision in Task 5 (verify `MetadataNormalizer`
tolerance before committing to the approach), the live-repro-before-fix step in Task 9, the
progress-bar UX call in Task 11, and PR sequencing/splitting judgment.

**Delegation logging** with
`pwsh -File C:\Users\erik.OPBTA\.claude\skills\continue-new-session-prompt\scripts\log-delegation-outcome.ps1`:
log every escalation/redo/drop (`-Category`, `-FailureMode`, one-line `-Evidence`) even if
recovered in seconds. **Required final step before reporting finished:** log totals, one row per
category, `-Outcome ok -Dispatches N`, each tagged
`-PromptPath 'C:\development\scan_organization\docs\PROMPTS\2026-07-30-ollama-reliability-and-analysis-ux.md'`.
If nothing was delegated, record that explicitly — this tally is required, not optional.

## 5. Reporting

Terse; lead with the action/answer; end every turn with a single numbered list of items needing a
decision — nothing that matters lives outside it. Verify counts with a tool before stating them;
correct any earlier wrong claim in one line. On finish, state: which PRs merged (numbers, SHAs),
test results per PR, whether each of the user's 9 asks is confirmed fixed (not just "code changed"
— re-launch the app and check where feasible), and any item deferred with a clear reason.

---

**Model note:** pinned to Sonnet — this involves live debugging, a real (if small) schema-adjacent
design decision, and PyQt6 threading/signal work, not purely mechanical changes. Delegate the
mechanical pieces named above to `haiku`; escalate to Opus via `/model` only if the metadata-join
design in Task 5 turns out gnarlier than the schema inspection here suggests.
