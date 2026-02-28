"""
Tests for ExportPanel in ui.pipeline.export_panel.
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


@pytest.fixture
def mock_config_manager():
    cfg = MagicMock()
    cfg.get_setting.side_effect = lambda section, key, default=None: {
        ("OutputDirectory", "strategy", "same_as_source"): "global_custom",
        ("OutputDirectory", "global_custom_path", ""): "/output",
        ("OutputDirectory", "subdirectory_name", "PDFs"): "PDFs",
    }.get((section, key, default), default)
    return cfg


def _make_panel(qapp, mock_config_manager):
    from ui.pipeline.export_panel import ExportPanel

    return ExportPanel(config_manager=mock_config_manager, dark_mode=True)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_panel_builds_without_error(qapp, mock_config_manager):
    """ExportPanel must construct without raising."""
    panel = _make_panel(qapp, mock_config_manager)
    assert panel is not None


def test_panel_has_metric_labels(qapp, mock_config_manager):
    """ExportPanel must have all 6 metric card labels after construction."""
    panel = _make_panel(qapp, mock_config_manager)
    assert panel._metric_images is not None
    assert panel._metric_pdfs is not None
    assert panel._metric_pages is not None
    assert panel._metric_rejected is not None
    assert panel._metric_errors is not None
    assert panel._metric_success is not None


def test_panel_has_pdf_table(qapp, mock_config_manager):
    """ExportPanel must have a _pdf_table QTableWidget."""
    from PyQt6.QtWidgets import QTableWidget

    panel = _make_panel(qapp, mock_config_manager)
    assert panel._pdf_table is not None
    assert isinstance(panel._pdf_table, QTableWidget)


def test_pdf_table_has_6_columns(qapp, mock_config_manager):
    """PDF table must have exactly 6 columns."""
    panel = _make_panel(qapp, mock_config_manager)
    assert panel._pdf_table.columnCount() == 6


# ---------------------------------------------------------------------------
# update_stats()
# ---------------------------------------------------------------------------


def test_update_stats_sets_pdfs_created(qapp, mock_config_manager):
    """update_stats() must update the PDFs Created metric card."""
    panel = _make_panel(qapp, mock_config_manager)
    panel.update_stats({"accepted": 5, "rejected": 2, "errors": 0, "pdf_files": []})
    assert panel._metric_pdfs.text() == "5"


def test_update_stats_sets_rejected(qapp, mock_config_manager):
    """update_stats() must update the Bundles Rejected metric card."""
    panel = _make_panel(qapp, mock_config_manager)
    panel.update_stats({"accepted": 5, "rejected": 3, "errors": 0, "pdf_files": []})
    assert panel._metric_rejected.text() == "3"


def test_update_stats_sets_errors(qapp, mock_config_manager):
    """update_stats() must update the Errors metric card."""
    panel = _make_panel(qapp, mock_config_manager)
    panel.update_stats({"accepted": 4, "rejected": 1, "errors": 2, "pdf_files": []})
    assert panel._metric_errors.text() == "2"


def test_update_stats_computes_success_rate(qapp, mock_config_manager):
    """update_stats() must compute success rate as accepted/total*100."""
    panel = _make_panel(qapp, mock_config_manager)
    panel.update_stats({"accepted": 3, "rejected": 1, "errors": 0, "pdf_files": []})
    # 3/(3+1) = 75%
    assert panel._metric_success.text() == "75%"


def test_update_stats_zero_total_shows_dash(qapp, mock_config_manager):
    """When accepted+rejected is 0, success rate should show '—'."""
    panel = _make_panel(qapp, mock_config_manager)
    panel.update_stats({"accepted": 0, "rejected": 0, "errors": 0, "pdf_files": []})
    assert panel._metric_success.text() == "—"


# ---------------------------------------------------------------------------
# _populate_pdf_table()
# ---------------------------------------------------------------------------


def test_populate_pdf_table_adds_rows(qapp, mock_config_manager):
    """_populate_pdf_table must add one row per PDF entry."""
    panel = _make_panel(qapp, mock_config_manager)
    rows = [
        {
            "pdf_filename": "doc1.pdf",
            "company": "ACME",
            "document_type": "Invoice",
            "document_date": "2024-01-01",
            "pages": 3,
            "created_at": "2024-01-02",
        },
        {
            "pdf_filename": "doc2.pdf",
            "company": "Globex",
            "document_type": "Statement",
            "document_date": "2024-02-01",
            "pages": 1,
            "created_at": "2024-02-02",
        },
    ]
    panel._populate_pdf_table(rows)
    assert panel._pdf_table.rowCount() == 2


def test_populate_pdf_table_sets_correct_cells(qapp, mock_config_manager):
    """_populate_pdf_table must populate filename, company, type correctly."""
    panel = _make_panel(qapp, mock_config_manager)
    rows = [
        {
            "pdf_filename": "invoice.pdf",
            "company": "ACME Corp",
            "document_type": "Invoice",
            "document_date": "2024-01-01",
            "pages": 2,
            "created_at": "2024-01-02",
        },
    ]
    panel._populate_pdf_table(rows)
    assert panel._pdf_table.item(0, 0).text() == "invoice.pdf"
    assert panel._pdf_table.item(0, 1).text() == "ACME Corp"
    assert panel._pdf_table.item(0, 2).text() == "Invoice"


def test_populate_pdf_table_clears_previous_rows(qapp, mock_config_manager):
    """Calling _populate_pdf_table twice replaces, not appends, rows."""
    panel = _make_panel(qapp, mock_config_manager)
    panel._populate_pdf_table(
        [
            {
                "pdf_filename": "a.pdf",
                "company": "",
                "document_type": "",
                "document_date": "",
                "pages": 1,
                "created_at": "",
            }
        ]
    )
    panel._populate_pdf_table(
        [
            {
                "pdf_filename": "b.pdf",
                "company": "",
                "document_type": "",
                "document_date": "",
                "pages": 2,
                "created_at": "",
            },
            {
                "pdf_filename": "c.pdf",
                "company": "",
                "document_type": "",
                "document_date": "",
                "pages": 2,
                "created_at": "",
            },
        ]
    )
    assert panel._pdf_table.rowCount() == 2


def test_populate_pdf_table_with_empty_list(qapp, mock_config_manager):
    """_populate_pdf_table with empty list results in 0 rows."""
    panel = _make_panel(qapp, mock_config_manager)
    panel._populate_pdf_table([])
    assert panel._pdf_table.rowCount() == 0


def test_update_stats_populates_table(qapp, mock_config_manager):
    """update_stats() with pdf_files list must populate the PDF table."""
    panel = _make_panel(qapp, mock_config_manager)
    panel.update_stats(
        {
            "accepted": 1,
            "rejected": 0,
            "errors": 0,
            "pdf_files": [
                {
                    "pdf_filename": "out.pdf",
                    "company": "TestCo",
                    "document_type": "Invoice",
                    "document_date": "2024-06-01",
                    "pages": 4,
                    "created_at": "2024-06-02",
                },
            ],
        }
    )
    assert panel._pdf_table.rowCount() == 1
    assert panel._pdf_table.item(0, 0).text() == "out.pdf"


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


def test_summary_lbl_is_not_none(qapp, mock_config_manager):
    """summary_lbl must remain non-None for backward-compat callers."""
    panel = _make_panel(qapp, mock_config_manager)
    assert panel.summary_lbl is not None
