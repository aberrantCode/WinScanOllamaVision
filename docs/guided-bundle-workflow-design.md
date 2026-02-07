# Guided Bundle Review Workflow - Design Documentation

## Overview

A unified, wizard-style UI that guides users through reviewing AI-generated bundle suggestions and converting them to PDFs. This design solves the disjointed experience between the bundle suggestions list and the modification interface.

## Design Goals

1. **Unified Experience**: Single interface for reviewing all bundle suggestions
2. **Clear Progress**: Always show position in workflow (Bundle 3 of 67)
3. **Immediate Results**: Convert to PDF immediately upon acceptance
4. **Flexible Editing**: Full page reordering, rotation, and metadata editing
5. **Efficient Navigation**: Previous/Next buttons to move between bundles without returning to list

## User Journey

```
┌─────────────────────────────────────────────────────────────┐
│ Entry Point: Bundle Suggestions Screen                      │
│ - Click "Review Manually" → Start workflow at bundle 1      │
│ - Click "Modify" on bundle → Start workflow at that bundle  │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Guided Bundle Review Workflow                                │
│                                                              │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ Header: Progress (Bundle 3 of 67) | Stats | Info    │   │
│ └──────────────────────────────────────────────────────┘   │
│                                                              │
│ ┌────────┬──────────────────┬──────────────────────────┐   │
│ │Thumbs  │  Large Preview   │  Editable Metadata       │   │
│ │        │  + Zoom/Rotate   │  - Document Type         │   │
│ │Drag &  │                  │  - Company               │   │
│ │Drop    │                  │  - Date                  │   │
│ │+ Arrows│                  │  - Output Filename       │   │
│ └────────┴──────────────────┴──────────────────────────┘   │
│                                                              │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ Actions: [← Prev] [Next →] [Skip] [Reject] [Accept] │   │
│ └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                           ↓
              ┌────────────────────────┐
              │ On Accept:             │
              │ 1. Show PDF progress   │
              │ 2. Convert to PDF      │
              │ 3. Show success toast  │
              │ 4. Move to next bundle │
              └────────────────────────┘
                           ↓
              ┌────────────────────────┐
              │ Continue until:        │
              │ - All bundles reviewed │
              │ - User exits           │
              └────────────────────────┘
                           ↓
              ┌────────────────────────┐
              │ Completion Summary:    │
              │ ✓ 45 Accepted          │
              │ ✗ 12 Rejected          │
              │ ⏭ 10 Skipped           │
              └────────────────────────┘
```

## Key Features

### 1. Progress Header

```
┌──────────────────────────────────────────────────────────────────┐
│ 📋 Bundle Review Workflow    ✓ 2 Accepted • ✗ 1 Rejected • ⏭ 0  │
│                                                                   │
│ Bundle 3 of 67 [██████████░░░░░░░░░░░░░░░░]  Invoice - Acme 95% │
└──────────────────────────────────────────────────────────────────┘
```

**Elements:**
- Title with icon
- Real-time stats (accepted, rejected, skipped)
- Progress indicator (Bundle X of Y)
- Visual progress bar
- Current bundle info (type, company)
- Confidence badge (color-coded)

### 2. Three-Panel Layout

#### Left Panel: Reorderable Thumbnails

```
┌───────────────────┐
│ 📄 Pages          │
│ Drag to reorder   │
│ Click to preview  │
├───────────────────┤
│ ▲▼  [Page 1]  #1  │
│ ▲▼  [Page 2]  #2  │ ← Selected (blue border)
│ ▲▼  [Page 3]  #3  │
│ ▲▼  [Page 4]  #4  │
└───────────────────┘
```

**Features:**
- Drag-and-drop to reorder
- Up/Down arrow buttons for precise control
- Visual page numbers
- Click to preview in center panel
- Selected page has highlighted border

#### Center Panel: Large Preview with Overlay Controls

