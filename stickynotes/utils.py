# stickynotes/utils.py

from PyQt6.QtGui import QPainter, QColor, QPixmap, QIcon, QPen, QPolygonF, QPainterPath
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
    """A single clean checkbox '☑' icon with a checkmark."""
    pm, p = _make_crisp_pixmap(size)
    qcolor = QColor(color)

    cx, cy = size / 2.0, size / 2.0
    box_size = size * 0.72
    box_rect = QRectF(cx - box_size / 2.0, cy - box_size / 2.0, box_size, box_size)

    stroke = max(1.2, size * 0.08)
    pen = QPen(qcolor)
    pen.setWidthF(stroke)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    # Outer rounded square box
    p.drawRoundedRect(box_rect, 2.0, 2.0)

    # Crisp checkmark inside
    tick = QPen(qcolor)
    tick.setWidthF(stroke * 1.25)
    tick.setCapStyle(Qt.PenCapStyle.RoundCap)
    tick.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(tick)
    p.drawPolyline(QPolygonF([
        QPointF(box_rect.left() + box_size * 0.22, box_rect.center().y() + box_size * 0.02),
        QPointF(box_rect.left() + box_size * 0.44, box_rect.bottom() - box_size * 0.24),
        QPointF(box_rect.right() - box_size * 0.18, box_rect.top() + box_size * 0.24),
    ]))

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


def create_menu_lines_icon(color: str, size: int = 24) -> QIcon:
    """Crisp three horizontal lines '≡' icon for the Notes list button."""
    pm, p = _make_crisp_pixmap(size)
    pen = QPen(QColor(color))
    pen.setWidthF(max(1.3, size * 0.09))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)

    cx = size / 2.0
    half_w = size * 0.32
    left = cx - half_w
    right = cx + half_w
    y_spacing = size * 0.22

    for i in (-1, 0, 1):
        y = size / 2.0 + i * y_spacing
        p.drawLine(QPointF(left, y), QPointF(right, y))

    p.end()
    return QIcon(pm)


def create_search_icon(color: str, size: int = 24) -> QIcon:
    """Crisp magnifying glass icon for the notes search bar."""
    pm, p = _make_crisp_pixmap(size)
    pen = QPen(QColor(color))
    pen.setWidthF(max(1.3, size * 0.09))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    r = size * 0.25
    cx = size * 0.40
    cy = size * 0.40
    p.drawEllipse(QPointF(cx, cy), r, r)

    # 45-degree angled handle
    h_start_x = cx + r * 0.707
    h_start_y = cy + r * 0.707
    h_end_x = size * 0.82
    h_end_y = size * 0.82
    p.drawLine(QPointF(h_start_x, h_start_y), QPointF(h_end_x, h_end_y))
    p.end()
    return QIcon(pm)


def create_gear_icon(color: str, size: int = 24) -> QIcon:
    """Expressive, modern settings gear wheel with sculpted cogs and center hub."""
    import math
    pm, p = _make_crisp_pixmap(size)
    cx, cy = size / 2.0, size / 2.0

    path = QPainterPath()
    teeth = 6
    outer_r = size * 0.42
    root_r = size * 0.29
    hole_r = size * 0.14

    tip_half = math.radians(360 / teeth * 0.16)
    base_half = math.radians(360 / teeth * 0.26)

    for i in range(teeth):
        ca = i * (2 * math.pi / teeth)
        a1 = ca - base_half
        a2 = ca - tip_half
        a3 = ca + tip_half
        a4 = ca + base_half

        pt1 = QPointF(cx + math.cos(a1) * root_r, cy + math.sin(a1) * root_r)
        pt2 = QPointF(cx + math.cos(a2) * outer_r, cy + math.sin(a2) * outer_r)
        pt3 = QPointF(cx + math.cos(a3) * outer_r, cy + math.sin(a3) * outer_r)
        pt4 = QPointF(cx + math.cos(a4) * root_r, cy + math.sin(a4) * root_r)

        if i == 0:
            path.moveTo(pt1)
        else:
            path.lineTo(pt1)
        path.lineTo(pt2)
        path.lineTo(pt3)
        path.lineTo(pt4)

    path.closeSubpath()

    hole = QPainterPath()
    hole.addEllipse(QPointF(cx, cy), hole_r, hole_r)
    gear_shape = path.subtracted(hole)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawPath(gear_shape)
    p.end()
    return QIcon(pm)


def create_share_icon(color: str, size: int = 16) -> QIcon:
    """Crisp vector Paper Airplane (Send/Share) icon."""
    pm, p = _make_crisp_pixmap(size)
    qcolor = QColor(color)
    stroke = max(1.3, size * 0.085)
    pen = QPen(qcolor)
    pen.setWidthF(stroke)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    tip = QPointF(size * 0.86, size * 0.14)
    tail_left = QPointF(size * 0.14, size * 0.50)
    tail_bot = QPointF(size * 0.50, size * 0.86)
    inner_fold = QPointF(size * 0.44, size * 0.56)

    plane = QPainterPath()
    plane.moveTo(tip)
    plane.lineTo(tail_left)
    plane.lineTo(inner_fold)
    plane.lineTo(tail_bot)
    plane.closeSubpath()
    p.drawPath(plane)

    # Center crease line
    p.drawLine(tip, inner_fold)

    p.end()
    return QIcon(pm)


def create_receive_icon(color: str, size: int = 16) -> QIcon:
    """Crisp vector Inbox Tray with Plus (+) for Receive/Import."""
    pm, p = _make_crisp_pixmap(size)
    qcolor = QColor(color)
    stroke = max(1.3, size * 0.085)
    pen = QPen(qcolor)
    pen.setWidthF(stroke)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    # Tray at bottom
    x1 = size * 0.16
    x2 = size * 0.84
    y_top = size * 0.56
    y_bot = size * 0.84

    tray = QPainterPath()
    tray.moveTo(x1, y_top)
    tray.lineTo(x1, y_bot)
    tray.lineTo(x2, y_bot)
    tray.lineTo(x2, y_top)
    p.drawPath(tray)

    # Plus (+) symbol above tray
    cx = size / 2.0
    cy = size * 0.34
    plus_len = size * 0.17
    p.drawLine(QPointF(cx - plus_len, cy), QPointF(cx + plus_len, cy))
    p.drawLine(QPointF(cx, cy - plus_len), QPointF(cx, cy + plus_len))

    p.end()
    return QIcon(pm)


def create_check_icon(color: str, size: int = 16) -> QIcon:
    """Crisp vector Checkmark icon."""
    pm, p = _make_crisp_pixmap(size)
    qcolor = QColor(color)
    stroke = max(1.6, size * 0.12)
    pen = QPen(qcolor)
    pen.setWidthF(stroke)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    path = QPainterPath()
    path.moveTo(size * 0.22, size * 0.52)
    path.lineTo(size * 0.42, size * 0.74)
    path.lineTo(size * 0.78, size * 0.28)
    p.drawPath(path)

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
