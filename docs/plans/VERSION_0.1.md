# WinScan Ollama Vision - Comprehensive Enhancement Plan

> **Historical Note:** This document preserves the original plan created before the application was renamed to "WinScanLLM". The original name is maintained here for historical accuracy.

## Executive Summary

Transform the document scanning application with AI-powered automatic bundling, multi-provider LLM support, PDF extraction for re-bundling, and a modern UI redesign. The implementation maintains backward compatibility while adding powerful new features centered around pre-analysis and intelligent document grouping.

## User Requirements Summary

**Main Goals:**
1. Rename main menu buttons and windows to reflect intended actions
2. Add PDF extraction window for unbundling existing PDFs
3. Enhance settings with 11+ new capabilities (multi-directories, LLM providers, database management, themes, etc.)
4. Implement automatic page analysis on startup
5. Provide automatic document bundling recommendations with confidence scores
6. Add comprehensive analysis result persistence
7. Enable manual page rotation in UI
8. Redesign conversion window to support pre-analyzed bundling suggestions

**User Answers:**
- Convert PDFs: Extract pages from PDFs to PNGs for re-bundling
- CLI Providers: Claude Code CLI and Google Gemini CLI (specific tools)
- Auto Analysis: Run on application startup (scan once)
- Bundle Recommendations: Pre-grouped thumbnails with confidence scores

**Additional Requirements:**
- Zoom Controls: Support "Fit to Width", "Fit to Height", and custom % entry (not just +/-)
- CLI Templates: Command templates must include %MODEL% variable for proper model substitution
- Dynamic Model Selection: Model dropdown updates when provider changes (populated from provider)
- Prompt Optimization: Settings UI allows manual editing PLUS "Optimize Prompt" button that uses AI to improve prompts, plus "Reset to Default" button

## Architecture Overview

### Core Architectural Changes

**1. Database Schema Extensions**
- **New Tables:**
  - `analysis_results` - Comprehensive page analysis storage
  - `llm_providers` - Provider configuration tracking
  - `source_directories` - Multiple directory support
  - `document_bundles` - Auto-bundling recommendations
  - `audit_trail` - User action tracking (optional)
  - `rotation_preferences` - Per-file rotation tracking

**2. LLM Provider Abstraction Layer**
```
BaseLLMProvider (Abstract)
├── OllamaProvider (HTTP API via Python SDK)
├── ClaudeCliProvider (CLI via subprocess)
└── GeminiCliProvider (CLI via subprocess)

ProviderFactory creates instances based on settings
```

**3. New Services**
- `AnalysisService` - Automatic startup analysis
- `BundlingService` - Document recommendation engine
- `PurgeService` - Database cleanup management

**4. UI Architecture**
```
StartupWindow (4 buttons instead of 3)
├── ConvertImagesWindow (renamed from ProcessingWindow)
│   └── Pre-bundling step before existing 4-step workflow
├── ConvertPDFsWindow (NEW - PDF extraction)
└── EnhancedSettingsWindow (5 tabs)
```

## Implementation Plan

### Phase 1: Database Foundation (Week 1)

**Files to Create:**
- `src/analysis_db.py` - Extended database access layer

**Files to Modify:**
- `src/metadata_db.py` - Add new table creation, migration utilities

**Tasks:**
1. Create new database schema (6 new tables)
2. Add migration logic for existing databases
3. Implement AnalysisDB class with methods:
   - `save_analysis()` - Store comprehensive page analysis
   - `get_analyzed_pages()` - Retrieve analyzed pages
   - `add_source_directory()` - Manage multiple directories
   - `save_bundle_suggestion()` - Store bundling recommendations
4. Add indices for performance
5. Test database operations with existing metadata.db

**Verification:**
- Create test database, add entries to all new tables
- Verify migration preserves existing data
- Check query performance with sample data

### Phase 2: LLM Provider Abstraction (Week 2)

**Files to Create:**
- `src/llm_providers/__init__.py`
- `src/llm_providers/base_provider.py` - Abstract base class
- `src/llm_providers/provider_factory.py` - Factory pattern
- `src/llm_providers/command_builder.py` - CLI template processor
- `src/llm_providers/ollama_provider.py` - Refactored Ollama
- `src/llm_providers/claude_cli_provider.py` - Claude CLI
- `src/llm_providers/gemini_cli_provider.py` - Gemini CLI

