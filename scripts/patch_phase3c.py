"""Phase 3c: Wire BundleMetadataPanel into guided_bundle_workflow.py."""

import re

path = r"C:\development\scan_organization\src\ui\guided_bundle_workflow.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

# == 1. Add import ===========================================================
old = "from ui.bundle.bundle_preview_panel import BundlePreviewPanel"
new = (
    "from ui.bundle.bundle_metadata_panel import BundleMetadataPanel\n"
    "from ui.bundle.bundle_preview_panel import BundlePreviewPanel"
)
assert src.count(old) == 1
src = src.replace(old, new, 1)
print("1. Import added.")

# == 2. Remove stale __init__ vars ===========================================
for snippet in [
    "        # Metadata inputs\n        self.metadata_inputs = {}\n\n",
    "        # Accordion sections\n        self.accordion_sections = []\n\n",
    "        # Edit mode tracking\n        self.edit_mode = False\n        self.original_metadata = {}\n\n",
    "        # Output filename tracking\n        self.output_filename_manually_edited = False\n",
]:
    assert src.count(snippet) == 1, f"Expected 1 match for: {snippet[:50]!r}"
    src = src.replace(snippet, "", 1)
print("2. __init__ vars removed.")

# == 3. Replace metadata panel creation in _init_ui ==========================
old = (
    "        # Right panel - Metadata (fixed width)\n"
    "        self.metadata_panel = self._create_metadata_panel()\n"
    "        self.metadata_panel.setFixedWidth(380)\n"
    "        content_layout.addWidget(self.metadata_panel)"
)
new = (
    "        # Right panel - Metadata (fixed width)\n"
    "        self.metadata_panel = BundleMetadataPanel(dark_mode=self.dark_mode, parent=self)\n"
    "        self.metadata_panel.setFixedWidth(380)\n"
    "        self.metadata_panel.metadata_changed.connect(self._on_metadata_changed)\n"
    "        self.metadata_panel.save_requested.connect(self._on_metadata_save)\n"
    "        self.metadata_panel.cancel_requested.connect(self._on_metadata_cancel)\n"
    "        content_layout.addWidget(self.metadata_panel)"
)
assert src.count(old) == 1
src = src.replace(old, new, 1)
print("3. _init_ui metadata panel creation replaced.")

# == 4. Simplify _load_current_bundle ========================================
old = (
    "        self._update_header()\n"
    "        self._populate_thumbnails()\n"
    "        self._update_metadata_form()\n"
    "        self._display_current_page()\n"
    "\n"
    "        # Reset output filename manual edit flag for new bundle\n"
    "        self.output_filename_manually_edited = False\n"
    "\n"
    "        # Update output filename based on bundle metadata\n"
    '        if hasattr(self, "output_filename_input"):\n'
    "            self._update_output_filename()\n"
    "\n"
    '        if hasattr(self, "accordion_sections"):  # Only if accordions initialized\n'
    "            self._refresh_accordion_content()\n"
    "\n"
    "        # Apply configured zoom mode after UI is fully laid out\n"
    "        # Use longer delay to ensure container dimensions are available\n"
    "        QTimer.singleShot(300, self._apply_default_zoom)"
)
new = (
    "        self._update_header()\n"
    "        self._populate_thumbnails()\n"
    "        self._display_current_page()\n"
    "        self.metadata_panel.load_bundle(bundle, self.page_order, 0, self.prototype_mode)\n"
    "\n"
    "        # Apply configured zoom mode after UI is fully laid out\n"
    "        # Use longer delay to ensure container dimensions are available\n"
    "        QTimer.singleShot(300, self._apply_default_zoom)"
)
assert src.count(old) == 1, f"Expected 1 match for _load_current_bundle block, got {src.count(old)}"
src = src.replace(old, new, 1)
print("4. _load_current_bundle simplified.")

