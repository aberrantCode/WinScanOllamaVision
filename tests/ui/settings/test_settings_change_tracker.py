"""
Tests for _ChangeTrackerMixin in ui.settings.settings_change_tracker.

Covers:
- _capture_original_values() partial failure preserves already-captured values
  (does NOT reset _original_values to {})
- _update_save_button_style() does NOT call traceback.format_stack
- _update_save_button_style() behaves correctly when save_button is None
- _check_for_changes() does not run during initialization (tracking disabled)
"""

import logging
import traceback
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Minimal concrete host for _ChangeTrackerMixin
# ---------------------------------------------------------------------------


class TestableChangeTracker:
    """Concrete host that exercises _ChangeTrackerMixin without a real QDialog."""

    def __init__(self):
        from ui.settings.settings_change_tracker import _ChangeTrackerMixin

        # Inject all mixin methods
        for attr in dir(_ChangeTrackerMixin):
            if not attr.startswith("__"):
                method = getattr(_ChangeTrackerMixin, attr)
                if callable(method):
                    import types

                    setattr(self, attr, types.MethodType(method, self))

        self._original_values = {}
        self._tracking_enabled = True
        self.save_button = MagicMock()

        # Config manager stub
        self.config_manager = MagicMock()
        self.config_manager.get_setting.return_value = "light"

        # Logger stub
        self._logger = logging.getLogger("test_change_tracker")

    def _get_logger(self):
        return self._logger

    def _current_export_strategy(self):
        return "same_as_source"


def _make_checkbox(checked=False):
    cb = MagicMock()
    cb.isChecked.return_value = checked
    return cb


def _make_combo(text="", data=None):
    combo = MagicMock()
    combo.currentText.return_value = text
    combo.currentData.return_value = data
    return combo


def _make_spinbox(value=0):
    spin = MagicMock()
    spin.value.return_value = value
    return spin


def _make_textedit(text=""):
    edit = MagicMock()
    edit.toPlainText.return_value = text
    edit.text = lambda: text  # for lineEdit compat
    return edit


def _make_lineedit(text=""):
    edit = MagicMock()
    edit.text.return_value = text
    return edit


def _attach_all_widgets(host):
    """Attach all the widget attributes expected by _capture_original_values and _check_for_changes."""
    # General tab
    host.audit_trail_checkbox = _make_checkbox()
    host.auto_start_analysis_checkbox = _make_checkbox()
    host.confirm_exit_checkbox = _make_checkbox()
    host.persist_rotation_checkbox = _make_checkbox(True)
    host.log_sql_checkbox = _make_checkbox()

    # Provider tab
    host.provider_combo = _make_combo(data="ollama")
    host.ollama_model_combo = _make_combo(text="qwen2.5-vl:latest", data="qwen2.5-vl:latest")
    host.ollama_url_edit = _make_lineedit("http://localhost:11434")
    host.ollama_timeout_spin = _make_spinbox(60)
    host.claude_model_combo = _make_combo("claude-3-5-sonnet-20241022")
    host.claude_command_edit = _make_textedit("claude")
    host.claude_timeout_spin = _make_spinbox(60)
    host.gemini_model_combo = _make_combo("gemini-1.5-pro")
    host.gemini_command_edit = _make_textedit("gemini")
    host.gemini_timeout_spin = _make_spinbox(60)

    # Prompts tab
    host.pages_prompt_edit = _make_textedit("Extract pages")
    host.metadata_prompt_edit = _make_textedit("Extract metadata")

    # Directories tab
    mock_list = MagicMock()
    mock_list.count.return_value = 1
    mock_item = MagicMock()
    mock_item.text.return_value = "/source/docs"
    mock_list.item.return_value = mock_item
    mock_model = MagicMock()
    mock_list.model.return_value = mock_model
    host.directories_list = mock_list
    host.scan_on_startup_checkbox = _make_checkbox()
    host.export_static_radio = _make_checkbox()
    host.export_subfolder_radio = _make_checkbox()
    host.export_beside_radio = _make_checkbox()
    host.export_static_path_edit = _make_lineedit("")
    host.export_subfolder_name_edit = _make_lineedit("PDFs")
    host.discovery_enabled_checkbox = _make_checkbox()
    host.discovery_interval_spinbox = _make_spinbox(60)
    host.auto_analyze_checkbox = _make_checkbox()

    # Appearance tab
    host.theme_combo = _make_combo(data="light")
    host.png_zoom_combo = _make_combo("fit_window")
    host.pdf_zoom_combo = _make_combo("fit_window")
    host.png_zoom_percent = _make_spinbox(100)
    host.pdf_zoom_percent = _make_spinbox(100)
    host.minimize_to_tray_checkbox = _make_checkbox()
    host.close_to_tray_checkbox = _make_checkbox()


