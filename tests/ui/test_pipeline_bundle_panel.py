"""
Tests for BundlePanel in ui.pipeline.bundle_panel.
"""

from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_analysis_db():
    db = MagicMock()
    db.connection = MagicMock()
    return db


@pytest.fixture
def mock_metadata_db():
    return MagicMock()


@pytest.fixture
def mock_config_manager():
    cfg = MagicMock()
    cfg.get_setting.return_value = "dark"
    return cfg


def _make_bundle_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager):
    from ui.pipeline_window import BundlePanel

    with patch("ui.pipeline.bundle_panel.BundlingService"):
        panel = BundlePanel(
            analysis_db=mock_analysis_db,
            metadata_db=mock_metadata_db,
            config_manager=mock_config_manager,
            dark_mode=True,
        )
    return panel


# ---------------------------------------------------------------------------
# M8 — _load_embedded_workflow exits cleanly when _content_stack is None
# ---------------------------------------------------------------------------


def test_load_embedded_workflow_returns_early_when_content_stack_none(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """_load_embedded_workflow must not raise when _content_stack is None.

    Without the guard, an assert would be stripped by -O and raise AttributeError
    at runtime. With the guard, the method returns early safely.
    """
    panel = _make_bundle_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)

    # Force the stack to None to simulate an uninitialised widget
    panel._content_stack = None

    bundles = [{"name": "Bundle 1", "analyses": []}]

    with patch("ui.guided_bundle_workflow.GuidedBundleWorkflow"):
        # Must not raise AssertionError, AttributeError, or any other exception
        panel._load_embedded_workflow(bundles)


def test_load_embedded_workflow_sets_embedded_workflow_even_when_stack_none(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """_embedded_workflow is still assigned before the guard check fires."""
    panel = _make_bundle_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    panel._content_stack = None

    bundles = [{"name": "Bundle 1", "analyses": []}]

    mock_wf = MagicMock()
    with patch("ui.guided_bundle_workflow.GuidedBundleWorkflow", return_value=mock_wf):
        panel._load_embedded_workflow(bundles)

    assert panel._embedded_workflow is mock_wf


def test_load_embedded_workflow_adds_to_stack_when_stack_present(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """_load_embedded_workflow calls addWidget/setCurrentWidget on the stack when it exists."""
    panel = _make_bundle_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)

    # Replace the real QStackedWidget with a mock so addWidget accepts any argument
    mock_stack = MagicMock()
    panel._content_stack = mock_stack

    bundles = [{"name": "Bundle 1", "analyses": []}]

    mock_wf = MagicMock()
    with patch("ui.guided_bundle_workflow.GuidedBundleWorkflow", return_value=mock_wf):
        panel._load_embedded_workflow(bundles)

    mock_wf.workflow_completed.connect.assert_called_once()
    mock_stack.addWidget.assert_called_once_with(mock_wf)
    mock_stack.setCurrentWidget.assert_called_once_with(mock_wf)
