# ConvertImagesWindow UI Redesign

## Current UI Problems

1. **No metadata display**: Doesn't show AI-extracted metadata (document_type, confidence, page numbers, etc.)
2. **Color clashing**: Inconsistent button colors, poor contrast
3. **No image selection**: Forces sequential iteration through folder - can't jump to specific images
4. **Poor information density**: Large preview takes all space, little room for metadata/controls
5. **Confusing workflow**: Not clear which step user is in or what actions are available
6. **No bundle context**: When reviewing bundles, can't see which pages belong together

---

## Design Principles

1. **Metadata-First**: AI analysis results should be prominently visible
2. **Visual Hierarchy**: Important info (confidence, document type) stands out
3. **Color Consistency**: Follow modern design system (not random colors)
4. **Flexible Navigation**: User can jump to any image, not just sequential
5. **Context Awareness**: Show different UI based on current step (bundles vs manual vs metadata)

---

## Color Scheme (Modern, Consistent)

### Base Colors
- **Background**: `#F9FAFB` (light gray)
- **Card Background**: `#FFFFFF` (white)
- **Border**: `#E5E7EB` (medium gray)
- **Text Primary**: `#111827` (near black)
- **Text Secondary**: `#6B7280` (gray)

### Semantic Colors
- **Primary (Actions)**: `#2563EB` (blue) - "Accept", "Continue", "Apply"
- **Success**: `#059669` (green) - "High confidence", checkmarks
- **Warning**: `#F59E0B` (amber) - "Medium confidence", alerts
- **Danger**: `#DC2626` (red) - "Low confidence", "Reject", "Delete"
- **Neutral**: `#6B7280` (gray) - "Cancel", "Skip", secondary actions

### Hover States
- Primary hover: `#1D4ED8`
- Success hover: `#047857`
- Warning hover: `#D97706`
- Danger hover: `#B91C1C`
- Neutral hover: `#4B5563`

---

## Layout Redesign: Three-Column Layout

### Overall Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Header: Step Title + Controls                                    [Back] [✕] │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────┐  ┌────────────────────────────────┐  ┌──────────────────┐│
│  │              │  │                                │  │                  ││
│  │   LEFT       │  │        CENTER                  │  │      RIGHT       ││
│  │   PANEL      │  │        PREVIEW                 │  │      PANEL       ││
│  │              │  │                                │  │                  ││
│  │  Image       │  │    Large image preview         │  │  AI Metadata     ││
│  │  Gallery     │  │    with zoom/rotation          │  │  + Actions       ││
│  │              │  │                                │  │                  ││
│  │  (250px)     │  │    (fluid, min 600px)          │  │   (350px)        ││
│  │              │  │                                │  │                  ││
│  └──────────────┘  └────────────────────────────────┘  └──────────────────┘│
│                                                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ Footer: Status + Progress                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Step 0: Bundle Suggestions View

**Full-Width Layout** (no three-column, dedicated to bundle cards)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 0 of 4: AI Bundle Suggestions                     [Accept All High ✓] │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ℹ The AI has analyzed 47 pages and suggests 8 document groupings.          │
│    Review each suggestion below.                                             │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ 🟢 HIGH CONFIDENCE (90%)                                                │ │
│  │                                                                          │ │
│  │ Invoice • Acme Corp • 2024-01-15 • 6 pages                             │ │
│  │                                                                          │ │
│  │ [thumb] [thumb] [thumb] [thumb] [thumb] [thumb]                        │ │
│  │                                                                          │ │
│  │ [✓ Accept]  [✎ Modify]  [✗ Reject]                                     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ 🟡 MEDIUM CONFIDENCE (65%)                                              │ │
│  │                                                                          │ │
│  │ Statement • Unknown • 2024-01-12 • 3 pages                             │ │
│  │                                                                          │ │
│  │ [thumb] [thumb] [thumb]                                                │ │
│  │                                                                          │ │
│  │ [✓ Accept]  [✎ Modify]  [✗ Reject]                                     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
│  ...more bundles...                                                          │
│                                                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ 8 bundles found (6 high, 2 medium) • 47 pages total   [Review Manually →] │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Manual Stitching (Three-Column)

### LEFT PANEL: Image Gallery (250px)

**Purpose**: Show all available images, allow jumping to any image

