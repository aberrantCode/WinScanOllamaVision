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
    from ui.pipeline import ImportPanel

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

            from ui.pipeline import ImportPanel

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
            from ui.pipeline import ImportPanel

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
        from ui.pipeline import ImportPanel

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
        from ui.pipeline import ImportPanel

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

    from ui.pipeline.stages import _make_divider

    divider = _make_divider()

    assert isinstance(divider, QFrame)
    assert divider.frameShape() == QFrame.Shape.HLine
    assert divider.height() == 1


def test_make_divider_returns_independent_instances(qapp):
    """Each call to _make_divider() returns a distinct QFrame object."""
    from ui.pipeline.stages import _make_divider

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
    from ui.pipeline import ImportPanel

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
    from ui.pipeline import ImportPanel

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
# Column-header sorting
# ---------------------------------------------------------------------------


def test_image_tree_sorting_enabled(qapp, mock_analysis_db, mock_config_manager):
    """Clicking a column header must sort — sorting has to be enabled and shown."""
    panel = _make_panel(qapp, mock_analysis_db, mock_config_manager)

    assert panel.image_tree.isSortingEnabled() is True
    hdr = panel.image_tree.header()
    assert hdr is not None
    assert hdr.isSortIndicatorShown() is True
    assert hdr.sectionsClickable() is True


def test_size_column_sorts_numerically_not_lexically(qapp):
    """The Size column must sort by byte count, not by the formatted string.

    Lexically '1.2 MB' < '900 B'; numerically 900 B < 1.2 MB. The item must
    order by bytes.
    """
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QTreeWidget

    from ui.pipeline.import_panel import _ImageTreeItem

    tree = QTreeWidget()
    tree.setColumnCount(4)
    tree.setSortingEnabled(True)

    small = _ImageTreeItem(["a.png", "registered", "2024-01-01", "900 B"])
    small.setData(3, Qt.ItemDataRole.UserRole, 900)
    big = _ImageTreeItem(["b.png", "registered", "2024-01-02", "1.2 MB"])
    big.setData(3, Qt.ItemDataRole.UserRole, 1_258_291)

    tree.addTopLevelItem(big)
    tree.addTopLevelItem(small)
    tree.sortItems(3, Qt.SortOrder.AscendingOrder)

    # Ascending by bytes: 900 B first, then 1.2 MB.
    assert tree.topLevelItem(0).text(3) == "900 B"
    assert tree.topLevelItem(1).text(3) == "1.2 MB"


