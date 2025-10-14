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
        self.open_notes = {}  # Dictionary for easy lookup by ID

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
        
        # New Note action
        new_note_action = QAction("📝  New Note", parent=self.tray_icon)
        new_note_action.triggered.connect(self._create_new_note)
        self.menu.addAction(new_note_action)
        
        # Show All Notes action
        show_all_action = QAction("👁️  Show All Notes", parent=self.tray_icon)
        show_all_action.triggered.connect(self._show_all_notes)
        self.menu.addAction(show_all_action)
        
        self.menu.addSeparator()
        
        # Quit action
        quit_action = QAction("❌  Quit", parent=self.tray_icon)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()

    def _create_new_note(self, note_id=None, content="", geometry=None):
        """Creates and shows a new sticky note window."""
        note_window = StickyNote(note_id, content, geometry)
        
        # Connect signals
        note_window.noteDeleted.connect(self._handle_note_deletion)
        note_window.newNoteRequested.connect(self._create_new_note)
        
        note_window.show()
        self.open_notes[note_window.note_id] = note_window  # Store by ID

    def _show_all_notes(self):
        """Brings all notes to the front and makes them visible."""
        if not self.open_notes:
            # If no notes exist, create a new one
            self._create_new_note()
            return
        
        for note_window in self.open_notes.values():
            note_window.show()  # Make sure it's visible (not minimized)
            note_window.raise_()  # Bring to front
            note_window.activateWindow()  # Give it focus

    def _handle_note_deletion(self, note_id):
        """Removes a note from settings and memory."""
        # Remove from QSettings (persistent storage)
        settings = QSettings(config.ORG_NAME, config.APP_NAME)
        settings.beginGroup("notes")
        settings.remove(note_id)  # Removes the entire subgroup
        settings.endGroup()
        
        # Remove from our tracking dictionary
        if note_id in self.open_notes:
            del self.open_notes[note_id]
        
        print(f"✓ Note {note_id} deleted")

    def _load_notes(self):
        """Loads all saved notes from settings on startup."""
        settings = QSettings(config.ORG_NAME, config.APP_NAME)
        settings.beginGroup("notes")
        
        # Use childGroups() to get note IDs
        note_ids = settings.childGroups()
        
        for note_id in note_ids:
            content = settings.value(f"{note_id}/content", "")
            geometry = settings.value(f"{note_id}/geometry")
            self._create_new_note(note_id, content, geometry)
        
        settings.endGroup()