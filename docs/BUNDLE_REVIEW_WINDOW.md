# Bundle Review Window - Implementation Documentation

## Overview

The **Bundle Review Window** (`BundleReviewWindow`) is a prototype PyQt6 dialog for reviewing and editing document bundles. It provides a comprehensive UI for:

- Viewing bundle pages as thumbnails with multiple layout modes
- Inspecting pages in a large preview with zoom, rotation, and pan capabilities
- Managing bundle composition (add/remove pages)
- Confirming or rejecting bundles

**Status:** ✅ Prototype Complete (No backend connections)

## File Location

- **Implementation:** `src/ui/bundle_review_window.py`
- **Test Script:** `scripts/test_bundle_review_window.py`

## Architecture

### Window Type
- `QDialog` (non-modal)
- Default size: 1400×900px
- Three-panel layout using `QSplitter`

### Class Structure

```python
class BundleReviewWindow(QDialog):
    # Signals
    bundle_confirmed = pyqtSignal(dict)
    bundle_rejected = pyqtSignal(dict)

    def __init__(self, bundle_data=None, prototype_mode=True, parent=None)
```

### State Management

```python
self.prototype_mode = True          # No backend connections
self.current_page_index = 0         # Active page index
self.zoom_level = 100               # Zoom percentage (25-400%)
self.rotation_angle = 0             # Rotation in degrees (0-360)
self.pan_offset = QPoint(0, 0)      # Pan offset for zoomed images
self.layout_mode = "flow"           # Thumbnail layout: flow/grid/list
self.confirmed_pages = set()        # User-confirmed page indices
self.removed_pages = set()          # Pages removed from bundle
```

## UI Layout

### Three-Panel Design

```
┌─────────────────────────────────────────────────────────────────┐
│  Header: "Review Bundle: Invoice - Acme Corp"    [Confidence] ✕ │
├──────────────┬──────────────────────────────┬────────────────────┤
│  LEFT PANEL  │      CENTER PANEL            │   RIGHT PANEL      │
│  (300px)     │      (Flexible)              │   (280px)          │
│              │                              │                    │
│ ┌─────────┐  │  ┌────────────────────────┐  │  Page Info Card    │
│ │Layout ▼ │  │  │                        │  │  • Filename        │
│ └─────────┘  │  │   Large Preview        │  │  • Page 3 of 7     │
│              │  │   with Pan/Zoom        │  │  • Metadata        │
│ [Thumbnails] │  │                        │  │                    │
│ ┌──┐ ┌──┐    │  └────────────────────────┘  │  Page Actions      │
│ │ 1│ │ 2│    │                              │  ✓ Confirm Page    │
│ └──┘ └──┘    │  [Zoom] [Rotation] [Save]   │  Remove Page       │
│ ┌──┐ ┌──┐    │                              │  Add Pages...      │
│ │ 3│ │ 4│    │                              │  Re-Analyze        │
│ └──┘ └──┘    │                              │  Delete Page       │
│              │                              │                    │
│              │                              │  ─────────────     │
│              │                              │  Bundle Actions    │
│              │                              │  Save Bundle       │
│              │                              │  Cancel            │
└──────────────┴──────────────────────────────┴────────────────────┘
```

### 1. Header Bar

**Components:**
- Title: "Review Bundle: {document_type} - {company}"
- Confidence badge (color-coded):
  - Green (≥80%)
  - Amber (50-80%)
  - Red (<50%)
- Page count: "X pages"
- Close button (✕)

**Styling:**
- Background: `Colors.GRAY_50`
- Border: 1px solid `Colors.GRAY_200`
- Height: 60px

### 2. Left Panel - Thumbnails (300px fixed)

**Layout Selector:**
- Dropdown with 3 options:
  1. "Flow Layout" - Wraps thumbnails left-to-right, auto-rows
  2. "4-Column Grid" - Fixed 4 columns, vertical scroll
  3. "Vertical List" - Single column, one per row