# == 5. Replace _on_accept_bundle metadata assembly ==========================
old = (
    "        # Get metadata edits\n"
    "        metadata = {\n"
    '            "document_type": self.metadata_inputs["document_type"].currentText(),\n'
    '            "company": self.metadata_inputs["company"].currentText(),\n'
    '            "document_date": self.metadata_inputs["document_date"].text(),\n'
    "        }\n"
    "\n"
    "        # Get output filename from textbox (user may have edited it)\n"
    '        if hasattr(self, "output_filename_input"):\n'
    "            raw_filename = self.output_filename_input.text().strip()\n"
    "        else:\n"
    "            # Fallback if textbox doesn't exist\n"
    "            raw_filename = self._generate_suggested_filename(bundle)\n"
    "\n"
    "        # Enforce .PDF extension (strips any existing extension user may have typed)\n"
    '        metadata["output_filename"] = self._get_pdf_filename(raw_filename)'
)
new = (
    "        # Get metadata and output filename from panel\n"
    "        metadata = self.metadata_panel.get_metadata()\n"
    "        raw_filename = self.metadata_panel.get_output_filename().strip()\n"
    "        # Enforce .PDF extension (strips any existing extension user may have typed)\n"
    '        metadata["output_filename"] = self._get_pdf_filename(raw_filename)'
)
assert src.count(old) == 1, f"Expected 1 match for _on_accept_bundle block, got {src.count(old)}"
src = src.replace(old, new, 1)
print("5. _on_accept_bundle updated.")

# == 6. Update _on_reanalyze_page to use metadata_panel.load_bundle ==========
old = "                    # Refresh UI\n" "                    self._refresh_accordion_content()"
new = (
    "                    # Refresh UI\n"
    "                    self.metadata_panel.load_bundle(\n"
    "                        bundle, self.page_order, self.current_page_index, self.prototype_mode\n"
    "                    )"
)
assert src.count(old) == 1, f"Expected 1 match for _on_reanalyze_page block, got {src.count(old)}"
src = src.replace(old, new, 1)
print("6. _on_reanalyze_page updated.")

# == 7. Delete form-builder methods block (L305-L1010) =======================
# _create_metadata_panel through _format_file_size; next method is _create_action_bar
m = re.search(
    r"\n    def _create_metadata_panel\(self\).*?(?=\n    def _create_action_bar)",
    src,
    re.DOTALL,
)
assert m, "_create_metadata_panel..._create_action_bar block not found"
src = src[: m.start()] + src[m.end() :]
print("7. Form-builder methods deleted (_create_metadata_panel through _format_file_size).")

# == 8. Delete _update_metadata_form ==========================================
m = re.search(
    r"\n    def _update_metadata_form\(self\).*?(?=\n    def _display_current_page)",
    src,
    re.DOTALL,
)
assert m, "_update_metadata_form not found"
src = src[: m.start()] + src[m.end() :]
print("8. _update_metadata_form deleted.")

# == 9. Delete _on_output_filename_manual_edit, _update_output_filename, _sanitize_filename
m = re.search(
    r"\n    def _on_output_filename_manual_edit\(self\).*?(?=\n    def _get_pdf_filename)",
    src,
    re.DOTALL,
)
assert m, "_on_output_filename_manual_edit.._sanitize_filename block not found"
src = src[: m.start()] + src[m.end() :]
print("9. _on_output_filename_manual_edit, _update_output_filename, _sanitize_filename deleted.")

# == 10. Delete _refresh_accordion_content ====================================
m = re.search(
    r"\n    def _refresh_accordion_content\(self\).*?(?=\n    def _toggle_theme)",
    src,
    re.DOTALL,
)
assert m, "_refresh_accordion_content not found"
src = src[: m.start()] + src[m.end() :]
print("10. _refresh_accordion_content deleted.")

# == 11. Clean _update_all_component_styles ==================================

# 11a. Replace stale metadata_scroll block with metadata_panel.apply_theme
old_block = (
    "        # Update metadata panel\n"
    '        if hasattr(self, "metadata_scroll"):\n'
    "            self.metadata_scroll.setStyleSheet(f\"background: {theme['metadata_bg']};\")\n"
    "\n"
    "        # Update action bar"
)
new_block = (
    "        # Update metadata panel\n"
    '        if hasattr(self, "metadata_panel"):\n'
    "            self.metadata_panel.apply_theme(self.dark_mode)\n"
    "\n"
    "        # Update action bar"
)
assert (
    src.count(old_block) == 1
), f"Expected 1 match for metadata_scroll block, got {src.count(old_block)}"
src = src.replace(old_block, new_block, 1)
print("11a. metadata_scroll block replaced with apply_theme call.")

