# Validation Checklist - Phases 1-5

**Implementation Date:** 2026-02-02
**Phases Completed:** 1-5 (Database, Providers, Services, UI Foundation)
**Status:** Ready for validation testing

---

## Pre-Validation Setup

### ✅ Prerequisites
- [ ] Python 3.14 installed
- [ ] All dependencies installed (`pip install -r requirements.txt` if exists)
- [ ] PyQt6 installed (`pip install PyQt6`)
- [ ] PyMuPDF installed (`pip install PyMuPDF`)
- [ ] Ollama installed (optional, for testing provider)
- [ ] Test images available (PNG files)
- [ ] Test PDF files available (for PDF extraction)

### ✅ Environment Setup
- [ ] Navigate to project directory: `cd C:\development\scan_organization`
- [ ] Verify directory structure intact:
  - [ ] `src/` folder exists with all Python files
  - [ ] `tests/` folder exists with test files
  - [ ] `assets/` folder exists (for icons/images)
- [ ] Check git status: `git status` (should show clean working tree)

---

## Phase 1: Database Foundation Validation

### ✅ MetadataDB Tests

**Test 1.1: Database Creation**
```bash
cd tests
python -c "import sys; sys.path.insert(0, '../src'); from metadata_db import MetadataDB; db = MetadataDB('test.db'); print(f'Schema version: {db.get_schema_version()}'); db.close(); import os; os.remove('test.db')"
```
- [ ] Command runs without errors
- [ ] Outputs schema version ≥ 1
- [ ] No error messages

**Test 1.2: Metadata Storage**
```bash
python simple_test_runner.py 2>&1 | grep -A 5 "Phase 1"
```
- [ ] Phase 1 shows [PASS]
- [ ] MetadataDB creation test passes
- [ ] AnalysisDB creation test passes
- [ ] ConfigManager test passes

**Expected Output:**
```
[PASS] Phase 1
```

### ✅ AnalysisDB Tests

**Test 1.3: Extended Tables**
```bash
python -c "import sys; sys.path.insert(0, '../src'); from analysis_db import AnalysisDB; db = AnalysisDB('test.db'); stats = db.get_extended_statistics(); print(f'Tables working: {len(stats)} metrics'); db.close(); import os; os.remove('test.db')"
```
- [ ] Command runs without errors
- [ ] Outputs "Tables working: 9 metrics" or similar
- [ ] All 6 new tables created

**Test 1.4: Provider Configuration**
```bash
python -c "import sys; sys.path.insert(0, '../src'); from analysis_db import AnalysisDB; db = AnalysisDB('test.db'); db.add_provider('test', 'ollama', {'url': 'test'}, 'model1'); p = db.get_active_provider(); db.close(); import os; os.remove('test.db'); print('Provider test OK' if p is None else f'Provider: {p}')"
```
- [ ] No errors
- [ ] Provider operations functional

### ✅ ConfigManager Tests

**Test 1.5: Configuration Loading**
```bash
python -c "import sys; sys.path.insert(0, '../src'); from config_manager import ConfigManager; import tempfile; f = tempfile.NamedTemporaryFile(suffix='.ini', delete=False); path = f.name; f.close(); c = ConfigManager(path); p = c.get_active_provider(); print(f'Active provider: {p}'); import os; os.remove(path)"
```
- [ ] Runs without errors
- [ ] Shows active provider (ollama, claude_cli, or gemini_cli)
- [ ] No import errors

**Test 1.6: Directory Management**
```bash
python -c "import sys; sys.path.insert(0, '../src'); from config_manager import ConfigManager; import tempfile; f = tempfile.NamedTemporaryFile(suffix='.ini', delete=False); path = f.name; f.close(); c = ConfigManager(path); c.add_directory('C:\\\\test'); dirs = c.get_directories(); print(f'Directories: {len(dirs)}'); import os; os.remove(path)"
```
- [ ] No errors
- [ ] Directory operations work

---

## Phase 2: LLM Provider Abstraction Validation

### ✅ Provider Factory Tests

