# Task: Fix Ollama model-name mismatch that breaks analysis + auto-download; then launch for review

You are an unattended session. The LLM-preflight/auto-download feature (PR #61, already merged to
`dev`) is wired correctly, but it is fed an **invalid model name**, so analysis 404s and any
auto-download fails. Fix the name end-to-end, verify the download path, merge to `dev`, correct the
user's live config, and launch the app for the user to review. You have **no prior conversation
history** — treat "State already established" as ground truth; do not re-derive it.

## 0. Orientation

- Follow `C:\development\scan_organization\CLAUDE.md` **exactly** (test runner, file placement,
  package imports, pre-commit, PR title format). Defer to it; do not restate its rules.
- **Your worktree and branch already exist. Work in them. Do NOT create another worktree.**
  - Worktree: `C:\development\scan_organization\.worktrees\fix-ollama-model-name`
  - Branch: `fix/fix-ollama-model-name` (from `origin/dev @ 9e5efe6`, which contains PR #61)
- PyQt6 desktop app (WinScanLLM). Active provider = Ollama at `http://localhost:11434`.

## 1. Hard constraints (read first — only guardrail; you run with permissions skipped)

1. **Never trigger a real multi-GB model pull.** In tests, **mock `OllamaService.pull_model`**. Do
   not run `ollama pull` yourself. The user already has the needed model installed (see below), so
   no real download is required to make their app work.
2. **Never push directly to `main`/`dev`; never delete `main`/`dev`.** The only write to `dev` is the
   final merge of your feature branch via PR.
3. **You may edit the user's live config** `%APPDATA%/WinScanLLM/settings.ini` — but **only** the
   `[Ollama] model` value, surgically. Do not rewrite or reorder the rest of the file. (This is so
   the app works when the user reviews it.) There are no secrets in it.
4. Atomic conventional commits; semantic PR title (uppercase subject).
5. If a task seems to require a forbidden/irreversible action you can't resolve from this prompt,
   **stop and report it** in your final numbered list — no human is watching mid-run.

## 2. State already established (verified this session — do NOT re-verify, do NOT redo)

**The root cause (verified):** a spurious hyphen in the model name.
- The app's configured/seeded Ollama model is **`qwen2.5-vl`** (with a hyphen). Confirmed in:
  - `src/config/config_manager.py:93` (`"model": "qwen2.5-vl"` default) and `:310`
    (`get_setting("Ollama","model","qwen2.5-vl")` fallback),
  - `src/llm_providers/provider_factory.py:104` (`"model": "qwen2.5-vl"`),
  - the user's live `%APPDATA%/WinScanLLM/settings.ini` → `[Ollama] model = qwen2.5-vl`.
- **Ollama is running and reachable.** Its installed models (via `GET /api/tags`) are:
  `qwen3.5:9b, nomic-embed-text:latest, qwen2.5:14b, llama3.1:8b, mistral:latest,`
  **`qwen2.5vl:7b, qwen2.5vl:3b, qwen2.5vl:latest`**`, qwen3-vl:latest, deepseek-r1:8b`.
- The valid Ollama name has **no hyphen**: `qwen2.5vl`. `qwen2.5-vl` is not a real model — Ollama
  404s on analysis, `LLMReadinessService` reports it "missing", and a pull of `qwen2.5-vl` would also
  fail. **The user already has `qwen2.5vl:latest` (and 7b/3b) installed**, so correcting the name
  fixes analysis with zero download.

**The feature is otherwise correct — do NOT rebuild it:**
- `src/services/llm_readiness_service.py` — `LLMReadinessService.check_readiness()` /
  `ensure_model(policy, approve_callback, progress_callback)`. Matching is `_model_is_available()`
  (matches on `base:tag` boundary — so a corrected config `qwen2.5vl` **will** match available
  `qwen2.5vl:latest`). Startup passes `approve_callback=None` under `policy=prompt` **by design**
  (non-blocking; defers approval to Settings) — leave that design as-is.
- `src/services/llm_readiness_worker.py` — `LLMPreflightWorker(QThread)` runs the check/pull off the
  main thread.
- `src/ui/settings/settings_window_enhanced.py` — `_run_save_preflight()` (`:447`) runs readiness on
  save; on a missing model with approval it downloads via `LLMPreflightWorker(config,"auto")` with a
  `QProgressDialog` (`:526-546`). Settings UI controls live in `settings_tab_general.py` (LLM
  Readiness group) and persist `LLMPreflight/{verify_on_startup,verify_on_save,model_download_policy}`.
- Provider API: `get_default_model()` exists on `base_provider.py:69` and `ollama_provider.py:133`
  (so `check_readiness` reads a real model — the value it reads is just wrong).

**Decision already made (implement exactly):** the corrected model name is **`qwen2.5vl:latest`**
(valid, pullable, and matches the user's installed set). Use it for both the seeded defaults and the
user's live config.

**Tooling / environment (saves you a dead end):**
- Test runner: `python run_tests.py <paths>`. The **worktree has no venv** — prefix PATH with the
  main checkout's venv so `python`/`pytest`/`ruff`/`mypy`/the **pre-push hook** resolve:
  ```bash
  export PATH="/c/development/scan_organization/venv/Scripts:$PATH"
  ```
  Without it, `git push` fails at the pre-push hook with `ModuleNotFoundError: No module named
  'pytest'` (environmental, not your code).
- Pre-push hook runs `python run_tests.py tests/services tests/db tests/config tests/llm_providers
  --no-cov -x` — put tests where that gate sees them; they must pass.
- Pre-commit: ruff (auto-fixes → `git add -u` and re-commit), ruff-format, mypy (stricter — wrap
  `Any` returns in the concrete type), bandit.
- **CI is pre-existing red on every branch including `dev`** (Linux: `winrt-runtime` won't build;
  Windows: `tests/test_workflow.py` collection `LoggingService not initialized`). Both unrelated to
  this fix. The PR into `dev` will be `BLOCKED` → **admin-merge** (repo owner is admin). Expected.

## 3. Tasks, in dependency order (one branch `fix/fix-ollama-model-name`)

Order rationale: fix the seeded defaults first (source of truth for fresh installs), then add the
migration that heals existing configs, then the tests, then correct the *user's live* config, then
merge and launch. Correcting the live config before the code is merged would let a later app launch
(with old code) re-seed the wrong value; do it after, or make the migration authoritative.

1. **Rename the seeded default** everywhere it appears. Grep the whole repo for `qwen2.5-vl`
   (delegate this sweep to a `haiku` subagent) and replace the **default/seed** occurrences with
   `qwen2.5vl:latest` — at least `config_manager.py:93`, `config_manager.py:310`,
   `provider_factory.py:104`. Update any test that asserts the old default. Done = no seed/default
   references `qwen2.5-vl`; a fresh config yields `qwen2.5vl:latest`.
2. **One-time config migration** in `ConfigManager` (on load/normalize): if `[Ollama] model` equals
   the legacy `qwen2.5-vl`, rewrite it to `qwen2.5vl:latest` and persist. Idempotent; touches only
   that key. Add a unit test in `tests/config/`. Done = loading a config with the legacy value
   upgrades it automatically.
3. **Verify the readiness + auto-download path with the corrected name** (mocked — no real pull):
   - `check_readiness()` with configured `qwen2.5vl:latest` and available `["qwen2.5vl:latest", …]`
     → `ok=True` (also test config `qwen2.5vl` matches available `qwen2.5vl:latest`).
   - `ensure_model("auto", …)` with a missing-but-valid model and a **mocked** `OllamaService.pull_model`
     → asserts `pull_model` is called with the corrected name and the post-pull re-check path runs.
   Put these in `tests/services/` and/or `tests/llm_providers/`. Done = tests green; the download
   wiring is proven to receive a valid name.
4. **Tests + gates**: `export PATH=...venv...` then
   `python run_tests.py tests/config tests/services tests/llm_providers -v`, plus `ruff check`,
   `ruff format`, `mypy src/... --ignore-missing-imports`. ≥80% on any code you add.
5. **Finish + correct the user's live config + launch** — see below.

## 4. Finishing (do this exactly)

1. Commit atomically; ruff/mypy clean; changed-area tests green (venv PATH prefix).
2. Land via the github skill **`/ship`** (push → PR into `dev` → merge → cleanup). PR will be
   **BLOCKED by pre-existing red CI** → **admin-merge**
   (`gh pr merge <branch> --merge --admin --delete-branch`). Merge-commit strategy (no squash).
3. In the **main checkout** (`C:\development\scan_organization`, on `dev`):
   `git checkout dev && git pull origin dev`.
4. **Correct the user's live config so the app works on review:** in
   `%APPDATA%/WinScanLLM/settings.ini` set `[Ollama] model = qwen2.5vl:latest` (surgical edit of that
   one key only; the merged migration will also handle this, but set it explicitly so the review
   launch is guaranteed correct).
5. **Launch the app for review:** `bash scripts/start-app.sh` (background). Confirm via
   `%APPDATA%/WinScanLLM/logs/app.log` that it shows `DocumentPipelineWindow shown` and that the LLM
   preflight now reports the model **ready** (no "missing"/"not approved" warning). If feasible, spot
   the readiness/analysis path resolving `qwen2.5vl:latest`.
   - **Persistence caveat (known, reproducible):** a **detached/background** launch runs full startup
     then exits cleanly (code 0) after a few seconds instead of staying resident. That is not a crash.
     For a **persistent window the user can actually review**, the user should launch from an
     interactive terminal — tell them: run `! bash scripts/start-app.sh` in their Claude session (or
     `bash scripts/start-app.sh` in a normal terminal). Report whether your background launch stayed
     resident (a `python.exe` ~170 MB+) or exited, and include that one-liner.
6. **Do NOT delete this prompt file** (`docs/PROMPTS/2026-07-30-fix-ollama-model-name.md`) — its
   retirement is gated on a human review you cannot perform.
7. Report finished (see Reporting).

## 5. Delegation (required)

- Use `model: "haiku"` subagents (pass it explicitly — unset inherits this session's model) for
  mechanical work, dispatched in parallel in one message: the repo-wide `qwen2.5-vl` grep sweep;
  reading `config_manager` load/normalize flow to find the right migration seam; locating tests that
  assert the old default. **Keep in the main session:** the migration design (must be idempotent and
  only touch one key), the readiness-matching reasoning, and the live-config edit.
- **Delegation logging** with
  `pwsh -File C:\Users\erik.OPBTA\.claude\skills\continue-new-session-prompt\scripts\log-delegation-outcome.ps1`:
  log every escalation/redo/drop (`-Category`, `-FailureMode`, one-line `-Evidence`) even if
  recovered in seconds. **Required final step before reporting finished:** log totals, one row per
  category, `-Outcome ok -Dispatches N`, each tagged `-PromptPath
  'C:\development\scan_organization\docs\PROMPTS\2026-07-30-fix-ollama-model-name.md'`. If you
  delegated nothing, record that explicitly. This tally is the denominator — do not skip it.

## 6. Reporting

Terse; lead with the action/answer; **end every turn with a single numbered list of items needing a
decision** — nothing that matters lives outside it. Verify counts with a tool before stating them;
correct any earlier wrong claim in one line. On finish, state: what merged (PR #, SHA), test results,
whether the model now resolves, whether the app launched and stayed resident, and the interactive
one-liner for a persistent review window.

---

**Model note:** this session is pinned to Sonnet — the work is a targeted rename + a small,
careful config migration + verification, not frontier reasoning. Delegate the mechanical greps to
`haiku`; switch with `/model` only if the migration turns out trickier than expected.
