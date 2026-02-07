# Guided Bundle Workflow Integration - Verification Checklist

## Quick Verification (5 minutes)

### 1. Run Integration Tests
```powershell
python scripts/test_guided_integration.py
```

**Expected Output**:
```
============================================================
Testing Guided Bundle Workflow Integration
============================================================
Testing bundle completeness detection...
[OK] Bundle completeness detection works correctly

Testing bundle sorting...
[OK] Bundle sorting works correctly
  Order: Complete (0.9) -> Complete (0.8) -> Incomplete (0.7) -> Incomplete (0.6)

Testing bundle metadata update...
[OK] Required methods exist

============================================================
[SUCCESS] All tests passed!
============================================================
```

- [ ] All tests pass
- [ ] No errors or warnings

### 2. Run Demo Workflow
```powershell
python scripts/demo_guided_workflow.py
```

**Expected Behavior**:
- [ ] Workflow window opens
- [ ] Shows "Bundle 1 of 7" in header
- [ ] Left panel shows thumbnail images
- [ ] Center panel shows large preview
- [ ] Right panel shows metadata form
- [ ] Can click "Next Bundle" to navigate
- [ ] Can click "Accept & Convert to PDF" (shows mock conversion)
- [ ] Can complete all 7 bundles
- [ ] Shows completion summary at end

### 3. Check Code Quality
```powershell
# Syntax check
python -m py_compile src/services/bundling_service.py
python -m py_compile src/db/repositories/bundle_repo.py
python -m py_compile src/ui/guided_bundle_workflow.py

# Linting (should show minimal warnings)
ruff check src/services/bundling_service.py --select E,F
ruff check src/db/repositories/bundle_repo.py --select E,F
ruff check src/ui/guided_bundle_workflow.py --select E,F
```

- [ ] No syntax errors
- [ ] No critical linting errors (E, F)

## Full Application Testing (15 minutes)

### 4. Launch Application
```powershell
python src/main.py
```

- [ ] Application launches without errors
- [ ] Main window appears

### 5. Test Bundle Generation
1. Click "Convert Scans" button
2. Wait for analysis to complete

**Expected**:
- [ ] Progress dialog shows during analysis
- [ ] Guided workflow opens (NOT card-based view)
- [ ] Shows bundle count in header (e.g., "Bundle 1 of 12")
- [ ] Shows real images (not colored placeholders)

### 6. Test Bundle Navigation
In the guided workflow:
- [ ] Click "Next Bundle" → advances to next bundle
- [ ] Click "Previous Bundle" → goes back to previous bundle
- [ ] Progress label updates correctly (Bundle X of Y)
- [ ] Thumbnails update for new bundle
- [ ] Preview updates for new bundle
- [ ] Metadata updates for new bundle

### 7. Test Page Reordering
For a multi-page bundle:
- [ ] Drag a thumbnail to new position → pages reorder
- [ ] Click up arrow on page 2 → moves to position 1
- [ ] Click down arrow on page 1 → moves to position 2
- [ ] Preview updates when clicking thumbnails
- [ ] Page numbers update correctly

### 8. Test Metadata Editing
- [ ] Click in "Company" field → can type
- [ ] Edit "Document Type" field
- [ ] Edit "Document Date" field
- [ ] Edit "Output Filename" field
- [ ] Changes are retained while navigating pages

### 9. Test Zoom/Rotate Controls
- [ ] Click zoom buttons (50%, 100%, 150%) → preview scales
- [ ] Click rotate buttons (90°, 180°, 270°) → preview rotates
- [ ] Transformations persist when switching pages

### 10. Test Bundle Actions

#### Accept Bundle
1. Click "Accept & Convert to PDF"
2. Wait for PDF conversion

**Expected**:
- [ ] Progress dialog appears
- [ ] PDF created in output directory
- [ ] Success dialog shows with "Open PDF" option
- [ ] Clicking "Open" opens PDF in default app
- [ ] PDF contains correct pages in correct order
- [ ] PDF has correct rotation applied
- [ ] Workflow advances to next bundle automatically
- [ ] Stats update (Accepted count increases)

#### Reject Bundle
1. Click "Reject"

**Expected**:
- [ ] Advances to next bundle immediately
- [ ] Stats update (Rejected count increases)
- [ ] No PDF created

#### Skip Bundle
1. Click "Skip"

**Expected**:
- [ ] Advances to next bundle
- [ ] Stats update (Skipped count increases)
- [ ] Bundle marked for later review

### 11. Test Workflow Completion
Process all bundles until the end:

**Expected**:
- [ ] Completion summary dialog shows
- [ ] Displays correct stats (Accepted/Rejected/Skipped)
- [ ] Clicking "OK" closes workflow
- [ ] Returns to main window
- [ ] Can close main window normally

### 12. Verify Database Updates
Check the database:

```powershell
# Open database with SQLite browser or run query
sqlite3 %APPDATA%\WinScanLLM\analysis.db "SELECT status, company, document_type FROM document_bundles ORDER BY id DESC LIMIT 5;"
```

