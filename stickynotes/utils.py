# stickynotes/utils.py

from PyQt6.QtGui import QPainter, QColor, QPixmap, QIcon, QPen, QPolygonF
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


def create_pin_icon(color: str, size: int = 24, filled: bool = True) -> QIcon:
    """A thumbtack: round head, flange, and a stubby needle.

    Painted rather than drawn from a font glyph on purpose — 📌 and 📍 resolve
    to a colour emoji font on most Linux setups, which ignores the button's
    theme colour and renders as a coloured blob at small sizes. Same reason
    create_bullet_list_icon exists.

    `filled` carries the pinned/unpinned state. FloatingButton's :checked
    background alone is too subtle to read at a glance on the lighter themes
    (idle glass is 0.55 alpha vs 0.85 checked), so the icon itself changes:
    solid when pinned, outline when not. Same convention as a bookmark toggle.
    """
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    qcolor = QColor(color)

    if filled:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qcolor)
    else:
        pen = QPen(qcolor)
        # Scale the stroke with the icon so the outline stays visible at 16px
        # without going chunky at 24px.
        pen.setWidthF(max(1.2, size * 0.085))
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

    cx = size / 2
    head_r = size * 0.235          # bigger head reads as a tack, not a balloon
    head_cy = size * 0.31
    flange_half = size * 0.30      # wide shoulder under the head
    flange_y = head_cy + head_r * 0.85
    needle_half = size * 0.055
    tip_y = size * 0.90

    p.drawEllipse(QPointF(cx, head_cy), head_r, head_r)
    # Flange + needle as one silhouette: a wide shoulder tapering to a point.
    # The shoulder is what distinguishes a thumbtack from a lollipop.
    p.drawPolygon(QPolygonF([
        QPointF(cx - flange_half, flange_y),
        QPointF(cx + flange_half, flange_y),
        QPointF(cx + needle_half, flange_y + size * 0.10),
        QPointF(cx,               tip_y),
        QPointF(cx - needle_half, flange_y + size * 0.10),
    ]))

    p.end()
    return QIcon(pm)


def tooltip_stylesheet() -> str:
    """App-wide QToolTip styling, built from the config tokens.

    Applied once to the QApplication rather than per note: tooltips are
    top-level windows, and a single app-level rule reaches every one of them
    (note chrome, the options panel swatches, the About dialog) without each
    widget having to restyle them. Nothing else in the app styles QToolTip,
    so this can't collide with the per-widget stylesheets.
    """
    return f"""
        QToolTip {{
            background-color: {config.TOOLTIP_BACKGROUND_COLOR};
            color: {config.TOOLTIP_TEXT_COLOR};
            border: 1px solid {config.TOOLTIP_BORDER_COLOR};
            border-radius: {config.TOOLTIP_CORNER_RADIUS_PX}px;
            padding: {config.TOOLTIP_PADDING};
            font-size: {config.TOOLTIP_FONT_SIZE_PT}pt;
        }}
    """


def get_theme(name: str) -> dict:
    """Returns theme dict for name, falling back to DEFAULT_THEME if not found."""
    return config.THEMES.get(name, config.THEMES[config.DEFAULT_THEME])


def apply_theme_to_window(window, theme: dict) -> None:
    """Applies bg color, title bar color, and text color to a StickyNote window."""
    window._apply_theme(theme)
