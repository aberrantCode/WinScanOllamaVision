# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WinScanLLM is a Python/PyQt6 desktop application for intelligently organizing scanned documents using AI-powered analysis. It supports multiple LLM providers (Ollama, Claude CLI, Gemini CLI), automatically groups scanned pages into documents, extracts metadata via vision models, and creates organized, searchable PDFs.

**Repository:** https://github.com/aberrantCode/WinScanLLM.git

## Essential Commands

### Setup & Installation
```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment (PowerShell)
.\venv\Scripts\Activate.ps1

# Activate virtual environment (cmd.exe)
.\venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```powershell
# Main entry point
python src/main.py

# Alternative: Direct GUI launch
python src/gui.py
```

### Testing
```powershell
# Run all tests
python -m unittest discover tests

# Run specific test file
python -m unittest tests.test_config_manager
python -m unittest tests.test_file_processor
python -m unittest tests.test_ollama_service

# Run with verbose output
python -m unittest discover tests -v
```

### Development Tools
```powershell
# Check for TIFFs that need conversion
ls "C:\Users\<username>\Pictures\Scans" | Where-Object { $_.Extension -match "\.tiff?$" }

# View application logs
Get-Content app.log -Tail 50

# Clear logs
Remove-Item app.log
```

## Architecture Overview

### Multi-Window GUI Architecture

The application uses a multi-window PyQt6 architecture with three main windows:

1. **StartupWindow** (`src/gui.py`)
   - Entry point with 4 main buttons
   - Non-blocking analysis banner with real-time progress
   - Scanner GIF animation (controlled by analysis state)
   - Clickable scanner stats widget (opens AnalysisStatusWindow)

2. **ConvertImagesWindow** (`src/gui.py`)
   - Multi-step document bundling workflow
   - Workflow steps: BUNDLE_SUGGESTIONS → STITCHING → ANALYSIS → ORDERING → FINALIZATION
   - Full keyboard navigation support (see docs/keyboard_shortcuts_reference.md)
   - Thumbnail gallery + center preview split view

3. **ConvertPDFsWindow** (`src/gui.py`)
   - PDF import and re-analysis workflow
   - Extracts pages from existing PDFs
   - Routes pages back through analysis pipeline

### LLM Provider System

**Plugin Architecture** (`src/llm_providers/`):
- **BaseLLMProvider** (abstract): Defines interface for all providers
- **OllamaProvider**: Local Ollama server integration (HTTP API)
- **ClaudeCliProvider**: Claude Code CLI integration via subprocess
- **GeminiCliProvider**: Google Gemini CLI integration via subprocess
- **ProviderFactory**: Creates provider instances from config

All providers implement:
- `analyze_images(image_paths, prompt, model)` → metadata extraction
- `get_available_models()` → list models
- `test_connection()` → validate provider availability

**Command Building** (`src/llm_providers/command_builder.py`):
- Templated command construction for CLI-based providers
- Variable substitution: `%%MODEL%%`, `%%IMAGE_PATHS%%`, `%%PROMPT%%`
- Handles shell escaping and path formatting

### Analysis & Caching System

**AnalysisService** (`src/analysis_service.py`):
- Orchestrates automatic startup analysis of all scan directories
- Incremental analysis: skips already-cached files (file hash + mtime based)
- Progress callbacks for real-time UI updates
- Supports cancellation mid-analysis

**AnalysisDB** (`src/analysis_db.py`):
- SQLite database for analysis results cache
- Stores: file paths, hashes, mtimes, analysis results, timestamps
- Tracks analysis runs for statistics and history
- Manages source directories (active/inactive state)

**MetadataDB** (`src/metadata_db.py`):
- SQLite database for document metadata
- Two tables: `active_metadata` (current processing) and `archive_metadata` (completed)
- Caches LLM extraction results: company, document_type, document_date, page numbers
- Field history tracking for autocomplete suggestions

### Bundling System

**BundlingService** (`src/bundling_service.py`):
- Generates intelligent document bundling recommendations
- Two grouping strategies:
  1. Explicit page numbers: Groups files marked as "page X of Y"
  2. Metadata clustering: Groups by company + document_type + date proximity
- Confidence scoring based on:
  - Page number continuity
  - Metadata consistency
  - Temporal proximity (file mtimes)

**BundleSuggestionsView** (`src/bundle_widgets.py`):
- UI for reviewing AI-generated bundle suggestions
- Card-based layout with preview thumbnails
- Actions: Accept (auto-finalize), Modify (enter stitching workflow), Reject (exclude)
- Confidence indicators (High/Medium/Low)

### File Processing Pipeline

**FileProcessor** (`src/file_processor.py`):
- TIFF → PNG conversion (auto-deletes original TIFF)
- Timestamp-based file grouping (within N seconds = same document)
- PDF generation from image sequences
- OCR integration via PyMuPDF for searchable PDFs
- File move/rename operations with collision handling

### Configuration System

**ConfigManager** (`src/config_manager.py`):
- INI-based configuration (stores in AppData/Roaming/WinScanLLM)
- Sections: `[LLMProvider]`, `[Ollama]`, `[ClaudeCLI]`, `[GeminiCLI]`, `[DocumentProcessing]`, `[AutoAnalysis]`, `[GUI]`
- Dynamic section creation for new providers
- Active provider selection + per-provider model configuration

**AppData Structure**:
```
%APPDATA%\WinScanLLM\
├── settings.ini         # Configuration
├── metadata.db         # Document metadata cache
└── analysis_cache.db   # Analysis results cache
```

### UI Components & Styling

**Styles Module** (`src/styles.py`):
- Standardized modal dialogs: `show_information()`, `show_warning()`, `show_critical()`, `show_question()`
- Consistent color scheme and typography
- Themed message boxes with custom icons

**ProgressBannerWidget** (`src/gui.py`):
- Non-modal progress indicator at top of StartupWindow
- Expandable details panel (current file, elapsed time, success/failure counts)
- Auto-dismisses on completion (5s delay)

**AnalysisStatusWindow** (`src/analysis_status_window.py`):
- Detailed analysis history viewer
- Run-by-run statistics and logs
- File-level error inspection

## Key Workflows

### Startup Flow
1. `src/main.py` initializes AppData directory
2. Creates StartupWindow (visible immediately)
3. Spawns AnalysisWorker thread (QThread) to run startup analysis
4. ProgressBannerWidget shows real-time progress (non-blocking)
5. Scanner GIF animates during analysis, stops when idle
6. User can click any of 4 main buttons while analysis runs

### Document Conversion Flow
1. **Bundle Suggestions** (Step 0):
   - Load AI-generated bundles from BundlingService
   - User accepts/modifies/rejects each bundle
   - Accepted bundles skip manual stitching → go to finalization

2. **Stitching** (Step 1):
   - Manual page selection from gallery
   - Space = include, Delete = exclude
   - Approve bundle → move to analysis

3. **Analysis** (Step 2):
   - LLM extracts metadata from selected pages
   - Shows extracted company, document_type, document_date
   - User can edit/override suggestions

4. **Ordering** (Step 3):
   - Drag-and-drop page reordering
   - Arrow keys to reorder selected pages
   - Approve order → move to finalization

5. **Finalization** (Step 4):
   - Review final bundle configuration
   - Customize filename template
   - Create PDF button → generates searchable PDF
   - Final confirmation dialog with 3 options:
     - Accept & Delete Source Files
     - Accept & Keep Source Files
     - Reject & Delete PDF

### Configuration Changes
- Changes to `settings.ini` require app restart to take effect
- Provider changes trigger re-validation on next analysis
- Model selection persists per provider

## Important Implementation Details

### Thread Safety
- Analysis runs in QThread worker (AnalysisWorker)
- Use `pyqtSignal` for worker → UI communication
- Never update GUI directly from worker thread
- All file operations must be thread-safe (SQLite handles this)

### Database Schema Migrations
- MetadataDB and AnalysisDB auto-create tables on init
- Schema version tracking in `schema_version` table
- No automatic migrations yet - handle schema changes manually

### File Hash Caching Strategy
- Cache key = MD5(file_path) + file_mtime + file_size
- Changing file mtime invalidates cache (triggers re-analysis)
- Moving files = new cache entry (different path)
- Analysis results cached indefinitely (no TTL)

### Provider Command Templates
- ClaudeCliProvider and GeminiCliProvider use templated commands
- Variables: `%%MODEL%%`, `%%IMAGE_PATHS%%`, `%%PROMPT%%`
- Image paths are space-separated, quoted if containing spaces
- Commands executed via `subprocess.run()` with timeout

### Error Handling Patterns
- Analysis errors stored in AnalysisDB with error messages
- UI shows warning banners for failed analyses
- Partial results still usable (e.g., 45/50 pages analyzed)
- User can retry failed files via "Retry Failed" button in AnalysisStatusWindow

## Common Development Tasks

### Adding a New LLM Provider

1. Create new provider class in `src/llm_providers/`:
```python
from .base_provider import BaseLLMProvider

