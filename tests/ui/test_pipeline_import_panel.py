"""
Tests for ImportPanel in ui.pipeline.import_panel.
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
    db.connection.fetch_all_dicts = MagicMock(return_value=[])
    return db


@pytest.fixture
def mock_config_manager():
    cfg = MagicMock()
    cfg.get_directories.return_value = ["/some/path"]
    cfg.get_setting.return_value = "dark"
    return cfg


def _make_panel(qapp, mock_analysis_db, mock_config_manager):
    """Instantiate ImportPanel with Qt widgets suppressed where needed."""
    from ui.pipeline_window import ImportPanel

    with patch("ui.pipeline.import_panel.ImageFilesRepository") as mock_repo:
        mock_repo.return_value.get_all.return_value = []
        panel = ImportPanel(
            analysis_db=mock_analysis_db,
            config_manager=mock_config_manager,
            dark_mode=True,
        )
    return panel


# ---------------------------------------------------------------------------
# C2 — logging on get_directories() failure
# ---------------------------------------------------------------------------


def test_populate_directory_combo_logs_on_config_error(qapp, mock_analysis_db, mock_config_manager):
    """When get_directories() raises, the error is logged rather than silently swallowed."""
    mock_config_manager.get_directories.side_effect = RuntimeError("INI read failed")

    with patch("ui.pipeline.import_panel.ImageFilesRepository") as mock_repo:
        mock_repo.return_value.get_all.return_value = []
        with patch("ui.pipeline.import_panel.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            from ui.pipeline_window import ImportPanel

            ImportPanel(
                analysis_db=mock_analysis_db,
                config_manager=mock_config_manager,
                dark_mode=True,
            )

    mock_logger.error.assert_called_once()
    call_args = mock_logger.error.call_args
    # First positional arg is the format string
    assert "[ImportPanel]" in call_args.args[0]
    assert "Failed to load directories" in call_args.args[0]


def test_populate_directory_combo_still_shows_all_directories_on_error(
    qapp, mock_analysis_db, mock_config_manager
):
    """Even when get_directories() raises, 'All Directories' sentinel item is still present."""
    mock_config_manager.get_directories.side_effect = RuntimeError("INI read failed")

    with patch("ui.pipeline.import_panel.ImageFilesRepository") as mock_repo:
        mock_repo.return_value.get_all.return_value = []
        with patch("ui.pipeline.import_panel.get_logger"):
            from ui.pipeline_window import ImportPanel

            panel = ImportPanel(
                analysis_db=mock_analysis_db,
                config_manager=mock_config_manager,
                dark_mode=True,
            )

    assert panel.directory_combo is not None
    assert panel.directory_combo.count() >= 1
    assert panel.directory_combo.itemText(0) == "All Directories"


def test_populate_directory_combo_happy_path(qapp, mock_analysis_db, mock_config_manager):
    """Happy path: configured directories appear in the combo after 'All Directories'."""
    mock_config_manager.get_directories.return_value = [
        "C:/scans/inbox",
        "C:/scans/archive",
    ]

    with patch("ui.pipeline.import_panel.ImageFilesRepository") as mock_repo:
        mock_repo.return_value.get_all.return_value = []
        from ui.pipeline_window import ImportPanel

        panel = ImportPanel(
            analysis_db=mock_analysis_db,
            config_manager=mock_config_manager,
            dark_mode=True,
        )

    assert panel.directory_combo is not None
    texts = [panel.directory_combo.itemText(i) for i in range(panel.directory_combo.count())]
    assert texts[0] == "All Directories"
    assert "C:/scans/inbox" in texts
    assert "C:/scans/archive" in texts


# ---------------------------------------------------------------------------
# M1 — public refresh() delegates to _refresh()
# ---------------------------------------------------------------------------


def test_refresh_public_method_delegates_to_private(qapp, mock_analysis_db, mock_config_manager):
    """ImportPanel.refresh() must call _refresh() exactly once."""
    with patch("ui.pipeline.import_panel.ImageFilesRepository") as mock_repo:
        mock_repo.return_value.get_all.return_value = []
        from ui.pipeline_window import ImportPanel

        panel = ImportPanel(
            analysis_db=mock_analysis_db,
            config_manager=mock_config_manager,
            dark_mode=True,
        )

    with patch.object(panel, "_refresh") as mock_refresh:
        panel.refresh()

    mock_refresh.assert_called_once_with()


# ---------------------------------------------------------------------------
# M3 — shared _make_divider() module-level helper
# ---------------------------------------------------------------------------


def test_make_divider_returns_hline_frame(qapp):
    """_make_divider() returns a QFrame with HLine shape and 1-pixel height."""
    from PyQt6.QtWidgets import QFrame

    from ui.pipeline_window import _make_divider

    divider = _make_divider()

    assert isinstance(divider, QFrame)
    assert divider.frameShape() == QFrame.Shape.HLine
    assert divider.height() == 1


def test_make_divider_returns_independent_instances(qapp):
    """Each call to _make_divider() returns a distinct QFrame object."""
    from ui.pipeline_window import _make_divider

    d1 = _make_divider()
    d2 = _make_divider()

    assert d1 is not d2


# ---------------------------------------------------------------------------
# M8 — tree header guard (assert → if … return)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# L2 — ImageFilesRepository cached as _image_repo
# ---------------------------------------------------------------------------


def test_image_repo_instantiated_once_on_init(qapp, mock_analysis_db, mock_config_manager):
    """ImageFilesRepository is constructed exactly once (in __init__), not per call."""
    from ui.pipeline_window import ImportPanel

    with patch("ui.pipeline.import_panel.ImageFilesRepository") as mock_repo:
        mock_repo.return_value.get_all.return_value = []
        panel = ImportPanel(
            analysis_db=mock_analysis_db,
            config_manager=mock_config_manager,
            dark_mode=True,
        )
        # One construction during __init__
        assert mock_repo.call_count == 1
        # _refresh() reuses the cached instance, no new construction
        panel._refresh()
        panel._refresh()
        assert mock_repo.call_count == 1


def test_image_repo_attribute_is_repo_instance(qapp, mock_analysis_db, mock_config_manager):
    """panel._image_repo is the ImageFilesRepository instance created in __init__."""
    from ui.pipeline_window import ImportPanel

    with patch("ui.pipeline.import_panel.ImageFilesRepository") as mock_repo:
        mock_instance = MagicMock()
        mock_instance.get_all.return_value = []
        mock_repo.return_value = mock_instance
        panel = ImportPanel(
            analysis_db=mock_analysis_db,
            config_manager=mock_config_manager,
            dark_mode=True,
        )

    assert panel._image_repo is mock_instance


def test_image_tree_header_is_configured_after_init(qapp, mock_analysis_db, mock_config_manager):
    """ImportPanel must configure the image_tree header without raising.

    The guard replaces `assert tree_hdr is not None` so that the code is safe
    even when Python runs with -O (which strips assert statements).
    """
    from PyQt6.QtWidgets import QHeaderView

    panel = _make_panel(qapp, mock_analysis_db, mock_config_manager)

    tree_hdr = panel.image_tree.header()
    assert tree_hdr is not None
    # Column 0 must be Interactive (set immediately after the guard)
    assert tree_hdr.sectionResizeMode(0) == QHeaderView.ResizeMode.Interactive
    # Last section must not stretch
    assert tree_hdr.stretchLastSection() is False


# ---------------------------------------------------------------------------
# Summary bar — Phase 2 additions
# ---------------------------------------------------------------------------


def test_summary_bar_exists_after_init(qapp, mock_analysis_db, mock_config_manager):
    """ImportPanel must create a _summary_bar QLabel during _build_ui."""
    from PyQt6.QtWidgets import QLabel

    panel = _make_panel(qapp, mock_analysis_db, mock_config_manager)
    assert panel._summary_bar is not None
    assert isinstance(panel._summary_bar, QLabel)


def test_summary_bar_shows_no_images_when_empty(qapp, mock_analysis_db, mock_config_manager):
    """When _update_summary_bar is called with [], it should indicate none found."""
    panel = _make_panel(qapp, mock_analysis_db, mock_config_manager)
    assert panel._summary_bar is not None
    # Call directly — _post_init fires asynchronously via QTimer so we trigger manually
    panel._update_summary_bar([])
    assert "No images" in panel._summary_bar.text() or "found" in panel._summary_bar.text().lower()


def test_update_summary_bar_counts_analyzed(qapp, mock_analysis_db, mock_config_manager):
    """_update_summary_bar must count analyzed images correctly."""
    panel = _make_panel(qapp, mock_analysis_db, mock_config_manager)
    images = [
        {"status": "analyzed"},
        {"status": "analyzed"},
        {"status": "registered"},
        {"status": "error"},
    ]
    panel._update_summary_bar(images)
    text = panel._summary_bar.text()
    assert "4" in text  # total
    assert "2" in text  # analyzed count


def test_update_summary_bar_counts_errors(qapp, mock_analysis_db, mock_config_manager):
    """_update_summary_bar must include error count when errors exist."""
    panel = _make_panel(qapp, mock_analysis_db, mock_config_manager)
    images = [
        {"status": "analyzed"},
        {"status": "error"},
        {"status": "error"},
    ]
    panel._update_summary_bar(images)
    text = panel._summary_bar.text()
    # Should mention 2 errors
    assert "2" in text


def test_update_summary_bar_no_errors_omits_error_segment(
    qapp, mock_analysis_db, mock_config_manager
):
    """When there are no errors, _update_summary_bar should not include an error indicator."""
    panel = _make_panel(qapp, mock_analysis_db, mock_config_manager)
    images = [{"status": "analyzed"}, {"status": "registered"}]
    panel._update_summary_bar(images)
    text = panel._summary_bar.text()
    assert "\u274c" not in text  # ❌ emoji only appears for errors


def test_summary_bar_updated_after_refresh(qapp, mock_analysis_db, mock_config_manager):
    """Calling _refresh() must update the summary bar with correct image counts."""
    from unittest.mock import patch

    images = [
        {
            "filename": "a.png",
            "file_path": "/a.png",
            "status": "analyzed",
            "file_mtime": 0,
            "file_size": 0,
            "directory_path": "/",
            "is_ignored": False,
        },
        {
            "filename": "b.png",
            "file_path": "/b.png",
            "status": "registered",
            "file_mtime": 0,
            "file_size": 0,
            "directory_path": "/",
            "is_ignored": False,
        },
    ]

    with patch("ui.pipeline.import_panel.ImageFilesRepository") as mock_repo:
        mock_repo.return_value.get_all.return_value = images
        from ui.pipeline_window import ImportPanel

        panel = ImportPanel(
            analysis_db=mock_analysis_db,
            config_manager=mock_config_manager,
            dark_mode=False,
        )

    assert panel._summary_bar is not None
    # Manually trigger _refresh() because _post_init is deferred via QTimer.singleShot
    panel._refresh()
    text = panel._summary_bar.text()
    # 2 total images should appear somewhere in the bar
    assert "2" in text
