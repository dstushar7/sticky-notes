# stickynotes/note_window.py

import uuid
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel,
    QSizePolicy, QGraphicsDropShadowEffect, QApplication,
)
from PyQt6.QtCore import (
    QSettings, pyqtSignal, Qt, QPoint, QRect, QSize, QByteArray,
    QPropertyAnimation, QParallelAnimationGroup, QEasingCurve,
    QEvent, QTimer,
)
from PyQt6.QtGui import (
    QColor, QTextListFormat, QTextCursor, QKeySequence, QShortcut, QFont,
)

from . import config
from . import utils


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
        layout.setSpacing(6)

        # Row 1 — color swatches
        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(4)
        for name, color in self._SWATCHES:
            btn = QPushButton("✓" if name == self._current_theme else "")
            btn.setFixedSize(28, 28)
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

        # Row 2 — actions
        delete_btn = QPushButton("🗑  Delete Note")
        delete_btn.setStyleSheet(self._action_btn_style("#cc0000"))
        delete_btn.clicked.connect(self.deleteRequested.emit)
        layout.addWidget(delete_btn)

        self.setFixedWidth(220)

    @staticmethod
    def _action_btn_style(color: str) -> str:
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {color};
                border: none;
                text-align: left;
                padding: 4px 8px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: #f0f0f0;
                border-radius: 4px;
            }}
        """

    def _apply_panel_style(self):
        self.setStyleSheet("QWidget { background-color: #ffffff; border-radius: 8px; }")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)


# ---------------------------------------------------------------------------
# DragHandle — transparent spacer in the title bar.
# Drag and release are handled by StickyNote.eventFilter so the top-level
# window calls self.move() directly (more reliable than doing it from a child).
# Only double-click is handled here because it's a discrete gesture that
# doesn't need the event-filter machinery.
# ---------------------------------------------------------------------------
class DragHandle(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Title label — auto-derived from the first non-empty line of content.
        # Transparent to mouse events so drag/double-click still go to DragHandle.
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)
        self.title_label = QLabel("")
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        layout.addWidget(self.title_label)

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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setFixedHeight(config.TITLE_BAR_HEIGHT)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(0)

        self.add_btn = QPushButton("+")
        self.add_btn.setFixedSize(32, 32)
        self.add_btn.clicked.connect(self.newNoteRequested.emit)
        layout.addWidget(self.add_btn)

        self.drag_handle = DragHandle(self)
        layout.addWidget(self.drag_handle)

        self.opts_btn = QPushButton("•••")
        self.opts_btn.setFixedSize(32, 32)
        self.opts_btn.clicked.connect(self.optionsRequested.emit)
        layout.addWidget(self.opts_btn)

    def apply_colors(self, title_bg: str, btn_color: str = "#555555",
                     hover_overlay: str = "rgba(0, 0, 0, 0.12)"):
        """Restyle title bar and its buttons with the given colors."""
        self._title_bg = title_bg
        self._btn_color = btn_color
        self.setStyleSheet(f"""
            QWidget#titleBar {{
                background-color: {title_bg};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }}
        """)
        btn_style = f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
                color: {btn_color};
            }}
            QPushButton:hover {{
                background-color: {hover_overlay};
            }}
        """
        self.add_btn.setStyleSheet(btn_style + "QPushButton { font-size: 16pt; }")
        self.opts_btn.setStyleSheet(btn_style + "QPushButton { font-size: 10pt; }")
        # Drag handle background; title label inherits theme color
        self.drag_handle.setStyleSheet(
            f"background-color: {title_bg};"
        )
        self.drag_handle.title_label.setStyleSheet(
            f"color: {btn_color}; background-color: transparent; "
            f"font-size: 10pt; font-weight: 600;"
        )

    def set_title_text(self, text: str):
        """Set (and elide) the auto-derived title displayed in the drag handle."""
        self._full_title = text
        label = self.drag_handle.title_label
        avail = max(20, label.width() - 12)
        from PyQt6.QtGui import QFontMetrics
        metrics = QFontMetrics(label.font())
        label.setText(metrics.elidedText(text, Qt.TextElideMode.ElideRight, avail))
        label.setToolTip(text if text else "")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Re-elide the title for the new available width
        if hasattr(self, "_full_title"):
            self.set_title_text(self._full_title)


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
        self._btn_size = self.BTN_DEFAULT
        self._last_colors = None    # remembered for re-apply after resize
        self._setup_ui()
        self.apply_size(self.BTN_DEFAULT)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(3)

        self.bold_btn      = self._make_btn("B", "boldBtn")
        self.italic_btn    = self._make_btn("I", "italicBtn")
        self.underline_btn = self._make_btn("U", "underlineBtn")
        self.strike_btn    = self._make_btn("S", "strikeBtn")
        # Bullet button uses a painted icon (set in apply_colors); empty text
        self.bullet_btn    = self._make_btn("", "bulletBtn")

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
    def _make_btn(label: str, name: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName(name)
        btn.setCheckable(True)
        # Don't steal keyboard focus from QTextEdit; otherwise pressing a
        # button shifts focus and Ctrl+B/I/U shortcuts stop working.
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
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
        # Re-apply theme so font sizes inside the stylesheet pick up the new size
        if self._last_colors is not None:
            self.apply_colors(*self._last_colors)

    def apply_colors(self, bg_color: str, btn_color: str, hover_overlay: str,
                     active_overlay: str):
        """Restyle bar and buttons. active_overlay = checked-state background."""
        self._last_colors = (bg_color, btn_color, hover_overlay, active_overlay)

        # Font sizes scale with button size
        font_px = max(11, int(self._btn_size * 0.45))      # ~13 at btn 30
        bullet_px = max(15, int(self._btn_size * 0.65))    # ~19 at btn 30

        self.setStyleSheet(f"""
            QWidget#formatBar {{
                background-color: {bg_color};
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }}
        """)
        common = f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
                color: {btn_color};
                font-size: {font_px}px;
            }}
            QPushButton:hover {{
                background-color: {hover_overlay};
            }}
            QPushButton:checked {{
                background-color: {active_overlay};
            }}
        """
        # Per-button font styling so each button visually shows its action
        self.bold_btn.setStyleSheet(common + "QPushButton { font-weight: bold; }")
        self.italic_btn.setStyleSheet(common + "QPushButton { font-style: italic; }")
        self.underline_btn.setStyleSheet(common + "QPushButton { text-decoration: underline; }")
        self.strike_btn.setStyleSheet(common + "QPushButton { text-decoration: line-through; }")
        self.bullet_btn.setStyleSheet(common)
        # Painted bullet-list icon, recolored to match the current btn_color
        icon_px = max(14, int(self._btn_size * 0.7))
        self.bullet_btn.setIcon(utils.create_bullet_list_icon(btn_color, icon_px))
        self.bullet_btn.setIconSize(QSize(icon_px, icon_px))


# ---------------------------------------------------------------------------
# StickyNote — main frameless note window
# ---------------------------------------------------------------------------
class StickyNote(QWidget):
    noteDeleted = pyqtSignal(str)
    newNoteRequested = pyqtSignal(str)   # emits theme_name

    def __init__(
        self,
        note_id=None,
        content="",
        geometry_data=None,
        theme=config.DEFAULT_THEME,
        collapsed=False,
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

        # Resize tracking
        self._resize_zone = _NONE
        self._is_resizing = False
        self._resize_start_global = None
        self._resize_start_geo = None

        # Drag tracking
        self._is_dragging = False
        self._drag_start_global = None
        self._drag_start_window_pos = None

        # Debounced save — fires 500ms after the last move/resize so we
        # never lose position even if the user quits abruptly.
        self._save_debounce = QTimer(self)
        self._save_debounce.setSingleShot(True)
        self._save_debounce.setInterval(500)
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
        if isinstance(geometry_data, tuple) and len(geometry_data) == 4:
            x, y, w, h = geometry_data
            self.resize(w, h)
            self.move(x, y)
        elif geometry_data:
            # Some QSettings backends (INI on certain platforms) roundtrip
            # QByteArray as str/bytes. Coerce so restoreGeometry works.
            if isinstance(geometry_data, str):
                geometry_data = QByteArray(geometry_data.encode("latin-1"))
            elif isinstance(geometry_data, (bytes, bytearray)):
                geometry_data = QByteArray(bytes(geometry_data))
            self.restoreGeometry(geometry_data)
        else:
            # Default size scales with the user's screen so notes don't look
            # tiny on 1440p/4K or oversized on small laptops.
            screen = QApplication.primaryScreen().availableGeometry()
            default_w = max(280, min(480, screen.width() // 8))
            default_h = max(280, min(480, screen.height() // 6))
            self.resize(default_w, default_h)

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
        # Initial title (also covers the empty-content "New note" case)
        self._refresh_title()

        if collapsed:
            QTimer.singleShot(0, self._collapse_immediately)

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
        # Auto-derive title from first non-empty line of content
        self.text_edit.textChanged.connect(self._refresh_title)

        outer.addWidget(self.bg_widget)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 130))
        self.bg_widget.setGraphicsEffect(shadow)

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
        active_overlay = "rgba(255, 255, 255, 0.28)" if is_dark else "rgba(0, 0, 0, 0.20)"

        self.bg_widget.setStyleSheet(f"""
            QWidget#noteBackground {{
                background-color: {bg};
                border-radius: 8px;
            }}
        """)
        self.title_bar.apply_colors(title_bg, btn_color, hover_overlay)
        self.format_bar.apply_colors(title_bg, btn_color, hover_overlay, active_overlay)
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

        panel = OptionsPanel(self._theme_name)
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

    def toggle_collapse(self):
        if self._is_collapsed:
            self._expand()
        else:
            self._collapse()

    def _collapse(self):
        self._pre_collapse_height = self.height()
        self._is_collapsed = True

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

    def _refresh_title(self):
        """Set the title-bar label from the first non-empty line of content."""
        text = self.text_edit.toPlainText()
        first = next(
            (line.strip() for line in text.splitlines() if line.strip()),
            "New note",
        )
        self.title_bar.set_title_text(first)

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

    def _save(self):
        if self._is_being_deleted:
            return
        settings = QSettings(config.ORG_NAME, config.APP_NAME)
        settings.beginGroup("notes")
        settings.setValue(f"{self.note_id}/content",   self.text_edit.toHtml())
        # Use Qt's encoded geometry — this is the path Wayland compositors
        # honor at window mapping. Manual x/y/w/h via move() doesn't work
        # because Wayland forbids apps from positioning themselves.
        settings.setValue(f"{self.note_id}/geometry",  self.saveGeometry())
        settings.setValue(f"{self.note_id}/theme",     self._theme_name)
        settings.setValue(f"{self.note_id}/collapsed", self._is_collapsed)
        settings.endGroup()

    def closeEvent(self, event):
        if not self._is_being_deleted:
            self._save()
        super().closeEvent(event)
