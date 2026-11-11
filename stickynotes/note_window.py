
import re
import uuid
from datetime import datetime, timezone
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QAbstractButton,
    QLabel, QLineEdit, QStackedLayout, QSizePolicy, QGraphicsDropShadowEffect,
    QApplication, QFrame, QSlider,
)
from PyQt6.QtCore import (
    QSettings, pyqtSignal, Qt, QPoint, QRect, QRectF, QPointF, QSize, QByteArray,
    QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, QVariantAnimation,
    QEvent, QTimer,
)
from PyQt6.QtGui import (
    QColor, QTextListFormat, QTextBlockFormat, QTextCursor, QKeySequence,
    QShortcut, QFont, QFontMetrics, QFontMetricsF, QPainter, QPen, QCursor,
    QSyntaxHighlighter, QTextCharFormat, QPolygonF,
)

from . import config
from . import utils
from . import xwm
from . import sharing
from .widgets import FloatingButton, MenuRow
from .richtext import sanitized_fragment, style_for_indent


def rgba(hex_color: str, alpha: float) -> str:
    """'#RRGGBB' + 0..1 alpha -> a stylesheet rgba() string."""
    c = QColor(hex_color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {max(0, min(255, round(alpha * 255)))})"


def edited_phrase(iso: str) -> str:
    """'Edited just now' / '5 min ago' / … / '12 Oct', from a last_edited ISO timestamp."""
    try:
        then = datetime.fromisoformat(iso)
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return ""
    now = datetime.now(timezone.utc)
    secs = (now - then).total_seconds()
    if secs < 60:
        return "Edited just now"
    if secs < 3600:
        return f"Edited {int(secs // 60)} min ago"
    local_then, local_now = then.astimezone(), now.astimezone()
    if local_then.date() == local_now.date():
        return f"Edited {int(secs // 3600)} hr ago"
    if (local_now.date() - local_then.date()).days == 1:
        return "Edited yesterday"
    if local_then.year == local_now.year:
        return f"Edited {local_then.day} {local_then.strftime('%b')}"
    return f"Edited {local_then.day} {local_then.strftime('%b %Y')}"


def checklist_progress(document) -> tuple:
    """(done, total) checklist items in `document`."""
    done = total = 0
    block = document.begin()
    while block.isValid():
        if _is_checklist_block(block):
            total += 1
            if block.blockFormat().marker() == _MARKER_CHECKED:
                done += 1
        block = block.next()
    return done, total


def _now_iso() -> str:
    """Timezone-aware UTC ISO-8601 timestamp used for last_edited."""
    return datetime.now(timezone.utc).isoformat()


