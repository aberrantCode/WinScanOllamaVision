"""
Tests for DocumentPipelineWindow stage navigation bounds checking (H2).
"""

from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QApplication

from ui.pipeline import (
    STAGE_ANALYZE,
    STAGE_BUNDLE,
    STAGE_EXPORT,
    STAGE_IMPORT,
    DocumentPipelineWindow,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_window(qapp):
    """Create a DocumentPipelineWindow with all heavy setup bypassed."""
    with (
        patch.object(DocumentPipelineWindow, "_build_ui"),
        patch.object(DocumentPipelineWindow, "_apply_theme"),
    ):
        cfg = MagicMock()
        cfg.get_setting.return_value = "dark"
        cfg.get_directories.return_value = []
        window = DocumentPipelineWindow(
            analysis_db=MagicMock(),
            metadata_db=MagicMock(),
            config_manager=cfg,
        )

    # Provide the minimal attributes _go_to_stage needs
    window._current_stage = STAGE_IMPORT
    window._completed_stages = set()
    window.stack = MagicMock()
    window.header = MagicMock()
    window.import_panel = MagicMock()
    window.analyze_panel = MagicMock()
    window.bundle_panel = MagicMock()
    window._back_btn = MagicMock()
    window._fwd_btn = MagicMock()
    return window


# ---------------------------------------------------------------------------
# _go_to_stage — clamp
# ---------------------------------------------------------------------------


def test_go_to_stage_below_minimum_clamped(qapp):
    """Calling _go_to_stage(-1) must clamp to STAGE_IMPORT, not crash."""
    window = _make_window(qapp)
    window._go_to_stage(-1)
    window.stack.setCurrentIndex.assert_called_once_with(STAGE_IMPORT)
    assert window._current_stage == STAGE_IMPORT


def test_go_to_stage_above_maximum_clamped(qapp):
    """Calling _go_to_stage(4) must clamp to STAGE_EXPORT, not crash."""
    window = _make_window(qapp)
    window._current_stage = STAGE_EXPORT
    window._go_to_stage(STAGE_EXPORT + 1)
    window.stack.setCurrentIndex.assert_called_once_with(STAGE_EXPORT)
    assert window._current_stage == STAGE_EXPORT


def test_go_to_stage_large_out_of_bounds_clamped(qapp):
    """Arbitrary large values are clamped to STAGE_EXPORT."""
    window = _make_window(qapp)
    window._go_to_stage(99)
    window.stack.setCurrentIndex.assert_called_once_with(STAGE_EXPORT)


def test_go_to_stage_valid_values_pass_through(qapp):
    """Valid stage values are passed through unchanged."""
    for stage in (STAGE_IMPORT, STAGE_ANALYZE, STAGE_BUNDLE, STAGE_EXPORT):
        window = _make_window(qapp)
        window._current_stage = stage
        window._go_to_stage(stage)
        window.stack.setCurrentIndex.assert_called_once_with(stage)


# ---------------------------------------------------------------------------
# _on_back_clicked — boundary
# ---------------------------------------------------------------------------


def test_back_at_first_stage_stays_at_import(qapp):
    """Pressing Back on STAGE_IMPORT must not navigate to stage -1."""
    window = _make_window(qapp)
    window._current_stage = STAGE_IMPORT
    window._on_back_clicked()
    window.stack.setCurrentIndex.assert_called_once_with(STAGE_IMPORT)
    assert window._current_stage == STAGE_IMPORT


def test_back_from_analyze_goes_to_import(qapp):
    """Pressing Back on STAGE_ANALYZE navigates to STAGE_IMPORT."""
    window = _make_window(qapp)
    window._current_stage = STAGE_ANALYZE
    window._on_back_clicked()
    window.stack.setCurrentIndex.assert_called_once_with(STAGE_IMPORT)


# ---------------------------------------------------------------------------
# _on_next_clicked — boundary
# ---------------------------------------------------------------------------


def test_next_at_last_stage_stays_at_export(qapp):
    """Pressing Next on STAGE_EXPORT must not navigate to stage 4."""
    window = _make_window(qapp)
    window._current_stage = STAGE_EXPORT
    window._on_next_clicked()
    window.stack.setCurrentIndex.assert_called_once_with(STAGE_EXPORT)
    assert window._current_stage == STAGE_EXPORT


def test_next_from_import_goes_to_analyze(qapp):
    """Pressing Next on STAGE_IMPORT navigates to STAGE_ANALYZE."""
    window = _make_window(qapp)
    window._current_stage = STAGE_IMPORT
    window._on_next_clicked()
    window.stack.setCurrentIndex.assert_called_once_with(STAGE_ANALYZE)


# ---------------------------------------------------------------------------
# M1 — _go_to_stage uses public import_panel.refresh(), not _refresh()
# ---------------------------------------------------------------------------


def test_go_to_import_stage_calls_public_refresh(qapp):
    """_go_to_stage(STAGE_IMPORT) must call import_panel.refresh(), not _refresh()."""
    window = _make_window(qapp)
    window._current_stage = STAGE_ANALYZE  # start somewhere else so we navigate back
    window._go_to_stage(STAGE_IMPORT)
    window.import_panel.refresh.assert_called_once()
    window.import_panel._refresh.assert_not_called()
