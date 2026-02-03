# Keyboard Shortcuts Reference - ConvertImagesWindow

Quick reference for all keyboard shortcuts in the document conversion workflow.

## Navigation Shortcuts

Work across all steps to navigate through images in the gallery:

| Shortcut | Action |
|----------|--------|
| `←` Left Arrow | Previous image |
| `→` Right Arrow | Next image |
| `Page Up` | Jump back 10 images |
| `Page Down` | Jump forward 10 images |
| `Home` | Jump to first image |
| `End` | Jump to last image |

## Action Shortcuts

Context-aware shortcuts that change behavior based on the current step:

| Shortcut | Action |
|----------|--------|
| `Space` | Include current page in bundle |
| `Delete` | Exclude current page from bundle |
| `Enter` | Approve/Continue to next step |
| `Esc` | Cancel current request or go back |

### Enter Key Behavior by Step:
- **Step 1 (Stitching)**: Approve bundle and continue
- **Step 3 (Ordering)**: Approve page order and continue
- **Step 4 (Finalization)**: Finalize and create PDFs

## Zoom Shortcuts

Control the center preview zoom level:

| Shortcut | Action |
|----------|--------|
| `Ctrl` + `+` | Zoom in (increase by 25%) |
| `Ctrl` + `-` | Zoom out (decrease by 25%) |
| `Ctrl` + `0` | Fit to window |

**Note:** Zoom range is 25% to 400%

## Bundle Shortcuts

Only active in Step 0 (Bundle Suggestions):

| Shortcut | Action |
|----------|--------|
| `Ctrl` + `A` | Accept all high confidence bundles |
| `Ctrl` + `D` | Skip to manual workflow |

## Help

| Shortcut | Action |
|----------|--------|
| `F1` | Toggle keyboard shortcuts legend |
| `?` | Toggle keyboard shortcuts legend |

## Visual Feedback

The application provides visual feedback when you use keyboard shortcuts:

- **Green flash**: Page included in bundle
- **Red flash**: Page excluded from bundle

Both the center preview and the thumbnail will flash briefly to confirm the action.

## Tips

1. **Hover over buttons** to see their keyboard shortcuts in tooltips
2. **Press F1** anytime to see the complete shortcuts legend
3. **Use Tab** to navigate between controls
4. **All shortcuts work without a mouse** - full keyboard accessibility

## Accessibility

All functionality in ConvertImagesWindow is accessible via keyboard:
- Tab through all controls in logical order
- Visual focus indicators show current control
- Tooltips provide shortcut hints
- Complete shortcuts legend available with F1

## Workflow Example

Efficient keyboard-only workflow for document stitching:

1. **Launch window**: Application opens with first image
2. **Navigate**: Use `→` and `←` to review images
3. **Include/Exclude**: Press `Space` to include, `Delete` to exclude
4. **Zoom if needed**: `Ctrl+0` to fit, `Ctrl++` to zoom in for details
5. **Approve bundle**: Press `Enter` when bundle is complete
6. **Repeat**: Process next bundle
7. **Get help**: Press `F1` if you forget a shortcut

## Shortcut Conflicts

These shortcuts are reserved by the application and won't trigger system shortcuts:

- Navigation arrows don't scroll the window
- Space doesn't scroll (it includes pages)
- Enter doesn't activate focused button (it approves workflow)

If you need to use these keys for their normal function, click with the mouse instead.

## Customization

**Note:** Keyboard shortcuts are currently fixed and cannot be customized. This may be added in a future version.

## Troubleshooting

**Shortcut not working?**
1. Check if the corresponding button is visible and enabled
2. Verify you're in the correct step (e.g., bundle shortcuts only work in Step 0)
3. Make sure the window has focus (not another application)
4. Check the shortcuts legend (F1) for the exact key combination

**Legend not appearing?**
1. Press F1 or ? again to toggle it
2. Scroll down - the legend appears at the bottom of the window
3. Check if it's collapsed - click the legend title to expand

## Print Version

For a printable version of this guide, open the shortcuts legend in the application (press F1) and take a screenshot.