def default_note_size() -> tuple:
    """(width, height) for a new note, scaled to the screen."""
    screen = QApplication.primaryScreen().availableGeometry()
    return (
        max(280, min(480, screen.width() // 8)),
        max(280, min(480, screen.height() // 6)),
    )


def derive_title_from_text(plain_text: str) -> str:
    """Title from the first non-empty body line (a few words), or DEFAULT_NOTE_TITLE."""
    if plain_text:
        for line in plain_text.splitlines():
            stripped = line.strip()
            if stripped:
                words = stripped.split()[:config.AUTO_SEED_WORD_COUNT]
                derived = " ".join(words)[:config.MAX_TITLE_LENGTH].strip()
                if derived:
                    return derived
    return config.DEFAULT_NOTE_TITLE


# Checklists are ordinary QTextLists whose blocks carry a Checked/Unchecked marker.
# The marker replaces the bullet when drawn and round-trips through toHtml() as
# <li class="checked|unchecked">, so saving needs nothing special.
_MARKER_NONE = QTextBlockFormat.MarkerType.NoMarker
_MARKER_UNCHECKED = QTextBlockFormat.MarkerType.Unchecked
_MARKER_CHECKED = QTextBlockFormat.MarkerType.Checked


def _is_checklist_block(block) -> bool:
    """True if `block` is a list item carrying a checkbox marker."""
    if not block.isValid() or block.textList() is None:
        return False
    return block.blockFormat().marker() != _MARKER_NONE


def _cursor_in_checklist(cursor: QTextCursor) -> bool:
    return _is_checklist_block(cursor.block())


# Typed lists: lines typed as "1. milk" or "- milk" are plain text, not QTextLists.
# Enter continues them, Tab/Shift+Tab nest them, and numbers renumber after edits.
# They stay plain text so typed numbers survive paste and Share exactly as written.
_TYPED_ITEM_RE = re.compile(
    r"^([ \t]*)"                          # 1 indent
    r"(?:(\d{1,9}|[A-Za-z])([.)])"        # 2,3 "12." "12)" "c." "C)"
    r"|([-*+•◦▪‣–]))"                     # 4   bullet glyph
    r"([ \t]+)"                           # 5   gap — required, so "1.5", "-3", "e.g." don't match
)
_LINE_SEPARATOR = "\u2028"   # what Shift+Enter inserts outside a list
_INDENT_UNIT = "    "        # one nesting level of a typed list
_SIBLING_LOOKBACK = 50       # lines scanned upward for an item at the same level


def _indent_width(indent: str) -> int:
    return len(indent.expandtabs(len(_INDENT_UNIT)))


def _outdented(indent: str) -> str:
    """`indent` one level shallower: drop a trailing tab, or up to one unit of spaces."""
    if indent.endswith("\t"):
        return indent[:-1]
    spaces = len(indent) - len(indent.rstrip(" "))
    return indent[:len(indent) - min(spaces, len(_INDENT_UNIT))]


def _next_token(token: str):
    """"3" -> "4" (padding kept: "09" -> "10"), "c" -> "d"; None after "z"."""
    if token.isdigit():
        return str(int(token) + 1).zfill(len(token))
    return None if token in "zZ" else chr(ord(token) + 1)


def _first_token(token: str) -> str:
    """Start of a fresh list of the same kind as `token`: "1", "a" or "A"."""
    if token.isdigit():
        return "1"
    return "a" if token.islower() else "A"


def typed_list_prefix(line: str):
    """If `line` starts like a typed list item, return
    (prefix_length, prefix_for_next_item); otherwise None."""
    m = _TYPED_ITEM_RE.match(line)
    if m is None:
        return None
    indent, token, delim, bullet, gap = m.groups()
    if token is None:
        marker = bullet
    else:
        nxt = _next_token(token)
        if nxt is None:
            return None
        marker = nxt + delim
    return m.end(), f"{indent}{marker}{gap}"


def _same_kind(a: str, b: str) -> bool:
    """Both numbers, or both letters of the same case."""
    if a.isdigit() or b.isdigit():
        return a.isdigit() and b.isdigit()
    return a.islower() == b.islower()


def _line_indent_width(line: str) -> int:
    return _indent_width(line[:len(line) - len(line.lstrip(" \t"))])


def _level_context(indent: str, lines_above):
    """(sibling, parent) for a line at `indent`: the nearest typed item above at the same
    indent (skipping nested lines), or else the item it is nested under.
    """
    width = _indent_width(indent)
    for i, line in enumerate(lines_above):
        if i >= _SIBLING_LOOKBACK:
            break
        line_width = _line_indent_width(line)
        if line.strip() and line_width > width:
            continue   # a nested item or its text — keep looking up
        m = _TYPED_ITEM_RE.match(line)
        if m is None:
            break
        return (m, None) if line_width == width else (None, m)
    return None, None


def _item_above(indent: str, lines_above):
    """Match of the nearest typed item above at the same indent, or None."""
    return _level_context(indent, lines_above)[0]


def renest_prefix(line: str, deeper: bool, lines_above=()):
    """New (prefix_length, prefix) for typed item `line` moved one level deeper or
    shallower, or None. It continues an item already at that level, else starts afresh.
    """
    m = _TYPED_ITEM_RE.match(line)
    if m is None:
        return None
    indent, token, delim, bullet, gap = m.groups()
    if deeper:
        new_indent = indent + _INDENT_UNIT
    elif indent:
        new_indent = _outdented(indent)
    else:
        return None

    marker = None
    above = _item_above(new_indent, lines_above)
    if above is not None:
        if above.group(2) is None:
            marker = above.group(4)
        else:
            nxt = _next_token(above.group(2))
            marker = nxt and nxt + above.group(3)
    if marker is None:
        marker = bullet if token is None else _first_token(token) + delim
    return m.end(), f"{new_indent}{marker}{gap}"


def _lines_above(block, line_start: int):
    """Lines above `line_start` in `block`, nearest first, across blocks and line breaks."""
    if line_start:
        yield from reversed(block.text()[:line_start].split(_LINE_SEPARATOR)[:-1])
    block = block.previous()
    while block.isValid():
        yield from reversed(block.text().split(_LINE_SEPARATOR))
        block = block.previous()


# Resize zones
_NONE, _N, _NE, _E, _SE, _S, _SW, _W, _NW = range(9)

_CURSORS = {
    _N:  Qt.CursorShape.SizeVerCursor,
    _S:  Qt.CursorShape.SizeVerCursor,
    _E:  Qt.CursorShape.SizeHorCursor,
    _W:  Qt.CursorShape.SizeHorCursor,
    _NE: Qt.CursorShape.SizeBDiagCursor,
    _SW: Qt.CursorShape.SizeBDiagCursor,
    _NW: Qt.CursorShape.SizeFDiagCursor,
    _SE: Qt.CursorShape.SizeFDiagCursor,
}

# Map our resize zones to Qt.Edge bitfields for QWindow.startSystemResize
_EDGES = {
    _N:  Qt.Edge.TopEdge,
    _S:  Qt.Edge.BottomEdge,
    _E:  Qt.Edge.RightEdge,
    _W:  Qt.Edge.LeftEdge,
    _NE: Qt.Edge.TopEdge | Qt.Edge.RightEdge,
    _NW: Qt.Edge.TopEdge | Qt.Edge.LeftEdge,
    _SE: Qt.Edge.BottomEdge | Qt.Edge.RightEdge,
    _SW: Qt.Edge.BottomEdge | Qt.Edge.LeftEdge,
}


# Note editor
class ChecklistHighlighter(QSyntaxHighlighter):
    """Fades and strikes through ticked checklist items. Display only: the formats never
    reach toHtml(), so saved notes and Share text are unchanged.
    """

    def __init__(self, document):
        super().__init__(document)
        self._fmt = QTextCharFormat()
        self._fmt.setFontStrikeOut(True)
        self.set_ink("#1a1a1a")

    def set_ink(self, text_color: str):
        ink = QColor(text_color)
        ink.setAlpha(125)
        self._fmt.setForeground(ink)

    def highlightBlock(self, text):   # noqa: N802 (Qt naming)
        block = self.currentBlock()
        if text and _is_checklist_block(block) and block.blockFormat().marker() == _MARKER_CHECKED:
            self.setFormat(0, len(text), self._fmt)


class NoteTextEdit(QTextEdit):
    """Rich-text note body: list keyboard handling, and it paints the checkboxes itself."""

    highlighter = None   # set by StickyNote; re-run when a box is ticked

    def __init__(self, parent=None):
        super().__init__(parent)
        # Checkbox colours, kept in step with the paper by StickyNote._apply_surface.
        self._surface = QColor("#FFF39C")
        self._ink = QColor("#2B2410")

    def set_paint_colors(self, surface: QColor, ink: QColor):
        self._surface = QColor(surface)
        self._ink = QColor(ink)
        self.viewport().update()

    def paintEvent(self, event):   # noqa: N802 (Qt naming)
        """Draw rounded checkboxes over Qt's square markers, which can't be restyled: refill
        the marker band with the paper colour, then draw our own box. Visual only.
        """
        super().paintEvent(event)
        doc = self.document()
        band = doc.indentWidth() or config.LIST_INDENT_PX
        layout = doc.documentLayout()
        dy = -self.verticalScrollBar().value()
        visible = self.viewport().rect()
        painter = None
        block = doc.begin()
        while block.isValid():
            if _is_checklist_block(block) and block.layout() is not None and block.layout().lineCount():
                rect = layout.blockBoundingRect(block)
                if rect.bottom() + dy >= 0 and rect.top() + dy <= visible.bottom():
                    if painter is None:
                        painter = QPainter(self.viewport())
                        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    self._paint_box(painter, block, band, rect.top() + dy)
            block = block.next()
        if painter is not None:
            painter.end()

    def _paint_box(self, p: QPainter, block, band: float, block_top: float):
        line = block.layout().lineAt(0)
        text_x = self.cursorRect(QTextCursor(block)).left()
        top = block_top + line.y()
        height = line.height()
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(QRectF(text_x - band - 2, top, band + 1, height), self._surface)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        size = max(12.0, min(band - 3.0, QFontMetricsF(self.font()).height() * 0.62))
        box = QRectF(text_x - band + (band - size) / 2 - 2, top + (height - size) / 2, size, size)
        checked = block.blockFormat().marker() == _MARKER_CHECKED
        ink = QColor(self._ink)
        if checked:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(ink)
            p.drawRoundedRect(box, size * 0.28, size * 0.28)
            tick = QPen(QColor(self._surface.red(), self._surface.green(), self._surface.blue()))
            tick.setWidthF(max(1.6, size * 0.14))
            tick.setCapStyle(Qt.PenCapStyle.RoundCap)
            tick.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(tick)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolyline(QPolygonF([
                QPointF(box.left() + size * 0.24, box.top() + size * 0.52),
                QPointF(box.left() + size * 0.43, box.top() + size * 0.70),
                QPointF(box.left() + size * 0.76, box.top() + size * 0.32),
            ]))
        else:
            ink.setAlpha(175)
            pen = QPen(ink)
            pen.setWidthF(1.6)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(box.adjusted(0.8, 0.8, -0.8, -0.8), size * 0.26, size * 0.26)

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()
        cursor = self.textCursor()

        # Tab / Shift+Tab — sublist nesting (only inside a list)
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab) and cursor.currentList():
            increase = key == Qt.Key.Key_Tab and not (mods & Qt.KeyboardModifier.ShiftModifier)
            self._change_list_indent(increase)
            return

        # Shift+Enter — break out of list
        if (
            key == Qt.Key.Key_Return
            and mods == Qt.KeyboardModifier.ShiftModifier
            and cursor.currentList()
        ):
            self._break_out_of_list()
            return

        # Qt copies the marker to the new block, so Enter after a ticked item would make a
        # ticked one; reset it to unchecked.
        if (
            key in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and not (mods & Qt.KeyboardModifier.ShiftModifier)
            and _is_checklist_block(cursor.block())
        ):
            super().keyPressEvent(event)
            new_cursor = self.textCursor()
            fmt = new_cursor.blockFormat()
            if fmt.marker() == _MARKER_CHECKED:
                fmt.setMarker(_MARKER_UNCHECKED)
                new_cursor.setBlockFormat(fmt)
            return

        # Typed "1." / "-" lines. Real lists never get here: Qt handles those.
        no_mods = not (mods & (Qt.KeyboardModifier.ControlModifier
                               | Qt.KeyboardModifier.AltModifier
                               | Qt.KeyboardModifier.MetaModifier))
        if no_mods and not cursor.hasSelection() and cursor.currentList() is None:
            if (key in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                    and not (mods & Qt.KeyboardModifier.ShiftModifier)
                    and self._continue_typed_list(cursor)):
                return
            if (key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)
                    and self._renest_typed_item(cursor, deeper=(
                        key == Qt.Key.Key_Tab
                        and not (mods & Qt.KeyboardModifier.ShiftModifier)))):
                return

        # Deleting items can leave gaps in the numbering; renumber in the same undo step.
        if (key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete)
                or event.matches(QKeySequence.StandardKey.Cut)):
            super().keyPressEvent(event)
            after = self.textCursor()
            if after.currentList() is None:
                line_start, _, _ = self._typed_line(after)
                after.joinPreviousEditBlock()
                self._renumber_level(after.block(), line_start)
                after.endEditBlock()
            return

        super().keyPressEvent(event)

    # Typed-list renumbering

    @staticmethod
    def _line_text(block, line_start: int) -> str:
        text = block.text()
        end = text.find(_LINE_SEPARATOR, line_start)
        return text[line_start:] if end == -1 else text[line_start:end]

    @staticmethod
    def _lines_below(block, line_start: int):
        """Each line after the given one, as (block, line_start). Lazy, so the caller may edit
        a line before asking for the next.
        """
        while True:
            end = block.text().find(_LINE_SEPARATOR, line_start)
            if end != -1:
                line_start = end + 1
            else:
                block = block.next()
                if not block.isValid():
                    return
                line_start = 0
            yield block, line_start

    def _renumber_level(self, block, line_start: int):
        """Renumber this item and the rest of its level so they count on without gaps.
        A nested first item restarts at 1/a/A; a list's first item keeps its number.
        """
        m = _TYPED_ITEM_RE.match(self._line_text(block, line_start))
        if m is None or m.group(2) is None:
            return   # not a numbered/lettered item — bullets have nothing to fix
        indent, token, delim = m.group(1), m.group(2), m.group(3)
        width = _indent_width(indent)

        sibling, parent = _level_context(indent, _lines_above(block, line_start))
        if (sibling is not None and sibling.group(2) is not None
                and sibling.group(3) == delim and _same_kind(sibling.group(2), token)):
            expected = _next_token(sibling.group(2))
        elif parent is not None:
            expected = _first_token(token)
        else:
            expected = token

        position = (block, line_start)
        below = self._lines_below(block, line_start)
        while position is not None:
            blk, start = position
            line = self._line_text(blk, start)
            if line.strip() and _line_indent_width(line) > width:
                position = next(below, None)
                continue   # nested under this level — skip, don't stop
            lm = _TYPED_ITEM_RE.match(line)
            if (lm is None or _indent_width(lm.group(1)) != width
                    or lm.group(2) is None or lm.group(3) != delim
                    or not _same_kind(lm.group(2), token) or expected is None):
                return   # end of this level's run
            if lm.group(2) != expected:
                pos = blk.position() + start + len(lm.group(1))
                # Qt would carry a caret at the number's start past the new digits; hold it.
                caret = self.textCursor()
                pin = not caret.hasSelection() and caret.position() == pos
                edit = QTextCursor(self.document())
                edit.setPosition(pos)
                edit.setPosition(pos + len(lm.group(2)), QTextCursor.MoveMode.KeepAnchor)
                edit.insertText(expected, self._line_format(blk, start))
                if pin:
                    caret.setPosition(pos)
                    self.setTextCursor(caret)
            expected = _next_token(expected)
            position = next(below, None)

    def _renumber_after_move(self, block, line_start: int, old_width: int):
        """After an item changed level, renumber its new level and the level it left."""
        self._renumber_level(block, line_start)
        for blk, start in self._lines_below(block, line_start):
            line = self._line_text(blk, start)
            if not line.strip():
                return
            line_width = _line_indent_width(line)
            if line_width > old_width:
                continue
            if line_width == old_width:
                self._renumber_level(blk, start)
            return

    @staticmethod
    def _typed_line(cursor: QTextCursor):
        """(line_start, line_end, line) around the cursor. Shift+Enter (U+2028) splits a
        block into several lines.
        """
        text = cursor.block().text()
        col = cursor.positionInBlock()
        line_start = text.rfind(_LINE_SEPARATOR, 0, col) + 1
        line_end = text.find(_LINE_SEPARATOR, col)
        if line_end == -1:
            line_end = len(text)
        return line_start, line_end, text[line_start:line_end]

    @staticmethod
    def _line_format(block, line_start: int):
        """Char format of the line's first character, given to a rewritten marker."""
        probe = QTextCursor(block)
        probe.setPosition(block.position() + line_start + 1)
        return probe.charFormat()

    def _move_item(self, cursor, line_start, prefix_len, new_prefix):
        """Replace the marker on the cursor's line (moving it to another level), keep the
        cursor in place and renumber both levels, as one undo step.
        """
        block = cursor.block()
        base = block.position() + line_start
        old_width = _line_indent_width(self._line_text(block, line_start))
        text_offset = max(0, cursor.position() - base - prefix_len)
        fmt = self._line_format(block, line_start)
        cursor.beginEditBlock()
        cursor.setPosition(base)
        cursor.setPosition(base + prefix_len, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(new_prefix, fmt)
        cursor.setPosition(base + len(new_prefix) + text_offset)
        self._renumber_after_move(block, line_start, old_width)
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def _continue_typed_list(self, cursor: QTextCursor) -> bool:
        """Enter on a typed list line. False means let Qt do a plain Enter."""
        block = cursor.block()
        line_start, line_end, line = self._typed_line(cursor)
        found = typed_list_prefix(line)
        if found is None:
            return False
        prefix_len, next_prefix = found
        if cursor.positionInBlock() - line_start < prefix_len:
            return False   # cursor before/inside "1. " — plain Enter, no new marker

        if not line[prefix_len:].strip():
            # Empty item: step out a level, or end the list by dropping the marker.
            outer = renest_prefix(line, False, _lines_above(block, line_start))
            if outer is not None:
                self._move_item(cursor, line_start, prefix_len, outer[1])
            else:
                base = block.position()
                cursor.setPosition(base + line_start)
                cursor.setPosition(base + line_end, QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                self.setTextCursor(cursor)
            return True

        # The marker copies the previous marker's format; typed text keeps the cursor's.
        marker_fmt = self._line_format(block, line_start)
        typing_fmt = cursor.charFormat()
        cursor.beginEditBlock()
        cursor.insertBlock()
        cursor.insertText(next_prefix, marker_fmt)
        cursor.setCharFormat(typing_fmt)
        # The new item now holds the next number; push the ones below along.
        self._renumber_level(cursor.block(), 0)
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        return True

    def _renest_typed_item(self, cursor: QTextCursor, deeper: bool) -> bool:
        """Tab / Shift+Tab on a typed list line. False means let Qt handle the key."""
        line_start, _, line = self._typed_line(cursor)
        found = renest_prefix(line, deeper, _lines_above(cursor.block(), line_start))
        if found is None:
            # Shift+Tab at the top level does nothing, but swallow it so focus doesn't move.
            return _TYPED_ITEM_RE.match(line) is not None
        self._move_item(cursor, line_start, *found)
        return True

    def insertFromMimeData(self, source):
        """Paste / drop: rich content is sanitised (see richtext)."""
        if source.hasHtml():
            self.textCursor().insertFragment(sanitized_fragment(source.html()))
            self.ensureCursorVisible()
            return
        super().insertFromMimeData(source)

    def _marker_block_at(self, pos):
        """The checklist block whose checkbox is at viewport `pos`, or None. Shared by clicks
        and the hover cursor, so the clickable area and the hand cursor always match.
        """
        block = self.cursorForPosition(pos).block()
        if not _is_checklist_block(block):
            return None
        text_x = self.cursorRect(QTextCursor(block)).left()
        band = self.document().indentWidth() or config.LIST_INDENT_PX
        if text_x - band <= pos.x() < text_x:
            return block
        return None

    def mousePressEvent(self, event):
        """Tick/untick a checklist item by clicking its checkbox."""
        if event.button() == Qt.MouseButton.LeftButton:
            block = self._marker_block_at(event.pos())
            if block is not None:
                self._toggle_marker(block)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Hand cursor over checkboxes only. Qt computes its own from the default 40px
        indent, which lands over the text instead of the box.
        """
        super().mouseMoveEvent(event)
        pos = event.pos()
        if _is_checklist_block(self.cursorForPosition(pos).block()):
            self.viewport().setCursor(
                Qt.CursorShape.PointingHandCursor
                if self._marker_block_at(pos) is not None
                else Qt.CursorShape.IBeamCursor
            )

    def _toggle_marker(self, block):
        """Tick or untick a checklist item (a normal edit, so it autosaves)."""
        cursor = QTextCursor(block)
        fmt = cursor.blockFormat()
        fmt.setMarker(
            _MARKER_UNCHECKED if fmt.marker() == _MARKER_CHECKED
            else _MARKER_CHECKED
        )
        cursor.setBlockFormat(fmt)
        if self.highlighter is not None:
            self.highlighter.rehighlightBlock(block)

    def _break_out_of_list(self):
        cursor = self.textCursor()
        cursor.insertBlock()
        block = cursor.block()
        lst = block.textList()
        if lst:
            lst.remove(block)
        fmt = cursor.blockFormat()
        fmt.setIndent(0)
        # Leaving a checklist drops the checkbox too, or the paragraph keeps an orphan marker.
        fmt.setMarker(_MARKER_NONE)
        cursor.setBlockFormat(fmt)
        self.setTextCursor(cursor)

    def _change_list_indent(self, increase: bool):
        cursor = self.textCursor()
        current_list = cursor.currentList()
        if not current_list:
            return
        current_indent = current_list.format().indent()
        new_indent = current_indent + (1 if increase else -1)

        if new_indent < 1:
            # Outdent past level 1: remove the block from the list.
            block = cursor.block()
            current_list.remove(block)
            bf = cursor.blockFormat()
            bf.setIndent(0)
            # Same as _break_out_of_list: drop the orphan checkbox.
            bf.setMarker(_MARKER_NONE)
            cursor.setBlockFormat(bf)
            return

        new_fmt = QTextListFormat()
        new_fmt.setIndent(new_indent)
        new_fmt.setStyle(style_for_indent(new_indent))
        cursor.createList(new_fmt)


# OptionsPanel: the ••• menu (colours, opacity, keep on top, collapse, share,
# receive, delete). Opens beside the note so the opacity preview stays visible.
# Painted opaque: translucent popups bleed through under XWayland.
class _Swatch(QAbstractButton):
    """A round colour swatch; ticked when it's the note's current colour."""

    def __init__(self, theme_name: str, current: bool, parent=None):
        super().__init__(parent)
        self._theme = utils.get_theme(theme_name)
        self._current = current
        self.setFixedSize(26, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(self._theme.get("name", theme_name.capitalize()))
        self.setAccessibleName(f"{self.toolTip()} colour")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def paintEvent(self, _event):   # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        if self.underMouse() and not self._current:
            r = QRectF(0, 0, self.width(), self.height())
        p.setPen(QPen(QColor(0, 0, 0, 45), 1))
        p.setBrush(QColor(self._theme["bg"]))
        p.drawEllipse(r)
        if self._current:
            pen = QPen(QColor("#FFFFFF" if self._theme.get("dark") else "#2A2A2A"))
            pen.setWidthF(2.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            w = self.width()
            p.drawPolyline(QPolygonF([
                QPointF(w * 0.30, w * 0.52), QPointF(w * 0.45, w * 0.66), QPointF(w * 0.72, w * 0.36),
            ]))


class _DeleteRow(MenuRow):
    """'Delete note' with a two-click confirm: the first click arms it for
    DELETE_CONFIRM_WINDOW_MS, a second click inside that window confirms.
    """
    confirmed = pyqtSignal()

    def __init__(self, pal: dict, parent=None):
        super().__init__("Delete note", parent=parent)
        self._pal = pal
        self._armed = False
        self._remaining = 0.0
        self.set_icon(utils.line_icon("trash", pal["danger"]))
        self.setProperty("danger", True)
        self._drain = QVariantAnimation(self)
        self._drain.setDuration(config.DELETE_CONFIRM_WINDOW_MS)
        self._drain.setStartValue(1.0)
        self._drain.setEndValue(0.0)
        self._drain.valueChanged.connect(self._on_drain)
        self._drain.finished.connect(self._disarm)
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self):
        if self._armed:
            self._drain.stop()
            self.confirmed.emit()
        else:
            self._armed = True
            self.set_text("Click again to delete")
            self.setProperty("armed", True)
            self._repolish()
            self._drain.start()

    def _disarm(self):
        self._armed = False
        self._remaining = 0.0
        self.set_text("Delete note")
        self.setProperty("armed", False)
        self._repolish()

    def _on_drain(self, value):
        self._remaining = float(value)
        self.update()

    def _repolish(self):
        for w in (self, self.text_label):
            w.style().unpolish(w)
            w.style().polish(w)
        self.update()

    def paintEvent(self, event):   # noqa: N802
        super().paintEvent(event)
        if self._armed and self._remaining > 0:
            p = QPainter(self)
            p.fillRect(QRectF(0, self.height() - 3, self.width() * self._remaining, 3),
                       QColor(self._pal["danger"]))


class OptionsPanel(QWidget):
    themeSelected = pyqtSignal(str)
    opacityChanged = pyqtSignal(int)        # live, on every slider step
    pinToggleRequested = pyqtSignal()
    collapseToggleRequested = pyqtSignal()
    deleteRequested = pyqtSignal()
    shareRequested = pyqtSignal()
    receiveRequested = pyqtSignal()
    # Emitted on every dismissal; carries self so the owner can check identity.
    dismissed = pyqtSignal(object)

    WIDTH = 260
    SHADOW_MARGIN = 12

    def __init__(self, *, theme: str, opacity: int, pinned: bool, pin_available: bool,
                 collapsed: bool, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._dismissed = False
        self._pal = utils.chrome_palette()
        self._setup_ui(theme, opacity, pinned, pin_available, collapsed)

    def hideEvent(self, event):
        # Outside clicks hide() the popup rather than close() it, so clean up here.
        super().hideEvent(event)
        if not self._dismissed:
            self._dismissed = True
            self.dismissed.emit(self)
            self.deleteLater()

    def _setup_ui(self, theme, opacity, pinned, pin_available, collapsed):
        pal = self._pal
        m = self.SHADOW_MARGIN
        outer = QVBoxLayout(self)
        outer.setContentsMargins(m, m, m, m)

        body = QFrame(self)
        body.setObjectName("panelBody")
        body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        shadow = QGraphicsDropShadowEffect(body)
        blur, offset_y, alpha = config.SHADOW_PANEL
        shadow.setBlurRadius(blur)
        shadow.setOffset(0, offset_y)
        shadow.setColor(QColor(0, 0, 0, alpha + 30))
        body.setGraphicsEffect(shadow)
        outer.addWidget(body)

        lay = QVBoxLayout(body)
        lay.setContentsMargins(12, 12, 12, 10)
        lay.setSpacing(2)

        # Colours
        swatches = QHBoxLayout()
        swatches.setSpacing(6)
        swatches.setContentsMargins(2, 0, 2, 8)
        for name in config.THEMES:
            sw = _Swatch(name, name == theme, body)
            sw.clicked.connect(lambda _c=False, n=name: self.themeSelected.emit(n))
            swatches.addWidget(sw)
        lay.addLayout(swatches)

        # Opacity
        head = QHBoxLayout()
        head.setContentsMargins(8, 2, 6, 4)
        head.setSpacing(12)
        icon = QLabel(body)
        icon.setPixmap(utils.line_icon("opacity", pal["text"]).pixmap(QSize(18, 18)))
        head.addWidget(icon)
        head.addWidget(QLabel("Opacity", body), 1)
        self._value = QLabel(f"{opacity}%", body)
        self._value.setObjectName("valuePill")
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value.setMinimumWidth(46)
        head.addWidget(self._value)
        lay.addLayout(head)

        self.slider = QSlider(Qt.Orientation.Horizontal, body)
        self.slider.setRange(config.OPACITY_MIN, config.OPACITY_MAX)
        self.slider.setSingleStep(config.OPACITY_STEP)
        self.slider.setPageStep(config.OPACITY_STEP * 2)
        self.slider.setValue(opacity)
        self.slider.setAccessibleName("Opacity")
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider.valueChanged.connect(self._on_slider)
        slider_row = QHBoxLayout()
        slider_row.setContentsMargins(8, 0, 8, 0)
        slider_row.addWidget(self.slider)
        lay.addLayout(slider_row)

        ends = QHBoxLayout()
        ends.setContentsMargins(8, 0, 8, 6)
        for text, align in (("50%", Qt.AlignmentFlag.AlignLeft),
                            ("text stays solid", Qt.AlignmentFlag.AlignHCenter),
                            ("100%", Qt.AlignmentFlag.AlignRight)):
            lbl = QLabel(text, body)
            lbl.setObjectName("panelSmall")
            lbl.setAlignment(align)
            ends.addWidget(lbl, 1)
        lay.addLayout(ends)
        lay.addWidget(self._divider(body))

        # Actions
        self._pin_row = MenuRow("Unpin from top" if pinned else "Keep on top", parent=body)
        self._pin_row.set_icon(utils.create_pin_icon(pal["text"], 18, filled=pinned))
        if pin_available:
            self._pin_row.clicked.connect(self._emit_and_close(self.pinToggleRequested))
        else:
            self._pin_row.setEnabled(False)
            self._pin_row.setToolTip("Keep on top needs X11 or XWayland — unavailable in this session")
        lay.addWidget(self._pin_row)

        fold = MenuRow("Expand" if collapsed else "Collapse", "Double-click bar", body)
        fold.set_icon(utils.line_icon("unfold" if collapsed else "fold", pal["text"]))
        fold.clicked.connect(self._emit_and_close(self.collapseToggleRequested))
        lay.addWidget(fold)

        self._share_row = MenuRow("Share…", "Copies as text", body)
        self._share_row.set_icon(utils.line_icon("share", pal["text"]))
        self._share_row.setToolTip(
            "Copy this note as text you can send to anyone.\n"
            "Anyone with the text can read the note."
        )
        self._share_row.clicked.connect(self.shareRequested.emit)
        lay.addWidget(self._share_row)

        receive = MenuRow("Receive a note…", parent=body)
        receive.set_icon(utils.line_icon("receive", pal["text"]))
        receive.setToolTip("Add a note someone shared with you")
        receive.clicked.connect(self.receiveRequested.emit)
        lay.addWidget(receive)

        lay.addWidget(self._divider(body))
        delete = _DeleteRow(pal, body)
        delete.confirmed.connect(self.deleteRequested.emit)
        lay.addWidget(delete)

        self.setFixedWidth(self.WIDTH + 2 * m)
        self._apply_style()

    def _emit_and_close(self, signal):
        def handler():
            self.close()
            signal.emit()
        return handler

    def _on_slider(self, value: int):
        # Snap to whole steps so the stored value is always 50, 55 … 100.
        step = config.OPACITY_STEP
        snapped = int(round(value / step) * step)
        if snapped != value:
            self.slider.setValue(snapped)
            return
        self._value.setText(f"{snapped}%")
        self.slider.setAccessibleDescription(f"{snapped}%")
        self.opacityChanged.emit(snapped)

    @staticmethod
    def _divider(parent) -> QFrame:
        line = QFrame(parent)
        line.setObjectName("panelDivider")
        line.setFixedHeight(1)
        return line

    def show_share_copied(self):
        """Confirm the copy in place, then get out of the way."""
        self._share_row.set_text("Copied — paste it in any chat")
        self._share_row.hint_label.hide()
        self._share_row.set_icon(utils.line_icon("check", self._pal["ok"]))
        self._share_row.setProperty("done", True)
        for w in (self._share_row, self._share_row.text_label):
            w.style().unpolish(w)
            w.style().polish(w)
        self._share_row.setEnabled(False)
        QTimer.singleShot(config.SHARE_COPIED_FEEDBACK_MS, self.close)

    def _apply_style(self):
        pal = self._pal
        r = config.PANEL_RADIUS_PX
        self.setStyleSheet(f"""
            QFrame#panelBody {{
                background-color: {pal['surface']};
                border: 1px solid {pal['line']};
                border-radius: {r}px;
            }}
            QLabel {{ color: {pal['text']}; background: transparent; font-size: 10pt; }}
            QLabel#panelSmall {{ color: {pal['muted']}; font-size: 8pt; }}
            QLabel#menuHint {{ color: {pal['muted']}; font-size: 8.5pt; }}
            QLabel#valuePill {{
                background-color: {pal['raised']}; border-radius: 7px;
                padding: 1px 6px; font-weight: 700; font-size: 9pt;
            }}
            QFrame#panelDivider {{ background-color: {pal['line']}; border: none; margin: 4px 0; }}
            QWidget#menuRow {{ background-color: {pal['surface']}; border-radius: 9px; }}
            QWidget#menuRow:hover {{ background-color: {pal['raised']}; }}
            QWidget#menuRow:disabled QLabel {{ color: {pal['muted']}; }}
            QWidget#menuRow[danger="true"] QLabel {{ color: {pal['danger']}; }}
            QWidget#menuRow[armed="true"] {{ background-color: {pal['danger_soft']}; }}
            QWidget#menuRow[armed="true"] QLabel {{ font-weight: 700; }}
            QWidget#menuRow[done="true"] QLabel {{ color: {pal['ok']}; }}
            QSlider {{ background: transparent; min-height: 22px; }}
            QSlider::groove:horizontal {{ height: 4px; background: {pal['line']}; border-radius: 2px; }}
            QSlider::sub-page:horizontal {{ background: {pal['text']}; border-radius: 2px; }}
            QSlider::handle:horizontal {{
                background: {pal['text']}; width: 16px; height: 16px;
                margin: -6px 0; border-radius: 8px;
            }}
        """)

    def place_beside(self, note: QWidget):
        """Open right of the note, else left, top-aligned and kept on the note's screen."""
        self.adjustSize()
        g = config.SHADOW_GUTTER
        m = self.SHADOW_MARGIN
        top_left = note.mapToGlobal(QPoint(g, g))
        vis_w = note.width() - 2 * g
        screen = note.screen() or QApplication.primaryScreen()
        area = screen.availableGeometry()
        y = top_left.y() - m
        x = top_left.x() + vis_w + 8 - m
        if x + self.width() - m > area.right():
            x = top_left.x() - self.width() - 8 + m
        if x < area.left() - m:
            # No room either side: drop down from the ••• end of the title bar.
            x = top_left.x() + vis_w - self.width() + m
            y = top_left.y() + config.TITLE_BAR_HEIGHT + 4 - m
        y = max(area.top() - m, min(y, area.bottom() - self.height() + m))
        x = max(area.left() - m, min(x, area.right() - self.width() + m))
        self.move(QPoint(x, y))

