# tests/test_unfocused_bars.py
import os
import pytest
from unittest.mock import patch, MagicMock

# Force offscreen platform for headless Qt tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QEvent
from PyQt6.QtGui import QMouseEvent
from stickynotes.note_window import StickyNote, TitleBar, FormatBar
from stickynotes import config


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_title_bar_set_focused(qapp):
    """TitleBar should shrink to thin accent stripe when unfocused and restore when focused."""
    tb = TitleBar()
    tb.show()
    assert tb.height() == config.TITLE_BAR_HEIGHT
    assert tb.add_btn.isVisible()
    assert tb.close_btn.isVisible()

    tb.set_focused(False)
    assert tb.height() == config.TITLE_BAR_UNFOCUSED_HEIGHT
    assert not tb.add_btn.isVisible()
    assert not tb.drag_handle.isVisible()
    assert not tb.pin_btn.isVisible()
    assert not tb.opts_btn.isVisible()
    assert not tb.close_btn.isVisible()

    tb.set_focused(True)
    assert tb.height() == config.TITLE_BAR_HEIGHT
    assert tb.add_btn.isVisible()
    assert tb.drag_handle.isVisible()
    assert tb.pin_btn.isVisible()
    assert tb.opts_btn.isVisible()
    assert tb.close_btn.isVisible()
    tb.close()


def test_restored_note_starts_unfocused(qapp):
    """An existing note loaded with note_id should start unfocused with hidden bars."""
    note = StickyNote(note_id="saved-note-1", content="Sample content")
    note.show()
    assert note.is_focused() is False
    assert note.title_bar.height() == config.TITLE_BAR_UNFOCUSED_HEIGHT
    assert not note.format_bar.isVisible()
    assert not note.title_bar.add_btn.isVisible()
    assert not note.title_bar.close_btn.isVisible()
    note.close()


def test_new_note_starts_focused(qapp):
    """A brand-new note (note_id=None) should start focused so user can edit immediately."""
    note = StickyNote(note_id=None, content="")
    note.show()
    assert note.is_focused() is True
    assert note.title_bar.height() == config.TITLE_BAR_HEIGHT
    assert note.format_bar.isVisible()
    note.close()


def test_focus_toggle_bars_visibility(qapp):
    """Calling set_focused toggles top bar height and format bar visibility."""
    note = StickyNote(note_id="test-toggle-id", content="Test note")
    note.show()

    # Initially unfocused
    assert not note.is_focused()
    assert not note.format_bar.isVisible()
    assert note.title_bar.height() == config.TITLE_BAR_UNFOCUSED_HEIGHT

    # Focus note
    note.set_focused(True)
    assert note.is_focused() is True
    assert note.format_bar.isVisible()
    assert note.title_bar.height() == config.TITLE_BAR_HEIGHT

    # Unfocus note
    note.set_focused(False)
    assert note.is_focused() is False
    assert not note.format_bar.isVisible()
    assert note.title_bar.height() == config.TITLE_BAR_UNFOCUSED_HEIGHT
    note.close()


def test_click_inside_focuses_unfocused_note(qapp):
    """Clicking inside the text edit or window should focus the note and show bars."""
    note = StickyNote(note_id="test-click-id", content="First line\nSecond line")
    note.show()
    assert not note.is_focused()

    # Simulate mouse press event on text_edit
    pos = QPoint(20, 20)
    gpos = note.text_edit.mapToGlobal(pos)
    ev = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        pos.toPointF(),
        gpos.toPointF(),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    # Deliver through eventFilter
    note.eventFilter(note.text_edit, ev)

    assert note.is_focused() is True
    assert note.format_bar.isVisible()
    assert note.title_bar.height() == config.TITLE_BAR_HEIGHT
    note.close()


def test_click_top_stripe_allows_drag(qapp):
    """Clicking and dragging the thin top stripe when unfocused starts drag and focuses."""
    note = StickyNote(note_id="test-drag-id", content="Note drag test")
    note.show()
    assert not note.is_focused()

    gpos = note.mapToGlobal(QPoint(50, 2))
    # _try_start_drag on self.title_bar should be accepted
    with patch.object(note, "windowHandle", return_value=None):
        can_drag = note._try_start_drag(gpos, note.title_bar)
        assert can_drag is True
        assert note._is_dragging is True
    note.close()


def test_collapsed_note_keeps_title_bar(qapp):
    """When a note is collapsed, title bar remains in pill shape and does not collapse to 6px."""
    note = StickyNote(note_id="test-collapsed-id", content="Body text")
    note._collapse_immediately()
    assert note._is_collapsed is True

    # Attempting to unfocus shouldn't collapse the title bar to 6px
    note.set_focused(False)
    assert note.title_bar.height() == config.TITLE_BAR_HEIGHT
    note.close()
