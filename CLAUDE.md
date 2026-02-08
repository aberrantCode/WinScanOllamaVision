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

## Development Rigor (MANDATORY)

**Core Principle:** Code is not complete until it passes type checking and relevant tests.

### Before Making ANY Code Change

1. **Search exhaustively** - Don't assume you found all references
   ```bash
   # Search for the component/variable in multiple ways
   Grep "component_name" -i
   Grep "ComponentName"  # Try different casings
   Grep "def.*component" -i
   Grep "component.*=" -i
   ```

2. **Read before writing** - Always read existing implementations
   - Read the full method before modifying it
   - Read related methods that might interact with it
   - Read the class documentation/docstrings

3. **Understand the full picture** - Map out dependencies
   - Where is this created?
   - Where is this updated?
   - What calls this method?
   - What does this method call?

4. **Verify your solution** - Think through edge cases
   - Will this work when the theme changes?
   - Will this work when the window is resized?
   - Will this work when data is refreshed?
   - Could anything override this change?

### When User Reports Issue Not Fixed

**STOP and search more thoroughly:**
1. Search for the component name in ALL forms (camelCase, snake_case, with/without prefixes)
2. Read the ENTIRE file, don't just jump to specific methods
3. Search for common override patterns: `_update_`, `_refresh_`, `_apply_`, `set_`
4. Look for signal connections that might trigger resets
5. Check parent classes for inherited behavior

**If issue persists after 2 attempts:**
- Explicitly state what you searched for
- List ALL locations you found
- Ask user if they know of other locations you might have missed

### Quality Standards

- **First attempt should be correct** - Take time to search thoroughly upfront
- **Never make assumptions** - Verify by searching the codebase
- **Explicit is better than implicit** - State what you found and what you're changing
- **One fix, all locations** - Update everything consistently

### Validation Before Committing (MANDATORY)

**ALWAYS run these checks before considering any change complete:**

1. **Type Check Modified Files**
   ```bash
   # Run mypy on the specific file you changed
   mypy src/ui/file_details_grid.py --ignore-missing-imports

   # Or check entire module
   mypy src/ui/ --ignore-missing-imports
   ```
   **Why:** Catches method name errors, type mismatches, and attribute errors at development time.

2. **Run Relevant Unit Tests**
   ```bash
   # If you modified a service
   python run_tests.py tests/services/test_analysis_service.py -v

   # If you modified a database class
   python run_tests.py tests/db/test_analysis_db.py -v

   # If you modified UI code, run integration tests
   python run_tests.py tests/integration/ -k "save_metadata"
   ```
   **Why:** Verifies your changes work and don't break existing functionality.

3. **Create Tests for New Functionality**
   ```bash
   # If you add a new method, add a test for it
   # Location: tests/<module>/test_<class_name>.py
   ```
   **Why:** Prevents future regressions and documents expected behavior.

**Example Workflow:**
```bash
# 1. Make code change to src/ui/file_details_grid.py
# 2. Run type checker
mypy src/ui/file_details_grid.py --ignore-missing-imports

# 3. Run related tests
python run_tests.py tests/ui/ -v
python run_tests.py tests/integration/ -k "file_details"

# 4. If tests don't exist, create them first (TDD)
# 5. Only then commit the changes
```

**If you skip these checks, you WILL introduce bugs that could have been caught immediately.**

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

**Pre-Commit Checklist (MANDATORY):**
```powershell
# 1. Type check modified files
mypy src/path/to/modified_file.py --ignore-missing-imports

# 2. Run relevant tests
python run_tests.py tests/path/to/relevant_tests.py -v

# 3. Lint code
ruff check src/

# 4. Format code
ruff format src/

# 5. Run all pre-commit hooks manually (if needed)
pre-commit run --all-files
```

