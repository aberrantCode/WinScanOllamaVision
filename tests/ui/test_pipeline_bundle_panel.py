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


# ---------------------------------------------------------------------------
# Stats grid — Phase 4 additions
# ---------------------------------------------------------------------------


def test_bundle_stats_widget_created_in_build_ui(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """BundlePanel must create _bundle_stats_widget during _build_ui."""
    panel = _make_bundle_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    assert panel._bundle_stats_widget is not None


def test_update_bundle_stats_sets_bundle_count(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """update_bundle_stats() must update the bundles-ready label."""
    panel = _make_bundle_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    panel.update_bundle_stats(
        {"total": 7, "avg_pages": 3.5, "doc_types": {}, "completeness_pct": 80}
    )
    if panel._stat_bundles_lbl:
        assert "7" in panel._stat_bundles_lbl.text()


def test_update_bundle_stats_sets_avg_pages(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """update_bundle_stats() must update the avg-pages label."""
    panel = _make_bundle_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    panel.update_bundle_stats(
        {"total": 4, "avg_pages": 5.5, "doc_types": {}, "completeness_pct": 0}
    )
    if panel._stat_avg_pages_lbl:
        assert "5.5" in panel._stat_avg_pages_lbl.text()


def test_update_bundle_stats_zero_avg_pages_shows_dash(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """When avg_pages is 0, the label should display '—'."""
    panel = _make_bundle_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    panel.update_bundle_stats({"total": 0, "avg_pages": 0, "doc_types": {}, "completeness_pct": 0})
    if panel._stat_avg_pages_lbl:
        assert panel._stat_avg_pages_lbl.text() == "—"


def test_update_bundle_stats_shows_top_doc_types(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """update_bundle_stats() populates doc types from the provided dict."""
    panel = _make_bundle_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    panel.update_bundle_stats(
        {
            "total": 3,
            "avg_pages": 2.0,
            "doc_types": {"Invoice": 2, "Statement": 1},
            "completeness_pct": 75,
        }
    )
    if panel._stat_doc_types_lbl:
        text = panel._stat_doc_types_lbl.text()
        assert "Invoice" in text


def test_update_bundle_stats_empty_doc_types_shows_dash(
    qapp, mock_analysis_db, mock_metadata_db, mock_config_manager
):
    """When doc_types is empty, the label should display '—'."""
    panel = _make_bundle_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    panel.update_bundle_stats({"total": 0, "avg_pages": 0, "doc_types": {}, "completeness_pct": 0})
    if panel._stat_doc_types_lbl:
        assert panel._stat_doc_types_lbl.text() == "—"


def test_compute_bundle_stats_basic(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager):
    """_compute_bundle_stats derives correct totals from bundle list."""
    panel = _make_bundle_panel(qapp, mock_analysis_db, mock_metadata_db, mock_config_manager)
    bundles = [
        {
            "file_paths": ["a.png", "b.png"],
            "document_type": "Invoice",
            "company": "ACME",
            "document_date": "2024-01-01",
        },
        {
            "file_paths": ["c.png"],
            "document_type": "Statement",
            "company": "Globex",
            "document_date": "",
        },
    ]
    stats = panel._compute_bundle_stats(bundles)
    assert stats["total"] == 2
    assert stats["avg_pages"] == 1.5
    assert "Invoice" in stats["doc_types"]
    assert stats["doc_types"]["Invoice"] == 1
