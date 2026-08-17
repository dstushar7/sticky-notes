# stickynotes/note_window.py

import uuid
from datetime import datetime, timezone
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel,
    QLineEdit, QStackedLayout, QSizePolicy, QGraphicsDropShadowEffect,
    QApplication, QDialog, QCheckBox, QFrame,
)
from PyQt6.QtCore import (
    QSettings, pyqtSignal, Qt, QPoint, QRect, QSize, QByteArray, QUrl,
    QPropertyAnimation, QParallelAnimationGroup, QEasingCurve,
    QEvent, QTimer,
)
from PyQt6.QtGui import (
    QColor, QTextListFormat, QTextCursor, QKeySequence, QShortcut, QFont,
    QFontMetrics, QDesktopServices,
)

from . import __version__
from . import config
from . import utils
from . import autostart
from . import xwm
from .widgets import FloatingButton


def _now_iso() -> str:
    """Timezone-aware UTC ISO-8601 timestamp used for last_edited."""
    return datetime.now(timezone.utc).isoformat()


def derive_title_from_text(plain_text: str) -> str:
    """Title from the first non-empty body line, capped at AUTO_SEED_WORD_COUNT
    words and MAX_TITLE_LENGTH characters. Falls back to DEFAULT_NOTE_TITLE."""
    if plain_text:
        for line in plain_text.splitlines():
            stripped = line.strip()
            if stripped:
                words = stripped.split()[:config.AUTO_SEED_WORD_COUNT]
                derived = " ".join(words)[:config.MAX_TITLE_LENGTH].strip()
                if derived:
                    return derived
    return config.DEFAULT_NOTE_TITLE


# Bullet styles cycled by sublist depth so nested levels are visually distinct.
_LIST_STYLES = (
    QTextListFormat.Style.ListDisc,
    QTextListFormat.Style.ListCircle,
    QTextListFormat.Style.ListSquare,
)


def _style_for_indent(indent: int) -> QTextListFormat.Style:
    return _LIST_STYLES[(max(1, indent) - 1) % len(_LIST_STYLES)]

# ---------------------------------------------------------------------------
# Resize zone ids
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# NoteTextEdit — Shift+Enter list-break, Tab/Shift+Tab sublist nesting
# ---------------------------------------------------------------------------
class NoteTextEdit(QTextEdit):
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

        super().keyPressEvent(event)

    def _break_out_of_list(self):
        cursor = self.textCursor()
        cursor.insertBlock()
        block = cursor.block()
        lst = block.textList()
        if lst:
            lst.remove(block)
        fmt = cursor.blockFormat()
        fmt.setIndent(0)
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
            cursor.setBlockFormat(bf)
            return

        new_fmt = QTextListFormat()
        new_fmt.setIndent(new_indent)
        new_fmt.setStyle(_style_for_indent(new_indent))
        cursor.createList(new_fmt)