**Files to Modify:**
- `src/config_manager.py` - Add provider configuration sections

**Tasks:**
1. Implement BaseLLMProvider with unified interface
2. Create OllamaProvider wrapping existing OllamaService
3. Implement CommandBuilder with variable substitution
4. Create CLI provider implementations
5. Add ProviderFactory for instantiation
6. Extend settings.ini with provider configurations

**Verification:**
- Test OllamaProvider produces identical results to old code
- Test Claude CLI provider with test images
- Test Gemini CLI provider with test images
- Verify provider switching in settings

### Phase 3: Automatic Analysis Service (Week 3)

**Files to Create:**
- `src/analysis_service.py` - Startup analysis orchestration
- `src/bundling_service.py` - Document bundling recommendations

**Files to Modify:**
- `src/main.py` - Add startup analysis trigger
- `src/gui.py` - Add progress dialog for analysis

**Tasks:**
1. Implement AnalysisService with:
   - `scan_all_directories()` - Batch analysis
   - `_analyze_single_page()` - Comprehensive metadata extraction
   - Cache-aware processing
2. Implement BundlingService with:
   - `generate_bundle_recommendations()` - Clustering algorithm
   - `_group_by_page_numbers()` - Explicit page number grouping
   - `_group_by_metadata()` - Metadata-based grouping
   - `_calculate_bundle_confidence()` - Scoring algorithm
3. Create comprehensive page analysis prompt
4. Add startup progress dialog
5. Integrate with metadata caching

**Verification:**
- Analyze 50+ test images, verify metadata extraction
- Check cache hit rate on re-scan
- Verify bundling suggestions for known documents
- Test confidence scoring accuracy

### Phase 4: UI Foundation - Window Renaming & Buttons (Week 4)

**Files to Modify:**
- `src/gui.py` - All window classes

**Tasks:**
1. **StartupWindow (lines 3609-3817):**
   - Add 4th button: "Quit"
   - Rename buttons: "Convert Scans", "Convert PDFs", "Change Settings"
   - Add button descriptions
   - Add icons to buttons
   - Update layout and spacing

2. **Rename ProcessingWindow → ConvertImagesWindow (lines 657-3607):**
   - Update class name throughout
   - Update window title
   - Update references in StartupWindow

3. **Update SettingsWindow (lines 147-616):**
   - Keep name but prepare for tabbed redesign

**Verification:**
- Launch app, verify 4 buttons visible
- Click each button, verify navigation
- Verify "Quit" shows confirmation dialog
- Check window titles updated

### Phase 5: ConvertPDFsWindow (Week 5)

**Files to Create:**
- Add `ConvertPDFsWindow` class to `src/gui.py`

**Tasks:**
1. Create new window class with 3 steps:
   - Step 1: PDF selection with checkboxes
   - Step 2: Extraction progress
   - Step 3: Completion summary
2. Implement PDF extraction using PyMuPDF:
   - Extract pages to PNGs at 300 DPI
   - Name pattern: `{pdf_name}_page_{num:03d}.png`
   - Save to scan folder
3. Add preview functionality
4. Add "Send to Conversion" action
5. Integrate with StartupWindow "Convert PDFs" button

**Verification:**
- Extract pages from test PDF
- Verify PNG quality and naming
- Click "Send to Conversion", verify opens ConvertImagesWindow
- Test with scanner-generated and app-generated PDFs

### Phase 6: Enhanced Settings Window (Week 6)

**Files to Modify:**
- `src/gui.py` - SettingsWindow class (lines 147-616)
- `src/config_manager.py` - Add new settings sections

**Tasks:**
1. Convert to QTabWidget with 5 tabs:
   - **General:** Scan folder, auto-approval, audit trail
   - **LLM Provider:** Provider selection with dynamic panels
   - **Directories:** Multi-directory management (add/remove)
   - **Database:** Purge options, statistics viewer
   - **Appearance:** Theme, zoom defaults, system tray

2. Implement provider-specific settings panels:
   - **Provider Selector:** Dropdown (Ollama/Claude CLI/Gemini CLI)
   - **Model Dropdown:** Dynamically populated based on selected provider
     * When provider changes, fetch available models and update dropdown
     * Ollama: Query via SDK
     * CLI: Parse from settings or query command
   - **Endpoint/Command Template:** Editable field with variable syntax
   - **Timeout:** Numeric spinner

