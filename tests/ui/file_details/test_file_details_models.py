"""
Tests for FileDetailsTableModel and FileDetailsSortFilterProxyModel.

Covers:
- Row / column counts with sample data
- Data formatting (confidence, file size, booleans, rotation)
- Quick-filter modes: "recent", "high_confidence", "has_errors", "missing_metadata"
- Text search across searchable fields
"""

from datetime import datetime, timedelta

import pytest
from PyQt6.QtWidgets import QApplication

from ui.file_details.file_details_filter_model import FileDetailsSortFilterProxyModel
from ui.file_details.file_details_table_model import FileDetailsTableModel

# ---------------------------------------------------------------------------
# Shared Qt app fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


# ---------------------------------------------------------------------------
# Sample data helpers
# ---------------------------------------------------------------------------


def _make_row(**kwargs):
    base = {
        "filename": "/docs/invoice.png",
        "status": "analyzed",
        "confidence": 90.0,
        "company": "Acme Corp",
        "document_type": "Invoice",
        "document_date": "2024-01-15",
        "tax_related": False,
        "is_blank": False,
        "page_number": 1,
        "total_pages": 3,
        "rotation": 0,
        "file_size": 102400,
        "modified_time": "2024-01-14",
        "analysis_time": "2024-01-15",
        "processing_duration": 2.5,
        "model_used": "qwen2.5-vl",
        "provider": "ollama",
        "cache_hit": False,
        "error_message": None,
        "full_path": "/docs/invoice.png",
        "file_hash": "abc12345",
    }
    base.update(kwargs)
    return base


SAMPLE_DATA = [
    _make_row(filename="/docs/invoice1.png", confidence=95.0, company="Acme"),
    _make_row(filename="/docs/receipt.png", confidence=45.0, company="Bakery", tax_related=True),
    _make_row(
        filename="/docs/error_file.png",
        status="Failed",
        confidence=0,
        error_message="Timeout",
    ),
]


# ---------------------------------------------------------------------------
# FileDetailsTableModel — basic row / column counts
# ---------------------------------------------------------------------------


def test_table_model_row_count_empty(qapp):
    """Model with no data should report 0 rows."""
    model = FileDetailsTableModel()
    assert model.rowCount() == 0


def test_table_model_row_count(qapp):
    """rowCount() must match the number of records loaded via set_data()."""
    model = FileDetailsTableModel()
    model.set_data(SAMPLE_DATA)
    assert model.rowCount() == len(SAMPLE_DATA)


def test_table_model_column_count_default_visible(qapp):
    """Column count should equal the number of columns marked visible=True by default."""
    model = FileDetailsTableModel()
    expected = sum(1 for _, _, visible in FileDetailsTableModel.COLUMNS if visible)
    assert model.columnCount() == expected


def test_table_model_column_count_custom_visible(qapp):
    """set_visible_columns() should change the reported column count."""
    model = FileDetailsTableModel()
    model.set_data(SAMPLE_DATA)
    model.set_visible_columns([0, 1, 2])
    assert model.columnCount() == 3


def test_table_model_get_row_data(qapp):
    """get_row_data() must return the full dict for a given row index."""
    model = FileDetailsTableModel()
    model.set_data(SAMPLE_DATA)
    row = model.get_row_data(0)
    assert row is not None
    assert row["company"] == "Acme"


def test_table_model_get_row_data_out_of_range(qapp):
    """get_row_data() must return None for an out-of-range index."""
    model = FileDetailsTableModel()
    model.set_data(SAMPLE_DATA)
    assert model.get_row_data(999) is None


# ---------------------------------------------------------------------------
# FileDetailsTableModel — data formatting
# ---------------------------------------------------------------------------


def _display_for(model, row_idx, col_key):
    """Helper: get the DisplayRole string for a specific column key."""
    from PyQt6.QtCore import Qt

    col_idx = None
    for i, (key, _, _) in enumerate(FileDetailsTableModel.COLUMNS):
        if key == col_key:
            # Find the visible column position
            if i in model.get_visible_columns():
                col_idx = model.get_visible_columns().index(i)
            break

    if col_idx is None:
        return None

    index = model.index(row_idx, col_idx)
    return model.data(index, Qt.ItemDataRole.DisplayRole)