```
┌────────────────────┐
│ Available Pages    │
│ [Search: ____]     │  ← Filter by filename
│                    │
│ [Sort: Date ▼]     │  ← Sort: Date/Name/Type
│                    │
│ ┌────────────────┐ │
│ │[✓] img_001.png│ │  ← Checkbox + thumbnail
│ │    [Preview]   │ │     Checked = included
│ ├────────────────┤ │
│ │[ ] img_002.png│ │  ← Can click to select
│ │    [Preview]   │ │
│ ├────────────────┤ │
│ │[✓] img_003.png│ │
│ │    [Preview]   │ │
│ ├────────────────┤ │
│ │[ ] img_004.png│ │  ← Selected (highlighted)
│ │    [Preview]   │ │     Currently viewing
│ └────────────────┘ │
│                    │
│ Showing: 4 of 47   │
│                    │
│ [Select All]       │
│ [Clear Selection]  │
│                    │
│ Metadata Badges:   │
│ 🟢 Analyzed        │  ← Color-coded status
│ 🟡 Needs Review    │
│ ⭘ Unanalyzed      │
└────────────────────┘
```

**Features:**
- **Click any image** to view it (not just next/prev)
- **Checkbox** to include/exclude from current bundle
- **Search/filter** by filename
- **Sort** by date, name, or document type
- **Status badges** showing analysis state
- **Bulk actions**: Select all, clear selection

---

### CENTER PANEL: Preview (Fluid, min 600px)

**Purpose**: Show current image with zoom/rotation controls

```
┌─────────────────────────────────────────┐
│ Zoom: [Fit Width ▼] [100%] [-] [+]    │
│                                         │
│  ╔═════════════════════════════════╗   │
│  ║                                 ║   │
│  ║                                 ║   │
│  ║       [Large Preview]           ║   │
│  ║                                 ║   │
│  ║       invoice_001.png           ║   │
│  ║                                 ║   │
│  ║                                 ║   │
│  ╚═════════════════════════════════╝   │
│                                         │
│ Rotation: [↺ 90°] [↻ 90°] [⟲ 180°]   │
│                                         │
│ Navigation: [◀ Prev] [Next ▶]          │
└─────────────────────────────────────────┘
```

**Features:**
- **Zoom modes**: Fit Width, Fit Height, Fit Window, Custom %
- **Rotation**: Display-only (stored in DB)
- **Keyboard navigation**: Arrow keys to move between images
- **Mouse wheel zoom**: Ctrl+scroll to zoom

---

### RIGHT PANEL: AI Metadata + Actions (350px)

**Purpose**: Show AI-extracted metadata and available actions

```
┌──────────────────────────────────────┐
│ AI Analysis                          │
│                                      │
│ ┌──────────────────────────────────┐│
│ │ 🟢 HIGH CONFIDENCE (92%)         ││
│ │                                  ││
│ │ Document Type: Invoice           ││
│ │ Company: Acme Corporation        ││
│ │ Date: 2024-01-15                 ││
│ │ Page: 1 of 6                     ││
│ │                                  ││
│ │ Rotation: None needed ✓          ││
│ └──────────────────────────────────┘│
│                                      │
│ Current Bundle                       │
│ ┌──────────────────────────────────┐│
│ │ 3 pages included:                ││
│ │                                  ││
│ │ [thumb] invoice_001.png          ││
│ │ [thumb] invoice_002.png          ││
│ │ [thumb] invoice_003.png          ││
│ │                                  ││
│ │ [Remove]                         ││
│ └──────────────────────────────────┘│
│                                      │
│ Actions                              │
│ ┌──────────────────────────────────┐│
│ │                                  ││
│ │ [✓ Include in Bundle]    (Blue) ││  ← Primary action
│ │                                  ││
│ │ [✗ Exclude Page]      (Red)     ││  ← Destructive
│ │                                  ││
│ │ [→ Approve Bundle]    (Green)   ││  ← Success
│ │                                  ││
│ │ [↻ Request Re-analysis] (Gray)  ││  ← Utility
│ │                                  ││
│ └──────────────────────────────────┘│
│                                      │
│ Suggested Documents                  │
│ ┌──────────────────────────────────┐│
│ │ AI suggests this belongs with:   ││
│ │                                  ││
│ │ [Doc #3: Invoice, Acme, 6 pgs]  ││  ← Clickable
│ │                                  ││
│ │ [Use Suggestion]                 ││
│ └──────────────────────────────────┘│
└──────────────────────────────────────┘
```

**Metadata Display Sections:**

1. **AI Analysis Card** (top):
   - Confidence badge (color-coded)
   - All extracted fields:
     - Document Type (editable dropdown)
     - Company (editable text)
     - Date (editable date picker)
     - Page numbers (if detected)
     - Rotation status
     - Extracted text summary (expandable)
   - "Edit Metadata" button

