<!-- GitHub Copilot / AI agent instructions for WinScanLLM -->
# WinScanLLM — Quick AI Agent Guide

Purpose: Help AI coding agents be immediately productive in this repository by describing the architecture, developer workflows, integration points, and code patterns actually used in the codebase.

1) Big picture
- UI (desktop): `src/gui.py` is the PyQt6 entry for the app UI; `src/main.py` composes services and shows the `StartupWindow`.
- Services: Core business logic lives in service classes under `src/` — notably `AnalysisService` (`src/analysis_service.py`), `BundlingService` and `FileProcessor` (`src/file_processor.py`).
- Datastores: `AnalysisDB` and `MetadataDB` (see `src/analysis_db.py`, `src/metadata_db.py`) hold cached analysis, runs and metadata.
- LLM Providers: Provider implementations are under `src/llm_providers` and selected via `ProviderFactory.create_from_config_manager(...)`. `OllamaService` (`src/ollama_service.py`) is the primary provider wrapper.

2) Primary responsibilities & data flow (short)
- `FileProcessor` groups scanned images by timestamp, converts TIFF→PNG, and builds searchable PDFs.
- `AnalysisService` orchestrates page-level analysis: it collects files, uses the provider (`provider.analyze_images(...)`) and writes results to `AnalysisDB` and `MetadataDB`.
- The GUI triggers `AnalysisService` via threads/workers (see `OllamaWorker` in `src/gui.py`) and displays results for manual confirmation.

3) Important developer workflows
- Run GUI (dev): `python src/gui.py` (or `python src/main.py` to run full startup routine).
- Run tests: `python -m unittest discover tests` (from repo root). Use individual tests for focused debugging (e.g. `tests/test_file_processor.py`).
- Ollama model: The app expects a local Ollama server. Pull the default vision model used in config (default `qwen2.5-vl`):
  ```powershell
  ollama pull qwen2.5-vl
  ```
- Settings: `ConfigManager` persists settings to an INI file. In normal runs the file is in AppData (see `ConfigManager`), but a repo-local `settings.ini` is used in some dev/test helpers — check how tests create temp configs.

4) Project-specific conventions & patterns
- Config access: Always use `ConfigManager.get_setting(section, key, default)` / `get_bool` / `get_int`. Avoid hard-coding paths; prefer `ConfigManager` helpers like `get_directories()`.
- Provider interface: Providers must implement `analyze_images(image_paths: List[str], prompt: str) -> Dict` and expose a `provider_name` and `model_used` in returned results. `AnalysisService` expects `result['success']`, `result['metadata']`, `result['response']`, and `result['processing_time_ms']`.
- Strict JSON responses: Several prompts instruct LLMs to respond with ONLY valid JSON (see `OllamaService.extract_document_info` and `validate_grouping_with_page_number`). When changing prompts or provider code, preserve that requirement or update the callers' parsing logic.
- Error handling: Services commonly return dictionaries with `success`, `error`, `cached`, etc. Use that shape when integrating new code so callers can consistently update stats.

4.1) Repository file-placement rules (must-follow)
- New source code files: place under the `src/` directory. Avoid creating new top-level `.py` files in the repo root.
- New unit tests: place under the `tests/` directory and follow the existing naming convention (`test_*.py`). Tests should import project modules via the `src` package layout used in existing tests.
- Documentation (Markdown): place under `docs/` or `docs/<area>/`. Prefer `docs/` for user-facing guides and `docs/architecture` for design notes.
- Assets and test data: images and sample data go in `assets/` or `data/` respectively.
- Helper scripts: put one-off scripts in `scripts/` and keep them small; don't drop helpers at repo root.

Rationale: this repository treats the root as a small orchestration area (README, requirements, top-level config). Keeping new files in the appropriate subfolders preserves import paths, test discovery, and CI assumptions.

5) Integration & external dependencies
- Ollama: `src/ollama_service.py` uses the Ollama Python SDK and `httpx` for timeouts. Tests may mock provider behavior rather than contacting the real service.
- CLI providers: `ConfigManager` includes `ClaudeCLI` / `GeminiCLI` templates — these use `command_template` strings and expect agent code that spawns a subprocess and captures stdout/stderr.

6) Files to check when making changes (examples)
- App startup: [src/main.py](src/main.py)
- UI entry and widgets: [src/gui.py](src/gui.py)
- Analysis orchestration: [src/analysis_service.py](src/analysis_service.py)
- Ollama integration: [src/ollama_service.py](src/ollama_service.py)
- File grouping / PDF creation: [src/file_processor.py](src/file_processor.py)
- Config & provider selection: [src/config_manager.py](src/config_manager.py)
- Tests: [tests](tests/) — run with `python -m unittest discover tests`.

7) Small examples & gotchas for agents
- When implementing a new LLM provider, add it under `src/llm_providers/` and register it in `ProviderFactory`. Ensure your provider returns the same keys `AnalysisService` expects.
- When modifying prompts used for metadata extraction or grouping, do not remove the JSON-only instruction unless you update the JSON-cleaning logic in `src/ollama_service.py` and `src/analysis_service.py`.
- `ConfigManager` loads defaults if no config exists; tests sometimes create temporary `settings.ini` files — prefer using the API over editing INI files directly.

8) Editing & testing checklist for PRs
- Update or add unit tests under `tests/` for any behavioral change.
- Run `python -m unittest discover tests` before pushing.
- If you change provider prompts or parsing, add unit tests that simulate provider responses (include malformed JSON cases).

If anything here is unclear or you'd like more detail in a specific area (provider interface, DB schema, or GUI thread handling), tell me which area to expand and I will iterate.
