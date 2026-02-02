# Quick Start Guide - New Features

## What's New?

### 🎯 Page Ordering (Step 3)
Automatically detects page numbers and reorders pages correctly.

### ⚡ Smart Caching
First run extracts metadata, subsequent runs are 99% faster!

### 🔍 Zoom Controls
Zoom in/out on preview images (25%-400%) with mouse wheel or buttons.

### ⏱️ Timeout Configuration
Control how long to wait for Ollama responses.

---

## Quick Start

### 1. Run the Application
```bash
cd C:\development\scan_organization
python src/main.py
```

### 2. New Workflow (4 Steps)

**Step 1: Document Stitching**
- First time: Ollama extracts comprehensive metadata (2-10 seconds per page)
- Subsequent times: Uses cached metadata (<0.01 seconds per page)
- Watch for cache messages:
  - `⟳ Fetching fresh metadata` = New file, calling Ollama
  - `✓ Using cached metadata` = Cache hit, instant!

**Step 2: Document Analysis**
- Company and document type may be pre-filled from Step 1 metadata
- Review and adjust as needed

**Step 3: Order Pages (NEW!)**
- Pages automatically reorder by detected page numbers
- Manual controls:
  - Drag-and-drop pages in list
  - Click "↑ Move Up" / "↓ Move Down"
  - Mouse wheel to zoom preview
- Look for page position indicators (e.g., "3 of 6")
- Click "✓ Approve Order" when satisfied

**Step 4: Document Finalization**
- Review PDF
- Metadata automatically archived to database
- Choose to keep or delete source files

### 3. Zoom Controls

**Location:** Top-right corner of preview image

**Controls:**
- `−` = Zoom Out (25% steps)
- `⊙` = Reset to 100%
- `+` = Zoom In (25% steps)
- Mouse wheel = Quick zoom

**Range:** 25% to 400%

### 4. Configuration

**File:** `settings.ini`

```ini
[Ollama]
model = qwen2.5-vl
base_url = http://localhost:11434
timeout = 300  # Seconds to wait for Ollama (default: 5 minutes)
```

**Adjust timeout if:**
- You have slow hardware: Increase to 600+
- You have fast hardware: Decrease to 120-180
- Processing large documents: Increase timeout

---

## Understanding Metadata Extraction

### What's Extracted (Step 1)
From each page:
- ✓ Page number (e.g., `3`)
- ✓ Total pages (e.g., `6` from "3 of 6")
- ✓ Page position (e.g., `"Page 3 of 6"`)
- ✓ Company name
- ✓ Document type
- ✓ Document date
- ✓ Additional info (invoice numbers, totals, etc.)

### Cached Data
- Stored in `metadata.db` (created automatically)
- Never expires unless file changes
- File hash + modification time validation
- Instant retrieval on subsequent runs

### Archived Data
- Stored after PDF creation
- Complete document history
- All source file references
- Processing timestamps

---

## Tips & Tricks

### Maximize Cache Hits
1. **Don't modify source PNGs** after first processing
2. **Batch process** similar documents together
3. **Re-run** on same files = instant processing!

### Page Ordering
1. **Review auto-order** - usually correct with high confidence
2. **Check page position** - "4 of 6" means total is 6 pages
3. **Manual override** - drag-and-drop or move up/down
4. **Reset available** - if you mess up, reset to original

### Zoom Usage
1. **Inspect details** - zoom to 200% or 400% for small text
2. **Wheel zoom** - fastest way to zoom in/out
3. **Pan not available** - zoom resets position (may add later)

### Performance
1. **First run:** Normal processing time (Ollama calls)
2. **Second run:** 99% faster (cache hits)
3. **Modified files:** Auto-detected, re-processed
4. **Large documents:** Increase timeout if needed

---

## Troubleshooting

### Cache Not Working
**Symptom:** Always shows "⟳ Fetching fresh metadata"

**Check:**
1. Is `metadata.db` in app directory?
2. File permissions correct?
3. Console shows any errors?

**Fix:**
- Restart application
- Check file permissions
- Delete `metadata.db` to start fresh

### Page Order Wrong
**Symptom:** Pages in wrong order after auto-reorder

**Solution:**
1. Check confidence icons (✓ high, ~ medium, ? low)
2. Use manual controls (Move Up/Down or drag-and-drop)
3. Click "Reset to Original Order" if needed
4. Approve when satisfied

### Timeout Errors
**Symptom:** "Timeout" error during processing

**Solution:**
1. Increase timeout in `settings.ini`
2. For large docs: Set to 600 (10 minutes)
3. For slow hardware: Set to 900 (15 minutes)
4. Restart app to load new setting

### Zoom Not Working
**Symptom:** Buttons don't zoom or mouse wheel doesn't work

**Check:**
1. Buttons appear in top-right corner?
2. Mouse cursor over preview image?
3. Preview image is displayed?

**Fix:**
- Resize window to trigger button reposition
- Ensure image is loaded first

---

## Database Maintenance

