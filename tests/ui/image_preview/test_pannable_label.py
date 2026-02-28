"""
Tests for PannableImageLabel in ui.image_preview.pannable_label.

Covers:
- mouseMoveEvent emits pan_changed signal when panning
- pan_changed signal is connected and fires correctly
- reset_pan / get_pan_offset / set_pan_offset state management
- Parent widget walk (documents current implementation behavior)
"""

from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


# ---------------------------------------------------------------------------
# Helper: fake mouse event
# ---------------------------------------------------------------------------


def _fake_mouse_event(pos_x, pos_y, button=Qt.MouseButton.LeftButton):
    """Create a minimal mock for a QMouseEvent."""
    event = MagicMock()
    event.button.return_value = button
    event.pos.return_value = QPoint(pos_x, pos_y)
    event.accept = MagicMock()
    return event


# ---------------------------------------------------------------------------
# Basic construction
# ---------------------------------------------------------------------------


def test_pannable_label_initializes_with_zero_pan(qapp):
    """PannableImageLabel should start with a zero pan offset."""
    from ui.image_preview.pannable_label import PannableImageLabel

    label = PannableImageLabel()
    assert label.get_pan_offset() == QPoint(0, 0)


def test_pannable_label_is_not_panning_initially(qapp):
    """is_panning should be False before any mouse interaction."""
    from ui.image_preview.pannable_label import PannableImageLabel

    label = PannableImageLabel()
    assert label.is_panning is False


# ---------------------------------------------------------------------------
# mouseMoveEvent — signal emission
# ---------------------------------------------------------------------------


def test_mouse_move_emits_pan_changed_signal(qapp):
    """pan_changed must be emitted when the mouse is dragged while panning."""
    from ui.image_preview.pannable_label import PannableImageLabel

    label = PannableImageLabel()

    received = []
    label.pan_changed.connect(lambda: received.append(True))

    # Simulate starting a pan drag
    press_event = _fake_mouse_event(10, 10)
    label.mousePressEvent(press_event)
    assert label.is_panning is True

    # Now move — pan_changed should fire
    move_event = _fake_mouse_event(20, 20)
    label.mouseMoveEvent(move_event)

    assert len(received) == 1, "pan_changed must be emitted once per drag step"


def test_mouse_move_updates_pan_offset(qapp):
    """After a drag, the pan_offset should reflect the delta."""
    from ui.image_preview.pannable_label import PannableImageLabel

    label = PannableImageLabel()

    press_event = _fake_mouse_event(10, 10)
    label.mousePressEvent(press_event)

    move_event = _fake_mouse_event(15, 20)
    label.mouseMoveEvent(move_event)

    offset = label.get_pan_offset()
    assert offset.x() == 5
    assert offset.y() == 10


def test_mouse_move_does_not_emit_when_not_panning(qapp):
    """pan_changed should NOT be emitted when is_panning is False."""
    from ui.image_preview.pannable_label import PannableImageLabel

    label = PannableImageLabel()
    assert label.is_panning is False

    signals_received = []
    label.pan_changed.connect(lambda: signals_received.append(True))

    # Create a minimal fake event that won't crash when passed to super().mouseMoveEvent
    # We simulate a mouse move when is_panning=False; the signal should NOT fire.
    # Patch super().mouseMoveEvent to avoid requiring a real QMouseEvent object.
    with patch.object(type(label).__bases__[0], "mouseMoveEvent", return_value=None):
        move_event = _fake_mouse_event(20, 20, button=Qt.MouseButton.NoButton)
        label.mouseMoveEvent(move_event)

    assert len(signals_received) == 0


# ---------------------------------------------------------------------------
# mouseMoveEvent — signal is emitted on drag
# ---------------------------------------------------------------------------


