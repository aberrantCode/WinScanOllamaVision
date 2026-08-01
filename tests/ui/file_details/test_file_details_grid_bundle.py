"""
Tests for _GridActionsMixin._bundle_selected (manual page bundling).

Exercises the context-menu handler without a real QWidget by injecting the mixin
methods onto a plain host, mirroring test_file_details_dialog_actions.py.
"""

import types
from unittest.mock import MagicMock, patch


class _FakeSignal:
    """Minimal signal stub recording emitted values."""

    def __init__(self):
        self.emitted = []

    def emit(self, *args):
        self.emitted.append(args[0] if len(args) == 1 else args)


class TestableGridActions:
    """Concrete host for _GridActionsMixin._bundle_selected."""

    def __init__(self, analysis_db, rows):
        from ui.file_details.file_details_grid_actions import _GridActionsMixin

        for attr in dir(_GridActionsMixin):
            if not attr.startswith("__"):
                method = getattr(_GridActionsMixin, attr)
                if callable(method):
                    setattr(self, attr, types.MethodType(method, self))

        self.analysis_db = analysis_db
        self.bundle_created = _FakeSignal()

        # Build selection: one index per row, index.row() -> position.
        indexes = []
        for i in range(len(rows)):
            idx = MagicMock()
            idx.row.return_value = i
            indexes.append(idx)

        self.table_view = MagicMock()
        self.table_view.selectionModel.return_value.selectedRows.return_value = indexes
        self.proxy_model = MagicMock()
        self.proxy_model.mapToSource.side_effect = lambda idx: idx
        self.model = MagicMock()
        self.model.get_row_data.side_effect = lambda r: rows[r]

        self._saved = []

    def _on_metadata_saved(self, file_path):
        self._saved.append(file_path)


def _rows(*paths):
    return [{"full_path": p} for p in paths]


def test_bundle_selected_calls_merge_and_emits_bundle_id():
    db = MagicMock()
    host = TestableGridActions(db, _rows("a.png", "b.png"))

    mock_service = MagicMock()
    mock_service.create_or_extend_manual_bundle.return_value = {
        "status": "created",
        "bundle_id": 55,
        "existing_bundle_ids": [],
        "added_image_ids": [1, 2],
        "message": "ok",
    }

    with patch("services.bundling_service.BundlingService", return_value=mock_service):
        host._bundle_selected()

    mock_service.create_or_extend_manual_bundle.assert_called_once_with(["a.png", "b.png"])
    # Both pages marked BUNDLED
    assert db.update_image_status.call_count == 2
    for call in db.update_image_status.call_args_list:
        assert call.args[1] == "bundled"
    # Signal carries the resulting bundle id
    assert host.bundle_created.emitted == [55]


def test_bundle_selected_ambiguous_warns_and_does_not_emit():
    db = MagicMock()
    host = TestableGridActions(db, _rows("a.png", "b.png"))

    mock_service = MagicMock()
    mock_service.create_or_extend_manual_bundle.return_value = {
        "status": "ambiguous",
        "bundle_id": None,
        "existing_bundle_ids": [10, 20],
        "added_image_ids": [],
        "message": "spans 2",
    }

    with (
        patch("services.bundling_service.BundlingService", return_value=mock_service),
        patch("ui.file_details.file_details_grid_actions.show_warning") as warn,
    ):
        host._bundle_selected()

    warn.assert_called_once()
    db.update_image_status.assert_not_called()
    assert host.bundle_created.emitted == []


def test_bundle_selected_single_selection_is_noop():
    db = MagicMock()
    host = TestableGridActions(db, _rows("a.png"))  # only one row selected

    with patch("services.bundling_service.BundlingService") as svc_cls:
        host._bundle_selected()

    svc_cls.assert_not_called()
    assert host.bundle_created.emitted == []


def test_bundle_selected_error_warns_no_emit():
    db = MagicMock()
    host = TestableGridActions(db, _rows("a.png", "b.png"))

    mock_service = MagicMock()
    mock_service.create_or_extend_manual_bundle.return_value = {
        "status": "error",
        "bundle_id": None,
        "existing_bundle_ids": [],
        "added_image_ids": [],
        "message": "no pages registered",
    }

    with (
        patch("services.bundling_service.BundlingService", return_value=mock_service),
        patch("ui.file_details.file_details_grid_actions.show_warning") as warn,
    ):
        host._bundle_selected()

    warn.assert_called_once()
    db.update_image_status.assert_not_called()
    assert host.bundle_created.emitted == []
