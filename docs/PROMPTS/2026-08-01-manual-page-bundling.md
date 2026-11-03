# Task: Manual page bundling from the Analyze list view

You are a fresh, unattended Claude Code session. Everything below was verified by
the previous session by reading the code directly — trust it, but line numbers may
drift a few lines, so grep for the named methods/symbols rather than trusting the
number. Do not re-derive the architecture from scratch; the expensive discovery is
already done and captured here.

## Your workspace already exists — use it, don't create another

- **Worktree:** `C:\development\scan_organization\.worktrees\manual-page-bundling`
- **Branch:** `feat/manual-page-bundling` (already checked out there, branched off `origin/dev`)
- Work **in that worktree**. Do not create a new worktree or branch. All commits land on
  `feat/manual-page-bundling`; this ships as **one PR into `dev`**.
- The repo's `venv/` is gitignored and lives only in the **main** checkout. Run all Python
  tooling with that interpreter, from inside the worktree:
  - Tests: `C:\development\scan_organization\venv\Scripts\python.exe run_tests.py tests/... -v`
  - Types: `C:\development\scan_organization\venv\Scripts\mypy.exe src\...\file.py --ignore-missing-imports`
  - (The worktree's `run_tests.py` sets `sys.path` to the worktree's `src/`; the main venv only
    supplies third-party packages, so this is correct.)

## Orientation

Read and follow `C:\development\scan_organization\CLAUDE.md` exactly — it is authoritative for
this repo (test runner, file placement, the mandatory UI-change "find ALL locations" checklist,
PR title format, pre-commit gates). Do not restate or override its conventions. Also honor the
user's global output discipline: terse, and end **every** turn with a single numbered list of
items needing a decision (verify any count before stating it; correct your own earlier claims in
one line).

## Model

This task needs frontier reasoning — the bundle-view display path, the cross-widget signal
wiring, and the merge logic are subtle. If you are not on Opus, switch with `/model opus` before
designing. Delegate only the mechanical lookups to `haiku` subagents (see Delegation).

## HARD CONSTRAINTS (read first — you run with permissions skipped)

1. **Never touch `main` or `dev`.** No direct commits, no pushes, no merges to them except the
   final PR merge into `dev` at the very end.
2. **Do not delete this prompt file.** Retirement is gated on a human review you cannot perform.
3. **Do not modify the AppData databases** (`%APPDATA%/WinScanLLM/*.db`). All DB work is against
   the code + tests with mocked/temporary DBs. Never run the GUI against real data to "test".
4. **Do not run real LLM/Ollama calls.** This feature exists precisely because Ollama is down;
   the whole point is manual bundling with **no analysis required**.
5. If a task appears to require any of the above, **stop and report** rather than improvising.

## State already established (verified — do NOT redo this discovery)

### The user's request (the spec)
In the Analyze tab's list view, when **more than one** page/row is selected, the right-click
context menu must offer a **"Bundle"** action. On invoke:
- The selected pages are marked as belonging to the **same bundle** (visually indicated in the list).
- **If none** of the selected pages are already in a bundle → create a new bundle containing all of them.
- **If exactly one** distinct existing bundle is present among the selection → add the other selected
  pages to **that** bundle.
- **If two or more** distinct existing bundles are present among the selection → **abort** with a
  clear message (future work will ask which bundle wins; not now).
- On success → switch the pipeline UI to the **Bundle** view with **that bundle selected**.

### Decision already made by the user
A manually-created bundle enters as a **`'suggested'`** bundle (reviewable), opened **selected** in
the Bundle view where the user can Accept/Reject/edit it. (Not auto-accepted.)