2. **Current Bundle** (middle):
   - Thumbnails of included pages
   - Click thumbnail to jump to that page
   - Remove button for each page
   - Reorder by drag-drop

3. **Actions** (lower-middle):
   - Large, clear buttons with consistent colors
   - Icons + text labels
   - Keyboard shortcuts shown

4. **AI Suggestions** (bottom):
   - Show which existing bundle this page might belong to
   - Based on metadata similarity
   - "Use Suggestion" auto-adds to that bundle

---

## Step 2: Metadata Review (Three-Column)

### LEFT PANEL: Bundle List (250px)

```
┌────────────────────┐
│ Document Bundles   │
│                    │
│ [Filter: All ▼]    │
│                    │
│ ┌────────────────┐ │
│ │ Bundle 1       │ │  ← Selected (highlighted)
│ │ Invoice        │ │
│ │ Acme Corp      │ │
│ │ 6 pages        │ │
│ │ 2024-01-15     │ │
│ └────────────────┘ │
│ ┌────────────────┐ │
│ │ Bundle 2       │ │
│ │ Statement      │ │
│ │ Beta Inc       │ │
│ │ 3 pages        │ │
│ │ 2024-01-12     │ │
│ └────────────────┘ │
│ ┌────────────────┐ │
│ │ Bundle 3       │ │
│ │ Receipt        │ │
│ │ Charlie Co     │ │
│ │ 1 page         │ │
│ │ 2024-01-10     │ │
│ └────────────────┘ │
│                    │
│ 3 bundles • 10 pgs │
│                    │
│ [Merge Bundles]    │
│ [Split Bundle]     │
└────────────────────┘
```

---

### CENTER PANEL: Page Carousel (Fluid)

```
┌─────────────────────────────────────────┐
│ ◀                                    ▶  │  ← Navigation arrows
│                                         │
│  [thumb] [thumb] [LARGE] [thumb] [thm] │  ← Carousel
│                                         │
│  Page 1   Page 2  Page 3  Page 4  Pg5  │
│                     ↑                   │
│                 Currently               │
│                 Selected                │
│                                         │
│ ╔═══════════════════════════════════╗   │
│ ║                                   ║   │
│ ║       Full Preview                ║   │
│ ║       of Page 3                   ║   │
│ ║                                   ║   │
│ ╚═══════════════════════════════════╝   │
│                                         │
│ [◀ Previous Bundle] [Next Bundle ▶]    │
└─────────────────────────────────────────┘
```

---

### RIGHT PANEL: Metadata Editor (350px)

```
┌──────────────────────────────────────┐
│ Bundle Metadata                      │
│                                      │
│ Company *                            │
│ [Acme Corporation        ▼]          │  ← Dropdown with history
│                                      │
│ Document Type *                      │
│ [Invoice                 ▼]          │  ← Predefined types
│                                      │
│ Document Date *                      │
│ [📅 2024-01-15]                      │  ← Date picker
│                                      │
│ Document Title                       │
│ [Q1 2024 Invoice         ]          │  ← Optional
│                                      │
│ Notes                                │
│ [________________________]          │
│ [________________________]          │
│                                      │
│ ┌──────────────────────────────────┐│
│ │ 🟢 All required fields filled    ││
│ └──────────────────────────────────┘│
│                                      │
│ Quick Actions                        │
│ [Copy from Previous]                 │  ← Batch editing
│ [Apply to Selected]                  │
│                                      │
│ ┌──────────────────────────────────┐│
│ │ [← Back to Stitching]            ││
│ │                                  ││
│ │ [Continue to Finalization →]    ││  ← Primary
│ └──────────────────────────────────┘│
└──────────────────────────────────────┘
```

**Features:**
- **Autocomplete**: Company/title fields remember previous entries
- **Validation**: Required fields clearly marked
- **Batch editing**: "Apply to Selected" for multiple bundles
- **Quick copy**: Copy metadata from previous bundle
- **Visual feedback**: Green checkmark when complete

---

