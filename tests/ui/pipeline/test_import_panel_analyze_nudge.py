"""
Tests for the post-discovery "Go to Analyze" behaviour in ui.pipeline.import_panel.

Two code paths depend on the
``SourceDirectories.auto_advance_on_empty_discovery`` setting:

* **Auto-advance ON (default)** — when a discovery scan finds no new images
  but there are pending/errored files, ``jump_to_analyze_requested`` is
  emitted immediately and no banner is shown.

* **Auto-advance OFF** — instead of switching tabs, a dismissible banner
  appears on the Import panel offering a one-click jump to Analyze.

Both paths must be no-ops when ``new_count > 0`` or when there is no pending
or errored work.
"""

from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _make_config_manager(auto_advance: bool = True):
    """Config manager stub with the controllable auto_advance setting."""
    cfg = MagicMock()
    cfg.get_directories.return_value = ["/source/docs"]
    cfg.get_setting.return_value = "dark"

    def get_bool(section, key, default):
        if section == "SourceDirectories" and key == "auto_advance_on_empty_discovery":
            return auto_advance
        return default

    cfg.get_bool.side_effect = get_bool
    return cfg


@pytest.fixture
def mock_analysis_db():
    db = MagicMock()
    db.connection = MagicMock()
    return db


def _make_panel(qapp, mock_analysis_db, config_manager, images: list[dict]):
    """Build an ImportPanel whose repo will return *images* from get_all()."""
    from ui.pipeline.import_panel import ImportPanel

    with patch("ui.pipeline.import_panel.ImageFilesRepository") as mock_repo_cls:
        mock_repo_cls.return_value.get_all.return_value = images
        panel = ImportPanel(
            analysis_db=mock_analysis_db,
            config_manager=config_manager,
            dark_mode=True,
        )
    return panel


# ---------------------------------------------------------------------------
# Default banner state
# ---------------------------------------------------------------------------


def test_banner_hidden_by_default(qapp, mock_analysis_db):
    panel = _make_panel(qapp, mock_analysis_db, _make_config_manager(), images=[])
    # isHidden() is the intent-safe check in headless tests — isVisible() is False
    # whenever ancestors aren't shown, regardless of the widget's own state.
    assert panel._analyze_nudge is not None
    assert panel._analyze_nudge.isHidden() is True


# ---------------------------------------------------------------------------
# No-op guards (apply regardless of auto_advance setting)
# ---------------------------------------------------------------------------


def test_no_op_when_new_count_positive(qapp, mock_analysis_db):
    """When discovery finds new images, neither path should fire."""
    images = [{"status": "registered", "is_ignored": False}]
    panel = _make_panel(
        qapp, mock_analysis_db, _make_config_manager(auto_advance=True), images=images
    )
    emissions: list[bool] = []
    panel.jump_to_analyze_requested.connect(lambda: emissions.append(True))

    panel.maybe_show_analyze_nudge_after_discovery(new_count=5)

    assert panel._analyze_nudge.isHidden() is True
    assert emissions == []


def test_no_op_when_nothing_pending_or_errored(qapp, mock_analysis_db):
    """0 new + 0 pending + 0 errors = nothing to propose."""
    images = [
        {"status": "analyzed", "is_ignored": False},
        {"status": "analyzed", "is_ignored": False},
    ]
    panel = _make_panel(
        qapp, mock_analysis_db, _make_config_manager(auto_advance=True), images=images
    )
    emissions: list[bool] = []
    panel.jump_to_analyze_requested.connect(lambda: emissions.append(True))

    panel.maybe_show_analyze_nudge_after_discovery(new_count=0)

    assert panel._analyze_nudge.isHidden() is True
    assert emissions == []


def test_ignored_rows_are_excluded_from_counts(qapp, mock_analysis_db):
    """Rows with is_ignored=True must not count — nothing should fire."""
    images = [
        {"status": "registered", "is_ignored": True},
        {"status": "registered", "is_ignored": True},
        {"status": "analyzed", "is_ignored": False},
    ]
    panel = _make_panel(
        qapp, mock_analysis_db, _make_config_manager(auto_advance=True), images=images
    )
    emissions: list[bool] = []
    panel.jump_to_analyze_requested.connect(lambda: emissions.append(True))

    panel.maybe_show_analyze_nudge_after_discovery(new_count=0)

    assert panel._analyze_nudge.isHidden() is True
    assert emissions == []


# ---------------------------------------------------------------------------
# Auto-advance ON (default) — fires signal, no banner
# ---------------------------------------------------------------------------


