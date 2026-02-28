"""Phase 3b: Wire BundlePreviewPanel into guided_bundle_workflow.py."""

import re

path = r"C:\development\scan_organization\src\ui\guided_bundle_workflow.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

# ── 1. Add BundlePreviewPanel import ─────────────────────────────────────────
old = "from ui.bundle.bundle_thumbnail_panel import BundleThumbnailPanel"
new = (
    "from ui.bundle.bundle_preview_panel import BundlePreviewPanel\n"
    "from ui.bundle.bundle_thumbnail_panel import BundleThumbnailPanel"
)
assert src.count(old) == 1
src = src.replace(old, new, 1)
print("1. Import added.")

# ── 2. Remove init vars: zoom_level, rotation_angle, original_pixmap ─────────
old = "        self.zoom_level = 100\n" "        self.rotation_angle = 0\n"
assert src.count(old) == 1, f"Expected 1 match, got {src.count(old)}"
src = src.replace(old, "", 1)

old = "        self.original_pixmap = None  # Store original pixmap for fit calculations\n"
assert src.count(old) == 1, f"Expected 1 match for original_pixmap, got {src.count(old)}"
src = src.replace(old, "", 1)
print("2. Init vars removed.")

# ── 3. Delete _create_preview_panel and replace call in _init_ui ─────────────
# First replace the CALL in _init_ui
old = (
    "        # Center panel - Large preview (takes remaining space)\n"
    "        preview_panel = self._create_preview_panel()\n"
    "        content_layout.addWidget(preview_panel, stretch=1)"
)
new = (
    "        # Center panel - Large preview (takes remaining space)\n"
    "        self.preview_panel = BundlePreviewPanel(dark_mode=self.dark_mode, parent=self)\n"
    "        content_layout.addWidget(self.preview_panel, stretch=1)"
)
assert src.count(old) == 1, f"Expected 1 match for preview init, got {src.count(old)}"
src = src.replace(old, new, 1)
print("3a. Preview panel creation replaced.")

# Delete the _create_preview_panel method (up to _create_metadata_panel)
old_method = re.search(
    r"\n    def _create_preview_panel\(self\).*?(?=\n    def _create_metadata_panel)",
    src,
    re.DOTALL,
)
assert old_method, "_create_preview_panel method not found"
src = src[: old_method.start()] + src[old_method.end() :]
print("3b. _create_preview_panel deleted.")

# ── 4. Replace _display_current_page body ────────────────────────────────────
# Keep the method but simplify to just create pixmap + delegate to panel
old_method = re.search(
    r"\n    def _display_current_page\(self\):.*?(?=\n    def _apply_transform)",
    src,
    re.DOTALL,
)
assert old_method, "_display_current_page method not found"
new_method = (
    "\n"
    "    def _display_current_page(self):\n"
    '        """Create a pixmap for the current page and hand it to preview_panel."""\n'
    "        bundle = self.bundles[self.current_bundle_index]\n"
    '        file_paths = bundle.get("file_paths", [])\n'
    "\n"
    "        if not file_paths or self.current_page_index >= len(self.page_order):\n"
    "            return\n"
    "\n"
    "        actual_index = self.page_order[self.current_page_index]\n"
    "        file_path = file_paths[actual_index]\n"
    "\n"
    "        if self.prototype_mode:\n"
    "            pixmap = QPixmap(600, 800)\n"
    "            base_color = QColor(220 + (actual_index * 10) % 30, 230, 245)\n"
    "            pixmap.fill(base_color)\n"
    "            painter = QPainter(pixmap)\n"
    "            painter.drawText(\n"
    "                pixmap.rect(),\n"
    "                Qt.AlignmentFlag.AlignCenter,\n"
    '                f"Page {actual_index + 1}\\n\\n(Mock Preview)",\n'
    "            )\n"
    "            painter.end()\n"
    "        else:\n"
    "            pixmap = QPixmap(file_path)\n"
    "            if pixmap.isNull():\n"
    "                pixmap = QPixmap(600, 800)\n"
    "                pixmap.fill(QColor(240, 240, 240))\n"
    "                painter = QPainter(pixmap)\n"
    "                painter.drawText(\n"
    "                    pixmap.rect(),\n"
    "                    Qt.AlignmentFlag.AlignCenter,\n"
    '                    f"Page {actual_index + 1}\\n\\nFailed to load image:\\n{file_path}",\n'
    "                )\n"
    "                painter.end()\n"
    "\n"
    "        self.preview_panel.display_page(\n"
    "            pixmap, self.current_page_index + 1, len(self.page_order)\n"
    "        )\n"
)
src = src[: old_method.start()] + new_method + src[old_method.end() :]
print("4. _display_current_page simplified.")