3. **Dynamic Model Selection:**
   - Create `_on_provider_changed()` slot
   - Clear and repopulate model dropdown when provider switches
   - For CLI providers, parse models from comma-separated config
   - Persist selected model per provider separately

4. **Prompt Editor with AI Optimization:**
   - Expandable text editor for each prompt type
   - **[Optimize Prompt] button:**
     * Sends current prompt to selected provider
     * Request: "Improve this prompt for better responses from your model: {current_prompt}"
     * Replaces prompt with optimized version
     * Show before/after comparison dialog
   - **[Reset to Default] button:**
     * Restores original system prompt
     * Confirmation dialog to prevent accidental reset
   - **[Save Prompt] button:**
     * Saves to settings.ini
   - Support for multiple prompt types: Document validation, Metadata extraction, Page analysis

5. Add directory management UI:
   - QListWidget with add/remove buttons
   - Store as JSON array in settings

6. Add database management:
   - Statistics dialog (counts, sizes)
   - Purge operations with checkboxes
   - Backup database button

**Verification:**
- Switch provider, verify model dropdown updates
- Edit command template, verify variables work
- Click "Optimize Prompt", verify AI improves it
- Reset prompt, verify returns to default
- Add multiple source directories
- View database statistics

### Phase 7: Document Bundling UI (Week 7)

**Files to Modify:**
- `src/gui.py` - ConvertImagesWindow

**Tasks:**
1. Create BundleSuggestionCard widget:
   - Shows suggested document metadata
   - Displays thumbnails in horizontal strip
   - Shows confidence badge (high/medium/low)
   - Actions: Accept, Modify, Reject

2. Add pre-bundling step before Step 1:
   - Run analysis on all imported scans
   - Generate bundle suggestions
   - Display as scrollable list of cards
   - "Accept All High Confidence" button
   - "Review Manually" to skip to normal workflow

3. Implement bundle actions:
   - Accept: Add to completed groups
   - Modify: Enter manual stitching for this bundle
   - Reject: Mark pages as excluded

4. Update thumbnail display (PagePreviewWidget):
   - Add metadata overlays (page number, type, company)
   - Add cache indicator
   - Add confidence color border

**Verification:**
- Import 20+ scans, verify bundling suggestions appear
- Accept high-confidence bundle, verify skips to Step 2
- Modify bundle, verify enters manual stitching
- Check metadata displays on thumbnails

### Phase 8: Rotation & Zoom Controls (Week 8)

**Files to Modify:**
- `src/gui.py` - ConvertImagesWindow Step 1

**Tasks:**
1. **Enhanced Zoom Controls:**
   - Replace simple +/- buttons with comprehensive zoom toolbar
   - Add zoom mode dropdown:
     * "Fit to Width" - Scale to window width
     * "Fit to Height" - Scale to window height
     * "Fit to Window" - Scale to fit entire window
     * "Custom %" - Manual percentage entry
   - Add zoom percentage spinner (25% to 400%, step 25%)
   - Remember last zoom mode per session
   - Add keyboard shortcuts: Ctrl+0 (fit), Ctrl++ (zoom in), Ctrl+- (zoom out)

2. **Zoom Implementation:**
   - `_apply_zoom_mode(mode, value=None)` method
   - Calculate fit-to-width/height based on window size
   - Update on window resize if in fit mode
   - Save preference per document type (PNG vs PDF)

3. Add rotation button group to right panel:
   - 4 buttons: 90° CCW, 90° CW, 180°, 270°
   - 2x2 grid layout
   - Unicode rotation arrow icons

4. Implement rotation functionality:
   - `_rotate_current_page(degrees)` method
   - Use PIL Image.rotate()
   - Save rotated PNG (overwrite original)
   - Invalidate metadata cache
   - Refresh preview immediately

5. Add visual indicators:
   - Red corner triangle for pages needing rotation
   - Blue rotation badge showing current rotation
   - Update thumbnail display

6. Integrate with automatic analysis:
   - Store `rotation_needed` from AI analysis
   - Auto-indicate pages requiring rotation
   - Remember manual rotations

**Verification:**
- Test "Fit to Width" and "Fit to Height" modes
- Enter custom zoom (e.g., 175%), verify display
- Rotate image 90°, verify PNG updated
- Resize window in fit mode, verify auto-adjusts
- Check cache invalidated for rotated page
- Test keyboard shortcuts for zoom