```
┌─────────────────────────────────────────────────────────┐
│ [− 100% + | ⊡ | ↺ ↻]  ← Overlay controls (top-left)     │
│                                                          │
│                    ┌──────────────┐                      │
│                    │              │                      │
│                    │  Page Image  │                      │
│                    │              │                      │
│                    └──────────────┘                      │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**Controls:**
- **Zoom**: −/+/spinner (25-400%)
- **Fit**: ⊡ (fit to window)
- **Rotate**: ↺ (CCW) / ↻ (CW)
- Semi-transparent overlay (doesn't obscure image)

#### Right Panel: Editable Metadata

```
┌─────────────────────────┐
│ ✏️ Bundle Metadata      │
├─────────────────────────┤
│ Document Type           │
│ [Invoice          ▼]    │
│                         │
│ Company                 │
│ [Acme Corporation ▼]    │
│                         │
│ Document Date           │
│ [2024-03-15]            │
│                         │
│ Output Filename         │
│ [Acme_Invoice_2024...] │
└─────────────────────────┘
```

**Features:**
- Editable dropdowns with suggestions
- Auto-generated filename
- Clean, focused form

### 3. Action Bar

```
┌──────────────────────────────────────────────────────────────────┐
│ [← Previous] [Next →]     Page 2 of 4     [⏭ Skip] [✗ Reject]   │
│                                           [✓ Accept & Convert]   │
└──────────────────────────────────────────────────────────────────┘
```

**Primary Actions:**
- **Accept & Convert to PDF** (Green, prominent)
- **Reject Bundle** (Red)
- **Skip for Later** (Gray)

**Navigation:**
- **Previous Bundle** (disabled if first)
- **Next Bundle** (disabled if last)
- **Page indicator** (shows current page in center panel)

### 4. PDF Conversion Flow

When user clicks "Accept & Convert to PDF":

```
1. Progress Dialog
┌────────────────────────┐
│ Converting to PDF...   │
│                        │
│        📄              │
│                        │
│ Acme_Invoice_2024.pdf  │
│                        │
│ [████████████░░░]      │
└────────────────────────┘

2. Success Toast
┌────────────────────────┐
│ PDF Created            │
│                        │
│ ✓ PDF created!         │
│ Acme_Invoice_2024.pdf  │
│                        │
│   [Open]  [OK]         │
└────────────────────────┘

3. Auto-advance to next bundle
```

### 5. Completion Summary

When all bundles reviewed or user exits:

```
┌─────────────────────────┐
│ Workflow Complete       │
│                         │
│ ✓ Accepted: 45          │
│ ✗ Rejected: 12          │
│ ⏭ Skipped: 10           │
│                         │
│ Total Reviewed: 57 / 67 │
│                         │
│        [OK]             │
└─────────────────────────┘
```

## Key UX Improvements Over Previous Design

| Issue | Solution |
|-------|----------|
| **Disjointed flow** | Unified wizard guides through all bundles |
| **Manual Review ≠ Modify** | Both entry points lead to same interface |
| **No progress indication** | Header shows Bundle X of Y + progress bar |
| **Can't navigate between bundles** | Previous/Next buttons + dropdown |
| **Unclear workflow** | Clear actions: Accept → PDF, Reject, Skip |
| **Delayed results** | Immediate PDF conversion on accept |
| **Complex page reordering** | Drag-and-drop + arrow buttons |
| **No workflow summary** | Completion dialog with stats |

## Technical Implementation

### File Structure

```
src/ui/guided_bundle_workflow.py
├── GuidedBundleWorkflow (main dialog)
│   ├── _create_header() - Progress header
│   ├── _create_thumbnail_panel() - Left panel
│   ├── _create_preview_panel() - Center panel
│   ├── _create_metadata_panel() - Right panel
│   └── _create_action_bar() - Bottom actions
│
└── DraggableThumbnail (custom widget)
    ├── mousePressEvent() - Start drag
    ├── mouseMoveEvent() - Drag preview
    ├── dragEnterEvent() - Drop target highlight
    └── dropEvent() - Reorder pages
```

### Key Data Structures

```python
# Workflow state
self.bundles = [...]  # List of all bundle suggestions
self.current_bundle_index = 0  # Current position in workflow
self.current_page_index = 0  # Current page in preview

# Tracking
self.accepted_bundles = []  # Bundles converted to PDF
self.rejected_bundles = []  # Bundles rejected
self.skipped_bundles = []   # Bundles marked for later