**Thumbnail Grid:**
- Size: 80×100px (content) + 2px border
- Selected: 2px blue border (`Colors.PRIMARY`)
- Unselected: 1px gray border (`Colors.GRAY_300`)
- Hover: Blue background tint (`Colors.PRIMARY_PALE`)
- Confirmed pages: Show ✓ checkmark overlay

**Thumbnail Features:**
- Click to load in large preview
- Metadata tooltips on hover
- Reuses `ClickableLabel` from `bundle_widgets.py`

### 3. Center Panel - Large Preview (Flexible)

**Preview Container:**
- QLabel with QPixmap
- White background
- 2px border (`Colors.GRAY_200`)
- Padding: 12px
- Min size: 600×500px

**Control Panel (Below Preview):**

**Zoom Controls:**
- Zoom Out (−) button
- Zoom spinner (25-400%, 1% increments)
- Zoom In (+) button
- Fit Width button
- Fit Height button

**Rotation Controls:**
- Rotate CCW 90° (↺)
- Rotate CW 90° (↻)
- Rotate 180° (180°)
- Reset (0°)

**Other:**
- Save Copy button (opens file dialog)

**Pan/Drag Functionality:**
- Active when zoom > 100%
- Cursor changes to hand cursor
- Click and drag to pan
- Mouse events: `mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`

### 4. Right Panel - Actions (280px fixed)

**Page Info Card:**
- Filename (truncated with tooltip)
- "Page X of Y"
- Company, Type, Date
- Confidence score with color indicator

**Page Actions:**
1. **"✓ Confirm Page"** (green) - Mark page as confirmed
2. **"Remove from Bundle"** (red) - Remove from bundle
3. **"Add Pages..."** (blue) - Show UnassignedPagesDialog
4. **"Re-Analyze Page"** (gray) - Show prototype message
5. **"Delete Page"** (red outline) - Confirm and delete

**Bundle Actions:**
- Divider line
- **"Save Bundle"** (green) - Emit `bundle_confirmed` signal
- **"Cancel"** (gray) - Emit `bundle_rejected` signal

## Key Features

### 1. Multiple Layout Modes

Switch between three thumbnail layout modes:

- **Flow Layout** (default): Thumbnails wrap naturally in 3 columns
- **4-Column Grid**: Fixed 4-column grid with vertical scroll
- **Vertical List**: Single column, one thumbnail per row

### 2. Zoom and Pan

**Zoom:**
- Range: 25% to 400%
- Controls: +/− buttons, spinner, fit width/height
- Updates live in preview

**Pan:**
- Enabled when zoom > 100%
- Click and drag to pan
- Cursor changes to open/closed hand
- Pan offset tracked in `self.pan_offset`

### 3. Rotation

**Rotation controls:**
- CCW 90°: Rotate counter-clockwise
- CW 90°: Rotate clockwise
- 180°: Flip upside down
- Reset: Reset to 0°

**Transform logic:**
- Cumulative rotation (0-360°)
- Applied via `QTransform`
- Reset button clears rotation, pan, and zoom

### 4. Page Management

**Confirm Page:**
- Marks page as confirmed (visual checkmark)
- Tracked in `self.confirmed_pages` set
- Shows confirmation dialog

**Remove Page:**
- Removes from current bundle
- Tracked in `self.removed_pages` set
- Auto-advances to next page
- Shows confirmation dialog

**Add Pages:**
- Opens `UnassignedPagesDialog`
- Select multiple pages with checkboxes
- Adds selected pages to bundle
- Updates thumbnail grid

**Delete Page:**
- Permanently delete (same as remove in prototype)
- Shows confirmation dialog

### 5. Save Copy

**Save Copy button:**
- Opens `QFileDialog` for save location
- Saves current pixmap with transforms applied
- Supports PNG and JPEG formats

