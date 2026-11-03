# Task: LLM target/model preflight — startup + settings-save readiness checks with gated auto-download

You are an unattended session. Implement this feature end-to-end, merge it into `dev`, then start
the app locally and report. Everything you need is below — you have **no prior conversation
history**, so treat the "State already established" section as ground truth and do not re-derive it.

---

## 0. Orientation

- Follow the repo's own `C:\development\scan_organization\CLAUDE.md` **exactly** (test runner,
  file placement, package-import rules, pre-commit, PR title format). Do not restate or reinvent
  its conventions — defer to it.
- **Your worktree and branch already exist. Work in them. Do NOT create another worktree.**
  - Worktree: `C:\development\scan_organization\.worktrees\llm-model-preflight`
  - Branch: `feat/llm-model-preflight` (branched from `origin/main @ 030e0b5`)
- This is a PyQt6 desktop app (WinScanLLM). No HTTP service of its own. It talks to a local Ollama
  server (`http://localhost:11434`) and, optionally, Claude/Gemini CLIs via subprocess.

## 1. Hard constraints (read first — this is the only guardrail; you run with permissions skipped)

1. **Never push directly to `main` or `dev`, and never delete `main` or `dev`.** The only write to
   `dev` is the final merge of your feature branch via a PR (Task 7).
2. **Model downloads can be multi-GB.** Respect the `model_download_policy` setting you are building.
   Its default is `prompt` — never silently pull a model except when policy is explicitly `auto`.
   During your own testing, **mock `OllamaService.pull_model` — never trigger a real multi-GB pull.**
3. **No secrets in code or commits.** There are none needed here (LLM provider access is configured
   in-app), so do not add any.
4. Atomic conventional commits (`feat:`/`test:`/`refactor:` …), PR title in the repo's semantic
   format (uppercase subject). One logical change per commit.
5. If a task appears to require a forbidden or irreversible action you cannot resolve from this
   prompt, **stop and report it in your final numbered list** rather than improvising — no human is
   watching to approve mid-run.

## 2. State already established (verified this session — do NOT re-verify, do NOT redo)

**Base/merge topology**
- Branch is off `origin/main @ 030e0b5`. `main` is a **strict ancestor of `dev`** (dev is +10, main
  +0), so your feature merges into `dev` cleanly with no divergence.
- `origin/main` already contains the StatusReporter/status-history system **and** `ollama_service.py`
  — your design (below) depends on both and they are present in your tree.

**Provider layer** (`src/llm_providers/`)
- All providers implement `test_connection() -> bool` and `get_available_models() -> list[str]`
  (`base_provider.py:50,60`; ollama/claude_cli/gemini_cli all at `:159,:168`).
- `OllamaProvider` (`ollama_provider.py`): `base_url` from config (`:37`, default
  `http://localhost:11434`), wraps `OllamaService` (`:42`), has `validate_config()` (`:191`).
- **`OllamaService` already has the download primitive** (`ollama_service.py`):
  - `list_models() -> list[dict]` (`:24`) — raises `ConnectionError` if server unreachable.
  - `pull_model(model_name, progress_callback=None) -> None` (`:34`) — streams progress via the
    `ollama` SDK, calls `progress_callback(f"{status}: {pct}%")`, verifies the model appears after.
- Claude/Gemini CLI providers **cannot download models** — their `get_available_models()` returns a
  static list. For them, "readiness" = CLI reachable (`test_connection`) + selected model is in the
  available list. No pull path.
- Create providers via `ProviderFactory.create_from_config_manager(config_manager)`
  (`provider_factory.py`). Ollama default config: `base_url=http://localhost:11434`, `model=qwen2.5-vl`.

**Where analysis fails today** — `AnalysisService._analyze_single_page` (`src/services/analysis_service.py`)
calls `provider.analyze_images(...)`; when the model is missing at the host, this fails per-file.
The point of this feature is to catch that **before** analysis runs and self-heal.

**Startup hook** — `src/main.py`:
- `_on_init_complete()` (`:235`) creates `DocumentPipelineWindow`, then calls
  `_start_discovery_if_enabled(window, config_manager)` (`:255`) and shows the window (`:262`).