# EditableTitleLabel: a label that turns into a QLineEdit on click.
# Enter or focus loss commits; Escape cancels.
class EditableTitleLabel(QWidget):
    committed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("titlePill")
        # The pill sizes to its text; the layout margins give it padding.
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        self._editable = True
        self._current_text = ""
        self._text_color = "#555555"
        self._hover_overlay = "rgba(0, 0, 0, 0.12)"

        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(8, 2, 8, 2)

        self._label = QLabel("")
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self._label.setCursor(Qt.CursorShape.IBeamCursor)
        self._label.installEventFilter(self)

        self._edit = QLineEdit("")
        self._edit.setMaxLength(config.MAX_TITLE_LENGTH)
        self._edit.setFrame(False)
        self._edit.installEventFilter(self)
        self._edit.editingFinished.connect(self._on_editing_finished)

        self._stack.addWidget(self._label)
        self._stack.addWidget(self._edit)
        self._stack.setCurrentIndex(0)

    def set_text(self, text: str):
        self._current_text = text
        self._update_display()
        self.updateGeometry()  # sizeHint changed, ask layout to re-measure

    def current_text(self) -> str:
        return self._current_text

    def set_editable(self, editable: bool):
        """Turn click-to-rename on or off (off while collapsed); commits any edit in progress."""
        if self._editable == editable:
            return
        self._editable = editable
        if not editable and self._stack.currentIndex() == 1:
            # Force-commit before locking so the user doesn't lose typing
            self._on_editing_finished()
        self._label.setCursor(
            Qt.CursorShape.IBeamCursor if editable else Qt.CursorShape.ArrowCursor
        )
        self._apply_pill_style()

    def is_editing(self) -> bool:
        return self._stack.currentIndex() == 1

    def apply_text_style(self, text_color: str, hover_overlay: str):
        """Style the pill and its text; the pill shows only on hover or while editing."""
        self._text_color = text_color
        self._hover_overlay = hover_overlay
        text_qss = (
            f"color: {text_color}; background-color: transparent;"
            f"font-size: 10pt; font-weight: 700;"
        )
        self._label.setStyleSheet(f"QLabel {{ {text_qss} }}")
        self._edit.setStyleSheet(
            f"QLineEdit {{ {text_qss} border: none; padding: 0px; "
            f"selection-background-color: {text_color}; "
            f"selection-color: white; }}"
        )
        self._apply_pill_style()

    def _apply_pill_style(self):
        """(Re)compute the pill background for the current state."""
        if not self._editable:
            # Collapsed → no pill, no hover. Just plain text on title bar.
            self.setStyleSheet(
                "QWidget#titlePill { background-color: transparent; "
                "border-radius: 10px; }"
            )
            return
        if self.is_editing():
            # Active edit → keep the pill visible the whole time
            self.setStyleSheet(
                f"QWidget#titlePill {{ background-color: {self._hover_overlay}; "
                f"border-radius: 10px; }}"
            )
            return
        # Display mode, clickable → reveal pill only on hover
        self.setStyleSheet(
            "QWidget#titlePill {"
            " background-color: transparent; border-radius: 10px; }"
            f" QWidget#titlePill:hover {{ background-color: {self._hover_overlay}; }}"
        )

    def eventFilter(self, obj, event):
        if obj is self._label:
            if (event.type() == QEvent.Type.MouseButtonPress
                    and event.button() == Qt.MouseButton.LeftButton):
                if self._editable:
                    self._enter_edit_mode()
                    return True
        elif obj is self._edit:
            if (event.type() == QEvent.Type.KeyPress
                    and event.key() == Qt.Key.Key_Escape):
                self._cancel_edit()
                return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_display()

    def _enter_edit_mode(self):
        self._edit.setText(self._current_text)
        self._stack.setCurrentIndex(1)
        self._apply_pill_style()
        self._edit.setFocus(Qt.FocusReason.MouseFocusReason)
        self._edit.selectAll()

    def _on_editing_finished(self):
        # Fires on Enter and focus loss; the index check makes it safe to re-enter.
        if self._stack.currentIndex() != 1:
            return
        new_text = self._edit.text()
        self._stack.setCurrentIndex(0)
        self._update_display()
        self._apply_pill_style()
        self.committed.emit(new_text)

    def _cancel_edit(self):
        if self._stack.currentIndex() != 1:
            return
        # Otherwise hiding the editor fires editingFinished and commits again.
        self._edit.blockSignals(True)
        self._stack.setCurrentIndex(0)
        self._edit.blockSignals(False)
        self._update_display()
        self._apply_pill_style()

    def _update_display(self):
        text = self._current_text
        if not text:
            self._label.setText("")
            self._label.setToolTip("")
            return
        metrics = QFontMetrics(self._label.font())
        m = self._stack.contentsMargins()
        avail = self.width() - m.left() - m.right() - 2
        if avail <= 0:
            # Layout not settled yet: show the full text; resizeEvent elides it later.
            self._label.setText(text)
        elif metrics.horizontalAdvance(text) <= avail:
            self._label.setText(text)
        else:
            self._label.setText(
                metrics.elidedText(text, Qt.TextElideMode.ElideRight, max(20, avail))
            )
        self._label.setToolTip(text)

    def sizeHint(self) -> QSize:
        """Size hint from the text itself, not the elided label, to avoid a shrink loop."""
        metrics = QFontMetrics(self._label.font())
        text_w = metrics.horizontalAdvance(self._current_text or " ")
        m = self._stack.contentsMargins()
        return QSize(
            text_w + m.left() + m.right() + 2,
            metrics.height() + m.top() + m.bottom(),
        )

    def minimumSizeHint(self) -> QSize:
        metrics = QFontMetrics(self._label.font())
        m = self._stack.contentsMargins()
        return QSize(
            24 + m.left() + m.right(),
            metrics.height() + m.top() + m.bottom(),
        )