## Mock Data Structure

### Bundle Data Format

```python
{
    'bundle_id': 'mock_bundle_001',
    'file_paths': [
        'mock_bundle_page_1.png',
        'mock_bundle_page_2.png',
        # ... 7 pages total
    ],
    'company': 'Acme Corporation',
    'document_type': 'Invoice',
    'document_date': '2024-03-15',
    'confidence_score': 0.87,
    'total_pages': 7,
    'analyses': [
        {
            'file_path': 'mock_bundle_page_1.png',
            'company': 'Acme Corporation',
            'document_type': 'Invoice',
            'page_number': 1,
            'total_pages': 7,
            'confidence_score': 0.85,
            'legibility': 'clear',
            'rotation_needed': False
        },
        # ... per-page metadata
    ]
}
```

### Placeholder Images

Since this is a prototype, mock images are generated as colored pixmaps:

```python
pixmap = QPixmap(80, 100)
pixmap.fill(QColor(220, 230, 245))  # Light blue
painter = QPainter(pixmap)
painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Page 1")
painter.end()
```

## UnassignedPagesDialog

### Purpose
Show pages NOT assigned to any bundle for adding to the current bundle.

### UI Layout
- QDialog with grid of thumbnails (4 columns)
- Checkboxes on each thumbnail for multi-select
- "Add Selected (X)" button (updates count dynamically)
- "Cancel" button

### Mock Data
- Generates 12 mock unassigned pages
- Each has company, document type, page number
- Placeholder pixmaps with unique colors

### Usage

```python
dialog = UnassignedPagesDialog(self)
dialog.pages_selected.connect(self._on_pages_added)
dialog.exec()

# When user clicks "Add Selected":
# Signal emits: list of file paths
```

## Signals

### bundle_confirmed

Emitted when user clicks "Save Bundle".

**Payload:**
```python
{
    'bundle_id': 'mock_bundle_001',
    'file_paths': [...],  # Remaining pages (removed ones excluded)
    'user_edits': {
        'removed_pages': [2, 5],      # Indices
        'confirmed_pages': [0, 1, 3]  # Indices
    }
}
```

### bundle_rejected

Emitted when user clicks "Cancel".

**Payload:**
```python
{
    'bundle_id': 'mock_bundle_001',
    # ... original bundle_data unchanged
}
```

## Key Methods

### UI Initialization

| Method | Purpose |
|--------|---------|
| `_init_ui()` | Main UI setup with QSplitter |
| `_create_header_bar()` | Title + badges + close |
| `_create_thumbnail_panel()` | Layout selector + grid |
| `_create_large_preview()` | Preview + controls |
| `_create_control_panel()` | Zoom + rotation + save |
| `_create_action_panel()` | Page/bundle actions |

### Data & Display

| Method | Purpose |
|--------|---------|
| `_load_bundle()` | Populate thumbnails from bundle_data |
| `_create_mock_bundle()` | Generate 7 mock pages |
| `_create_thumbnail(file_path, index)` | Create ClickableLabel |
| `_display_page(index)` | Load page in large preview |
| `_apply_transform(pixmap)` | Apply zoom + rotation + pan |
| `_update_page_info(index)` | Update info card |
| `_populate_thumbnails()` | Refresh thumbnail grid |

### Interaction Handlers

**Thumbnails:**
- `_on_thumbnail_clicked(index)` - Make page active
- `_on_layout_changed(layout_name)` - Switch grid layout

**Zoom:**
- `_on_zoom_in()`, `_on_zoom_out()`
- `_on_zoom_percent_changed(value)`
- `_on_fit_width()`, `_on_fit_height()`

**Rotation:**
- `_on_rotate_ccw()`, `_on_rotate_cw()`
- `_on_rotate_180()`, `_on_reset_rotation()`

