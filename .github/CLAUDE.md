<!-- Claude-specific instructions for AI agents working on WinScanLLM -->
# Claude Provider — Agent Guide (WinScanLLM)

Purpose: Provide actionable, Claude-focused guidance for implementing and testing `claude` CLI-style providers in this repository.

1) Where Claude fits
- The codebase supports multiple provider types. Claude CLI integrations live conceptually under `src/llm_providers/` and are selected via `ProviderFactory.create_from_config_manager(...)`.
- Use `ConfigManager`'s `ClaudeCLI` section to read command templates and timeouts (see `src/config_manager.py`).

2) Implementation expectations
- Provider contract: match the same shape as other providers used by `AnalysisService` — implement `analyze_images(image_paths: List[str], prompt: str) -> Dict` and provide `provider_name` and `model_used` in the returned dict. Include keys: `success`, `metadata`, `response`, `processing_time_ms`.
- CLI execution: the Claude provider should build a command using `ConfigManager.get_provider_config('claude_cli')['command_template']`, substitute `%%MODEL%%`, `%%IMAGE_PATHS%%`, and `%%PROMPT%%`, then run it capturing stdout/stderr (use `subprocess.run([...], capture_output=True, text=True, timeout=...)`).
- JSON-only responses: Prompts used for metadata extraction and validation must ask Claude to return ONLY valid JSON. The app's parsing code (see `src/ollama_service.py` for JSON-cleaning examples) expects and attempts to clean JSON — write providers/tests to handle malformed outputs.

3) Testing & mocking
- Unit tests should NOT call the real Claude CLI. Mock the subprocess call to return predictable stdout/stderr payloads. Cover both well-formed JSON responses and malformed cases (extra text, markdown code fences).
- Add tests under `tests/test_phase2_providers.py`-style files and follow existing patterns for provider tests (see `tests/test_ollama_service.py`).

4) Config & examples
- `src/config_manager.py` includes a `ClaudeCLI` default template:
  `claude --model %%MODEL%% --image %%IMAGE_PATHS%% --prompt %%PROMPT%%`
- Example behavior: when invoked, the provider should:
  - Replace `%%IMAGE_PATHS%%` with a space-joined list of image file paths.
  - Pass the prompt via a safe mechanism (stdin or a temporary file) if the CLI supports it to avoid shell-escaping issues.

5) Integration tips
- Keep CLI parsing robust: guard against partial JSON and include fallback heuristics similar to `OllamaService.extract_document_info` (strip fences, find the first/last braces, regex key extraction).
- Respect `timeout` from `ConfigManager.get_provider_config('claude_cli')['timeout']` to avoid hanging tests or UI blocking threads.

6) File placement
- Implement provider code in `src/llm_providers/claude_cli_provider.py` and register it in `src/llm_providers/provider_factory.py`.

If you'd like, I can scaffold a `claude_cli_provider.py` implementation and unit tests (with subprocess mocks) following these guidelines—should I proceed?
