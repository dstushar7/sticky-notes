# stickynotes/note_window.py

import uuid
from PyQt6.QtWidgets import QMainWindow, QTextEdit, QMenu
from PyQt6.QtCore import QSettings, pyqtSignal, Qt
from PyQt6.QtGui import QAction
from . import config

class StickyNote(QMainWindow):
    """Represents a single sticky note window."""
    
    # Signals
    noteDeleted = pyqtSignal(str)  # Emits note_id when note should be deleted
    newNoteRequested = pyqtSignal()  # Emits when user wants to create a new note
    
    def __init__(self, note_id=None, content="", geometry=None, parent=None):
        super().__init__(parent)
        self.note_id = note_id if note_id else str(uuid.uuid4())
        self._is_being_deleted = False  # Flag to prevent saving on delete

        self.setWindowTitle("Sticky Note")
        self.setMinimumSize(200, 200)

        self.central_widget = QTextEdit()
        self.central_widget.setText(content)
        
        # IMPORTANT: Set custom context menu policy
        self.central_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.central_widget.customContextMenuRequested.connect(self._show_context_menu)
        
        self.setCentralWidget(self.central_widget)

        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(250, 250)

        self._apply_styles()

    def _apply_styles(self):
        """Applies styles from the central config file."""
        self.setStyleSheet(f"background-color: {config.NOTE_BACKGROUND_COLOR}; border: 1px solid {config.NOTE_BORDER_COLOR};")
        self.central_widget.setStyleSheet(f"""
            background-color: {config.NOTE_BACKGROUND_COLOR};
            color: {config.NOTE_TEXT_COLOR};
            border: none;
            font-size: 14px;
            padding: 5px;
        """)
    
    def _show_context_menu(self, position):
        """Shows custom context menu on right-click inside the text area."""
        context_menu = QMenu(self)
        
        # Style the context menu using config values
        context_menu.setStyleSheet(f"""
            QMenu {{
                background-color: {config.MENU_BACKGROUND_COLOR};
                border: 1px solid {config.MENU_BORDER_COLOR};
                border-radius: 4px;
                padding: 5px;
            }}
            QMenu::item {{
                color: {config.MENU_TEXT_COLOR};
                padding: 8px 25px;
                border-radius: 3px;
            }}
            QMenu::item:selected {{
                background-color: {config.MENU_HOVER_BACKGROUND_COLOR};
                color: {config.MENU_HOVER_TEXT_COLOR};
            }}
            QMenu::item:disabled {{
                color: {config.MENU_TEXT_DISABLED_COLOR};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {config.MENU_SEPARATOR_COLOR};
                margin: 5px 0px;
            }}
        """)
        
        # Add New Note action at the top
        new_note_action = QAction("📝  New Note", self)
        new_note_action.triggered.connect(self.newNoteRequested.emit)
        context_menu.addAction(new_note_action)
        
        context_menu.addSeparator()
        
        # Add Undo action
        undo_action = QAction("Undo", self)
        undo_action.triggered.connect(self.central_widget.undo)
        undo_action.setEnabled(self.central_widget.document().isUndoAvailable())
        context_menu.addAction(undo_action)
        
        # Add Redo action
        redo_action = QAction("Redo", self)
        redo_action.triggered.connect(self.central_widget.redo)
        redo_action.setEnabled(self.central_widget.document().isRedoAvailable())
        context_menu.addAction(redo_action)
        
        context_menu.addSeparator()
        
        # Add Cut action
        cut_action = QAction("Cut", self)
        cut_action.triggered.connect(self.central_widget.cut)
        cut_action.setEnabled(self.central_widget.textCursor().hasSelection())
        context_menu.addAction(cut_action)
        
        # Add Copy action
        copy_action = QAction("Copy", self)
        copy_action.triggered.connect(self.central_widget.copy)
        copy_action.setEnabled(self.central_widget.textCursor().hasSelection())
        context_menu.addAction(copy_action)
        
        # Add Paste action
        paste_action = QAction("Paste", self)
        paste_action.triggered.connect(self.central_widget.paste)
        context_menu.addAction(paste_action)
        
        # Add Select All action
        select_all_action = QAction("Select All", self)
        select_all_action.triggered.connect(self.central_widget.selectAll)
        context_menu.addAction(select_all_action)
        
        context_menu.addSeparator()
        
        # Add our custom Delete Note action
        delete_action = QAction("🗑️  Delete Note", self)
        delete_action.triggered.connect(self._handle_delete)
        context_menu.addAction(delete_action)
        
        # Show menu at cursor position
        context_menu.exec(self.central_widget.mapToGlobal(position))
    
    def _handle_delete(self):
        """Handle delete action from context menu."""
        self._is_being_deleted = True
        self.noteDeleted.emit(self.note_id)
        self.close()

    def closeEvent(self, event):
        """Saves the note's data when closed (unless being deleted)."""
        if not self._is_being_deleted:
            settings = QSettings(config.ORG_NAME, config.APP_NAME)
            settings.beginGroup("notes")
            settings.setValue(f"{self.note_id}/content", self.central_widget.toPlainText())
            settings.setValue(f"{self.note_id}/geometry", self.saveGeometry())
            settings.endGroup()
        super().closeEvent(event)