"""Phase 4: Create BundleReviewWidget and replace guided_bundle_workflow.py with shim."""

src_path = r"C:\development\scan_organization\src\ui\guided_bundle_workflow.py"
widget_path = r"C:\development\scan_organization\src\ui\bundle\bundle_review_widget.py"

with open(src_path, encoding="utf-8") as f:
    src = f.read()

# == 1. Update module docstring ==============================================
old_doc = (
    '"""\n'
    "Guided Bundle Review Workflow - Modern UI for reviewing AI bundle suggestions\n"
    "\n"
    "Features:\n"
    "- Wizard-style workflow through all bundle suggestions\n"
    "- Three-panel layout: thumbnails (reorderable) | large preview | metadata\n"
    "- Immediate PDF conversion on accept\n"
    "- Previous/Next bundle navigation\n"
    "- Progress tracking\n"
    "- Drag-and-drop page reordering with up/down buttons\n"
    '"""\n'
)
new_doc = (
    '"""Orchestrator widget: navigation state machine for the bundle review workflow.\n'
    "\n"
    "Composes BundleThumbnailPanel, BundlePreviewPanel, and BundleMetadataPanel\n"
    "into a QWidget (not QDialog) that can be embedded in a parent layout.\n"
    '"""\n'
)
assert src.count(old_doc) == 1
src = src.replace(old_doc, new_doc, 1)
print("1. Module docstring updated.")

# == 2. Remove QDialog from imports ==========================================
old = "    QDialog,\n"
assert src.count(old) == 1
src = src.replace(old, "", 1)
print("2. QDialog removed from imports.")

# == 3. Rename class and change base class ===================================
old = "class GuidedBundleWorkflow(QDialog):"
new = "class BundleReviewWidget(QWidget):"
assert src.count(old) == 1
src = src.replace(old, new, 1)
print("3. Class declaration updated.")

# == 4. Update class docstring ===============================================
old = (
    '    """\n'
    "    Guided workflow for reviewing bundle suggestions and converting to PDF.\n"
    "\n"
    "    Features:\n"
    "    - Step through bundles with Previous/Next\n"
    "    - Edit metadata, rotate, reorder pages\n"
    "    - Accept → Immediate PDF conversion\n"
    "    - Reject → Move to next\n"
    "    - Skip → Mark for later review\n"
    '    """\n'
)
new = (
    '    """Orchestrator widget composing the three bundle-review panels.\n'
    "\n"
    "    Owns the navigation state machine and wires cross-panel interactions.\n"
    "    Emits ``workflow_completed``, ``bundle_accepted``, and ``bundle_rejected``.\n"
    '    """\n'
)
assert src.count(old) == 1, f"Expected 1 match for class docstring, got {src.count(old)}"
src = src.replace(old, new, 1)
print("4. Class docstring updated.")

# == 5. Remove self.accept() call ============================================
old = "        if not self.embedded_mode:\n            self.accept()\n"
assert src.count(old) == 1, f"Expected 1 match for self.accept(), got {src.count(old)}"
src = src.replace(old, "", 1)
print("5. self.accept() removed.")

# == 6. Verify class name doesn't still say GuidedBundleWorkflow =============
remaining = src.count("GuidedBundleWorkflow")
if remaining > 0:
    print(f"WARNING: {remaining} remaining GuidedBundleWorkflow references")
else:
    print("6. No stale GuidedBundleWorkflow references.")

with open(widget_path, "w", encoding="utf-8") as f:
    f.write(src)
print(f"Written: {widget_path}")

# == 7. Write compatibility shim =============================================
shim = (
    '"""Backward-compatibility shim for guided_bundle_workflow.\n'
    "\n"
    "Import BundleReviewWidget under the old GuidedBundleWorkflow name so that\n"
    "code written before the Phase 5 cleanup continues to work unchanged.\n"
    '"""\n'
    "\n"
    "from ui.bundle.bundle_review_widget import BundleReviewWidget as GuidedBundleWorkflow\n"
    "\n"
    '__all__ = ["GuidedBundleWorkflow"]\n'
)
with open(src_path, "w", encoding="utf-8") as f:
    f.write(shim)
print(f"Shim written: {src_path}")

print("\nDone.")
