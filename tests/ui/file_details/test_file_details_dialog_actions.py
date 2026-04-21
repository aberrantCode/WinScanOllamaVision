"""
Tests for _DialogActionsMixin in ui.file_details.file_details_dialog_actions.

Covers:
- _save_metadata() writes correct fields to both databases
- _delete_record() calls mark_image_deleted (soft-delete)
- _view_document() rejects paths outside configured source directories
"""

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Minimal concrete class that exercises the mixin without a real QDialog
# ---------------------------------------------------------------------------


class _FakeSignal:
    """Minimal signal stub that records the last emitted value."""

    def __init__(self):
        self._emitted = []

    def emit(self, *args):
        self._emitted.extend(args)

    @property
    def last(self):
        return self._emitted[-1] if self._emitted else None


class TestableDialogActions:
    """Concrete host for _DialogActionsMixin that mimics what FileDetailsDialog provides."""

    # Sentinel value to distinguish "caller explicitly passed None" vs "not passed"
    _UNSET = object()

    def __init__(self, analysis_db=_UNSET, metadata_db=_UNSET, config_manager=None, file_data=None):
        from ui.file_details.file_details_dialog_actions import _DialogActionsMixin

        # Dynamically inject the mixin's methods into this instance so we can
        # call them without instantiating a real QDialog.
        for attr in dir(_DialogActionsMixin):
            if not attr.startswith("__"):
                method = getattr(_DialogActionsMixin, attr)
                if callable(method):
                    import types

                    setattr(self, attr, types.MethodType(method, self))

        # Use sentinel to distinguish explicitly-None from "use a mock default"
        self.analysis_db = (
            MagicMock() if analysis_db is TestableDialogActions._UNSET else analysis_db
        )
        self.metadata_db = (
            MagicMock() if metadata_db is TestableDialogActions._UNSET else metadata_db
        )
        self.config_manager = config_manager or MagicMock()
        self.file_data = file_data or {"full_path": "/source/docs/test.png", "filename": "test.png"}
        self.is_dark_mode = False
        self.theme_colors = {
            "accent": "#3B82F6",
            "text_primary": "#111827",
            "bg_secondary": "#F9FAFB",
            "border": "#E5E7EB",
        }
        self.metadata_inputs = {}
        self.original_metadata_values = {}
        self.metadata_saved = _FakeSignal()
        self.re_analyze_requested = _FakeSignal()
        self.record_deleted = _FakeSignal()

    # Stubs for methods called by the mixin that need a real widget context
    def parent(self):
        return None

    def accept(self):
        pass

    def _store_original_metadata_values(self):
        pass

    def _update_save_button_state(self):
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_analysis_db():
    db = MagicMock()
    db.get_analysis.return_value = {
        "document_type": "Invoice",
        "company": "Acme",
        "document_date": "2024-01-01",
        "page_number": 1,
        "total_pages": 2,
        "rotation_needed": "none",
        "tax_related": False,
        "confidence": 95.0,
        "output_filename": "",
        "document_category": "",
    }
    return db


@pytest.fixture
def mock_metadata_db():
    db = MagicMock()
    db.get_rotation.return_value = 0
    return db


# ---------------------------------------------------------------------------
# _save_metadata tests
# ---------------------------------------------------------------------------


def test_save_metadata_calls_update_analysis_metadata(mock_analysis_db, mock_metadata_db):
    """_save_metadata() must call analysis_db.update_analysis_metadata with the file path."""
    from PyQt6.QtWidgets import QApplication, QLineEdit

    QApplication.instance() or QApplication([])

    line_edit = QLineEdit()
    line_edit.setText("Invoice")

    host = TestableDialogActions(
        analysis_db=mock_analysis_db,
        metadata_db=mock_metadata_db,
        file_data={"full_path": "/source/docs/test.png", "filename": "test.png"},
    )
    host.metadata_inputs = {"document_type": line_edit}

    with patch("ui.file_details.file_details_dialog_actions.show_information"):
        host._save_metadata()

    mock_analysis_db.update_analysis_metadata.assert_called_once()
    call_args = mock_analysis_db.update_analysis_metadata.call_args
    assert call_args[0][0] == "/source/docs/test.png"