### Phase 9: UI Redesign - Visual Polish (Week 9)

**Files to Create:**
- `src/styles.py` - QSS stylesheet definitions

**Files to Modify:**
- `src/gui.py` - Apply new styles throughout
- `src/main.py` - Load stylesheet on startup

**Tasks:**
1. Implement modern color palette:
   - Primary: #2563EB (Modern Blue)
   - Success: #059669 (Emerald)
   - Danger: #DC2626 (Red)
   - Warning: #F59E0B (Amber)

2. Create QSS stylesheets:
   - Button styles with hover states
   - Card-based thumbnail design
   - Two-column layout improvements
   - Typography updates

3. Add micro-interactions:
   - Button hover lift effect
   - Smooth transitions between steps
   - Loading state animations
   - Toast notifications for success/error

4. Update layouts:
   - Two-column main area (preview + context panel)
   - Status ribbon at bottom
   - Carousel thumbnails with better spacing
   - Improved header with consolidated controls

**Verification:**
- Launch app, verify color palette applied
- Hover buttons, verify lift animation
- Navigate through workflow, verify smooth transitions
- Check responsive behavior at different window sizes

### Phase 10: Integration & Testing (Week 10)

**Tasks:**
1. End-to-end workflow testing:
   - Import scans → Review bundles → Accept/modify → Finalize PDFs
   - Extract PDF → Re-bundle → Create new PDF
   - Multi-directory scanning
   - Provider switching

2. Performance testing:
   - Startup analysis time with 100+ images
   - Cache hit rate verification
   - UI responsiveness during analysis

3. Error handling:
   - Provider connection failures
   - Invalid PDFs
   - Corrupted images
   - Database errors

4. Accessibility:
   - Keyboard navigation
   - Screen reader compatibility
   - High contrast mode

5. Documentation:
   - Update README with new features
   - Create user guide for bundling suggestions
   - Document provider configuration
   - Add troubleshooting section

**Verification:**
- Complete 10 full workflows without errors
- Process 100 images in under 5 minutes (with cache)
- Navigate entirely with keyboard
- Verify settings persist across restarts

## Critical Files Summary

### Files to Create (9 new files)
1. `src/llm_providers/__init__.py`
2. `src/llm_providers/base_provider.py`
3. `src/llm_providers/provider_factory.py`
4. `src/llm_providers/command_builder.py`
5. `src/llm_providers/ollama_provider.py`
6. `src/llm_providers/claude_cli_provider.py`
7. `src/llm_providers/gemini_cli_provider.py`
8. `src/analysis_service.py`
9. `src/bundling_service.py`
10. `src/analysis_db.py`
11. `src/styles.py`

### Files to Modify (6 existing files)
1. **`src/gui.py`** (3000+ lines)
   - StartupWindow: Add 4th button, rename existing (lines 3609-3817)
   - ProcessingWindow → ConvertImagesWindow: Add bundling UI (lines 657-3607)
   - ConvertPDFsWindow: New class (~300 lines)
   - SettingsWindow: Convert to tabs (lines 147-616)
   - PagePreviewWidget: Add metadata overlays (lines 618-650)

2. **`src/metadata_db.py`** (419 lines)
   - Add new table creation in `_create_tables()`
   - Add migration utilities
   - Extend with analysis-specific methods

3. **`src/config_manager.py`** (79 lines)
   - Add new INI sections for providers, directories, database, appearance
   - Add helper methods for provider configuration
   - Support JSON arrays for directories

4. **`src/ollama_service.py`** (547 lines)
   - Mark as deprecated (kept for backward compatibility)
   - Eventually replaced by OllamaProvider

5. **`src/main.py`** (entry point)
   - Add startup analysis trigger
   - Load stylesheet
   - Initialize provider factory

6. **`settings.ini`**
   - Add new sections: LLMProvider, ClaudeCLI, GeminiCLI, SourceDirectories, AutoAnalysis, Theme, OutputDirectory, SystemTray, AuditTrail

## Configuration Schema Extensions

### settings.ini New Sections

