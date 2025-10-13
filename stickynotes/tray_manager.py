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
        self.open_notes = []

        # Prevent app exit when the last window closes
        self.app.setQuitOnLastWindowClosed(False)

        self._setup_tray_icon()
        self._load_notes()

        # Create a default note if none exist
        if not self.open_notes:
            self._create_new_note()

    def _setup_tray_icon(self):
        """Initializes the system tray icon and its context menu."""
        self.tray_icon = QSystemTrayIcon(utils.create_tray_icon(), parent=self.app)
        self.tray_icon.setToolTip("Sticky Notes")


        self.menu = QMenu()
        new_note_action = QAction("New Note", parent=self.tray_icon) # Parent must be given to make the tray work properly

        new_note_action.triggered.connect(self._create_new_note)
        self.menu.addAction(new_note_action)
        
        self.menu.addSeparator()
        
        quit_action = QAction("Quit", parent=self.tray_icon)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()

    def _create_new_note(self, note_id=None, content="", geometry=None):
        """Creates and shows a new sticky note window."""
        note_window = StickyNote(note_id, content, geometry)
        note_window.show()
        self.open_notes.append(note_window) # Keep a reference

    def _load_notes(self):
        """Loads all saved notes from settings on startup."""
        settings = QSettings(config.ORG_NAME, config.APP_NAME)
        settings.beginGroup("notes")
        
        note_ids_loaded = set()
        for key in settings.childKeys():
            note_id = key.split('/')[0]
            if note_id not in note_ids_loaded:
                content = settings.value(f"{note_id}/content", "")
                geometry = settings.value(f"{note_id}/geometry")
                self._create_new_note(note_id, content, geometry)
                note_ids_loaded.add(note_id)
        
        settings.endGroup()