- Deferred startup work uses `QTimer.singleShot(500, fn)` (see `_start_discovery_if_enabled` at
  `:65`) and runs off the main thread via a worker (`DiscoveryWorker`) with `finished`/`error`
  signals. Toasts are shown via a toast notifier (`toast_notifier.show_discovery_toast(count)` at
  `:48`). There is a `src/services/notification_service.py` — inspect it for the toast API.
- **This is where you add the startup preflight** (Task 3): deferred, non-blocking, off the main
  thread, surfacing results via a StatusEvent (+ toast), never blocking window show.

**Settings save hook** — `src/ui/settings/settings_window_enhanced.py`:
- `save_settings()` (`:447`), wired from `button_box.accepted.connect(self.save_settings)` (`:306`).
  It writes provider config (`LLMProvider/active_provider`, and `Ollama/model`, `Ollama/base_url`,
  etc.) then `self.accept()` (`:636`). **This is where you add the settings-save preflight** (Task 4):
  after writing settings, run readiness and inform the user of the result (with a progress dialog on
  the download path). Note: the Ollama model combo already carries download-status hints and there is
  a `_ModelLoaderMixin` (`settings_model_loader.py`) — reuse existing model-loading rather than
  duplicating it where you can.
- Settings mixins/decomposition are documented in the project memory; the orchestrator MRO is in
  `settings_window_enhanced.py`. New settings-tab controls follow the existing `_SettingsTab*Mixin`
  pattern.

**StatusReporter (the failure channel)** — `src/services/status_reporter.py`:
- `get_reporter()` returns the singleton. `reporter.error(feature, title, *, detail=..., file_path=...,
  traceback=..., context={...})`, plus `.warn(...)` / `.info(...)`. Events show up in the Analyze
  view's status-history bar/dropdown. Use `warn` for "model missing, will download" and `error` for
  "host unreachable / download failed", with an actionable `detail` and a `context` dict
  (`provider`, `model`, `base_url`).

**Config** — `src/config/config_manager.py`: `get_bool(section,key,default)`, `get_int`,
`get_setting(section,key,default=None)`, `set_setting(section,key,value)`,
`get_provider_config(name)`. Defaults are seeded in `_create_default_config()` — **add your new
section there** so a fresh install has it.

**Tooling / environment (important — saves you a dead end)**
- Test runner is `python run_tests.py <paths>` (pytest under the hood, sets `sys.path` to `src/`).
- **The worktree has no usable venv.** Prefix PATH with the main checkout's venv so `python`,
  `pytest`, `ruff`, `mypy`, and the git **pre-push hook** all resolve:
  ```bash
  export PATH="/c/development/scan_organization/venv/Scripts:$PATH"
  ```
  Without this, `git push` fails at the pre-push hook with `ModuleNotFoundError: No module named
  'pytest'` — that is environmental, not your code.
- Pre-push hook runs `python run_tests.py tests/services tests/db tests/config tests/llm_providers
  --no-cov -x`. **Put your new service tests in `tests/services/` and provider tests in
  `tests/llm_providers/`** so the gate exercises them; they must pass or the push is blocked.
- Pre-commit runs ruff, ruff-format, mypy, bandit. ruff may auto-fix on commit → `git add -u` and
  re-commit. mypy is stricter than a bare run (flags `no-any-return`) — wrap `Any`-typed returns in
  the concrete type (e.g. `bool(...)`).

