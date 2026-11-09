# stickynotes/chrome.py
#
# The app's own windows (v4): All notes, Settings (General / Shortcuts /
# About), Receive, and the small "Note deleted · Undo" toast.
#
# They follow the desktop's light/dark preference (utils.chrome_palette);
# notes keep their own colours either way. Windows use normal system
# decorations — on XWayland that's what makes them movable and closable in
# the way users expect — and only their contents are styled.

from html import escape as html_escape

from PyQt6.QtCore import Qt, QSize, QSettings, QTimer, QUrl, QRectF, QEvent, pyqtSignal
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QPen, QFont, QDesktopServices, QTextDocument,
    QTextBlockFormat, QGuiApplication,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QStackedWidget, QAbstractButton, QPlainTextEdit, QSizePolicy,
    QApplication, QSystemTrayIcon,
)

from . import __version__
from . import config
from . import utils
from . import autostart
from . import sharing
from .widgets import ToggleSwitch
from .note_window import derive_title_from_text, edited_phrase


def _set_role(label: QLabel, role: str) -> QLabel:
    label.setProperty("role", role)
    return label


def _kind(button: QPushButton, kind: str) -> QPushButton:
    button.setProperty("kind", kind)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def _discard(widget):
    """Remove a widget from view now and free it later. deleteLater alone
    leaves it on screen until the event loop gets back round to it."""
    if widget is not None:
        widget.hide()
        widget.setParent(None)
        widget.deleteLater()


def _divider() -> QFrame:
    line = QFrame()
    line.setObjectName("divider")
    line.setFixedHeight(1)
    return line


def preview_lines(body_html: str, limit: int = 6) -> list:
    """Plain-text lines for a card preview, with checklist items shown as
    '☐ ' / '✓ '. Reads the HTML into a throwaway document; never touches a
    real note."""
    doc = QTextDocument()
    doc.setHtml(body_html)
    lines = []
    block = doc.begin()
    while block.isValid() and len(lines) < limit:
        text = block.text().replace(" ", " ").strip()
        if text:
            marker = block.blockFormat().marker()
            if block.textList() is not None and marker == QTextBlockFormat.MarkerType.Checked:
                text = "✓ " + text
            elif block.textList() is not None and marker == QTextBlockFormat.MarkerType.Unchecked:
                text = "☐ " + text
            elif block.textList() is not None:
                text = "• " + text
            lines.append(text)
        block = block.next()
    return lines