# ── 5. Delete _apply_transform method ────────────────────────────────────────
old_method = re.search(
    r"\n    def _apply_transform\(self, pixmap.*?(?=\n    def _on_zoom_in)",
    src,
    re.DOTALL,
)
assert old_method, "_apply_transform method not found"
src = src[: old_method.start()] + src[old_method.end() :]
print("5. _apply_transform deleted.")

# ── 6. Update _on_zoom_in / _on_zoom_out to read panel.zoom_level ────────────
old = "        new_zoom = min(400, self.zoom_level + 25)"
new = "        new_zoom = min(400, self.preview_panel.zoom_level + 25)"
assert src.count(old) == 1
src = src.replace(old, new, 1)

old = "        new_zoom = max(25, self.zoom_level - 25)"
new = "        new_zoom = max(25, self.preview_panel.zoom_level - 25)"
assert src.count(old) == 1
src = src.replace(old, new, 1)
print("6. zoom_in/out updated.")

# ── 7. Replace _on_zoom_changed body ─────────────────────────────────────────
old = (
    "    def _on_zoom_changed(self, value: int):\n"
    '        """Handle zoom change."""\n'
    "        self.zoom_level = value\n"
    "        self._display_current_page()"
)
new = (
    "    def _on_zoom_changed(self, value: int):\n"
    '        """Propagate zoom change to the preview panel."""\n'
    "        self.preview_panel.set_zoom(value)"
)
assert src.count(old) == 1, f"Expected 1 match for _on_zoom_changed, got {src.count(old)}"
src = src.replace(old, new, 1)
print("7. _on_zoom_changed updated.")

# ── 8. Rewrite fit methods to use panel API ───────────────────────────────────
old_method = re.search(
    r"\n    def _on_fit_width\(self\):.*?(?=\n    def _on_fit_height)",
    src,
    re.DOTALL,
)
assert old_method, "_on_fit_width not found"
new_body = (
    "\n"
    "    def _on_fit_width(self):\n"
    '        """Fit image to preview panel width."""\n'
    "        size = self.preview_panel.get_original_pixel_size(rotation_adjusted=True)\n"
    "        if size is None:\n"
    "            return\n"
    "        image_width = size[0]\n"
    "        container_width = self.preview_panel.get_container_size()[0] - 40\n"
    "        if image_width > 0:\n"
    "            zoom = max(25, min(400, int(container_width / image_width * 100)))\n"
    "            self.zoom_spinner.setValue(zoom)\n"
)
src = src[: old_method.start()] + new_body + src[old_method.end() :]
print("8a. _on_fit_width rewritten.")

old_method = re.search(
    r"\n    def _on_fit_height\(self\):.*?(?=\n    def _on_fit_window)",
    src,
    re.DOTALL,
)
assert old_method, "_on_fit_height not found"
new_body = (
    "\n"
    "    def _on_fit_height(self):\n"
    '        """Fit image to preview panel height."""\n'
    "        size = self.preview_panel.get_original_pixel_size(rotation_adjusted=True)\n"
    "        if size is None:\n"
    "            return\n"
    "        image_height = size[1]\n"
    "        container_height = self.preview_panel.get_container_size()[1] - 100\n"
    "        if image_height > 0:\n"
    "            zoom = max(25, min(400, int(container_height / image_height * 100)))\n"
    "            self.zoom_spinner.setValue(zoom)\n"
)
src = src[: old_method.start()] + new_body + src[old_method.end() :]
print("8b. _on_fit_height rewritten.")

old_method = re.search(
    r"\n    def _on_fit_window\(self\):.*?(?=\n    def _apply_default_zoom)",
    src,
    re.DOTALL,
)
assert old_method, "_on_fit_window not found"
new_body = (
    "\n"
    "    def _on_fit_window(self):\n"
    '        """Fit image to preview panel (both width and height)."""\n'
    "        size = self.preview_panel.get_original_pixel_size(rotation_adjusted=True)\n"
    "        if size is None:\n"
    "            return\n"
    "        image_width, image_height = size\n"
    "        container_width = self.preview_panel.get_container_size()[0] - 40\n"
    "        container_height = self.preview_panel.get_container_size()[1] - 100\n"
    "        if image_width > 0 and image_height > 0:\n"
    "            zoom_w = int(container_width / image_width * 100)\n"
    "            zoom_h = int(container_height / image_height * 100)\n"
    "            zoom = max(25, min(400, min(zoom_w, zoom_h)))\n"
    "            self.zoom_spinner.setValue(zoom)\n"
)
src = src[: old_method.start()] + new_body + src[old_method.end() :]
print("8c. _on_fit_window rewritten.")

