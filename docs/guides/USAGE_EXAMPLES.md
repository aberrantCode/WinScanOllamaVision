# Page Ordering Feature - Usage Examples

## Example 1: Document with Sequential Page Numbers

### Scenario
User scans a 5-page document with visible page numbers (1, 2, 3, 4, 5) but accidentally scans them in order: 3, 1, 4, 2, 5.

### Workflow

**Step 1: Document Stitching**
```
Status: "Analyzing page 1 with llama3.2-vision..."
Result: "✓ Page included automatically [Page 3]. Group has 1 page(s)."

Status: "Analyzing page 2 with llama3.2-vision..."
Result: "✓ Page included automatically [Page 1]. Group has 2 page(s)."

Status: "Analyzing page 3 with llama3.2-vision..."
Result: "✓ Page included automatically [Page 4]. Group has 3 page(s)."

... (continues for remaining pages)
```

**Step 2: Document Analysis**
```
Company: Acme Corporation
Title: Invoice
Date: 2026-01-15
```

**Step 3: Order Pages**
```
Initial order (from stitching):
1. Page 3 ✓ - scan_0001.png
2. Page 1 ✓ - scan_0002.png
3. Page 4 ✓ - scan_0003.png
4. Page 2 ✓ - scan_0004.png
5. Page 5 ✓ - scan_0005.png

Status: "✓ Pages auto-reordered. 5/5 pages had numbers."

Auto-reordered to:
1. Page 1 ✓ - scan_0002.png
2. Page 2 ✓ - scan_0004.png
3. Page 3 ✓ - scan_0001.png
4. Page 4 ✓ - scan_0003.png
5. Page 5 ✓ - scan_0005.png

User clicks: "✓ Approve Order"
```

**Step 4: Document Finalization**
```
PDF created with pages in correct order (1, 2, 3, 4, 5)
```

---

## Example 2: Document Without Page Numbers

### Scenario
User scans a 3-page letter without visible page numbers.

### Workflow

**Step 1: Document Stitching**
```
Status: "Analyzing page 1 with llama3.2-vision..."
Result: "✓ Page included automatically. Group has 1 page(s)."

Status: "Analyzing page 2 with llama3.2-vision..."
Result: "✓ Page included automatically. Group has 2 page(s)."

Status: "Analyzing page 3 with llama3.2-vision..."
Result: "✓ Page included automatically. Group has 3 page(s)."
```

**Step 2: Document Analysis**
```
Company: XYZ Inc.
Title: Business Letter
Date: 2026-02-01
```

**Step 3: Order Pages**
```
Initial order:
1. [No page #] - scan_0001.png
2. [No page #] - scan_0002.png
3. [No page #] - scan_0003.png

Dialog: "No page numbers detected. Would you like Ollama to analyze content flow?"

User clicks: "Yes"

Status: "Analyzing content flow with llama3.2-vision..."

Content analysis result:
{
  "ordered_indices": [0, 1, 2],
  "confidence": "high"
}

Status: "✓ Pages reordered by content analysis (confidence: high). Review and approve."

Order remains:
1. [No page #] - scan_0001.png
2. [No page #] - scan_0002.png
3. [No page #] - scan_0003.png

User clicks: "✓ Approve Order"
```

**Step 4: Document Finalization**
```
PDF created with analyzed order
```

---

## Example 3: Mixed Document (Some Pages with Numbers)

### Scenario
User scans a 4-page document where only 3 pages have visible numbers (2, 4, 5), and one page has no number.

### Workflow

**Step 1: Document Stitching**
```
Pages detected with metadata:
- scan_0001.png: Page 2, confidence: high
- scan_0002.png: Page 4, confidence: medium
- scan_0003.png: No page number
- scan_0004.png: Page 5, confidence: high
```

**Step 2: Document Analysis**
```
Company: Tech Corp
Title: Manual
Date: 2026-01-20
```