def test_pan_handler_emits_pan_changed_signal_on_drag(qapp):
    """
    mouseMoveEvent emits pan_changed to notify connected slots.
    This is the primary signal-based notification path.
    """
    from ui.image_preview.pannable_label import PannableImageLabel

    label = PannableImageLabel()

    received = []
    label.pan_changed.connect(lambda: received.append(True))

    press_event = _fake_mouse_event(10, 10)
    label.mousePressEvent(press_event)

    move_event = _fake_mouse_event(20, 20)
    label.mouseMoveEvent(move_event)

    assert len(received) == 1, "pan_changed must be emitted once per drag step"


def test_pan_handler_does_not_call_parent_update_image_preview(qapp):
    """
    The parent-walking loop that called _update_image_preview() has been removed.
    mouseMoveEvent now ONLY emits pan_changed; consumers connect to the signal.

    Verify that even when a real parent widget provides _update_image_preview(),
    it is NOT called directly during a drag — only the signal fires.
    """
    from PyQt6.QtWidgets import QWidget

    from ui.image_preview.pannable_label import PannableImageLabel

    # Create a real parent widget that has _update_image_preview
    parent_widget = QWidget()
    call_log = []
    parent_widget._update_image_preview = lambda: call_log.append(True)

    label = PannableImageLabel(parent_widget)

    received_signal = []
    label.pan_changed.connect(lambda: received_signal.append(True))

    press_event = _fake_mouse_event(10, 10)
    label.mousePressEvent(press_event)

    move_event = _fake_mouse_event(20, 20)
    label.mouseMoveEvent(move_event)

    # pan_changed signal must fire
    assert len(received_signal) == 1, "pan_changed must be emitted"
    # _update_image_preview must NOT be called directly (parent walk removed)
    assert len(call_log) == 0, "_update_image_preview must NOT be called directly"


# ---------------------------------------------------------------------------
# reset_pan / set_pan_offset
# ---------------------------------------------------------------------------


def test_reset_pan_returns_offset_to_zero(qapp):
    """reset_pan() must zero out the pan_offset."""
    from ui.image_preview.pannable_label import PannableImageLabel

    label = PannableImageLabel()
    label.set_pan_offset(QPoint(50, 100))
    assert label.get_pan_offset() != QPoint(0, 0)

    label.reset_pan()
    assert label.get_pan_offset() == QPoint(0, 0)


def test_set_pan_offset_stores_value(qapp):
    """set_pan_offset() must store the given offset, retrievable by get_pan_offset()."""
    from ui.image_preview.pannable_label import PannableImageLabel

    label = PannableImageLabel()
    label.set_pan_offset(QPoint(30, 40))
    offset = label.get_pan_offset()
    assert offset.x() == 30
    assert offset.y() == 40


# ---------------------------------------------------------------------------
# mouseReleaseEvent — ends panning
# ---------------------------------------------------------------------------


def test_mouse_release_ends_panning(qapp):
    """mouseReleaseEvent must set is_panning to False."""
    from ui.image_preview.pannable_label import PannableImageLabel

    label = PannableImageLabel()

    press_event = _fake_mouse_event(10, 10)
    label.mousePressEvent(press_event)
    assert label.is_panning is True

    release_event = _fake_mouse_event(10, 10)
    label.mouseReleaseEvent(release_event)
    assert label.is_panning is False


# ---------------------------------------------------------------------------
# zoom_requested signal
# ---------------------------------------------------------------------------


def test_wheel_event_emits_zoom_requested(qapp):
    """Scrolling the wheel should emit zoom_requested with a non-zero step."""
    from PyQt6.QtCore import QPoint
    from PyQt6.QtGui import QWheelEvent

    from ui.image_preview.pannable_label import PannableImageLabel

    label = PannableImageLabel()

    received = []
    label.zoom_requested.connect(lambda v: received.append(v))

    # Build a synthetic wheel event with positive delta (scroll up = zoom in)
    wheel_event = MagicMock(spec=QWheelEvent)
    wheel_event.angleDelta.return_value = QPoint(0, 120)  # 1 step up
    wheel_event.accept = MagicMock()

    label.wheelEvent(wheel_event)

    assert len(received) == 1
    assert received[0] > 0  # Scrolling up should zoom in (positive)