**CI reality (do not be alarmed; do not try to "fix" it here)**
- GitHub Actions checks are **pre-existing red on every branch, including `dev`**: Linux jobs fail at
  `pip install` (`winrt-runtime` can't build on Linux); Windows jobs fail at test *collection*
  (`RuntimeError: LoggingService not initialized` in `tests/test_workflow.py`). Both are unrelated to
  this feature. The PR into `dev` will therefore be `BLOCKED` by red required checks and needs an
  **admin merge** (the repo owner is admin). This is the established, expected path.

**Decisions already made (do NOT re-ask — implement exactly these)**
- `model_download_policy` **default = `prompt`** (values: `off` | `prompt` | `auto`).
- Startup preflight failure surfaces **non-blocking**: a StatusEvent + a toast; never a startup-blocking
  modal.
- **Ollama is the only provider that downloads.** Claude/Gemini CLI get reachability + valid-model-name
  validation only, with a clear "cannot auto-download — install Ollama-side or select a valid model"
  message.
- Finish by **merging into `dev`** (feature branched off `origin/main`) and then **starting the app
  locally** and reporting.

## 3. Design to implement (this is the agreed approach)

A single reusable service used by both entry points (DRY), capability-aware, that reports through the
StatusReporter.

**New: `src/services/llm_readiness_service.py`**
- A small immutable result, e.g. `@dataclass(frozen=True) class ReadinessResult` with:
  `provider_name: str`, `reachable: bool`, `model: str`, `model_available: bool`,
  `can_download: bool`, `ok: bool`, `message: str`.
- `class LLMReadinessService:` constructed from `ConfigManager` (build the active provider via
  `ProviderFactory.create_from_config_manager`).
  - `check_readiness() -> ReadinessResult` — `test_connection()`; if reachable, compare the configured
    model against `get_available_models()` (Ollama: also usable via `service.list_models()`). Set
    `can_download = (provider is Ollama)`.
  - `ensure_model(policy, approve_callback=None, progress_callback=None) -> ReadinessResult` — if the
    model is missing and `can_download`:
    - `policy == "off"` → do not download; return not-ok with a "missing, downloads disabled" message.
    - `policy == "prompt"` → call `approve_callback(model)`; download only if it returns True.
    - `policy == "auto"` → download.
    - Download via `OllamaService.pull_model(model, progress_callback)`; re-check afterwards.
  - Emit StatusEvents inside the service (or return the result and let callers emit — pick one and be
    consistent): `warn` for "missing → downloading", `error` for "unreachable" / "download failed",
    `info`/nothing for success. Include `context={"provider":..., "model":..., "base_url":...}`.
- **Never block the main thread on network/download.** The service itself is synchronous; callers run
  it on a worker thread (startup) or a modal progress dialog with the pull on a `QThread` (settings).

**New config section** (seed in `_create_default_config()`), section `[LLMPreflight]`:
- `verify_on_startup` = `true`
- `verify_on_save` = `true`
- `model_download_policy` = `prompt`

**Settings UI** — add a control for `model_download_policy` (a 3-way: Off / Prompt / Auto) and the two
`verify_on_*` toggles, following the existing `_SettingsTab*Mixin` pattern; persist them in
`save_settings()`.

## 4. Tasks, in dependency order (each on the one branch `feat/llm-model-preflight`)

Order rationale: config + service are the foundation both entry points import; build and unit-test
them first so the wiring in Tasks 3–4 targets a tested API. UI/setting (Task 5) can land with Task 4.
Tests (Task 6) accompany each unit as you go (TDD per CLAUDE.md), not bolted on at the end.

1. **Config**: add `[LLMPreflight]` defaults in `_create_default_config()` (+ any typed getters used).
   Done = a fresh config exposes the three keys with the defaults above.
2. **`LLMReadinessService`** (`src/services/llm_readiness_service.py`) + unit tests in
   `tests/services/test_llm_readiness_service.py`. Mock providers/`OllamaService` — **never a real
   pull**. Cover: reachable+present (ok), reachable+missing+ollama+auto (downloads), +prompt
   (approve/deny), +off (no download), unreachable (error), CLI-provider-missing (validate-only, no
   download). Done = tests green, `check_readiness`/`ensure_model` behave per policy.
3. **Startup wiring** in `src/main.py::_on_init_complete` — gated on `LLMPreflight/verify_on_startup`,
   deferred (`QTimer.singleShot`), run off the main thread, non-blocking; on failure emit a StatusEvent
   + toast; on `prompt` policy surface an approval (non-blocking) before download. Done = window still
   opens instantly; a missing model produces a status event/toast, not a hang or a blocking modal.
4. **Settings-save wiring** in `settings_window_enhanced.py::save_settings` — gated on
   `LLMPreflight/verify_on_save`; after writing settings, run readiness; on missing model honor the
   policy (progress dialog for the download); **inform the user of the outcome, including failures**.
   Done = saving with a bad host/model tells the user clearly; a good config is silent or a brief OK.
5. **Settings UI control** for the policy + toggles (Task 3/4 read these). Done = the control persists
   and round-trips.
6. **Tests**: ≥80% on the new service; add focused tests for the save-path behavior (mock Qt deps per
   CLAUDE.md's UI-testing guidance) and, where feasible, the startup helper. Run:
   `export PATH="/c/development/scan_organization/venv/Scripts:$PATH"` then
   `python run_tests.py tests/services tests/llm_providers -v` and the changed-area suites. Also
   `mypy src/... --ignore-missing-imports`, `ruff check`, `ruff format`.
7. **Finish** (see below).

## 5. Finishing (do this exactly)

1. Ensure everything is committed on `feat/llm-model-preflight`, ruff/mypy clean, changed-area tests
   green (with the venv PATH prefix).
2. Land it via the **github skill `/ship`** (it handles push → PR into `dev` → preflight → merge →
   worktree cleanup). The PR into `dev` will be **BLOCKED by pre-existing red CI** — perform an
   **admin merge** (`gh pr merge <branch> --merge --admin --delete-branch`), consistent with the
   established path. Merge commit strategy = merge commit (no squash).
3. After the merge, in the **main checkout** (`C:\development\scan_organization`, on `dev`), sync:
   `git checkout dev && git pull origin dev`.
4. **Start the app locally** and confirm it launches: `bash scripts/start-app.sh` (run in background).
   Verify via `%APPDATA%/WinScanLLM/logs/app.log` for `DocumentPipelineWindow shown`. NOTE: a
   background launch has been observed to run full startup then exit cleanly (code 0) — that is not a
   crash; report whether the GUI stayed resident (a `python.exe` ~130MB+) or exited.
5. **Do NOT delete this prompt file** (`docs/PROMPTS/2026-07-30-llm-model-preflight.md`) — its
   retirement is gated on a human review you cannot perform.
6. Report finished (see Reporting).

## 6. Delegation (cost discipline — required)

- Spawn subagents for **mechanical** work with **`model: "haiku"` passed explicitly** (an unset model
  silently inherits this session's expensive model). Dispatch independent lookups in parallel in one
  message. Good candidates here:
  - locating call sites / imports of `ProviderFactory`, `get_reporter`, `save_settings`,
    `_create_default_config`;
  - reading `notification_service.py` and reporting the toast API;
  - reading the existing `_ModelLoaderMixin` and summarizing its reusable methods;
  - drafting test scaffolds/fixtures; cross-checking config keys against code.
- **Keep in the main session** (do not delegate): the readiness-service design, the threading/policy
  gating, the startup wiring, and any adversarial reasoning.
- **Delegation logging** — with
  `pwsh -File C:\Users\erik.OPBTA\.claude\skills\continue-new-session-prompt\scripts\log-delegation-outcome.ps1`:
  - Log every escalation / redo / dropped subagent task with `-Category`, a `-FailureMode`, and one
    line of `-Evidence` — even if you recovered in seconds.
  - **Required final step before reporting finished:** log the totals, one row per category,
    `-Outcome ok -Dispatches N`, each tagged `-PromptPath
    'C:\development\scan_organization\docs\PROMPTS\2026-07-30-llm-model-preflight.md'`. If you
    delegated nothing, you must still record that fact. This tally is the denominator; do not skip it.

## 7. Reporting

Follow the user's output discipline: terse; lead with the action/answer; **end every turn with a
single numbered list of items needing a decision** (nothing that matters lives outside that list).
Verify counts with a tool before stating them; correct any earlier wrong claim in one line and move
on. When you report finished, state: what merged (PR #, merge SHA), test results, whether the app
started and stayed resident, and any open items.

---

**Model note:** this session is pinned to a frontier model on purpose — the hardest task (the
readiness service's threading + policy gating + non-blocking startup wiring) needs it. Delegate the
mechanical lookups above to `haiku` subagents; switch with `/model` only if you have a specific
reason.
