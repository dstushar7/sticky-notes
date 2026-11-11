# Rich-text helpers shared by the note editor and Share/Receive.

from PyQt6.QtGui import (
    QFont, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextDocument,
    QTextDocumentFragment, QTextListFormat,
)


# Bullet styles cycled by sublist depth so nested levels are visually distinct.
_LIST_STYLES = (
    QTextListFormat.Style.ListDisc,
    QTextListFormat.Style.ListCircle,
    QTextListFormat.Style.ListSquare,
)


def style_for_indent(indent: int) -> QTextListFormat.Style:
    return _LIST_STYLES[(max(1, indent) - 1) % len(_LIST_STYLES)]


# Pasted or received rich text keeps only what the user could have typed: B/I/U/S,
# lists and checklists. The HTML is rebuilt into a fresh document, so formats
# nobody thought of (cell backgrounds, white-space: pre...) can't leak in.
_OBJECT_REPLACEMENT_CHAR = "￼"   # stands in for images / inline objects
_NBSP = " "


def _clean_char_format(src: QTextCharFormat) -> QTextCharFormat:
    fmt = QTextCharFormat()
    if src.fontWeight() >= QFont.Weight.DemiBold:
        fmt.setFontWeight(QFont.Weight.Bold)
    if src.fontItalic():
        fmt.setFontItalic(True)
    # Once the link is dropped, its underline would just be a stray decoration.
    if src.fontUnderline() and not src.isAnchor():
        fmt.setFontUnderline(True)
    if src.fontStrikeOut():
        fmt.setFontStrikeOut(True)
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
                # Numbered and custom lists become the bullet styles Tab-nesting uses.
                indent = max(1, src_list.format().indent())
                list_fmt = QTextListFormat()
                list_fmt.setIndent(indent)
                list_fmt.setStyle(style_for_indent(indent))
                lists[src_list.objectIndex()] = cursor.createList(list_fmt)
            else:
                dst_list.add(cursor.block())

        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid() and not frag.charFormat().isImageFormat():
                # Code from editors arrives as non-breaking spaces, which would stop lines wrapping.
                text = (frag.text()
                        .replace(_OBJECT_REPLACEMENT_CHAR, "")
                        .replace(_NBSP, " "))
                if text:
                    cursor.insertText(text, _clean_char_format(frag.charFormat()))
            it += 1
        block = block.next()

    return dst


def sanitized_fragment(html: str) -> QTextDocumentFragment:
    """Sanitised `html` as a fragment, for inserting at the cursor (paste)."""
    return QTextDocumentFragment(_rebuild(html))


def sanitized_html(html: str) -> str:
    """Sanitised `html` as a whole document, for loading into a new note."""
    return _rebuild(html).toHtml()
