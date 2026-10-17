import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtGui import QTextCursor, QTextFormat, QTextListFormat
from PyQt6.QtWidgets import QApplication

from stickynotes.note_window import NoteTextEdit, StickyNote


def _app():
    return QApplication.instance() or QApplication([])


def test_new_list_hides_qt_marker_for_custom_alignment(qapp):
    note = StickyNote(note_id="marker-alignment-new")
    note.text_edit.setPlainText("မြန်မာ English")
    note._toggle_bullet_list()

    text_list = note.text_edit.document().firstBlock().textList()
    assert text_list is not None
    assert text_list.format().intProperty(QTextFormat.Property.ListStyle) == 0


def test_pasted_list_hides_qt_marker_for_custom_alignment(qapp):
    edit = NoteTextEdit()
    edit.document().setHtml("<ul><li>မြန်မာ English</li></ul>")
    edit.hide_native_list_markers()

    text_list = edit.document().firstBlock().textList()
    assert text_list is not None
    assert text_list.format().intProperty(QTextFormat.Property.ListStyle) == 0


def test_custom_marker_uses_the_actual_myanmar_line_box(qapp):
    edit = NoteTextEdit()
    edit.resize(400, 160)
    edit.setPlainText("မြန်မာ English")
    cursor = edit.textCursor()
    list_format = QTextListFormat()
    list_format.setIndent(1)
    list_format.setProperty(QTextFormat.Property.ListStyle, 0)
    cursor.createList(list_format)
    edit.show()
    qapp.processEvents()

    block = edit.document().firstBlock()
    line = block.layout().lineAt(0)
    marker_center = edit.cursorRect(QTextCursor(block)).top() + line.naturalTextRect().center().y()

    # Myanmar makes this line taller than the editor's Latin default.  A
    # marker centred in that real glyph box cannot be pinned to its top.
    assert marker_center > edit.cursorRect(QTextCursor(block)).top() + 10
