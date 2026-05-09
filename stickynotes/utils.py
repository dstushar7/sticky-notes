# stickynotes/utils.py

from PyQt6.QtGui import QPainter, QColor, QPixmap, QIcon, QPen
from PyQt6.QtCore import Qt, QPointF, QRectF
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


def create_bullet_list_icon(color: str, size: int = 24) -> QIcon:
    """A 'bulleted list' icon: three small dots, each followed by a short bar."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    qcolor = QColor(color)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(qcolor)

    # Three rows: bullet (small filled circle) + horizontal bar
    rows = 3
    margin_x = size * 0.15
    bullet_r = size * 0.07
    bar_h = max(1.5, size * 0.08)
    row_spacing = size * 0.28
    first_y = (size - row_spacing * (rows - 1)) / 2  # vertically center the group
    bar_x = margin_x + bullet_r * 2 + size * 0.10
    bar_w = size - bar_x - margin_x

    for i in range(rows):
        cy = first_y + i * row_spacing
        # Bullet
        p.drawEllipse(QPointF(margin_x + bullet_r, cy), bullet_r, bullet_r)
        # Bar (rounded ends)
        bar_rect = QRectF(bar_x, cy - bar_h / 2, bar_w, bar_h)
        p.drawRoundedRect(bar_rect, bar_h / 2, bar_h / 2)

    p.end()
    return QIcon(pm)


def get_theme(name: str) -> dict:
    """Returns theme dict for name, falling back to DEFAULT_THEME if not found."""
    return config.THEMES.get(name, config.THEMES[config.DEFAULT_THEME])


def apply_theme_to_window(window, theme: dict) -> None:
    """Applies bg color, title bar color, and text color to a StickyNote window."""
    window._apply_theme(theme)
