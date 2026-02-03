# Analysis Service UX Flow & Error Handling

## Startup Analysis UX

### Option A: Non-Blocking with Skip (RECOMMENDED)

**Flow:**
1. App starts → Main window appears immediately
2. **Non-modal progress banner** at top of StartupWindow:
   ```
   [📊 Analyzing documents...] [23 / 47 pages] [Cancel] [▼ Details]
   ```
3. User can:
   - **Continue using app** while analysis runs in background
   - Click "Details" to see:
     - Current file being analyzed: `invoice_2024_page_003.png`
     - Estimated time remaining: `~30 seconds`
     - Success/failure count: `22 succeeded, 1 failed`
   - Click "Cancel" to stop analysis
     - Already-analyzed pages are kept
     - Remaining pages skipped
     - User can still use app with partial data
4. When complete:
   - Banner changes to: `[✓ Analysis complete] [47 pages analyzed] [2 minutes ago] [Dismiss]`
   - Auto-dismiss after 5 seconds
5. All 4 buttons remain usable throughout

**Advantages:**
- Non-blocking - user isn't forced to wait
- Can click "Convert Scans" immediately (works with partial data)
- Can click "Change Settings" to adjust LLM settings if analysis is slow
- Professional feel

---

### Option B: Modal Dialog with Cancel (Alternative)

**Flow:**
1. App starts → Splash screen or blank
2. **Modal progress dialog** appears:
   ```
   Analyzing Documents

   [████████░░░░░░] 23 / 47 pages (48%)

   Current: invoice_2024_page_003.png
   Elapsed: 45s | Remaining: ~30s

   [Cancel]  [Run in Background]
   ```
3. User can:
   - **Wait** for completion (blocked from app)
   - Click "Cancel" → Analysis stops, app opens with no data
   - Click "Run in Background" → Converts to Option A (non-blocking banner)
4. When complete:
   - Dialog closes automatically
   - StartupWindow appears with 4 buttons

**Advantages:**
- Clear focus on analysis task
- User sees progress prominently
- Can switch to non-blocking mode

**Disadvantages:**
- Blocks app usage initially
- More disruptive

---

## Recommended: Option A (Non-Blocking Banner)

### Implementation Details

**Banner Component:**
```python
class AnalysisProgressBanner(QWidget):
    """
    Non-modal banner showing analysis progress at top of StartupWindow
    """
    def __init__(self, parent):
        # Fixed height: 60px
        # Background: Light blue (#E3F2FD)
        # Auto-dismisses when complete
        # Expandable details panel
```

**Visual Design:**
```
┌─────────────────────────────────────────────────────────┐
│ [📊] Analyzing documents...                             │
│                                                          │
│ [██████████░░░░░] 23 / 47 pages (48%)                   │
│                                                          │
│ [Cancel] [▼ Details]                              1m 23s│
└─────────────────────────────────────────────────────────┘

Details expanded:
┌─────────────────────────────────────────────────────────┐
│ [📊] Analyzing documents...                             │
│                                                          │
│ [██████████░░░░░] 23 / 47 pages (48%)                   │
│                                                          │
│ Current: invoice_2024_page_003.png                      │
│ Succeeded: 22 | Failed: 1                               │
│                                                          │
│ [Cancel] [▲ Hide Details] [View Errors]           1m 23s│
└─────────────────────────────────────────────────────────┘
```

---

## Error Handling Scenarios

### Error 1: LLM Service Connection Failure

**Scenario:** Ollama not running, wrong URL, or network issue

**Detection:** Before analysis starts, AnalysisService pings LLM provider

**User Experience:**
1. Banner shows: `[⚠] Cannot connect to LLM service`
2. Error dialog appears:
   ```
   LLM Connection Failed

   Could not connect to Ollama at http://localhost:11434

   Possible causes:
   • Ollama is not running
   • Wrong URL in settings
   • Firewall blocking connection

   [Open Settings] [Retry Connection] [Skip Analysis]
   ```