class MyNewProvider(BaseLLMProvider):
    def analyze_images(self, image_paths, prompt, model=None):
        # Implementation
        pass

    def get_available_models(self):
        return ['model1', 'model2']

    def test_connection(self):
        # Validation logic
        return True
```

2. Register in `provider_factory.py`:
```python
PROVIDER_CLASSES = {
    'ollama': OllamaProvider,
    'claude_cli': ClaudeCliProvider,
    'gemini_cli': GeminiCliProvider,
    'my_new': MyNewProvider  # Add here
}
```

3. Add config section in `config_manager.py`:
```python
if 'MyNew' not in self.config:
    self.config['MyNew'] = {
        'api_key': '',
        'endpoint': 'https://api.example.com',
        'default_model': 'model1'
    }
```

4. Add UI controls in `settings_window_enhanced.py`

### Modifying Analysis Prompts

LLM prompts are stored in settings under `[PromptOptimization]`:
- Edit via EnhancedSettingsWindow → Prompt Optimization tab
- Variables: `{title_keywords}`, `{company_keywords}`, `{date_format}`
- Changes affect future analyses (not cached results)

### Debugging Analysis Issues

1. Check `app.log` for exceptions
2. Open AnalysisStatusWindow to see per-file results
3. Query AnalysisDB directly:
```python
from analysis_db import AnalysisDB
db = AnalysisDB()
failed = db.get_failed_analyses()
for f in failed:
    print(f['file_path'], f['error_message'])
