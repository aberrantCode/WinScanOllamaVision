# Analysis Status Window Design

## Purpose

Provide transparency into the analysis service's current status, recent runs, and historical results. Users can troubleshoot issues, monitor progress, and understand what the AI has analyzed.

---

## Access Points

### 1. Click Status Banner
When analysis banner is visible, clicking it opens the status window:
```
┌─────────────────────────────────────────────────────────┐
│ 📊 Analyzing documents... 23/47 pages    [Click me!]   │
└─────────────────────────────────────────────────────────┘
```

### 2. New Button on StartupWindow
Add 5th button or info icon:
```
┌─────────────────────────────────┐
│ [Convert Scans]                 │
│ [Convert PDFs]                  │
│ [Change Settings]               │
│ [ℹ Analysis Status]  ← NEW     │
│ [Quit]                          │
└─────────────────────────────────┘
```

Or as an icon next to existing buttons:
```
[Convert Scans] [ℹ]
```

### 3. System Tray Menu
```
Analysis                    ▶
  ├─ Start Analysis
  ├─ View Status...          ← Opens status window
  └─ Cancel
```

---

## Window Layout

### Tabbed Interface (4 tabs)

```
┌─────────────────────────────────────────────────────────────────┐
│ Analysis Status                                       [Refresh] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ [Current] [Recent Runs] [File Details] [Statistics]            │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────────┐│
│ │                                                             ││
│ │              Tab Content Here                               ││
│ │                                                             ││
│ └─────────────────────────────────────────────────────────────┘│
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ [Export Report] [Clear History]                       [Close]  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tab 1: Current Status

Shows real-time information about ongoing or most recent analysis.

```
┌─────────────────────────────────────────────────────────┐
│ Current Analysis                                        │
│                                                         │
│ Status: [Running / Complete / Idle / Failed]           │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐│
│ │ 🟢 Analysis Running                                 ││
│ │                                                     ││
│ │ Progress: 23 / 47 pages (48%)                       ││
│ │ [████████████░░░░░░░░░░]                           ││
│ │                                                     ││
│ │ Current File: invoice_2024_page_003.png            ││
│ │                                                     ││
│ │ Statistics:                                         ││
│ │   Analyzed: 22 (47%)                               ││
│ │   Cached: 18 (82%)                                 ││
│ │   Errors: 1 (4%)                                   ││
│ │                                                     ││
│ │ Elapsed: 1m 23s                                    ││
│ │ Remaining: ~1m 15s                                 ││
│ │ Avg: 3.6s per page                                 ││
│ │                                                     ││
│ │ [Cancel Analysis]                                  ││
│ └─────────────────────────────────────────────────────┘│
│                                                         │
│ Recent Errors (if any):                                │
│ ┌─────────────────────────────────────────────────────┐│
│ │ ❌ invoice_2024_page_007.png                       ││
│ │    Error: Request timeout after 60s                ││
│ │    [Retry] [View Details]                          ││
│ └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

**When Idle:**
```
┌─────────────────────────────────────────────────────────┐
│ Status: Idle                                            │
│                                                         │
│ No analysis currently running.                          │
│                                                         │
│ Last analysis: 2 hours ago                             │
│ - 445 files analyzed                                    │
│ - 423 cached (95%)                                      │
│ - 22 newly analyzed                                     │
│ - 0 errors                                              │
│ - Completed in 1m 47s                                  │
│                                                         │
│ [Start New Analysis]                                    │
└─────────────────────────────────────────────────────────┘
```

---

## Tab 2: Recent Runs

Shows history of last 10 analysis runs with summary.