**Expected**:
- [ ] Accepted bundles have status = "accepted"
- [ ] Rejected bundles have status = "rejected"
- [ ] Metadata fields updated correctly

### 13. Verify PDF Output
Check output directory (configured in settings):

**Expected**:
- [ ] PDFs exist for accepted bundles
- [ ] Filenames match edited metadata
- [ ] PDFs open correctly
- [ ] PDFs contain correct pages
- [ ] Page order matches reordered sequence
- [ ] Rotation applied correctly

## Edge Cases (10 minutes)

### 14. Test Single-Page Bundle
Find or create a bundle with only 1 page:

- [ ] Shows "Page 1 of 1"
- [ ] Cannot reorder (only 1 page)
- [ ] Can still accept/reject/skip
- [ ] PDF contains single page

### 15. Test Incomplete Bundle
Find or create a bundle missing pages (e.g., "1 of 5, 2 of 5, 5 of 5"):

- [ ] Shows as incomplete in workflow
- [ ] Can still accept (creates PDF with available pages)
- [ ] Metadata indicates missing pages (if shown)

### 16. Test Large Bundle (10+ pages)
Find or create a bundle with 10+ pages:

- [ ] Thumbnail panel scrolls correctly
- [ ] All pages load without errors
- [ ] Reordering still works
- [ ] PDF conversion succeeds

### 17. Test Image Loading Error
Temporarily rename an image file:

- [ ] Placeholder shown instead of image
- [ ] Error message displayed in placeholder
- [ ] Workflow continues normally
- [ ] Can skip or reject bundle

### 18. Test Empty Analysis
Run "Convert Scans" with no analyzed files:

**Expected**:
- [ ] Shows "No bundle suggestions" message
- [ ] Does NOT crash
- [ ] Falls back to manual workflow (if implemented)

## Performance (5 minutes)

### 19. Test Large Dataset
With 50+ analyzed files:

- [ ] Bundle generation completes in < 10 seconds
- [ ] Workflow loads without lag
- [ ] Navigation is responsive
- [ ] PDF conversion completes in < 5 seconds per bundle

### 20. Test Memory Usage
Monitor memory during full workflow:

- [ ] No memory leaks
- [ ] Memory usage reasonable (< 500MB)
- [ ] Application remains responsive

## Regression Testing (5 minutes)

### 21. Test Old Workflow Still Works
If manual stitching workflow still exists:

- [ ] Can still access manual workflow
- [ ] Manual workflow functions normally
- [ ] No conflicts with new workflow

### 22. Test Settings
Open settings dialog:

- [ ] Output directory setting works
- [ ] Provider settings unaffected
- [ ] Auto-analysis settings unaffected

## Final Checklist

### Code Quality
- [ ] No syntax errors
- [ ] Linting passes (minimal warnings)
- [ ] All imports work
- [ ] Tests pass

### Functionality
- [ ] Workflow launches on "Convert Scans"
- [ ] Real images load correctly
- [ ] Bundle sorting works (complete first)
- [ ] Page reordering works (drag + buttons)
- [ ] Metadata editing works
- [ ] PDF conversion works
- [ ] Database updates correctly
- [ ] Navigation works smoothly

### User Experience
- [ ] UI is responsive
- [ ] No crashes or freezes
- [ ] Error messages are clear
- [ ] Success feedback is immediate
- [ ] Progress tracking is accurate

### Performance
- [ ] Fast bundle generation
- [ ] Fast image loading
- [ ] Fast PDF conversion
- [ ] No memory leaks

## Issues Found

Document any issues here:

### Issue 1
- **Description**:
- **Severity**: Critical / High / Medium / Low
- **Steps to Reproduce**:
- **Expected**:
- **Actual**:

### Issue 2
- **Description**:
- **Severity**: Critical / High / Medium / Low
- **Steps to Reproduce**:
- **Expected**:
- **Actual**:

## Sign-Off

- [ ] All critical tests pass
- [ ] All high-priority tests pass
- [ ] No critical issues found
- [ ] Ready for production use

**Tested By**: _______________
**Date**: _______________
**Version**: _______________

---

## Troubleshooting Common Issues

### Issue: "ModuleNotFoundError: No module named 'PIL'"
**Solution**: Install Pillow
```powershell
pip install Pillow
```

### Issue: PDFs not created
**Solution**: Check output directory exists and is writable
```powershell
# View current setting
python -c "from config.config_manager import ConfigManager; print(ConfigManager().get_setting('OutputDirectory', 'path'))"
```

### Issue: Images not loading
**Solution**: Check file paths are valid and files exist
```powershell
# Verify files exist
dir <path-to-image>
```

### Issue: Database errors
**Solution**: Check database file exists and is not corrupted
```powershell
# Check database location
dir %APPDATA%\WinScanLLM\analysis.db
```

### Issue: Workflow doesn't open
**Solution**: Check for errors in console output
```powershell
# Run with verbose logging
python src/main.py 2>&1 | tee workflow-debug.log
```
