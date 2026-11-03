# Task: PR2-5 (analysis diagnostics/UX) + rigorous proof of the pre-push code-review hook

You are an unattended session. Treat "State already established" as ground truth — it was
verified this session by reading code, running the actual test suite, and executing real `git
push` operations. Do not re-derive it. You have no prior conversation history.

## 0. Orientation

- **Your worktree and branch already exist. Work in them. Do NOT create another worktree.**
  - Worktree: `C:\development\scan_organization\.worktrees\analysis-error-diagnostics`
  - Branch: `feat/analysis-error-diagnostics` (branched from `origin/dev @ bfbb663`, which already
    contains PR #63 — pre-push hook speed-up — and PR #64 — Ollama SDK-key + f-string crash fixes.
    Both merged and verified green this session. Do not redo either.)
- Follow `C:\development\scan_organization\CLAUDE.md` exactly (test runner, file placement, package
  imports, pre-commit, PR title format, PR size limits — warn at 400 lines changed, hard limit 800).
  Defer to it; do not restate its rules.
- PyQt6 desktop app (WinScanLLM). This is a continuation of an earlier unattended session whose
  original task file is `docs/PROMPTS/2026-07-30-ollama-reliability-and-analysis-ux.md` (still in
  the main checkout, untouched, for reference only — do not edit or delete it, it is not yours).

## 1. Hard constraints

1. **Never trigger a real multi-GB model pull in tests.** Mock `OllamaService.pull_model` /
   `ollama.Client`. Do not run `ollama pull` yourself.
2. **Never push directly to `main`/`dev`; never delete `main`/`dev`.** Land everything through PRs.
3. **The venv lives in the MAIN checkout, not this worktree.** `scripts/pre_push_tests.py`'s
   self-healing venv lookup only checks `<repo-root>/venv` relative to itself, and a worktree has
   no `venv/` of its own — so it silently falls through to whatever `python` is first on PATH.
   **Before every `git push` (and before running tests directly), prefix PATH with the venv:**
   `PATH="/c/development/scan_organization/venv/Scripts:$PATH"` — otherwise the pre-push
   `pytest-fast` hook fails with `ModuleNotFoundError: No module named 'pytest'`, which looks like a
   real failure but is purely this PATH issue. This is not a bug to fix — it's a known environment
   quirk, already worked around this session.
4. **A local pre-push hook (`.git/hooks/pre-push.legacy`, NOT tracked in the repo — Erik's own
   machine config) runs an automated Claude Code review and blocks the push only on a regex match
   for specific security-vulnerability phrases** (`SQL injection|XSS|hardcoded.*secret|...` etc,
   case-insensitive). It was already patched this session to skip lines that *negate* a trigger
   phrase (e.g. "no hardcoded secrets" no longer false-positives). If it blocks on a *real* finding
   from your own diff, fix the finding — don't bypass with `--no-verify`. If you believe it's a
   false positive, stop and report it in your final numbered list rather than working around it
   silently — this is Erik's personal safety net, not yours to weaken unilaterally.
5. **This repo's CI is pre-existing red on some jobs** (Windows: `tests/test_workflow.py`
   collection fails with `LoggingService not initialized`; there was also a `Build Check` failure
   observed this session on PR #64, confirmed as a pre-existing, unrelated issue — not caused by
   the change being merged). Every PR from this session may show `mergeStateStatus: BLOCKED` for
   this reason — check `gh pr checks <n>` first; if the *only* red jobs are the ones named above (or
   clearly unrelated to your diff), merge via `gh pr merge <n> --merge --admin`. **Do not use
   `--delete-branch` when merging from inside this worktree** — it fails with `fatal: 'dev' is
   already used by worktree at 'C:/development/scan_organization'` because the main checkout has
   `dev` checked out. Merge without `--delete-branch`, then separately run
   `git push origin --delete <branch>` from the worktree and clean up the local branch from the
   **main checkout** (`cd C:\development\scan_organization && git checkout dev && git pull`) —
   never try to delete/prune a branch from within the worktree that has it checked out.
