# stickynotes/utils.py

from PyQt6.QtGui import QPainter, QColor, QPixmap, QIcon
from PyQt6.QtCore import Qt
from . import config

def create_tray_icon() -> QIcon:
    """Generates a simple icon for the system tray using config colors."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setBrush(QColor(config.NOTE_BACKGROUND_COLOR))
    painter.drawRect(4, 4, 24, 24)
    painter.end()
    return QIcon(pixmap)