**Test 2.1: Factory Creation**
```bash
python -c "import sys; sys.path.insert(0, '../src'); from llm_providers.provider_factory import ProviderFactory; types = ProviderFactory.get_available_provider_types(); print(f'Provider types: {types}')"
```
- [ ] No import errors
- [ ] Shows 3 provider types: ['ollama', 'claude_cli', 'gemini_cli']

**Test 2.2: Ollama Provider**
```bash
python -c "import sys; sys.path.insert(0, '../src'); from llm_providers.provider_factory import ProviderFactory; config = {'base_url': 'http://localhost:11434', 'timeout': 300, 'model': 'qwen2.5-vl'}; p = ProviderFactory.create_provider('ollama', config); print(f'Default model: {p.get_default_model()}')"
```
- [ ] No errors
- [ ] Shows "Default model: qwen2.5-vl"

**Test 2.3: Provider Validation**
```bash
python -c "import sys; sys.path.insert(0, '../src'); from llm_providers.ollama_provider import OllamaProvider; p = OllamaProvider({'model': 'test', 'base_url': 'http://localhost:11434', 'timeout': 300}); valid, err = p.validate_config(); print(f'Valid: {valid}')"
```
- [ ] Runs successfully
- [ ] Shows "Valid: True"

### ✅ Command Builder Tests

**Test 2.4: Template Validation**
```bash
python -c "import sys; sys.path.insert(0, '../src'); from llm_providers.command_builder import CommandBuilder; template = 'claude --model %%MODEL%% --image %%IMAGE_PATHS%% --prompt %%PROMPT%%'; valid, err = CommandBuilder.validate_template(template); print(f'Template valid: {valid}')"
```
- [ ] Shows "Template valid: True"
- [ ] No errors

**Test 2.5: Command Building**
```bash
python -c "import sys; sys.path.insert(0, '../src'); from llm_providers.command_builder import CommandBuilder; cmd = CommandBuilder.build_command('test %%MODEL%%', 'model1', ['img.png'], 'prompt'); print(f'Command built: {\"model1\" in cmd}')"
```
- [ ] Shows "Command built: True"
- [ ] Variable substitution works

---

## Phase 3: Analysis & Bundling Services Validation

### ✅ Analysis Service Tests

**Test 3.1: Service Initialization**
```bash
python -c "import sys; sys.path.insert(0, '../src'); from analysis_service import AnalysisService; from analysis_db import AnalysisDB; from metadata_db import MetadataDB; from config_manager import ConfigManager; import tempfile; f1 = tempfile.NamedTemporaryFile(suffix='.db', delete=False); f2 = tempfile.NamedTemporaryFile(suffix='.ini', delete=False); db_path = f1.name; cfg_path = f2.name; f1.close(); f2.close(); c = ConfigManager(cfg_path); a = AnalysisDB(db_path); m = MetadataDB(db_path); s = AnalysisService(c, a, m); print(f'Service created: {s is not None}'); a.close(); m.close(); import os; os.remove(db_path); os.remove(cfg_path)"
```
- [ ] Shows "Service created: True"
- [ ] No errors

**Test 3.2: Analysis Prompt**
```bash
python -c "import sys; sys.path.insert(0, '../src'); from analysis_service import AnalysisService; print(f'Prompt length: {len(AnalysisService.DEFAULT_ANALYSIS_PROMPT)} chars')"
```
- [ ] Shows prompt length ~1500 characters
- [ ] Prompt includes key fields (document_type, company, rotation)

### ✅ Bundling Service Tests

**Test 3.3: Bundling Service Creation**
```bash
python -c "import sys; sys.path.insert(0, '../src'); from bundling_service import BundlingService; from analysis_db import AnalysisDB; import tempfile; f = tempfile.NamedTemporaryFile(suffix='.db', delete=False); path = f.name; f.close(); db = AnalysisDB(path); s = BundlingService(db); print(f'Bundling service: {s is not None}'); db.close(); import os; os.remove(path)"
```
- [ ] Shows "Bundling service: True"
- [ ] No errors

**Test 3.4: Bundle Generation**
```bash
cd tests
python simple_test_runner.py 2>&1 | grep -A 3 "Bundling recommendations"
```
- [ ] Shows bundling test passes
- [ ] No errors in Phase 3

---

## Phase 4: UI Foundation Validation

