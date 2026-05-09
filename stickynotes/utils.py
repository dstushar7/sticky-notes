# stickynotes/utils.py

from PyQt6.QtGui import QPainter, QColor, QPixmap, QIcon
from PyQt6.QtCore import Qt
from . import config


def create_tray_icon() -> QIcon:
    """Generates a simple icon for the system tray using the default theme color."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setBrush(QColor(config.THEMES[config.DEFAULT_THEME]["bg"]))
    painter.drawRect(4, 4, 24, 24)
    painter.end()
    return QIcon(pixmap)


def get_theme(name: str) -> dict:
    """Returns theme dict for name, falling back to DEFAULT_THEME if not found."""
    return config.THEMES.get(name, config.THEMES[config.DEFAULT_THEME])


def apply_theme_to_window(window, theme: dict) -> None:
    """Applies bg color, title bar color, and text color to a StickyNote window."""
    window._apply_theme(theme)
