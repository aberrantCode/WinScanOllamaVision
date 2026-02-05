# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Skills

Read and follow these skills before writing any code:
- `.claude/skills/base/SKILL.md` - Universal coding patterns, TDD workflow, atomic todos
- `.claude/skills/security/SKILL.md` - Security best practices and OWASP patterns
- `.claude/skills/python/SKILL.md` - Python development with ruff, mypy, pytest
- `.claude/skills/llm-patterns/SKILL.md` - AI-first application patterns and LLM testing
- `.claude/skills/session-management/SKILL.md` - Context preservation and state tracking
- `.claude/skills/project-tooling/SKILL.md` - CLI tooling (gh, vercel, supabase)

## Project Overview

**WinScanLLM** - A PyQt6 desktop application for document scanning and analysis using multiple LLM providers (Ollama, Claude CLI, Gemini CLI). The application provides automatic document metadata extraction, batch processing, and intelligent file organization.

**Goals:**
- Multi-provider LLM integration with unified interface
- Robust error handling and incremental processing
- Local-first with AppData storage (databases, logs, settings)
- Clean architecture with testable components

## Atomic Todos

All work is tracked in `_project_specs/todos/`:
- `active.md` - Current work
- `backlog.md` - Future work
- `completed.md` - Done (for reference)

Every todo must have validation criteria and test cases. See `.claude/skills/base/SKILL.md` for format.

## Session Management

Maintain session state in `_project_specs/session/`:
- `current-state.md` - Live session state (update every 15-20 tool calls)
- `decisions.md` - Key architectural/implementation decisions (append-only)
- `code-landmarks.md` - Important code locations for quick reference
- `archive/` - Past session summaries

See `.claude/skills/session-management/SKILL.md` for details.

## File Organization (CRITICAL)

**NEVER place new files in the repository root unless absolutely necessary.**

Follow these strict placement rules:

- **Tests** → `/tests` (with subfolder structure mirroring `/src`)
- **Source code** → `/src` (with package structure as described below)
- **Scripts & utilities** → `/scripts`
- **Markdown documentation** → `/docs`
- **Images & assets** → `/assets`
- **Databases & import datasets** → `/data`

## Essential Commands

### Running the Application
```powershell
python src/main.py
```

### Running Tests

**Test Framework:** This project uses **pytest** (not unittest) for all tests.

```powershell
# Run all tests with coverage (recommended)
python run_tests.py tests/

# Run specific test module
python run_tests.py tests/config/

# Run specific test file
python run_tests.py tests/config/test_config_manager.py

# Run tests matching pattern
python run_tests.py tests/ -k "provider"

# Run tests with verbose output
python run_tests.py tests/ -v

# Run core tests only (config, db, llm_providers)
python run_tests.py tests/ --ignore=tests/gui --ignore=tests/integration --ignore=tests/services --ignore=tests/prompt
```

**Note:** The `run_tests.py` script ensures `src/` is in the Python path for correct imports.

### Development Setup
```powershell
# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Install pre-commit hooks (run once after clone)
pre-commit install
pre-commit install --hook-type commit-msg

# Verify tooling
.\scripts\verify-tooling.ps1

# Run security checks
.\scripts\security-check.ps1
```

### Code Quality
```powershell
# Lint code
ruff check src/

# Format code
ruff format src/

# Type check
mypy src/ --ignore-missing-imports

# Run all pre-commit hooks manually
pre-commit run --all-files
```

## Architecture Overview

### Package Structure

The codebase follows a clean package-based structure with **NO compatibility shims**:

```
src/
├── main.py              # Application entry point (ONLY file in root)
├── config/              # Configuration management
│   ├── config_manager.py
│   └── appdata_manager.py
├── db/                  # Database layer
│   ├── analysis_db.py
│   └── metadata_db.py
├── services/            # Business logic and orchestration
│   ├── analysis_service.py
│   ├── file_service.py
│   ├── bundling_service.py
│   └── logging_service.py
├── ui/                  # User interface components
│   ├── gui.py
│   ├── analysis_status_window.py
│   ├── bundle_widgets.py
│   ├── bundle_workflow_handlers.py  # UI event handler mixin
│   ├── file_details_grid.py
│   ├── settings_window_enhanced.py
│   ├── collection_status_helpers.py
│   ├── style.py
│   ├── styles.py
│   └── style.qss
└── llm_providers/       # LLM provider implementations
    ├── base_provider.py
    ├── provider_factory.py
    ├── ollama_provider.py
    ├── ollama_service.py
    ├── claude_cli_provider.py
    ├── gemini_cli_provider.py
    └── command_builder.py
```

