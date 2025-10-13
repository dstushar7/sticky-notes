# stickynotes/note_window.py

import uuid
from PyQt6.QtWidgets import QMainWindow, QTextEdit
from PyQt6.QtCore import QSettings
from . import config

class StickyNote(QMainWindow):
    """Represents a single sticky note window."""
    def __init__(self, note_id=None, content="", geometry=None, parent=None):
        super().__init__(parent)
        self.note_id = note_id if note_id else str(uuid.uuid4())

        self.setWindowTitle("Sticky Note")
        self.setMinimumSize(200, 200)

        self.central_widget = QTextEdit()
        self.central_widget.setText(content)
        self.setCentralWidget(self.central_widget)

        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(250, 250)

        self._apply_styles()

    def _apply_styles(self):
        """Applies styles from the central config file."""
        self.setStyleSheet(f"background-color: {config.NOTE_BACKGROUND_COLOR}; border: 1px solid #ccc;")
        self.central_widget.setStyleSheet(f"""
            background-color: {config.NOTE_BACKGROUND_COLOR};
            color: {config.NOTE_TEXT_COLOR};
            border: none;
            font-size: 14px;
            padding: 5px;
        """)

    def closeEvent(self, event):
        """Saves the note's data when closed."""
        settings = QSettings(config.ORG_NAME, config.APP_NAME)
        settings.beginGroup("notes")
        settings.setValue(f"{self.note_id}/content", self.central_widget.toPlainText())
        settings.setValue(f"{self.note_id}/geometry", self.saveGeometry())
        settings.endGroup()
        super().closeEvent(event)