```
┌─────────────────────────────────────────────────────────┐
│ Recent Analysis Runs                                    │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐│
│ │ ✓ 2 hours ago                           [View]     ││
│ │   445 files • 22 analyzed • 423 cached • 0 errors  ││
│ │   Duration: 1m 47s                                  ││
│ ├─────────────────────────────────────────────────────┤│
│ │ ✓ Yesterday 3:24 PM                     [View]     ││
│ │   438 files • 438 analyzed • 0 cached • 3 errors   ││
│ │   Duration: 21m 15s                                 ││
│ ├─────────────────────────────────────────────────────┤│
│ │ ✓ Yesterday 9:17 AM                     [View]     ││
│ │   412 files • 47 analyzed • 365 cached • 0 errors  ││
│ │   Duration: 3m 02s                                  ││
│ ├─────────────────────────────────────────────────────┤│
│ │ ❌ 2 days ago                           [View]     ││
│ │   401 files • 12 analyzed • 389 cached • 1 error   ││
│ │   Duration: 45s (cancelled)                         ││
│ └─────────────────────────────────────────────────────┘│
│                                                         │
│ [Load More] (showing 4 of 47 runs)                     │
└─────────────────────────────────────────────────────────┘
```

Clicking **[View]** switches to Tab 3 filtered to that run's files.

---

## Tab 3: File Details

Searchable, filterable table of all analyzed files.

```
┌─────────────────────────────────────────────────────────┐
│ File Analysis Details                                   │
│                                                         │
│ Filter: [All ▼]  Search: [________]  [🔍]             │
│        (All / Analyzed / Cached / Failed)               │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐│
│ │ File                    │Status│Confidence│Date     ││
│ ├─────────────────────────┼──────┼──────────┼─────────┤│
│ │ invoice_001.png         │  ✓   │   92%    │2h ago   ││
│ │ invoice_002.png         │  ⚡  │   --     │2h ago   ││  ⚡ = cached
│ │ invoice_003.png         │  ⚡  │   --     │2h ago   ││
│ │ statement_001.png       │  ✓   │   78%    │2h ago   ││
│ │ receipt_042.png         │  ❌  │   --     │2h ago   ││  ❌ = failed
│ │ ...                     │      │          │         ││
│ └─────────────────────────────────────────────────────┘│
│                                                         │
│ Showing 5 of 445 files                                 │
│                                                         │
│ Double-click row to view full analysis details         │
└─────────────────────────────────────────────────────────┘
```

**Double-click opens details dialog:**
```
┌─────────────────────────────────────────────────────────┐
│ Analysis Details: invoice_001.png               [Close] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ File Information:                                       │
│   Path: C:\...\Scans\invoice_001.png                  │
│   Size: 2.3 MB                                          │
│   Modified: 2024-01-15 10:23 AM                        │
│   Hash: abc123def456...                                 │
│                                                         │
│ Analysis Information:                                   │
│   Status: ✓ Success                                    │
│   Analyzed: 2 hours ago                                │
│   Provider: Ollama (qwen3-vl:latest)                   │
│   Processing Time: 4.2 seconds                         │
│   Confidence: 92%                                       │
│                                                         │
│ Extracted Metadata:                                     │
│   Document Type: Invoice                               │
│   Company: Acme Corporation                            │
│   Date: 2024-01-15                                     │
│   Page: 1 of 6                                         │
│   Rotation Needed: No                                  │
│                                                         │
│ Raw Response:                                           │
│ ┌─────────────────────────────────────────────────────┐│
│ │ {                                                   ││
│ │   "document_type": "Invoice",                       ││
│ │   "company": "Acme Corporation",                    ││
│ │   "document_date": "2024-01-15",                    ││
│ │   "page_number": 1,                                 ││
│ │   ...                                               ││
│ │ }                                                   ││
│ └─────────────────────────────────────────────────────┘│
│                                                         │
│ [Re-analyze] [Copy JSON]                     [Close]   │
└─────────────────────────────────────────────────────────┘
```

---

## Tab 4: Statistics

Overall statistics and performance metrics.

