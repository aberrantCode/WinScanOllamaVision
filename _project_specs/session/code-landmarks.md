<!--
UPDATE WHEN:
- Adding new entry points or key files
- Introducing new patterns
- Discovering non-obvious behavior

Helps quickly navigate the codebase when resuming work.
-->

# Code Landmarks

Quick reference to important parts of the codebase.

## Entry Points

| Location | Purpose |
|----------|---------|
| `src/main.py` | Main application entry point, PyQt6 GUI startup |

## Core Business Logic

| Location | Purpose |
|----------|---------|
| `src/services/analysis_service.py` | Orchestrates LLM-based document analysis |
| `src/llm_providers/provider_factory.py` | Creates LLM provider instances |
| `src/llm_providers/base_provider.py` | Abstract base class for all providers |

## Configuration

| Location | Purpose |
|----------|---------|
| `src/config/config_manager.py` | INI-based configuration management |
| `src/config/appdata_manager.py` | AppData directory handling |
| `%APPDATA%/WinScanLLM/settings.ini` | User settings (runtime location) |

## Key Patterns

| Pattern | Example Location | Notes |
|---------|------------------|-------|
| Provider Pattern | `src/llm_providers/` | BaseLLMProvider → Ollama/Claude/Gemini |
| Singleton Logger | `src/services/logging_service.py` | get_logger() returns shared instance |
| Qt Mixins | `src/ui/bundle_workflow_handlers.py` | UI event handler mixin |
| Hash-based caching | `src/db/analysis_db.py`, `src/db/metadata_db.py` | SHA-256 file hashing for incremental processing |

## Testing

| Location | Purpose |
|----------|---------|
| `tests/` | Test files mirroring `src/` structure |
| `tests/llm_providers/` | Provider tests with mocked subprocess calls |
| `tests/helpers/run_all_tests.py` | Custom test runner |

## Gotchas & Non-Obvious Behavior

| Location | Issue | Notes |
|----------|-------|-------|
| `src/llm_providers/ollama_service.py` | JSON parsing | Robust parsing handles markdown fences, extra text, malformed JSON |
| Database files | Not in repo | Stored in `%APPDATA%/WinScanLLM/`, blank template in `/data` |
| Import paths | No relative imports | Must use full package paths: `from config.config_manager import ConfigManager` |
| Provider responses | Standardized dict | All providers return `{success, response, metadata, processing_time_ms, model_used, provider_name, error}` |