**Quick Commands:**
```powershell
# Type check specific file
mypy src/ui/file_details_grid.py --ignore-missing-imports

# Run tests for specific module
python run_tests.py tests/ui/ -v

# Run tests matching pattern
python run_tests.py tests/ -k "metadata" -v
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
6. **UI code needs tests too** - Even though `src/ui/` shows as "excluded" from coverage, business logic in UI components (like `_save_metadata()`, `_on_metadata_saved()`) MUST have unit tests with mocked dependencies

**Testing UI Business Logic:**
```python
# tests/ui/test_file_details_dialog.py
def test_save_metadata_calls_database(mocker):
    """Test that save metadata calls the correct database methods."""
    mock_analysis_db = mocker.Mock()
    mock_analysis_db.get_analysis.return_value = {"rotation_needed": "90_cw"}

    dialog = FileDetailsDialog(
        file_data={"full_path": "/test.png"},
        analysis_db=mock_analysis_db
    )
    dialog._save_metadata()

    # Verify correct method was called (prevents typos like get_analysis_for_file)
    mock_analysis_db.get_analysis.assert_called_once_with("/test.png")
```

### Test Coverage Status

| Module | Coverage | Status |
|--------|----------|--------|
| `src/config/` | 95%+ | ✓ Complete |
| `src/db/` | 98%+ | ✓ Complete |
| `src/llm_providers/` | 98%+ | ✓ Complete |
| `src/services/` | 0% | ⚠ Needs tests |
| `src/ui/` | Excluded | ⚠ Business logic needs unit tests (mock Qt dependencies) |

**Note:** "Excluded" for UI doesn't mean "no tests needed" - it means coverage tracking is disabled for Qt rendering code. Business logic in UI classes (save handlers, data transformations, validation) MUST still have unit tests with mocked Qt dependencies.

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

## UI Development Methodology (CRITICAL)

When making ANY UI change, follow this mandatory checklist:

### 1. Find ALL Locations Where Component Is Modified
Before changing ANY UI element, search for:
- **Creation methods**: `_create_*()` where the component is initially created
- **Update methods**: `_update_*()`, `_refresh_*()`, `_apply_*()` that may override your changes
- **Theme methods**: `_apply_dark_theme()`, `_apply_light_theme()`, `_update_all_component_styles()`
- **Event handlers**: Methods that recreate or reset the component

**Example searches:**
```python
# If modifying output_filename_input:
Grep "output_filename" -i          # Find all references
Grep "def _update" -i               # Find update methods
Grep "def _apply.*theme" -i         # Find theme methods
Grep "setStyleSheet.*output" -i     # Find where styles are set
```

### 2. Verify Changes in ALL Locations
**NEVER change just one location.** If a component has:
- Initial creation in `_create_foo()`
- Theme updates in `_update_all_component_styles()`
- Both MUST be updated identically

**Checklist:**
- [ ] Changed initial creation method
- [ ] Changed ALL theme/update methods that touch the same component
- [ ] Verified no other methods override the changes
- [ ] Checked for any signal handlers that recreate the component

### 3. Search for Override Patterns
Common patterns that override UI changes:
- `widget.setStyleSheet()` - Overrides previous stylesheet
- `widget.setMinimumHeight()` - Can be reset elsewhere
- `layout.setContentsMargins()` - Can be reset in update methods
- `widget.parent().setStyleSheet()` - Parent styles affect children

**Always search for these patterns** affecting your component.

### 4. Test Your Understanding
Before implementing, answer:
1. Where is this component created?
2. What methods update/refresh it?
3. Are there theme switching methods that affect it?
4. Could anything recreate or override this component?

**If you can't answer all 4, search more thoroughly.**

### 5. Document What You Find
When you find multiple locations, **explicitly state them** in your response:
```
I found this component is modified in 3 places:
1. _create_foo() at line 500 - initial creation
2. _update_all_component_styles() at line 3200 - theme updates
3. _refresh_display() at line 1800 - refreshes on data change

I will update ALL THREE locations.
```

## Common Pitfalls

1. **Don't import from root-level compatibility shims in new code** - Use package imports (`from config.config_manager import ConfigManager`)

2. **Don't hardcode prompts** - Use configuration or service defaults

3. **Don't forget to mock subprocess calls in tests** - Real CLI tools shouldn't be invoked during testing

4. **Don't assume JSON responses are clean** - Always use the robust parsing from `ollama_service.py` patterns

5. **Remember file placement rules** - Tests go in `/tests`, not root. Source code goes in `/src`, not root.

6. **NEVER make UI changes in only one location** - Always search for and update ALL locations where the component is created, styled, or modified (especially theme update methods)

7. **Always search for override patterns** - Methods like `_update_all_component_styles()`, `_apply_theme()`, `_refresh_*()` commonly override initial settings