# ---------------------------------------------------------------------------
# _DeleteButton — destructive action with a two-click confirm pattern.
#
# First click arms the button: text + visual state change to "Confirm Delete?"
# in a fully red filled style. A second click within CONFIRM_WINDOW_MS emits
# `confirmed`; if the timeout expires (or the panel closes) the button reverts
# to its idle state. The two states are visually distinct on purpose — the
# armed style is loud so the user can't miss that the next click is real.
# ---------------------------------------------------------------------------
class _DeleteButton(QPushButton):
    confirmed = pyqtSignal()

    _IDLE_LABEL = "🗑  Delete Note"
    _ARMED_LABEL = "✓  Click again to confirm"

    def __init__(self, parent=None):
        super().__init__(self._IDLE_LABEL, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # No keyboard focus; this is purely a pointer action inside a popup.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._armed = False
        self._disarm_timer = QTimer(self)
        self._disarm_timer.setSingleShot(True)
        self._disarm_timer.setInterval(config.DELETE_CONFIRM_WINDOW_MS)
        self._disarm_timer.timeout.connect(self._disarm)

        self.clicked.connect(self._on_clicked)
        self._apply_idle_style()

    def _on_clicked(self):
        if self._armed:
            self._disarm_timer.stop()
            self.confirmed.emit()
        else:
            self._arm()

    def _arm(self):
        self._armed = True
        self.setText(self._ARMED_LABEL)
        self._apply_armed_style()
        self._disarm_timer.start()

    def _disarm(self):
        self._armed = False
        self.setText(self._IDLE_LABEL)
        self._apply_idle_style()

    def _apply_idle_style(self):
        # Opaque colors equivalent to the original rgba(220, 50, 60, α)
        # composited against the panel's #ffffff background. Kept opaque on
        # purpose: WA_TranslucentBackground on the OptionsPanel can fail to
        # reliably paint the panel's white BG under child widgets on Wayland
        # (via XWayland), causing the note's text to bleed through any
        # translucent child. These hex values render IDENTICALLY to the
        # original on the white panel but never leak content behind.
        self.setStyleSheet("""
            QPushButton {
                background-color: #fceaec;
                color: #c0341d;
                border: 1px solid #f7d2d4;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 10pt;
                font-weight: 500;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #f9dadc;
                border: 1px solid #f3b7bb;
            }
            QPushButton:pressed {
                background-color: #f5c6c8;
            }
        """)

    def _apply_armed_style(self):
        self.setStyleSheet("""
            QPushButton {
                background-color: #d33f2f;
                color: #ffffff;
                border: 1px solid #b03224;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 10pt;
                font-weight: 600;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #c0341d;
            }
            QPushButton:pressed {
                background-color: #a52a1c;
            }
        """)


# ---------------------------------------------------------------------------
# OptionsPanel — floating popup below the "..." button
# ---------------------------------------------------------------------------
class OptionsPanel(QWidget):
    themeSelected = pyqtSignal(str)
    deleteRequested = pyqtSignal()
    # Emitted on every dismissal (outside click, explicit close, theme pick).
    # Carries self so the owner can verify identity before clearing its ref.
    dismissed = pyqtSignal(object)

    _SWATCHES = [
        ("yellow",   "#FFF176"),
        ("green",    "#B5EBBF"),
        ("pink",     "#F9B8C6"),
        ("purple",   "#D8B8F9"),
        ("blue",     "#B3E5FC"),
        ("gray",     "#E0E0E0"),
        ("charcoal", "#4A4A4A"),
    ]

    def __init__(self, current_theme: str, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Give the popup an alpha channel so the four corners outside the
        # 8 px border-radius become genuinely transparent, instead of the
        # default opaque widget background that otherwise frames the panel
        # with four dark dots.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._dismissed = False
        self._current_theme = current_theme
        self._setup_ui()
        self._apply_panel_style()

    def hideEvent(self, event):
        # Popup auto-dismisses on outside click via hide(), not close(), so
        # WA_DeleteOnClose alone wouldn't free the widget. Emit + deleteLater
        # here covers every dismissal path.
        super().hideEvent(event)
        if not self._dismissed:
            self._dismissed = True
            self.dismissed.emit(self)
            self.deleteLater()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Row 1 — color swatches
        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(4)
        for name, color in self._SWATCHES:
            btn = QPushButton("✓" if name == self._current_theme else "")
            btn.setFixedSize(28, 28)
            # Swatches carry no text (bar a tick on the active one), so the
            # colour is the only cue — and at 28px "gray" and "charcoal" are
            # hard to tell apart. Name them for hover and for screen readers.
            label = name.capitalize()
            btn.setToolTip(label)
            btn.setAccessibleName(f"{label} theme")
            tick_color = "#ffffff" if name == "charcoal" else "#333333"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    border-radius: 14px;
                    color: {tick_color};
                    font-size: 9pt;
                    border: none;
                }}
                QPushButton:hover {{
                    border: 2px solid white;
                }}
            """)
            btn.clicked.connect(lambda _checked, n=name: self.themeSelected.emit(n))
            swatch_row.addWidget(btn)
        layout.addLayout(swatch_row)

        # Separator — reads as the boundary between picker and destructive
        # action. Opaque hex equivalent of rgba(0, 0, 0, 0.10) composited on
        # the panel's #ffffff (see _DeleteButton._apply_idle_style for why
        # opaque colors are required here on Wayland-via-XWayland).
        separator = QFrame(self)
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #e6e6e6;")
        layout.addWidget(separator)

        # Destructive action — two-click confirm pattern lives inside the button
        delete_btn = _DeleteButton(self)
        delete_btn.confirmed.connect(self.deleteRequested.emit)
        layout.addWidget(delete_btn)

        self.setFixedWidth(220)

    def _apply_panel_style(self):
        # Selector-scoped so we don't accidentally restyle every QWidget child
        # (which would clobber the swatches and delete button stylesheets).
        self.setObjectName("optionsPanel")
        self.setStyleSheet(
            f"QWidget#optionsPanel {{ background-color: #ffffff; "
            f"border-radius: {config.CORNER_RADIUS_PX}px; }}"
        )
        shadow = QGraphicsDropShadowEffect(self)
        blur, offset_y, alpha = config.SHADOW_PANEL
        shadow.setBlurRadius(blur)
        shadow.setOffset(0, offset_y)
        shadow.setColor(QColor(0, 0, 0, alpha))
        self.setGraphicsEffect(shadow)


# ---------------------------------------------------------------------------
# EditableTitleLabel — read-only label that swaps to a QLineEdit on click.
#
# Behavior:
#   - Single-click on the visible label (when editable) → enter edit mode.
#   - Enter or focus-loss → commit via the `committed(str)` signal.
#   - Escape → cancel without emitting.
#   - set_editable(False) commits any in-progress edit and disables click +
#     hover affordance — used when the note is collapsed.
#
# Layout: QStackedLayout swaps a QLabel (display) with a QLineEdit (edit).
# Mouse-event consumption is intentional: we install ourselves as an event
# filter on the inner label so single-click is captured before propagating
# back to StickyNote's resize/drag filter.
# ---------------------------------------------------------------------------
class EditableTitleLabel(QWidget):
    committed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("titlePill")
        # Pill sizes to its text content, never overflows. Stacked layout's
        # contentsMargins give the pill its horizontal padding.
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

    # ---- Public API ---------------------------------------------------

    def set_text(self, text: str):
        self._current_text = text
        self._update_display()
        self.updateGeometry()  # sizeHint changed, ask layout to re-measure

    def current_text(self) -> str:
        return self._current_text

    def set_editable(self, editable: bool):
        """Toggle the click-to-edit affordance. Used to disable rename while
        the note is collapsed; force-commits any in-progress edit on lock."""
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
        """Style the pill and its text content. Hover/edit states show the
        overlay color; idle state is fully transparent so the title text
        sits flush on the title bar background."""
        self._text_color = text_color
        self._hover_overlay = hover_overlay
        text_qss = (
            f"color: {text_color}; background-color: transparent;"
            f"font-size: 10pt; font-weight: 600;"
        )
        self._label.setStyleSheet(f"QLabel {{ {text_qss} }}")
        self._edit.setStyleSheet(
            f"QLineEdit {{ {text_qss} border: none; padding: 0px; "
            f"selection-background-color: {text_color}; "
            f"selection-color: white; }}"
        )
        self._apply_pill_style()

    def _apply_pill_style(self):
        """(Re)compute the pill background. Hidden when collapsed; hover-only
        when display mode; always-on when editing."""
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

    # ---- Event handling ----------------------------------------------

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

    # ---- Mode transitions --------------------------------------------

    def _enter_edit_mode(self):
        self._edit.setText(self._current_text)
        self._stack.setCurrentIndex(1)
        self._apply_pill_style()
        self._edit.setFocus(Qt.FocusReason.MouseFocusReason)
        self._edit.selectAll()

    def _on_editing_finished(self):
        # Fires on Enter and on focus-loss. Re-entrancy-safe via the
        # currentIndex check (cancel already switched us back to display).
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
        # Block signals so the focus-out from the hide() doesn't fire
        # editingFinished and re-trigger a commit on the unchanged text.
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
            # First paint, layout not settled — show full text; resizeEvent
            # will re-run this once we have a real width.
            self._label.setText(text)
        elif metrics.horizontalAdvance(text) <= avail:
            self._label.setText(text)
        else:
            self._label.setText(
                metrics.elidedText(text, Qt.TextElideMode.ElideRight, max(20, avail))
            )
        self._label.setToolTip(text)

    def sizeHint(self) -> QSize:
        """Pill sizes to its text. We compute this ourselves (rather than
        letting QLabel.sizeHint drive it) so that eliding the label text
        doesn't feed back into our own sizeHint and cause an infinite
        shrink loop in the layout."""
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


# ---------------------------------------------------------------------------
# DragHandle — title-bar grab strip housing the editable title.
#
# Layout: [EditableTitleLabel (pill, sized to text)] [drag area (fills rest)]
#
# The title pill claims only as much width as its text needs (Maximum size
# policy). The remainder of the strip is the drag area — an expanding,
# mouse-transparent QWidget so clicks pass through to DragHandle itself,
# which is what StickyNote.eventFilter watches for drag start, and what
# our own mouseDoubleClickEvent uses for collapse. Result: drag and
# double-click work across almost the whole title bar; click-to-rename
# is only triggered on the pill.
# ---------------------------------------------------------------------------
class DragHandle(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dragHandle")
        # QWidget subclasses don't paint their stylesheet background unless
        # this attribute is set — without it, the parent's color leaks
        # through and the title bar looks like the body color.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)

        self.title_widget = EditableTitleLabel(self)
        layout.addWidget(self.title_widget, 0, Qt.AlignmentFlag.AlignVCenter)

        # Drag/collapse grab area — fills all remaining horizontal space.
        # Mouse-transparent so clicks reach DragHandle itself.
        self._drag_area = QWidget(self)
        self._drag_area.setObjectName("dragArea")
        self._drag_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._drag_area.setMinimumWidth(config.TITLE_DRAG_SPACER_WIDTH)
        self._drag_area.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        # WA_StyledBackground forces Qt to honor a setStyleSheet background
        # on this widget. Without it, on some platform/style combinations
        # Qt paints the system palette window color for a plain QWidget
        # regardless of stylesheet cascade from the parent.
        self._drag_area.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground, True
        )
        layout.addWidget(self._drag_area)

    def apply_bg(self, color: str):
        """Paint both surfaces of the drag handle in the title-bar color.
        Each widget is styled directly (not via a parent-cascade rule),
        because cascading background-color from a parent stylesheet to a
        plain QWidget child is unreliable across Qt themes."""
        self.setStyleSheet(
            f"QWidget#dragHandle {{ background-color: {color}; }}"
        )
        self._drag_area.setStyleSheet(
            f"QWidget#dragArea {{ background-color: {color}; }}"
        )

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            note = self.window()
            if isinstance(note, StickyNote):
                note.toggle_collapse()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)


# ---------------------------------------------------------------------------
# TitleBar — 32px strip: [+]  [drag handle]  [...]
# ---------------------------------------------------------------------------
class TitleBar(QWidget):
    newNoteRequested = pyqtSignal()
    optionsRequested = pyqtSignal()
    titleCommitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("titleBar")
        # QWidget subclasses need this to honor a stylesheet background-color.
        # Otherwise the parent (bg_widget) paints the body color through us.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(config.TITLE_BAR_HEIGHT)
        # Style state — kept so set_collapsed_style and apply_colors can
        # re-emit the stylesheet without re-passing every parameter.
        self._title_bg = "#F9E44A"
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

        self.opts_btn = FloatingButton(
            "•••",
            tone=FloatingButton.Tone.TITLE_BAR,
            font_css="font-size: 10pt;",
            tooltip="Options",
        )
        self.opts_btn.clicked.connect(self.optionsRequested.emit)
        layout.addWidget(self.opts_btn)

    def apply_colors(self, title_bg: str, btn_color: str, hover_overlay: str,
                     is_dark_theme: bool):
        """Restyle the title bar surface, its buttons, and the title pill.

        - title_bg: bar background color (theme["title"])
        - btn_color: text/icon color for buttons and the title pill
        - hover_overlay: overlay used by the title pill on hover/edit
        - is_dark_theme: forwarded to FloatingButton so it picks the
          dark-glass token set on charcoal
        """
        self._title_bg = title_bg
        self._btn_color = btn_color
        self._rebuild_bar_style()
        FloatingButton.apply_theme_to_all(
            (self.add_btn, self.opts_btn), btn_color, is_dark_theme
        )
        # DragHandle owns the styling for both its own surface and the inner
        # drag-area widget (parent-cascade isn't reliable, so each widget
        # is given its own stylesheet directly).
        self.drag_handle.apply_bg(title_bg)
        self.drag_handle.title_widget.apply_text_style(btn_color, hover_overlay)

    def set_collapsed_style(self, collapsed: bool):
        """Switch the bar between 'top of a note' shape (rounded top only) and
        'self-contained pill' shape (rounded all corners) used while the
        note is collapsed."""
        if self._is_collapsed_style == collapsed:
            return
        self._is_collapsed_style = collapsed
        self._rebuild_bar_style()

    def _rebuild_bar_style(self):
        r = config.CORNER_RADIUS_PX
        bottom_radius = r if self._is_collapsed_style else 0
        self.setStyleSheet(f"""
            QWidget#titleBar {{
                background-color: {self._title_bg};
                border-top-left-radius: {r}px;
                border-top-right-radius: {r}px;
                border-bottom-left-radius: {bottom_radius}px;
                border-bottom-right-radius: {bottom_radius}px;
            }}
        """)

    def set_title_text(self, text: str):
        """Render the title text in the drag handle (eliding handled inside)."""
        self.drag_handle.title_widget.set_text(text)

    def set_title_editable(self, editable: bool):
        """Lock/unlock click-to-rename. Used when the note is collapsed."""
        self.drag_handle.title_widget.set_editable(editable)


# ---------------------------------------------------------------------------
# FormatBar — bottom strip: [B] [I] [U] [S] [•]
# ---------------------------------------------------------------------------
class FormatBar(QWidget):
    boldClicked      = pyqtSignal()
    italicClicked    = pyqtSignal()
    underlineClicked = pyqtSignal()
    strikeClicked    = pyqtSignal()
    bulletClicked    = pyqtSignal()

    # Defaults — buttons scale around these via apply_size()
    BTN_MIN, BTN_DEFAULT, BTN_MAX = 24, 30, 44

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("formatBar")
        # QWidget subclasses need this to honor a stylesheet background-color.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._btn_size = self.BTN_DEFAULT
        self._last_colors = None    # remembered for re-apply after resize
        self._setup_ui()
        self.apply_size(self.BTN_DEFAULT)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(3)

        self.bold_btn      = self._make_btn("B", "boldBtn",      "font-weight: bold;",            "Bold")
        self.italic_btn    = self._make_btn("I", "italicBtn",    "font-style: italic;",           "Italic")
        self.underline_btn = self._make_btn("U", "underlineBtn", "text-decoration: underline;",   "Underline")
        self.strike_btn    = self._make_btn("S", "strikeBtn",    "text-decoration: line-through;", "Strikethrough")
        # Bullet button uses a painted icon (set in apply_colors); empty text.
        # With no label at all, the tooltip/accessible name is the ONLY thing
        # identifying this button to either a sighted or a screen-reader user.
        self.bullet_btn    = self._make_btn("", "bulletBtn",     "",                              "Bullet list")

        layout.addStretch()
        for btn in self._buttons():
            layout.addWidget(btn)
        layout.addStretch()

        self.bold_btn.clicked.connect(self.boldClicked.emit)
        self.italic_btn.clicked.connect(self.italicClicked.emit)
        self.underline_btn.clicked.connect(self.underlineClicked.emit)
        self.strike_btn.clicked.connect(self.strikeClicked.emit)
        self.bullet_btn.clicked.connect(self.bulletClicked.emit)

    def _buttons(self):
        return (self.bold_btn, self.italic_btn, self.underline_btn,
                self.strike_btn, self.bullet_btn)

    @staticmethod
    def _make_btn(label: str, name: str, extra_css: str, tooltip: str = "") -> FloatingButton:
        btn = FloatingButton(
            label,
            tone=FloatingButton.Tone.TOOLBAR,
            checkable=True,
            extra_css=extra_css,
            tooltip=tooltip,
        )
        btn.setObjectName(name)
        return btn

    def apply_size(self, btn_size: int):
        """Resize all toolbar buttons. Called by StickyNote on resize so
        buttons grow proportionally with the note width."""
        btn_size = max(self.BTN_MIN, min(self.BTN_MAX, int(btn_size)))
        if btn_size == self._btn_size:
            return
        self._btn_size = btn_size
        # Bar height = button height + small vertical padding
        self.setFixedHeight(btn_size + 6)
        for btn in self._buttons():
            btn.setFixedSize(btn_size, btn_size)
        # Re-apply theme so font sizes and the bullet icon pick up the new size
        if self._last_colors is not None:
            self.apply_colors(*self._last_colors)

    def apply_colors(self, bg_color: str, btn_color: str, is_dark_theme: bool):
        """Restyle the bar surface, all five buttons (via FloatingButton),
        and the bullet button's painted icon."""
        self._last_colors = (bg_color, btn_color, is_dark_theme)

        # Font size scales with button size — ~13 at btn 30, ~20 at btn 44
        font_px = max(11, int(self._btn_size * 0.45))
        font_css = f"font-size: {font_px}px;"

        r = config.CORNER_RADIUS_PX
        self.setStyleSheet(f"""
            QWidget#formatBar {{
                background-color: {bg_color};
                border-bottom-left-radius: {r}px;
                border-bottom-right-radius: {r}px;
            }}
        """)
        for btn in self._buttons():
            btn.set_font_css(font_css)
        FloatingButton.apply_theme_to_all(self._buttons(), btn_color, is_dark_theme)

        # Painted bullet-list icon, recolored to match the current btn_color
        icon_px = max(14, int(self._btn_size * 0.7))
        self.bullet_btn.setIcon(utils.create_bullet_list_icon(btn_color, icon_px))
        self.bullet_btn.setIconSize(QSize(icon_px, icon_px))