6. If a task seems to require a forbidden/irreversible action you can't resolve from this prompt,
   **stop and report it** in your final numbered list — no human is watching mid-run.

## 2. State already established (verified this session — do not re-verify, do not redo)

### Pre-push hook mechanics — confirmed facts

- `.git/hooks/pre-push` is the pre-commit-framework stub; it chains to `.git/hooks/pre-push.legacy`
  (a hand-written bash script, **not tracked in git**, backed up by `pre-commit install` when it
  found an existing hook). That legacy script runs `claude --print "/code-review $changed_files"`
  where `$changed_files` is computed from `git diff --name-only <range>` — on a branch's *first*
  push, `<range>` is `origin/<base>...<local_sha>` (the **full branch-vs-base diff**, not just the
  latest commit); on subsequent pushes to the same branch it's `<remote_sha>...<local_sha>` (just
  the new commits).
- The `claude --print` call has **no `--model` flag** at all. `~/.claude/settings.json` sets a
  global default `"model": "opus[1m]"` — confirmed by direct read of that file. So every pre-push
  review runs on Opus with a 1M context window, fully unscoped, for what is fundamentally a
  per-file checklist task. This is not tiered per the user's own `~/.claude/rules/
  subagent-model-selection.md` philosophy.
- `~/.claude/plugins/installed_plugins.json` was read directly this session: the marketplace plugin
  `code-review@claude-plugins-official` (a 5-parallel-Sonnet-agent + Haiku-confidence-scoring
  methodology, designed to review an actual GitHub PR via `gh pr view`) is **NOT installed** for
  this user, in any scope. It cannot be the thing executing inside the hook. An earlier hypothesis
  this session (that the observed "sub-review agents" language came from that plugin) was **wrong**
  and is retracted — flag this if you see it referenced anywhere as fact.
- Two other `/code-review` definitions exist on this machine and remain **unresolved** as to which
  (if either) actually fires: `~/.claude/commands/code-review.md` (plain, single-pass, ~40-line
  checklist, no sub-agents mentioned) and `~/.claude/skills/code-review/SKILL.md` (a large
  documentation skill about multi-engine — Claude/Codex/Gemini — review options; not itself an
  executable review procedure).
- A direct attempt this session to probe command resolution —
  `claude --print --model haiku "/code-review nonexistent_probe_file_xyz.py"` — did **not** behave
  like a resolved slash command at all. It returned a confused, conversational response ("That
  command doesn't match any real tools or files in your repo... `C:/Program Files/Git/code-review`
  isn't a valid executable"), suggesting `/code-review` was passed through as plain chat text rather
  than expanded from a command template, and ended with an unrelated `SessionEnd hook ... Hook
  cancelled` message. **This directly contradicts the fact that real, multi-file, line-accurate
  reviews clearly DID execute during actual `git push` invocations this session** — captured hook
  output referenced genuine file/line content from this repo (e.g. `settings_window_enhanced.py:459`
  `_run_save_preflight`, `file_details_table_model.py:24`, `ollama_provider.py:151`) across multiple
  separate pushes, which cannot be templated/generic text — it required actually reading this
  codebase. **The probe's flaws, most likely causes of the contradiction:** it changed two variables
  at once relative to the real hook invocation (added `--model haiku`, and used a single nonexistent
  filename instead of a real list of existing changed files) — either could plausibly change how the
  CLI resolves or short-circuits the command. This was not a clean experiment and its result should
  not be trusted as evidence either way. **Task 1 below is to design and run a clean one.**

### Real review outputs captured this session (use as raw evidence, not as something to re-fetch)

Two real pushes went through the actual hook and produced full reviews:
1. PR #64's second push (37 files, first push of a multi-commit branch) — found 1 High, 2 Medium, 4
   Low issues, all citing real file:line locations in this repo, e.g. `settings_window_enhanced.py:
   459` (`_run_save_preflight` blocking the UI thread), `file_details_table_model.py:24` (column
   reorder breaking persisted layouts), `ollama_provider.py:151` (untested malformed-model-list
   edge case). Also explicitly said in its own "Strengths" section: "no hardcoded secrets, no
   injection surface, no unsafe rich-text sinks" — the substring `hardcoded.*secret` in that
   sentence is exactly what caused the false-positive block (fixed by the negation patch).
2. PR #64's final push (5 files, after rebase onto the smaller post-PR63 dev baseline) — "Code
   review passed", no findings.
3. PR #63's push (36 files) — "Code review passed", no findings.

These are strong circumstantial evidence a real review runs, but the user explicitly wants this
**proven**, not inferred from circumstantial pattern-matching. That's Task 1.

### PR2 design — fully decided this session, implement as specified, do not redesign

**Root cause** (from `AnalysisService`/`AnalysisDB`/`ImageFilesRepository`, all in `src/`):
`_analyze_single_page()` (`src/services/analysis_service.py`, the `not result["success"]` branch
around line ~362-377 and the `except Exception` branch around line ~410-431) updates image status to
`"error"` on failure but **never persists a proper diagnostic record** — no provider, model, prompt,
response, or processing time survive a fresh DB read. The bulk `scan_all_directories()` path calls
`self.analysis_db.save_error(...)` (the *old*, poorer `analysis_errors` table — only
`file_path`/`error_message`/`error_type`), but `re_analyze_file()`, `analyze_specific_files()`, and
— critically — the **actual live re-analysis path**, `AnalysisWorker._process_job()`'s
`JobType.ANALYZE_FILES` branch (`src/services/analysis_worker.py`, calls
`thread_analysis_service._analyze_single_page(...)` **directly**, bypassing
`re_analyze_file`/`analyze_specific_files` entirely) — don't persist anything richer either.

**The already-built, unused machinery to wire up instead:** `analysis_results` table
(`src/db/schema.py`) already has `had_error BOOLEAN DEFAULT 0` with an index, and
`AnalysisRepository.save()` (`src/db/repositories/analysis_repo.py`) already accepts `had_error`,
`prompt_text`, `response_text`, `provider_name`, `model_name`, `processing_time_ms` as real
parameters. `AnalysisRepository.count_by_status()` already computes `{total, successful, errors}`
from this column — confirmed zero callers anywhere in `src/` this session.

**Chosen design (do not use the state-doc's original "also write a metadata row" approach — it's
unsafe):** `MetadataRepository.create_from_analysis()` does `INSERT OR REPLACE INTO metadata` keyed
on `image_file_id UNIQUE` — writing a metadata row on a failed **re-analysis of a previously
successful file** would silently wipe that file's good company/document-type/etc. data. Instead:

1. Add `AnalysisDB.save_failed_analysis(file_path, file_hash, provider_name, model_name,
   prompt_text, error_message, processing_time_ms=0)` in `src/db/analysis_db.py`, mirroring
   `save_analysis()`'s image-file lookup/registration (reuse `self._image_files.get_by_path` /
   `.register`), then call `self._analysis.save(..., had_error=True, response_text=error_message or
   "Unknown error", extracted_metadata=None, model_options=None)`. **Do not touch the `metadata`
   table at all** — this is the key design decision that avoids the data-loss risk.
2. Call `self.analysis_db.save_failed_analysis(...)` from **inside `_analyze_single_page()`**, in
   both error branches — this is the single choke point that fixes `scan_all_directories()`,
   `analyze_specific_files()`, `re_analyze_file()`, `analyze_single_file()`, **and** the real
   `AnalysisWorker` path all at once, since they all call `_analyze_single_page()`. Thread the
   actual prompt text through (it's held in a local `metadata_prompt` variable inside the try block
   already — for the exception branch, guard for the case where the exception happens before that
   variable is assigned).
3. Fix the join gap: `ImageFilesRepository.get_all_with_analysis()` **and** the structurally
   identical `get_batch_with_analysis()` (both in `src/db/repositories/image_files_repo.py`)
   currently do `LEFT JOIN analysis_results ar ON m.analysis_result_id = ar.id` — routed through the
   metadata table, so a failed analysis with no (or a stale) metadata row never surfaces. Change
   both to join the **latest** `analysis_results` row directly off `image_file_id`, independent of
   `metadata`:
   ```sql
   LEFT JOIN analysis_results ar ON ar.id = (
       SELECT ar2.id FROM analysis_results ar2
       WHERE ar2.image_file_id = img.id
       ORDER BY ar2.analyzed_at DESC, ar2.id DESC
       LIMIT 1
   )
   ```
   This decouples "latest attempt" (raw provenance — always current) from "approved metadata"
   (sticky — only updated on success or user edit), which is the correct semantics: a failed
   re-analysis shouldn't erase a file's last-known-good company/doc-type, but should still surface
   its own diagnostics. `AnalysisRepository.get_latest_by_image_file_id()` (used by the file-details
   dialog via `AnalysisDB.get_analysis()`) already does this correctly — no change needed there,
   already verified this session.
4. Fix `analyze_panel.py::_transform_data_for_grid()` — `"error_message": ""` is hardcoded (never
   sourced from anywhere). Change to source from the row: `(row.get("response_text") or "") if
   row.get("had_error") else ""`. Verified this session: `error_message` is a real, wired-up grid
   column (`file_details_table_model.py`) — shown in its own column, colors the row light-red,
   colors the status text red, and shown as a distinct "Error" line in the file-details dialog's
   Analysis Information section — separate from the LLM Prompt/Response sections (which read
   `prompt_text`/`response_text` directly and will already work correctly once step 3 lands, no
   separate fix needed for those two).
5. Verify `_refresh_analytics_section()` in `analyze_panel.py` — **confirmed this session it already
   reads `r.get("had_error")` from `get_analyzed_pages()`** (line ~354: `n_errors = sum(1 for r in
   raw_data if r.get("had_error"))`) — so once steps 1-3 land, the Analytics panel's error count
   will update correctly with **no changes needed** there. Confirm this with a real test rather than
   re-reading the code.
6. Add/update tests in `tests/services/test_analysis_service.py` and `tests/db/` for the new
   error-persistence path (mock the provider failure, assert the DB row and its fields — provider,
   model, prompt, had_error, response_text). Add a test proving a failed re-analysis of a
   previously-successful file does NOT touch its `metadata` row (the specific risk this design
   avoids).
7. End-to-end verify: force a re-analysis against a mocked/deliberately-unreachable provider,
   confirm the file-details dialog shows prompt/error/provider/model/processing-time, and the
   Analytics panel's error count updates without a full app restart.

## 3. Tasks, in order

### Task 1 — Prove or disprove the code-review hook, rigorously (do first — independent, fast)

The user wants a **definitive, evidence-based** answer to: "Does a code review get performed as
part of the hook? How was it tested? What's the proof?" — not inference from pattern-matching. Do
NOT just restate the circumstantial evidence in State §2 above — design and run a clean experiment.

Suggested method (adjust if you find a better one, but it must produce artifacts you can cite):

1. Create a **fully disposable** scratch branch off `origin/dev` (not this worktree's branch — use
   a separate throwaway branch/worktree, or a temp branch in this worktree that you delete before
   moving to Task 2 — your call, but it must not pollute `feat/analysis-error-diagnostics`).
2. Add one small `.py` file containing an unambiguous, deliberately obvious issue an LLM could only
   catch by actually reading the file content — e.g. a fake secret
   (`API_KEY = "sk-test-DEFINITELY-FAKE-1234567890abcdef"`) and a raw f-string SQL query
   (`query = f"SELECT * FROM users WHERE id = {user_id}"`), each on an identifiable line number.
3. Commit it, then push through the **real** hook (PATH must include the venv — see constraint #3).
   Capture the full output.
4. Check whether the review output cites the actual file name, line number, and variable names you
   used — if it does, that's strong direct proof a real read happened (not a cached/generic
   response). If it doesn't, that's evidence against a real review running.
5. Confirm whether the push actually **blocks** this time (a positively-stated "hardcoded secret"
   finding should still trip the regex even after this session's negation patch — that patch only
   suppresses negated sentences like "no hardcoded secrets", not real positive findings). This
   proves the blocking mechanism itself is live, not just cosmetically reporting.
6. Optional, if time permits — identify which of the two candidate `/code-review` sources
   (`~/.claude/commands/code-review.md` vs `~/.claude/skills/code-review/SKILL.md`) actually fires:
   temporarily add a unique marker string (e.g. `"UNIQUE-MARKER-<random>"`) to
   `~/.claude/commands/code-review.md`'s checklist, then re-run the **exact same real hook
   invocation pattern** (no `--model` override, a real list of existing changed `.py` files — do not
   repeat this session's flawed probe design). If the marker surfaces in the review's behavior or
   is otherwise attributable, that identifies the source. **Revert the marker edit afterward
   regardless of outcome** — don't leave test markers in the user's global command file.
7. Clean up every scratch branch you created, locally and on `origin`, before finishing this task.
8. Write your answer with the artifacts as evidence: quote the specific lines from the captured hook
   output that prove your conclusion, not a restatement of confidence.

### Task 2 — PR2: Error persistence + diagnostics (implement the design in State §2 verbatim)

Implement exactly the design already decided above. This branch (`feat/analysis-error-diagnostics`)
is already checked out for this. Run the pre-push test gate
(`PATH="/c/development/scan_organization/venv/Scripts:$PATH" python run_tests.py tests/services
tests/db tests/config tests/llm_providers --no-cov -x -n auto` — note `-n auto` now works, ~30s not
~120s), push, open PR into `dev`, merge per constraint #5.

### Task 3 — PR3: Fail-fast connectivity + honest progress (new branch off updated dev, same worktree)

After Task 2 merges, sync: from the **main checkout**, `git checkout dev && git pull`. From the
**worktree**, `git fetch origin && git checkout -b fix/ollama-timeout-and-progress origin/dev`.

1. **Reproduce the "couldn't communicate with Ollama" failure live first** — don't apply the fix
   blind. `OllamaService.__init__` (`src/llm_providers/ollama_service.py`) builds one
   `httpx.Timeout(timeout)` shared across connect/read/write/pool (default 300s), used by both
   `pull_model()` (long-running by design) and `chat_with_vision_model()` (the per-image analysis
   call) — a genuinely-unreachable host and a genuinely-slow first vision-model load currently look
   identical: both wait the full timeout before failing.
2. Split the timeout: a short connect-timeout (5-10s) distinct from the long generation timeout —
   `httpx.Timeout(timeout, connect=<short>)` at the client construction. Verify whether
   `chat_with_vision_model` needs its own client/timeout distinct from `pull_model`'s.
3. Enrich the error path (`chat_with_vision_model`'s bare `ConnectionError(f"Failed to communicate
   with Ollama: {e}")`) to include `base_url`, model name, and elapsed time — flows into both the
   Status Event toast and (after Task 2) the persisted error record.
4. Progress bar UX (`analyze_panel.py`): the "100%" shown while the *last* file is still analyzing
   is real but misleading (`current = idx + 1` fires *before* `_analyze_single_page` runs for that
   file, in `scan_all_directories()`). This is a genuine UX judgment call, not a correctness fix —
   recommend switching to indeterminate/busy mode (`progress_bar.setRange(0, 0)`) while the last
   file's HTTP call is in flight, since there's no real sub-file progress signal available. State
   which you chose and why in the PR description.
5. Tests + the same push/PR/merge flow as Task 2.

### Task 4 — PR4: Analyze refresh button + Import scan lock (new branch, same pattern)

1. **Refresh button** (`analyze_panel.py`) — trivial. Add to the existing toolbar, wire
   `btn.clicked.connect(self.refresh)` — `refresh()` (`src/ui/pipeline/analyze_panel.py`) already
   re-queries the DB, transforms, refreshes the grid, and refreshes analytics. No new logic.
2. **Import-view scan-in-progress lock** — `main.py::_start_discovery_if_enabled()` creates its own
   `DiscoveryWorker` instance whose `progress` signal is **never connected to anything**, and it's
   separate from the instance `import_panel.py::_on_scan_clicked()` uses for the manual "Discover
   Images" button (which *does* have working UI: `scan_progress_bar`,
   `_on_scan_progress`/`_on_scan_finished` at `import_panel.py:636-651`). Wire the startup worker's
   `progress`/`finished`/`error` signals through the same mechanism the manual button uses (or an
   equivalent visible "scanning…" state), and **visually disable/lock the Import view's interactive
   elements** (scan button, refresh button, directory combo, tree selection buttons) while a scan —
   startup or manual — is in flight.