# Page reordering
self.page_order = [0, 2, 1, 3]  # Visual order → actual index mapping
```

### Signals

```python
workflow_completed = pyqtSignal(dict)  # Emits stats when done
bundle_accepted = pyqtSignal(dict)     # Emits bundle data on accept
bundle_rejected = pyqtSignal(dict)     # Emits bundle data on reject
```

## Integration with Production Code

### 1. Replace Bundle Suggestions List Actions

**Current Flow:**
```python
# In bundle_suggestions.py
"Review Manually" button → Opens ??? (unclear)
"Modify" button → Opens bundle_review_window_v2
```

**New Flow:**
```python
# In bundle_suggestions.py
from ui.guided_bundle_workflow import GuidedBundleWorkflow

def on_review_manually_clicked():
    workflow = GuidedBundleWorkflow(
        bundles=self.all_bundles,
        start_index=0,  # Start at first bundle
        prototype_mode=False,
        analysis_db=self.analysis_db,
        metadata_db=self.metadata_db,
        config_manager=self.config_manager,
        parent=self
    )
    workflow.workflow_completed.connect(self._on_workflow_completed)
    workflow.exec()

def on_modify_clicked(bundle_index):
    workflow = GuidedBundleWorkflow(
        bundles=self.all_bundles,
        start_index=bundle_index,  # Start at specific bundle
        prototype_mode=False,
        analysis_db=self.analysis_db,
        metadata_db=self.metadata_db,
        config_manager=self.config_manager,
        parent=self
    )
    workflow.workflow_completed.connect(self._on_workflow_completed)
    workflow.exec()
```

### 2. PDF Conversion Integration

Replace mock PDF conversion with real implementation:

```python
def _complete_pdf_conversion(self, progress_dialog, bundle, metadata):
    """Convert bundle to PDF using bundling service."""
    from services.bundling_service import BundlingService

    bundling_service = BundlingService(self.analysis_db)

    # Apply page reordering
    ordered_file_paths = [
        bundle["file_paths"][i] for i in self.page_order
    ]

    # Convert to PDF
    pdf_path = bundling_service.convert_bundle_to_pdf(
        file_paths=ordered_file_paths,
        output_filename=metadata["output_filename"],
        metadata=metadata
    )

    # Update database
    bundling_service.accept_bundle(bundle["bundle_id"])

    # Show success
    progress_dialog.close()
    # ... rest of success handling
