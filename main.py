import sys
import uuid
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTextEdit, QSystemTrayIcon, QMenu)
from PyQt6.QtGui import QIcon, QAction, QPainter, QColor, QPixmap
from PyQt6.QtCore import QSettings, Qt

# This will store references to all open note windows
open_notes = []

def create_new_note(note_id=None, content="", geometry=None):
    """Creates and shows a new sticky note window."""
    note_window = StickyNote(note_id, content, geometry)
    open_notes.append(note_window) # Keep a reference
    note_window.show()

def load_notes():
    """Load all saved notes on startup."""
    settings = QSettings("MyStickyNotes", "App")
    settings.beginGroup("notes")
    
    note_ids_loaded = set()
    for key in settings.childKeys():
        note_id = key.split('/')[0]
        if note_id not in note_ids_loaded:
            content = settings.value(f"{note_id}/content", "")
            geometry = settings.value(f"{note_id}/geometry")
            create_new_note(note_id, content, geometry)
            note_ids_loaded.add(note_id)
    
    settings.endGroup()

class StickyNote(QMainWindow):
    def __init__(self, note_id=None, content="", geometry=None, parent=None):
        super().__init__(parent)
        self.note_id = note_id if note_id else str(uuid.uuid4())

        self.setWindowTitle("Sticky Note")
        self.setMinimumSize(200, 200)

        # Central widget to hold the text editor
        self.central_widget = QTextEdit()
        self.central_widget.setText(content)
        self.setCentralWidget(self.central_widget)

        # Set initial size and position if provided
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(250, 250)

        # Style the note to look like a sticky note
        self.setStyleSheet("""
            QMainWindow {
                background-color: #fdfd96;
                border: 1px solid #ccc;
            }
        """)
        self.central_widget.setStyleSheet("""
            QTextEdit {
                background-color: #fdfd96;
                border: none;
                font-size: 14px;
                padding: 5px;
                color: #000000; /* Explicitly set text color to black */
            }
        """)
    
    def closeEvent(self, event):
        """Save the note's content and geometry when closed."""
        settings = QSettings("MyStickyNotes", "App")
        settings.beginGroup("notes")
        
        settings.setValue(f"{self.note_id}/content", self.central_widget.toPlainText())
        settings.setValue(f"{self.note_id}/geometry", self.saveGeometry())
        
        settings.endGroup()
        
        # Remove from our list of open notes
        if self in open_notes:
            open_notes.remove(self)

        super().closeEvent(event)

def create_tray_icon():
    """Generates a simple icon for the system tray."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setBrush(QColor("#fdfd96")) # Yellow sticky note color
    painter.drawRect(4, 4, 24, 24)
    painter.end()
    return QIcon(pixmap)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # This is crucial: don't exit the app when the last window is closed
    app.setQuitOnLastWindowClosed(False)

    # Setup the System Tray Icon
    tray_icon = QSystemTrayIcon(create_tray_icon(), parent=app)
    tray_icon.setToolTip("Sticky Notes")
    
    # Create the menu for the tray icon
    menu = QMenu()
    
    new_note_action = QAction("New Note")
    new_note_action.triggered.connect(create_new_note)
    menu.addAction(new_note_action)
    
    menu.addSeparator()
    
    quit_action = QAction("Quit")
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)
    
    tray_icon.setContextMenu(menu)
    tray_icon.show()
    
    # Load any existing notes
    load_notes()
    
    # If no notes were loaded, create one default note
    if not open_notes:
        create_new_note()

    sys.exit(app.exec())