**Import Rules:**
- All imports MUST use full package paths (e.g., `from ui.gui import StartupWindow`)
- No relative imports outside of package boundaries
- No backward-compatibility shims exist in the root

### Key Architectural Patterns

#### 1. Provider Pattern for LLM Integration
All LLM providers inherit from `BaseLLMProvider` and implement:
- `analyze_images(image_paths, prompt, model) -> Dict`
- `get_available_models() -> List[str]`
- `test_connection() -> bool`

**Provider contract returns:**
```python
{
    'success': bool,
    'response': str,           # Full LLM response text
    'metadata': dict,          # Extracted metadata
    'processing_time_ms': int,
    'model_used': str,
    'provider_name': str,
    'error': str               # Only if success=False
}
```

Create providers via `ProviderFactory.create_from_config_manager(config_manager)`.

#### 2. Configuration Management
`ConfigManager` (in `src/config/config_manager.py`) manages all settings via INI file:
- Defaults to `%APPDATA%/WinScanLLM/settings.ini`
- Provides type-safe getters: `get_bool()`, `get_int()`, `get_directories()`
- Provider-specific config via `get_provider_config(provider_name)`

**Key configuration sections:**
- `LLMProvider` - Active provider selection
- `Ollama`, `ClaudeCLI`, `GeminiCLI` - Provider-specific settings
- `AutoAnalysis` - Startup analysis behavior
- `SourceDirectories` - Scan folder configuration (JSON array)
- `OutputDirectory` - Output strategy settings

#### 3. Analysis Service Architecture
`AnalysisService` orchestrates automatic document analysis:
- Scans configured directories for images (PNG, JPG, JPEG)
- Uses incremental analysis (cache-aware via file hashing)
- Saves results to both `AnalysisDB` and `MetadataDB`
- Provides progress callbacks and abort checking
- Tracks analysis runs with statistics (analyzed, cached, errors, skipped)

**Key method:** `scan_all_directories(progress_callback, incremental, abort_check)`

#### 4. Database Layer
Two separate databases:
- **AnalysisDB** (`db/analysis_db.py`) - Page analysis results, cache, and run tracking
- **MetadataDB** (`db/metadata_db.py`) - Document metadata and field history

Both use SQLite and include file hash-based caching.

**IMPORTANT:** Database files are stored in the user's AppData directory (`%APPDATA%/WinScanLLM/`), NOT in the source directory. A blank template exists in `/data` for initialization.

#### 5. Logging Service
Centralized logging using Python's standard `logging` module:
- **Singleton pattern** - One logger instance across the application
- **Location:** Logs stored in `%APPDATA%/WinScanLLM/logs/app.log`
- **Rotating file handler** - 10MB max file size, 5 backups retained
- **Level-based logging** - DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Formatted output** - Timestamps, module names, and log levels

**Usage:**
```python
from services.logging_service import get_logger

logger = get_logger()
logger.info("Application started")
logger.error("Error occurred", exc_info=True)  # Includes traceback
```

**DO NOT:**
- Write directly to log files using `open()`
- Use `print()` statements for logging (except debug during development)
- Store log files in the source directory

### Multi-Provider Support

The application supports three LLM provider types:

1. **Ollama** - Local Ollama server via HTTP API
   - Default model: `qwen2.5-vl`
   - Base URL: `http://localhost:11434`

2. **Claude CLI** - Claude CLI command execution via subprocess
   - Uses command template with `%%MODEL%%`, `%%IMAGE_PATHS%%`, `%%PROMPT%%` placeholders
   - Default models: `claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022`

3. **Gemini CLI** - Gemini CLI command execution via subprocess
   - Similar template-based approach
   - Default models: `gemini-2.0-flash-exp`, `gemini-1.5-pro`

### JSON Response Handling