def test_save_metadata_calls_save_rotation_on_metadata_db(mock_analysis_db, mock_metadata_db):
    """_save_metadata() must persist rotation via metadata_db.save_rotation."""
    from PyQt6.QtWidgets import QApplication, QComboBox

    QApplication.instance() or QApplication([])

    rotation_combo = QComboBox()
    rotation_combo.addItem("90_cw")
    rotation_combo.setCurrentText("90_cw")

    host = TestableDialogActions(
        analysis_db=mock_analysis_db,
        metadata_db=mock_metadata_db,
        file_data={"full_path": "/source/docs/test.png", "filename": "test.png"},
    )
    host.metadata_inputs = {"rotation_needed": rotation_combo}

    with patch("ui.file_details.file_details_dialog_actions.show_information"):
        host._save_metadata()

    # rotation_needed "90_cw" maps to 90 degrees
    mock_metadata_db.save_rotation.assert_called_once_with("/source/docs/test.png", 90)


def test_save_metadata_calls_save_metadata_on_metadata_db(mock_analysis_db, mock_metadata_db):
    """_save_metadata() must call metadata_db.save_metadata to persist normalized metadata."""
    from PyQt6.QtWidgets import QApplication, QLineEdit

    QApplication.instance() or QApplication([])

    company_edit = QLineEdit()
    company_edit.setText("TestCorp")

    host = TestableDialogActions(
        analysis_db=mock_analysis_db,
        metadata_db=mock_metadata_db,
        file_data={"full_path": "/source/docs/test.png", "filename": "test.png"},
    )
    host.metadata_inputs = {"company": company_edit}

    with patch("ui.file_details.file_details_dialog_actions.show_information"):
        host._save_metadata()

    mock_metadata_db.save_metadata.assert_called_once()
    call_args = mock_metadata_db.save_metadata.call_args
    assert call_args[0][0] == "/source/docs/test.png"


def test_save_metadata_emits_metadata_saved_signal(mock_analysis_db, mock_metadata_db):
    """_save_metadata() must emit metadata_saved signal with the file path."""
    from PyQt6.QtWidgets import QApplication, QLineEdit

    QApplication.instance() or QApplication([])

    line_edit = QLineEdit()
    line_edit.setText("Invoice")

    host = TestableDialogActions(
        analysis_db=mock_analysis_db,
        metadata_db=mock_metadata_db,
        file_data={"full_path": "/source/docs/test.png", "filename": "test.png"},
    )
    host.metadata_inputs = {"document_type": line_edit}

    with patch("ui.file_details.file_details_dialog_actions.show_information"):
        host._save_metadata()

    assert host.metadata_saved.last == "/source/docs/test.png"


def test_save_metadata_warns_when_no_databases():
    """_save_metadata() shows warning when analysis_db and metadata_db are both None."""
    from PyQt6.QtWidgets import QApplication, QLineEdit

    QApplication.instance() or QApplication([])

    line_edit = QLineEdit()
    line_edit.setText("Invoice")

    host = TestableDialogActions(
        analysis_db=None,
        metadata_db=None,
        file_data={"full_path": "/source/docs/test.png", "filename": "test.png"},
    )
    host.metadata_inputs = {"document_type": line_edit}

    # Patch both show_warning (called when DB is missing) and show_information
    # (called on success) to prevent Qt widget hierarchy errors.
    with (
        patch("ui.file_details.file_details_dialog_actions.show_warning") as mock_warn,
        patch("ui.file_details.file_details_dialog_actions.show_information"),
    ):
        host._save_metadata()

    mock_warn.assert_called_once()
    # The third positional arg is the message body
    warning_msg = mock_warn.call_args[0][2]
    assert "analysis_db" in warning_msg or "metadata_db" in warning_msg