### ✅ Window Renaming Tests

**Test 4.1: Check Class Names**
```bash
cd src
grep -n "class.*Window" gui.py
```
- [ ] Line ~147: `class SettingsWindow`
- [ ] Line ~651: `class ConvertPDFsWindow`
- [ ] Line ~990: `class ConvertImagesWindow` (NOT ProcessingWindow)
- [ ] Line ~3900: `class StartupWindow`

**Test 4.2: Verify Window Titles**
```bash
grep -A 2 "setWindowTitle" gui.py | head -20
```
- [ ] ConvertImagesWindow shows "Convert Images"
- [ ] ConvertPDFsWindow shows "Convert PDFs"
- [ ] No "Processing" window title

**Test 4.3: Check Button Labels**
```bash
grep "QPushButton(" gui.py | grep -E "(Convert|Change|Quit)"
```
- [ ] Shows "Convert Scans" button
- [ ] Shows "Convert PDFs" button
- [ ] Shows "Change Settings" button
- [ ] Shows "Quit" button

### ✅ Application Launch Test

**Test 4.4: Syntax Check**
```bash
python -m py_compile src/gui.py && echo "✓ Syntax OK"
```
- [ ] Shows "✓ Syntax OK"
- [ ] No syntax errors

**Test 4.5: Launch Application (Visual Test)**
```bash
cd src
python gui.py
```

**Manual Checks:**
- [ ] Application window opens
- [ ] Title shows "WinScanOllamaVision" or configured name
- [ ] 4 buttons visible:
  - [ ] "Convert Scans"
  - [ ] "Convert PDFs"
  - [ ] "Change Settings"
  - [ ] "Quit"
