# stickynotes/note_window.py

import uuid
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QSizePolicy, QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import (
    QSettings, pyqtSignal, Qt, QPoint, QRect,
    QPropertyAnimation, QParallelAnimationGroup, QEasingCurve,
    QEvent, QTimer,
)
from PyQt6.QtGui import (
    QColor, QTextListFormat, QTextCursor, QKeySequence, QShortcut, QFont,
)

from . import config
from . import utils

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


# ---------------------------------------------------------------------------
# NoteTextEdit — thin subclass for Shift+Enter list-break
# ---------------------------------------------------------------------------
class NoteTextEdit(QTextEdit):
    def keyPressEvent(self, event):
        if (
            event.key() == Qt.Key.Key_Return
            and event.modifiers() == Qt.KeyboardModifier.ShiftModifier
            and self.textCursor().currentList()
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


# ---------------------------------------------------------------------------
# OptionsPanel — floating popup below the "..." button
# ---------------------------------------------------------------------------
class OptionsPanel(QWidget):
    themeSelected = pyqtSignal(str)
    deleteRequested = pyqtSignal()
    alwaysOnTopToggled = pyqtSignal(bool)

    _SWATCHES = [
        ("yellow",   "#FFF176"),
        ("green",    "#B5EBBF"),
        ("pink",     "#F9B8C6"),
        ("purple",   "#D8B8F9"),
        ("blue",     "#B3E5FC"),
        ("gray",     "#E0E0E0"),
        ("charcoal", "#4A4A4A"),
    ]

    def __init__(self, current_theme: str, always_on_top: bool, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._current_theme = current_theme
        self._always_on_top = always_on_top
        self._setup_ui()
        self._apply_panel_style()

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
                    font-size: 12px;
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

        self._aot_btn = QPushButton()
        self._aot_btn.setStyleSheet(self._action_btn_style("#333333"))
        self._aot_btn.clicked.connect(self._toggle_aot)
        layout.addWidget(self._aot_btn)
        self._refresh_aot_label()

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
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #f0f0f0;
                border-radius: 4px;
            }}
        """

    def _refresh_aot_label(self):
        suffix = "  ✓" if self._always_on_top else ""
        self._aot_btn.setText(f"📌  Always on Top{suffix}")

    def _toggle_aot(self):
        self._always_on_top = not self._always_on_top
        self._refresh_aot_label()
        self.alwaysOnTopToggled.emit(self._always_on_top)

    def _apply_panel_style(self):
        self.setStyleSheet("QWidget { background-color: #ffffff; border-radius: 8px; }")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)


# ---------------------------------------------------------------------------
# DragHandle — transparent spacer that drags the window; dbl-click collapses
# ---------------------------------------------------------------------------
class DragHandle(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._drag_offset = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            )
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)

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

    def apply_colors(self, title_bg: str):
        """Restyle title bar and its buttons with the given background color."""
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
                color: #555555;
            }}
            QPushButton:hover {{
                background-color: rgba(0, 0, 0, 0.12);
            }}
        """
        self.add_btn.setStyleSheet(btn_style + "QPushButton { font-size: 18px; }")
        self.opts_btn.setStyleSheet(btn_style + "QPushButton { font-size: 11px; }")
        self.drag_handle.setStyleSheet(f"background-color: {title_bg};")


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
        always_on_top=False,
        collapsed=False,
        parent=None,
    ):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.note_id = note_id or str(uuid.uuid4())
        self._is_being_deleted = False
        self._theme_name = theme
        self._always_on_top = always_on_top
        self._is_collapsed = False
        self._pre_collapse_height = 250
        self._options_panel = None
        self._anim_group = None

        # Resize tracking
        self._resize_zone = _NONE
        self._is_resizing = False
        self._resize_start_global = None
        self._resize_start_geo = None

        self.setMinimumSize(config.MIN_NOTE_WIDTH, config.MIN_NOTE_HEIGHT)
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_autosave()

        # Enable mouse tracking on self and all children for resize cursor
        self.setMouseTracking(True)

        self._apply_theme(utils.get_theme(theme))

        if always_on_top:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        if geometry_data:
            self.restoreGeometry(geometry_data)
        else:
            self.resize(250, 250)

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

        if collapsed:
            QTimer.singleShot(0, self._collapse_immediately)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
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
        bg_layout.addWidget(self.text_edit)

        outer.addWidget(self.bg_widget)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.bg_widget.setGraphicsEffect(shadow)

    def _setup_shortcuts(self):
        # Ctrl+B/I/U are handled natively by QTextEdit in rich-text mode.
        # Only the bullet toggle needs explicit wiring.
        sc = QShortcut(QKeySequence("Ctrl+Shift+L"), self.text_edit)
        sc.setContext(Qt.ShortcutContext.WidgetShortcut)
        sc.activated.connect(self._toggle_bullet_list)

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

        self.bg_widget.setStyleSheet(f"""
            QWidget#noteBackground {{
                background-color: {bg};
                border-radius: 8px;
            }}
        """)
        self.title_bar.apply_colors(title_bg)
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
            self._options_panel.close()
            self._options_panel = None
            return

        panel = OptionsPanel(self._theme_name, self._always_on_top)
        panel.themeSelected.connect(self._change_theme)
        panel.deleteRequested.connect(self._handle_delete)
        panel.alwaysOnTopToggled.connect(self._set_always_on_top)
        panel.destroyed.connect(lambda: setattr(self, "_options_panel", None))

        # Position: below and right-aligned to the "..." button
        btn = self.title_bar.opts_btn
        btn_bottom_left = btn.mapToGlobal(QPoint(0, btn.height()))
        panel.adjustSize()
        x = btn_bottom_left.x() + btn.width() - panel.width()
        panel.move(QPoint(x, btn_bottom_left.y()))
        panel.show()
        self._options_panel = panel

    def _change_theme(self, theme_name: str):
        self._theme_name = theme_name
        self._apply_theme(utils.get_theme(theme_name))
        self._options_panel = None
        self._save()

    def _set_always_on_top(self, enabled: bool):
        self._always_on_top = enabled
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        self.show()     # required to re-apply window flags
        self._save()

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def _handle_delete(self):
        self._is_being_deleted = True
        self.noteDeleted.emit(self.note_id)
        self.close()

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

        group = QParallelAnimationGroup(self)
        for prop in (b"minimumHeight", b"maximumHeight"):
            anim = QPropertyAnimation(self, prop)
            anim.setDuration(config.COLLAPSE_ANIMATION_MS)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(self.height())
            anim.setEndValue(config.TITLE_BAR_HEIGHT)
            group.addAnimation(anim)

        group.finished.connect(self.text_edit.hide)
        group.start()
        self._anim_group = group    # prevent GC

    def _expand(self):
        self._is_collapsed = False
        target_h = max(self._pre_collapse_height, config.MIN_NOTE_HEIGHT)

        self.text_edit.show()

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
        self._is_collapsed = True
        self.text_edit.hide()
        self.setMinimumHeight(0)
        self.setMaximumHeight(config.TITLE_BAR_HEIGHT)
        self.resize(self.width(), config.TITLE_BAR_HEIGHT)

    # ------------------------------------------------------------------
    # Bullet list toggle
    # ------------------------------------------------------------------

    def _toggle_bullet_list(self):
        cursor = self.text_edit.textCursor()
        if cursor.currentList():
            self._remove_list(cursor)
        else:
            list_fmt = QTextListFormat()
            list_fmt.setStyle(QTextListFormat.Style.ListDisc)
            list_fmt.setIndent(1)
            cursor.createList(list_fmt)

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

    def eventFilter(self, obj, event):
        t = event.type()

        if t == QEvent.Type.MouseButtonPress:
            gpos = event.globalPosition().toPoint()
            zone = self._get_resize_zone(self.mapFromGlobal(gpos))
            if zone != _NONE:
                self._is_resizing = True
                self._resize_zone = zone
                self._resize_start_global = gpos
                self._resize_start_geo = self.geometry()
                self.setCursor(_CURSORS[zone])
                return True

        elif t == QEvent.Type.MouseMove:
            gpos = event.globalPosition().toPoint()
            if self._is_resizing:
                self._do_resize(gpos)
                return True
            zone = self._get_resize_zone(self.mapFromGlobal(gpos))
            self.setCursor(_CURSORS[zone]) if zone != _NONE else self.unsetCursor()

        elif t == QEvent.Type.MouseButtonRelease:
            if self._is_resizing:
                self._is_resizing = False
                self._resize_zone = _NONE
                self.unsetCursor()
                return True

        return super().eventFilter(obj, event)

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
        settings.setValue(f"{self.note_id}/content",      self.text_edit.toHtml())
        settings.setValue(f"{self.note_id}/geometry",     self.saveGeometry())
        settings.setValue(f"{self.note_id}/theme",        self._theme_name)
        settings.setValue(f"{self.note_id}/always_on_top", self._always_on_top)
        settings.setValue(f"{self.note_id}/collapsed",    self._is_collapsed)
        settings.endGroup()

    def closeEvent(self, event):
        if not self._is_being_deleted:
            self._save()
        super().closeEvent(event)