```

### Testing Provider Integration

```python
from config_manager import ConfigManager
from llm_providers.provider_factory import ProviderFactory

config = ConfigManager()
provider = ProviderFactory.create_from_config_manager(config, 'ollama')

# Test connection
if provider.test_connection():
    print("Provider is available")

# Test analysis
result = provider.analyze_images(
    image_paths=['test.png'],
    prompt='Extract company name from this document'
)
print(result)
```

## Dependencies

Core dependencies (from requirements.txt):
- **PyQt6**: GUI framework
- **PyMuPDF (fitz)**: PDF manipulation and OCR
- **Pillow**: Image processing (TIFF conversion)
- **requests**: HTTP client for Ollama API

## AppData Storage

All persistent data stored in `%APPDATA%\WinScanLLM\`:
- `settings.ini`: User configuration
- `metadata.db`: Document metadata cache (SQLite)
- `analysis_cache.db`: Analysis results cache (SQLite)

## Keyboard Shortcuts

Full reference in `docs/keyboard_shortcuts_reference.md`. Key shortcuts:
- `Space`: Include current page in bundle
- `Delete`: Exclude current page from bundle
- `Enter`: Approve/Continue to next step
- `←`/`→`: Navigate images
- `Ctrl+A`: Accept all high-confidence bundles
- `F1` or `?`: Toggle shortcuts legend

## External Dependencies

### Ollama Setup
1. Install from https://ollama.com/
2. Pull a vision model: `ollama pull qwen2.5-vl`
3. Server runs on http://localhost:11434 by default

### Claude CLI Setup
1. Install Claude Code CLI
2. Authenticate: `claude auth`
3. Verify: `claude --help`

### Gemini CLI Setup
1. Install Google Gemini CLI
2. Configure API key
3. Verify: `gemini --version`

## Common Issues

### TIFF Files Not Converting
- Ensure Pillow is installed: `pip install Pillow`
- Check file permissions in scan folder
- Review `app.log` for PIL errors

### Analysis Hangs/Timeouts
- Check provider timeout settings (default: 300s)
- Verify provider server is running (e.g., Ollama)
- Large images may timeout - consider resizing

### Database Locked Errors
- SQLite doesn't handle concurrent writes well
- Ensure only one app instance running
- If corrupted, delete `*.db` files (data loss) and restart

### PDF Not Searchable
- Requires PyMuPDF with OCR support
- Check `fitz.TOOLS.mupdf_supports_ocr()` returns True
- Install Tesseract OCR if needed

## Testing Notes

Test files in `tests/`:
- `test_config_manager.py`: Configuration loading/saving
- `test_file_processor.py`: TIFF conversion, grouping, PDF generation
- `test_ollama_service.py`: Ollama API integration (requires running server)

Run tests from repository root to ensure correct imports.