def test_confidence_formatted_with_percent(qapp):
    """Confidence values should be formatted as 'XX.X%'."""
    model = FileDetailsTableModel()
    model.set_data([_make_row(confidence=85.0)])
    # Make confidence visible (it's visible by default)
    val = _display_for(model, 0, "confidence")
    assert val == "85.0%"


def test_file_size_formatted_human_readable(qapp):
    """File sizes >= 1024 bytes should be formatted with KB/MB units."""
    model = FileDetailsTableModel()
    model.set_data([_make_row(file_size=2048)])
    val = _display_for(model, 0, "file_size")
    assert "KB" in val or "MB" in val


def test_tax_related_boolean_formatted_as_yes_no(qapp):
    """tax_related=True should display 'Yes', False should display 'No'."""
    model = FileDetailsTableModel()
    model.set_data([_make_row(tax_related=True)])
    val = _display_for(model, 0, "tax_related")
    assert val == "Yes"

    model2 = FileDetailsTableModel()
    model2.set_data([_make_row(tax_related=False)])
    val2 = _display_for(model2, 0, "tax_related")
    assert val2 == "No"


def test_rotation_formatted_with_degrees_symbol(qapp):
    """Rotation values should be formatted as 'Xdeg' with the degree symbol."""
    model = FileDetailsTableModel()
    model.set_data([_make_row(rotation=90)])
    val = _display_for(model, 0, "rotation")
    assert val == "90°"


def test_filename_displays_basename(qapp):
    """The filename column should show only the basename, not the full path."""
    model = FileDetailsTableModel()
    model.set_data([_make_row(filename="/very/deep/path/myfile.png")])
    val = _display_for(model, 0, "filename")
    assert val == "myfile.png"


def test_empty_value_returns_empty_string(qapp):
    """None and empty-string values should both display as empty string."""
    model = FileDetailsTableModel()
    model.set_data([_make_row(company=None)])
    val = _display_for(model, 0, "company")
    assert val == ""


# ---------------------------------------------------------------------------
# FileDetailsTableModel — header data
# ---------------------------------------------------------------------------


def test_header_data_returns_column_name(qapp):
    """Horizontal header for column 0 (filename) should return 'Filename'."""
    from PyQt6.QtCore import Qt

    model = FileDetailsTableModel()
    model.set_data(SAMPLE_DATA)
    header = model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
    assert header == "Filename"


# ---------------------------------------------------------------------------
# FileDetailsSortFilterProxyModel — quick filters
# ---------------------------------------------------------------------------


def _make_proxy_with_data(data):
    """Helper: create a proxy model backed by a populated source model."""
    source = FileDetailsTableModel()
    source.set_data(data)
    proxy = FileDetailsSortFilterProxyModel()
    proxy.setSourceModel(source)
    return proxy


def test_quick_filter_high_confidence_keeps_high_rows(qapp):
    """'high_confidence' quick filter should keep only rows with confidence >= 80."""
    data = [
        _make_row(confidence=95.0),
        _make_row(confidence=45.0),
        _make_row(confidence=80.0),
    ]
    proxy = _make_proxy_with_data(data)
    proxy.set_quick_filter("high_confidence")

    visible = proxy.rowCount()
    assert visible == 2  # 95.0 and 80.0 pass; 45.0 does not


def test_quick_filter_recent_keeps_within_24h(qapp):
    """'recent' quick filter should include rows analyzed within the last 24 hours."""
    now = datetime.now()
    recent_time = (now - timedelta(hours=2)).isoformat()
    old_time = (now - timedelta(hours=48)).isoformat()

    data = [
        _make_row(analysis_time=recent_time),
        _make_row(analysis_time=old_time),
    ]
    proxy = _make_proxy_with_data(data)
    proxy.set_quick_filter("recent")

    assert proxy.rowCount() == 1


def test_quick_filter_recent_excludes_none_analysis_time(qapp):
    """'recent' quick filter should exclude rows with no analysis_time."""
    data = [
        _make_row(analysis_time=None),
    ]
    proxy = _make_proxy_with_data(data)
    proxy.set_quick_filter("recent")

    assert proxy.rowCount() == 0