# DragHandle: the title pill plus a drag area filling the rest of the bar. The drag
# area is mouse-transparent, so drags and double-clicks reach DragHandle.
class DragHandle(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dragHandle")
        # Without this a QWidget subclass ignores its stylesheet background.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)

        self.title_widget = EditableTitleLabel(self)
        layout.addWidget(self.title_widget, 0, Qt.AlignmentFlag.AlignVCenter)

        # Checklist progress ("1/4"), shown only while collapsed.
        self.progress_badge = QLabel(self)
        self.progress_badge.setObjectName("progressBadge")
        self.progress_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.progress_badge.hide()
        layout.addSpacing(4)
        layout.addWidget(self.progress_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        # Fills the rest of the bar; mouse-transparent so clicks reach DragHandle.
        self._drag_area = QWidget(self)
        self._drag_area.setObjectName("dragArea")
        self._drag_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._drag_area.setMinimumWidth(config.TITLE_DRAG_SPACER_WIDTH)
        self._drag_area.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        # Same: honour the stylesheet background.
        self._drag_area.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground, True
        )
        layout.addWidget(self._drag_area)

    def apply_bg(self, color: str):
        """Always 'transparent' since v4: only the title bar paints the bar colour, or the
        layers' opacity would stack. Styled directly; parent cascading is unreliable.
        """
        self.setStyleSheet(
            f"QWidget#dragHandle {{ background-color: {color}; }}"
        )
        self._drag_area.setStyleSheet(
            f"QWidget#dragArea {{ background-color: {color}; }}"
        )

    def set_progress(self, done: int, total: int, visible: bool, text_color: str, chip_bg: str):
        self.progress_badge.setText(f"{done}/{total}")
        self.progress_badge.setToolTip(f"{done} of {total} done")
        self.progress_badge.setStyleSheet(
            f"QLabel#progressBadge {{ color: {text_color}; background-color: {chip_bg};"
            f" border-radius: 7px; padding: 1px 7px; font-size: 8.5pt; font-weight: 700; }}"
        )
        self.progress_badge.setVisible(visible and total > 0)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            note = self.window()
            if isinstance(note, StickyNote):
                note.toggle_collapse()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)


# TitleBar: [+] [drag handle] [pin] [•••]
class TitleBar(QWidget):
    newNoteRequested = pyqtSignal()
    optionsRequested = pyqtSignal()
    titleCommitted = pyqtSignal(str)
    pinToggled = pyqtSignal(bool)              # emits the new pinned state

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("titleBar")
        # Paint our own background instead of the parent's body colour.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(config.TITLE_BAR_HEIGHT)
        # Remembered so the stylesheet can be rebuilt without re-passing everything.
        self._title_bg = "#FBE36E"
        # Paper opacity of the bar (0..1), kept in step with the note body.
        self._alpha = 1.0
        # Remembered so the thumbtack can be repainted on toggle.
        self._btn_color = "#1a1a1a"
        self._is_collapsed_style = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)  # tiny breathing room between chip buttons and pill

        self.add_btn = FloatingButton(
            "+",
            tone=FloatingButton.Tone.TITLE_BAR,
            font_css="font-size: 16pt;",
            tooltip="New note",
        )
        self.add_btn.clicked.connect(self.newNoteRequested.emit)
        layout.addWidget(self.add_btn)

        self.drag_handle = DragHandle(self)
        self.drag_handle.title_widget.committed.connect(self.titleCommitted.emit)
        layout.addWidget(self.drag_handle)

        # Checkable, so the pinned state shows at a glance. On native Wayland (no keep-above)
        # it stays visible but disabled, with a tooltip saying why.
        self.pin_btn = FloatingButton(
            "",
            tone=FloatingButton.Tone.TITLE_BAR,
            checkable=True,
            tooltip="Always on top",
        )
        if QApplication.platformName() != "xcb":
            self.pin_btn.setEnabled(False)
            self.pin_btn.setToolTip(
                "Always on top needs X11 or XWayland — unavailable in this session"
            )
        self.pin_btn.toggled.connect(self._refresh_pin_icon)
        self.pin_btn.toggled.connect(self.pinToggled.emit)
        layout.addWidget(self.pin_btn)

        self.opts_btn = FloatingButton(
            "•••",
            tone=FloatingButton.Tone.TITLE_BAR,
            font_css="font-size: 10pt;",
            tooltip="Options",
        )
        self.opts_btn.clicked.connect(self.optionsRequested.emit)
        layout.addWidget(self.opts_btn)

        # Pin and ••• appear on hover; they keep their space so the title doesn't jump.
        for btn in (self.pin_btn, self.opts_btn):
            policy = btn.sizePolicy()
            policy.setRetainSizeWhenHidden(True)
            btn.setSizePolicy(policy)

    def set_hover_chrome(self, show_pin: bool, show_opts: bool):
        self.pin_btn.setVisible(show_pin)
        self.opts_btn.setVisible(show_opts)

    def set_surface_alpha(self, alpha: float):
        if abs(alpha - self._alpha) < 0.002:
            return
        self._alpha = alpha
        self._rebuild_bar_style()

    def set_pinned(self, pinned: bool):
        """Show the pinned state without emitting pinToggled (used when restoring a note)."""
        self.pin_btn.blockSignals(True)
        self.pin_btn.setChecked(pinned)
        self.pin_btn.blockSignals(False)
        self._refresh_pin_icon()

    def _refresh_pin_icon(self, *_args):
        """Repaint the thumbtack for the current checked state and theme colour."""
        icon_px = max(14, int(FloatingButton.TITLE_BAR_SIZE * 0.66))
        self.pin_btn.setIcon(utils.create_pin_icon(
            self._btn_color, icon_px, filled=self.pin_btn.isChecked()
        ))
        self.pin_btn.setIconSize(QSize(icon_px, icon_px))

    def apply_colors(self, title_bg: str, btn_color: str, hover_overlay: str,
                     is_dark_theme: bool):
        """Restyle the bar, its buttons and the title pill for a theme."""
        self._title_bg = title_bg
        self._btn_color = btn_color
        self._rebuild_bar_style()
        FloatingButton.apply_theme_to_all(
            (self.add_btn, self.pin_btn, self.opts_btn), btn_color, is_dark_theme
        )
        # Repaint the thumbtack in the new button colour.
        self._refresh_pin_icon()
        # DragHandle styles itself and its drag area directly.
        self.drag_handle.apply_bg("transparent")
        self.drag_handle.title_widget.apply_text_style(btn_color, hover_overlay)

    def set_collapsed_style(self, collapsed: bool):
        """Rounded top only for an open note, rounded all round while collapsed."""
        if self._is_collapsed_style == collapsed:
            return
        self._is_collapsed_style = collapsed
        self._rebuild_bar_style()

    def _rebuild_bar_style(self):
        r = config.CORNER_RADIUS_PX
        bottom_radius = r if self._is_collapsed_style else 0
        self.setStyleSheet(f"""
            QWidget#titleBar {{
                background-color: {rgba(self._title_bg, self._alpha)};
                border-top-left-radius: {r}px;
                border-top-right-radius: {r}px;
                border-bottom-left-radius: {bottom_radius}px;
                border-bottom-right-radius: {bottom_radius}px;
            }}
        """)

    def set_title_text(self, text: str):
        """Show the title (elided inside the drag handle)."""
        self.drag_handle.title_widget.set_text(text)

    def set_title_editable(self, editable: bool):
        """Lock/unlock click-to-rename. Used when the note is collapsed."""
        self.drag_handle.title_widget.set_editable(editable)