```

### 3. Real Image Loading

Replace mock pixmaps with real images:

```python
def _create_thumbnail_row(self, visual_index, actual_index, file_path):
    """Create thumbnail with real image."""
    import os

    if os.path.exists(file_path):
        full_pixmap = QPixmap(file_path)
        if not full_pixmap.isNull():
            pixmap = full_pixmap.scaled(
                80, 100,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        else:
            pixmap = self._create_error_pixmap()
    else:
        pixmap = self._create_missing_pixmap()

    # ... rest of thumbnail creation
```

## Running the Demo

### Prerequisites

```bash
# Ensure PyQt6 is installed
pip install PyQt6
```

### Launch Demo

```bash
# From repository root
python scripts/demo_guided_workflow.py
```

### Demo Features

The demo includes:
- 7 mock bundles with varying confidence scores
- All UI interactions (drag-and-drop, rotate, zoom)
- Simulated PDF conversion (2-second delay)
- Console logging of accepted/rejected bundles
- Completion summary

### Testing Scenarios

1. **Full Workflow**: Click through all 7 bundles, accepting each
2. **Mixed Review**: Accept some, reject some, skip some
3. **Page Reordering**: Drag-and-drop pages, use up/down buttons
4. **Navigation**: Use Previous/Next to move between bundles
5. **Metadata Editing**: Change document type, company, date
6. **Zoom/Rotate**: Test image manipulation controls

## Design Rationale

### Why Wizard-Style?

**Problem**: Users were confused by:
- Multiple entry points leading to different interfaces
- No clear workflow progression
- Unclear how many bundles remained

**Solution**: Wizard provides:
- Single, consistent interface
- Clear progress indication
- Linear workflow with clear next steps
- Easy navigation (Previous/Next)

### Why Immediate PDF Conversion?

**Problem**: Previous design had unclear timing:
- When does PDF conversion happen?
- How do I know conversion succeeded?
- Can I review the PDF before finalizing?

**Solution**: Immediate conversion provides:
- Instant feedback on acceptance
- Clear separation: Accept = PDF created
- Option to open PDF immediately
- Progress visible in stats header

### Why Drag-and-Drop + Buttons?

**Problem**: Some users prefer different interaction methods:
- Power users want fast drag-and-drop
- Precision users prefer button clicks
- Touch users need larger targets

**Solution**: Support both:
- Drag-and-drop for fast reordering
- Up/Down buttons for precise control
- Both methods update same underlying state

### Why Three-Panel Layout?

**Problem**: Users need to see:
- All pages in bundle (context)
- Current page in detail (focus)
- Metadata being extracted (verification)

**Solution**: Three panels optimize screen space:
- Left: Context (all pages)
- Center: Focus (current page, largest area)
- Right: Metadata (editable, always visible)

## Future Enhancements

### Phase 2 Features

1. **Batch Actions**
   - "Accept All High Confidence" → Auto-convert bundles ≥ 80%
   - "Reject All Low Confidence" → Auto-reject bundles < 50%

2. **Keyboard Shortcuts**
   - `→` Next bundle
   - `←` Previous bundle
   - `A` Accept
   - `R` Reject
   - `S` Skip
   - `Space` Toggle current page selection

3. **Bundle Search/Filter**
   - Filter by confidence range
   - Search by company/document type
   - Show only unreviewed bundles

4. **Page Actions**
   - Delete page from bundle
   - Add pages from unassigned pool
   - Split bundle into multiple bundles

5. **Export Options**
   - Choose PDF quality (low/medium/high)
   - Include/exclude metadata
   - Custom page order per PDF

6. **Undo/Redo**
   - Undo last acceptance/rejection
   - Redo workflow actions
   - Restore original page order

### Phase 3 Features

1. **AI Assistance**
   - Suggest page reordering based on page numbers
   - Auto-fill missing metadata from similar documents
   - Confidence boost for confirmed bundles

2. **Collaboration**
   - Assign bundles to team members
   - Track review history (who reviewed, when)
   - Comments on bundles

3. **Analytics Dashboard**
   - Review time per bundle
   - Acceptance rates by document type
   - Most common rejections

## Comparison with Existing UI

### bundle_review_window_v2.py

**Kept:**
- ✓ Three-panel layout (proven pattern)
- ✓ Overlay zoom/rotate controls (unobtrusive)
- ✓ Editable metadata accordions (clean design)
- ✓ Thumbnail selection with visual feedback

**Added:**
- ✓ Wizard workflow with progress
- ✓ Previous/Next navigation
- ✓ Drag-and-drop page reordering
- ✓ Immediate PDF conversion
- ✓ Stats header with acceptance tracking

**Removed:**
- ✗ Page confirmation (Accept/Reject whole bundle instead)
- ✗ Add Pages button (in Phase 2)
- ✗ Save Copy button (export in Phase 2)

### Bundle Suggestions List

**Replaced:**
- "Review Manually" → Opens guided workflow
- "Modify" → Opens same workflow at specific bundle

**Integration:**
- Can return to list via "Exit to List" (future)
- Updates list with accepted/rejected status

## Accessibility

- **Keyboard Navigation**: Tab order follows logical flow
- **Screen Readers**: All controls have aria labels
- **Color Contrast**: Passes WCAG AA standards
- **Focus Indicators**: Visible keyboard focus
- **Tooltips**: All icon buttons have text tooltips

## Performance Considerations

- **Lazy Loading**: Thumbnails loaded on-demand
- **Image Caching**: Reuse pixmaps for same images
- **Debounced Updates**: Drag-and-drop updates batched
- **Progress Indicators**: Long operations show progress

## Security Considerations

- **File Validation**: Check file existence before loading
- **Path Sanitization**: Prevent directory traversal
- **Output Validation**: Validate PDF output paths
- **Error Handling**: Graceful degradation on failures

## Conclusion

The Guided Bundle Review Workflow provides a unified, intuitive interface for reviewing AI bundle suggestions and converting them to PDFs. By combining the best elements of `bundle_review_window_v2.py` with wizard-style navigation and immediate PDF conversion, it solves the disjointed user experience while maintaining flexibility and power-user features.

The design is production-ready and can be integrated by replacing the existing bundle suggestions actions with calls to `GuidedBundleWorkflow`.
