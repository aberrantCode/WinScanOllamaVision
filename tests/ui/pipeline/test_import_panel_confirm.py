"""
Tests for ImportPanel confirmation behavior in ui.pipeline.import_panel.

Covers:
- _on_unregister() shows a QMessageBox.question confirm dialog BEFORE
  calling _image_repo.mark_deleted_batch
- When the user answers "No", mark_deleted_batch is NOT called
- When the user answers "Yes", mark_deleted_batch IS called with the selected paths
"""

from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def mock_analysis_db():
    db = MagicMock()
    db.connection = MagicMock()
    return db


@pytest.fixture
def mock_config_manager():
    cfg = MagicMock()
    cfg.get_directories.return_value = ["/source/docs"]
    cfg.get_setting.return_value = "dark"
    return cfg


# ---------------------------------------------------------------------------
# Panel factory
# ---------------------------------------------------------------------------


def _make_panel(qapp, mock_analysis_db, mock_config_manager):
    """Instantiate ImportPanel with all heavy-weight deps mocked."""
    from ui.pipeline.import_panel import ImportPanel

    with patch("ui.pipeline.import_panel.ImageFilesRepository") as mock_repo_cls:
        mock_repo_cls.return_value.get_all.return_value = []
        panel = ImportPanel(
            analysis_db=mock_analysis_db,
            config_manager=mock_config_manager,
            dark_mode=True,
        )
    return panel


# ---------------------------------------------------------------------------
# _on_unregister — shows confirm dialog before deleting
# ---------------------------------------------------------------------------


def test_unregister_shows_confirm_dialog_before_deletion(
    qapp, mock_analysis_db, mock_config_manager
):
    """
    _on_unregister() must display a QMessageBox.question dialog before
    calling mark_deleted_batch.

    The dialog must appear BEFORE any database mutation.
    """
    panel = _make_panel(qapp, mock_analysis_db, mock_config_manager)

    # Simulate two selected files in the tree
    selected_paths = ["/source/docs/a.png", "/source/docs/b.png"]
    panel._selected_paths = MagicMock(return_value=selected_paths)
    panel._refresh = MagicMock()

    call_order = []

    def record_question(*args, **kwargs):
        call_order.append("question")
        return QMessageBox.StandardButton.Yes

    def record_mark_deleted(paths):
        call_order.append("mark_deleted")

    panel._image_repo.mark_deleted_batch.side_effect = record_mark_deleted

    with patch(
        "ui.pipeline.import_panel.QMessageBox.question",
        side_effect=record_question,
    ):
        panel._on_unregister()

    assert "question" in call_order, "QMessageBox.question was not called"
    assert "mark_deleted" in call_order, "mark_deleted_batch was not called"
    assert call_order.index("question") < call_order.index("mark_deleted"), (
        "Confirm dialog must appear BEFORE mark_deleted_batch is called"
    )


def test_unregister_no_answer_does_not_call_mark_deleted_batch(
    qapp, mock_analysis_db, mock_config_manager
):
    """
    When the user clicks 'No' in the confirm dialog, mark_deleted_batch
    must NOT be called.
    """
    panel = _make_panel(qapp, mock_analysis_db, mock_config_manager)

    panel._selected_paths = MagicMock(return_value=["/source/docs/a.png"])
    panel._refresh = MagicMock()

    with patch(
        "ui.pipeline.import_panel.QMessageBox.question",
        return_value=QMessageBox.StandardButton.No,
    ):
        panel._on_unregister()

    panel._image_repo.mark_deleted_batch.assert_not_called()


def test_unregister_yes_answer_calls_mark_deleted_batch_with_paths(
    qapp, mock_analysis_db, mock_config_manager
):
    """
    When the user clicks 'Yes', mark_deleted_batch must be called
    with the exact list of selected file paths.
    """
    panel = _make_panel(qapp, mock_analysis_db, mock_config_manager)

    paths = ["/source/docs/a.png", "/source/docs/b.png"]
    panel._selected_paths = MagicMock(return_value=paths)
    panel._refresh = MagicMock()

    with patch(
        "ui.pipeline.import_panel.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        panel._on_unregister()

    panel._image_repo.mark_deleted_batch.assert_called_once_with(paths)


def test_unregister_calls_refresh_after_deletion(qapp, mock_analysis_db, mock_config_manager):
    """
    After a confirmed unregister, the panel must refresh its file list.
    """
    panel = _make_panel(qapp, mock_analysis_db, mock_config_manager)

    panel._selected_paths = MagicMock(return_value=["/source/docs/a.png"])
    refresh_mock = MagicMock()
    panel._refresh = refresh_mock

    with patch(
        "ui.pipeline.import_panel.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        panel._on_unregister()

    refresh_mock.assert_called_once()


def test_unregister_with_empty_selection_does_nothing(qapp, mock_analysis_db, mock_config_manager):
    """
    _on_unregister() with no selected files must be a complete no-op —
    no dialog shown, no database calls.
    """
    panel = _make_panel(qapp, mock_analysis_db, mock_config_manager)

    panel._selected_paths = MagicMock(return_value=[])
    panel._refresh = MagicMock()

    with patch("ui.pipeline.import_panel.QMessageBox.question") as mock_q:
        panel._on_unregister()

    mock_q.assert_not_called()
    panel._image_repo.mark_deleted_batch.assert_not_called()
    panel._refresh.assert_not_called()


# ---------------------------------------------------------------------------
# _on_unregister — dialog content verification
# ---------------------------------------------------------------------------


def test_unregister_dialog_mentions_file_count(qapp, mock_analysis_db, mock_config_manager):
    """
    The confirmation dialog text must mention the number of files being
    unregistered, so the user knows the scope of the operation.
    """
    panel = _make_panel(qapp, mock_analysis_db, mock_config_manager)

    paths = ["/source/docs/a.png", "/source/docs/b.png", "/source/docs/c.png"]
    panel._selected_paths = MagicMock(return_value=paths)
    panel._refresh = MagicMock()

    captured_args = {}

    def capture_question(parent, title, text, *args, **kwargs):
        captured_args["title"] = title
        captured_args["text"] = text
        return QMessageBox.StandardButton.No

    with patch("ui.pipeline.import_panel.QMessageBox.question", side_effect=capture_question):
        panel._on_unregister()

    # The dialog text should include the count (3)
    assert "3" in captured_args.get("text", ""), (
        f"Expected file count '3' in dialog text, got: {captured_args.get('text')!r}"
    )
