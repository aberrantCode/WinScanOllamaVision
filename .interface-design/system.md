# WinScanLLM Design System

## Intent

**Who:** Document-processing operators and archivists managing batches of scanned files on a local desktop workstation. Focused, methodical, checking progress across runs.

**What they do:** Scan directories, run LLM metadata extraction, review and correct fields, bundle documents, track analysis status.

**Feel:** A professional instrument. Quiet authority — like a terminal crossed with archival software. Dense enough to show information, disciplined enough not to feel cluttered.

---

## Single Source of Truth

**`ThemeManager`** (`src/ui/theme_manager.py`) is the authoritative design token source.

- Apply at startup: `app.setStyleSheet(ThemeManager.get_stylesheet(is_dark))`
- Access tokens: `ThemeManager.get_colors(is_dark)` → `dict[str, str]`
- Do NOT maintain parallel color dicts using `Colors.*` neutrals — use ThemeManager

**`styles.py`** (`src/ui/styles.py`) provides:
- `Colors` class — semantic (accent/status) colors only, theme-invariant
- Accent button style overrides (`get_primary/success/danger/secondary_button_style()`)
- Progress bar overrides (`get_progress_bar_style()`, `get_distribution_bar_style()`)
- Themed message box helpers (`show_information/warning/critical/question/confirm()`)

---

## Color Tokens

### Dark Mode (default)
```
bg_primary:    #0B1120  — main surface (very dark navy)
bg_secondary:  #151D2F  — sidebar/panel
bg_tertiary:   #1F2A40  — cards, inputs, buttons
bg_hover:      #2A3550  — hover state

text_primary:  #E0E0E0
text_secondary:#B0B0B0
text_tertiary: #808080
text_disabled: #606060

border:        #4A4A4A
border_light:  #5A5A5A
border_focus:  #3B82F6

selection_bg:  #3B82F640 (transparent blue)
selection_text:#E0E0E0
```

### Light Mode
```
bg_primary:    #FFFFFF
bg_secondary:  #F9FAFB
bg_tertiary:   #F3F4F6
bg_hover:      #E5E7EB

text_primary:  #111827
text_secondary:#374151
text_tertiary: #6B7280
text_disabled: #9CA3AF

border:        #E5E7EB
border_light:  #F3F4F6
border_focus:  #3B82F6

selection_bg:  #DBEAFE
selection_text:#1E40AF
```

### Semantic Colors (theme-invariant)
```
accent:        #3B82F6  — primary blue
accent_hover:  #2563EB
success:       #10B981  — emerald
warning:       #F59E0B  — amber
error:         #EF4444  — red
```

---

## Typography

```
Font family:  "Segoe UI", Arial, sans-serif
Base size:    10pt
Headings:     font-weight: 600
```

---

## Geometry

```
Border radius:  4px  (tight, precise — not bubbly)
Spacing unit:   8px
Button padding: 6px 14px (default), 8px 16px (accent)
Min button height: auto (no artificial minimum)
```

---

## Depth / Elevation

Depth via background layering, not shadows:
1. `bg_primary` — main canvas
2. `bg_secondary` — panels, sidebars
3. `bg_tertiary` — cards, inputs, floating elements

No heavy drop shadows. Borders (`1px solid {border}`) delineate surfaces.

---

## Component Patterns

### Buttons

**Neutral (default)** — inherits from ThemeManager global stylesheet:
```qss
background-color: {bg_tertiary}; color: {text_primary};
border: 1px solid {border}; border-radius: 4px; padding: 6px 14px;
```

**Accent overrides** — call from `styles.py` when semantic color needed:
- `get_primary_button_style()` → blue (#3B82F6)
- `get_success_button_style()` → green (#10B981)
- `get_danger_button_style()` → red (#EF4444)
- `get_secondary_button_style()` → neutral, theme-aware

### Inputs / Dropdowns
Inherit from ThemeManager. Focus ring: `border-color: {border_focus}; border-width: 2px`

### Progress Bars
Use `get_progress_bar_style(percentage)` for color-coded chunked bars.
Use `get_distribution_bar_style()` for compact metric bars.
Both adapt background to current theme.

### Message Boxes
Always use `show_information/warning/critical/question/confirm()` from `styles.py`.
Never create `QMessageBox` directly — these helpers apply correct theming.

---

## Widget Theme Access Pattern

When a widget needs theme colors for inline styling (e.g. QTreeWidget items, custom paint):

```python
from ui.theme_manager import ThemeManager

# If widget has self.dark_mode:
c = ThemeManager.get_colors(self.dark_mode)

# If widget needs to read config (no self.dark_mode):
from ui.styles import _is_dark
c = ThemeManager.get_colors(_is_dark())
```

When widget needs extra keys not in ThemeManager (e.g. `button_bg`, `button_hover`):
```python
c = ThemeManager.get_colors(self.dark_mode)
colors = {**c, "button_bg": c["bg_tertiary"], "button_hover": c["bg_hover"]}
```

---

## What NOT to Do

- Do NOT build custom color dicts from `Colors.WHITE`, `Colors.GRAY_*` for theme-adaptive UI
- Do NOT use `get_main_app_stylesheet()` — it was removed; use `ThemeManager.get_stylesheet()`
- Do NOT create `QMessageBox` directly — use `show_*()` helpers
- Do NOT call `widget.setStyleSheet()` with hardcoded light-mode neutrals for theme-adaptive widgets
- Do NOT add new functions to `styles.py` that duplicate ThemeManager's global stylesheet

---

## File Map

```
src/ui/theme_manager.py          — Global stylesheet + color tokens (PRIMARY source)
src/ui/styles.py                  — Accent buttons, progress bars, message box helpers
src/ui/gui.py                     — Main window
src/ui/discover_window.py         — Image discovery & review (uses ThemeManager via _get_theme_colors)
src/ui/guided_bundle_workflow.py  — Bundle creation workflow (has its own extended theme dict)
src/ui/image_preview_widget.py    — Reusable image viewer with toolbar
src/ui/analysis_status_window.py  — Analysis progress tracking
src/ui/collection_status_helpers.py — Collection metrics UI helpers
src/ui/verify_documents_window.py — Document review interface
src/ui/settings_window_enhanced.py — Settings UI
```