**Step 3: Order Pages**
```
Initial order:
1. Page 2 ✓ - scan_0001.png
2. Page 4 ~ - scan_0002.png
3. [No page #] - scan_0003.png
4. Page 5 ✓ - scan_0004.png

Auto-reordered to:
1. Page 2 ✓ - scan_0001.png
2. Page 4 ~ - scan_0002.png
3. Page 5 ✓ - scan_0004.png
4. [No page #] - scan_0003.png  (moved to end)

Status: "✓ Pages auto-reordered. 3/4 pages had numbers."

User reviews and notices page without number should be page 3.
User selects row 4 and clicks "↑ Move Up" twice.

Final order:
1. Page 2 ✓ - scan_0001.png
2. [No page #] - scan_0003.png  (manually moved)
3. Page 4 ~ - scan_0002.png
4. Page 5 ✓ - scan_0004.png

User clicks: "✓ Approve Order"
```

**Step 4: Document Finalization**
```
PDF created with manual adjustments
```

---

## Example 4: Duplicate Page Numbers

### Scenario
Scanner malfunction causes two pages to be detected as "Page 3".

### Workflow

**Step 1: Document Stitching**
```
Pages detected:
- scan_0001.png: Page 1, confidence: high
- scan_0002.png: Page 2, confidence: high
- scan_0003.png: Page 3, confidence: high
- scan_0004.png: Page 3, confidence: high  (DUPLICATE!)
- scan_0005.png: Page 4, confidence: high
```

**Step 2: Document Analysis**
```
Metadata extracted normally
```

**Step 3: Order Pages**
```
Initial order:
1. Page 1 ✓ - scan_0001.png
2. Page 2 ✓ - scan_0002.png
3. Page 3 ✓ - scan_0003.png
4. Page 3 ✓ - scan_0004.png
5. Page 4 ✓ - scan_0005.png

Warning Dialog: "Duplicate page numbers detected: [3]
Please review and reorder manually."

Auto-reordered (best effort):
1. Page 1 ✓ - scan_0001.png
2. Page 2 ✓ - scan_0002.png
3. Page 3 ✓ - scan_0003.png
4. Page 3 ✓ - scan_0004.png  (duplicate kept in order)
5. Page 4 ✓ - scan_0005.png

User examines previews and determines scan_0004.png is actually page 5.
User selects row 4, clicks "↓ Move Down" once.

Final order:
1. Page 1 ✓ - scan_0001.png
2. Page 2 ✓ - scan_0002.png
3. Page 3 ✓ - scan_0003.png
4. Page 4 ✓ - scan_0005.png
5. Page 3 ✓ - scan_0004.png  (manually moved to end)

User clicks: "✓ Approve Order"
```

**Step 4: Document Finalization**
```
PDF created with corrected order
```

---

## Example 5: Drag-and-Drop Reordering

### Scenario
User wants to quickly reorder pages using drag-and-drop.

### Workflow

**Step 3: Order Pages**
```
Initial auto-reordered:
1. Page 1 ✓ - scan_0001.png
2. Page 2 ✓ - scan_0002.png
3. Page 3 ✓ - scan_0003.png
4. Page 4 ✓ - scan_0004.png

User realizes page 4 should come before page 2.

User drags "4. Page 4 ✓ - scan_0004.png" and drops it after row 1.

Final order:
1. Page 1 ✓ - scan_0001.png
2. Page 4 ✓ - scan_0004.png  (moved)
3. Page 2 ✓ - scan_0002.png
4. Page 3 ✓ - scan_0003.png

List automatically refreshes:
1. Page 1 ✓ - scan_0001.png
2. Page 4 ✓ - scan_0004.png
3. Page 2 ✓ - scan_0002.png
4. Page 3 ✓ - scan_0003.png

User clicks: "✓ Approve Order"
```

---

## Example 6: Reset to Original Order

### Scenario
User makes several manual adjustments but decides to start over.

### Workflow

**Step 3: Order Pages**
```
Auto-reordered:
1. Page 1 ✓ - scan_0001.png
2. Page 2 ✓ - scan_0002.png
3. Page 3 ✓ - scan_0003.png

User makes manual changes:
1. Page 3 ✓ - scan_0003.png
2. Page 1 ✓ - scan_0001.png
3. Page 2 ✓ - scan_0002.png

User clicks: "Reset to Original Order"

Confirmation Dialog: "Reset to original page order from stitching step?"
User clicks: "Yes"

Order restored to stitching order:
1. Page 1 ✓ - scan_0001.png
2. Page 2 ✓ - scan_0002.png
3. Page 3 ✓ - scan_0003.png

Status: "Page order reset to original."

User can now re-apply auto-reordering or make different adjustments.
```

---

## Example 7: Going Back to Analysis