# ---------------------------------------------------------------------------
# NoteCard — a miniature note: coloured title band, a few lines, footer.
# ---------------------------------------------------------------------------
class NoteCard(QAbstractButton):
    def __init__(self, *, theme: str, title: str, lines: list, footer: str,
                 pinned: bool = False, interactive: bool = True, parent=None):
        super().__init__(parent)
        self._theme = utils.get_theme(theme)
        self._title = title
        self._lines = lines
        self._footer = footer
        self._pinned = pinned
        self._interactive = interactive
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        if interactive:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Bring this note forward")
        else:
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName(f"{title}, {self._theme.get('name', theme)} note")
        self.setFixedHeight(156)
        self.setMinimumWidth(170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event):   # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        hot = self._interactive and (self.underMouse() or self.hasFocus())
        if hot:
            p.setPen(QPen(QColor(utils.chrome_palette()["text"]), 2))
        else:
            p.setPen(QPen(QColor(0, 0, 0, 40), 1))
        p.setBrush(QColor(self._theme["bg"]))
        p.drawRoundedRect(r, 12, 12)

        text = QColor(self._theme["text"])
        band = QRectF(r.left() + 1, r.top() + 1, r.width() - 2, 32)
        p.save()
        clip = QRectF(r.left() + 1, r.top() + 1, r.width() - 2, r.height() - 2)
        path = QPainterPath()
        path.addRoundedRect(clip, 11, 11)
        p.setClipPath(path)
        p.fillRect(band, QColor(self._theme["title"]))
        p.restore()

        title_font = QFont(self.font())
        title_font.setBold(True)
        title_font.setPointSizeF(max(8.5, self.font().pointSizeF()))
        p.setFont(title_font)
        p.setPen(text)
        title_rect = band.adjusted(10, 0, -26 if self._pinned else -10, 0)
        p.drawText(title_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   p.fontMetrics().elidedText(self._title, Qt.TextElideMode.ElideRight, int(title_rect.width())))
        if self._pinned:
            pin = utils.create_pin_icon(self._theme["text"], 14, filled=True)
            p.drawPixmap(int(band.right() - 20), int(band.center().y() - 7), pin.pixmap(QSize(14, 14)))

        body_font = QFont(self.font())
        body_font.setPointSizeF(max(8.0, self.font().pointSizeF() - 0.5))
        p.setFont(body_font)
        fm = p.fontMetrics()
        y = band.bottom() + 8
        x = r.left() + 10
        width = int(r.width() - 20)
        bottom_limit = r.bottom() - 26
        body_color = QColor(text)
        body_color.setAlpha(225)
        p.setPen(body_color)
        for line in self._lines:
            if y + fm.height() > bottom_limit:
                break
            p.drawText(QRectF(x, y, width, fm.height()), Qt.AlignmentFlag.AlignLeft,
                       fm.elidedText(line, Qt.TextElideMode.ElideRight, width))
            y += fm.height() + 2

        foot = QColor(text)
        foot.setAlpha(150)
        small = QFont(self.font())
        small.setPointSizeF(max(7.5, self.font().pointSizeF() - 1.5))
        p.setFont(small)
        p.setPen(foot)
        p.drawText(QRectF(x, r.bottom() - 22, width, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self._footer)


class _ColourDot(QAbstractButton):
    """Colour filter dot for All notes. `theme=None` is the 'all colours' dot."""

    def __init__(self, theme, pal: dict, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._pal = pal
        self.setCheckable(True)
        self.setFixedSize(26, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        name = "All colours" if theme is None else utils.get_theme(theme).get("name", theme)
        self.setToolTip(name)
        self.setAccessibleName(name)

    def paintEvent(self, _event):   # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        inner = QRectF(4, 4, 18, 18)
        if self._theme is None:
            names = list(config.THEMES)
            span = 360 * 16 / len(names)
            for i, name in enumerate(names):
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(config.THEMES[name]["bg"]))
                p.drawPie(inner, int(90 * 16 - i * span), -int(span) - 1)
        else:
            p.setPen(QPen(QColor(0, 0, 0, 50), 1))
            p.setBrush(QColor(utils.get_theme(self._theme)["bg"]))
            p.drawEllipse(inner)
        if self.isChecked():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(self._pal["text"]), 2))
            p.drawEllipse(QRectF(1, 1, 24, 24))


