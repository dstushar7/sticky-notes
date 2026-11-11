
import os
import sys

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QAction, QGuiApplication
from PyQt6.QtCore import QSettings, QTimer, Qt
from .note_window import StickyNote, default_note_size
from .chrome import NotesHub, SettingsWindow, ReceiveDialog, Toast
from . import __version__
from . import autostart
from . import utils
from . import config
from . import whats_new


# Snap autostart on Wayland: Mutter overrides the first window placement, so saved
# positions are re-applied once it settles.
_AUTOSTART_ON_WAYLAND = (
    "--autostart" in sys.argv
    and os.environ.get("XDG_SESSION_TYPE") == "wayland"
)


class TrayManager:
    """Manages the system tray icon and application life cycle."""

    # How far a received note opens from the note Receive was opened from.
    _RECEIVED_NOTE_OFFSET = 36

    def __init__(self, app: QApplication):
        self.app = app
        self.open_notes = {}
        self._settings_dialog = None
        self._hub = None
        self._receive_dialog = None
        self._receive_anchor_id = None   # note the dialog was opened from
        # Saved values of the last deleted note, in memory only, for Undo.
        self._undo_snapshot = None
        self._undo_toast = None

        self.app.setQuitOnLastWindowClosed(False)
        # app.quit() skips closeEvent, so flush every note before exit.
        self.app.aboutToQuit.connect(self._save_all_notes)

        self._setup_tray_icon()
        self._load_notes()

        # First launch = no notes and no flag (old installs only set the flag when empty).
        settings = QSettings(config.ORG_NAME, config.APP_NAME)
        is_first_ever = not self.open_notes and not settings.value(
            "first_launch_completed", False, type=bool
        )

        self._show_whats_new(settings, skip=is_first_ever)

        # No notes restored: first launch -> welcome note, manual launch -> blank note,
        # autostart -> stay quietly in the tray.
        if not self.open_notes:
            is_autostart = "--autostart" in sys.argv

            if is_first_ever:
                self._create_welcome_note()
                # Autostart defaults to on for new installs.
                try:
                    autostart.set_enabled(True)
                except OSError:
                    pass  # filesystem hiccup; user can enable via Settings
            elif not is_autostart:
                self._create_new_note()
            # else: autostart with no saved notes → stay silent in the tray.

            settings.setValue("first_launch_completed", True)

        # Rewrite the autostart entry on every launch so older formats get migrated.
        if autostart.is_enabled():
            try:
                autostart.set_enabled(True)
            except OSError:
                pass  # leave the stale file rather than crash on startup

    def _hide_from_dock_enabled(self) -> bool:
        """The effective dock preference: honoured only with a tray and X11, since the tray is
        the only way back to hidden notes. The stored value is left untouched.
        """
        settings = QSettings(config.ORG_NAME, config.APP_NAME)
        if not settings.value(config.SETTING_HIDE_FROM_DOCK, False, type=bool):
            return False
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return False
        return QApplication.platformName() == "xcb"

    def _apply_hide_from_dock(self, hidden: bool):
        """Apply the dock preference to every open note."""
        for note in self.open_notes.values():
            note.set_hidden_from_dock(hidden)

    def _create_welcome_note(self):
        """First-launch welcome note with a short tour."""
        # HTML, so every character gets an explicit format (plain text broke the Ctrl+B/I/U
        # toggles). The tour is a checklist the user ticks off by trying each thing.
        body = (
            "<p>A few things worth knowing. Tick them off as you try them:</p>"
            "<ul>"
            '<li class="unchecked">Click the title above to rename this note</li>'
            '<li class="unchecked">Double-click the empty part of the bar to fold the note away</li>'
            '<li class="unchecked">Start a line with 1. or - and press Enter to keep the list going</li>'
            '<li class="unchecked">Open ••• for colours, opacity and sharing</li>'
            "</ul>"
            "<p>Your notes live in the tray icon at the top of the screen. "
            "Delete this note whenever you like.</p>"
        )
        self._create_new_note(
            title="Welcome to Sticky Notes",
            content=body,
            geometry_data=self._centered_geometry(*self._ANNOUNCEMENT_SIZE),
        )

    # Big enough that the text fits without scrolling.
    _ANNOUNCEMENT_SIZE = (460, 440)

    def _show_whats_new(self, settings: QSettings, skip: bool):
        """One-time note after upgrading to a feature release (whats_new.py).
        Always records the running version; `skip` is set for first-time users.
        """
        last_seen = settings.value(config.SETTING_LAST_SEEN_VERSION, None)
        settings.setValue(config.SETTING_LAST_SEEN_VERSION, __version__)
        if skip:
            return
        release = whats_new.pending(last_seen, __version__)
        if release is None:
            return
        self._create_new_note(
            title=release.title,
            content=release.body,
            geometry_data=self._centered_geometry(*self._ANNOUNCEMENT_SIZE),
        )

    def _centered_geometry(self, w: int, h: int) -> tuple:
        """(x, y, w, h) centered on the primary screen — somewhere obvious."""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return (250, 200, w, h)
        g = screen.availableGeometry()
        return (g.x() + (g.width() - w) // 2, g.y() + (g.height() - h) // 2, w, h)

    def _save_all_notes(self):
        for note in self.open_notes.values():
            note._save()

    def _setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(utils.create_tray_icon(), parent=self.app)
        self.tray_icon.setToolTip("Sticky Notes")

        self.menu = QMenu()
        # Rebuilt on every open so titles and order are current.
        self.menu.aboutToShow.connect(self._rebuild_menu)
        self._rebuild_menu()

        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()

    def _rebuild_menu(self):
        """(Re)build the tray menu."""
        self.menu.clear()
        ink = utils.chrome_palette()["text"]

        def add(text, icon, slot):
            action = QAction(text, parent=self.menu)
            if icon:
                action.setIcon(utils.line_icon(icon, ink, 16))
            action.triggered.connect(lambda _checked=False: slot())
            self.menu.addAction(action)
            return action

        add("New note", "plus", self._create_default_note)
        add("All notes…", "grid", self._show_hub)
        add("Bring all to front", "front", self._show_all_notes)
        add("Receive a note…", "receive", self._show_receive_dialog)

        self.menu.addSeparator()
        recent = sorted(self.open_notes.values(), key=lambda n: n.last_edited or "", reverse=True)
        if recent:
            header = QAction("Recent", parent=self.menu)
            header.setEnabled(False)
            self.menu.addAction(header)
            for note in recent[: config.TRAY_MENU_RECENT_COUNT]:
                title = note.title or config.DEFAULT_NOTE_TITLE
                # Defensive elide so a rogue long title can't blow out the menu.
                if len(title) > config.MAX_TITLE_LENGTH:
                    title = title[: config.MAX_TITLE_LENGTH - 1] + "…"
                action = QAction(utils.color_dot_icon(utils.get_theme(note.theme_name)["bg"]), title, self.menu)
                # Bind note_id now, not the loop variable.
                action.triggered.connect(lambda _checked=False, nid=note.note_id: self._focus_note(nid))
                self.menu.addAction(action)
        else:
            empty = QAction("No notes yet", parent=self.menu)
            empty.setEnabled(False)
            self.menu.addAction(empty)

        self.menu.addSeparator()
        add("Settings…", "gear", self._show_settings)
        add("Quit", "power", self.app.quit)

    def _focus_note(self, note_id: str):
        note = self.open_notes.get(note_id)
        if note is None:
            return
        if note._is_collapsed:
            note.toggle_collapse()
        note.show()
        note.raise_()
        note.activateWindow()
        note.flash()

    def _default_theme(self) -> str:
        """Colour for notes made from the tray / All notes (the old default if unset)."""
        theme = QSettings(config.ORG_NAME, config.APP_NAME).value(
            config.SETTING_DEFAULT_THEME, config.DEFAULT_THEME
        )
        return theme if theme in config.THEMES else config.DEFAULT_THEME

    def _create_default_note(self):
        self._create_new_note(theme=self._default_theme())

    def _create_new_note(
        self,
        note_id=None,
        content="",
        geometry_data=None,
        theme=None,
        collapsed=False,
        title=None,
        last_edited=None,
        pinned=False,
        opacity=config.OPACITY_MAX,
    ):
        theme = theme or config.DEFAULT_THEME
        note = StickyNote(
            note_id, content, geometry_data, theme, collapsed, title, last_edited,
            pinned, self._hide_from_dock_enabled(), opacity=opacity,
        )
        note.noteDeleted.connect(self._handle_note_deletion)
        note.newNoteRequested.connect(self._new_note_from_signal)
        note.receiveRequested.connect(self._show_receive_dialog)
        note.show()
        self.open_notes[note.note_id] = note
        self._refresh_hub()
        return note

        # Mutter overrides positions during initial placement on Wayland autostart;
        # re-applying them once it settles makes them stick.
        if _AUTOSTART_ON_WAYLAND and geometry_data is not None:
            QTimer.singleShot(2000, note._reapply_initial_position)

    def _new_note_from_signal(self, theme_name: str, opacity: int):
        """The + on a note: a sibling in the same colour and opacity."""
        self._create_new_note(theme=theme_name, opacity=opacity)

    def _show_settings(self, tab: str = "general"):
        # Reuse the open window instead of stacking another.
        if self._settings_dialog is not None and self._settings_dialog.isVisible():
            self._settings_dialog.show_tab(tab)
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        win = SettingsWindow(tab)
        win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        win.hideFromDockChanged.connect(self._apply_hide_from_dock)
        win.destroyed.connect(lambda *_: setattr(self, "_settings_dialog", None))
        self._settings_dialog = win
        win.show()

    def _show_hub(self):
        if self._hub is not None and self._hub.isVisible():
            self._hub.refresh()
            self._hub.raise_()
            self._hub.activateWindow()
            return
        hub = NotesHub(lambda: list(self.open_notes.values()))
        hub.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        hub.noteChosen.connect(self._focus_note)
        hub.newNoteRequested.connect(self._create_default_note)
        hub.destroyed.connect(lambda *_: setattr(self, "_hub", None))
        self._hub = hub
        hub.show()

    def _refresh_hub(self):
        if self._hub is not None and self._hub.isVisible():
            self._hub.refresh()

    def _show_receive_dialog(self, anchor_note_id=None):
        """Open Receive; the received note opens beside `anchor_note_id` (None = tray)."""
        self._receive_anchor_id = anchor_note_id
        # Reuse the open dialog, re-anchored to whichever note asked last.
        if self._receive_dialog is not None and self._receive_dialog.isVisible():
            self._receive_dialog.raise_()
            self._receive_dialog.activateWindow()
            return
        dlg = ReceiveDialog()
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dlg.noteReceived.connect(self._add_received_note)
        dlg.destroyed.connect(lambda *_: setattr(self, "_receive_dialog", None))
        self._receive_dialog = dlg
        dlg.show()

    def _add_received_note(self, shared):
        """Create the note from a decoded share (sharing.SharedNote)."""
        w, h = default_note_size()
        anchor = self.open_notes.get(self._receive_anchor_id)
        if anchor is not None and anchor.isVisible():
            offset = self._RECEIVED_NOTE_OFFSET
            geometry = (anchor.x() + offset, anchor.y() + offset, w, h)
        else:
            geometry = self._centered_geometry(w, h)
        note = self._create_new_note(
            content=shared.body_html,
            geometry_data=geometry,
            theme=shared.theme,
            title=shared.title,
        )
        note.flash()

    def _show_all_notes(self):
        if not self.open_notes:
            self._create_default_note()
            return
        for note in self.open_notes.values():
            note.show()
            note.raise_()
            note.activateWindow()

    def _handle_note_deletion(self, note_id: str):
        """Delete the note's saved group, keeping its values in memory for Undo (never on disk)."""
        settings = QSettings(config.ORG_NAME, config.APP_NAME)
        settings.beginGroup("notes")
        settings.beginGroup(note_id)
        snapshot = {key: settings.value(key) for key in settings.allKeys()}
        settings.endGroup()
        settings.remove(note_id)
        settings.endGroup()

        self.open_notes.pop(note_id, None)
        self._refresh_hub()
        print(f"✓ Note {note_id} deleted")

        self._undo_snapshot = (note_id, snapshot) if snapshot else None
        if self._undo_toast is not None:
            self._undo_toast.close()
        if self._undo_snapshot is None:
            return
        toast = Toast("Note deleted", "Undo", config.UNDO_DELETE_MS)
        toast.actionTriggered.connect(self._undo_delete)
        toast.destroyed.connect(lambda *_: self._on_undo_toast_gone(toast))
        self._undo_toast = toast
        toast.show_at_bottom()

    def _on_undo_toast_gone(self, toast):
        if self._undo_toast is toast:
            self._undo_toast = None
            self._undo_snapshot = None

    def _undo_delete(self):
        """Restore the deleted note's values and reopen it."""
        if self._undo_snapshot is None:
            return
        note_id, snapshot = self._undo_snapshot
        self._undo_snapshot = None
        if note_id in self.open_notes:
            return
        settings = QSettings(config.ORG_NAME, config.APP_NAME)
        settings.beginGroup("notes")
        settings.beginGroup(note_id)
        for key, value in snapshot.items():
            settings.setValue(key, value)
        settings.endGroup()
        settings.endGroup()
        settings.sync()
        note = self._load_note(settings, note_id)
        if note is not None:
            note.flash()

    def _load_notes(self):
        settings = QSettings(config.ORG_NAME, config.APP_NAME)
        settings.beginGroup("notes")
        note_ids = settings.childGroups()
        settings.endGroup()
        for note_id in note_ids:
            self._load_note(settings, note_id)

    def _load_note(self, settings: QSettings, note_id: str):
        """Open one saved note; every key keeps its old default, so older notes load unchanged."""
        settings.beginGroup("notes")
        try:
            content   = settings.value(f"{note_id}/content", "")
            theme     = settings.value(f"{note_id}/theme", config.DEFAULT_THEME)
            collapsed = settings.value(f"{note_id}/collapsed", False, type=bool)
            # Absent on notes from before pinning existed: not pinned.
            pinned    = settings.value(f"{note_id}/pinned", False, type=bool)
            # New in v4. Absent on every older note, which means fully opaque.
            opacity   = settings.value(f"{note_id}/opacity", config.OPACITY_MAX)

            # None on older notes: the title comes from the first line, last_edited from the next save.
            title       = settings.value(f"{note_id}/title", None)
            last_edited = settings.value(f"{note_id}/last_edited", None)

            # Encoded geometry (works on Wayland); plain x/y/w/h from an old version as a fallback.
            geometry = settings.value(f"{note_id}/geometry")
            if geometry is None:
                x = settings.value(f"{note_id}/x")
                y = settings.value(f"{note_id}/y")
                w = settings.value(f"{note_id}/w")
                h = settings.value(f"{note_id}/h")
                if None not in (x, y, w, h):
                    geometry = (int(x), int(y), int(w), int(h))

        finally:
            settings.endGroup()
        return self._create_new_note(
            note_id, content, geometry, theme, collapsed, title, last_edited,
            pinned, opacity=opacity,
        )