3. User options:
   - **Open Settings**: Go to LLM Provider settings tab
   - **Retry Connection**: Try again after fixing issue
   - **Skip Analysis**: Continue without analysis (manual workflow only)

**Fallback:**
- App remains usable
- "Convert Scans" button works (manual stitching only)
- No bundle suggestions available

---

### Error 2: Individual Page Analysis Failures

**Scenario:** Some pages fail (corrupted image, LLM timeout, parsing error)

**User Experience:**
1. Analysis continues for other pages (don't fail entire batch)
2. Failed pages tracked: `succeeded: 45, failed: 2`
3. Banner shows warning icon when complete:
   ```
   [⚠] Analysis complete (2 pages failed)
   [View Details]
   ```
4. Details view shows:
   ```
   Failed Pages:
   • invoice_2024_page_007.png - Timeout after 60s
   • receipt_scan_042.png - Invalid image format

   [Retry Failed Pages] [Continue Without These]
   ```
5. User options:
   - **Retry Failed Pages**: Try again (maybe increase timeout)
   - **Continue Without These**: Proceed, failed pages go to manual stitching

**Fallback:**
- Successful analyses are kept
- Failed pages appear as "unanalyzed" in manual stitching
- Bundles generated from successful analyses only

---

### Error 3: Analysis Timeout

**Scenario:** Single page taking too long (>60 seconds default)

**User Experience:**
1. Progress shows: "Analyzing page 23/47... (45s)"
2. At 60s, auto-timeout occurs
3. Banner updates: "Page 23 timed out, continuing..."
4. That page marked as failed, analysis continues

**Settings:**
- Timeout configurable in Settings → LLM Provider → Timeout
- Default: 60 seconds per page
- Range: 30-300 seconds

---

### Error 4: User Cancels Analysis

**Scenario:** User clicks "Cancel" during analysis

**User Experience:**
1. Immediate stop (current page finishes, remaining skipped)
2. Confirmation dialog:
   ```
   Cancel Analysis?

   23 of 47 pages have been analyzed.

   You can:
   • Use analyzed pages for bundle suggestions (partial data)
   • Continue manually for remaining pages

   [Yes, Cancel] [No, Continue Analysis]
   ```
3. If confirmed:
   - Banner disappears
   - Analyzed pages kept in database
   - Remaining pages unanalyzed
   - App fully usable

**Fallback:**
- Bundle suggestions work with partial data
- Unanalyzed pages go to manual stitching
- Can re-run analysis later

---

### Error 5: Complete Analysis Failure

**Scenario:** Zero pages successfully analyzed

**User Experience:**
1. Error dialog:
   ```
   Analysis Failed

   Could not analyze any pages.

   Error: [specific error message]

   You can still use the app with manual document stitching.

   [View Logs] [Open Settings] [Continue Manually]
   ```
2. User options:
   - **View Logs**: Show detailed error log for troubleshooting
   - **Open Settings**: Adjust LLM settings
   - **Continue Manually**: Proceed with manual workflow (no AI features)

**Fallback:**
- Full manual workflow available
- No bundle suggestions
- App fully functional (just no AI assistance)

---

## PDF Extraction Analysis

### Blocking Behavior (Acceptable)

**Why blocking is OK here:**
- User explicitly triggered extraction
- Immediate feedback desired
- Typically fast (10-20 pages)
- User wants to see results before next action

**Flow:**
1. User clicks "Extract Pages" in ConvertPDFsWindow
2. **Modal progress dialog** (blocking):
   ```
   Extracting and Analyzing PDFs

   Step 1/2: Extracting pages... [█████████░] 8/14 pages
   Current: invoice_2024.pdf (page 3/6)

   [Cancel]
   ```
3. Extraction completes → immediately transitions to:
   ```
   Extracting and Analyzing PDFs

   Step 2/2: Analyzing pages... [████░░░░░░] 4/14 pages
   Current: invoice_2024_page_003.png

   [Cancel]
   ```
4. Analysis completes → Success dialog:
   ```
   Extraction Complete

   ✓ Extracted 14 pages from 3 PDFs
   ✓ Analysis complete

   [Continue to Conversion] [Done]
   ```

**Error Handling:**
- PDF extraction fails: Show error, allow retry or skip that PDF
- Analysis fails: Offer "Continue Anyway" (manual workflow for extracted pages)
- User cancels: Keep extracted PNGs, skip analysis

---

## Settings Integration

### Analysis Settings Panel

Add to Settings → General tab:

```
┌─────────────────────────────────────────────────┐
│ Automatic Analysis                              │
│                                                  │
│ [✓] Analyze documents on startup                │
│                                                  │
│ [✓] Analyze immediately after PDF extraction    │
│                                                  │
│ Timeout per page: [60] seconds                  │
│                                                  │
│ [✓] Show detailed progress                      │
│                                                  │
│ [Re-analyze All Documents]                      │
│     Force re-analysis of all pages              │
└─────────────────────────────────────────────────┘
```

---

## Analysis Modes

### Mode 1: Incremental Analysis (Default for Startup)

**When**: App starts with "Analyze on startup" enabled

**Behavior**:
- Scans all PNG files in source directories
- **Checks database for existing analysis**:
  - File hash matches cached analysis → SKIP (instant)
  - File modified or new → ANALYZE
- Progress shows: "Analyzing 12 new pages (88 cached)"
- Fast for users with mostly-analyzed backlogs

**Settings Control**:
```
Settings → General → Automatic Analysis

[✓] Analyze documents on startup
    Mode: [Incremental (new/modified only) ▼]
```

---

### Mode 2: Full Re-Analysis (User-Triggered)

**When**: User explicitly requests via UI

**Behavior**:
- Ignores all cached analysis
- Re-analyzes EVERY file from scratch
- Overwrites existing database entries
- Progress shows: "Re-analyzing 100 pages (0 cached)"
- Useful for:
  - First-time setup with existing backlog
  - After changing LLM provider/model
  - After updating analysis prompts
  - Fixing corrupted/incorrect analysis

**Trigger Locations**:

1. **Settings → General Tab**:
   ```
   ┌─────────────────────────────────────────┐
   │ Analysis Actions                        │
   │                                         │
   │ [Re-analyze All Documents]              │  ← Full re-analysis
   │   Force re-analysis of all pages,       │
   │   ignoring cached results                │
   │                                         │
   │ [Analyze Unanalyzed Only]               │  ← Backlog analysis
   │   Analyze files that have never been    │
   │   analyzed (skips cached)               │
   │                                         │
   │ [Clear Analysis Cache]                  │  ← Nuclear option
   │   Delete all cached analysis results    │
   │   (requires re-analysis)                │
   └─────────────────────────────────────────┘
   ```

2. **StartupWindow Banner** (when unanalyzed files exist):
   ```
   ┌───────────────────────────────────────────────────────┐
   │ ⚠ 73 unanalyzed pages found                          │
   │                                                       │
   │ [Analyze Now] [Analyze Later] [Don't Show Again]     │
   └───────────────────────────────────────────────────────┘
   ```

3. **Right-Click Tray Menu**:
   ```
   Analysis                    ▶
     ├─ Analyze New/Modified
     ├─ Re-analyze All          ← Full re-analysis
     └─ Cancel
   ```

---

### Mode 3: Selective Analysis (Advanced)

**When**: User wants to analyze specific files only

**UI**: ConvertImagesWindow → Image Gallery

**Behavior**:
```
Left Panel (Image Gallery):
┌────────────────────────┐
│ Available Pages        │
│                        │
│ [Filter: Unanalyzed ▼] │  ← Filter options:
│                        │     • All
│                        │     • Analyzed
│                        │     • Unanalyzed
│                        │     • Failed
│                        │
│ [ ] img_001.png  🟢   │  🟢 = Analyzed
│ [ ] img_002.png  ⭘   │  ⭘ = Unanalyzed
│ [✓] img_003.png  ⭘   │  🔴 = Failed
│ [✓] img_004.png  🟢   │
│ [ ] img_005.png  🔴   │
│                        │
│ [Select All Unanalyzed]│
│                        │
│ [Analyze Selected]     │  ← Right-click or button
└────────────────────────┘
```

**Use Cases**:
- User has 1000 files, only wants to analyze 50 specific ones
- Re-analyze failed pages only
- Analyze newly scanned batch without touching old files

---

## First-Time Setup: Backlog Detection

### Scenario: User Has Existing Scans

**Problem**: User installs app, has 200 existing PNGs, never analyzed

**Solution: Smart Detection + User Choice**

1. **App first starts**:
   - Checks database: 0 analyzed pages
   - Scans directories: 200 PNG files found
   - Calculates: 200 unanalyzed files

2. **Welcome Dialog Appears**:
   ```
   ┌─────────────────────────────────────────────────────┐
   │ Welcome to WinScanLLM                               │
   │                                                     │
   │ Found 200 unanalyzed pages in scan folder.         │
   │                                                     │
   │ Would you like to analyze them now?                │
   │                                                     │
   │ Analysis will take approximately 10-15 minutes     │
   │ and will enable AI-powered bundle suggestions.     │
   │                                                     │
   │ You can:                                           │
   │ • Analyze now (recommended)                        │
   │ • Analyze later (via Settings)                     │
   │ • Skip analysis (manual workflow only)             │
   │                                                     │
   │ [Analyze Now] [Analyze Later] [Skip]               │
   └─────────────────────────────────────────────────────┘
   ```

3. **User Choices**:
   - **Analyze Now**:
     - Shows progress banner
     - Blocks access to "Convert Scans" until complete
     - "Convert PDFs" and "Settings" remain available
   - **Analyze Later**:
     - Banner persists: "73 unanalyzed pages [Analyze Now]"
     - User can click anytime
     - Can also use Settings → "Re-analyze All"
   - **Skip**:
     - No banner shown
     - Manual workflow available
     - Can analyze later via Settings

---

## Progress Estimation

### Calculating Time Remaining

**Factors**:
- Average time per page (measured during analysis)
- Pages remaining
- Cache hit rate

**Formula**:
```python
pages_remaining = total_pages - current_page
avg_time_per_page = total_elapsed / current_page
estimated_time = pages_remaining * avg_time_per_page
```

**Display**:
```
Analyzing documents... 23 / 200 pages (11%)

Elapsed: 2m 15s | Remaining: ~17m 30s
Average: 5.8s per page

[Cancel] [Run in Background] [▼ Details]
```

**Accuracy Improves Over Time**:
- First 5 pages: No estimate shown ("Calculating...")
- After 10 pages: Initial estimate (±50%)
- After 25 pages: Good estimate (±20%)
- After 50 pages: Accurate estimate (±10%)

---

## Handling Interruptions

### User Cancels Mid-Analysis

**Scenario**: Started analyzing 200 pages, cancels at page 50

**Behavior**:
1. Immediate stop (current page finishes)
2. Database contains 50 analyzed pages
3. Next startup:
   - Detects: 50 analyzed, 150 unanalyzed
   - Banner: "150 unanalyzed pages [Resume Analysis]"
4. If user clicks "Resume Analysis":
   - Continues from page 51 (incremental mode)
   - No re-analysis of first 50 pages

### App Crash During Analysis

**Scenario**: App crashes at page 50/200

**Recovery**:
1. Next startup:
   - Checks database: 49 complete, 1 incomplete (page 50)
   - Marks incomplete analysis as failed
2. Auto-resume prompt:
   ```
   ┌─────────────────────────────────────────────────────┐
   │ Previous analysis incomplete                        │
   │                                                     │
   │ 49 pages analyzed successfully                     │
   │ 151 pages remaining                                │
   │                                                     │
   │ [Resume Analysis] [Start Over] [Cancel]            │
   └─────────────────────────────────────────────────────┘
   ```

---

## Performance Considerations

### Large Backlogs (1000+ pages)

**Recommendations**:

1. **Batch Processing**:
   - Process in batches of 100 pages
   - Show: "Batch 1/10: 100 pages"
   - Commit to database after each batch
   - More resilient to crashes

2. **Priority Ordering**:
   - Analyze most recent files first
   - User likely needs recent scans
   - Banner: "Analyzing recent files first..."

3. **Overnight Processing**:
   - User can start analysis and minimize to tray
   - Leave running overnight
   - Get notification in morning

4. **Parallel Processing** (Future Enhancement):
   - Process multiple pages simultaneously
   - Requires thread-safe LLM calls
   - Can cut time by 50-75%

---

## Settings: Analysis Control

### Complete Settings Panel

```
┌─────────────────────────────────────────────────────────┐
│ Automatic Analysis                                      │
│                                                          │
│ [✓] Analyze documents on startup                        │
│     Mode: [Incremental (new/modified only) ▼]           │
│           Options:                                       │
│           • Incremental (new/modified only)              │
│           • Full (re-analyze all)                        │
│           • None (skip startup analysis)                 │
│                                                          │
│ [✓] Analyze immediately after PDF extraction            │
│                                                          │
│ Timeout per page: [60] seconds                          │
│                                                          │
│ [✓] Show detailed progress                              │
│                                                          │
│ Priority order: [Recent files first ▼]                  │
│                 Options:                                 │
│                 • Recent files first (default)           │
│                 • Oldest files first                     │
│                 • Alphabetical                           │
│                 • Random                                 │
│                                                          │
├─────────────────────────────────────────────────────────┤
│ Manual Analysis Actions                                 │
│                                                          │
│ [Re-analyze All Documents]                              │
│   Force re-analysis of all pages, ignoring cache        │
│   (Useful after changing LLM settings)                  │
│                                                          │
│ [Analyze Unanalyzed Only]                               │
│   Analyze files that have never been analyzed           │
│   (Useful for handling backlog)                         │
│                                                          │
│ [Clear Analysis Cache]                                  │
│   Delete all cached analysis results                    │
│   (Next analysis will process everything)               │
│                                                          │
├─────────────────────────────────────────────────────────┤
│ Current Status                                          │
│                                                          │
│ Total files: 200                                        │
│ Analyzed: 150 (75%)                                     │
│ Unanalyzed: 50 (25%)                                    │
│ Failed: 0                                               │
│                                                          │
│ Database size: 2.3 MB                                   │
│ Last analysis: 2 hours ago                              │
│                                                          │
│ [View Details →]                                        │
└─────────────────────────────────────────────────────────┘
```

---

## Summary: Analysis Strategy

**For Backlog Users (Existing Scans)**:
1. First launch: Detect unanalyzed files → offer to analyze
2. User can analyze now or later
3. Settings provides "Re-analyze All" and "Analyze Unanalyzed Only"
4. Progress is persistent (interruptions don't lose work)

**For Regular Users (New Scans)**:
1. Incremental analysis on startup (fast, only new files)
2. Cached results used when possible
3. Minimal delay for typical workflows

**User Control**:
- Can disable startup analysis entirely
- Can trigger manual analysis anytime
- Can selectively analyze specific files
- Can clear cache and start fresh

---

## Summary: Key UX Principles

1. **Non-Blocking**: User can always use the app
2. **Cancellable**: User can stop analysis anytime
3. **Informative**: Clear progress and status
4. **Graceful Degradation**: Errors don't break the app
5. **Partial Success**: Use what worked, skip what failed
6. **User Control**: Settings to disable/configure analysis
7. **Feedback**: Always show what's happening and why

**Result:** Professional, responsive app that handles analysis intelligently without frustrating users.
