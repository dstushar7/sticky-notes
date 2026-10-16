# stickynotes/utils.py

from PyQt6.QtGui import QPainter, QColor, QPixmap, QIcon, QPen, QPolygonF
from PyQt6.QtCore import Qt, QPointF, QRectF
from . import config


def _make_crisp_pixmap(size: int, scale: int = 4):
    """Creates a high-DPI transparent QPixmap and initialized antialiased QPainter.

    Using 4x supersampling with setDevicePixelRatio ensures vector drawing
    is rendered razor-sharp and crispy on any display scaling (1080p, 2K, 4K, Retina).
    """
    pm = QPixmap(size * scale, size * scale)
    pm.setDevicePixelRatio(scale)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    return pm, p


def create_tray_icon() -> QIcon:
    """Generates a simple icon for the system tray using the default theme color."""
    pm, painter = _make_crisp_pixmap(32)
    painter.setBrush(QColor(config.THEMES[config.DEFAULT_THEME]["bg"]))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(4, 4, 24, 24), 4, 4)
    painter.end()
    return QIcon(pm)


def create_bullet_list_icon(color: str, size: int = 24) -> QIcon:
    """A 'bulleted list' icon: three small dots, each followed by a short bar."""
    pm, p = _make_crisp_pixmap(size)
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


def create_checklist_icon(color: str, size: int = 24) -> QIcon:
    """A 'checklist' icon: three rows of a small square box plus a short bar,
    with a tick in the first box. Deliberately mirrors the geometry of
    create_bullet_list_icon so the two toolbar buttons read as siblings —
    same three rows, same bar lengths, box instead of bullet."""
    pm, p = _make_crisp_pixmap(size)
    qcolor = QColor(color)

    rows = 3
    margin_x = size * 0.15
    box = size * 0.17                     # box side length
    bar_h = max(1.5, size * 0.08)
    row_spacing = size * 0.28
    first_y = (size - row_spacing * (rows - 1)) / 2
    bar_x = margin_x + box + size * 0.12
    bar_w = size - bar_x - margin_x

    stroke = max(1.0, size * 0.055)
    for i in range(rows):
        cy = first_y + i * row_spacing
        box_rect = QRectF(margin_x, cy - box / 2, box, box)

        # Outlined box
        pen = QPen(qcolor)
        pen.setWidthF(stroke)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(box_rect)

        # Tick in the first box only — signals "checklist", not "empty boxes"
        if i == 0:
            tick = QPen(qcolor)
            tick.setWidthF(stroke * 1.15)
            tick.setCapStyle(Qt.PenCapStyle.RoundCap)
            tick.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(tick)
            p.drawPolyline(QPolygonF([
                QPointF(box_rect.left() + box * 0.22, box_rect.center().y()),
                QPointF(box_rect.center().x(),        box_rect.bottom() - box * 0.24),
                QPointF(box_rect.right() - box * 0.16, box_rect.top() + box * 0.22),
            ]))

        # Bar (rounded ends), same as the bullet-list icon
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qcolor)
        bar_rect = QRectF(bar_x, cy - bar_h / 2, bar_w, bar_h)
        p.drawRoundedRect(bar_rect, bar_h / 2, bar_h / 2)

    p.end()
    return QIcon(pm)


def create_pin_icon(color: str, size: int = 24, filled: bool = True) -> QIcon:
    """A thumbtack: round head, flange, and a stubby needle."""
    pm, p = _make_crisp_pixmap(size)
    qcolor = QColor(color)

    if filled:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qcolor)
    else:
        pen = QPen(qcolor)
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
    p.drawPolygon(QPolygonF([
        QPointF(cx - flange_half, flange_y),
        QPointF(cx + flange_half, flange_y),
        QPointF(cx + needle_half, flange_y + size * 0.10),
        QPointF(cx,               tip_y),
        QPointF(cx - needle_half, flange_y + size * 0.10),
    ]))

    p.end()
    return QIcon(pm)


def create_plus_icon(color: str, size: int = 24) -> QIcon:
    """Crisp geometric '+' icon for the new note button."""
    pm, p = _make_crisp_pixmap(size)
    pen = QPen(QColor(color))
    pen.setWidthF(max(1.2, size * 0.08))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)

    cx, cy = size / 2.0, size / 2.0
    half_arm = size * 0.28
    p.drawLine(QPointF(cx - half_arm, cy), QPointF(cx + half_arm, cy))
    p.drawLine(QPointF(cx, cy - half_arm), QPointF(cx, cy + half_arm))
    p.end()
    return QIcon(pm)


def create_options_icon(color: str, size: int = 24) -> QIcon:
    """Crisp three horizontal dots '•••' icon for the options button."""
    pm, p = _make_crisp_pixmap(size)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))

    cx, cy = size / 2.0, size / 2.0
    spacing = size * 0.24
    dot_r = max(1.2, size * 0.075)

    p.drawEllipse(QPointF(cx - spacing, cy), dot_r, dot_r)
    p.drawEllipse(QPointF(cx, cy), dot_r, dot_r)
    p.drawEllipse(QPointF(cx + spacing, cy), dot_r, dot_r)
    p.end()
    return QIcon(pm)


def create_close_icon(color: str, size: int = 24) -> QIcon:
    """Crisp geometric '✕' icon for the close note window button."""
    pm, p = _make_crisp_pixmap(size)
    pen = QPen(QColor(color))
    pen.setWidthF(max(1.2, size * 0.08))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)

    cx, cy = size / 2.0, size / 2.0
    d = size * 0.24
    p.drawLine(QPointF(cx - d, cy - d), QPointF(cx + d, cy + d))
    p.drawLine(QPointF(cx - d, cy + d), QPointF(cx + d, cy - d))
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
