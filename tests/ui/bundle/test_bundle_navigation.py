"""Regression tests for bundle page-navigation behaviour.

Covers two defects introduced when page navigation was restored:

1. Perf: clicking a thumbnail rebuilt the entire thumbnail list, re-decoding
   every page image from disk on every click. Navigation must now use the
   selection-only fast path and a per-path thumbnail cache.
2. Carry-over: clicking a thumbnail never refreshed the metadata panel, so the
   previously-viewed page's fields (e.g. Page Number) stayed on screen.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QLineEdit

from ui.bundle.bundle_metadata_panel import BundleMetadataPanel
from ui.bundle.bundle_review_widget import BundleReviewWidget
from ui.bundle.bundle_thumbnail_panel import BundleThumbnailPanel

from .bundle_test_helpers import create_mock_bundles

# ---------------------------------------------------------------------------
# Thumbnail panel: caching + selection-only update (perf fix)
# ---------------------------------------------------------------------------


def test_thumbnail_pixmaps_are_cached_by_path(qapp, tmp_path):
    """Real file thumbnails are decoded once and reused on subsequent rebuilds."""
    img_path = tmp_path / "page1.png"
    image = QImage(120, 160, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    assert image.save(str(img_path))

    panel = BundleThumbnailPanel(dark_mode=False)
    panel.populate([str(img_path)], [0], 0, prototype_mode=False)
    assert str(img_path) in panel._thumb_cache
    cached = panel._thumb_cache[str(img_path)]

    # Rebuilding must reuse the exact cached pixmap — no second disk decode.
    panel.populate([str(img_path)], [0], 0, prototype_mode=False)
    assert panel._thumb_cache[str(img_path)] is cached


def test_set_selected_updates_highlight_without_rebuilding(qapp):
    """set_selected() moves the highlight and keeps the same widget objects."""
    panel = BundleThumbnailPanel(dark_mode=False)
    file_paths = [f"mock_{i}.png" for i in range(3)]
    panel.populate(file_paths, [0, 1, 2], 0, prototype_mode=True)

    thumb0 = panel._thumbnails[0]
    thumb2 = panel._thumbnails[2]

    panel.set_selected(2)

    assert panel._current_selected == 2
    # Widgets are reused, not recreated.
    assert panel._thumbnails[0] is thumb0
    assert panel._thumbnails[2] is thumb2


def test_clear_cache_empties_thumbnail_cache(qapp, tmp_path):
    img_path = tmp_path / "page1.png"
    image = QImage(120, 160, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    assert image.save(str(img_path))

    panel = BundleThumbnailPanel(dark_mode=False)
    panel.populate([str(img_path)], [0], 0, prototype_mode=False)
    assert panel._thumb_cache

    panel.clear_cache()
    assert panel._thumb_cache == {}


# ---------------------------------------------------------------------------
# Metadata panel: per-page refresh (carry-over fix)
# ---------------------------------------------------------------------------


def _page_number_text(panel: BundleMetadataPanel) -> str:
    widget = panel._metadata_inputs["page_number"]
    assert isinstance(widget, QLineEdit)
    return widget.text()


def test_set_current_page_shows_selected_pages_metadata(qapp):
    """Navigating pages replaces page-level fields with the new page's values."""
    bundle = create_mock_bundles()[0]  # 12 pages, page_number == str(p + 1)
    page_order = list(range(len(bundle["file_paths"])))

    panel = BundleMetadataPanel(dark_mode=False)
    panel.load_bundle(bundle, page_order, 0, prototype_mode=True)
    assert _page_number_text(panel) == "1"

    panel.set_current_page(2)
    assert panel._current_page_index == 2
    assert _page_number_text(panel) == "3"


def test_set_current_page_preserves_manual_output_filename(qapp):
    """Page navigation must not overwrite a manually edited output filename."""
    bundle = create_mock_bundles()[0]
    page_order = list(range(len(bundle["file_paths"])))

    panel = BundleMetadataPanel(dark_mode=False)
    panel.load_bundle(bundle, page_order, 0, prototype_mode=True)

    panel._output_filename_input.setText("My Custom Name")  # simulates manual edit
    assert panel._output_filename_manually_edited is True

    panel.set_current_page(1)
    assert panel.get_output_filename() == "My Custom Name"


# ---------------------------------------------------------------------------
# Orchestrator: thumbnail click wires both fixes together
# ---------------------------------------------------------------------------


def test_thumbnail_click_refreshes_metadata_and_moves_selection(qapp):
    widget = BundleReviewWidget(bundles=create_mock_bundles(), prototype_mode=True)
    thumb0 = widget.thumbnail_panel._thumbnails[0]

    widget._on_thumbnail_clicked(2)

    assert widget.current_page_index == 2
    assert widget.metadata_panel._current_page_index == 2
    assert widget.thumbnail_panel._current_selected == 2
    # Carry-over fixed: page 3's own page_number is shown.
    assert _page_number_text(widget.metadata_panel) == "3"
    # Fast path: the existing thumbnail widget was reused, not rebuilt.
    assert widget.thumbnail_panel._thumbnails[0] is thumb0