**CRITICAL:** All prompts used for metadata extraction must request JSON-only responses. Providers include robust parsing that handles:
- Markdown code fences (```json ... ```)
- Extra text before/after JSON
- Malformed JSON (fallback regex extraction)

See `src/llm_providers/ollama_service.py` for JSON-cleaning examples.

## Test Organization

Tests mirror the `src/` package structure:

```
tests/
├── config/              # ConfigManager tests
├── db/                  # Database layer tests
├── gui/                 # UI component tests
├── llm_providers/       # Provider implementation tests
├── services/            # Service layer tests
├── integration/         # End-to-end integration tests
├── prompt/              # Prompt optimization tests
└── helpers/             # Test utilities
```

### Testing Guidelines

1. **Provider tests MUST mock subprocess calls** - Never call real CLI tools
2. **Use pytest framework** - All tests use pytest fixtures and assertions
3. **Test both success and failure cases** - Including malformed JSON responses
4. **Follow existing patterns** - See `tests/llm_providers/test_claude_cli_provider.py`
5. **Minimum 80% coverage required** - Use `python run_tests.py tests/` to check

### Test Coverage Status

| Module | Coverage | Status |
|--------|----------|--------|
| `src/config/` | 95%+ | ✓ Complete |
| `src/db/` | 98%+ | ✓ Complete |
| `src/llm_providers/` | 98%+ | ✓ Complete |
| `src/services/` | 0% | ⚠ Needs tests |
| `src/ui/` | Excluded | GUI (separate testing) |

## Development Workflow

### Adding a New LLM Provider

1. Create provider class in `src/llm_providers/` inheriting from `BaseLLMProvider`
2. Implement required methods: `analyze_images()`, `get_available_models()`, `test_connection()`
3. Register in `ProviderFactory.PROVIDER_CLASSES` dict
4. Add default config section to `ConfigManager._create_default_config()`
5. Create unit tests in `tests/llm_providers/` with mocked subprocess calls

### Working with Configuration

```python
from config.config_manager import ConfigManager

config = ConfigManager()

# Get provider config
provider_config = config.get_provider_config('claude_cli')

# Get typed values
enabled = config.get_bool('AutoAnalysis', 'enabled', default=True)
batch_size = config.get_int('AutoAnalysis', 'batch_size', default=10)

# Manage directories
directories = config.get_directories()
config.add_directory('/path/to/new/dir')
```

### Analysis Service Integration

```python
from services.analysis_service import AnalysisService
from config.config_manager import ConfigManager
from analysis_db import AnalysisDB
from metadata_db import MetadataDB

# Initialize
config = ConfigManager()
analysis_db = AnalysisDB()
metadata_db = MetadataDB()
service = AnalysisService(config, analysis_db, metadata_db)

# Run analysis with progress callback
def progress_callback(status_text, current, total):
    print(f"[{current}/{total}] {status_text}")

stats = service.scan_all_directories(
    progress_callback=progress_callback,
    incremental=True  # Use cache
)
```

## Important Implementation Notes

### Prompt Engineering
- Use `AnalysisService.DEFAULT_ANALYSIS_PROMPT` constant for standard analysis
- Custom prompts can be set via `ConfigManager.get_setting('Prompts', 'document_metadata')`
- Always instruct LLMs to return **valid JSON only** to avoid parsing issues

### Error Handling
- Providers return structured error info in response dict (`success=False`, `error` field)
- `AnalysisService` saves errors to database via `save_analysis_error()`
- Long-running operations support abort checking via callback

### File Hashing
- `MetadataDB.compute_file_hash()` uses SHA-256 for cache validation
- Hash stored alongside analysis results for incremental updates

### Threading Considerations
- GUI components use Qt threading
- Analysis operations provide progress callbacks for UI updates
- Abort checking enables graceful cancellation

## Common Pitfalls

1. **Don't import from root-level compatibility shims in new code** - Use package imports (`from config.config_manager import ConfigManager`)

2. **Don't hardcode prompts** - Use configuration or service defaults

3. **Don't forget to mock subprocess calls in tests** - Real CLI tools shouldn't be invoked during testing

4. **Don't assume JSON responses are clean** - Always use the robust parsing from `ollama_service.py` patterns

5. **Remember file placement rules** - Tests go in `/tests`, not root. Source code goes in `/src`, not root.