**Pan:**
- `mousePressEvent(event)` - Start drag
- `mouseMoveEvent(event)` - Update pan offset
- `mouseReleaseEvent(event)` - End drag
- `_update_cursor()` - Hand cursor when zoomed

**Page Actions:**
- `_on_confirm_page()` - Visual feedback
- `_on_remove_page()` - Remove from bundle
- `_on_add_pages()` - Show UnassignedPagesDialog
- `_on_reanalyze_page()` - Show message
- `_on_delete_page()` - Confirm + delete

**Bundle Actions:**
- `_on_save_copy()` - QFileDialog, save image
- `_on_save_bundle()` - Emit signal, close
- `_on_reject_bundle()` - Emit signal, close

## Reused Components

| Feature | Source | Method/Class |
|---------|--------|--------------|
| ClickableLabel | `bundle_widgets.py:23-34` | `ClickableLabel` |
| Button styles | `styles.py:94-214` | `get_*_button_style()` |
| Colors | `styles.py:6-54` | `Colors` class |

## Testing

### Test Script

Run the window with mock data:

```bash
python scripts/test_bundle_review_window.py
```

### Manual Testing Checklist

**Layout:**
- [ ] Window opens at 1400×900px
- [ ] Three panels visible with correct widths
- [ ] Layout selector shows all 3 options
- [ ] Switching layouts works smoothly

**Thumbnails:**
- [ ] 7 mock thumbnails display
- [ ] Clicking thumbnail updates large preview
- [ ] Selected thumbnail has blue border
- [ ] Hover effects work
- [ ] Metadata tooltips show on hover

**Large Preview:**
- [ ] Initial page displays correctly
- [ ] Zoom in/out works (25%-400% range)
- [ ] Fit Width/Height work
- [ ] Rotation buttons rotate correctly
- [ ] Pan/drag works when zoomed >100%
- [ ] Cursor changes to hand when pannable

**Controls:**
- [ ] All zoom buttons respond
- [ ] Spinner updates zoom level
- [ ] All rotation buttons respond
- [ ] Save Copy opens file dialog

**Actions:**
- [ ] Page info card shows correct data
- [ ] Confirm page gives visual feedback
- [ ] Remove page updates bundle
- [ ] Add Pages shows unassigned dialog
- [ ] Delete page shows confirmation
- [ ] Save Bundle emits signal
- [ ] Cancel closes window

**Edge Cases:**
- [ ] Single page bundle works
- [ ] Large bundle (15+ pages) scrolls properly
- [ ] Remove last page handles gracefully
- [ ] Zoom at boundaries (25% and 400%) works

## Future Backend Integration

When connecting to real data (set `prototype_mode=False`):

### 1. Data Loading

Replace mock data with real bundle data:

```python
from services.bundling_service import BundlingService

bundling_service = BundlingService(analysis_db)
bundle_data = bundling_service.get_bundle(bundle_id)

window = BundleReviewWindow(bundle_data, prototype_mode=False)
```

### 2. Re-Analyze Page

Wire to `AnalysisService`:

```python
def _on_reanalyze_page(self):
    file_path = self.bundle_data['file_paths'][self.current_page_index]

    # Re-analyze via service
    result = analysis_service.analyze_specific_files([file_path])

    # Update bundle data
    self.bundle_data['analyses'][self.current_page_index] = result[0]
    self._update_page_info(self.current_page_index)
```

### 3. Save Bundle

Wire to `BundleRepository`:

```python
def _on_save_bundle(self):
    remaining_paths = [
        fp for i, fp in enumerate(self.bundle_data['file_paths'])
        if i not in self.removed_pages
    ]

    # Save to database
    bundle_repo.update_bundle(
        bundle_id=self.bundle_data['bundle_id'],
        file_paths=remaining_paths,
        user_confirmed=True
    )

    self.bundle_confirmed.emit(...)
    self.accept()
```

### 4. Delete Page

Wire to `AnalysisDB`:

