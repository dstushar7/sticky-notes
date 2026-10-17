# stickynotes/richtext.py
#
# Rich-text helpers shared by the note editor and Share/Receive. Kept free of
# widget code so sharing.py can use the sanitiser without importing the note
# window.

from PyQt6.QtGui import (
    QFont, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextDocument,
    QTextDocumentFragment, QTextFormat, QTextListFormat,
)


# Bullet styles cycled by sublist depth so nested levels are visually distinct.
_LIST_STYLES = (
    QTextListFormat.Style.ListDisc,
    QTextListFormat.Style.ListCircle,
    QTextListFormat.Style.ListSquare,
)

# QTextDocumentLayout draws built-in list glyphs with the block's default
# (usually Latin) font metrics, even when the line itself is taller because it
# contains a fallback-script glyph such as Myanmar.  The editor paints those
# glyphs itself, centred in the real line box, so keep Qt's marker hidden while
# preserving QTextList for editing, nesting and HTML round-tripping.
_HIDDEN_LIST_STYLE = 0


def hide_native_list_marker(list_format: QTextListFormat) -> None:
    """Keep a QTextList's layout/indentation but suppress Qt's list glyph."""
    list_format.setProperty(QTextFormat.Property.ListStyle, _HIDDEN_LIST_STYLE)


def style_for_indent(indent: int) -> QTextListFormat.Style:
    return _LIST_STYLES[(max(1, indent) - 1) % len(_LIST_STYLES)]


# ---------------------------------------------------------------------------
# Sanitising
#
# Rule: incoming rich text may only carry formatting the user could have
# typed. The format bar offers bold/italic/underline/strike, bullets and
# checklists — so that is all that survives. Font family and size, text and
# background colours, line-height, alignment, headings, links, images and
# tables are dropped, because once inserted there would be no way to remove
# them from inside the note (e.g. VS Code's dark editor background and
# monospace font).
#
# Applies to pastes (NoteTextEdit.insertFromMimeData) and to received shared
# notes (sharing.decode_note), so a shared note can never contain anything a
# paste couldn't.
#
# The HTML is REBUILT into a fresh document rather than stripped in place:
# only what is explicitly copied below gets through, so formats we never
# thought of (table cell backgrounds, frame borders, white-space: pre) can't
# leak in.
# ---------------------------------------------------------------------------
_OBJECT_REPLACEMENT_CHAR = "￼"   # stands in for images / inline objects
_NBSP = " "


# Custom strikethrough property used instead of native fontStrikeOut so
# strikethrough lines can be custom-painted at the visual vertical center
# across all languages/scripts (e.g. Myanmar and English).
_CUSTOM_STRIKE_PROP = QTextFormat.Property.UserProperty + 2


def _clean_char_format(src: QTextCharFormat) -> QTextCharFormat:
    fmt = QTextCharFormat()
    if src.fontWeight() >= QFont.Weight.DemiBold:
        fmt.setFontWeight(QFont.Weight.Bold)
    if src.fontItalic():
        fmt.setFontItalic(True)
    # Links are rendered underlined; once the link itself is dropped that
    # underline would just be a stray decoration.
    if src.fontUnderline() and not src.isAnchor():
        fmt.setFontUnderline(True)
    if src.fontStrikeOut() or src.boolProperty(_CUSTOM_STRIKE_PROP):
        fmt.setProperty(_CUSTOM_STRIKE_PROP, True)
    return fmt


def _rebuild(html: str) -> QTextDocument:
    """Rebuild `html` keeping only text, B/I/U/S, lists and checkboxes."""
    src = QTextDocument()
    src.setHtml(html)
    dst = QTextDocument()
    cursor = QTextCursor(dst)
    lists = {}   # source list objectIndex -> rebuilt QTextList

    block = src.begin()
    first = True
    while block.isValid():
        if not first:
            cursor.insertBlock(QTextBlockFormat(), QTextCharFormat())
        first = False

        src_list = block.textList()
        block_fmt = QTextBlockFormat()
        if src_list is not None:
            block_fmt.setMarker(block.blockFormat().marker())
        cursor.setBlockFormat(block_fmt)

        if src_list is not None:
            dst_list = lists.get(src_list.objectIndex())
            if dst_list is None:
                # Numbered and custom lists collapse to the same bullet
                # styles Tab-nesting uses, keyed off the nesting depth.
                indent = max(1, src_list.format().indent())
                list_fmt = QTextListFormat()
                list_fmt.setIndent(indent)
                hide_native_list_marker(list_fmt)
                lists[src_list.objectIndex()] = cursor.createList(list_fmt)
            else:
                dst_list.add(cursor.block())

        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid() and not frag.charFormat().isImageFormat():
                # Code from editors arrives as white-space: pre, which Qt
                # turns into non-breaking spaces — keep them and long lines
                # would refuse to wrap in a narrow note.
                text = (frag.text()
                        .replace(_OBJECT_REPLACEMENT_CHAR, "")
                        .replace(_NBSP, " "))
                if text:
                    cursor.insertText(text, _clean_char_format(frag.charFormat()))
            it += 1
        block = block.next()

    return dst


def doc_to_html_with_strikethrough(doc: QTextDocument) -> str:
    """Export document to HTML with standard text-decoration: line-through.
    
    Clones the document and promotes _CUSTOM_STRIKE_PROP and checked checklist
    blocks to standard fontStrikeOut so exported HTML preserves strikethrough.
    """
    clone = doc.clone()
    b = clone.begin()
    while b.isValid():
        is_task_checked = (
            b.blockFormat().marker() == QTextBlockFormat.MarkerType.Checked
        )
        it = b.begin()
        while not it.atEnd():
            f = it.fragment()
            if f.isValid():
                cf = f.charFormat()
                if is_task_checked or cf.boolProperty(_CUSTOM_STRIKE_PROP) or cf.fontStrikeOut():
                    c = QTextCursor(clone)
                    c.setPosition(f.position())
                    c.setPosition(f.position() + f.length(), QTextCursor.MoveMode.KeepAnchor)
                    cf2 = QTextCharFormat()
                    cf2.setFontStrikeOut(True)
                    c.mergeCharFormat(cf2)
            it += 1
        b = b.next()
    return clone.toHtml()


def sanitized_fragment(html: str) -> QTextDocumentFragment:
    """Sanitised `html` as a fragment, for inserting at the cursor (paste)."""
    return QTextDocumentFragment(_rebuild(html))


def sanitized_html(html: str) -> str:
    """Sanitised `html` as a whole document, for loading into a new note."""
    return doc_to_html_with_strikethrough(_rebuild(html))

