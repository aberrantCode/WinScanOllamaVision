# Bundle Review Window - Testing Guide

## Quick Start

```bash
# Launch the prototype window
python scripts/test_bundle_review_window.py
```

## Test Scenarios

### 1. Layout and Initial Display

**Steps:**
1. Launch the test script
2. Verify window opens at correct size (~1400×900px)
3. Check three panels are visible with correct proportions

**Expected:**
- Header shows "Review Bundle: Invoice - Acme Corporation"
- Confidence badge shows "87%" in green
- Page count shows "7 pages"
- Left panel shows 7 thumbnails in Flow Layout
- Center panel shows "Page 1" preview
- Right panel shows page info card

### 2. Thumbnail Interactions

**Test 2.1: Click to Select**
1. Click thumbnail #1
2. Click thumbnail #3
3. Click thumbnail #7

**Expected:**
- Clicked thumbnail gets blue 2px border
- Large preview updates to show selected page
- Page info card updates (Page X of 7)

**Test 2.2: Hover Effects**
1. Hover over each thumbnail

**Expected:**
- Background changes to light blue on hover
- Tooltip appears showing metadata

**Test 2.3: Layout Switching**
1. Change layout dropdown to "4-Column Grid"
2. Change to "Vertical List"
3. Change back to "Flow Layout"

**Expected:**
- Flow: 3 columns, wraps naturally
- Grid: 4 columns, fixed layout
- List: 1 column, vertical stack
- All thumbnails remain selectable

### 3. Zoom Controls

**Test 3.1: Zoom Buttons**
1. Click "+" button 4 times
2. Click "−" button 2 times

**Expected:**
- Each + click: zoom increases by 25%
- Each − click: zoom decreases by 25%
- Spinner shows correct percentage
- Preview scales accordingly

**Test 3.2: Zoom Spinner**
1. Type "200" in spinner
2. Type "50"
3. Try to type "500" (should clamp to 400)
4. Try to type "10" (should clamp to 25)

**Expected:**
- Preview zooms to typed percentage
- Values clamp to 25-400% range

**Test 3.3: Fit Buttons**
1. Click "Fit Width"
2. Click "Fit Height"

**Expected:**
- Fit Width: Sets zoom to 100%
- Fit Height: Sets zoom to 75%
- Preview updates

### 4. Rotation Controls

**Test 4.1: Rotate CCW**
1. Select page 1
2. Click "↺ 90°" once
3. Click "↺ 90°" again

**Expected:**
- First click: Image rotates 90° counter-clockwise
- Second click: Image rotates to 180° (upside down)

**Test 4.2: Rotate CW**
1. Click "Reset" to clear
2. Click "↻ 90°" once
3. Click "↻ 90°" again

**Expected:**
- First click: Image rotates 90° clockwise
- Second click: Image rotates to 180°

**Test 4.3: Rotate 180°**
1. Click "Reset"
2. Click "180°"

**Expected:**
- Image flips upside down instantly

**Test 4.4: Reset**
1. Zoom to 200%, rotate 90°
2. Click "Reset"

**Expected:**
- Rotation resets to 0°
- Zoom resets to 100%
- Pan offset clears

### 5. Pan/Drag

**Test 5.1: Pan When Zoomed**
1. Zoom to 200%
2. Hover over preview
3. Click and drag in any direction

**Expected:**
- Cursor changes to open hand
- Cursor changes to closed hand when dragging
- Image pans with mouse movement

**Test 5.2: No Pan at 100% Zoom**
1. Reset zoom to 100%
2. Try to drag preview

**Expected:**
- Cursor remains arrow
- No panning occurs

### 6. Page Actions

**Test 6.1: Confirm Page**
1. Select page 1
2. Click "✓ Confirm Page"

**Expected:**
- Dialog shows "Page 1 confirmed!"
- Thumbnail #1 shows green ✓ checkmark
- Page remains selected

**Test 6.2: Remove Page**
1. Select page 3
2. Click "Remove from Bundle"
3. Click "Yes" in confirmation dialog

**Expected:**
- Page 3 disappears from thumbnails
- Active page switches to page 1 or 4
- Preview updates

