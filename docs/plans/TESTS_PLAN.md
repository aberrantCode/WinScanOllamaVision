**Tests Reorganization Plan**

- **Goal**: Organize the `tests/` tree so it mirrors the functional subpackages under `src/` and identify missing tests to reach reasonable coverage.

1) New test subfolders (created):
- `tests/config` — config-related tests (e.g. `ConfigManager`).
- `tests/db` — database tests (`AnalysisDB`, `MetadataDB`, field-history, migrations).
- `tests/services` — core services tests (`AnalysisService`, `FileProcessor`, `BundlingService`).
- `tests/llm_providers` — provider tests (Ollama, Claude/Gemini CLI wrappers).
- `tests/gui` — UI/widget/window tests.
- `tests/integration` — long-running integration and end-to-end tests.
- `tests/prompt` — prompt optimization + prompt-related integration tests.
- `tests/helpers` — test helpers, runners, and small utilities.

2) Files to move (existing test files that should be relocated):
- `tests/test_config_manager.py` -> `tests/config/test_config_manager.py`
- `tests/test_analysis_db_edge_cases.py` -> `tests/db/test_analysis_db_edge_cases.py`
- `tests/test_analysis_db_queries.py` -> `tests/db/test_analysis_db_queries.py`
- `tests/test_analysis_status_db.py` -> `tests/db/test_analysis_status_db.py`
- `tests/test_phase1_database.py` -> `tests/db/test_phase1_database.py`
- `tests/test_field_history_database.py` -> `tests/db/test_field_history_database.py`
- `tests/test_file_processor.py` -> `tests/services/test_file_processor.py`
- `tests/test_phase3_services.py` -> `tests/services/test_phase3_services.py`
- `tests/test_phase3_integration.py` -> `tests/services/test_phase3_integration.py`
- `tests/test_phase7_bundling.py` -> `tests/services/test_bundling.py`
- `tests/test_ollama_service.py` -> `tests/llm_providers/test_ollama_service.py`
- `tests/test_phase2_providers.py` -> `tests/llm_providers/test_phase2_providers.py`
- `tests/test_analysis_status_window.py` -> `tests/gui/test_analysis_status_window.py`
- `tests/test_analysis_status_window_integration.py` -> `tests/gui/test_analysis_status_window_integration.py`
- `tests/test_enhanced_startup_window.py` -> `tests/gui/test_enhanced_startup_window.py`
- `tests/test_bundle_workflow.py` -> `tests/gui/test_bundle_workflow.py`
- `tests/test_collection_status_tab.py` -> `tests/gui/test_collection_status_tab.py`
- `tests/test_file_details_grid.py` -> `tests/gui/test_file_details_grid.py`
- `tests/test_image_gallery.py` -> `tests/gui/test_image_gallery.py`
- `tests/test_keyboard_shortcuts.py` -> `tests/gui/test_keyboard_shortcuts.py`
- `tests/test_metadata_display_widget.py` -> `tests/gui/test_metadata_display_widget.py`
- `tests/test_duplicate_detection.py` -> `tests/gui/test_duplicate_detection.py`
- `tests/test_phase10_integration.py` -> `tests/integration/test_phase10_integration.py`
- `tests/test_prompt_optimization.py` -> `tests/prompt/test_prompt_optimization.py`
- `tests/test_prompt_optimization_integration.py` -> `tests/prompt/test_prompt_optimization_integration.py`
- `tests/test_no_unicode.py` -> `tests/helpers/test_no_unicode.py`
- `tests/run_all_tests.py` -> `tests/helpers/run_all_tests.py`
- `tests/simple_test_runner.py` -> `tests/helpers/simple_test_runner.py`

3) Candidate deletions (legacy or duplicate tests):
- If after inspection any tests are found to be duplicate or not meaningful with the refactor, delete them. No deletions have been applied automatically — this requires manual review.

4) Missing tests to add (priority list)
These are concrete tests that should be added to reach reasonable coverage across the refactor. Create these under the matching test subfolders.

- `tests/config/test_config_manager_edge_cases.py`
  - Validate INI defaults, concurrent writes, missing file behavior, boolean/int parsing edge-cases.

- `tests/db/test_migrations_and_schema.py`
  - Explicit tests that exercise schema migrations across versions (Phase 8+).

- `tests/db/test_metadata_db_concurrency.py`
  - Concurrency tests for `MetadataDB` read/write under parallel threads.

- `tests/services/test_analysis_service_workflow.py`
  - Unit tests for `AnalysisService.scan_all_directories`, including abort, incremental caching, and provider switch behaviors.

- `tests/services/test_file_processor_io_and_pdf.py`
  - More robust tests for TIFF→PNG conversion, rotation map behavior, and searchable PDF creation with mocked PyMuPDF.

- `tests/services/test_bundling_service_edgecases.py`
  - Tests for bundle suggestions, acceptance/rejection workflows and persistence.

- `tests/llm_providers/test_claude_cli_provider.py`
  - CLI provider tests with `subprocess.run` mocked for well-formed and malformed JSON outputs.

- `tests/llm_providers/test_gemini_cli_provider.py`
  - Same as Claude provider.

- `tests/llm_providers/test_provider_factory_integration.py`
  - Ensure `ProviderFactory` returns correct provider instances given config and that provider contracts are honoured.

- `tests/gui/test_settings_window_signals_and_prompt_optimization.py`
  - Tests for `PromptOptimizationThread` signals, `EnhancedSettingsWindow` prompt editors, and provider selection interactions (use Qt test harness / QTest or headless approach).

- `tests/gui/test_analysis_status_window_flow.py`
  - Validate analysis start/stop, progress updates, cancelled state, and result display (use mocks for `AnalysisService`).

- `tests/integration/test_end_to_end_scan_and_bundle.py`
  - High-level integration test: create temp images, run `AnalysisService` end-to-end with a mocked provider, and assert bundles persisted.

5) Next steps (recommended):
- Move tests into the new folders (I created placeholders). I can perform file moves and commits if you want — I held off automating mass `git mv` earlier to avoid interrupting your branch state.
- Add the missing tests incrementally starting from provider and service unit tests, then GUI/integration tests.
- Run CI (or `python -m unittest discover tests`) after each batch to keep failures small and fixable.

If you want, I will now:
- (A) Move all tests into the subfolders and commit the changes, or
- (B) Move a small batch (config, db, llm_providers, services) and run tests to iterate.

Pick A or B and I'll proceed.
