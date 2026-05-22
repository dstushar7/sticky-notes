# stickynotes/tray_manager.py

import sys

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QSettings
from .note_window import StickyNote, SettingsDialog
from . import autostart
from . import utils
from . import config


class TrayManager:
    """Manages the system tray icon and application life cycle."""

    def __init__(self, app: QApplication):
        self.app = app
        self.open_notes = {}
        self._settings_dialog = None

        self.app.setQuitOnLastWindowClosed(False)
        # app.quit() does not call closeEvent on individual windows, so any
        # unsaved position/size would be lost. Flush every note before exit.
        self.app.aboutToQuit.connect(self._save_all_notes)

        self._setup_tray_icon()
        self._load_notes()

        # Decide whether to show a starter note when no notes were restored.
        # Three states map to three behaviors:
        #   - first launch ever (no QSettings flag yet)  → welcoming note
        #   - subsequent manual launch with no notes     → blank starter
        #   - autostart launch with no notes             → silent tray
        #
        # The autostart case is the important one: without this gate, every
        # login on an empty state would flash up an unwanted blank note —
        # the exact "gets in your way" behavior the app is positioned against.
        if not self.open_notes:
            settings = QSettings(config.ORG_NAME, config.APP_NAME)
            is_first_ever = not settings.value(
                "first_launch_completed", False, type=bool
            )
            is_autostart = "--autostart" in sys.argv

            if is_first_ever:
                self._create_welcome_note()
            elif not is_autostart:
                self._create_new_note()
            # else: autostart with no saved notes → stay silent in the tray.

            settings.setValue("first_launch_completed", True)

        # Self-heal the autostart entry on every launch. If the user enabled
        # autostart on an older version with a different Exec format (e.g.
        # before --autostart was added), the file in $SNAP_USER_DATA was
        # never rewritten by the snap upgrade. Rewriting it here with the
        # current code's format migrates it forward so the next login uses
        # the up-to-date desktop entry. No-op when autostart is disabled.
        if autostart.is_enabled():
            try:
                autostart.set_enabled(True)
            except OSError:
                pass  # leave the stale file rather than crash on startup

    def _create_welcome_note(self):
        """First-launch onboarding note. Pre-filled with a short tour so a
        brand-new user discovers the non-obvious features (collapse,
        keyboard shortcuts, theme switcher) within seconds of install."""
        body = (
            "A few quick tips:\n"
            "• Double-click the title bar to collapse to a pill\n"
            "• Ctrl+B, Ctrl+I, Ctrl+U for bold, italic, underline\n"
            "• Click the + button to add another note\n"
            "• Click ••• to switch themes or delete\n"
            "\n"
            "Click the title to rename. Edit or delete this note whenever."
        )
        self._create_new_note(title="Welcome to Sticky Notes", content=body)

    def _save_all_notes(self):
        for note in self.open_notes.values():
            note._save()

    def _setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(utils.create_tray_icon(), parent=self.app)
        self.tray_icon.setToolTip("Sticky Notes")

        self.menu = QMenu()
        # Rebuild the whole menu each time it's shown so the dynamic note
        # list reflects current titles, last-edited order, and open notes.
        self.menu.aboutToShow.connect(self._rebuild_menu)
        self._rebuild_menu()

        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()

    def _rebuild_menu(self):
        """(Re)build the tray menu. Note list lives under a 'Show Note' submenu
        so the main menu stays short; the submenu itself shows newest-edited
        first and is capped by TRAY_MENU_NOTE_LIMIT."""
        self.menu.clear()

        new_note_action = QAction("New Note", parent=self.menu)
        new_note_action.triggered.connect(lambda _checked=False: self._create_new_note())
        self.menu.addAction(new_note_action)

        show_all_action = QAction("Show All Notes", parent=self.menu)
        show_all_action.triggered.connect(self._show_all_notes)
        self.menu.addAction(show_all_action)

        # "Show Note ▶" submenu — Qt renders the arrow automatically.
        show_note_menu = self.menu.addMenu("Show Note")
        self._populate_show_note_submenu(show_note_menu)

        self.menu.addSeparator()
        settings_action = QAction("Settings", parent=self.menu)
        settings_action.triggered.connect(self._show_settings)
        self.menu.addAction(settings_action)

        self.menu.addSeparator()
        quit_action = QAction("Quit", parent=self.menu)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)

    def _populate_show_note_submenu(self, submenu):
        """Fill the 'Show Note' submenu with one entry per open note, sorted
        by last_edited descending. Empty state shows a single disabled hint."""
        if not self.open_notes:
            empty = QAction("(no saved notes)", parent=submenu)
            empty.setEnabled(False)
            submenu.addAction(empty)
            return

        notes = sorted(
            self.open_notes.values(),
            key=lambda n: n.last_edited or "",
            reverse=True,
        )
        cap = max(0, int(config.TRAY_MENU_NOTE_LIMIT))
        shown = notes[:cap] if cap else notes
        for note in shown:
            title = note.title or config.DEFAULT_NOTE_TITLE
            # Defensive elide so a rogue long title can't blow out the menu.
            if len(title) > config.MAX_TITLE_LENGTH:
                title = title[: config.MAX_TITLE_LENGTH - 1] + "…"
            action = QAction(title, parent=submenu)
            # Bind note_id at lambda-creation time so the closure doesn't
            # capture the loop variable's final value.
            action.triggered.connect(
                lambda _checked=False, nid=note.note_id: self._focus_note(nid)
            )
            submenu.addAction(action)
        hidden = len(notes) - len(shown)
        if hidden > 0:
            more = QAction(f"+{hidden} more…", parent=submenu)
            more.setEnabled(False)
            submenu.addAction(more)

    def _focus_note(self, note_id: str):
        note = self.open_notes.get(note_id)
        if note is None:
            return
        note.show()
        note.raise_()
        note.activateWindow()

    def _create_new_note(
        self,
        note_id=None,
        content="",
        geometry_data=None,
        theme=None,
        collapsed=False,
        title=None,
        last_edited=None,
    ):
        theme = theme or config.DEFAULT_THEME
        note = StickyNote(
            note_id, content, geometry_data, theme, collapsed, title, last_edited
        )
        note.noteDeleted.connect(self._handle_note_deletion)
        note.newNoteRequested.connect(self._new_note_from_signal)
        note.show()
        self.open_notes[note.note_id] = note

    def _new_note_from_signal(self, theme_name: str):
        """Slot for StickyNote.newNoteRequested — creates note in same theme."""
        self._create_new_note(theme=theme_name)

    def _show_settings(self):
        # Reuse the existing dialog if it's already open so multiple clicks
        # don't stack windows.
        if self._settings_dialog is not None and self._settings_dialog.isVisible():
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        dlg = SettingsDialog()
        dlg.finished.connect(lambda _r: setattr(self, "_settings_dialog", None))
        self._settings_dialog = dlg
        dlg.show()

    def _show_all_notes(self):
        if not self.open_notes:
            self._create_new_note()
            return
        for note in self.open_notes.values():
            note.show()
            note.raise_()
            note.activateWindow()

    def _handle_note_deletion(self, note_id: str):
        settings = QSettings(config.ORG_NAME, config.APP_NAME)
        settings.beginGroup("notes")
        settings.remove(note_id)
        settings.endGroup()

        self.open_notes.pop(note_id, None)
        print(f"✓ Note {note_id} deleted")

    def _load_notes(self):
        settings = QSettings(config.ORG_NAME, config.APP_NAME)
        settings.beginGroup("notes")
        for note_id in settings.childGroups():
            content   = settings.value(f"{note_id}/content", "")
            theme     = settings.value(f"{note_id}/theme", config.DEFAULT_THEME)
            collapsed = settings.value(f"{note_id}/collapsed", False, type=bool)

            # New fields in this schema. Both default to None so legacy notes
            # get the "smart default" behavior in StickyNote.__init__ —
            # title is auto-derived from existing body content, and
            # last_edited will be filled in at first save.
            title       = settings.value(f"{note_id}/title", None)
            last_edited = settings.value(f"{note_id}/last_edited", None)

            # Prefer the QByteArray-encoded geometry (works on Wayland).
            # Fall back to (x, y, w, h) ints for notes saved during the
            # broken intermediate version where we wrote raw coords only.
            geometry = settings.value(f"{note_id}/geometry")
            if geometry is None:
                x = settings.value(f"{note_id}/x")
                y = settings.value(f"{note_id}/y")
                w = settings.value(f"{note_id}/w")
                h = settings.value(f"{note_id}/h")
                if None not in (x, y, w, h):
                    geometry = (int(x), int(y), int(w), int(h))

            self._create_new_note(
                note_id, content, geometry, theme, collapsed, title, last_edited
            )
        settings.endGroup()