3. Tests + push/PR/merge.

### Task 5 — PR5: Settings LLM tab Validate button + icon-only buttons (new branch, same pattern)

1. **Validate button** — `settings_tab_provider.py`'s `model_buttons` layout already has
   Refresh/Download (`QPushButton`, `.setObjectName("compactButton")`, `.setToolTip(...)`). Add a
   third button that tests the **currently-entered** (not necessarily saved) base URL + model
   combination without requiring Save first. `OllamaProvider.test_connection()`
   (`src/llm_providers/ollama_provider.py:166-181`) already exists for exactly this — construct a
   transient provider/service from the in-progress form values and call it; show success/failure
   inline (a status label next to the buttons). Reuse the short-connect-timeout probe from Task 3
   if it landed first.
2. **Icon-only buttons** — convert Refresh/Download/Validate to icon-only with the label moved into
   the tooltip (tooltips already exist on Refresh/Download). **Use `QStyle.standardIcon()`** —
   confirmed this session it's the only icon pattern already in use in this codebase
   (`settings_tab_directories.py:243`, `QStyle.StandardPixmap.SP_DirIcon`) — no dedicated icon asset
   set exists (`assets/images/` is all documentation screenshots, not UI icons). Do not add new
   image files.
3. Tests + push/PR/merge.