def test_save_metadata_middle_failure_aborts_cleanly_no_silent_partial_save():
    """
    Partial-save invariant lock (H-1).

    _save_metadata() performs three sequential writes against two databases:
      1. analysis_db.update_analysis_metadata()
      2. metadata_db.save_rotation()
      3. metadata_db.save_metadata()

    A prior revision wrapped write #3 in its own try/except that swallowed
    the error to a logger.warning — execution continued and the user saw
    "Metadata saved successfully!" even when the normalized-metadata table
    was never written. That made real bugs invisible.

    This test simulates write #2 (save_rotation) failing and locks in the
    four invariants that MUST hold on a mid-failure:

        A) show_critical is called (user sees the failure)
        B) show_information ("Success!") is NOT called
        C) metadata_saved signal is NOT emitted
        D) file_data is NOT merged with the user's in-flight edits

    A future refactor that re-introduces a middle-swallow will break (A/B).
    A future refactor that emits-then-fails will break (C). A future
    refactor that merges before persisting will break (D). These four are
    the precise contract a subsequent save_metadata reviewer cares about.
    """
    from PyQt6.QtWidgets import QApplication, QComboBox, QLineEdit

    QApplication.instance() or QApplication([])

    # Include one text input (company) AND a rotation combo so all three
    # writes get triggered and save_rotation is reached.
    company_edit = QLineEdit()
    company_edit.setText("NewCompanyValue")
    rotation_combo = QComboBox()
    rotation_combo.addItem("90_cw")
    rotation_combo.setCurrentText("90_cw")

    analysis_db = MagicMock()
    analysis_db.get_analysis.return_value = {
        "company": "OldCompany",
        "rotation_needed": "none",
    }
    metadata_db = MagicMock()
    # Force middle-write failure
    metadata_db.save_rotation.side_effect = RuntimeError("simulated DB lock contention mid-save")

    original_file_data = {
        "full_path": "/source/docs/test.png",
        "filename": "test.png",
        "company": "OldCompany",
    }

    host = TestableDialogActions(
        analysis_db=analysis_db,
        metadata_db=metadata_db,
        file_data=dict(original_file_data),
    )
    host.metadata_inputs = {
        "company": company_edit,
        "rotation_needed": rotation_combo,
    }

    with (
        patch("ui.file_details.file_details_dialog_actions.show_critical") as mock_critical,
        patch("ui.file_details.file_details_dialog_actions.show_information") as mock_info,
    ):
        # Must not raise; the outer catch in _save_metadata handles the error
        host._save_metadata()

    # Invariant A — user sees the failure
    mock_critical.assert_called_once()
    critical_args = mock_critical.call_args[0]
    assert "Save Failed" in critical_args[1]
    assert "simulated DB lock contention" in critical_args[2]

    # Invariant B — no lying "Success!" toast
    mock_info.assert_not_called()

    # Invariant C — signal not emitted (no false downstream refresh)
    assert host.metadata_saved.last is None

    # Invariant D — file_data is not polluted with unsaved edits
    assert host.file_data["company"] == "OldCompany", (
        "file_data must NOT be merged with the user's in-flight edits when "
        "the save failed mid-way — otherwise closing & re-opening the "
        "dialog would show values that were never persisted."
    )

    # Sanity — the first write did happen (and cannot be rolled back across
    # separate DB objects). This is documented current behaviour and the
    # reason we show_critical instead of pretending nothing happened.
    analysis_db.update_analysis_metadata.assert_called_once()
    # Third write should never have been attempted
    metadata_db.save_metadata.assert_not_called()


# ---------------------------------------------------------------------------
# _delete_record tests
# ---------------------------------------------------------------------------


