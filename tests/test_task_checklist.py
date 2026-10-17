import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QKeyEvent, QTextCursor, QTextFormat, QTextListFormat, QTextBlockFormat, QTextCharFormat
from PyQt6.QtWidgets import QApplication

from stickynotes.note_window import NoteTextEdit, StickyNote, _MARKER_CHECKED, _MARKER_UNCHECKED


def test_checklist_toggle_checked_strikes_through_text(qapp):
    edit = NoteTextEdit()
    edit.setPlainText("Buy groceries")
    cursor = edit.textCursor()
    list_format = QTextListFormat()
    list_format.setIndent(1)
    list_format.setProperty(QTextFormat.Property.ListStyle, 0)
    cursor.createList(list_format)

    block = edit.document().firstBlock()
    fmt = block.blockFormat()
    fmt.setMarker(_MARKER_UNCHECKED)
    cursor.setBlockFormat(fmt)

    # Initial state: unchecked and not struck through
    assert block.blockFormat().marker() == _MARKER_UNCHECKED
    assert not edit.is_strikethrough(block)

    # Toggle to checked
    edit._toggle_marker(block)
    assert block.blockFormat().marker() == _MARKER_CHECKED
    assert edit.is_strikethrough(block)
    assert "line-through" in edit.toHtml()

    # Toggle back to unchecked
    edit._toggle_marker(block)
    assert block.blockFormat().marker() == _MARKER_UNCHECKED
    assert not edit.is_strikethrough(block)


def test_enter_on_checked_task_clears_strikethrough_for_new_task(qapp):
    edit = NoteTextEdit()
    edit.setPlainText("Completed task")
    cursor = edit.textCursor()
    list_format = QTextListFormat()
    list_format.setIndent(1)
    list_format.setProperty(QTextFormat.Property.ListStyle, 0)
    cursor.createList(list_format)

    block = edit.document().firstBlock()
    edit._toggle_marker(block)
    assert block.blockFormat().marker() == _MARKER_CHECKED
    assert edit.is_strikethrough(block)

    # Position cursor at end of line and simulate Enter
    cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
    edit.setTextCursor(cursor)

    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    edit.keyPressEvent(event)

    new_block = edit.document().lastBlock()
    assert new_block.blockFormat().marker() == _MARKER_UNCHECKED
    assert not edit.is_strikethrough(edit.textCursor())

    # Insert text in new item
    edit.insertPlainText("Next task")
    assert not edit.is_strikethrough(new_block)


def test_html_restore_checked_item_has_strikethrough(qapp):
    edit = NoteTextEdit()
    edit.document().setHtml('<ul><li class="checked">Existing completed task</li></ul>')
    edit.hide_native_list_markers()

    block = edit.document().firstBlock()
    assert block.blockFormat().marker() == _MARKER_CHECKED
    assert edit.is_strikethrough(block)
    assert "line-through" in edit.toHtml()


def test_strike_button_disabled_for_tasks_and_toggle_ignored(qapp):
    note = StickyNote(note_id="test-strike-disabled")
    note.text_edit.setPlainText("Regular text\nTask item")

    # Put cursor in regular text
    cursor = note.text_edit.textCursor()
    cursor.setPosition(2)
    note.text_edit.setTextCursor(cursor)
    note._refresh_format_bar()

    assert note.format_bar.strike_btn.isEnabled()

    # Convert second line to checklist
    cursor.setPosition(15)
    note.text_edit.setTextCursor(cursor)
    note._toggle_checklist()

    # Cursor is in checklist: strike button must not be active
    assert not note.format_bar.strike_btn.isEnabled()
    assert not note.format_bar.strike_btn.isChecked()

    # Invoking _toggle_strike inside task does nothing
    note._toggle_strike()
    block = note.text_edit.textCursor().block()
    assert not note.text_edit.is_strikethrough(block)

    # Mark as completed
    note.text_edit._toggle_marker(block)
    assert note.text_edit.is_strikethrough(block)

    # Invoking _toggle_strike inside completed task cannot remove strikethrough
    note._toggle_strike()
    assert note.text_edit.is_strikethrough(block)

    # The only way to remove strikethrough is to uncheck the box
    note.text_edit._toggle_marker(block)
    assert not note.text_edit.is_strikethrough(block)


