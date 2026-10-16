import os
import pytest
from PyQt6.QtCore import QByteArray, QSettings
from stickynotes.storage import NoteDatabase


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_notes.db"
    db = NoteDatabase(db_file)
    yield db
    db.close()


def test_save_and_retrieve_note(temp_db):
    """Test inserting a new note and retrieving it by ID."""
    temp_db.save_note(
        note_id="note-1",
        content="<p>Test note content</p>",
        geometry=QByteArray(b"fake_geometry"),
        theme="blue",
        collapsed=False,
        title="My Test Note",
        last_edited="2026-10-16T12:00:00Z",
        pinned=True,
    )

    note = temp_db.get_note("note-1")
    assert note is not None
    assert note["id"] == "note-1"
    assert note["content"] == "<p>Test note content</p>"
    assert note["geometry"] == b"fake_geometry"
    assert note["theme"] == "blue"
    assert note["collapsed"] is False
    assert note["title"] == "My Test Note"
    assert note["last_edited"] == "2026-10-16T12:00:00Z"
    assert note["pinned"] is True


def test_upsert_note_updates_in_place(temp_db):
    """Test updating an existing note updates its fields without creating duplicates."""
    temp_db.save_note(note_id="note-2", content="Initial", theme="yellow")
    assert temp_db.count_notes() == 1

    temp_db.save_note(note_id="note-2", content="Updated Content", theme="green", title="Updated")
    assert temp_db.count_notes() == 1

    note = temp_db.get_note("note-2")
    assert note["content"] == "Updated Content"
    assert note["theme"] == "green"
    assert note["title"] == "Updated"


def test_delete_note(temp_db):
    """Test deleting a note removes it from database."""
    temp_db.save_note(note_id="to-delete", content="Delete me")
    assert temp_db.get_note("to-delete") is not None

    temp_db.delete_note("to-delete")
    assert temp_db.get_note("to-delete") is None
    assert temp_db.count_notes() == 0


def test_get_all_notes_ordering(temp_db):
    """Test get_all_notes returns notes ordered by last_edited descending."""
    temp_db.save_note(note_id="older", content="Older", last_edited="2026-10-10T10:00:00Z")
    temp_db.save_note(note_id="newer", content="Newer", last_edited="2026-10-16T10:00:00Z")

    all_notes = temp_db.get_all_notes()
    assert len(all_notes) == 2
    assert all_notes[0]["id"] == "newer"
    assert all_notes[1]["id"] == "older"


def test_migrate_from_qsettings(tmp_path):
    """Test seamless migration of legacy QSettings notes into an empty SQLite database."""
    conf_file = tmp_path / "test_config.ini"
    settings = QSettings(str(conf_file), QSettings.Format.IniFormat)

    # Populate mock legacy notes in QSettings
    settings.beginGroup("notes")
    settings.setValue("legacy-1/content", "<h1>Legacy Note 1</h1>")
    settings.setValue("legacy-1/title", "Legacy 1")
    settings.setValue("legacy-1/theme", "pink")
    settings.setValue("legacy-1/collapsed", True)
    settings.setValue("legacy-1/pinned", False)
    settings.setValue("legacy-1/last_edited", "2026-09-01T00:00:00Z")
    settings.endGroup()
    settings.sync()

    db_file = tmp_path / "migrated_notes.db"
    db = NoteDatabase(db_file)

    # Migrate
    count = db.migrate_from_qsettings(settings)
    assert count == 1
    assert db.count_notes() == 1

    migrated = db.get_note("legacy-1")
    assert migrated["content"] == "<h1>Legacy Note 1</h1>"
    assert migrated["title"] == "Legacy 1"
    assert migrated["theme"] == "pink"
    assert migrated["collapsed"] is True

    # Running migration again on non-empty DB should be a no-op
    assert db.migrate_from_qsettings(settings) == 0
    db.close()
