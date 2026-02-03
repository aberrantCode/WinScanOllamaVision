# Complete Application Workflow Redesign

## Current Broken Workflow

1. User clicks "Convert Scans"
2. `_scan_and_group()` called → tries to generate bundles
3. BundlingService looks for analysis data → finds NONE (AnalysisService never ran)
4. No bundles generated → immediately skips to manual stitching
5. User forced to manually review every page one-by-one
6. No benefit from AI analysis at all

**Result**: User does 100% manual work even though AI analysis infrastructure exists.

---

## Required Redesigned Workflow

### PDF Handling Strategy

**Key Decision**: PDFs are only extracted when user explicitly requests it (not automatically on startup).
- Startup analysis processes existing PNGs only
- PDFs require user action via "Convert PDFs" button
- After extraction, immediate analysis of new PNGs
- Then seamless transition to bundle suggestions

---

### Startup (BEFORE user makes any choice)

1. **App starts** (`main.py` or `StartupWindow.__init__`)
2. **AnalysisService.scan_all_directories()** runs automatically
   - Analyzes all **PNG files only** in scan folders
   - **PDFs are NOT extracted or analyzed** (requires explicit user action)
   - Extracts: document_type, company, date, page_number, total_pages, confidence_score, rotation_needed
   - Writes to `analysis_results` table
   - Shows progress dialog: "Analyzing 47 PNG files... 23/47 complete"
3. **Analysis complete** → StartupWindow displayed with 4 buttons:
   - **Convert Scans** → Work with pre-analyzed PNGs
   - **Convert PDFs** → Extract and re-bundle PDFs
   - **Change Settings** → Configure LLM, directories, etc.
   - **Quit** → Exit application

---

## Workflow Path A: Convert PDFs (Extract and Re-bundle)

### User clicks "Convert PDFs"

**Step 1: PDF Selection**

1. ConvertPDFsWindow opens
2. Shows list of all PDFs in scan folder with checkboxes
3. Preview available for each PDF
4. User selects PDFs to extract
5. Click "Extract Pages" button

**Step 2: Extraction Progress**

1. Extract pages to PNGs at 300 DPI
2. Name pattern: `{pdf_name}_page_{001}.png`
3. Save to scan folder
4. Progress bar: "Extracting: invoice_2024.pdf (3/6 pages)"
5. Extraction complete

**Step 3: Immediate Analysis**

1. **Auto-trigger AnalysisService** on newly extracted PNGs
2. Progress dialog: "Analyzing extracted pages... 14/14 complete"
3. Analysis results written to `analysis_results` table

**Step 4: Completion Dialog**

1. Show summary:
   - "Extracted 14 pages from 3 PDFs"
   - "Analysis complete"
2. Two options:
   - **"Continue to Conversion"** (primary button, green)
     - Opens ConvertImagesWindow
     - Shows bundle suggestions for extracted pages
     - User can re-bundle differently than original PDFs
   - **"Done"** (secondary button)
     - Close window
     - Return to StartupWindow
     - Pages are analyzed and ready for later conversion

---

## Workflow Path B: Convert Scans (Work with PNGs)

### User clicks "Convert Scans"

**Step 0: AI Bundle Suggestions (PRIMARY INTERFACE)**

1. ConvertImagesWindow opens
2. BundlingService generates bundles from pre-analyzed data
3. **BundleSuggestionsView displayed prominently** with cards showing:
   - Document metadata (type, company, date)
   - Thumbnail strip (visual verification)
   - Confidence badge (GREEN >80%, YELLOW 50-80%, RED <50%)
   - Page count
   - Actions: Accept / Modify / Reject

4. **Bulk Actions Available**:
   - **"Accept All High Confidence" button** (prominent, green)
     - Accepts all bundles with confidence >= 80%
     - Moves accepted bundles directly to Step 2 (metadata review)
     - Most common action for well-scanned documents
   - **"Review Manually" button** (gray, secondary)
     - Skips bundle suggestions entirely
     - Goes directly to old manual stitching workflow

5. **Per-Bundle Actions**:
   - **Accept**: Add bundle to completed groups → skip this bundle to Step 2
   - **Modify**: Load bundle pages into manual stitching view → user can add/remove pages
   - **Reject**: Mark all pages as ungrouped → send to manual stitching pool

### Step 1: Manual Stitching (FALLBACK FOR REJECTED/UNGROUPED PAGES ONLY)

- **Only shown if**: User rejected some bundles OR some pages weren't grouped
- **Purpose**: Handle edge cases the AI couldn't group confidently
- **Same UI as before**: Page-by-page review with Include/Exclude buttons
- **Key difference**: Far fewer pages to review (maybe 5-10 instead of 50)

### Step 2: Metadata Review (ENHANCED)

- Shows ALL accepted bundles (from AI + manual)
- Pre-filled with AI-extracted metadata:
  - Company (editable)
  - Document Type (dropdown, pre-selected)
  - Date (date picker, pre-filled)
- User can edit any fields
- "Apply to All" button for batch editing

### Step 3: Finalization

- PDF generation with progress
- Same as before

---

## Key UX Principles