# ---------------------------------------------------------------------------
# StickyNote — main frameless note window
# ---------------------------------------------------------------------------
class StickyNote(QWidget):
    noteDeleted = pyqtSignal(str)
    newNoteRequested = pyqtSignal(str)        # emits theme_name
    titleChanged = pyqtSignal(str, str)        # emits (note_id, new_title)

    def __init__(
        self,
        note_id=None,
        content="",
        geometry_data=None,
        theme=config.DEFAULT_THEME,
        collapsed=False,
        title=None,
        last_edited=None,
        parent=None,
    ):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.note_id = note_id or str(uuid.uuid4())
        # Stable window title. Mutter (and other Wayland compositors) use
        # this together with app_id to track per-window placement memory.
        self.setWindowTitle("Sticky Note")
        self._is_being_deleted = False
        self._theme_name = theme
        self._is_collapsed = False
        self._pre_collapse_height = 250
        self._options_panel = None
        self._anim_group = None

        # Title state. A missing `title` (None) marks this note as "still on
        # the smart default" — body edits will keep refreshing the displayed
        # title from the first body line until the user commits a custom one.
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

        # Debounced save — fires SAVE_DEBOUNCE_MS after the last move/resize
        # so we never lose position even if the user quits abruptly.
        self._save_debounce = QTimer(self)
        self._save_debounce.setSingleShot(True)
        self._save_debounce.setInterval(config.SAVE_DEBOUNCE_MS)
        self._save_debounce.timeout.connect(self._save)

        self.setMinimumSize(config.MIN_NOTE_WIDTH, config.MIN_NOTE_HEIGHT)
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_autosave()

        # Enable mouse tracking on self and all children for resize cursor
        self.setMouseTracking(True)

        self._apply_theme(utils.get_theme(theme))

        # geometry_data: prefer Qt's QByteArray from saveGeometry — its
        # internal restoreGeometry path is the one Wayland compositors honor
        # at window mapping. The (x, y, w, h) tuple branch only exists to
        # migrate notes saved during the broken intermediate version.
        #
        # Also remember the resolved position so TrayManager can ask us to
        # re-assert it later — Mutter overrides our position request during
        # its initial window placement phase on Wayland autostart, so a
        # deferred second move() (~2 s after show) is what actually makes
        # positions stick at login. We capture POSITION ONLY, not the full
        # geometry: Mutter doesn't fight requested size, and skipping size
        # in the reapply means collapsed notes don't get re-expanded from
        # a stale saved-while-expanded geometry blob.
        self._initial_position = None
        if isinstance(geometry_data, tuple) and len(geometry_data) == 4:
            x, y, w, h = geometry_data
            self.resize(w, h)
            self.move(x, y)
            self._initial_position = (x, y)
        elif geometry_data:
            # Some QSettings backends (INI on certain platforms) roundtrip
            # QByteArray as str/bytes. Coerce so restoreGeometry works.
            if isinstance(geometry_data, str):
                geometry_data = QByteArray(geometry_data.encode("latin-1"))
            elif isinstance(geometry_data, (bytes, bytearray)):
                geometry_data = QByteArray(bytes(geometry_data))
            self.restoreGeometry(geometry_data)
            self._initial_position = (self.x(), self.y())
        else:
            # Default size scales with the user's screen so notes don't look
            # tiny on 1440p/4K or oversized on small laptops.
            screen = QApplication.primaryScreen().availableGeometry()
            default_w = max(280, min(480, screen.width() // 8))
            default_h = max(280, min(480, screen.height() // 6))
            self.resize(default_w, default_h)

        # Tag the window's WM_NORMAL_HINTS with USPosition so Mutter (and any
        # other X11 WM) honors our requested position on the *initial* window
        # map instead of overriding it with its own placement strategy. This
        # is what addresses the autostart-on-Wayland-via-XWayland bug at
        # source — without USPosition, Mutter sees "program-requested
        # position" and applies its own layout. With USPosition it sees
        # "user explicitly requested this position" and honors it. Call
        # site is AFTER geometry is applied so winId() exists with the
        # correct geometry, and BEFORE the widget is show()'n so the hint
        # is set when the WM first maps the window.
        if geometry_data is not None:
            xwm.mark_position_user_requested(self)

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

        # Seed the title from body if still on the smart default — covers
        # both brand-new notes (empty body → DEFAULT_NOTE_TITLE) and legacy
        # notes loaded without a stored title (derive from existing body so
        # the user sees the same identity they had before the upgrade).
        if self._title_is_default:
            self._title = derive_title_from_text(self.text_edit.toPlainText())
        self._refresh_title_display()

        # Only now connect body-edit tracking — keeps the initial setHtml
        # from being treated as a user edit.
        self.text_edit.textChanged.connect(self._on_body_changed)

        if collapsed:
            QTimer.singleShot(0, self._collapse_immediately)

    def _reapply_initial_position(self):
        """Re-assert the position captured at init. Called via QTimer on
        autostart-on-Wayland after Mutter has finished its initial window
        placement (which silently overrode our requested position). Position-
        only is intentional: Mutter doesn't fight requested size, and not
        touching size here means collapsed notes stay collapsed instead of
        re-expanding. No-op for brand-new notes (no captured position)."""
        if self._initial_position is None:
            return
        self.move(*self._initial_position)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        # Margins around bg_widget give the drop shadow room to render —
        # without them the shadow gets clipped at the window edge and you
        # can't tell stacked notes apart.
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
        self.title_bar.newNoteRequested.connect(
            lambda: self.newNoteRequested.emit(self._theme_name)
        )
        self.title_bar.optionsRequested.connect(self._show_options_panel)
        self.title_bar.titleCommitted.connect(self._on_title_committed)
        bg_layout.addWidget(self.title_bar)

        self.text_edit = NoteTextEdit(self.bg_widget)
        self.text_edit.setFrameShape(QTextEdit.Shape.NoFrame)
        self.text_edit.setAcceptRichText(True)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Tighter list indentation than Qt's 40px default — sticky notes are
        # narrow, and the deep default eats real estate at every sublist level.
        self.text_edit.document().setIndentWidth(config.LIST_INDENT_PX)
        bg_layout.addWidget(self.text_edit)

        self.format_bar = FormatBar(self.bg_widget)
        self.format_bar.boldClicked.connect(self._toggle_bold)
        self.format_bar.italicClicked.connect(self._toggle_italic)
        self.format_bar.underlineClicked.connect(self._toggle_underline)
        self.format_bar.strikeClicked.connect(self._toggle_strike)
        self.format_bar.bulletClicked.connect(self._toggle_bullet_list)
        bg_layout.addWidget(self.format_bar)

        # Reflect cursor's current formatting in the toolbar's checked state.
        self.text_edit.cursorPositionChanged.connect(self._refresh_format_bar)
        self.text_edit.currentCharFormatChanged.connect(
            lambda _fmt: self._refresh_format_bar()
        )
        # Body-edit handler is wired AFTER the initial content load in
        # __init__ so the load itself doesn't bump last_edited or trigger
        # spurious title derivation.

        outer.addWidget(self.bg_widget)

        # Body drop shadow. Kept as an instance attribute so collapse/expand
        # can swap to a tighter, denser shadow profile when the note shrinks
        # to just the title bar (where the bigger expanded shadow gets clipped
        # by the window edge and the bar reads as having a harsh bottom).
        self._bg_shadow = QGraphicsDropShadowEffect(self)
        self.bg_widget.setGraphicsEffect(self._bg_shadow)
        self._apply_expanded_shadow()

    def _setup_shortcuts(self):
        # QTextEdit doesn't bind Ctrl+B/I/U on its own — wire them explicitly.
        # WidgetWithChildrenShortcut so the shortcut still fires if a child
        # widget (e.g. scroll bar) momentarily holds focus.
        ctx = Qt.ShortcutContext.WidgetWithChildrenShortcut
        for keys, slot in (
            ("Ctrl+B",       self._toggle_bold),
            ("Ctrl+I",       self._toggle_italic),
            ("Ctrl+U",       self._toggle_underline),
            ("Ctrl+Shift+S", self._toggle_strike),
            ("Ctrl+Shift+L", self._toggle_bullet_list),
        ):
            sc = QShortcut(QKeySequence(keys), self.text_edit)
            sc.setContext(ctx)
            sc.activated.connect(slot)

    def _setup_autosave(self):
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(config.AUTOSAVE_INTERVAL_MS)
        self._autosave_timer.timeout.connect(self._save)
        self._autosave_timer.start()

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_theme(self, theme: dict):
        bg = theme["bg"]
        title_bg = theme["title"]
        text_color = theme["text"]

        # Dark themes (charcoal) use light text — title-bar buttons need a
        # light tint and a light hover overlay to be visible.
        is_dark = text_color == "#f0f0f0"
        btn_color = "#cccccc" if is_dark else "#555555"
        hover_overlay = "rgba(255, 255, 255, 0.18)" if is_dark else "rgba(0, 0, 0, 0.12)"

        self.bg_widget.setStyleSheet(f"""
            QWidget#noteBackground {{
                background-color: {bg};
                border-radius: {config.CORNER_RADIUS_PX}px;
            }}
        """)
        self.title_bar.apply_colors(title_bg, btn_color, hover_overlay, is_dark)
        self.format_bar.apply_colors(title_bg, btn_color, is_dark)
        self.text_edit.setStyleSheet(f"""
            NoteTextEdit {{
                background-color: transparent;
                color: {text_color};
                border: none;
                padding: 8px;
            }}
        """)
        font = QFont()
        font.setFamilies(["Segoe UI", "Ubuntu", "Sans Serif"])
        font.setPointSize(config.FONT_SIZE)
        self.text_edit.setFont(font)

    # ------------------------------------------------------------------
    # Options panel
    # ------------------------------------------------------------------

    def _show_options_panel(self):
        # Toggle: if already open, close it
        if self._options_panel is not None:
            self._close_options_panel()
            return
        # Parent the popup to the note window so Wayland has a parent surface
        # to anchor the xdg_popup against. Without a parent, the panel either
        # falls back to a parentless toplevel (which can't be positioned on
        # Wayland) or lands at the compositor's default spot instead of the
        # "..." button.
        panel = OptionsPanel(self._theme_name, parent=self)
        panel.themeSelected.connect(self._change_theme)
        panel.deleteRequested.connect(self._handle_delete)
        panel.dismissed.connect(self._on_panel_dismissed)

        # Position: below and right-aligned to the "..." button
        btn = self.title_bar.opts_btn
        btn_bottom_left = btn.mapToGlobal(QPoint(0, btn.height()))
        panel.adjustSize()
        x = btn_bottom_left.x() + btn.width() - panel.width()
        panel.move(QPoint(x, btn_bottom_left.y()))
        panel.show()
        self._options_panel = panel

    def _close_options_panel(self):
        """Close the panel if open, clearing the reference synchronously so a
        rapid re-open creates a fresh panel instead of toggling the old one."""
        if self._options_panel is not None:
            old = self._options_panel
            self._options_panel = None
            old.close()

    def _on_panel_dismissed(self, panel):
        # Identity check guards against a delayed dismissed signal arriving
        # after the user opened a new panel (which would otherwise wipe the
        # new reference).
        if self._options_panel is panel:
            self._options_panel = None

    def _change_theme(self, theme_name: str):
        self._theme_name = theme_name
        self._apply_theme(utils.get_theme(theme_name))
        self._close_options_panel()
        self._save()

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def _handle_delete(self):
        self._close_options_panel()
        self._is_being_deleted = True
        self.noteDeleted.emit(self.note_id)
        self.close()
        # Free the C++ widget too — close() alone only hides it, leaking
        # shortcuts, timers, and child event-filter installations.
        self.deleteLater()

    # ------------------------------------------------------------------
    # Collapse / expand
    # ------------------------------------------------------------------

    def _apply_expanded_shadow(self):
        """Roomy soft shadow for the full note. Profile sourced from
        config.SHADOW_BODY_EXPANDED."""
        blur, offset_y, alpha = config.SHADOW_BODY_EXPANDED
        self._bg_shadow.setBlurRadius(blur)
        self._bg_shadow.setOffset(0, offset_y)
        self._bg_shadow.setColor(QColor(0, 0, 0, alpha))

    def _apply_collapsed_shadow(self):
        """Tighter, denser shadow used while collapsed. The body's gone so
        the shadow has to sell the 'floating pill' feel on its own — and
        a tighter blur stays within SHADOW_GUTTER instead of being clipped
        at the (now small) window edge."""
        blur, offset_y, alpha = config.SHADOW_BODY_COLLAPSED
        self._bg_shadow.setBlurRadius(blur)
        self._bg_shadow.setOffset(0, offset_y)
        self._bg_shadow.setColor(QColor(0, 0, 0, alpha))

    def toggle_collapse(self):
        if self._is_collapsed:
            self._expand()
        else:
            self._collapse()

    def _collapse(self):
        self._pre_collapse_height = self.height()
        self._is_collapsed = True
        # Lock title editing while collapsed — committing first so any
        # in-progress rename isn't silently dropped.
        self.title_bar.set_title_editable(False)
        # Round all four title-bar corners and swap to the dense floating-
        # pill shadow so the bottom of the collapsed note reads as a soft
        # rounded edge, not a hard cut.
        self.title_bar.set_collapsed_style(True)
        self._apply_collapsed_shadow()

        # Allow window to shrink below its normal minimum
        self.setMinimumHeight(0)

        # Window must accommodate the title bar plus the top/bottom
        # shadow gutters; otherwise the gutters consume all the height
        # and the title bar is clipped.
        collapsed_h = config.TITLE_BAR_HEIGHT + 2 * config.SHADOW_GUTTER

        group = QParallelAnimationGroup(self)
        for prop in (b"minimumHeight", b"maximumHeight"):
            anim = QPropertyAnimation(self, prop)
            anim.setDuration(config.COLLAPSE_ANIMATION_MS)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(self.height())
            anim.setEndValue(collapsed_h)
            group.addAnimation(anim)

        def _hide_body():
            self.text_edit.hide()
            self.format_bar.hide()
        group.finished.connect(_hide_body)
        group.start()
        self._anim_group = group    # prevent GC

    def _expand(self):
        self._is_collapsed = False
        target_h = max(self._pre_collapse_height, config.MIN_NOTE_HEIGHT)
        # Re-enable title click-to-rename now that the body is back.
        self.title_bar.set_title_editable(True)
        # Square off the title bar's bottom corners and restore the larger
        # body shadow — the body is about to reappear behind it.
        self.title_bar.set_collapsed_style(False)
        self._apply_expanded_shadow()

        self.text_edit.show()
        self.format_bar.show()

        group = QParallelAnimationGroup(self)
        for prop in (b"minimumHeight", b"maximumHeight"):
            anim = QPropertyAnimation(self, prop)
            anim.setDuration(config.COLLAPSE_ANIMATION_MS)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(self.height())
            anim.setEndValue(target_h)
            group.addAnimation(anim)

        def _restore_constraints():
            self.setMinimumSize(config.MIN_NOTE_WIDTH, config.MIN_NOTE_HEIGHT)
            self.setMaximumSize(16_777_215, 16_777_215)

        group.finished.connect(_restore_constraints)
        group.start()
        self._anim_group = group

    def _collapse_immediately(self):
        """Apply collapsed state on load without animation."""
        collapsed_h = config.TITLE_BAR_HEIGHT + 2 * config.SHADOW_GUTTER
        self._is_collapsed = True
        self.title_bar.set_title_editable(False)
        self.title_bar.set_collapsed_style(True)
        self._apply_collapsed_shadow()
        self.text_edit.hide()
        self.format_bar.hide()
        self.setMinimumHeight(0)
        self.setMaximumHeight(collapsed_h)
        self.resize(self.width(), collapsed_h)

    # ------------------------------------------------------------------
    # Bullet list toggle
    # ------------------------------------------------------------------

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

    def _toggle_bullet_list(self):
        cursor = self.text_edit.textCursor()
        if cursor.currentList():
            self._remove_list(cursor)
        else:
            list_fmt = QTextListFormat()
            list_fmt.setStyle(QTextListFormat.Style.ListDisc)
            list_fmt.setIndent(1)
            cursor.createList(list_fmt)
        self._refresh_format_bar()

    def _refresh_format_bar(self):
        """Sync FormatBar checked state with the cursor's current formatting."""
        fmt = self.text_edit.currentCharFormat()
        cursor = self.text_edit.textCursor()
        self.format_bar.bold_btn.setChecked(fmt.fontWeight() == QFont.Weight.Bold)
        self.format_bar.italic_btn.setChecked(fmt.fontItalic())
        self.format_bar.underline_btn.setChecked(fmt.fontUnderline())
        self.format_bar.strike_btn.setChecked(fmt.fontStrikeOut())
        self.format_bar.bullet_btn.setChecked(cursor.currentList() is not None)

    def _refresh_title_display(self):
        """Push the current `_title` value to the title bar."""
        self.title_bar.set_title_text(self._title)

    def _on_body_changed(self):
        """Body content changed via user input. Updates last_edited and,
        while the title is still on the smart default, re-derives the
        displayed title from the first body line."""
        self._last_edited = _now_iso()
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
        """Slot for the title bar's QLineEdit commit. Trims, caps length,
        ignores empty-input commits (keeps previous title), and locks the
        smart-default flag once a custom title is accepted."""
        cleaned = raw_text.strip()[:config.MAX_TITLE_LENGTH]
        if not cleaned:
            # Empty/whitespace → revert to previous title (refresh display
            # in case the QLineEdit briefly displayed the empty string)
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
            cursor.setBlockFormat(fmt)
            if cursor.position() >= end:
                break
            if not cursor.movePosition(QTextCursor.MoveOperation.NextBlock):
                break

    # ------------------------------------------------------------------
    # 8-zone resize via event filter
    # ------------------------------------------------------------------

    def _get_resize_zone(self, local: QPoint) -> int:
        x, y = local.x(), local.y()
        w, h = self.width(), self.height()
        z = config.RESIZE_ZONE
        left   = x < z
        right  = x > w - z
        top    = y < z
        bottom = y > h - z
        if top    and left:  return _NW
        if top    and right: return _NE
        if bottom and left:  return _SW
        if bottom and right: return _SE
        if top:    return _N
        if bottom: return _S
        if left:   return _W
        if right:  return _E
        return _NONE

    # ---- Mouse dispatch helpers (used by both eventFilter and self overrides)

    def _try_start_resize(self, gpos: QPoint) -> bool:
        """If gpos is in a resize zone, start a resize and return True."""
        zone = self._get_resize_zone(self.mapFromGlobal(gpos))
        if zone == _NONE:
            return False
        # Native WM resize is the most reliable on Linux — it handles
        # the geometry math correctly for all four edges (the manual
        # fallback gets the top-edge case wrong on some compositors).
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
            return True
        if self._is_dragging:
            self._is_dragging = False
            return True
        return False

    def eventFilter(self, obj, event):
        t = event.type()
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

    # ---- Mouse events on StickyNote itself (the shadow gutter region).
    # Children get events through the eventFilter above; the gutter is
    # not covered by any child, so events land here directly.

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

    # ---- Window lifecycle: persistence on move/resize, format-bar scaling

    def moveEvent(self, event):
        super().moveEvent(event)
        # Save position shortly after the user finishes moving the window.
        # Debouncing avoids hammering QSettings during a drag.
        if hasattr(self, "_save_debounce") and not self._is_being_deleted:
            self._save_debounce.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Scale format-bar buttons proportionally to note width
        if hasattr(self, "format_bar"):
            # 30px buttons at ~280px window; clamped by FormatBar to [24, 44]
            btn = int(self.width() / 9.5)
            self.format_bar.apply_size(btn)
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

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    # Read-only accessors used by TrayManager when building its menu
    @property
    def title(self) -> str:
        return self._title

    @property
    def last_edited(self) -> str:
        return self._last_edited

    def _save(self):
        if self._is_being_deleted:
            return
        settings = QSettings(config.ORG_NAME, config.APP_NAME)
        settings.beginGroup("notes")
        settings.setValue(f"{self.note_id}/content",     self.text_edit.toHtml())
        # Use Qt's encoded geometry — this is the path Wayland compositors
        # honor at window mapping. Manual x/y/w/h via move() doesn't work
        # because Wayland forbids apps from positioning themselves.
        settings.setValue(f"{self.note_id}/geometry",    self.saveGeometry())
        settings.setValue(f"{self.note_id}/theme",       self._theme_name)
        settings.setValue(f"{self.note_id}/collapsed",   self._is_collapsed)
        settings.setValue(f"{self.note_id}/title",       self._title)
        settings.setValue(f"{self.note_id}/last_edited", self._last_edited)
        settings.endGroup()

    def closeEvent(self, event):
        if not self._is_being_deleted:
            self._save()
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# AboutDialog — app metadata + useful links (opened from the tray menu).
#
# Deliberately brief. Version is pulled from stickynotes.__version__ so it
# never drifts from the actual package. Links open in the user's default
# browser / mail client via QDesktopServices.
# ---------------------------------------------------------------------------
class AboutDialog(QDialog):
    _SOURCE_URL = "https://github.com/dstushar7/sticky-notes"
    _ISSUES_URL = "https://github.com/dstushar7/sticky-notes/issues"
    _DONATE_URL = "https://www.patreon.com/dstushar7/posts/sticky-note-164511062"
    _CONTACT_EMAIL = "contact@dabobrotosarkar.com"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Sticky Notes")
        self.setModal(False)
        self.setFixedWidth(440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(10)

        # Header: icon + name + version side by side
        header = QHBoxLayout()
        header.setSpacing(14)

        icon_label = QLabel()
        icon_label.setPixmap(utils.create_tray_icon().pixmap(QSize(48, 48)))
        header.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignTop)

        name_block = QVBoxLayout()
        name_block.setSpacing(2)
        name = QLabel("Sticky Notes")
        name.setStyleSheet("font-size: 16pt; font-weight: 600;")
        version = QLabel(f"Version {__version__}")
        version.setStyleSheet("color: #888; font-size: 10pt;")
        name_block.addWidget(name)
        name_block.addWidget(version)
        name_block.addStretch()
        header.addLayout(name_block)
        header.addStretch()
        layout.addLayout(header)

        # Tagline — pulled from the Snap Store summary
        tagline = QLabel(
            "The lightest, prettiest sticky notes app on Linux."
        )
        tagline.setWordWrap(True)
        tagline.setStyleSheet("font-size: 10pt;")
        layout.addWidget(tagline)

        # Author + license one-liner
        meta = QLabel("© 2026 Dabobroto Sarkar  ·  MIT licensed")
        meta.setStyleSheet("color: #888; font-size: 9pt;")
        layout.addWidget(meta)

        layout.addSpacing(4)

        # Link buttons — each opens the URL in the user's default browser.
        # PointingHandCursor signals they're clickable like normal hyperlinks.
        # Donate sits last and carries the only bit of colour in the row, so
        # it reads as the one call to action among otherwise neutral links.
        link_row = QHBoxLayout()
        link_row.setSpacing(8)
        for label, url, accent in (
            ("Source", self._SOURCE_URL, False),
            ("Report a bug", self._ISSUES_URL, False),
            ("Donate", self._DONATE_URL, True),
        ):
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if accent:
                btn.setStyleSheet("color: #d1495b; font-weight: 600;")
                btn.setToolTip("Support development on Patreon")
            btn.clicked.connect(
                lambda _checked=False, u=url: QDesktopServices.openUrl(QUrl(u))
            )
            link_row.addWidget(btn)
        link_row.addStretch()
        layout.addLayout(link_row)

        layout.addSpacing(4)

        # Footer: tech credit + clickable mailto. Rich-text QLabel handles
        # the mailto: link via setOpenExternalLinks.
        footer = QLabel(
            "Built with Python and PyQt6  ·  "
            f'<a href="mailto:{self._CONTACT_EMAIL}" '
            f'style="color:#888;">{self._CONTACT_EMAIL}</a>'
        )
        footer.setTextFormat(Qt.TextFormat.RichText)
        footer.setOpenExternalLinks(True)
        footer.setStyleSheet("color: #888; font-size: 9pt;")
        layout.addWidget(footer)

        # Close button — bottom-right, conventional dialog placement
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


# ---------------------------------------------------------------------------
# SettingsDialog — global app preferences (opened from the tray menu)
# ---------------------------------------------------------------------------
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Plain "Settings" — desktop shells prepend the app name themselves,
        # so a longer title gets duplicated and truncated by the WM.
        self.setWindowTitle("Settings")
        self.setModal(False)
        self.resize(380, 180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("Settings")
        title.setStyleSheet("font-size: 14pt; font-weight: 600;")
        layout.addWidget(title)

        self.autostart_cb = QCheckBox("Launch on system startup")
        self.autostart_cb.setChecked(autostart.is_enabled())
        self.autostart_cb.toggled.connect(self._on_autostart_toggled)
        layout.addWidget(self.autostart_cb)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #cc0000; font-size: 9pt;")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _on_autostart_toggled(self, checked: bool):
        try:
            autostart.set_enabled(checked)
            self.status.clear()
        except OSError as e:
            # Revert the checkbox so the UI matches reality, then explain.
            self.autostart_cb.blockSignals(True)
            self.autostart_cb.setChecked(autostart.is_enabled())
            self.autostart_cb.blockSignals(False)
            self.status.setText(f"Could not update autostart: {e}")