# ---------------------------------------------------------------------------
# _capture_original_values — partial failure test
# ---------------------------------------------------------------------------


def test_capture_original_values_partial_failure_preserves_captured():
    """
    When _capture_original_values raises midway, values captured BEFORE the
    exception must be preserved in _original_values (not reset to {}).
    """
    host = TestableChangeTracker()
    _attach_all_widgets(host)

    # Force an error midway through capture (after audit_trail is captured)
    # by breaking auto_start_analysis_checkbox
    host.auto_start_analysis_checkbox.isChecked.side_effect = RuntimeError("Widget destroyed")

    host._capture_original_values()

    # audit_trail must have been captured before the failure
    assert "audit_trail" in host._original_values
    # The dict must NOT be reset to {} on exception
    assert host._original_values != {}


def test_capture_original_values_success_captures_all_fields():
    """When no error occurs, all expected fields should be captured."""
    host = TestableChangeTracker()
    _attach_all_widgets(host)

    host._capture_original_values()

    expected_keys = [
        "audit_trail",
        "auto_start_analysis",
        "confirm_exit",
        "persist_rotation",
        "active_provider",
        "ollama_model",
        "ollama_url",
        "claude_model",
        "gemini_model",
        "directories",
        "theme",
    ]
    for key in expected_keys:
        assert key in host._original_values, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# _update_save_button_style — no traceback.format_stack
# ---------------------------------------------------------------------------


def test_update_save_button_style_no_traceback_format_stack():
    """
    _update_save_button_style() must NOT call traceback.format_stack.

    Calling format_stack on every keystroke is a performance hazard.
    """
    host = TestableChangeTracker()
    _attach_all_widgets(host)

    with patch.object(traceback, "format_stack") as mock_fmt:
        host._update_save_button_style(True)
        host._update_save_button_style(False)

    mock_fmt.assert_not_called()


def test_update_save_button_style_calls_setStyleSheet(qapp=None):
    """_update_save_button_style() must call setStyleSheet on the save_button."""
    host = TestableChangeTracker()
    _attach_all_widgets(host)

    host._update_save_button_style(True)
    host.save_button.setStyleSheet.assert_called()


def test_update_save_button_style_does_nothing_when_no_button():
    """_update_save_button_style() must silently return when save_button is None."""
    host = TestableChangeTracker()
    _attach_all_widgets(host)
    host.save_button = None  # No button

    # Should not raise
    host._update_save_button_style(True)
    host._update_save_button_style(False)


def test_update_save_button_style_enabled_sets_button_enabled():
    """When enabled=True, save_button.setEnabled(True) must be called."""
    host = TestableChangeTracker()
    _attach_all_widgets(host)

    host._update_save_button_style(True)

    host.save_button.setEnabled.assert_called_with(True)


def test_update_save_button_style_disabled_sets_button_disabled():
    """When enabled=False, save_button.setEnabled(False) must be called."""
    host = TestableChangeTracker()
    _attach_all_widgets(host)

    host._update_save_button_style(False)

    host.save_button.setEnabled.assert_called_with(False)


# ---------------------------------------------------------------------------
# _check_for_changes — tracking gate
# ---------------------------------------------------------------------------


def test_check_for_changes_does_not_run_when_tracking_disabled():
    """_check_for_changes() must be a no-op when _tracking_enabled is False."""
    host = TestableChangeTracker()
    _attach_all_widgets(host)
    host._tracking_enabled = False

    # _update_save_button_style must not be called
    with patch.object(host, "_update_save_button_style") as mock_update:
        host._check_for_changes()

    mock_update.assert_not_called()


def test_check_for_changes_does_not_run_when_original_values_empty():
    """_check_for_changes() must be a no-op when _original_values is empty."""
    host = TestableChangeTracker()
    _attach_all_widgets(host)
    host._original_values = {}  # No baseline captured yet

    with patch.object(host, "_update_save_button_style") as mock_update:
        host._check_for_changes()

    mock_update.assert_not_called()


def test_check_for_changes_detects_no_changes():
    """_check_for_changes() must disable Save when values match originals."""
    host = TestableChangeTracker()
    _attach_all_widgets(host)

    # Capture baseline
    host._capture_original_values()

    with patch.object(host, "_update_save_button_style") as mock_update:
        host._check_for_changes()

    # After capturing and immediately checking, there should be no changes
    mock_update.assert_called_with(False)