- [ ] Buttons have consistent styling (blue background)
- [ ] Quit button has red background (#8B0000)
- [ ] Scanner GIF animation plays (if asset exists)

**Test 4.6: Quit Button Functionality**
- [ ] Click "Quit" button
- [ ] Confirmation dialog appears: "Are you sure you want to quit?"
- [ ] "Yes" closes application
- [ ] "No" cancels and returns to main window

---

## Phase 5: ConvertPDFsWindow Validation

### ✅ PDF Extraction Window Tests

**Test 5.1: Check ConvertPDFsWindow Exists**
```bash
grep -n "class ConvertPDFsWindow" src/gui.py
```
- [ ] Shows line number (around line 651)
- [ ] Class definition found

**Test 5.2: Check Window Structure**
```bash
grep -A 5 "def _show_step_" src/gui.py | head -20
```
- [ ] Shows `_show_step_1` method
- [ ] Shows `_show_step_2` method
- [ ] Shows `_show_step_3` method

### ✅ PDF Extraction Functionality (Visual Test)

**Test 5.3: Prepare Test PDFs**
1. Create/copy 1-2 test PDF files to scan folder
2. Scan folder location: Check `settings.ini` → `[DocumentProcessing]` → `scan_folder`
3. Verify PDFs are readable (not corrupted)

**Test 5.4: Launch and Test PDF Extraction**
```bash
cd src
python gui.py
```

**Step 1: PDF Selection**
- [ ] Click "Convert PDFs" button
- [ ] ConvertPDFsWindow opens with title "Convert PDFs"
- [ ] Step 1 label shows "Select PDFs to Extract"
- [ ] PDF list displays with checkboxes
- [ ] Each PDF shows page count: "filename.pdf (N pages)"
- [ ] "Select All" button works
- [ ] "Deselect All" button works
- [ ] "Extract Pages" button enabled when PDFs selected
- [ ] "Extract Pages" button disabled when none selected

**Step 2: Extraction Progress**
- [ ] Select 1 PDF and click "Extract Pages"
- [ ] Window transitions to Step 2
- [ ] Progress label updates: "Extracting {name}..."
- [ ] Progress bar shows progress (0-100%)
- [ ] Log text shows extraction details:
  - [ ] "Extracting {pdf_name} (N pages)..."
  - [ ] Individual page extraction: "Page 1 -> {name}_page_001.png"
  - [ ] Completion: "✓ Completed {pdf_name}"
- [ ] "Continue" button appears when done

**Step 3: Completion Summary**
- [ ] Click "Continue"
- [ ] Window transitions to Step 3
- [ ] Summary shows:
  - [ ] PDFs Processed count
  - [ ] Successful count
  - [ ] Failed count (should be 0)
  - [ ] Total Pages Extracted count
- [ ] Details list shows "✓ {pdf_name}: N pages extracted"
- [ ] "Send to Convert Scans" button visible
- [ ] "Close" button works

**Test 5.5: Verify Extracted PNGs**
1. Navigate to scan folder
2. Check for extracted PNG files:
   - [ ] Files exist: `{pdf_name}_page_001.png`, `{pdf_name}_page_002.png`, etc.
   - [ ] Naming format correct: 3-digit page numbers with leading zeros
   - [ ] Images are readable (open in image viewer)
   - [ ] Images have good quality (300 DPI extraction)
   - [ ] All pages from PDF extracted

**Test 5.6: Error Handling**
- [ ] Test with corrupted PDF (should show error in log)
- [ ] Test with no PDFs in folder (should show "No PDF files found")
- [ ] Test with empty selection (button should stay disabled)

---

## Integration Testing

### ✅ End-to-End Workflow Test

**Scenario 1: PDF → PNG → Process**
1. [ ] Place test PDF in scan folder
2. [ ] Launch application
3. [ ] Click "Convert PDFs"
4. [ ] Select PDF and extract pages
5. [ ] Close PDF extraction window
6. [ ] Click "Convert Scans" (opens ConvertImagesWindow)
7. [ ] Verify extracted PNGs appear in file list
8. [ ] (Full processing not tested in this phase)

**Scenario 2: Settings Access**
1. [ ] Launch application
2. [ ] Click "Change Settings"
3. [ ] Settings dialog opens
4. [ ] Close settings dialog
5. [ ] Application returns to main window

**Scenario 3: Multiple PDFs**
1. [ ] Place 3+ PDFs in scan folder
2. [ ] Launch application → "Convert PDFs"
3. [ ] Select multiple PDFs (test Select All)
4. [ ] Extract all
5. [ ] Verify all PDFs processed in Step 3 summary
6. [ ] Check scan folder for all extracted PNGs

---

## Performance Validation

### ✅ Performance Benchmarks

**Test P.1: Database Operations**
```bash
cd tests
python -c "import sys; sys.path.insert(0, '../src'); from analysis_db import AnalysisDB; import time; import tempfile; f = tempfile.NamedTemporaryFile(suffix='.db', delete=False); path = f.name; f.close(); start = time.time(); db = AnalysisDB(path); stats = db.get_extended_statistics(); elapsed = (time.time() - start) * 1000; print(f'Database init: {elapsed:.0f}ms'); db.close(); import os; os.remove(path)"
```
- [ ] Database initialization < 100ms
- [ ] Statistics query completes quickly

**Test P.2: Provider Creation**
```bash
python -c "import sys; sys.path.insert(0, '../src'); from llm_providers.provider_factory import ProviderFactory; import time; start = time.time(); config = {'base_url': 'http://localhost:11434', 'timeout': 300, 'model': 'test'}; p = ProviderFactory.create_provider('ollama', config); elapsed = (time.time() - start) * 1000; print(f'Provider creation: {elapsed:.0f}ms')"
```
- [ ] Provider creation < 10ms
- [ ] Factory instantiation fast

**Test P.3: PDF Extraction Speed**
- [ ] Extract 10-page PDF
- [ ] Measure time from Step 2 start to "Complete"
- [ ] Expected: ~5-10 seconds for 10 pages at 300 DPI
- [ ] No UI freezing during extraction
- [ ] Progress updates smooth

---

## Regression Testing

### ✅ Existing Functionality Check

**Test R.1: Existing ProcessingWindow (now ConvertImagesWindow)**
```bash
cd src
python gui.py
```
- [ ] Click "Convert Scans" button
- [ ] ConvertImagesWindow opens (not error)
- [ ] Window title shows "Convert Images"
- [ ] No references to old "ProcessingWindow" in UI

**Test R.2: Settings Window Still Works**
- [ ] Click "Change Settings"
- [ ] Settings window opens
- [ ] Ollama settings visible
- [ ] Can modify settings
- [ ] Save works (no errors)

---

## Known Issues & Limitations

### ✅ Document Known Issues

**Issue 1: Ollama Provider Requires Running Server**
- [ ] OllamaProvider tests will fail if Ollama server not running
- [ ] Expected behavior: Connection test returns False
- [ ] Not a bug: Provider designed to fail gracefully
- [ ] Workaround: Start Ollama server for testing

**Issue 2: CLI Providers Require External Tools**
- [ ] ClaudeCliProvider requires `claude` CLI tool installed
- [ ] GeminiCliProvider requires `gemini` CLI tool installed
- [ ] Tests only validate structure, not live calls
- [ ] Expected: Command building works, execution requires tools

**Issue 3: Database Locking on Windows**
- [ ] Temporary database files may lock briefly on Windows
- [ ] Tests include 0.5s delays for cleanup
- [ ] If tests fail with "file is being used", wait and retry
- [ ] Not a production issue: only affects rapid test cycles

**Issue 4: Line Ending Warnings (Git)**
- [ ] Git warnings about LF → CRLF are normal on Windows
- [ ] Does not affect functionality
- [ ] Expected: Files work correctly regardless

---

## Validation Sign-Off

### ✅ Phase Completion Checklist

**Phase 1: Database Foundation**
- [ ] All database tests pass
- [ ] MetadataDB, AnalysisDB, ConfigManager functional
- [ ] Schema versioning works
- [ ] No data corruption

**Phase 2: LLM Provider Abstraction**
- [ ] All provider types available
- [ ] Factory creates providers correctly
- [ ] Command builder validates templates
- [ ] Provider switching functional

**Phase 3: Analysis & Bundling Services**
- [ ] Services initialize correctly
- [ ] Analysis prompt comprehensive
- [ ] Bundling algorithm functional
- [ ] Database integration works

**Phase 4: UI Foundation**
- [ ] All windows renamed correctly
- [ ] 4 buttons visible and functional
- [ ] Quit confirmation works
- [ ] No UI errors on launch

**Phase 5: ConvertPDFsWindow**
- [ ] Window opens from "Convert PDFs" button
- [ ] 3-step workflow complete
- [ ] PDF extraction works at 300 DPI
- [ ] PNGs created with correct naming
- [ ] Progress tracking functional

### ✅ Overall System Health

**Critical Checks**
- [ ] No syntax errors in any Python file
- [ ] All imports resolve correctly
- [ ] Application launches without errors
- [ ] No crashes during normal operation
- [ ] Database files created and readable
- [ ] Configuration persists correctly

**Quality Checks**
- [ ] Code follows consistent style
- [ ] Error messages are user-friendly
- [ ] Progress feedback is clear
- [ ] Confirmations prevent data loss
- [ ] File operations are safe (no overwrites without warning)

---

## Test Results Log

**Date:** _______________
**Tested By:** _______________
**Environment:** _______________

**Summary:**
- Total Tests: _____ / _____
- Passed: _____
- Failed: _____
- Skipped: _____

**Critical Issues Found:**
1. _______________________________________
2. _______________________________________
3. _______________________________________

**Notes:**
_____________________________________________
_____________________________________________
_____________________________________________

**Sign-Off:**
- [ ] All critical tests passed
- [ ] Known issues documented
- [ ] Ready for next phase development
- [ ] OR Issues require resolution before proceeding

**Signature:** _______________ **Date:** _______________

---

## Quick Reference Commands

### Run All Automated Tests
```bash
cd tests
python simple_test_runner.py
```

### Check Syntax Only
```bash
python -m py_compile src/gui.py
python -m py_compile src/analysis_db.py
python -m py_compile src/analysis_service.py
python -m py_compile src/bundling_service.py
```

### Launch Application
```bash
cd src
python gui.py
```

### Verify Git Status
```bash
git status
git log --oneline -5
```

### Check Database Files
```bash
ls -lh metadata.db   # If exists
ls -lh src/metadata.db   # Alternative location
```

---

**Document Version:** 1.0
**Last Updated:** 2026-02-02
**Status:** Active - Phases 1-5 Validation