```
┌─────────────────────────────────────────────────────────┐
│ Analysis Statistics                                     │
│                                                         │
│ Overall Summary:                                        │
│ ┌─────────────────────────────────────────────────────┐│
│ │ Total Files Analyzed: 445                           ││
│ │ Total Analysis Runs: 47                             ││
│ │ Success Rate: 99.5% (443 / 445)                     ││
│ │ Average Confidence: 87%                             ││
│ │                                                     ││
│ │ Cache Hit Rate: 95.2% (423 / 445)                   ││
│ │ Total Processing Time: 3h 12m                       ││
│ │ Average Time per Page: 3.8 seconds                  ││
│ └─────────────────────────────────────────────────────┘│
│                                                         │
│ Document Type Breakdown:                                │
│ ┌─────────────────────────────────────────────────────┐│
│ │ Invoice:    187 (42%)  [████████████░░░░░░]        ││
│ │ Statement:  143 (32%)  [█████████░░░░░░░░░]        ││
│ │ Receipt:     78 (18%)  [█████░░░░░░░░░░░░░]        ││
│ │ Letter:      25 (6%)   [██░░░░░░░░░░░░░░░░]        ││
│ │ Other:       12 (2%)   [█░░░░░░░░░░░░░░░░░]        ││
│ └─────────────────────────────────────────────────────┘│
│                                                         │
│ Provider Usage:                                         │
│ ┌─────────────────────────────────────────────────────┐│
│ │ Ollama (qwen3-vl:latest):  445 (100%)              ││
│ │ Average time: 3.8s                                  ││
│ └─────────────────────────────────────────────────────┘│
│                                                         │
│ Recent Errors:                                          │
│ ┌─────────────────────────────────────────────────────┐│
│ │ Timeout: 2 files                                    ││
│ │ Connection failed: 0 files                          ││
│ │ Parse error: 0 files                                ││
│ └─────────────────────────────────────────────────────┘│
│                                                         │
│ Database Size: 2.3 MB                                  │
│ Last Cleanup: Never                                    │
│ [Optimize Database]                                     │
└─────────────────────────────────────────────────────────┘
```

---

## Features

### Refresh Button
- Updates all data in real-time
- Shows loading spinner while refreshing
- Auto-refreshes during active analysis (every 1 second)

### Export Report
Exports current view to:
- **CSV**: File list with metadata
- **JSON**: Complete analysis data
- **PDF**: Formatted report with statistics

### Clear History
- Removes old analysis run history
- Options:
  - Clear runs older than X days
  - Clear all history (keeps current analysis data)
  - Clear failed analyses only

### Retry Failed
- Re-analyzes only failed files
- Shows progress dialog
- Updates results in real-time

---

## Implementation

### New File: `src/analysis_status_window.py`

```python
class AnalysisStatusWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.analysis_db = AnalysisDB()
        self.setWindowTitle("Analysis Status")
        self.setMinimumSize(800, 600)
        self._init_ui()

    def _init_ui(self):
        # Create tabbed interface
        # Tab 1: Current status
        # Tab 2: Recent runs
        # Tab 3: File details
        # Tab 4: Statistics
```

### Integration Points

1. **StartupWindow** - Add "Analysis Status" button
2. **ProgressBannerWidget** - Make clickable to open status window
3. **System Tray Menu** - Add "View Status..." option

### Database Queries

New methods in `AnalysisDB`:
```python
def get_recent_runs(limit=10) -> List[Dict]
def get_analysis_statistics() -> Dict
def get_document_type_breakdown() -> Dict[str, int]
def get_failed_analyses() -> List[Dict]
def retry_failed_analyses(file_paths: List[str])
```

---

## User Stories

### Story 1: Monitor Progress
"As a user analyzing 500+ files, I want to see detailed progress so I can estimate completion time and identify problems."

### Story 2: Troubleshoot Errors
"As a user with failed analyses, I want to see error details and retry specific files without re-analyzing everything."

### Story 3: Verify Analysis Quality
"As a user, I want to check the AI's confidence scores and extracted metadata to ensure accuracy before bundling."

### Story 4: Track Performance
"As a user, I want to see cache hit rates and processing times to understand if my LLM configuration is optimal."

---

## Testing

- [ ] Open window from StartupWindow button
- [ ] Open window by clicking banner
- [ ] Current tab updates during analysis
- [ ] Recent runs shows history
- [ ] File details table filterable/searchable
- [ ] Double-click shows full details
- [ ] Statistics accurate
- [ ] Retry failed works
- [ ] Export report generates files
- [ ] Refresh button updates data