# FormatBar: [B] [I] [U] [S] | [bullets] [checklist]
class FormatBar(QWidget):
    boldClicked      = pyqtSignal()
    italicClicked    = pyqtSignal()
    underlineClicked = pyqtSignal()
    strikeClicked    = pyqtSignal()
    bulletClicked    = pyqtSignal()
    checklistClicked = pyqtSignal()

    # Defaults — buttons scale around these via apply_size()
    BTN_MIN, BTN_DEFAULT, BTN_MAX = 24, 30, 34

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("formatBar")
        # Honour the stylesheet background.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._btn_size = self.BTN_DEFAULT
        self._last_colors = None    # remembered for re-apply after resize
        self._setup_ui()
        self.apply_size(self.BTN_DEFAULT)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(3)

        self.bold_btn      = self._make_btn("B", "boldBtn",      "font-weight: bold;",            "Bold",      "bold")
        self.italic_btn    = self._make_btn("I", "italicBtn",    "font-style: italic;",           "Italic",    "italic")
        self.underline_btn = self._make_btn("U", "underlineBtn", "text-decoration: underline;",   "Underline", "underline")
        self.strike_btn    = self._make_btn("S", "strikeBtn",    "text-decoration: line-through;", "Strikethrough", "strike")
        # Icon-only, so the tooltip and accessible name identify it. It also carries the
        # Tab hint, since Tab only nests inside a list.
        self.bullet_btn    = self._make_btn("", "bulletBtn",     "",                              "Bullet list", "bullet",
                                            hint="Tab to indent")
        # Also icon-only, same reasoning as the bullet button.
        self.checklist_btn = self._make_btn("", "checklistBtn",  "",                              "Checklist", "checklist",
                                            hint="click a box to tick it")

        # Thin divider between text styles and list types.
        self._divider = QFrame(self)
        self._divider.setObjectName("formatDivider")
        self._divider.setFixedSize(1, 18)

        layout.addStretch()
        for btn in self._buttons():
            layout.addWidget(btn)
            if btn is self.strike_btn:
                layout.addSpacing(3)
                layout.addWidget(self._divider, 0, Qt.AlignmentFlag.AlignVCenter)
                layout.addSpacing(3)
        layout.addStretch()

        self.bold_btn.clicked.connect(self.boldClicked.emit)
        self.italic_btn.clicked.connect(self.italicClicked.emit)
        self.underline_btn.clicked.connect(self.underlineClicked.emit)
        self.strike_btn.clicked.connect(self.strikeClicked.emit)
        self.bullet_btn.clicked.connect(self.bulletClicked.emit)
        self.checklist_btn.clicked.connect(self.checklistClicked.emit)

    def _buttons(self):
        return (self.bold_btn, self.italic_btn, self.underline_btn,
                self.strike_btn, self.bullet_btn, self.checklist_btn)

    @staticmethod
    def _make_btn(label: str, name: str, extra_css: str, tooltip: str = "",
                  shortcut_key: str = "", hint: str = "") -> FloatingButton:
        """`shortcut_key` indexes config.SHORTCUTS, so tooltips only show real bindings."""
        btn = FloatingButton(
            label,
            tone=FloatingButton.Tone.TOOLBAR,
            checkable=True,
            extra_css=extra_css,
            tooltip=tooltip,
            shortcut=config.SHORTCUTS.get(shortcut_key, ""),
            hint=hint,
        )
        btn.setObjectName(name)
        return btn

    def apply_size(self, btn_size: int):
        """Resize every toolbar button; StickyNote calls this as the note's width changes."""
        btn_size = max(self.BTN_MIN, min(self.BTN_MAX, int(btn_size)))
        if btn_size == self._btn_size:
            return
        self._btn_size = btn_size
        # Bar height = button height + small vertical padding
        self.setFixedHeight(btn_size + 6)
        for btn in self._buttons():
            btn.setFixedSize(btn_size, btn_size)
        # Re-apply the theme so fonts and icons pick up the new size.
        if self._last_colors is not None:
            self.apply_colors(*self._last_colors)

    def apply_colors(self, bg_color: str, btn_color: str, is_dark_theme: bool):
        """Restyle the bar, its buttons and the list icons."""
        self._last_colors = (bg_color, btn_color, is_dark_theme)

        # Font scales with the button: ~13px at 30, ~20px at 44.
        font_px = max(11, int(self._btn_size * 0.45))
        font_css = f"font-size: {font_px}px;"

        r = config.CORNER_RADIUS_PX
        self.setStyleSheet(f"""
            QWidget#formatBar {{
                background-color: {bg_color};
                border-bottom-left-radius: {r}px;
                border-bottom-right-radius: {r}px;
            }}
            QFrame#formatDivider {{ background-color: {rgba(btn_color, 0.25)}; border: none; }}
        """)
        for btn in self._buttons():
            btn.set_font_css(font_css)
        FloatingButton.apply_theme_to_all(self._buttons(), btn_color, is_dark_theme)

        # Painted list icons in the current button colour.
        icon_px = max(14, int(self._btn_size * 0.7))
        self.bullet_btn.setIcon(utils.create_bullet_list_icon(btn_color, icon_px))
        self.bullet_btn.setIconSize(QSize(icon_px, icon_px))
        self.checklist_btn.setIcon(utils.create_checklist_icon(btn_color, icon_px))
        self.checklist_btn.setIconSize(QSize(icon_px, icon_px))


# NoteFooter: "Edited 12 min ago" at rest, the FormatBar while typing in this note.
class NoteFooter(QWidget):
    def __init__(self, format_bar: "FormatBar", parent=None):
        super().__init__(parent)
        self.setObjectName("noteFooter")
        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)

        meta = QWidget(self)
        meta_layout = QHBoxLayout(meta)
        meta_layout.setContentsMargins(16, 0, 10, 2)
        meta_layout.setSpacing(6)
        self._clock = QLabel(meta)
        self._clock.setFixedSize(14, 14)
        self._label = QLabel(meta)
        self._label.setObjectName("editedLabel")
        meta_layout.addWidget(self._clock, 0, Qt.AlignmentFlag.AlignVCenter)
        meta_layout.addWidget(self._label, 0, Qt.AlignmentFlag.AlignVCenter)
        meta_layout.addStretch()

        self._stack.addWidget(meta)
        self._stack.addWidget(format_bar)
        self._stack.setCurrentIndex(0)

    def show_toolbar(self, show: bool):
        self._stack.setCurrentIndex(1 if show else 0)

    def set_edited_text(self, text: str):
        self._label.setText(text)

    def apply_colors(self, text_color: str):
        muted = rgba(text_color, 0.62)
        self._label.setStyleSheet(
            f"QLabel#editedLabel {{ color: {muted}; background: transparent; font-size: 9pt; }}"
        )
        self._clock.setPixmap(utils.line_icon("clock", muted_hex(text_color, 0.62), 14).pixmap(QSize(14, 14)))


def muted_hex(text_color: str, alpha: float) -> str:
    """`text_color` at `alpha`, as #AARRGGBB (what QColor accepts for icons)."""
    c = QColor(text_color)
    c.setAlphaF(alpha)
    return c.name(QColor.NameFormat.HexArgb)