## 4. Delegation (required)

Use `model: "haiku"` subagents, dispatched in parallel in one message where independent, for
mechanical work: writing DB/service unit tests once the shape is decided (Task 2 step 6), grepping
for other callers of `_analyze_single_page`/`get_all_with_analysis`/`get_batch_with_analysis` to
confirm no other call sites need touching, drafting the icon-conversion diff for Task 5 once the
pattern is confirmed, and any repo-wide sweeps needed along the way.

**Keep in the main session:** the hook-proof experiment design and evidence interpretation (Task
1), the live-repro-before-fix step in Task 3, the progress-bar UX call in Task 3, and PR
sequencing/merge judgment.

**Delegation logging** with
`C:\Users\erik.OPBTA\.claude\skills\continue-new-session-prompt\scripts\log-delegation-outcome.ps1`:
log every escalation/redo/drop (`-Category`, `-FailureMode`, one-line `-Evidence`) even if
recovered in seconds. **Required final step before reporting finished:** log totals, one row per
category, `-Outcome ok -Dispatches N`, each tagged
`-PromptPath 'C:\development\scan_organization\docs\PROMPTS\2026-07-30-analysis-diagnostics-ux-and-hook-proof.md'`.
If nothing was delegated, record that explicitly — this tally is required, not optional.

## 5. Reporting

Terse; lead with the action/answer; end every turn with a single numbered list of items needing a
decision — nothing that matters lives outside it. Verify counts with a tool before stating them;
correct any earlier wrong claim in one line. On finish, state: the Task 1 answer with its cited
evidence, which PRs merged (numbers, SHAs), test results per PR, whether each of the 4 features is
confirmed fixed (not just "code changed"), and any item deferred with a clear reason.

---

**Model note:** pinned to Sonnet — matches the model that did the design work in this prompt (the
PR2 schema/join decision, the timeout-conflation diagnosis) and the mix of remaining work: Task 1's
experiment design and Task 3's UX call need real judgment, but Tasks 2/4/5 are largely implementing
already-decided designs. Delegate the mechanical pieces named above to `haiku`; escalate via
`/model` only if Task 1's investigation turns out to need deeper reasoning than expected.