```ini
[LLMProvider]
active_provider = ollama
default_model =

[Ollama]
model = qwen3-vl:latest
base_url = http://localhost:11434
timeout = 300

[ClaudeCLI]
command_template = claude --model %MODEL% --image %IMAGE_PATHS% --prompt %PROMPT%
timeout = 300
models = claude-3-5-sonnet-20241022,claude-3-5-haiku-20241022
default_model = claude-3-5-sonnet-20241022

[GeminiCLI]
command_template = gemini --model %MODEL% --image %IMAGE_PATHS% --prompt %PROMPT%
timeout = 300
models = gemini-2.0-flash-exp,gemini-1.5-pro
default_model = gemini-2.0-flash-exp

[SourceDirectories]
directories = ["C:\\Users\\erik.OPBTA\\Pictures\\Scans"]
scan_on_startup = true

[AutoAnalysis]
enabled = true
incremental = true
batch_size = 10

[Theme]
theme = light
default_zoom_mode_png = fit_to_width
default_zoom_mode_pdf = fit_to_width
default_zoom_percent_png = 100
default_zoom_percent_pdf = 100

[OutputDirectory]
strategy = same_as_source
subdirectory_name = ORGANIZED
global_custom_path =

[SystemTray]
minimize_to_tray = false
close_to_tray = false

[AuditTrail]
enabled = false
```

## Database Schema Extensions

### New Tables

**analysis_results:**
- Comprehensive page-level metadata
- Provider/model tracking
- Full LLM response storage
- Rotation preferences
- Confidence scores

**source_directories:**
- Multiple directory support
- Per-directory settings
- Scan tracking

**document_bundles:**
- AI-generated suggestions
- Confidence scores
- File lists (JSON)
- Status tracking

**llm_providers:**
- Provider configuration
- Active provider tracking

**audit_trail:**
- User actions (optional)
- Decision tracking

**rotation_preferences:**
- Per-file rotation
- Source tracking (AI vs manual)

## Risk Mitigation

### Backward Compatibility
- Existing settings.ini sections unchanged
- Old database schema preserved, new tables added
- OllamaService.py kept for reference
- Migration path for existing databases

### Performance
- Metadata caching minimizes re-analysis
- Incremental scanning (only new/changed files)
- Batch processing with configurable size
- Cache hit rate monitoring

### User Experience
- Bundling suggestions are optional (can skip to manual)
- Settings changes don't break existing workflows
- Progressive disclosure of advanced features
- Clear error messages with recovery options

## Success Criteria

### Functional Requirements Met
- ✅ 4 buttons on main menu with correct names
- ✅ Windows renamed appropriately
- ✅ PDF extraction working for re-bundling
- ✅ Multi-directory support functional
- ✅ LLM provider switching (Ollama/Claude/Gemini)
- ✅ Automatic page analysis on startup
- ✅ Document bundling recommendations displayed
- ✅ Rotation controls in UI
- ✅ Enhanced settings with all requested options
- ✅ Advanced zoom controls (Fit to Width/Height/Window, Custom %)
- ✅ Dynamic model dropdown based on provider
- ✅ AI-powered prompt optimization in settings
- ✅ CLI command templates with %MODEL% variable support

### Performance Targets
- Startup analysis: < 2 seconds per uncached image
- Cache hit rate: > 95% on re-scan
- Bundle suggestion generation: < 5 seconds for 50 images
- UI responsiveness: No freezing during analysis

### Quality Standards
- Zero data loss during migration
- All existing workflows still functional
- Proper error handling and recovery
- Keyboard accessibility throughout

## Next Steps After Approval

1. Create DEV branch from main
2. Create feature branch from DEV
3. Set up worktree for modifications
4. Begin Phase 1: Database Foundation
5. Commit regularly with descriptive messages
6. Test after each phase before proceeding
7. Create PR when complete

## Estimated Timeline

- **Total Duration:** 10 weeks
- **Database & Architecture:** 3 weeks (Phases 1-3)
- **UI Development:** 5 weeks (Phases 4-8)
- **Polish & Testing:** 2 weeks (Phases 9-10)

## Dependencies

### Python Packages (likely already installed)
- PyQt6 (UI framework)
- ollama (Python SDK)
- PyMuPDF (fitz) - PDF operations
- PIL/Pillow - Image operations
- sqlite3 (built-in)

### External Tools (for CLI providers)
- Claude Code CLI (user needs to install)
- Google Gemini CLI (user needs to install)

### System Requirements
- Windows 10+ (current platform)
- Ollama server running (if using Ollama provider)
- Sufficient disk space for database growth
