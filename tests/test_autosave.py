import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Force offscreen platform for headless Qt tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSettings
from stickynotes.note_window import StickyNote
from stickynotes import config


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_restored_note_is_not_dirty_initially(qapp):
    """A restored note loaded from disk should start clean (_is_dirty=False)."""
    note = StickyNote(note_id="test-restored-id", content="Hello World")
    assert note._is_dirty is False
    note.close()


def test_new_note_is_dirty_initially(qapp):
    """A brand new note without note_id should start dirty so it persists."""
    note = StickyNote(note_id=None, content="")
    assert note._is_dirty is True
    note.close()


def test_idle_autosave_tick_does_not_save(qapp):
    """When _is_dirty is False, _autosave_tick should not perform any disk save."""
    note = StickyNote(note_id="test-idle-id", content="Existing Note")
    assert note._is_dirty is False

    with patch.object(note, "_save") as mock_save:
        note._autosave_tick()
        mock_save.assert_not_called()
    note.close()


def test_body_change_marks_dirty_and_starts_debounce(qapp):
    """Typing in the body should set _is_dirty=True and trigger debounce timer."""
    note = StickyNote(note_id="test-edit-id", content="Original")
    assert note._is_dirty is False

    # Simulate user typing
    note.text_edit.setPlainText("Updated text by user")
    assert note._is_dirty is True
    assert note._save_debounce.isActive()
    note.close()


def test_save_clears_dirty_flag(qapp):
    """Calling _save() should write to settings and reset _is_dirty to False."""
    note = StickyNote(note_id="test-save-id", content="Some text")
    note._mark_dirty()
    assert note._is_dirty is True

    note._save()
    assert note._is_dirty is False
    note.close()


def test_collapse_and_expand_mark_dirty(qapp):
    """Collapsing and expanding the note window should mark it as dirty."""
    note = StickyNote(note_id="test-collapse-id", content="Notes")
    note._is_dirty = False

    note._collapse()
    assert note._is_dirty is True

    note._is_dirty = False
    note._expand()
    assert note._is_dirty is True
    note.close()


def test_save_force_flag(qapp):
    """_save(force=True) should save even when _is_dirty is False (e.g. app shutdown)."""
    note = StickyNote(note_id="test-force-id", content="Persistent")
    assert note._is_dirty is False

    from stickynotes import storage
    with patch.object(storage.get_db(), "save_note") as mock_save_note:
        # Normal save while clean: no-op
        note._save(force=False)
        mock_save_note.assert_not_called()

        # Force save while clean: executes save
        note._save(force=True)
        mock_save_note.assert_called_once()
    note.close()