# ── 9. Update _apply_default_zoom for custom_% ───────────────────────────────
old = (
    '        elif self.default_zoom_mode == "custom_%":\n'
    "            # Zoom level already set in _load_current_bundle\n"
    "            self._display_current_page()"
)
new = (
    '        elif self.default_zoom_mode == "custom_%":\n'
    "            self.preview_panel.set_zoom(self.default_zoom_percent)"
)
assert (
    src.count(old) == 1
), f"Expected 1 match for _apply_default_zoom custom_%, got {src.count(old)}"
src = src.replace(old, new, 1)
print("9. _apply_default_zoom custom_% updated.")

# ── 10. Replace _on_rotate_ccw and _on_rotate_cw ─────────────────────────────
old = (
    "    def _on_rotate_ccw(self):\n"
    '        """Rotate counter-clockwise."""\n'
    "        self.rotation_angle = (self.rotation_angle - 90) % 360\n"
    "        self._display_current_page()"
)
new = (
    "    def _on_rotate_ccw(self):\n"
    '        """Rotate counter-clockwise."""\n'
    "        self.preview_panel.rotate_ccw()"
)
assert src.count(old) == 1, f"Expected 1 match for _on_rotate_ccw, got {src.count(old)}"
src = src.replace(old, new, 1)

old = (
    "    def _on_rotate_cw(self):\n"
    '        """Rotate clockwise."""\n'
    "        self.rotation_angle = (self.rotation_angle + 90) % 360\n"
    "        self._display_current_page()"
)
new = (
    "    def _on_rotate_cw(self):\n"
    '        """Rotate clockwise."""\n'
    "        self.preview_panel.rotate_cw()"
)
assert src.count(old) == 1, f"Expected 1 match for _on_rotate_cw, got {src.count(old)}"
src = src.replace(old, new, 1)
print("10. Rotation methods updated.")

# ── 11. Replace rotation_angle = 0 in _load_current_bundle ───────────────────
old = "        self.rotation_angle = 0\n"
assert src.count(old) == 1, f"Expected 1 match for rotation_angle=0, got {src.count(old)}"
src = src.replace(old, "        self.preview_panel.reset_rotation()\n", 1)

# Replace zoom_level init in _load_current_bundle
old = (
    '        if self.default_zoom_mode == "custom_%":\n'
    "            self.zoom_level = self.default_zoom_percent\n"
    "        else:\n"
    "            self.zoom_level = 100  # Will be recalculated by fit methods\n"
)
new = (
    '        if self.default_zoom_mode == "custom_%":\n'
    "            self.preview_panel.set_zoom(self.default_zoom_percent)\n"
    "        else:\n"
    "            self.preview_panel.set_zoom(100)  # Will be recalculated by fit methods\n"
)
assert src.count(old) == 1, f"Expected 1 match for zoom_level init, got {src.count(old)}"
src = src.replace(old, new, 1)
print("11. _load_current_bundle updated.")

# ── 12. Replace self.rotation_angle in _complete_pdf_conversion ──────────────
old = "                bundle, metadata, ordered_paths, self.rotation_angle\n"
new = "                bundle, metadata, ordered_paths, self.preview_panel.rotation_angle\n"
assert src.count(old) == 1, f"Expected 1 match for pdf rotation, got {src.count(old)}"
src = src.replace(old, new, 1)
print("12. PDF conversion rotation updated.")

# ── 13. Replace preview section in _update_all_component_styles ──────────────
old_block = re.search(
    r"        # Update preview panel\n"
    r"        if hasattr\(self, \"preview_container\"\):\n"
    r".*?"
    r"(?=\n        # Update metadata)",
    src,
    re.DOTALL,
)
assert old_block, "Preview block in _update_all_component_styles not found"
new_block = (
    "        # Update preview panel\n"
    '        if hasattr(self, "preview_panel"):\n'
    "            self.preview_panel.apply_theme(self.dark_mode)"
)
src = src[: old_block.start()] + new_block + src[old_block.end() :]
print("13. _update_all_component_styles preview section replaced.")

# ── 14. Verify no stale self.zoom_level / self.rotation_angle / self.original_pixmap ──
stale = []
for var in (
    "self.zoom_level",
    "self.rotation_angle",
    "self.original_pixmap",
    "self.preview_container",
    "self.large_preview",
    "self.page_label",
):
    count = src.count(var)
    if count > 0:
        stale.append(f"  {var}: {count} occurrences")
if stale:
    print("WARNING - stale references found:")
    for s in stale:
        print(s)
else:
    print("14. No stale references.")

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("\nDone.")
