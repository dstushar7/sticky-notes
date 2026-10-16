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


def create_bullet_list_icon(color: str, size: int = 16) -> QIcon:
    """A 'bulleted list' icon calibrated to match toolbar text cap-height."""
    pm, p = _make_crisp_pixmap(size)
    qcolor = QColor(color)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(qcolor)

    # Three rows: bullet (small filled circle) + horizontal bar
    rows = 3
    margin_x = size * 0.12
    bullet_r = size * 0.08
    bar_h = max(1.3, size * 0.09)
    row_spacing = size * 0.26
    first_y = (size - row_spacing * (rows - 1)) / 2  # vertically center the group
    bar_x = margin_x + bullet_r * 2 + size * 0.12
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


def create_checklist_icon(color: str, size: int = 16) -> QIcon:
    """A 'checklist' icon calibrated to match toolbar text cap-height."""
    pm, p = _make_crisp_pixmap(size)
    qcolor = QColor(color)

    rows = 3
    margin_x = size * 0.12
    box = size * 0.19                     # box side length
    bar_h = max(1.3, size * 0.09)
    row_spacing = size * 0.26
    first_y = (size - row_spacing * (rows - 1)) / 2
    bar_x = margin_x + box + size * 0.14
    bar_w = size - bar_x - margin_x

    stroke = max(1.0, size * 0.065)
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

        # Tick in the first box only
        if i == 0:
            tick = QPen(qcolor)
            tick.setWidthF(stroke * 1.15)
            tick.setCapStyle(Qt.PenCapStyle.RoundCap)
            tick.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(tick)
            p.drawPolyline(QPolygonF([
                QPointF(box_rect.left() + box * 0.20, box_rect.center().y()),
                QPointF(box_rect.center().x(),        box_rect.bottom() - box * 0.20),
                QPointF(box_rect.right() - box * 0.15, box_rect.top() + box * 0.18),
            ]))

        # Bar (rounded ends)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qcolor)
        bar_rect = QRectF(bar_x, cy - bar_h / 2, bar_w, bar_h)
        p.drawRoundedRect(bar_rect, bar_h / 2, bar_h / 2)

    p.end()
    return QIcon(pm)


def create_italic_icon(color: str, size: int = 16) -> QIcon:
    """Crisp vector Italic 'I' icon with top and bottom serifs."""
    pm, p = _make_crisp_pixmap(size)
    stroke = max(1.4, size * 0.09)
    pen = QPen(QColor(color))
    pen.setWidthF(stroke)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)

    cx, cy = size / 2.0, size / 2.0
    h = size * 0.58
    top_y = cy - h / 2.0
    bot_y = cy + h / 2.0
    slant = size * 0.11
    top_cx = cx + slant
    bot_cx = cx - slant

    serif_w = size * 0.18
    # Top horizontal serif
    p.drawLine(QPointF(top_cx - serif_w, top_y), QPointF(top_cx + serif_w, top_y))
    # Bottom horizontal serif
    p.drawLine(QPointF(bot_cx - serif_w, bot_y), QPointF(bot_cx + serif_w, bot_y))
    # Slanted center stem
    p.drawLine(QPointF(top_cx, top_y), QPointF(bot_cx, bot_y))

    p.end()
    return QIcon(pm)


def create_pin_icon(color: str, size: int = 24, filled: bool = True) -> QIcon:
    """Modern 45-degree angled pushpin icon for 'Always on top' state."""
    pm, p = _make_crisp_pixmap(size)
    qcolor = QColor(color)

    p.translate(size / 2.0, size / 2.0)
    p.rotate(45)

    stroke = max(1.2, size * 0.08)
    pen = QPen(qcolor)
    pen.setWidthF(stroke)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)

    if filled:
        p.setPen(pen)
        p.setBrush(qcolor)
    else:
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

    # Head (rounded cap at top)
    head_w = size * 0.34
    head_h = size * 0.16
    head_y = -size * 0.40
    p.drawRoundedRect(QRectF(-head_w / 2.0, head_y, head_w, head_h), 1.5, 1.5)

    # Body (tapering down to the neck)
    body = QPolygonF([
        QPointF(-head_w * 0.35, head_y + head_h),
        QPointF(head_w * 0.35,  head_y + head_h),
        QPointF(head_w * 0.52,  head_y + head_h + size * 0.18),
        QPointF(-head_w * 0.52, head_y + head_h + size * 0.18),
    ])
    p.drawPolygon(body)

    # Needle (sharp pin pointing down-left into the surface)
    needle_pen = QPen(qcolor)
    needle_pen.setWidthF(max(1.2, stroke * 1.0))
    needle_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(needle_pen)
    p.drawLine(QPointF(0, head_y + head_h + size * 0.18), QPointF(0, size * 0.40))

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
