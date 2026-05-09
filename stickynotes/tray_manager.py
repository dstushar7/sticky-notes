# stickynotes/tray_manager.py

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QSettings
from .note_window import StickyNote
from . import utils
from . import config


class TrayManager:
    """Manages the system tray icon and application life cycle."""

    def __init__(self, app: QApplication):
        self.app = app
        self.open_notes = {}

        self.app.setQuitOnLastWindowClosed(False)
        # app.quit() does not call closeEvent on individual windows, so any
        # unsaved position/size would be lost. Flush every note before exit.
        self.app.aboutToQuit.connect(self._save_all_notes)

        self._setup_tray_icon()
        self._load_notes()

        if not self.open_notes:
            self._create_new_note()

    def _save_all_notes(self):
        for note in self.open_notes.values():
            note._save()

    def _setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(utils.create_tray_icon(), parent=self.app)
        self.tray_icon.setToolTip("Sticky Notes")

        self.menu = QMenu()

        new_note_action = QAction("📝  New Note", parent=self.tray_icon)
        new_note_action.triggered.connect(self._create_new_note)
        self.menu.addAction(new_note_action)

        show_all_action = QAction("👁️  Show All Notes", parent=self.tray_icon)
        show_all_action.triggered.connect(self._show_all_notes)
        self.menu.addAction(show_all_action)

        self.menu.addSeparator()

        quit_action = QAction("❌  Quit", parent=self.tray_icon)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)

        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()

    def _create_new_note(
        self,
        note_id=None,
        content="",
        geometry_data=None,
        theme=None,
        collapsed=False,
    ):
        theme = theme or config.DEFAULT_THEME
        note = StickyNote(note_id, content, geometry_data, theme, collapsed)
        note.noteDeleted.connect(self._handle_note_deletion)
        note.newNoteRequested.connect(self._new_note_from_signal)
        note.show()
        self.open_notes[note.note_id] = note

    def _new_note_from_signal(self, theme_name: str):
        """Slot for StickyNote.newNoteRequested — creates note in same theme."""
        self._create_new_note(theme=theme_name)

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

            self._create_new_note(note_id, content, geometry, theme, collapsed)
        settings.endGroup()