### THE CRITICAL GOTCHA (this is where an hour gets wasted — read carefully)
The Bundle view does **not** simply display persisted `document_bundles`. It loads via
`bundle_panel.refresh_bundle_count()` → `BundlingService.generate_bundle_recommendations()`
(`src/services/bundling_service.py`), which:
- **requires analyzed pages** (`analysis_db.get_analyzed_pages()`) — there are **none** when Ollama
  is down (the user's exact situation), so it returns `[]`;
- **excludes** files already in accepted/completed bundles;
- **regenerates and persists brand-new `'suggested'` bundles** each call.

Therefore it will **NOT** surface a manually-created bundle. **You must add a new display path**:
`bundle_panel` must be able to load **one specific persisted bundle by id** (from
`AnalysisDB.get_bundle_suggestions()` / a new "get bundle by id" read) and feed it to
`BundleReviewWidget`, bypassing `generate_bundle_recommendations()`. Confirm the **dict shape**
`BundleReviewWidget` expects (see below) and make the persisted-bundle dict match it — this shape
match is the single most likely bug.

### Key code locations & APIs (grep the symbol; line #s approximate)

**Context menu (where the "Bundle" action goes):**
- `src/ui/file_details/file_details_grid_actions.py` → `_GridActionsMixin._show_context_menu(pos)` (~L209).
  Mixed into `FileDetailsGrid`. Selection: `self.table_view.selectionModel().selectedRows()`.
  Row dict: `src = self.proxy_model.mapToSource(index); row = self.model.get_row_data(src.row())`.
  **The file path is `row["full_path"]`.** The **multi-selection** branch is the `else` at ~L289 —
  add "Bundle" only when `len(selection) > 1`. There's already a `_change_status_for_selected(...)`
  helper in this mixin you can reuse to set page status.

**Page "in a bundle" visual indicator:**
- `ImageStatus.BUNDLED` exists (`from db.image_status import ImageStatus`; used in analyze_panel).
  Set selected pages to `ImageStatus.BUNDLED` so the list reflects membership.

**Bundle DB model:**
- Table `document_bundles`, `status` ∈ {`suggested`,`accepted`,`rejected`,`completed`}. Junction via
  `BundleImagesRepository`.
- `AnalysisDB.save_bundle_suggestion(file_paths: list[str], bundle_metadata: dict, confidence_score: float) -> int|None`
  — creates a bundle (**status hardcoded `'suggested'`** in `BundleRepository.save_suggestion`) and
  adds images through the junction using `self._image_files.get_by_path(path)["id"]`.
- `BundleImagesRepository.get_bundles_for_image(image_file_id) -> list[dict]` — **use this to detect
  existing membership** per selected page.
- `BundleImagesRepository.add_image(bundle_id, image_file_id, sequence_order)` and
  `add_images_bulk(bundle_id, image_file_ids)`.
- Path→id: `AnalysisDB._image_files.get_by_path(path) -> {"id": ...}`. Prefer adding a small **public**
  `AnalysisDB` helper (e.g. `get_image_id(path)`) rather than reaching into the private repo from UI.
- You will likely need a new read "get one bundle (+its images) by id" shaped like what the review
  widget consumes — check `AnalysisDB.get_bundle_suggestions()` and `BundleRepository.get_suggestions`.

**Bundle review widget (the "selected bundle" target):**
- `src/ui/bundle/bundle_review_widget.py` → `BundleReviewWidget(bundles=[...])`. It holds an in-memory
  `self.bundles` list and navigates by `self.current_bundle_index`. **There is no select-by-id method** —
  "select that bundle" means the list must include the manual bundle and `current_bundle_index` point
  at it. It **raises** `ValueError` if given an empty list.
- `src/ui/pipeline/bundle_panel.py` → `refresh_bundle_count()` (~L263) builds/starts the embedded
  `BundleReviewWidget`. **It early-returns if `self._embedded_workflow` already exists** (won't rebuild)
  — you must handle forcing a rebuild/refresh so a newly-created bundle actually appears and is selected.
  Add e.g. `select_bundle(bundle_id: int)` here.

**View switching (Analyze → Bundle):**
- `src/ui/pipeline/window.py` → `_go_to_stage(stage)` (~L268; `self.stack.setCurrentIndex(stage)` +
  stage-specific refresh; `STAGE_BUNDLE` refreshes the bundle panel ~L289). Constants from
  `ui.pipeline.stages` (`STAGE_ANALYZE`, `STAGE_BUNDLE`, …).
- **Pattern to copy:** `self.import_panel.jump_to_analyze_requested.connect(lambda: self._go_to_stage(STAGE_ANALYZE))`
  (window ~L156).
- Grid signals are declared on `FileDetailsGrid` (`src/ui/file_details/file_details_grid.py:42`,
  e.g. `re_analyze_requested = pyqtSignal(list)`). `analyze_panel` connects the grid's signal to its
  own handler at `src/ui/pipeline/analyze_panel.py:522`. Follow this chain: **grid emits →
  analyze_panel re-emits a panel-level signal → window connects it to switch to `STAGE_BUNDLE` and
  call `bundle_panel.select_bundle(bundle_id)`.**

## Tasks, in dependency order

Order matters: build the data layer first (it's unit-testable with no Qt), then the display path it
feeds, then wire the UI that triggers it. Doing UI first means testing against a merge/display layer
that doesn't exist yet.

1. **Data/merge layer (TDD).** Implement the bundle-merge decision as a pure, testable unit
   (a method on `BundlingService` or `AnalysisDB` — your call, but keep Qt out of it):
   given a list of file paths → resolve image ids → gather distinct existing bundle ids via
   `get_bundles_for_image` → apply the 0 / 1 / ≥2 rule (create / add-to-existing / abort). Return
   enough for the caller to know the resulting `bundle_id` **or** an "ambiguous, aborted" outcome.
   Add a public path→id helper if needed. **Write failing tests first** (mock the repos), covering:
   none-bundled→create, one-existing→others added, two-separate→abort, and idempotency (re-bundling
   the same set). Follow existing patterns in `tests/services/` or `tests/db/`.
   **Done =** unit tests green; `mypy` clean on changed files.

2. **Bundle-view display-by-id path.** Add `bundle_panel.select_bundle(bundle_id)` that loads that
   one persisted bundle (matching `BundleReviewWidget`'s expected dict shape — verify it) and shows
   it **selected**, forcing a rebuild if a workflow is already live. This must work with **zero
   analyzed pages** (do not route through `generate_bundle_recommendations()`).
   **Done =** a unit/integration test (mock DB + `BundleReviewWidget`, or a headless Qt test in the
   style of `tests/ui/`) proving a specific persisted `'suggested'` bundle is loaded and selected.

3. **Context menu + handler + status.** Add the "Bundle" `QAction` to the multi-select branch of
   `_show_context_menu` (only when `len(selection) > 1`). Its handler collects `row["full_path"]`
   for the selection, calls the task-1 merge, on the ≥2-bundle case shows an abort dialog (reuse the
   repo's `show_warning`/`show_information` helpers used elsewhere), on success sets the pages to
   `ImageStatus.BUNDLED`, and emits a new grid signal `bundle_created = pyqtSignal(int)`.
   **Follow CLAUDE.md's "find ALL locations" UI rule** — search for every place the context menu or
   these rows are built/refreshed so the action and status update aren't half-wired.
   **Done =** unit test of the handler with a mocked db/selection asserting the right merge call and
   `bundle_created` emission; `mypy` clean.

4. **Wire the view switch.** `analyze_panel` re-emits a panel-level signal (e.g.
   `bundle_view_requested = pyqtSignal(int)`) from the grid's `bundle_created`; `window` connects it
   to `_go_to_stage(STAGE_BUNDLE)` **and** `bundle_panel.select_bundle(bundle_id)`. Mirror the
   `import_panel.jump_to_analyze_requested` wiring exactly.
   **Done =** the signal chain is unit-tested where practical; a manual trace in your report shows
   grid→panel→window→bundle_panel is fully connected.

5. **Full verification.** Run the whole suite with the main venv python
   (`...\venv\Scripts\python.exe run_tests.py tests/ -v`); `mypy` + `ruff check` clean on all changed
   files (pre-commit will enforce this anyway). Note in your report any **pre-existing** failures
   (e.g. the known `LoggingService` collection errors in the pipeline UI tests) so they aren't
   mistaken for regressions.

Then open the PR into `dev`, merge it (regular merge commit per repo policy), sync local `dev` to
`origin/dev`, and **stop** — do not delete this prompt.

## Delegation (required discipline)

Spawn subagents for mechanical work and **pass `model: "haiku"` explicitly** (an unset model silently
inherits Opus). Good candidates here: locating every call site of a symbol, extracting a method's
exact signature/return shape, reading `BundleReviewWidget` to report the precise dict keys it expects,
confirming the repo helpers used for message dialogs. Dispatch independent lookups **in parallel in
one message**. Keep in the main session: the merge-rule design, the display-path shape-matching, the
signal wiring, and anything adversarial.

Log outcomes with `C:\Users\erik.OPBTA\.claude\skills\continue-new-session-prompt\scripts\log-delegation-outcome.ps1`:
- Whenever you escalate a subagent to a stronger model, redo its work yourself, or drop a task it
  couldn't finish → log with `-Category`, a `-FailureMode`, and one line of `-Evidence`. Log it even
  if you recovered in seconds.
- **Required final step before you report finished:** log the totals, one row per category, e.g.
  `-Outcome ok -Dispatches N -Category <cat> -PromptPath 'C:\development\scan_organization\docs\PROMPTS\2026-08-01-manual-page-bundling.md'`.
  This denominator is what makes the escalation logs interpretable; the retirement gate refuses to
  clean up without a tally correlated to this prompt. If you delegated nothing, that's fine — say so.

## Reporting

Terse. End each turn with one numbered decision list. Verify counts before stating them. At the end,
report: branch, PR URL, test results (pass counts + any pre-existing failures called out), files
changed, and the grid→panel→window→bundle_panel wiring trace. Then stop for human review.