**Test 6.3: Add Pages**
1. Click "Add Pages..."
2. Check 3 pages in dialog
3. Click "Add Selected (3)"

**Expected:**
- Dialog shows 12 unassigned pages
- Button updates count as you check boxes
- After clicking "Add Selected", dialog closes
- New pages appear in thumbnail grid
- Success message shows "Added 3 page(s) to bundle"

**Test 6.4: Re-Analyze Page**
1. Click "Re-Analyze Page"

**Expected:**
- Dialog shows "Re-analysis feature will be available..."
- No changes occur

**Test 6.5: Delete Page**
1. Select page 2
2. Click "Delete Page"
3. Click "Yes" in confirmation

**Expected:**
- Confirmation dialog with warning
- Page 2 removed (same as Remove Page in prototype)

### 7. Save Copy

**Test 7.1: Save Current Page**
1. Zoom to 150%, rotate 90°
2. Click "Save Copy"
3. Choose location and filename
4. Click "Save"

**Expected:**
- File dialog opens
- Default filename: "page_X.png"
- File saves successfully
- Success message shows path

### 8. Bundle Actions

**Test 8.1: Save Bundle**
1. Remove page 2
2. Confirm pages 1, 3, 5
3. Click "Save Bundle"

**Expected:**
- Console shows "BUNDLE CONFIRMED" with details
- Window closes
- Signal emitted with:
  - Remaining file paths (excluding page 2)
  - user_edits with removed and confirmed pages

**Test 8.2: Cancel**
1. Make some changes (remove, confirm, etc.)
2. Click "Cancel"
3. Click "Yes" in confirmation

**Expected:**
- Confirmation dialog asks to discard changes
- Console shows "BUNDLE REJECTED"
- Window closes
- Signal emitted with original bundle_data

**Test 8.3: Close Button**
1. Click ✕ in header
2. Click "Yes" if prompted

**Expected:**
- Same behavior as Cancel

### 9. Page Info Card

**Test Info Display**
1. Select each page (1-7)
2. Verify info card updates

**Expected for each page:**
- Filename: "mock_bundle_page_X.png"
- Position: "Page X of 7"
- Company: "Acme Corporation"
- Type: "Invoice"
- Date: "2024-03-15"
- Confidence: 85-99% (green if ≥80%)

### 10. UnassignedPagesDialog

**Test 10.1: Multi-Select**
1. Click "Add Pages..."
2. Check pages 1, 3, 5, 7
3. Uncheck page 3
4. Check pages 2, 4

**Expected:**
- Button updates: "Add Selected (5)"
- Only checked pages will be added

**Test 10.2: Cancel**
1. Click "Add Pages..."
2. Check some pages
3. Click "Cancel"

**Expected:**
- Dialog closes
- No pages added
- Main window unchanged

**Test 10.3: Add None**
1. Click "Add Pages..."
2. Don't check any pages

**Expected:**
- "Add Selected (0)" button is disabled

## Edge Cases

### Edge Case 1: Remove All Pages

1. Remove pages 1-7 one by one

**Expected:**
- After removing last page, preview clears
- Thumbnail grid is empty
- Can still click "Add Pages..." to add new ones

### Edge Case 2: Rapid Zoom Changes

1. Click + button rapidly 10 times
2. Click − button rapidly 10 times

**Expected:**
- Zoom clamps at 400% (no higher)
- Zoom clamps at 25% (no lower)
- No crashes or UI freezing

### Edge Case 3: Rotate While Panned

1. Zoom to 300%
2. Pan to upper-left corner
3. Rotate 90°

**Expected:**
- Image rotates around center
- Pan offset maintained
- No crashes

### Edge Case 4: Large Bundle (Future)

Modify `_create_mock_bundle()` to generate 50 pages:

```python
file_paths = [f'mock_bundle_page_{i}.png' for i in range(1, 51)]
```

**Expected:**
- Thumbnail scroll works smoothly
- Selecting any page works
- No performance issues

## Visual Inspection

### Colors