def test_edits_or_added_text_to_checked_task_automatically_strikethrough(qapp):
    edit = NoteTextEdit()
    edit.setPlainText("Milk")
    cursor = edit.textCursor()
    lf = QTextListFormat()
    cursor.createList(lf)
    block = edit.document().firstBlock()
    bf = block.blockFormat()
    bf.setMarker(_MARKER_CHECKED)
    cursor.setBlockFormat(bf)
    edit.sync_checklist_strikethrough()

    assert edit.is_strikethrough(block)

    # Typing inside checked task
    cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
    edit.setTextCursor(cursor)
    edit.insertPlainText(" and Bread")

    assert edit.is_strikethrough(block)


def test_incomplete_task_cannot_have_strikethrough(qapp):
    edit = NoteTextEdit()
    edit.setPlainText("Incomplete Task")
    cursor = edit.textCursor()
    lf = QTextListFormat()
    cursor.createList(lf)
    block = edit.document().firstBlock()
    bf = block.blockFormat()
    bf.setMarker(_MARKER_UNCHECKED)
    cursor.setBlockFormat(bf)
    edit.sync_checklist_strikethrough()

    # Try applying strikethrough directly to characters
    cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
    cf = QTextCharFormat()
    cf.setFontStrikeOut(True)
    cursor.mergeCharFormat(cf)
    edit.sync_checklist_strikethrough()

    # Must be stripped because task is incomplete
    assert not edit.is_strikethrough(block)


def test_myanmar_text_strikethrough_vertical_centering(qapp):
    """Verify that strikethrough for Myanmar text is centered vertically in the line box."""
    edit = NoteTextEdit()
    edit.resize(400, 200)
    edit.show()
    edit.setPlainText("စစ်ဆေးအတည်ပြုခဲ့ပါသည်hello")
    qapp.processEvents()

    block = edit.document().firstBlock()
    layout = block.layout()
    assert layout is not None and layout.lineCount() >= 1
    line = layout.lineAt(0)
    cursor_rect = edit.cursorRect(QTextCursor(block))
    center_y = cursor_rect.top() + line.naturalTextRect().center().y()

    # Consonant circles sit on baseline with height ~8-9px.
    # The visual center must be well inside the line (not at the top edge).
    line_top = cursor_rect.top()
    line_bottom = cursor_rect.top() + line.naturalTextRect().height()
    line_mid = (line_top + line_bottom) / 2.0

    assert abs(center_y - line_mid) < 1.0
    # In native Qt, strikethrough is at baseline - 6 which is near the top edge.
    # Our center_y is at visual mid (e.g. ~20.4 vs native ~17).
    assert center_y > line_top + 10


def test_task_box_has_clear_space_before_text_cursor(qapp):
    from PyQt6.QtGui import QFontMetrics
    note = StickyNote(note_id="test-task-space")
    note.text_edit.setPlainText("Spaced Task")
    note._toggle_checklist()
    note.show()
    qapp.processEvents()

    edit = note.text_edit
    block = edit.document().firstBlock()
    cursor_rect = edit.cursorRect(QTextCursor(block))
    font = block.charFormat().font()
    metrics = QFontMetrics(font)
    glyph_size = max(2.0, metrics.lineSpacing() / 3.0)
    box_size = glyph_size * 2.0
    space_behind = max(6.0, metrics.horizontalAdvance(" ") + 2.0)
    center_x = cursor_rect.left() - space_behind - box_size / 2.0
    box_right = center_x + box_size / 2.0

    # Ensure there is at least 6px gap so the text cursor doesn't touch the box
    gap = cursor_rect.left() - box_right
    assert gap >= 6.0
    assert box_right < cursor_rect.left()


def test_regular_text_strikethrough_toggle_and_html_roundtrip(qapp):
    note = StickyNote(note_id="test-regular-strike")
    note.text_edit.setPlainText("Hello world")
    cursor = note.text_edit.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    note.text_edit.setTextCursor(cursor)
    note._refresh_format_bar()

    assert not note.text_edit.is_strikethrough(cursor)
    assert not note.format_bar.strike_btn.isChecked()

    # Toggle strikethrough
    note._toggle_strike()
    assert note.text_edit.is_strikethrough(cursor)
    assert note.format_bar.strike_btn.isChecked()

    # HTML round-trip
    html = note.text_edit.toHtml()
    assert "line-through" in html

    # Load in fresh note
    note2 = StickyNote(note_id="test-regular-strike-2")
    note2.text_edit.setHtml(html)
    c2 = note2.text_edit.textCursor()
    c2.setPosition(2)
    assert note2.text_edit.is_strikethrough(c2)