# ---------------------------------------------------------------------------
# NotesHub — "All notes": every note, searchable, filterable by colour.
# ---------------------------------------------------------------------------
class NotesHub(QWidget):
    noteChosen = pyqtSignal(str)      # note_id to bring forward
    newNoteRequested = pyqtSignal()

    def __init__(self, notes_provider, parent=None):
        """`notes_provider()` returns the open StickyNote objects."""
        super().__init__(parent)
        self._provider = notes_provider
        self._pal = utils.chrome_palette()
        self._colour = None
        self.setObjectName("chromeRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("All notes")
        self.setWindowIcon(utils.create_tray_icon())
        self.resize(900, 600)
        self.setStyleSheet(utils.chrome_stylesheet(self._pal))

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Search titles and text")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(utils.line_icon("search", self._pal["muted"], 16), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self.refresh)
        top.addWidget(self.search, 1)

        self._dots = []
        dots = QHBoxLayout()
        dots.setSpacing(2)
        for theme in [None] + list(config.THEMES):
            dot = _ColourDot(theme, self._pal, self)
            dot.setChecked(theme is None)
            dot.clicked.connect(lambda _c=False, t=theme: self._pick_colour(t))
            self._dots.append(dot)
            dots.addWidget(dot)
        top.addLayout(dots)

        new_btn = _kind(QPushButton("New note", self), "primary")
        new_btn.setIcon(utils.line_icon("plus", config.ON_ACCENT, 16))
        new_btn.clicked.connect(self.newNoteRequested.emit)
        top.addWidget(new_btn)
        root.addLayout(top)

        info = QHBoxLayout()
        self._count = _set_role(QLabel(self), "heading")
        info.addWidget(self._count)
        info.addStretch()
        info.addWidget(_set_role(QLabel("Click a note to bring it forward", self), "muted"))
        root.addLayout(info)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 4, 0)
        self._grid.setSpacing(12)
        self._scroll.setWidget(self._grid_host)
        self._scroll.viewport().installEventFilter(self)
        root.addWidget(self._scroll, 1)
        self._columns = 0
        self.refresh()

    def eventFilter(self, obj, event):   # noqa: N802
        # Column count follows the visible width of the card area, which is
        # only known once the window is laid out (and on every resize).
        if obj is self._scroll.viewport() and event.type() == QEvent.Type.Resize:
            if self._column_count() != self._columns:
                QTimer.singleShot(0, self.refresh)
        return super().eventFilter(obj, event)

    def _column_count(self) -> int:
        return max(1, (self._scroll.viewport().width() + 12) // 212)

    def _pick_colour(self, theme):
        self._colour = theme
        for dot in self._dots:
            dot.setChecked(dot._theme == theme)
        self.refresh()

    def refresh(self):
        query = self.search.text().strip().lower()
        notes = sorted(self._provider(), key=lambda n: n.last_edited or "", reverse=True)
        shown = []
        for note in notes:
            if self._colour is not None and note.theme_name != self._colour:
                continue
            if query and query not in (note.title + "\n" + note.plain_text()).lower():
                continue
            shown.append(note)

        while self._grid.count():
            item = self._grid.takeAt(0)
            _discard(item.widget())

        cols = self._column_count()
        self._columns = cols
        for i, note in enumerate(shown):
            card = NoteCard(
                theme=note.theme_name, title=note.title or config.DEFAULT_NOTE_TITLE,
                lines=preview_lines(note.text_edit.toHtml()),
                footer=edited_phrase(note.last_edited).replace("Edited ", "").capitalize(),
                pinned=note.is_pinned,
            )
            card.clicked.connect(lambda _c=False, nid=note.note_id: self.noteChosen.emit(nid))
            self._grid.addWidget(card, i // cols, i % cols)
        for c in range(cols):
            self._grid.setColumnStretch(c, 1)
        if not shown:
            empty = _set_role(QLabel(
                f"No notes match “{html_escape(self.search.text())}”." if query or self._colour
                else "No notes yet. Click New note to make one."
            ), "muted")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setMinimumHeight(120)
            self._grid.addWidget(empty, 0, 0, 1, cols)
        self._grid.setRowStretch(self._grid.rowCount(), 1)
        total = len(notes)
        self._count.setText(
            f"{len(shown)} of {total} notes · most recently edited first" if len(shown) != total
            else f"{total} note{'' if total == 1 else 's'} · most recently edited first"
        )


# ---------------------------------------------------------------------------
# SettingsWindow — General / Shortcuts / About in one window.
# Replaces the three separate stock dialogs of v3. Same settings, same keys.
# ---------------------------------------------------------------------------
class _NavButton(QPushButton):
    def __init__(self, text: str, icon_name: str, pal: dict, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIcon(utils.line_icon(icon_name, pal["text"], 18))
        self.setIconSize(QSize(18, 18))
        self.setStyleSheet(f"""
            QPushButton {{ text-align: left; padding: 9px 12px; border-radius: 9px;
                           background: transparent; font-weight: 500; }}
            QPushButton:hover {{ background-color: {pal['raised']}; }}
            QPushButton:checked {{ background-color: {pal['raised']}; font-weight: 700; }}
        """)


class SettingsWindow(QWidget):
    # TrayManager pushes the dock preference to every open note on change.
    hideFromDockChanged = pyqtSignal(bool)

    TABS = ("general", "shortcuts", "about")

    def __init__(self, tab: str = "general", parent=None):
        super().__init__(parent)
        self._pal = utils.chrome_palette()
        self.setObjectName("chromeRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Plain "Settings" — desktop shells prepend the app name themselves.
        self.setWindowTitle("Settings")
        self.setWindowIcon(utils.create_tray_icon())
        self.resize(720, 520)
        self.setStyleSheet(utils.chrome_stylesheet(self._pal))

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        nav = QFrame(self)
        nav.setObjectName("settingsNav")
        nav.setFixedWidth(184)
        nav.setStyleSheet(
            f"QFrame#settingsNav {{ background-color: {self._pal['surface']};"
            f" border-right: 1px solid {self._pal['line']}; }}"
        )
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(12, 14, 12, 14)
        nav_layout.setSpacing(2)
        self._stack = QStackedWidget(self)
        self._nav_buttons = {}
        for key, label, icon, page in (
            ("general", "General", "gear", self._general_page()),
            ("shortcuts", "Shortcuts", "keys", self._shortcuts_page()),
            ("about", "About", "info", self._about_page()),
        ):
            btn = _NavButton(label, icon, self._pal, nav)
            btn.clicked.connect(lambda _c=False, k=key: self.show_tab(k))
            nav_layout.addWidget(btn)
            self._nav_buttons[key] = btn
            scroll = QScrollArea(self)
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self._stack.addWidget(scroll)
        nav_layout.addStretch()
        root.addWidget(nav)
        root.addWidget(self._stack, 1)
        self.show_tab(tab)

    def show_tab(self, key: str):
        key = key if key in self.TABS else "general"
        self._stack.setCurrentIndex(self.TABS.index(key))
        for k, btn in self._nav_buttons.items():
            btn.setChecked(k == key)

    # ---- General -------------------------------------------------------

    def _row(self, title: str, subtitle: str, control: QWidget) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(16, 13, 16, 13)
        lay.setSpacing(14)
        text = QVBoxLayout()
        text.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet("font-weight: 600;")
        s = _set_role(QLabel(subtitle), "muted")
        s.setWordWrap(True)
        text.addWidget(t)
        text.addWidget(s)
        lay.addLayout(text, 1)
        lay.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
        row._title, row._subtitle = t, s
        return row

    def _group(self, *rows) -> QFrame:
        group = QFrame()
        group.setObjectName("group")
        lay = QVBoxLayout(group)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        for i, row in enumerate(rows):
            if i:
                lay.addWidget(_divider())
            lay.addWidget(row)
        return group

    def _page(self, heading: str):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(26, 22, 26, 22)
        lay.setSpacing(14)
        lay.addWidget(_set_role(QLabel(heading), "title"))
        return page, lay

    def _general_page(self) -> QWidget:
        page, lay = self._page("General")
        settings = QSettings(config.ORG_NAME, config.APP_NAME)

        self.autostart_switch = ToggleSwitch(self._pal)
        self.autostart_switch.setAccessibleName("Launch on system startup")
        self.autostart_switch.setChecked(autostart.is_enabled())
        self.autostart_switch.toggled.connect(self._on_autostart_toggled)
        autostart_row = self._row("Launch on system startup",
                                  "Opens quietly in the tray and restores your notes.",
                                  self.autostart_switch)

        self.hide_dock_switch = ToggleSwitch(self._pal)
        self.hide_dock_switch.setAccessibleName("Hide notes from the dock and taskbar")
        self.hide_dock_switch.setChecked(settings.value(config.SETTING_HIDE_FROM_DOCK, False, type=bool))
        self.hide_dock_switch.toggled.connect(self._on_hide_dock_toggled)
        self._dock_row = self._row("Hide notes from the dock and taskbar",
                                   "Notes stay open and reachable from the tray. This also removes them from Alt-Tab.",
                                   self.hide_dock_switch)
        # Two hard requirements, each a way to strand the user with no route
        # back to their notes:
        #   * no system tray -> hiding from the dock removes the LAST way to
        #     reach the app, including this window, which opens from the tray.
        #   * not on xcb -> skip-taskbar is an EWMH state; native Wayland has
        #     no protocol for it, so the switch would silently do nothing.
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._disable_hide_dock("Unavailable: no system tray on this desktop, so hiding the "
                                    "dock icon would leave no way to reach your notes.")
        elif QApplication.platformName() != "xcb":
            self._disable_hide_dock("Unavailable: hiding from the dock needs X11 or XWayland.")
        lay.addWidget(self._group(autostart_row, self._dock_row))

        self.status = _set_role(QLabel(""), "error")
        self.status.setWordWrap(True)
        self.status.hide()
        lay.addWidget(self.status)

        colours = QWidget()
        colour_layout = QHBoxLayout(colours)
        colour_layout.setContentsMargins(0, 0, 0, 0)
        colour_layout.setSpacing(6)
        current = settings.value(config.SETTING_DEFAULT_THEME, config.DEFAULT_THEME)
        if current not in config.THEMES:
            current = config.DEFAULT_THEME
        self._colour_dots = []
        for name in config.THEMES:
            dot = _ColourDot(name, self._pal)
            dot.setChecked(name == current)
            dot.clicked.connect(lambda _c=False, n=name: self._on_default_colour(n))
            self._colour_dots.append(dot)
            colour_layout.addWidget(dot)
        lay.addWidget(self._group(self._row(
            "Colour for new notes",
            "Used by New note in the tray and All notes. The + on a note still copies that note.",
            colours)))
        lay.addStretch()
        return page

    def _disable_hide_dock(self, reason: str):
        # Show it off, because it genuinely isn't in effect — but block signals
        # while doing so, or setChecked(False) would ERASE the user's stored
        # preference just for opening Settings on a machine with no tray. The
        # value has to survive so it takes effect again once a tray is back.
        self.hide_dock_switch.blockSignals(True)
        self.hide_dock_switch.setChecked(False)
        self.hide_dock_switch.blockSignals(False)
        self.hide_dock_switch.setEnabled(False)
        self.hide_dock_switch.setToolTip(reason)
        self._dock_row._subtitle.setText(reason)

    def _on_hide_dock_toggled(self, checked: bool):
        settings = QSettings(config.ORG_NAME, config.APP_NAME)
        settings.setValue(config.SETTING_HIDE_FROM_DOCK, checked)
        settings.sync()
        self.hideFromDockChanged.emit(checked)

    def _on_autostart_toggled(self, checked: bool):
        try:
            autostart.set_enabled(checked)
            self.status.hide()
        except OSError as e:
            # Revert the switch so the UI matches reality, then explain.
            self.autostart_switch.blockSignals(True)
            self.autostart_switch.setChecked(autostart.is_enabled())
            self.autostart_switch.blockSignals(False)
            self.status.setText(f"Could not update autostart: {e}")
            self.status.show()

    def _on_default_colour(self, name: str):
        for dot in self._colour_dots:
            dot.setChecked(dot._theme == name)
        settings = QSettings(config.ORG_NAME, config.APP_NAME)
        settings.setValue(config.SETTING_DEFAULT_THEME, name)
        settings.sync()

    # ---- Shortcuts -----------------------------------------------------

    def _shortcuts_page(self) -> QWidget:
        page, lay = self._page("Keyboard shortcuts")
        pal = self._pal
        keycap = (
            f"QLabel {{ background-color: {pal['surface']}; border: 1px solid {pal['line']};"
            f" border-bottom-width: 2px; border-radius: 6px; padding: 1px 7px;"
            f" font-size: 9pt; font-weight: 600; }}"
        )
        for section, rows in config.SHORTCUT_REFERENCE:
            lay.addWidget(_set_role(QLabel(section.upper()), "heading"))
            grid = QGridLayout()
            grid.setHorizontalSpacing(16)
            grid.setVerticalSpacing(8)
            grid.setColumnMinimumWidth(0, 210)
            grid.setColumnStretch(1, 1)
            for r, (keys, what) in enumerate(rows):
                keys_box = QHBoxLayout()
                keys_box.setSpacing(4)
                if " " not in keys:
                    for part in keys.split("+"):
                        cap = QLabel(part)
                        cap.setStyleSheet(keycap)
                        cap.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
                        keys_box.addWidget(cap, 0, Qt.AlignmentFlag.AlignVCenter)
                else:
                    gesture = _set_role(QLabel(keys), "muted")
                    gesture.setStyleSheet("font-style: italic;")
                    keys_box.addWidget(gesture)
                keys_box.addStretch()
                holder = QWidget()
                holder.setLayout(keys_box)
                keys_box.setContentsMargins(0, 0, 0, 0)
                desc = QLabel(what)
                desc.setWordWrap(True)
                grid.addWidget(holder, r, 0)
                grid.addWidget(desc, r, 1)
            lay.addLayout(grid)
            if section == "Lists":
                foot = _set_role(QLabel(config.SHORTCUT_REFERENCE_FOOTNOTE), "muted")
                foot.setWordWrap(True)
                lay.addWidget(foot)
            lay.addSpacing(6)
        lay.addStretch()
        return page

    # ---- About ---------------------------------------------------------

    _SOURCE_URL = "https://github.com/dstushar7/sticky-notes"
    _ISSUES_URL = "https://github.com/dstushar7/sticky-notes/issues"
    _DONATE_URL = "https://www.patreon.com/dstushar7/posts/sticky-note-164511062"
    _CONTACT_EMAIL = "contact@dabobrotosarkar.com"

    def _about_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(26, 30, 26, 22)
        lay.setSpacing(6)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        icon = QLabel()
        icon.setPixmap(utils.create_tray_icon().pixmap(QSize(80, 80)))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(icon)
        name = QLabel("Sticky Notes")
        name.setStyleSheet("font-size: 18pt; font-weight: 700;")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(name)
        version = _set_role(QLabel(f"Version {__version__}"), "muted")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(version)
        lay.addSpacing(8)
        tagline = QLabel("The lightest, prettiest sticky notes app on Linux.")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(tagline)
        lay.addSpacing(12)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch()
        for label, url, kind in (("Source code", self._SOURCE_URL, None),
                                 ("Report a bug", self._ISSUES_URL, None),
                                 ("Donate", self._DONATE_URL, "green")):
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if kind:
                _kind(btn, kind)
                btn.setToolTip("Support development on Patreon")
            btn.clicked.connect(lambda _c=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            row.addWidget(btn)
        row.addStretch()
        lay.addLayout(row)
        lay.addSpacing(14)

        footer = QLabel(
            "© 2026 Dabobroto Sarkar · MIT licensed<br>Built with Python and PyQt6 · "
            f'<a href="mailto:{self._CONTACT_EMAIL}" style="color:{self._pal["muted"]};">'
            f"{self._CONTACT_EMAIL}</a>"
        )
        footer.setTextFormat(Qt.TextFormat.RichText)
        footer.setOpenExternalLinks(True)
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _set_role(footer, "muted")
        lay.addWidget(footer)
        lay.addStretch()
        return page


# ---------------------------------------------------------------------------
# ReceiveDialog — paste a shared note's text, preview it, add it as a note.
#
# Opened from the tray, All notes, or any note's ••• menu and owned by
# TrayManager, which creates the note on noteReceived. Validation reruns on
# every edit, so the preview / message and the Add button always describe
# what's in the box. The share format itself (sharing.py) is unchanged, so
# notes still travel between v3 and v4 users in both directions.
# ---------------------------------------------------------------------------
class ReceiveDialog(QWidget):
    noteReceived = pyqtSignal(object)   # sharing.SharedNote

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pal = utils.chrome_palette()
        self._shared = None
        self.setObjectName("chromeRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("Receive a note")
        self.setWindowIcon(utils.create_tray_icon())
        self.setMinimumWidth(500)
        self.setStyleSheet(utils.chrome_stylesheet(self._pal))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)

        label = QLabel("Paste the text someone shared with you")
        label.setStyleSheet("font-weight: 600;")
        lay.addWidget(label)
        self.input = QPlainTextEdit(self)
        self.input.setPlaceholderText("Sticky Note: …\nSN1:…")
        self.input.setFixedHeight(92)
        mono = QFont("monospace")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(9)
        self.input.setFont(mono)
        label.setBuddy(self.input)
        lay.addWidget(self.input)

        self._status = QLabel(self)
        self._status.setWordWrap(True)
        lay.addWidget(self._status)

        self._preview_box = QFrame(self)
        self._preview_box.setObjectName("previewBox")
        self._preview_box.setStyleSheet(
            f"QFrame#previewBox {{ background-color: {self._pal['raised']}; border-radius: 12px; }}"
        )
        self._preview_layout = QHBoxLayout(self._preview_box)
        self._preview_layout.setContentsMargins(16, 16, 16, 16)
        lay.addWidget(self._preview_box)
        lay.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel", self)
        cancel.clicked.connect(self.close)
        self._add_btn = _kind(QPushButton("Add note", self), "primary")
        self._add_btn.setDefault(True)
        self._add_btn.clicked.connect(self._add_note)
        buttons.addWidget(cancel)
        buttons.addWidget(self._add_btn)
        lay.addLayout(buttons)

        self.input.textChanged.connect(self._validate)
        self._prefill_from_clipboard()
        self._validate()

    def _prefill_from_clipboard(self):
        """Save a paste when the user has just copied a share. Only text that
        actually decodes is taken — never whatever else is on the clipboard."""
        text = QGuiApplication.clipboard().text()
        try:
            sharing.decode_note(text)
        except sharing.ShareError:
            return
        self.input.setPlainText(text)

    def _validate(self):
        text = self.input.toPlainText()
        self._shared = None
        while self._preview_layout.count():
            item = self._preview_layout.takeAt(0)
            _discard(item.widget())
        if not text.strip():
            self._show_message("Paste a shared note and a preview appears here. "
                               "If you copied one already, it's filled in for you.", "muted")
        else:
            try:
                self._shared = sharing.decode_note(text)
            except sharing.ShareError as error:
                self._show_message(f"⚠  {error}", "error")
            else:
                self._show_preview(self._shared)
        self._add_btn.setEnabled(self._shared is not None)
        self.adjustSize()

    def _show_message(self, message: str, role: str):
        self._status.setText(html_escape(message))
        _set_role(self._status, role)
        self._status.style().unpolish(self._status)
        self._status.style().polish(self._status)
        self._preview_box.hide()

    def _show_preview(self, shared):
        self._status.setText("✓  Found a note. This is how it will look:")
        _set_role(self._status, "ok")
        self._status.style().unpolish(self._status)
        self._status.style().polish(self._status)
        doc = QTextDocument()
        doc.setHtml(shared.body_html)
        title = shared.title or derive_title_from_text(doc.toPlainText())
        card = NoteCard(theme=shared.theme, title=title, lines=preview_lines(shared.body_html),
                        footer="Shared with you", interactive=False)
        card.setFixedWidth(260)
        self._preview_layout.addStretch()
        self._preview_layout.addWidget(card)
        self._preview_layout.addStretch()
        self._preview_box.show()

    def _add_note(self):
        if self._shared is None:
            return
        self.noteReceived.emit(self._shared)
        self.close()


# ---------------------------------------------------------------------------
# Toast — "Note deleted · Undo". A small frameless window near the bottom of
# the screen that fades itself out. Never takes focus.
# ---------------------------------------------------------------------------
class Toast(QWidget):
    actionTriggered = pyqtSignal()

    def __init__(self, text: str, action: str = "", duration_ms: int = 3000):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle("Sticky Notes")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        body = QFrame(self)
        body.setObjectName("toastBody")
        body.setStyleSheet("""
            QFrame#toastBody { background-color: #1E2026; border-radius: 12px; }
            QLabel { color: #FFFFFF; background: transparent; font-size: 10pt; }
            QPushButton { background-color: #34373F; color: #FBE36E; border: none;
                          border-radius: 8px; padding: 5px 12px; font-weight: 700; }
            QPushButton:hover { background-color: #41454E; }
        """)
        lay = QHBoxLayout(body)
        lay.setContentsMargins(16, 8, 8 if action else 16, 8)
        lay.setSpacing(14)
        lay.addWidget(QLabel(text, body))
        if action:
            btn = QPushButton(action, body)
            btn.setIcon(utils.line_icon("undo", "#FBE36E", 16))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(self._on_action)
            lay.addWidget(btn)
        outer.addWidget(body)
        QTimer.singleShot(duration_ms, self.close)

    def _on_action(self):
        self.actionTriggered.emit()
        self.close()

    def show_at_bottom(self):
        self.adjustSize()
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            g = screen.availableGeometry()
            self.move(g.x() + (g.width() - self.width()) // 2, g.bottom() - self.height() - 24)
        self.show()