- Primary buttons: Blue (#2563EB)
- Success buttons: Green (#059669)
- Danger buttons: Red (#DC2626)
- Confidence ≥80%: Green badge
- Confidence 50-79%: Amber badge
- Confidence <50%: Red badge

### Spacing

- Panels: Even spacing with splitter
- Thumbnails: 8px gap between items
- Buttons: 12px vertical spacing
- Header: 60px height
- Borders: Consistent 1-2px throughout

### Fonts

- Title: 16px bold
- Section headers: 13px bold
- Body text: 12-13px regular
- Buttons: 14px semibold

## Performance

### Expected Behavior

- Window opens in < 1 second
- Thumbnail clicks respond instantly
- Zoom/rotate updates < 100ms
- Layout switching < 200ms
- No memory leaks over extended use

## Console Output

### Expected Logs

**On Save Bundle:**
```
=== BUNDLE CONFIRMED ===
Bundle ID: mock_bundle_001
Remaining pages: 5
User edits: {'removed_pages': [1, 3], 'confirmed_pages': [0, 2, 4]}
```

**On Cancel:**
```
=== BUNDLE REJECTED ===
Bundle ID: mock_bundle_001
```

## Troubleshooting

### Window doesn't open

**Check:**
- PyQt6 installed: `pip list | grep PyQt6`
- No errors in console
- Run from project root

### Colors look wrong

**Check:**
- `Colors` class has all required attributes
- Using `Colors.PRIMARY_PALE` not `Colors.BLUE_50`

### Thumbnails don't click

**Check:**
- `ClickableLabel` imported correctly
- Signal connections in `_create_thumbnail()`

### Pan doesn't work

**Check:**
- Zoom level > 100%
- Mouse events firing (add debug prints)
- `self.is_panning` flag set correctly

## Automated Testing (Future)

When ready for automated tests:

```python
# tests/ui/test_bundle_review_window.py
import pytest
from PyQt6.QtCore import Qt
from ui.bundle_review_window import BundleReviewWindow

def test_window_opens(qtbot):
    """Test window opens with default size."""
    window = BundleReviewWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.isVisible()
    assert window.width() == 1400
    assert window.height() == 900

def test_thumbnail_click(qtbot):
    """Test clicking thumbnail updates preview."""
    window = BundleReviewWindow()
    qtbot.addWidget(window)

    # Click thumbnail 3
    window._on_thumbnail_clicked(2)

    assert window.current_page_index == 2
    assert "Page 3 of 7" in window.page_position.text()

def test_zoom_controls(qtbot):
    """Test zoom in/out."""
    window = BundleReviewWindow()
    qtbot.addWidget(window)

    window._on_zoom_in()
    assert window.zoom_level == 125

    window._on_zoom_out()
    assert window.zoom_level == 100

def test_remove_page(qtbot):
    """Test removing page from bundle."""
    window = BundleReviewWindow()
    qtbot.addWidget(window)

    initial_count = len(window.bundle_data['file_paths'])
    window.removed_pages.add(2)

    # Should have one less visible thumbnail
    visible = [i for i in range(initial_count) if i not in window.removed_pages]
    assert len(visible) == initial_count - 1
```

## Checklist Summary

Use this quick checklist for full testing:

- [ ] Window opens at 1400×900px
- [ ] All 3 panels visible
- [ ] 7 thumbnails display
- [ ] Clicking thumbnail updates preview
- [ ] Layout switcher works (Flow/Grid/List)
- [ ] Zoom in/out works (25-400%)
- [ ] Fit Width/Height work
- [ ] All 4 rotation buttons work
- [ ] Reset clears rotation and zoom
- [ ] Pan works when zoomed >100%
- [ ] Cursor changes to hand when pannable
- [ ] Confirm page shows checkmark
- [ ] Remove page works
- [ ] Add Pages dialog opens and adds pages
- [ ] Re-analyze shows message
- [ ] Delete page works
- [ ] Save Copy opens file dialog
- [ ] Save Bundle emits signal and closes
- [ ] Cancel shows confirmation and closes
- [ ] Close button works
- [ ] Page info card updates correctly
- [ ] All buttons styled correctly
- [ ] No console errors

## Success!

If all tests pass, the Bundle Review Window prototype is ready for:
1. User feedback and iteration
2. Backend integration planning
3. Real image testing
4. Production refinement
