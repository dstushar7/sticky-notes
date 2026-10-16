# tests/test_notes_list.py
import os
import pytest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from stickynotes.note_window import StickyNote, OptionsPanel
from stickynotes.notes_list import NotesListWindow, NoteCardWidget, format_note_date, get_plain_snippet
from stickynotes import storage, config, utils


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_options_panel_has_notes_list_button(qapp):
    """OptionsPanel must include a 'Notes list' button that emits notesListRequested."""
    panel = OptionsPanel(current_theme="yellow")
    assert hasattr(panel, "notes_list_btn")
    assert "Notes list" in panel.notes_list_btn.text()

    mock_slot = MagicMock()
    panel.notesListRequested.connect(mock_slot)

    panel.notes_list_btn.click()
    mock_slot.assert_called_once()


def test_sticky_note_forwards_notes_list_requested(qapp):
    """StickyNote must forward notesListRequested from OptionsPanel."""
    note = StickyNote(note_id="test-note-list-id", content="Test note")
    mock_slot = MagicMock()
    note.notesListRequested.connect(mock_slot)

    note._show_options_panel()
    assert note._options_panel is not None
    note._options_panel.notes_list_btn.click()

    mock_slot.assert_called_once()
    note.close()


def test_format_note_date():
    """format_note_date formats ISO string to readable short date."""
    assert format_note_date(None) == ""
    assert format_note_date("") == ""
    # Test valid date
    formatted = format_note_date("2026-10-02T12:00:00+00:00")
    assert "Oct 2" in formatted or "Oct 02" in formatted


def test_get_plain_snippet():
    """get_plain_snippet strips HTML and collapses extra spaces/newlines."""
    html = "<p>First line</p><p><br></p><p>Second line</p>"
    snippet = get_plain_snippet(html)
    assert "First line" in snippet
    assert "Second line" in snippet
    assert "<p>" not in snippet


def test_note_card_widget_ui_and_accent(qapp):
    """NoteCardWidget renders title, date, body preview and applies top accent color."""
    data = {
        "id": "card-1",
        "title": "Shopping List",
        "content": "<p>Milk, Bread, Coffee</p>",
        "theme": "yellow",
        "last_edited": "2026-10-02T10:00:00Z",
    }
    card = NoteCardWidget(data)
    assert card.title_label.text() == "Shopping List"
    assert "Milk, Bread, Coffee" in card.body_label.text()
    assert card._accent_color == NoteCardWidget._THEME_ACCENTS["yellow"]
    assert f"border-top: 3px solid {card._accent_color}" in card.styleSheet()


def test_note_card_click_emits_open_requested(qapp):
    """Clicking NoteCardWidget emits openRequested with note_id."""
    data = {
        "id": "card-click-test",
        "title": "Click Test",
        "content": "<p>Testing click</p>",
        "theme": "blue",
        "last_edited": None,
    }
    card = NoteCardWidget(data)
    mock_slot = MagicMock()
    card.openRequested.connect(mock_slot)

    card.openRequested.emit(card.note_id)
    mock_slot.assert_called_once_with("card-click-test")


def test_notes_list_window_ui_elements(qapp, tmp_path):
    """NotesListWindow must have add_btn (+), settings_btn (⚙), close_btn (✕), and search bar."""
    db_file = tmp_path / "notes_test.db"
    db = storage.NoteDatabase(db_file)
    with patch("stickynotes.storage.get_db", return_value=db):
        db.save_note("n1", content="<p>Note one content</p>", title="Note 1", theme="yellow")
        db.save_note("n2", content="<p>Note two content</p>", title="Note 2", theme="pink")

        mock_tm = MagicMock()
        mock_tm.open_notes = {}
        win = NotesListWindow(tray_manager=mock_tm)
        win.show()
        win.refresh_notes()

        assert win.add_btn is not None
        assert win.settings_btn is not None
        assert win.close_btn is not None
        assert win.search_input is not None
        assert len(win._cards) == 2

        # Test search filter
        win.search_input.setText("two")
        assert not win._cards[0].isVisible()  # Note 1 hidden
        assert win._cards[1].isVisible()      # Note 2 visible

        # Clear search
        win.search_input.setText("")
        assert win._cards[0].isVisible()
        assert win._cards[1].isVisible()

        win.close()


def test_notes_list_window_add_and_settings_buttons(qapp):
    """Clicking + calls _create_new_note and ⚙ calls _show_settings on tray_manager."""
    mock_tm = MagicMock()
    mock_tm.open_notes = {}
    win = NotesListWindow(tray_manager=mock_tm)

    win.add_btn.click()
    mock_tm._create_new_note.assert_called_once()

    win.settings_btn.click()
    mock_tm._show_settings.assert_called_once()
    win.close()