def _run_delete_record_accepted(host, delete_physical=False):
    """
    Helper: run _delete_record() with the confirmation dialog auto-accepted.

    Patches the QDialog class used inside _delete_record so that:
    - Construction succeeds even when parent is not a real QWidget.
    - exec() returns the Accepted code.
    - QCheckBox.isChecked() returns the desired value.
    """
    from PyQt6.QtWidgets import QDialog

    accepted_code = QDialog.DialogCode.Accepted

    with patch("ui.file_details.file_details_dialog_actions.QDialog") as mock_dialog_cls:
        mock_dialog_instance = MagicMock()
        mock_dialog_instance.exec.return_value = accepted_code
        mock_dialog_cls.return_value = mock_dialog_instance
        # Preserve the DialogCode enum so the comparison in the source code works
        mock_dialog_cls.DialogCode.Accepted = accepted_code

        with patch("ui.file_details.file_details_dialog_actions.QCheckBox") as mock_cb_cls:
            mock_cb = MagicMock()
            mock_cb.isChecked.return_value = delete_physical
            mock_cb_cls.return_value = mock_cb

            # Also patch layout/label/button constructors to avoid QWidget parent issues
            with (
                patch("ui.file_details.file_details_dialog_actions.QVBoxLayout"),
                patch("ui.file_details.file_details_dialog_actions.QHBoxLayout"),
                patch("ui.file_details.file_details_dialog_actions.QLabel"),
                patch("ui.file_details.file_details_dialog_actions.QPushButton"),
            ):
                host._delete_record()


def test_delete_record_calls_mark_image_deleted(mock_analysis_db):
    """_delete_record() must soft-delete via analysis_db.mark_image_deleted."""
    from PyQt6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])

    host = TestableDialogActions(
        analysis_db=mock_analysis_db,
        file_data={"full_path": "/source/docs/test.png", "filename": "test.png"},
    )

    _run_delete_record_accepted(host, delete_physical=False)

    mock_analysis_db.mark_image_deleted.assert_called_once_with("/source/docs/test.png")


def test_delete_record_calls_delete_metadata_by_path(mock_analysis_db):
    """_delete_record() must also remove metadata via analysis_db.delete_metadata_by_path."""
    from PyQt6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])

    host = TestableDialogActions(
        analysis_db=mock_analysis_db,
        file_data={"full_path": "/source/docs/test.png", "filename": "test.png"},
    )

    _run_delete_record_accepted(host, delete_physical=False)

    mock_analysis_db.delete_metadata_by_path.assert_called_once_with("/source/docs/test.png")


# ---------------------------------------------------------------------------
# _view_document / is_path_confined tests (path confinement)
# ---------------------------------------------------------------------------


def test_view_document_rejects_path_outside_source_dirs():
    """_view_document() must not call os.startfile for paths outside source directories."""
    from PyQt6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])

    mock_config = MagicMock()
    mock_config.get_directories.return_value = ["/source/docs"]

    host = TestableDialogActions(
        config_manager=mock_config,
        file_data={"full_path": "/etc/passwd", "filename": "passwd"},
    )

    # Override _find_actual_file_path to return the suspicious path directly
    host._find_actual_file_path = lambda stored, filename: "/etc/passwd"

    with (
        patch("ui.file_details.file_details_dialog_actions.show_warning") as mock_warn,
        patch("os.startfile") as mock_startfile,
    ):
        host._view_document()

    mock_startfile.assert_not_called()
    mock_warn.assert_called_once()
    warning_title = mock_warn.call_args[0][1]
    assert "Access Denied" in warning_title


def test_view_document_allows_path_within_source_dirs():
    """_view_document() must call os.startfile for paths inside source directories."""
    from PyQt6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])

    import os

    source_dir = os.path.normpath("C:/source/docs")

    mock_config = MagicMock()
    mock_config.get_directories.return_value = [source_dir]

    safe_path = os.path.join(source_dir, "invoice.png")
    host = TestableDialogActions(
        config_manager=mock_config,
        file_data={"full_path": safe_path, "filename": "invoice.png"},
    )
    host._find_actual_file_path = lambda stored, filename: safe_path

    with patch("os.startfile") as mock_startfile:
        host._view_document()

    mock_startfile.assert_called_once_with(safe_path)