1. **Minimize User Work**: Most documents should be handled with 1 click ("Accept All High Confidence")
2. **Visual Verification**: Thumbnail strips let users quickly verify bundles are correct
3. **Confidence-Based UI**: Color-coded badges help users prioritize review (focus on yellow/red bundles)
4. **Graceful Degradation**: If AI fails, user can still do everything manually
5. **Progressive Disclosure**: Show AI suggestions first, manual stitching only if needed

---

## Implementation Changes Required

### 1. main.py or StartupWindow.__init__
```python
# Add after app/window initialization
from analysis_service import AnalysisService
from analysis_db import AnalysisDB

analysis_db = AnalysisDB()
analysis_service = AnalysisService(config_manager, analysis_db, metadata_db)

# Show progress dialog
progress_dialog = QProgressDialog("Analyzing documents...", "Cancel", 0, 100, self)
progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)

def progress_callback(status, current, total):
    progress_dialog.setLabelText(f"{status} ({current}/{total})")
    progress_dialog.setValue(int((current / total) * 100))

# Run analysis
analysis_service.scan_all_directories(
    progress_callback=progress_callback,
    incremental=True  # Skip already-analyzed files
)

progress_dialog.close()
```

### 2. ConvertImagesWindow._scan_and_group()

**BEFORE** (broken):
```python
def _scan_and_group(self):
    self.all_files = self.file_processor._get_image_files()
    self._setup_step1_ui()
    self._load_and_show_bundle_suggestions()  # Fails, no data
```

**AFTER** (fixed):
```python
def _scan_and_group(self):
    self.all_files = self.file_processor._get_image_files()

    # Generate bundles from PRE-ANALYZED data
    bundles = self.bundling_service.generate_bundle_recommendations(self.all_files)

    if bundles and len(bundles) > 0:
        # Show AI suggestions as PRIMARY interface
        self._show_bundle_suggestions_view(bundles)
        self.current_step = WorkflowStep.BUNDLE_SUGGESTIONS  # New step
    else:
        # Fallback to manual if no analysis data
        self._setup_step1_ui()
        self._load_next_page_for_stitching()
```

### 3. New Bundle Action Handlers

```python
def _on_bundle_accepted(self, bundle):
    """User accepted an AI bundle → add to completed groups"""
    # Add to completed_groups
    # Remove from all_files
    # Update UI to show remaining bundles

def _on_bundle_modified(self, bundle):
    """User wants to modify bundle → load into manual stitching"""
    # Load bundle pages into current_group
    # Switch to Step 1 (manual stitching) for THIS bundle
    # After modification, return to bundle suggestions

def _on_bundle_rejected(self, bundle):
    """User rejected bundle → pages go to manual stitching pool"""
    # Mark pages as ungrouped
    # Remove bundle from view
    # Pages remain in all_files for manual processing
```

### 4. Step Indicator Update

Change from:
- Step 1 of 3: Document Stitching
- Step 2 of 3: Metadata Extraction
- Step 3 of 3: Finalization

To:
- **Step 0 of 4: AI Bundle Suggestions** (NEW - Primary interface)
- Step 1 of 4: Manual Stitching (Ungrouped pages only)
- Step 2 of 4: Metadata Review
- Step 3 of 4: Finalization

---

## Complete User Scenarios

### Scenario 1: User has only PNG scans
1. App starts → analyzes 47 PNGs → done in 30 seconds
2. User clicks "Convert Scans"
3. Sees 8 bundle suggestions (6 high confidence, 2 medium)
4. Clicks "Accept All High Confidence" → 6 bundles accepted
5. Reviews 2 medium confidence bundles → accepts 1, modifies 1
6. All bundles go to metadata review → PDF generation
7. **Total time: 2 minutes** (vs 15 minutes manual)

### Scenario 2: User has PDFs to unbundle
1. App starts → no PNGs to analyze → instant
2. User clicks "Convert PDFs"
3. Selects 3 PDFs (invoice, statement, receipt)
4. Extraction: 14 pages total
5. Analysis: 14 pages in 20 seconds
6. Clicks "Continue to Conversion"
7. Sees 3 bundle suggestions (original PDFs)
8. Realizes invoice should be split → rejects bundle
9. Manual stitching: splits invoice into 2 separate documents
10. All bundles finalized → new PDFs created
11. **Total time: 3 minutes** (extract + re-bundle)

### Scenario 3: Mixed PNGs and PDFs
1. App starts → analyzes 20 existing PNGs
2. User clicks "Convert PDFs" → extracts 10 pages from 2 PDFs
3. Now has 30 analyzed pages total
4. Clicks "Continue to Conversion"
5. Sees bundle suggestions for all 30 pages
6. Can bundle pages from both PNGs and extracted PDFs together
7. **Maximum flexibility**

## Success Metrics

- **High confidence bundles**: User clicks "Accept All High Confidence" → 90% of work done
- **Medium confidence**: User reviews 3-5 bundles quickly, accepts most with minor modifications
- **Low confidence or no AI data**: Falls back to manual workflow (no worse than before)
- **PDF extraction**: Seamless analysis → bundle suggestions flow
- **Overall**: User time reduced from 10-15 minutes to 2-3 minutes for typical scan batch

---

## Migration Path

1. Task #7: Document this workflow redesign ✓
2. Task #2: Implement startup analysis in main.py
3. Task #1: Update ConvertImagesWindow to use redesigned workflow
4. Task #3: Verify bundle suggestions display properly
5. Task #6: E2E testing with real scan data
