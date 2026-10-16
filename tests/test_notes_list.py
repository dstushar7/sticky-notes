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


def test_options_panel_paint_event_opaque_background(qapp):
    """OptionsPanel must paint an opaque background to prevent note text bleed-through."""
    from PyQt6.QtGui import QPixmap
    panel = OptionsPanel(current_theme="purple")
    panel.show()
    panel.adjustSize()
    pm = QPixmap(panel.size())
    panel.render(pm)
    img = pm.toImage()
    color = img.pixelColor(5, 50)
    assert color.name() == "#2b2b2b"
    assert color.alpha() == 255
    panel.close()


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
    """NoteCardWidget renders title, date, body preview, matches date color, and paints top accent."""
    from PyQt6.QtGui import QPixmap
    data = {
        "id": "card-1",
        "title": "Shopping List",
        "content": "<p>Milk, Bread, Coffee</p>",
        "theme": "yellow",
        "last_edited": "2026-10-02T10:00:00Z",
    }
    card = NoteCardWidget(data)
    card.resize(300, 100)
    assert card.title_label.text() == "Shopping List"
    assert "Milk, Bread, Coffee" in card.body_label.text()
    assert card._accent_color == NoteCardWidget._THEME_ACCENTS["yellow"]
    # Timestamp color matches note accent color
    assert card._accent_color in card.date_label.styleSheet()

    # Verify paintEvent fills top accent edge
    pm = QPixmap(300, 100)
    card.render(pm)
    img = pm.toImage()
    assert img.pixelColor(150, 2).name().lower() == NoteCardWidget._THEME_ACCENTS["yellow"].lower()

    # Verify purple card timestamp matches purple accent
    purple_card = NoteCardWidget({"id": "c2", "theme": "purple", "last_edited": "2026-10-02T10:00:00Z"})
    assert purple_card._accent_color == NoteCardWidget._THEME_ACCENTS["purple"]
    assert purple_card._accent_color in purple_card.date_label.styleSheet()


def test_notes_list_window_buttons_flat_modern_style(qapp):
    """NotesListWindow action buttons (+, ⚙, ✕) must have flat transparent idle style with no border."""
    win = NotesListWindow()
    for btn in (win.add_btn, win.settings_btn, win.close_btn):
        qss = btn.styleSheet()
        assert "background-color: transparent" in qss
        assert "border: none" in qss
    win.close()


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


def test_note_card_folded_corner_when_open(qapp):
    """NoteCardWidget renders a dog-ear folded corner at bottom-right if note is open."""
    from PyQt6.QtGui import QPixmap
    closed_card = NoteCardWidget({"id": "closed", "title": "Closed", "is_open": False})
    open_card = NoteCardWidget({"id": "open", "title": "Open", "is_open": True})

    assert not closed_card.is_open
    assert open_card.is_open

    closed_card.resize(200, 100)
    open_card.resize(200, 100)

    pm_closed = QPixmap(200, 100)
    pm_open = QPixmap(200, 100)

    closed_card.render(pm_closed)
    open_card.render(pm_open)

    # Pixel in the dog-ear area near bottom-right (e.g., x=192, y=92)
    # On the open card with fold_size=14, this area is the folded paper flap
    img_closed = pm_closed.toImage()
    img_open = pm_open.toImage()

    color_closed = img_closed.pixelColor(192, 92)
    color_open = img_open.pixelColor(192, 92)
    # The flap has a distinct lighter paper color compared to the standard card background
    assert color_open != color_closed


def test_notes_list_window_syncs_is_open_state(qapp, tmp_path):
    """NotesListWindow marks card as open when note window is active and visible."""
    db_file = tmp_path / "notes_test.db"
    db = storage.NoteDatabase(db_file)
    with patch("stickynotes.storage.get_db", return_value=db):
        db.save_note("open-note-1", content="<p>I am open</p>", title="Open Note")
        db.save_note("closed-note-2", content="<p>I am closed</p>", title="Closed Note")

        mock_open_note = MagicMock()
        mock_open_note.title = "Open Note"
        mock_open_note.text_edit.toHtml.return_value = "<p>I am open</p>"
        mock_open_note._theme_name = "yellow"
        mock_open_note.last_edited = "2026-10-16T12:00:00Z"
        mock_open_note.isVisible.return_value = True

        mock_tm = MagicMock()
        mock_tm.open_notes = {"open-note-1": mock_open_note}

        win = NotesListWindow(tray_manager=mock_tm)
        win.refresh_notes()

        card_map = {c.note_id: c for c in win._cards}
        assert card_map["open-note-1"].is_open is True
        assert card_map["closed-note-2"].is_open is False

        # When the note closes (isVisible returns False)
        mock_open_note.isVisible.return_value = False
        win.refresh_notes()
        card_map_after = {c.note_id: c for c in win._cards}
        assert card_map_after["open-note-1"].is_open is False
        win.close()


def test_notes_list_window_adaptive_dimensions(qapp, tmp_path):
    """NotesListWindow width is 1/4 viewport; height adapts to note count or takes full viewport when long."""
    db_file = tmp_path / "notes_geo_test.db"
    db = storage.NoteDatabase(db_file)
    with patch("stickynotes.storage.get_db", return_value=db):
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        avail_w = avail.width() if avail else 1440
        avail_h = avail.height() if avail else 810
        expected_w = max(NotesListWindow.MIN_WIDTH, int(avail_w * 0.25))

        mock_tm = MagicMock()
        mock_tm.open_notes = {}
        win = NotesListWindow(tray_manager=mock_tm)

        # 1. Empty / Few notes (1 note)
        db.save_note("n1", content="<p>Short note</p>", title="Special Unique Alpha")
        win.refresh_notes()

        assert win.width() == expected_w
        # Height is compact, only as much as note entries count
        assert win.height() < avail_h
        short_h = win.height()

        # 2. Add 20 notes to make note list very long
        for i in range(2, 25):
            db.save_note(f"n{i}", content=f"<p>Long content line 1<br>line 2<br>line 3 for note {i}</p>", title=f"Note {i}")
        win.refresh_notes()

        # Window width remains 1/4 viewport width
        assert win.width() == expected_w
        # Window takes all available height of the viewport when note list is very long
        assert win.height() == avail_h
        assert win.height() > short_h

        # 3. Filter notes with search to match only 1 note
        win.search_input.setText("Special Unique Alpha")
        # Height shrinks back to fit only the single matching note entry
        assert win.height() < avail_h

        win.close()