# 11b. Remove the second (now redundant) metadata_panel.setStyleSheet block
old_block = (
    "\n"
    "        # Update metadata panel background\n"
    '        if hasattr(self, "metadata_panel"):\n'
    "            self.metadata_panel.setStyleSheet(f\"background: {theme['metadata_bg']};\")\n"
    "\n"
    "        # Force widget update"
)
new_block = "\n" "        # Force widget update"
assert (
    src.count(old_block) == 1
), f"Expected 1 match for second metadata_panel block, got {src.count(old_block)}"
src = src.replace(old_block, new_block, 1)
print("11b. Redundant metadata_panel.setStyleSheet removed.")

# 11c. Remove accordion + output_filename blocks (from "# Update accordion sections styling"
#      to the end of _update_all_component_styles, which is just before _enter_edit_mode)
m = re.search(
    r"\n\n        # Update accordion sections styling\n        if hasattr\(self, \"accordion_sections\"\):.*?(?=\n\n    def _enter_edit_mode)",
    src,
    re.DOTALL,
)
assert m, "accordion_sections styling block not found"
src = src[: m.start()] + src[m.end() :]
print("11c. Accordion + output_filename styling blocks removed.")

# == 12. Delete _enter_edit_mode, _on_save_metadata_changes,
#         _on_cancel_metadata_changes, _exit_edit_mode =======================
m = re.search(
    r"\n    def _enter_edit_mode\(self\).*?(?=\n    def showEvent)",
    src,
    re.DOTALL,
)
assert m, "_enter_edit_mode.._exit_edit_mode block not found"
src = src[: m.start()] + src[m.end() :]
print("12. _enter_edit_mode, _on_save/cancel, _exit_edit_mode deleted.")

# == 13. Add new handler methods before showEvent ============================
old = "\n    def showEvent(self, event):  # noqa: N802"
new = (
    "\n"
    "    def _on_metadata_changed(self) -> None:\n"
    '        """Disable cross-panel interaction while user is editing metadata."""\n'
    "        self.thumbnail_panel.setEnabled(False)\n"
    "        self.action_bar.setEnabled(False)\n"
    "\n"
    "    def _on_metadata_save(self, metadata: dict) -> None:\n"
    '        """Re-enable panels after metadata save."""\n'
    "        self.thumbnail_panel.setEnabled(True)\n"
    "        self.action_bar.setEnabled(True)\n"
    "        QMessageBox.information(\n"
    "            self,\n"
    '            "Changes Saved",\n'
    '            "Metadata changes saved for this page.\\n\\n"\n'
    '            "Changes will be applied when you accept or save the bundle.",\n'
    "        )\n"
    "\n"
    "    def _on_metadata_cancel(self) -> None:\n"
    '        """Re-enable panels after metadata cancel."""\n'
    "        self.thumbnail_panel.setEnabled(True)\n"
    "        self.action_bar.setEnabled(True)\n"
    "\n"
    "    def showEvent(self, event):  # noqa: N802"
)
assert src.count(old) == 1, f"Expected 1 match for showEvent, got {src.count(old)}"
src = src.replace(old, new, 1)
print("13. New handler methods added.")

# == 14. Verify no stale references ==========================================
stale = []
for var in (
    "self.metadata_inputs",
    "self.accordion_sections",
    "self.edit_mode",
    "self.original_metadata",
    "self.output_filename_manually_edited",
    "self.output_filename_input",
    "self.metadata_save_btn",
    "self.metadata_cancel_btn",
    "self.metadata_scroll",
    "_update_metadata_form",
    "_refresh_accordion_content",
    "_create_metadata_panel",
    "_create_metadata_form",
    "_create_accordion_section",
):
    count = src.count(var)
    if count > 0:
        stale.append(f"  {var}: {count}")
if stale:
    print("WARNING - stale references:")
    for s in stale:
        print(s)
else:
    print("14. No stale references.")

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("\nDone.")