## Step 3: Finalization (Full-Width)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 3 of 4: Finalization                                         [Back] [✕]│
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  Review and Create PDFs                                                      │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Bundle 1: Invoice - Acme Corporation - 2024-01-15                       │ │
│  │                                                                          │ │
│  │ [thumb] [thumb] [thumb] [thumb] [thumb] [thumb]     6 pages            │ │
│  │                                                                          │ │
│  │ Filename: Acme Corporation - Invoice - 2024-01-15.pdf                  │ │
│  │ Output: C:\Users\...\Documents\Scans\                                  │ │
│  │                                                                          │ │
│  │ [✓ OCR Enabled]  [✓ Searchable PDF]                                    │ │
│  │                                                                          │ │
│  │ [Edit] [Remove]                                                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Bundle 2: Statement - Beta Inc - 2024-01-12                             │ │
│  │ ...                                                                      │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
│  Output Options                                                              │
│  [✓] Delete source PNGs after PDF creation                                  │
│  [✓] Archive bundle metadata to database                                    │
│  [ ] Open output folder when complete                                       │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                          │ │
│  │                    [Create 3 PDFs →]                                    │ │  ← Big, prominent
│  │                                                                          │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3 bundles ready • 10 pages total                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Responsive Behavior

### Window Resize Handling

**Minimum Window Size**: 1200x700px

**Panel Behavior:**
- **LEFT**: Fixed 250px (collapses to icon bar below 1200px)
- **CENTER**: Fluid (min 600px, takes remaining space)
- **RIGHT**: Fixed 350px (scrollable if content overflows)

**Small Screen Mode** (<1200px width):
- Left panel becomes collapsible sidebar (hamburger menu)
- Right panel moves to bottom half (horizontal split)
- Center preview takes full width

---

## Keyboard Shortcuts

Global shortcuts across all steps:

```
Navigation:
  ← →       : Previous/Next image
  PgUp/PgDn : Jump 10 images
  Home/End  : First/Last image

Actions:
  Space     : Include current page
  Delete    : Exclude current page
  Enter     : Approve/Continue
  Esc       : Cancel/Back

Zoom:
  Ctrl + +  : Zoom in
  Ctrl + -  : Zoom out
  Ctrl + 0  : Fit to window

Bundles:
  Ctrl + A  : Select all
  Ctrl + D  : Deselect all
  Ctrl + G  : Group selected (create bundle)
```

**Shortcuts displayed:**
- Tooltip on hover
- Legend at bottom of window (collapsible)

---

## Visual Design System

### Typography

```
Headings:
  H1: 24px, Bold, #111827
  H2: 18px, Semibold, #111827
  H3: 14px, Semibold, #374151

Body:
  Primary: 13px, Regular, #111827
  Secondary: 12px, Regular, #6B7280
  Small: 11px, Regular, #9CA3AF

Monospace (filenames):
  12px, "Consolas", #374151
```

### Spacing

```
Container padding: 16px
Card padding: 12px
Button padding: 8px 16px
Section gap: 20px
Element gap: 8px
```

### Shadows & Borders

```
Cards: 0 1px 3px rgba(0,0,0,0.1)
Hover: 0 4px 6px rgba(0,0,0,0.1)
Active: 0 1px 2px rgba(0,0,0,0.1)

Border: 1px solid #E5E7EB
Border radius: 6px (cards), 4px (buttons)
```

---

## Implementation Priority

1. **Phase 1: Color Scheme** (Quick Win)
   - Update all buttons to use consistent semantic colors
   - Fix clashing colors
   - Apply to existing UI

2. **Phase 2: Three-Column Layout** (Foundation)
   - Implement left/center/right panel structure
   - Make it responsive
   - Add panel resize handles

3. **Phase 3: Image Gallery** (Critical Feature)
   - Add left panel with all images
   - Enable click-to-select
   - Add search/filter
   - Show metadata badges

4. **Phase 4: Metadata Display** (AI Integration)
   - Right panel showing AI analysis
   - Confidence badges
   - All extracted fields
   - Edit capabilities

5. **Phase 5: Bundle Suggestions** (Major UX Improvement)
   - Full-width Step 0 view
   - Bundle cards with actions
   - Accept/Modify/Reject workflow

6. **Phase 6: Polish** (Final Touches)
   - Keyboard shortcuts
   - Animations/transitions
   - Accessibility
   - Help tooltips

---

## Success Metrics

**Usability:**
- User can find and jump to any image in < 3 seconds
- Metadata is always visible (no hidden info)
- Actions are color-coded and consistent
- No visual clutter or confusion

**Efficiency:**
- Bundle review takes < 10 seconds per bundle
- Metadata editing takes < 5 seconds per field
- No unnecessary clicks or navigation

**Professional Feel:**
- Consistent colors and spacing
- Smooth transitions
- Responsive layout
- Modern design aesthetic