def test_date_column_sorts_by_mtime(qapp):
    """The Date column must sort by the stored mtime, oldest first ascending."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QTreeWidget

    from ui.pipeline.import_panel import _ImageTreeItem

    tree = QTreeWidget()
    tree.setColumnCount(4)
    tree.setSortingEnabled(True)

    newer = _ImageTreeItem(["a.png", "registered", "2024-06-01", "1 KB"])
    newer.setData(2, Qt.ItemDataRole.UserRole, 1_717_200_000)
    older = _ImageTreeItem(["b.png", "registered", "2024-01-01", "1 KB"])
    older.setData(2, Qt.ItemDataRole.UserRole, 1_704_067_200)

    tree.addTopLevelItem(newer)
    tree.addTopLevelItem(older)
    tree.sortItems(2, Qt.SortOrder.AscendingOrder)

    assert tree.topLevelItem(0).text(2) == "2024-01-01"
    assert tree.topLevelItem(1).text(2) == "2024-06-01"


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
        from ui.pipeline import ImportPanel

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


# ---------------------------------------------------------------------------
# Scan UI locking
# ---------------------------------------------------------------------------


def test_on_scan_clicked_locks_controls(qapp, mock_analysis_db, mock_config_manager):
    """_on_scan_clicked must lock all controls when scan starts."""
    with patch("ui.pipeline.import_panel.ImageFilesRepository") as mock_repo:
        mock_repo.return_value.get_all.return_value = []
        with patch("ui.pipeline.import_panel.DiscoveryWorker") as mock_worker_class:
            from ui.pipeline import ImportPanel

            panel = ImportPanel(
                analysis_db=mock_analysis_db,
                config_manager=mock_config_manager,
                dark_mode=True,
            )

            mock_worker_class.return_value.isRunning.return_value = False
            panel._on_scan_clicked()

            # Assert all controls are disabled
            assert panel._refresh_btn.isEnabled() is False
            assert panel.directory_combo.isEnabled() is False
            assert panel._select_all_btn.isEnabled() is False
            assert panel._deselect_btn.isEnabled() is False


def test_set_controls_locked_disables_controls_when_true():
    """_set_controls_locked(True) must disable all four controls."""
    # Create a minimal mock panel for testing the _set_controls_locked method
    mock_refresh_btn = MagicMock()
    mock_dir_combo = MagicMock()
    mock_select_all_btn = MagicMock()
    mock_deselect_btn = MagicMock()

    # Create a dict-like object that has the attributes
    from ui.pipeline.import_panel import ImportPanel

    # We'll call the method directly on a dummy object
    class DummyPanel:
        def __init__(self):
            self._refresh_btn = mock_refresh_btn
            self.directory_combo = mock_dir_combo
            self._select_all_btn = mock_select_all_btn
            self._deselect_btn = mock_deselect_btn

        _set_controls_locked = ImportPanel._set_controls_locked

    panel = DummyPanel()
    panel._set_controls_locked(True)

    # Assert all buttons had setEnabled called with False
    mock_refresh_btn.setEnabled.assert_called_with(False)
    mock_dir_combo.setEnabled.assert_called_with(False)
    mock_select_all_btn.setEnabled.assert_called_with(False)
    mock_deselect_btn.setEnabled.assert_called_with(False)


def test_set_controls_locked_enables_controls_when_false():
    """_set_controls_locked(False) must enable all four controls."""
    mock_refresh_btn = MagicMock()
    mock_dir_combo = MagicMock()
    mock_select_all_btn = MagicMock()
    mock_deselect_btn = MagicMock()

    from ui.pipeline.import_panel import ImportPanel

    class DummyPanel:
        def __init__(self):
            self._refresh_btn = mock_refresh_btn
            self.directory_combo = mock_dir_combo
            self._select_all_btn = mock_select_all_btn
            self._deselect_btn = mock_deselect_btn

        _set_controls_locked = ImportPanel._set_controls_locked

    panel = DummyPanel()
    panel._set_controls_locked(False)

    # Assert all buttons had setEnabled called with True
    mock_refresh_btn.setEnabled.assert_called_with(True)
    mock_dir_combo.setEnabled.assert_called_with(True)
    mock_select_all_btn.setEnabled.assert_called_with(True)
    mock_deselect_btn.setEnabled.assert_called_with(True)


def test_lock_for_external_scan_wires_signals():
    """lock_for_external_scan must wire worker signals to the correct slots."""
    # Create a fake panel with minimal setup
    from ui.pipeline.import_panel import ImportPanel

    class DummyPanel:
        def __init__(self):
            self._discovery_worker = None
            self.scan_btn = MagicMock()
            self.scan_progress_bar = MagicMock()
            self._refresh_btn = MagicMock()
            self.directory_combo = MagicMock()
            self._select_all_btn = MagicMock()
            self._deselect_btn = MagicMock()

        # Bind the real method
        lock_for_external_scan = ImportPanel.lock_for_external_scan
        _set_controls_locked = ImportPanel._set_controls_locked
        _on_scan_progress = MagicMock()
        _on_external_scan_finished = MagicMock()
        _on_external_scan_error = MagicMock()

    panel = DummyPanel()

    # Create a fake worker
    fake_worker = MagicMock()
    fake_worker.progress = MagicMock()
    fake_worker.finished = MagicMock()
    fake_worker.error = MagicMock()

    # Call lock_for_external_scan
    panel.lock_for_external_scan(fake_worker)

    # Assert worker is stored
    assert panel._discovery_worker is fake_worker

    # Assert signals are connected
    fake_worker.progress.connect.assert_called_once()
    fake_worker.finished.connect.assert_called_once()
    fake_worker.error.connect.assert_called_once()

    # Assert the button text changed
    panel.scan_btn.setText.assert_called_with("Stop Scan")


def _make_locked_dummy_panel():
    """A dummy panel bound to the real unlock-path handlers, with controls
    pre-locked and heavier collaborators (_refresh, dialogs, logger) mocked
    out so these can run without a full Qt panel / real DiscoveryWorker."""
    from ui.pipeline.import_panel import ImportPanel

    class DummyPanel:
        def __init__(self):
            self._discovery_worker = None
            self.scan_btn = MagicMock()
            self.scan_progress_bar = MagicMock()
            self._refresh_btn = MagicMock()
            self.directory_combo = MagicMock()
            self._select_all_btn = MagicMock()
            self._deselect_btn = MagicMock()
            self._refresh = MagicMock()
            self.maybe_show_analyze_nudge_after_discovery = MagicMock()

        _set_controls_locked = ImportPanel._set_controls_locked
        _on_scan_finished = ImportPanel._on_scan_finished
        _on_scan_error = ImportPanel._on_scan_error
        _on_external_scan_finished = ImportPanel._on_external_scan_finished
        _on_external_scan_error = ImportPanel._on_external_scan_error

    panel = DummyPanel()
    panel._set_controls_locked(True)
    return panel


def test_on_scan_finished_unlocks_controls():
    """_on_scan_finished must re-enable all four controls once the manual
    scan completes."""
    with patch("ui.pipeline.import_panel.show_information"):
        panel = _make_locked_dummy_panel()

        panel._on_scan_finished(3)

        panel._refresh_btn.setEnabled.assert_called_with(True)
        panel.directory_combo.setEnabled.assert_called_with(True)
        panel._select_all_btn.setEnabled.assert_called_with(True)
        panel._deselect_btn.setEnabled.assert_called_with(True)
        panel._refresh.assert_called_once()


def test_on_scan_error_unlocks_controls():
    """_on_scan_error must re-enable all four controls when a manual scan fails."""
    with patch("ui.pipeline.import_panel.show_warning"):
        panel = _make_locked_dummy_panel()

        panel._on_scan_error("boom")

        panel._refresh_btn.setEnabled.assert_called_with(True)
        panel.directory_combo.setEnabled.assert_called_with(True)
        panel._select_all_btn.setEnabled.assert_called_with(True)
        panel._deselect_btn.setEnabled.assert_called_with(True)


def test_on_external_scan_finished_unlocks_refreshes_and_stays_silent():
    """_on_external_scan_finished must re-enable controls and refresh, but
    must NOT show a completion dialog (startup scans notify via toast, not
    a modal) — unlike _on_scan_finished, which does show one for manual scans."""
    with patch("ui.pipeline.import_panel.show_information") as mock_show_info:
        panel = _make_locked_dummy_panel()

        panel._on_external_scan_finished(2)

        panel._refresh_btn.setEnabled.assert_called_with(True)
        panel.directory_combo.setEnabled.assert_called_with(True)
        panel._select_all_btn.setEnabled.assert_called_with(True)
        panel._deselect_btn.setEnabled.assert_called_with(True)
        panel._refresh.assert_called_once()
        mock_show_info.assert_not_called()


def test_on_external_scan_error_unlocks_controls():
    """_on_external_scan_error must re-enable all four controls."""
    panel = _make_locked_dummy_panel()

    panel._on_external_scan_error("connection refused")

    panel._refresh_btn.setEnabled.assert_called_with(True)
    panel.directory_combo.setEnabled.assert_called_with(True)
    panel._select_all_btn.setEnabled.assert_called_with(True)
    panel._deselect_btn.setEnabled.assert_called_with(True)