# StickyNote: the frameless note window.
class StickyNote(QWidget):
    noteDeleted = pyqtSignal(str)
    newNoteRequested = pyqtSignal(str, int)   # emits (theme_name, opacity) to copy
    titleChanged = pyqtSignal(str, str)        # emits (note_id, new_title)
    receiveRequested = pyqtSignal(str)         # emits note_id (placement anchor)

    def __init__(
        self,
        note_id=None,
        content="",
        geometry_data=None,
        theme=config.DEFAULT_THEME,
        collapsed=False,
        title=None,
        last_edited=None,
        pinned=False,
        hide_from_dock=False,
        opacity=config.OPACITY_MAX,
        parent=None,
    ):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.note_id = note_id or str(uuid.uuid4())
        # Stable title; compositors use it with the app id to remember placement.
        self.setWindowTitle("Sticky Note")
        self._is_being_deleted = False
        self._theme_name = theme
        self._is_pinned = bool(pinned)
        self._hide_from_dock = bool(hide_from_dock)
        self._is_collapsed = False
        self._pre_collapse_height = 250
        self._options_panel = None
        self._anim_group = None

        # `_opacity` is the saved preference; `_surface_alpha` is what's painted now
        # (100% while hovered or typing).
        self._opacity = self._clamp_opacity(opacity)
        self._hovered = False
        self._typing = False
        self._surface_alpha = 1.0
        self._flashing = False
        self._theme = utils.get_theme(theme)
        self._alpha_anim = QVariantAnimation(self)
        self._alpha_anim.setDuration(config.OPACITY_FADE_MS)
        self._alpha_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._alpha_anim.valueChanged.connect(lambda v: self._apply_surface(float(v)))

        # None = still auto-titled from the first line until the user renames the note.
        self._title_is_default = (title is None)
        self._title = title or config.DEFAULT_NOTE_TITLE
        self._last_edited = last_edited or _now_iso()

        # Resize tracking
        self._resize_zone = _NONE
        self._is_resizing = False
        self._resize_start_global = None
        self._resize_start_geo = None

        # Drag tracking
        self._is_dragging = False
        self._drag_start_global = None
        self._drag_start_window_pos = None

        # Saves shortly after the last move/resize, so a quick quit loses nothing.
        self._save_debounce = QTimer(self)
        self._save_debounce.setSingleShot(True)
        self._save_debounce.setInterval(config.SAVE_DEBOUNCE_MS)
        self._save_debounce.timeout.connect(self._save)

        # True only while an edge resize is live (see _lock_size).
        self._size_unlocked = False
        self._relock_timer = QTimer(self)
        self._relock_timer.setSingleShot(True)
        self._relock_timer.setInterval(config.SIZE_RELOCK_DELAY_MS)
        self._relock_timer.timeout.connect(self._lock_size)

        self.setMinimumSize(config.MIN_NOTE_WIDTH, config.MIN_NOTE_HEIGHT)
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_autosave()

        # Enable mouse tracking on self and all children for resize cursor
        self.setMouseTracking(True)

        self._apply_theme(utils.get_theme(theme))

        # Prefer Qt's saveGeometry() bytes, which compositors honour at map time; the
        # (x, y, w, h) form is from an old version. The position is kept so it can be
        # re-applied after Mutter's initial placement on Wayland autostart.
        self._initial_position = None
        if isinstance(geometry_data, tuple) and len(geometry_data) == 4:
            x, y, w, h = geometry_data
            self.resize(w, h)
            self.move(x, y)
            self._initial_position = (x, y)
        elif geometry_data:
            # Some QSettings backends return QByteArray as str/bytes.
            if isinstance(geometry_data, str):
                geometry_data = QByteArray(geometry_data.encode("latin-1"))
            elif isinstance(geometry_data, (bytes, bytearray)):
                geometry_data = QByteArray(bytes(geometry_data))
            self.restoreGeometry(geometry_data)
            self._initial_position = (self.x(), self.y())
        else:
            self.resize(*default_note_size())

        # USPosition makes the WM honour our position on first map instead of placing the
        # window itself. Must run after the geometry is set and before show().
        if geometry_data is not None:
            xwm.mark_position_user_requested(self)

        # Locked before the first map, so the WM never sees a resizable note.
        self._lock_size()

        # States set before the first map apply at once (no flicker); showEvent re-asserts
        # them because Mutter clears them on unmap.
        xwm.set_initial_wm_states(
            self, above=self._is_pinned, skip_taskbar=self._hide_from_dock
        )
        # Never maximizable or tileable; changeEvent covers WMs that ignore the hint.
        xwm.disable_maximize(self)

        # Install event filter on children after UI is built
        for child in self.findChildren(QWidget):
            child.setMouseTracking(True)
            child.installEventFilter(self)

        # Load content (detect HTML vs plain text)
        if content:
            if content.strip().startswith("<"):
                self.text_edit.setHtml(content)
            else:
                self.text_edit.setPlainText(content)

        # Seed the title from the body while it's still auto-titled (also covers old notes).
        if self._title_is_default:
            self._title = derive_title_from_text(self.text_edit.toPlainText())
        self._refresh_title_display()

        # Connected only now, and gated on the modified flag, so loading a note never
        # changes its last_edited time.
        self.text_edit.document().setModified(False)
        self.text_edit.textChanged.connect(self._on_body_changed)

        # Start idle: the saved opacity, footer showing "Edited …".
        self._apply_surface(self._opacity / 100.0, force=True)
        self._refresh_chrome_state()
        self._refresh_progress()

        # The X11 keep-above state needs a mapped window, so showEvent applies it.
        if self._is_pinned:
            self.title_bar.set_pinned(True)

        if collapsed:
            QTimer.singleShot(0, self._collapse_immediately)

    def showEvent(self, event):
        """Re-assert keep-above once mapped (the WM ignores it for unmapped windows).
        Deferred one event-loop pass; repeating it is harmless.
        """
        super().showEvent(event)
        if self._is_pinned:
            QTimer.singleShot(0, lambda: xwm.set_always_on_top(self, True))
        if self._hide_from_dock:
            QTimer.singleShot(0, lambda: xwm.set_skip_taskbar(self, True))

    def changeEvent(self, event):
        """Undo any maximize/fullscreen the WM applies anyway: a maximized note ignores
        resizes, and collapsing it leaves an invisible window catching clicks.
        """
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            bad = Qt.WindowState.WindowMaximized | Qt.WindowState.WindowFullScreen
            if self.windowState() & bad:
                QTimer.singleShot(
                    0, lambda: self.setWindowState(self.windowState() & ~bad)
                )

    def set_hidden_from_dock(self, hidden: bool):
        """Apply the app-wide dock preference to this note."""
        self._hide_from_dock = bool(hidden)
        xwm.set_skip_taskbar(self, self._hide_from_dock)

    def _on_pin_toggled(self, pinned: bool):
        """Pin toggled by the user; the window is mapped, so it applies at once."""
        self._is_pinned = pinned
        xwm.set_always_on_top(self, pinned)
        self._save()

    def _reapply_initial_position(self):
        """Re-apply the saved position after Mutter's initial placement (Wayland autostart).
        Position only, so collapsed notes stay collapsed.
        """
        if self._initial_position is None:
            return
        self.move(*self._initial_position)

    # UI setup

    def _setup_ui(self):
        # Room for the drop shadow.
        outer = QVBoxLayout(self)
        g = config.SHADOW_GUTTER
        outer.setContentsMargins(g, g, g, g)
        outer.setSpacing(0)

        self.bg_widget = QWidget(self)
        self.bg_widget.setObjectName("noteBackground")

        bg_layout = QVBoxLayout(self.bg_widget)
        bg_layout.setContentsMargins(0, 0, 0, 0)
        bg_layout.setSpacing(0)

        self.title_bar = TitleBar(self.bg_widget)
        self.title_bar.pinToggled.connect(self._on_pin_toggled)
        self.title_bar.newNoteRequested.connect(
            lambda: self.newNoteRequested.emit(self._theme_name, self._opacity)
        )
        self.title_bar.optionsRequested.connect(self._show_options_panel)
        self.title_bar.titleCommitted.connect(self._on_title_committed)
        bg_layout.addWidget(self.title_bar)

        # bg_widget paints nothing; the bar and body paint their own colour, so no area of
        # a see-through note gets two translucent layers.
        self.body_widget = QWidget(self.bg_widget)
        self.body_widget.setObjectName("noteBody")
        self.body_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        body_layout = QVBoxLayout(self.body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        bg_layout.addWidget(self.body_widget)

        self.text_edit = NoteTextEdit(self.body_widget)
        self.text_edit.setFrameShape(QTextEdit.Shape.NoFrame)
        self.text_edit.setAcceptRichText(True)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Narrower than Qt's 40px default: notes are small.
        self.text_edit.document().setIndentWidth(config.LIST_INDENT_PX)
        body_layout.addWidget(self.text_edit)
        # Display-only styling of ticked items (see ChecklistHighlighter).
        self._highlighter = ChecklistHighlighter(self.text_edit.document())
        self.text_edit.highlighter = self._highlighter

        self.format_bar = FormatBar(self.body_widget)
        self.format_bar.boldClicked.connect(self._toggle_bold)
        self.format_bar.italicClicked.connect(self._toggle_italic)
        self.format_bar.underlineClicked.connect(self._toggle_underline)
        self.format_bar.strikeClicked.connect(self._toggle_strike)
        self.format_bar.bulletClicked.connect(self._toggle_bullet_list)
        self.format_bar.checklistClicked.connect(self._toggle_checklist)
        self.footer = NoteFooter(self.format_bar, self.body_widget)
        # Exactly the toolbar's height: all spare room belongs to the text.
        self.footer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.footer.setFixedHeight(self.format_bar.height())
        body_layout.addWidget(self.footer)

        self._edited_timer = QTimer(self)
        self._edited_timer.setInterval(config.EDITED_LABEL_REFRESH_MS)
        self._edited_timer.timeout.connect(self._refresh_edited_label)
        self._edited_timer.start()

        # Reflect cursor's current formatting in the toolbar's checked state.
        self.text_edit.cursorPositionChanged.connect(self._refresh_format_bar)
        self.text_edit.currentCharFormatChanged.connect(
            lambda _fmt: self._refresh_format_bar()
        )
        # The body-edit handler is connected after the content loads (see __init__).

        outer.addWidget(self.bg_widget)

        # Kept so collapse can swap to a tighter shadow.
        self._bg_shadow = QGraphicsDropShadowEffect(self)
        self.bg_widget.setGraphicsEffect(self._bg_shadow)
        self._apply_expanded_shadow()

    def _setup_shortcuts(self):
        # QTextEdit doesn't bind Ctrl+B/I/U itself. WidgetWithChildren so they still fire
        # when a child (e.g. the scroll bar) has focus.
        ctx = Qt.ShortcutContext.WidgetWithChildrenShortcut
        for key, slot in (
            ("bold",      self._toggle_bold),
            ("italic",    self._toggle_italic),
            ("underline", self._toggle_underline),
            ("strike",    self._toggle_strike),
            ("bullet",    self._toggle_bullet_list),
            ("checklist", self._toggle_checklist),
        ):
            sc = QShortcut(QKeySequence(config.SHORTCUTS[key]), self.text_edit)
            sc.setContext(ctx)
            sc.activated.connect(slot)

        # Ctrl+N works anywhere in the note window (title editor included) and makes the
        # same note the + button does.
        new_sc = QShortcut(QKeySequence(config.SHORTCUTS["new_note"]), self)
        new_sc.setContext(Qt.ShortcutContext.WindowShortcut)
        new_sc.activated.connect(
            lambda: self.newNoteRequested.emit(self._theme_name, self._opacity)
        )

    def _setup_autosave(self):
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(config.AUTOSAVE_INTERVAL_MS)
        self._autosave_timer.timeout.connect(self._save)
        self._autosave_timer.start()

    # Theme

    def _apply_theme(self, theme: dict):
        self._theme = theme
        title_bg = theme["title"]
        text_color = theme["text"]

        # Dark themes (charcoal) need light button tints and hover overlays.
        is_dark = bool(theme.get("dark", QColor(text_color).lightness() > 160))
        btn_color = "#D6D6D6" if is_dark else "#4A4A4A"
        self._btn_color = btn_color
        hover_overlay = "rgba(255, 255, 255, 0.18)" if is_dark else "rgba(0, 0, 0, 0.10)"
        # Translucent thumb, so it reads as a deeper shade of the note.
        if is_dark:
            thumb, thumb_hover, thumb_pressed = (
                "rgba(255, 255, 255, 0.22)", "rgba(255, 255, 255, 0.35)",
                "rgba(255, 255, 255, 0.45)",
            )
        else:
            thumb, thumb_hover, thumb_pressed = (
                "rgba(0, 0, 0, 0.18)", "rgba(0, 0, 0, 0.30)",
                "rgba(0, 0, 0, 0.40)",
            )

        # bg_widget paints nothing itself (see _setup_ui); the bar and body do.
        self.bg_widget.setStyleSheet("QWidget#noteBackground { background: transparent; }")
        self.title_bar.apply_colors(title_bg, btn_color, hover_overlay, is_dark)
        # The format bar sits on the paper now, not on a separate coloured band.
        self.format_bar.apply_colors("transparent", btn_color, is_dark)
        self.footer.apply_colors(text_color)
        self._highlighter.set_ink(text_color)
        self._highlighter.rehighlight()
        self.text_edit.setStyleSheet(f"""
            NoteTextEdit {{
                background-color: transparent;
                color: {text_color};
                border: none;
                padding: 6px 8px 2px 8px;
            }}
            /* Overlay-style scrollbar: transparent track, no arrow buttons,
               thin rounded thumb. The 4px right margin keeps the thumb out
               of the resize band at the note's right edge
               (RESIZE_ZONE - SHADOW_GUTTER), so grabbing it never resizes. */
            QScrollBar:vertical {{
                background: transparent;
                width: 12px;
                margin: 4px 4px 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {thumb};
                border-radius: 3px;
                min-height: 28px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {thumb_hover};
            }}
            QScrollBar::handle:vertical:pressed {{
                background: {thumb_pressed};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                border: none;
                background: none;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)
        # Same font as before: it's written into toHtml(), so saved notes stay identical.
        font = QFont()
        font.setFamilies(["Segoe UI", "Ubuntu", "Sans Serif"])
        font.setPointSize(config.FONT_SIZE)
        self.text_edit.setFont(font)
        self._apply_surface(self._surface_alpha, force=True)
        self._refresh_progress()

    # Opacity, hover chrome and the footer

    @staticmethod
    def _clamp_opacity(value) -> int:
        try:
            value = int(value)
        except (TypeError, ValueError):
            return config.OPACITY_MAX
        step = config.OPACITY_STEP
        value = int(round(value / step) * step)
        return max(config.OPACITY_MIN, min(config.OPACITY_MAX, value))

    def _apply_surface(self, alpha: float, force: bool = False):
        """Paint the paper at `alpha` (0..1). The shadow thins with it, or it would show
        through a see-through note as a grey smudge.
        """
        if not force and abs(alpha - self._surface_alpha) < 0.002:
            return
        self._surface_alpha = alpha
        theme = self._theme
        r = config.CORNER_RADIUS_PX
        self.body_widget.setStyleSheet(f"""
            QWidget#noteBody {{
                background-color: {rgba(theme['bg'], alpha)};
                border-bottom-left-radius: {r}px;
                border-bottom-right-radius: {r}px;
            }}
        """)
        self.title_bar.set_surface_alpha(alpha)
        surface = QColor(theme["bg"])
        surface.setAlphaF(alpha)
        self.text_edit.set_paint_colors(surface, QColor(theme["text"]))
        if not self._flashing:
            self._apply_shadow()

    def _apply_shadow(self):
        profile = config.SHADOW_BODY_COLLAPSED if self._is_collapsed else config.SHADOW_BODY_EXPANDED
        blur, offset_y, alpha = profile
        k = self._surface_alpha ** 3      # 1.0 solid -> ~0.34 at 70% -> ~0.13 at 50%
        self._bg_shadow.setBlurRadius(blur)
        self._bg_shadow.setOffset(0, offset_y)
        self._bg_shadow.setColor(QColor(0, 0, 0, int(alpha * k)))

    def _refresh_chrome_state(self):
        """Recompute the chrome for the pointer/keyboard state: chips, footer, opacity."""
        panel_open = self._options_panel is not None
        self.title_bar.set_hover_chrome(
            show_pin=self._hovered or self._is_pinned or panel_open,
            show_opts=self._hovered or panel_open,
        )
        self.footer.show_toolbar(self._typing)
        if not self._typing:
            self._refresh_edited_label()
        # While the ••• menu is open, preview the idle look so the slider shows its effect.
        solid = (self._hovered or self._typing) and not panel_open
        target = 1.0 if solid else self._opacity / 100.0
        if abs(target - self._surface_alpha) < 0.002:
            return
        self._alpha_anim.stop()
        self._alpha_anim.setStartValue(self._surface_alpha)
        self._alpha_anim.setEndValue(target)
        self._alpha_anim.start()

    def _refresh_edited_label(self):
        self.footer.set_edited_text(edited_phrase(self._last_edited))

    def _refresh_progress(self):
        done, total = checklist_progress(self.text_edit.document())
        chip = "rgba(255, 255, 255, 0.14)" if self._theme.get("dark") else "rgba(255, 255, 255, 0.55)"
        self.title_bar.drag_handle.set_progress(
            done, total, self._is_collapsed, self._btn_color, chip
        )

    def enterEvent(self, event):   # noqa: N802
        super().enterEvent(event)
        self._hovered = True
        self._refresh_chrome_state()

    def leaveEvent(self, event):   # noqa: N802
        super().leaveEvent(event)
        self._hovered = False
        self._refresh_chrome_state()

    def _set_opacity(self, value: int):
        value = self._clamp_opacity(value)
        if value == self._opacity:
            return
        self._opacity = value
        self._refresh_chrome_state()
        if hasattr(self, "_save_debounce") and not self._is_being_deleted:
            self._save_debounce.start()

    def flash(self):
        """Brief glow so a note picked from All notes or the tray stands out."""
        self._flashing = True
        self._bg_shadow.setColor(QColor(255, 255, 255, 235))
        self._bg_shadow.setBlurRadius(30)
        self._bg_shadow.setOffset(0, 0)

        def _done():
            self._flashing = False
            self._apply_shadow()
        QTimer.singleShot(config.FLASH_MS, _done)

    # Options panel

    def _show_options_panel(self):
        # Toggle: if already open, close it
        if self._options_panel is not None:
            self._close_options_panel()
            return
        # Parented to the note so Wayland has a surface to anchor the popup to.
        panel = OptionsPanel(
            theme=self._theme_name,
            opacity=self._opacity,
            pinned=self._is_pinned,
            pin_available=self.title_bar.pin_btn.isEnabled(),
            collapsed=self._is_collapsed,
            parent=self,
        )
        panel.themeSelected.connect(self._change_theme)
        panel.opacityChanged.connect(self._set_opacity)
        panel.pinToggleRequested.connect(self.title_bar.pin_btn.toggle)
        panel.collapseToggleRequested.connect(self.toggle_collapse)
        panel.deleteRequested.connect(self._handle_delete)
        panel.shareRequested.connect(self._share)
        panel.receiveRequested.connect(self._request_receive)
        panel.dismissed.connect(self._on_panel_dismissed)

        # Beside the note, not over it — so the opacity preview is visible.
        panel.place_beside(self)
        self._options_panel = panel
        panel.show()
        self._refresh_chrome_state()

    def _close_options_panel(self):
        """Close the panel and clear the reference now, so a quick reopen gets a new panel."""
        if self._options_panel is not None:
            old = self._options_panel
            self._options_panel = None
            old.close()

    def _on_panel_dismissed(self, panel):
        # Ignore a late dismissal from a panel that has already been replaced.
        if self._options_panel is panel:
            self._options_panel = None
            # The popup grabbed the pointer, so ask where it is instead of waiting for Enter.
            self._hovered = self.geometry().contains(QCursor.pos())
            self._refresh_chrome_state()

    def _change_theme(self, theme_name: str):
        self._theme_name = theme_name
        self._apply_theme(utils.get_theme(theme_name))
        self._close_options_panel()
        self._save()

    # Share / Receive (see sharing.py)

    def _share(self):
        """Put this note on the clipboard as shareable text."""
        QApplication.clipboard().setText(sharing.encode_note(
            title=self._title,
            title_is_auto=self._title_is_default,
            theme=self._theme_name,
            body_html=self.text_edit.toHtml(),
        ))
        if self._options_panel is not None:
            self._options_panel.show_share_copied()

    def _request_receive(self):
        """Receive creates a new note, so hand it to TrayManager with this note as the anchor."""
        self._close_options_panel()
        self.receiveRequested.emit(self.note_id)

    # Delete

    def _handle_delete(self):
        self._close_options_panel()
        self._is_being_deleted = True
        self.noteDeleted.emit(self.note_id)
        self.close()
        # close() only hides; free the widget, its timers and shortcuts too.
        self.deleteLater()

    # Collapse / expand

    def _apply_expanded_shadow(self):
        """Roomy soft shadow for an open note (config.SHADOW_BODY_EXPANDED)."""
        self._apply_shadow()

    def _apply_collapsed_shadow(self):
        """Tighter shadow while collapsed, so it fits the small window's gutter."""
        self._apply_shadow()

    def toggle_collapse(self):
        if self._is_collapsed:
            self._expand()
        else:
            self._collapse()

    def _collapse(self):
        self._pre_collapse_height = self.height()
        self._is_collapsed = True
        # Commit any rename in progress, then lock the title while collapsed.
        self.title_bar.set_title_editable(False)
        # Round all four corners and switch to the collapsed shadow.
        self.title_bar.set_collapsed_style(True)
        self._apply_collapsed_shadow()
        self._refresh_progress()

        # Title bar plus the shadow gutters, or the bar gets clipped.
        collapsed_h = config.TITLE_BAR_HEIGHT + 2 * config.SHADOW_GUTTER

        # Animate min and max together so the size stays locked on every frame.
        self._lock_size()
        group = QParallelAnimationGroup(self)
        for prop in (b"minimumHeight", b"maximumHeight"):
            anim = QPropertyAnimation(self, prop)
            anim.setDuration(config.COLLAPSE_ANIMATION_MS)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(self.height())
            anim.setEndValue(collapsed_h)
            group.addAnimation(anim)

        def _hide_body():
            self.body_widget.hide()
            self._lock_size()
        group.finished.connect(_hide_body)
        group.start()
        self._anim_group = group    # prevent GC

    def _expand(self):
        self._is_collapsed = False
        target_h = max(self._pre_collapse_height, config.MIN_NOTE_HEIGHT)
        # Re-enable title click-to-rename now that the body is back.
        self.title_bar.set_title_editable(True)
        # Square the bottom corners again and restore the body shadow.
        self.title_bar.set_collapsed_style(False)
        self._apply_expanded_shadow()

        self.body_widget.show()
        self._refresh_progress()

        # Same locked animation as _collapse.
        self._lock_size()
        group = QParallelAnimationGroup(self)
        for prop in (b"minimumHeight", b"maximumHeight"):
            anim = QPropertyAnimation(self, prop)
            anim.setDuration(config.COLLAPSE_ANIMATION_MS)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(self.height())
            anim.setEndValue(target_h)
            group.addAnimation(anim)

        group.finished.connect(self._lock_size)
        group.start()
        self._anim_group = group

    def _collapse_immediately(self):
        """Apply collapsed state on load without animation."""
        collapsed_h = config.TITLE_BAR_HEIGHT + 2 * config.SHADOW_GUTTER
        self._is_collapsed = True
        self.title_bar.set_title_editable(False)
        self.title_bar.set_collapsed_style(True)
        self._apply_collapsed_shadow()
        self.body_widget.hide()
        self._refresh_progress()
        self._lock_size(height=collapsed_h)

    # Formatting and lists

    def _toggle_bold(self):
        fmt = self.text_edit.currentCharFormat()
        is_bold = fmt.fontWeight() == QFont.Weight.Bold
        fmt.setFontWeight(QFont.Weight.Normal if is_bold else QFont.Weight.Bold)
        self.text_edit.mergeCurrentCharFormat(fmt)

    def _toggle_italic(self):
        fmt = self.text_edit.currentCharFormat()
        fmt.setFontItalic(not fmt.fontItalic())
        self.text_edit.mergeCurrentCharFormat(fmt)

    def _toggle_underline(self):
        fmt = self.text_edit.currentCharFormat()
        fmt.setFontUnderline(not fmt.fontUnderline())
        self.text_edit.mergeCurrentCharFormat(fmt)

    def _toggle_strike(self):
        fmt = self.text_edit.currentCharFormat()
        fmt.setFontStrikeOut(not fmt.fontStrikeOut())
        self.text_edit.mergeCurrentCharFormat(fmt)

    @staticmethod
    def _new_list_format() -> QTextListFormat:
        list_fmt = QTextListFormat()
        list_fmt.setStyle(QTextListFormat.Style.ListDisc)
        list_fmt.setIndent(1)
        return list_fmt

    def _expand_to_list_region(self, cursor: QTextCursor) -> QTextCursor:
        """Widen `cursor` to the whole contiguous run of list blocks, so a list is never half
        checkboxes, half bullets. Walks blocks because nested levels are separate QTextLists.
        """
        block = cursor.block()
        if block.textList() is None:
            return cursor

        first = block
        while first.previous().isValid() and first.previous().textList() is not None:
            first = first.previous()
        last = block
        while last.next().isValid() and last.next().textList() is not None:
            last = last.next()

        region = QTextCursor(self.text_edit.document())
        region.setPosition(first.position())
        region.setPosition(
            last.position() + last.length() - 1,
            QTextCursor.MoveMode.KeepAnchor,
        )
        return region

    def _set_markers(self, cursor: QTextCursor, marker):
        """Apply `marker` to every block the cursor spans."""
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        walker = QTextCursor(cursor)
        walker.setPosition(start)
        while True:
            fmt = walker.blockFormat()
            fmt.setMarker(marker)
            walker.setBlockFormat(fmt)
            if walker.position() >= end:
                break
            if not walker.movePosition(QTextCursor.MoveOperation.NextBlock):
                break

    # List buttons: bullet <-> checklist converts the whole list; removing items only
    # affects the selection.

    def _toggle_bullet_list(self):
        cursor = self.text_edit.textCursor()
        if _cursor_in_checklist(cursor):
            # Checklist -> bullets: drop the markers, keep the list.
            self._set_markers(self._expand_to_list_region(cursor), _MARKER_NONE)
        elif cursor.currentList():
            self._remove_list(cursor)
        else:
            cursor.createList(self._new_list_format())
        self._highlighter.rehighlight()
        self._refresh_format_bar()

    def _toggle_checklist(self):
        """Mirror of _toggle_bullet_list, for checkbox lists."""
        cursor = self.text_edit.textCursor()
        if _cursor_in_checklist(cursor):
            self._remove_list(cursor)
        elif cursor.currentList():
            # Bullet list -> checklist. New boxes start unticked.
            self._set_markers(
                self._expand_to_list_region(cursor), _MARKER_UNCHECKED
            )
        else:
            cursor.createList(self._new_list_format())
            self._set_markers(self.text_edit.textCursor(), _MARKER_UNCHECKED)
        self._highlighter.rehighlight()
        self._refresh_format_bar()

    def _refresh_format_bar(self):
        """Sync FormatBar checked state with the cursor's current formatting."""
        fmt = self.text_edit.currentCharFormat()
        cursor = self.text_edit.textCursor()
        self.format_bar.bold_btn.setChecked(fmt.fontWeight() == QFont.Weight.Bold)
        self.format_bar.italic_btn.setChecked(fmt.fontItalic())
        self.format_bar.underline_btn.setChecked(fmt.fontUnderline())
        self.format_bar.strike_btn.setChecked(fmt.fontStrikeOut())
        # The two list buttons are mutually exclusive.
        in_checklist = _cursor_in_checklist(cursor)
        self.format_bar.bullet_btn.setChecked(
            cursor.currentList() is not None and not in_checklist
        )
        self.format_bar.checklist_btn.setChecked(in_checklist)

    def _refresh_title_display(self):
        """Push the current `_title` value to the title bar."""
        self.title_bar.set_title_text(self._title)

    def _on_body_changed(self):
        """A user edit: update last_edited and, while auto-titled, the title."""
        doc = self.text_edit.document()
        # Loading and re-highlighting also emit textChanged; only real edits set modified.
        if not doc.isModified():
            return
        doc.setModified(False)
        self._last_edited = _now_iso()
        self._refresh_edited_label()
        self._refresh_progress()
        if self._title_is_default:
            new_title = derive_title_from_text(self.text_edit.toPlainText())
            if new_title != self._title:
                self._title = new_title
                self._refresh_title_display()
                self.titleChanged.emit(self.note_id, self._title)
        # Debounce save so a typing burst doesn't spam QSettings
        if hasattr(self, "_save_debounce") and not self._is_being_deleted:
            self._save_debounce.start()

    def _on_title_committed(self, raw_text: str):
        """Commit a title from the editor: trimmed and capped; empty keeps the old title."""
        cleaned = raw_text.strip()[:config.MAX_TITLE_LENGTH]
        if not cleaned:
            # Empty input: keep the previous title.
            self._refresh_title_display()
            return
        if cleaned == self._title and not self._title_is_default:
            return  # no-op commit
        self._title = cleaned
        self._title_is_default = False
        self._last_edited = _now_iso()
        self._refresh_title_display()
        self.titleChanged.emit(self.note_id, self._title)
        if hasattr(self, "_save_debounce") and not self._is_being_deleted:
            self._save_debounce.start()

    def _remove_list(self, cursor: QTextCursor):
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        cursor.setPosition(start)
        while True:
            block = cursor.block()
            lst = block.textList()
            if lst:
                lst.remove(block)
            fmt = block.blockFormat()
            fmt.setIndent(0)
            # Clear the checkbox marker too, or it keeps painting after the list is gone.
            fmt.setMarker(_MARKER_NONE)
            cursor.setBlockFormat(fmt)
            if cursor.position() >= end:
                break
            if not cursor.movePosition(QTextCursor.MoveOperation.NextBlock):
                break

    # Resizing (8 zones)

    def _get_resize_zone(self, local: QPoint) -> int:
        """Resize zone at `local` (window coords), or _NONE. Only inside the visible note:
        the transparent shadow gutter must not start resizes (issue #24).
        """
        x, y = local.x(), local.y()
        g = config.SHADOW_GUTTER
        vis_left, vis_top = g, g
        vis_right, vis_bottom = self.width() - g, self.height() - g

        # Outside the visible note: shadow only. Never a resize zone.
        if not (vis_left <= x < vis_right and vis_top <= y < vis_bottom):
            return _NONE

        # Original comparisons kept exactly: the far bands are 1px narrower, and any wider
        # would reach the format bar's buttons.
        z = config.RESIZE_ZONE
        band = z - g
        left   = x < vis_left + band
        right  = x > vis_right - band
        top    = y < vis_top + band
        bottom = y > vis_bottom - band
        if top    and left:  return _NW
        if top    and right: return _NE
        if bottom and left:  return _SW
        if bottom and right: return _SE
        if top:    return _N
        if bottom: return _S
        if left:   return _W
        if right:  return _E
        return _NONE

    # Size lock

    def _lock_size(self, width=None, height=None):
        """Set min == max == the note's size, so no WM or tiling extension can resize, tile
        or maximize it (a tiled note breaks collapse). Edge drags unlock it briefly.
        """
        self._relock_timer.stop()
        self._size_unlocked = False
        w = self.width() if width is None else width
        h = self.height() if height is None else height
        self.setFixedSize(w, h)
        # Flush the new size hints now; Qt can buffer them for up to a second.
        QApplication.sync()

    def _unlock_size_for_resize(self):
        """Lift the lock for an edge drag. Re-locked once resizing goes quiet, or when a
        title drag starts. A collapsed note keeps its height fixed.
        """
        if self._is_collapsed:
            self.setMinimumSize(config.MIN_NOTE_WIDTH, self.height())
            self.setMaximumSize(16_777_215, self.height())
        else:
            self.setMinimumSize(config.MIN_NOTE_WIDTH, config.MIN_NOTE_HEIGHT)
            self.setMaximumSize(16_777_215, 16_777_215)
        self._size_unlocked = True
        self._relock_timer.start()

    # Mouse dispatch (eventFilter and the window's own events)

    def _try_start_resize(self, gpos: QPoint) -> bool:
        """If gpos is in a resize zone, start a resize and return True."""
        zone = self._get_resize_zone(self.mapFromGlobal(gpos))
        if zone == _NONE:
            return False
        self._unlock_size_for_resize()
        # The WM's native resize handles every edge correctly.
        wh = self.windowHandle()
        if wh is not None and wh.startSystemResize(_EDGES[zone]):
            return True
        # Fallback: manual resize (edges only — corners get top wrong)
        self._is_resizing = True
        self._resize_zone = zone
        self._resize_start_global = gpos
        self._resize_start_geo = self.geometry()
        self.setCursor(_CURSORS[zone])
        return True

    def _try_start_drag(self, gpos: QPoint, obj) -> bool:
        """If pressed on a DragHandle, start a drag and return True."""
        if not isinstance(obj, DragHandle):
            return False
        # Never drag unlocked: a drag can reach a screen edge.
        if self._size_unlocked:
            self._lock_size()
        wh = self.windowHandle()
        if wh is not None and wh.startSystemMove():
            return True
        self._is_dragging = True
        self._drag_start_global = gpos
        self._drag_start_window_pos = self.pos()
        return True

    def _handle_mouse_move(self, gpos: QPoint) -> bool:
        if self._is_resizing:
            self._do_resize(gpos)
            return True
        if self._is_dragging:
            delta = gpos - self._drag_start_global
            self.move(self._drag_start_window_pos + delta)
            return True
        # Hover: update cursor to indicate resize affordance
        zone = self._get_resize_zone(self.mapFromGlobal(gpos))
        if zone != _NONE:
            self.setCursor(_CURSORS[zone])
        else:
            self.unsetCursor()
        return False

    def _handle_mouse_release(self) -> bool:
        if self._is_resizing:
            self._is_resizing = False
            self._resize_zone = _NONE
            self.unsetCursor()
            # The manual fallback does see the release, so lock right away.
            self._lock_size()
            return True
        if self._is_dragging:
            self._is_dragging = False
            return True
        return False

    def eventFilter(self, obj, event):
        t = event.type()
        if obj is self.text_edit and t in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            # The ••• popup takes focus while open; don't hide the toolbar for that.
            if event.reason() != Qt.FocusReason.PopupFocusReason:
                typing = t == QEvent.Type.FocusIn
                if typing != self._typing:
                    self._typing = typing
                    self._refresh_chrome_state()
        if t == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            gpos = event.globalPosition().toPoint()
            if self._try_start_resize(gpos):
                return True
            if self._try_start_drag(gpos, obj):
                return True
        elif t == QEvent.Type.MouseMove:
            if self._handle_mouse_move(event.globalPosition().toPoint()):
                return True
        elif t == QEvent.Type.MouseButtonRelease:
            if self._handle_mouse_release():
                return True
        return super().eventFilter(obj, event)

    # Events in the shadow gutter, which no child covers.

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._try_start_resize(event.globalPosition().toPoint()):
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._handle_mouse_move(event.globalPosition().toPoint()):
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._handle_mouse_release():
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # Move/resize: save, and scale the format bar

    def moveEvent(self, event):
        super().moveEvent(event)
        # Save shortly after the move ends.
        if hasattr(self, "_save_debounce") and not self._is_being_deleted:
            self._save_debounce.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Scale format-bar buttons proportionally to note width
        if hasattr(self, "format_bar"):
            # 30px buttons at ~320px window; clamped by FormatBar to [24, 34]
            btn = int(self.width() / 10.5)
            self.format_bar.apply_size(btn)
            self.footer.setFixedHeight(self.format_bar.height())
        # Still edge-resizing: push the re-lock back until the drag goes quiet.
        if getattr(self, "_size_unlocked", False):
            self._relock_timer.start()
        # Save size after the user finishes resizing
        if hasattr(self, "_save_debounce") and not self._is_being_deleted:
            self._save_debounce.start()

    def _do_resize(self, gpos: QPoint):
        dx = gpos.x() - self._resize_start_global.x()
        dy = gpos.y() - self._resize_start_global.y()
        geo = QRect(self._resize_start_geo)
        min_w, min_h = config.MIN_NOTE_WIDTH, config.MIN_NOTE_HEIGHT
        z = self._resize_zone

        if z in (_E, _NE, _SE):
            geo.setRight(max(geo.left() + min_w, geo.right() + dx))
        if z in (_W, _NW, _SW):
            geo.setLeft(min(geo.right() - min_w, geo.left() + dx))
        if z in (_S, _SE, _SW):
            geo.setBottom(max(geo.top() + min_h, geo.bottom() + dy))
        if z in (_N, _NE, _NW):
            geo.setTop(min(geo.bottom() - min_h, geo.top() + dy))

        self.setGeometry(geo)

    # Persistence

    # Read-only accessors used by TrayManager when building its menu
    @property
    def title(self) -> str:
        return self._title

    @property
    def last_edited(self) -> str:
        return self._last_edited

    @property
    def theme_name(self) -> str:
        return self._theme_name

    @property
    def opacity(self) -> int:
        return self._opacity

    @property
    def is_pinned(self) -> bool:
        return self._is_pinned

    def plain_text(self) -> str:
        return self.text_edit.toPlainText()

    def _save(self):
        if self._is_being_deleted:
            return
        settings = QSettings(config.ORG_NAME, config.APP_NAME)
        settings.beginGroup("notes")
        settings.setValue(f"{self.note_id}/content",     self.text_edit.toHtml())
        # Qt's encoded geometry: compositors honour it at map time, unlike move().
        settings.setValue(f"{self.note_id}/geometry",    self.saveGeometry())
        settings.setValue(f"{self.note_id}/theme",       self._theme_name)
        settings.setValue(f"{self.note_id}/collapsed",   self._is_collapsed)
        settings.setValue(f"{self.note_id}/title",       self._title)
        settings.setValue(f"{self.note_id}/last_edited", self._last_edited)
        settings.setValue(f"{self.note_id}/pinned",      self._is_pinned)
        # Added in v4; notes without it load fully opaque.
        settings.setValue(f"{self.note_id}/opacity",     self._opacity)
        settings.endGroup()

    def closeEvent(self, event):
        if not self._is_being_deleted:
            self._save()
        super().closeEvent(event)
