"""
Wiring tests for manual page bundling: grid -> analyze_panel -> window -> bundle_panel.

Verifies the two ends of the chain that are practical to unit test:
- FileDetailsGrid.bundle_created is a real int signal that forwards to a slot.
- PipelineWindow._go_to_bundle switches to the Bundle stage, then selects the bundle.
"""

from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_grid_bundle_created_signal_forwards_int(qapp):
    """The grid exposes bundle_created(int) and emitting it reaches a connected slot."""
    from ui.file_details.file_details_grid import FileDetailsGrid

    grid = FileDetailsGrid(analysis_db=MagicMock(), metadata_db=MagicMock())
    received = []
    grid.bundle_created.connect(received.append)

    grid.bundle_created.emit(42)

    assert received == [42]


def test_go_to_bundle_switches_stage_then_selects_bundle():
    """_go_to_bundle must switch to STAGE_BUNDLE and then select the given bundle."""
    from ui.pipeline.stages import STAGE_BUNDLE
    from ui.pipeline.window import DocumentPipelineWindow

    win = MagicMock()
    calls = []
    win._go_to_stage.side_effect = lambda s: calls.append(("stage", s))
    win.bundle_panel.select_bundle.side_effect = lambda b: calls.append(("select", b))

    # Call the unbound method against the mock to test its logic in isolation.
    DocumentPipelineWindow._go_to_bundle(win, 7)

    # Stage switch must happen before selection so select_bundle wins the rebuild.
    assert calls == [("stage", STAGE_BUNDLE), ("select", 7)]