### View Statistics
```python
from metadata_db import MetadataDB

db = MetadataDB()
stats = db.get_statistics()
print(f"Cached files: {stats['active_metadata_count']}")
print(f"Archived PDFs: {stats['archived_documents_count']}")
print(f"Database size: {stats['database_size_bytes']} bytes")
db.close()
```

### Cleanup Orphaned Data
```python
from metadata_db import MetadataDB

db = MetadataDB()
removed = db.cleanup_orphaned_metadata()
print(f"Removed {removed} orphaned entries")
db.close()
```

### Backup Database
```bash
cp metadata.db metadata_backup_2026-02-01.db
```

### Reset Everything
```bash
rm metadata.db
# Database recreated on next run
```

---

## Performance Examples

### Example 1: Fresh Document (6 pages)
```
Step 1 - Page 1: ⟳ Fetching (2.5s)
Step 1 - Page 2: ⟳ Fetching (2.8s)
Step 1 - Page 3: ⟳ Fetching (2.6s)
Step 1 - Page 4: ⟳ Fetching (2.7s)
Step 1 - Page 5: ⟳ Fetching (2.9s)
Step 1 - Page 6: ⟳ Fetching (2.5s)
Total: ~16 seconds
```

### Example 2: Same Document (Re-run)
```
Step 1 - Page 1: ✓ Cached (0.002s)
Step 1 - Page 2: ✓ Cached (0.001s)
Step 1 - Page 3: ✓ Cached (0.002s)
Step 1 - Page 4: ✓ Cached (0.001s)
Step 1 - Page 5: ✓ Cached (0.002s)
Step 1 - Page 6: ✓ Cached (0.001s)
Total: ~0.01 seconds (99.9% faster!)
```

---

## FAQ

**Q: Will this slow down my first run?**
A: No! Same speed as before, but now it extracts more metadata in the same call.

**Q: How much disk space does caching use?**
A: About 1-2 KB per page. 1000 pages = ~1-2 MB total.

**Q: Can I disable caching?**
A: Cache checks are automatic and instant. No reason to disable.

**Q: What if I move/rename PNG files?**
A: Cache uses absolute paths. Moving files = new cache entry.

**Q: Can I see what's in the cache?**
A: Yes! Use `sqlite3 metadata.db` to explore database.

**Q: Does zoom persist between pages?**
A: Yes! Zoom level maintained when switching pages.

**Q: Can I zoom beyond 400%?**
A: Not currently. May add in future update.

**Q: How does page ordering handle duplicates?**
A: Shows warning, allows manual reordering.

**Q: What if page numbers are missing?**
A: Offers content-based ordering via Ollama analysis.

**Q: Can I skip Step 3 (ordering)?**
A: No, but it's very quick - just click "✓ Approve Order".

---

## Keyboard Shortcuts

### General
- `Tab` - Navigate between controls
- `Enter` - Activate focused button
- `Esc` - Cancel dialogs

### Step 3 (Order Pages)
- `↑` / `↓` - Select page in list
- `Tab` to Move Up button, `Enter` - Move page up
- `Tab` to Move Down button, `Enter` - Move page down

### Zoom
- Mouse wheel - Zoom in/out
- `Tab` to zoom buttons, `Enter` - Activate

---

## Getting Help

### Documentation
- `IMPLEMENTATION_SUMMARY.md` - Page ordering details
- `PAGE_ORDERING_GUIDE.md` - Developer guide
- `TIMEOUT_AND_ZOOM_IMPLEMENTATION.md` - Timeout & zoom
- `METADATA_CACHING_IMPLEMENTATION.md` - Caching system
- `SESSION_SUMMARY.md` - Complete session overview

### Debug Information
- Console output shows cache hits/misses
- Status bar shows current operation
- Tooltips provide additional context
- Click status label to see raw Ollama response

### Support
- Check console for error messages
- Review log file (if enabled)
- Verify Ollama is running
- Test with simple document first

---

## What to Expect

### First Document (NEW files)
1. ⟳ Fetching metadata for each page (2-10 seconds each)
2. ✓ Metadata cached automatically
3. Auto-reorder by page numbers
4. Review and approve order
5. PDF created and metadata archived

### Second Document (SAME files)
1. ✓ Using cached metadata for each page (<0.01 seconds each)
2. 99% faster processing!
3. Auto-reorder still works
4. Same great workflow

### Mixed Scenario (SOME cached)
1. ✓ Cached files instant
2. ⟳ New files processed normally
3. Best of both worlds!

---

## Success Indicators

Look for these signs of proper operation:

✅ Console shows cache messages (✓ or ⟳)
✅ Page numbers detected with confidence icons
✅ Auto-reordering works correctly
✅ Zoom buttons appear in top-right
✅ Mouse wheel zooms preview
✅ Database file created (`metadata.db`)
✅ Subsequent runs are faster

---

## Enjoy the New Features!

- 🎯 **Automatic page ordering** saves manual work
- ⚡ **Smart caching** makes re-runs instant
- 🔍 **Zoom controls** help inspect details
- ⏱️ **Timeout config** adapts to your hardware

Happy scanning! 📄✨