def test_auto_advance_emits_signal_when_pending_exists(qapp, mock_analysis_db):
    images = [{"status": "registered", "is_ignored": False}]
    panel = _make_panel(
        qapp, mock_analysis_db, _make_config_manager(auto_advance=True), images=images
    )
    emissions: list[bool] = []
    panel.jump_to_analyze_requested.connect(lambda: emissions.append(True))

    panel.maybe_show_analyze_nudge_after_discovery(new_count=0)

    assert emissions == [True], "jump signal must fire once in auto-advance mode"
    assert panel._analyze_nudge.isHidden() is True, "banner must NOT appear in auto-advance mode"


def test_auto_advance_emits_signal_when_only_errors_exist(qapp, mock_analysis_db):
    images = [{"status": "error", "is_ignored": False}]
    panel = _make_panel(
        qapp, mock_analysis_db, _make_config_manager(auto_advance=True), images=images
    )
    emissions: list[bool] = []
    panel.jump_to_analyze_requested.connect(lambda: emissions.append(True))

    panel.maybe_show_analyze_nudge_after_discovery(new_count=0)

    assert emissions == [True]
    assert panel._analyze_nudge.isHidden() is True


# ---------------------------------------------------------------------------
# Auto-advance OFF — banner shown, no auto signal
# ---------------------------------------------------------------------------


def test_banner_shown_when_auto_advance_off_and_pending_exists(qapp, mock_analysis_db):
    images = [
        {"status": "analyzed", "is_ignored": False},
        {"status": "registered", "is_ignored": False},
        {"status": "registered", "is_ignored": False},
    ]
    panel = _make_panel(
        qapp, mock_analysis_db, _make_config_manager(auto_advance=False), images=images
    )
    emissions: list[bool] = []
    panel.jump_to_analyze_requested.connect(lambda: emissions.append(True))

    panel.maybe_show_analyze_nudge_after_discovery(new_count=0)

    assert emissions == [], "signal must NOT auto-fire when auto_advance is off"
    assert panel._analyze_nudge.isHidden() is False
    assert "2" in panel._analyze_nudge_label.text()
    assert "pending" in panel._analyze_nudge_label.text().lower()


def test_banner_shown_when_auto_advance_off_and_only_errors_exist(qapp, mock_analysis_db):
    images = [
        {"status": "analyzed", "is_ignored": False},
        {"status": "error", "is_ignored": False},
    ]
    panel = _make_panel(
        qapp, mock_analysis_db, _make_config_manager(auto_advance=False), images=images
    )

    panel.maybe_show_analyze_nudge_after_discovery(new_count=0)

    assert panel._analyze_nudge.isHidden() is False
    assert "error" in panel._analyze_nudge_label.text().lower()


def test_banner_accept_button_emits_jump_signal_and_hides(qapp, mock_analysis_db):
    """When auto-advance is off and the user clicks 'Go to Analyze' on the banner,
    the same signal fires and the banner hides."""
    images = [{"status": "registered", "is_ignored": False}]
    panel = _make_panel(
        qapp, mock_analysis_db, _make_config_manager(auto_advance=False), images=images
    )
    panel.maybe_show_analyze_nudge_after_discovery(new_count=0)
    assert panel._analyze_nudge.isHidden() is False

    emissions: list[bool] = []
    panel.jump_to_analyze_requested.connect(lambda: emissions.append(True))

    panel._on_analyze_nudge_accepted()

    assert emissions == [True]
    assert panel._analyze_nudge.isHidden() is True


def test_banner_hides_when_followup_scan_finds_new_images(qapp, mock_analysis_db):
    """A second discovery run finding new files must clear any stale banner."""
    images = [{"status": "registered", "is_ignored": False}]
    panel = _make_panel(
        qapp, mock_analysis_db, _make_config_manager(auto_advance=False), images=images
    )

    # First run: 0 new, 1 pending, auto-advance off → banner shows
    panel.maybe_show_analyze_nudge_after_discovery(new_count=0)
    assert panel._analyze_nudge.isHidden() is False

    # Second run: 3 new files → banner must be cleared
    panel.maybe_show_analyze_nudge_after_discovery(new_count=3)
    assert panel._analyze_nudge.isHidden() is True


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------


def test_repo_exception_is_swallowed_gracefully(qapp, mock_analysis_db):
    """If the image repo raises while computing counts, we must not crash or
    leave a stale banner showing or emit a spurious signal."""
    images = [{"status": "registered", "is_ignored": False}]
    panel = _make_panel(
        qapp, mock_analysis_db, _make_config_manager(auto_advance=True), images=images
    )
    emissions: list[bool] = []
    panel.jump_to_analyze_requested.connect(lambda: emissions.append(True))

    panel._image_repo.get_all.side_effect = RuntimeError("db gone")

    panel.maybe_show_analyze_nudge_after_discovery(new_count=0)

    assert panel._analyze_nudge.isHidden() is True
    assert emissions == []