```python
def _on_delete_page(self):
    # Confirm with user...

    file_path = self.bundle_data['file_paths'][self.current_page_index]

    # Delete from database
    analysis_db.delete_analysis(file_path)

    # Remove from bundle
    self._on_remove_page()
```

### 5. Unassigned Pages

Replace mock data with real database query:

```python
class UnassignedPagesDialog(QDialog):
    def _load_unassigned_pages(self):
        # Get pages not in any bundle
        unassigned = analysis_db.get_unbundled_pages()

        # Create thumbnails
        for page in unassigned:
            self._create_thumbnail(page)
```

## Integration with Main UI

### Opening from Bundle Management

```python
from ui.bundle_review_window import BundleReviewWindow

# In bundle management code:
def on_review_bundle_clicked(bundle_id):
    bundle_data = bundling_service.get_bundle(bundle_id)

    window = BundleReviewWindow(bundle_data, parent=self)
    window.bundle_confirmed.connect(self._on_bundle_updated)
    window.bundle_rejected.connect(self._on_bundle_cancelled)
    window.show()

def _on_bundle_updated(self, result):
    # Refresh bundle list
    self.refresh_bundles()

    # Show success message
    QMessageBox.information(self, "Success", "Bundle updated successfully!")
```

## Styling

### Color Palette

All colors use the `Colors` class from `styles.py`:

- **Primary:** `Colors.PRIMARY` (#2563EB)
- **Success:** `Colors.SUCCESS` (#059669)
- **Danger:** `Colors.DANGER` (#DC2626)
- **Gray shades:** `Colors.GRAY_50` through `Colors.GRAY_900`

### Button Styles

- Primary: `get_primary_button_style()`
- Success: `get_success_button_style()`
- Danger: `get_danger_button_style()`
- Secondary: `get_secondary_button_style()`

### Layout Spacing

- Window margins: 0px (uses splitter)
- Panel padding: 12-15px
- Section spacing: 10-15px
- Button spacing: 12px

## Known Limitations (Prototype Mode)

1. **No real images** - Uses colored placeholder pixmaps
2. **No backend** - All data is mocked
3. **No persistence** - Changes lost on close (unless signals handled)
4. **Simplified fit width/height** - Uses fixed zoom percentages
5. **Pan boundaries** - No boundary checking (can pan off-canvas)
6. **Re-analyze** - Shows message instead of actual analysis

## Next Steps

1. **User Testing** - Get feedback on layout and interactions
2. **Real Images** - Test with actual scanned documents
3. **Backend Integration** - Connect to services and database
4. **Polish** - Refine pan boundaries, add keyboard shortcuts
5. **Validation** - Add bundle validation logic
6. **Undo/Redo** - Add undo stack for actions

## Success Criteria

✅ **Prototype Complete When:**

1. Window opens with mock data showing 7 pages
2. Can click thumbnails to change active page
3. Can zoom, rotate, and pan the active page
4. Can switch between Flow/Grid/List layouts
5. Can click all action buttons (with appropriate feedback)
6. Save Copy opens file dialog
7. Add Pages shows unassigned pages dialog
8. All UI follows existing styling conventions
9. No backend dependencies (all mock data)
10. Ready for user feedback and iteration

**Status:** ✅ All criteria met!

## Additional Resources

- **Plan Document:** See original implementation plan for detailed specifications
- **Related Files:**
  - `src/ui/bundle_widgets.py` - Thumbnail components
  - `src/ui/gui.py` - Zoom/rotation reference
  - `src/ui/styles.py` - Button styles and colors
  - `src/services/bundling_service.py` - Bundle data structure (future)
  - `src/db/analysis_db.py` - Database queries (future)

## Questions & Feedback

For questions or feedback on the Bundle Review Window:
1. Test the prototype: `python scripts/test_bundle_review_window.py`
2. Provide feedback on layout, interactions, and features
3. Suggest improvements for backend integration