def test_quick_filter_has_errors_includes_failed_rows(qapp):
    """'has_errors' filter should include rows with status=Failed."""
    data = [
        _make_row(status="analyzed", error_message=None),
        _make_row(status="Failed", error_message="Timeout"),
    ]
    proxy = _make_proxy_with_data(data)
    proxy.set_quick_filter("has_errors")

    assert proxy.rowCount() == 1


def test_quick_filter_has_errors_includes_rows_with_error_message(qapp):
    """'has_errors' filter should also include rows with a non-empty error_message."""
    data = [
        _make_row(status="analyzed", error_message="Partial failure"),
        _make_row(status="analyzed", error_message=None),
    ]
    proxy = _make_proxy_with_data(data)
    proxy.set_quick_filter("has_errors")

    assert proxy.rowCount() == 1


def test_quick_filter_missing_metadata_requires_both_company_and_date_missing(qapp):
    """'missing_metadata' keeps only rows where BOTH company AND document_date are absent."""
    data = [
        _make_row(company="Acme", document_date=""),  # company present -> not missing
        _make_row(company="", document_date="2024-01-01"),  # date present -> not missing
        _make_row(company="", document_date=""),  # both absent -> missing
        _make_row(company="N/A", document_date="N/A"),  # both N/A -> missing
    ]
    proxy = _make_proxy_with_data(data)
    proxy.set_quick_filter("missing_metadata")

    assert proxy.rowCount() == 2


def test_no_quick_filter_shows_all_rows(qapp):
    """With no quick filter set, all rows should be visible."""
    proxy = _make_proxy_with_data(SAMPLE_DATA)
    proxy.set_quick_filter(None)

    assert proxy.rowCount() == len(SAMPLE_DATA)


# ---------------------------------------------------------------------------
# FileDetailsSortFilterProxyModel — text search
# ---------------------------------------------------------------------------


def test_text_search_filters_by_company(qapp):
    """set_search_text() should narrow rows to those whose company matches."""
    data = [
        _make_row(company="Acme Corp"),
        _make_row(company="Bakery Ltd"),
        _make_row(company="Acme Industries"),
    ]
    proxy = _make_proxy_with_data(data)
    proxy.set_search_text("acme")

    assert proxy.rowCount() == 2


def test_text_search_is_case_insensitive(qapp):
    """Text search must be case-insensitive."""
    data = [
        _make_row(company="InvoiceCorp", document_type="Receipt"),
        _make_row(company="BakeryShop", document_type="Receipt"),
    ]
    proxy = _make_proxy_with_data(data)
    proxy.set_search_text("INVOICECORP")

    assert proxy.rowCount() == 1


def test_text_search_empty_string_shows_all(qapp):
    """Empty search string should show all rows."""
    proxy = _make_proxy_with_data(SAMPLE_DATA)
    proxy.set_search_text("")

    assert proxy.rowCount() == len(SAMPLE_DATA)


def test_text_search_no_match_hides_all(qapp):
    """A search term that matches nothing should result in 0 visible rows."""
    proxy = _make_proxy_with_data(SAMPLE_DATA)
    proxy.set_search_text("zzz_no_match_zzz")

    assert proxy.rowCount() == 0


def test_text_search_searches_document_type(qapp):
    """Text search should also match against document_type field."""
    data = [
        _make_row(document_type="Receipt"),
        _make_row(document_type="Invoice"),
    ]
    proxy = _make_proxy_with_data(data)
    proxy.set_search_text("receipt")

    assert proxy.rowCount() == 1


# ---------------------------------------------------------------------------
# FileDetailsSortFilterProxyModel — column filters
# ---------------------------------------------------------------------------


def test_column_filter_by_status(qapp):
    """Column filter on 'status' should keep only rows matching that status."""
    data = [
        _make_row(status="analyzed"),
        _make_row(status="Failed"),
        _make_row(status="analyzed"),
    ]
    proxy = _make_proxy_with_data(data)
    proxy.set_filters({"status": "Failed"})

    assert proxy.rowCount() == 1