### Scenario
User realizes metadata extraction was incorrect after seeing page order.

### Workflow

**Step 3: Order Pages**
```
Order looks correct:
1. Page 1 ✓ - scan_0001.png
2. Page 2 ✓ - scan_0002.png
3. Page 3 ✓ - scan_0003.png

But user notices in preview that document title was extracted incorrectly.

User clicks: "Back to Analysis"

Transitions back to Step 2: Document Analysis

User corrects:
Company: Correct Corp (was: Wrong Corp)
Title: Correct Title (was: Wrong Title)
Date: 2026-02-01

User clicks: "Continue"

Returns to Step 3: Order Pages with same order intact.

User clicks: "✓ Approve Order"
```

---

## Example 8: Content-Based Ordering Success

### Scenario
Document has clear content flow but no page numbers.

### Workflow

**Step 3: Order Pages**
```
Initial order (scanned backwards):
1. [No page #] - scan_0001.png (Conclusion)
2. [No page #] - scan_0002.png (Body)
3. [No page #] - scan_0003.png (Introduction)

Dialog: "No page numbers detected. Content-based ordering?"
User clicks: "Yes"

Status: "Analyzing content flow with llama3.2-vision..."

Ollama analyzes:
- scan_0001.png: Contains "In conclusion, we recommend..."
- scan_0002.png: Contains "The methodology consists of..."
- scan_0003.png: Contains "Introduction: This document presents..."

Content analysis result:
{
  "ordered_indices": [2, 1, 0],
  "confidence": "high"
}

Reordered to:
1. [No page #] - scan_0003.png (Introduction)
2. [No page #] - scan_0002.png (Body)
3. [No page #] - scan_0001.png (Conclusion)

Status: "✓ Pages reordered by content analysis (confidence: high). Review and approve."

User reviews and confirms order makes sense.
User clicks: "✓ Approve Order"
```

---

## Example 9: Single Page Document

### Scenario
User scans a single-page document.

### Workflow

**Step 1: Document Stitching**
```
Status: "Started new group. Page 1 added."
Result: "✓ Page included automatically [Page 1]. Group has 1 page(s)."
```

**Step 2: Document Analysis**
```
Metadata extracted normally
```

**Step 3: Order Pages**
```
Order (only one page):
1. Page 1 ✓ - scan_0001.png

Status: "✓ Pages auto-reordered. 1/1 pages had numbers."

No reordering needed. User clicks: "✓ Approve Order"
```

**Step 4: Document Finalization**
```
PDF created with single page
```

---

## Example 10: Keyboard Navigation

### Scenario
User prefers keyboard shortcuts over mouse.

### Workflow

**Step 3: Order Pages**
```
Initial order:
1. Page 2 ✓ - scan_0001.png
2. Page 1 ✓ - scan_0002.png
3. Page 3 ✓ - scan_0003.png

User workflow (keyboard only):
1. Press Tab to focus on page list
2. Press Down arrow to select row 2
3. Click "↑ Move Up" button (or press Alt+U if shortcut exists)
4. Page 1 moves up to position 1
5. Press Down arrow to select row 3
6. Press Enter to preview page 3
7. Press Tab to focus on "✓ Approve Order" button
8. Press Enter to approve

Final order:
1. Page 1 ✓ - scan_0002.png
2. Page 2 ✓ - scan_0001.png
3. Page 3 ✓ - scan_0003.png
```

---

## Tips for Users

### Best Practices
1. **Always review auto-reordering** - Even with high confidence, verify the order is correct
2. **Use preview** - Click on each page in the list to preview before approving
3. **Save original order** - If unsure, you can always reset and start over
4. **Check for duplicates** - Look for warning messages about duplicate page numbers
5. **Trust content analysis** - If Ollama reports high confidence, it's usually accurate

### Troubleshooting
- **Pages not reordering**: Check if page numbers were detected in Step 1
- **Wrong order after auto-reorder**: Use manual controls or drag-and-drop
- **Content analysis fails**: Manually reorder using Move Up/Down buttons
- **Can't find a page**: Use Reset button to restore original order

### Advanced Usage
- **Batch operations**: Select and move multiple pages at once (future enhancement)
- **Custom ordering rules**: Set preferences for handling edge cases (future enhancement)
- **Confidence thresholds**: Adjust auto-approval settings (future enhancement)
