"""Phase 3a: Wire BundleThumbnailPanel into guided_bundle_workflow.py."""

import re

path = r"C:\development\scan_organization\src\ui\guided_bundle_workflow.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

original_len = len(src)

# ── 1. Add BundleThumbnailPanel import ───────────────────────────────────────
old = "from ui.bundle.draggable_thumbnail import DraggableThumbnail"
new = (
    "from ui.bundle.bundle_thumbnail_panel import BundleThumbnailPanel\n"
    "from ui.bundle.draggable_thumbnail import DraggableThumbnail"
)
assert src.count(old) == 1, f"Expected 1 match for import, got {src.count(old)}"
src = src.replace(old, new, 1)
print("1. Import added.")

# ── 2. Replace thumbnail panel creation in _init_ui ──────────────────────────
old = (
    "        # Left panel - Thumbnails with reordering (fixed width)\n"
    "        self.thumbnail_panel = self._create_thumbnail_panel()\n"
    "        self.thumbnail_panel.setFixedWidth(150)\n"
    "        content_layout.addWidget(self.thumbnail_panel)"
)
new = (
    "        # Left panel - Thumbnails with reordering (fixed width)\n"
    "        self.thumbnail_panel = BundleThumbnailPanel(dark_mode=self.dark_mode, parent=self)\n"
    "        self.thumbnail_panel.setFixedWidth(150)\n"
    "        self.thumbnail_panel.page_selected.connect(self._on_thumbnail_clicked)\n"
    "        self.thumbnail_panel.page_reorder_requested.connect(self._on_drop_requested)\n"
    "        self.thumbnail_panel.page_move_up_requested.connect(self._move_page_up)\n"
    "        self.thumbnail_panel.page_move_down_requested.connect(self._move_page_down)\n"
    "        self.thumbnail_panel.page_remove_requested.connect(self._on_remove_page)\n"
    "        self.thumbnail_panel.reanalyze_requested.connect(self._on_reanalyze_page)\n"
    "        self.thumbnail_panel.add_page_requested.connect(self._on_add_page)\n"
    "        content_layout.addWidget(self.thumbnail_panel)"
)
assert src.count(old) == 1, f"Expected 1 match for init_ui panel, got {src.count(old)}"
src = src.replace(old, new, 1)
print("2. Panel creation replaced.")

# ── 3. Delete _create_thumbnail_panel method (301-411) ───────────────────────
old_method = re.search(
    r"\n    def _create_thumbnail_panel\(self\).*?(?=\n    def _create_preview_panel)",
    src,
    re.DOTALL,
)
assert old_method, "_create_thumbnail_panel method not found"
src = src[: old_method.start()] + src[old_method.end() :]
print("3. _create_thumbnail_panel deleted.")

# ── 4. Replace _populate_thumbnails body ─────────────────────────────────────
# Match the whole method body up to (but not including) the blank line before next def
old_method = re.search(
    r"\n    def _populate_thumbnails\(self\):.*?(?=\n    def [a-z_])",
    src,
    re.DOTALL,
)
assert old_method, "_populate_thumbnails method not found"
new_body = (
    "\n"
    "    def _populate_thumbnails(self):\n"
    '        """Delegate to BundleThumbnailPanel.populate()."""\n'
    "        bundle = self.bundles[self.current_bundle_index]\n"
    "        self.thumbnail_panel.populate(\n"
    '            bundle.get("file_paths", []),\n'
    "            self.page_order,\n"
    "            self.current_page_index,\n"
    "            self.prototype_mode,\n"
    "        )\n"
)
src = src[: old_method.start()] + new_body + src[old_method.end() :]
print("4. _populate_thumbnails simplified.")

# ── 5. Delete _create_thumbnail_row method ───────────────────────────────────
# Note: method has multi-line signature: def _create_thumbnail_row(\n    self, ...
old_method = re.search(
    r"\n    def _create_thumbnail_row\(.*?(?=\n    def _update_metadata_form)",
    src,
    re.DOTALL,
)
assert old_method, "_create_thumbnail_row method not found"
src = src[: old_method.start()] + src[old_method.end() :]
print("5. _create_thumbnail_row deleted.")

# ── 6. Delete _on_drag_started no-op ─────────────────────────────────────────
old_method = re.search(
    r"\n    def _on_drag_started\(self, index: int\):.*?(?=\n    def [a-z_])",
    src,
    re.DOTALL,
)
assert old_method, "_on_drag_started method not found"
src = src[: old_method.start()] + src[old_method.end() :]
print("6. _on_drag_started deleted.")

# ── 7. Replace thumbnail section in _update_all_component_styles ─────────────
# Match from "# Update thumbnail panel" up to "# Update preview panel"
old_thumb_block = re.search(
    r"        # Update thumbnail panel\n"
    r"        if hasattr\(self, \"thumbnail_panel\"\):\n"
    r".*?"
    r"(?=\n        # Update preview panel)",
    src,
    re.DOTALL,
)
assert old_thumb_block, "Thumbnail block in _update_all_component_styles not found"
new_block = (
    "        # Update thumbnail panel\n"
    '        if hasattr(self, "thumbnail_panel"):\n'
    "            self.thumbnail_panel.apply_theme(self.dark_mode)"
)
src = src[: old_thumb_block.start()] + new_block + src[old_thumb_block.end() :]
print("7. _update_all_component_styles thumbnail section replaced.")

# ── 8. Remove DraggableThumbnail import (no longer used) ─────────────────────
old = "\nfrom ui.bundle.draggable_thumbnail import DraggableThumbnail"
assert src.count(old) == 1, f"Expected 1 match for DraggableThumbnail import, got {src.count(old)}"
src = src.replace(old, "", 1)
print("8. DraggableThumbnail import removed.")

with open(path, "w", encoding="utf-8") as f:
    f.write(src)

final_len = len(src)
print(
    f"\nDone. File size: {original_len} → {final_len} chars (removed {original_len - final_len} chars)"
)
