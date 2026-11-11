
import math

from PyQt6.QtGui import (
    QPainter, QColor, QPixmap, QIcon, QPen, QPolygonF, QPainterPath, QGuiApplication,
)
from PyQt6.QtCore import Qt, QPointF, QRectF
from . import config


def _note_glyph(p: QPainter, rect: QRectF):
    """A tiny sticky note: rounded yellow paper with a darker title band."""
    theme = config.THEMES[config.DEFAULT_THEME]
    radius = rect.width() * 0.2
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    p.save()
    p.setClipPath(path)
    p.fillRect(rect, QColor(theme["bg"]))
    band = QRectF(rect.left(), rect.top(), rect.width(), rect.height() * 0.3)
    p.fillRect(band, QColor(theme["title"]))
    p.restore()
    pen = QPen(QColor(0, 0, 0, 60))
    pen.setWidthF(max(1.0, rect.width() / 24))
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(rect, radius, radius)


def create_tray_icon() -> QIcon:
    """The app's sticky-note glyph, at the sizes trays and dialogs ask for."""
    icon = QIcon()
    for size in (16, 22, 24, 32, 48, 64, 96):
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        inset = size * 0.1
        _note_glyph(p, QRectF(inset, inset, size - 2 * inset, size - 2 * inset))
        p.end()
        icon.addPixmap(pm)
    return icon


# App chrome palette (follows the desktop's light/dark mode).

def chrome_is_dark() -> bool:
    """True when the desktop prefers dark. Falls back to the window colour's lightness
    when Qt can't tell (some xcb setups).
    """
    app = QGuiApplication.instance()
    if app is None:
        return False
    try:
        scheme = app.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except AttributeError:
        pass
    return app.palette().window().color().lightness() < 128


def chrome_palette() -> dict:
    return dict(config.CHROME_DARK if chrome_is_dark() else config.CHROME_LIGHT)


def chrome_stylesheet(pal: dict) -> str:
    """Shared stylesheet for All notes, Settings and Receive. Variants via properties:
    QPushButton[kind=primary|green|danger], QLabel[role=muted|heading|title].
    """
    return f"""
        QWidget#chromeRoot {{ background-color: {pal['window']}; }}
        QWidget {{ color: {pal['text']}; }}
        QLabel {{ background: transparent; }}
        QLabel[role="muted"] {{ color: {pal['muted']}; font-size: 9pt; }}
        QLabel[role="heading"] {{ color: {pal['muted']}; font-size: 9pt; font-weight: 700; }}
        QLabel[role="title"] {{ font-size: 13pt; font-weight: 700; }}
        QLabel[role="ok"] {{ color: {pal['ok']}; font-weight: 600; }}
        QLabel[role="error"] {{ color: {pal['danger']}; }}
        QPushButton {{
            background-color: {pal['raised']}; color: {pal['text']};
            border: none; border-radius: 10px; padding: 8px 16px; font-weight: 600;
        }}
        QPushButton:hover {{ background-color: {pal['hover']}; }}
        QPushButton:disabled {{ color: {pal['muted']}; }}
        QPushButton[kind="primary"] {{ background-color: {config.ACCENT}; color: {config.ON_ACCENT}; }}
        QPushButton[kind="primary"]:hover {{ background-color: #E8B900; }}
        QPushButton[kind="primary"]:disabled {{ background-color: {pal['raised']}; color: {pal['muted']}; }}
        QPushButton[kind="green"] {{ background-color: {config.DONATE_GREEN}; color: #FFFFFF; }}
        QPushButton[kind="green"]:hover {{ background-color: #196A33; }}
        QLineEdit, QPlainTextEdit {{
            background-color: {pal['surface']}; color: {pal['text']};
            border: 1.5px solid {pal['line']}; border-radius: 10px; padding: 7px 10px;
            selection-background-color: {config.ACCENT}; selection-color: {config.ON_ACCENT};
        }}
        QLineEdit:focus, QPlainTextEdit:focus {{ border-color: {config.ACCENT}; }}
        QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
        QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: {pal['line']}; border-radius: 3px; min-height: 28px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        QFrame#group {{ background-color: {pal['surface']}; border: 1px solid {pal['line']}; border-radius: 12px; }}
        QFrame#divider {{ background-color: {pal['line']}; border: none; }}
    """


# Line icons, painted: the snap has no Qt SVG support, and emoji ignore the theme colour.

def _icon_path(name: str) -> tuple:
    """(stroke_path, fill_path, dashed_path) for `name` in a 24x24 grid."""
    s, f, d = QPainterPath(), QPainterPath(), QPainterPath()

    def line(*pts):
        s.moveTo(*pts[0])
        for pt in pts[1:]:
            s.lineTo(*pt)

    if name == "plus":
        line((5, 12), (19, 12)); line((12, 5), (12, 19))
    elif name == "x":
        line((6, 6), (18, 18)); line((18, 6), (6, 18))
    elif name == "check":
        line((5, 12.5), (9.5, 17), (19, 7))
    elif name == "share":
        line((12, 15), (12, 3)); line((7, 8), (12, 3), (17, 8))
        line((5, 13), (5, 19), (19, 19), (19, 13))
    elif name == "receive":
        line((12, 3), (12, 15)); line((7, 10), (12, 15), (17, 10))
        line((5, 13), (5, 19), (19, 19), (19, 13))
    elif name == "fold":
        line((4, 6), (20, 6)); line((4, 11), (20, 11)); line((8.5, 15.5), (12, 19), (15.5, 15.5))
    elif name == "unfold":
        line((4, 6), (20, 6)); line((4, 11), (20, 11)); line((8.5, 19), (12, 15.5), (15.5, 19))
    elif name == "trash":
        line((4, 7), (20, 7)); line((6, 7), (7, 20), (17, 20), (18, 7))
        line((9, 7), (9, 4), (15, 4), (15, 7)); line((10, 11), (10, 16.5)); line((14, 11), (14, 16.5))
    elif name == "opacity":
        s.addRoundedRect(QRectF(3, 3, 12.5, 12.5), 2.5, 2.5)
        d.addRoundedRect(QRectF(8.5, 8.5, 12.5, 12.5), 2.5, 2.5)
    elif name == "search":
        s.addEllipse(QPointF(11, 11), 6.5, 6.5); line((16, 16), (20, 20))
    elif name == "grid":
        for x, y in ((4, 4), (13, 4), (4, 13), (13, 13)):
            s.addRoundedRect(QRectF(x, y, 7, 7), 1.5, 1.5)
    elif name == "front":
        s.addRoundedRect(QRectF(8, 8, 12, 12), 2, 2); line((16, 8), (16, 4), (4, 4), (4, 16), (8, 16))
    elif name == "gear":
        s.addEllipse(QPointF(12, 12), 6.5, 6.5); s.addEllipse(QPointF(12, 12), 2.5, 2.5)
        for i in range(8):
            a = math.radians(i * 45)
            line((12 + 6.5 * math.cos(a), 12 + 6.5 * math.sin(a)),
                 (12 + 9.5 * math.cos(a), 12 + 9.5 * math.sin(a)))
    elif name == "power":
        line((12, 3), (12, 11))
        s.arcMoveTo(QRectF(4, 4, 16, 16), 125)
        s.arcTo(QRectF(4, 4, 16, 16), 125, 290)
    elif name == "clock":
        s.addEllipse(QPointF(12, 12), 8.5, 8.5); line((12, 7.5), (12, 12), (15, 14))
    elif name == "keys":
        s.addRoundedRect(QRectF(2.5, 6, 19, 12), 2, 2); line((7, 14.5), (17, 14.5))
        for x in (6.5, 10, 13.5, 17):
            f.addEllipse(QPointF(x, 10), 0.9, 0.9)
    elif name == "info":
        s.addEllipse(QPointF(12, 12), 9, 9); line((12, 11), (12, 17)); f.addEllipse(QPointF(12, 7.8), 1.1, 1.1)
    elif name == "undo":
        line((9, 14), (4, 9), (9, 4))
        s.moveTo(4, 9); s.lineTo(14, 9); s.cubicTo(17.5, 9, 20, 11.7, 20, 15)
        s.cubicTo(20, 18.3, 17.5, 21, 14, 21); s.lineTo(11, 21)
    elif name == "list":
        line((9, 6), (20, 6)); line((9, 12), (20, 12)); line((9, 18), (20, 18))
        for y in (6, 12, 18):
            f.addEllipse(QPointF(4.5, y), 1.2, 1.2)
    return s, f, d


def line_icon(name: str, color: str, size: int = 18, stroke: float = 1.9) -> QIcon:
    """A single-colour stroke icon from _icon_path, drawn at 2x for HiDPI."""
    scale = 2
    pm = QPixmap(size * scale, size * scale)
    pm.setDevicePixelRatio(scale)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 24, size / 24)
    s, f, d = _icon_path(name)
    pen = QPen(QColor(color))
    pen.setWidthF(stroke)   # in grid units; the painter is scaled to `size`
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(s)
    if not d.isEmpty():
        pen.setDashPattern([1.6, 1.6])
        p.setPen(pen)
        p.drawPath(d)
    if not f.isEmpty():
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        p.drawPath(f)
    p.end()
    return QIcon(pm)


def color_dot_icon(fill: str, size: int = 14) -> QIcon:
    """A filled circle in a note colour — the tray menu's recent-note marker."""
    scale = 2
    pm = QPixmap(size * scale, size * scale)
    pm.setDevicePixelRatio(scale)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(0, 0, 0, 70), 1))
    p.setBrush(QColor(fill))
    p.drawEllipse(QRectF(1.5, 1.5, size - 3, size - 3))
    p.end()
    return QIcon(pm)


def create_bullet_list_icon(color: str, size: int = 24) -> QIcon:
    """A 'bulleted list' icon: three small dots, each followed by a short bar."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    qcolor = QColor(color)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(qcolor)

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
        p.drawEllipse(QPointF(margin_x + bullet_r, cy), bullet_r, bullet_r)
        bar_rect = QRectF(bar_x, cy - bar_h / 2, bar_w, bar_h)
        p.drawRoundedRect(bar_rect, bar_h / 2, bar_h / 2)

    p.end()
    return QIcon(pm)


def create_checklist_icon(color: str, size: int = 24) -> QIcon:
    """A checklist icon: the bullet-list layout with boxes, the first one ticked."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
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

        pen = QPen(qcolor)
        pen.setWidthF(stroke)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(box_rect)

        # Tick only the first box.
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

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qcolor)
        bar_rect = QRectF(bar_x, cy - bar_h / 2, bar_w, bar_h)
        p.drawRoundedRect(bar_rect, bar_h / 2, bar_h / 2)

    p.end()
    return QIcon(pm)


def create_pin_icon(color: str, size: int = 24, filled: bool = True) -> QIcon:
    """A thumbtack, painted because pin emoji ignore the theme colour.
    Solid when pinned, outline when not.
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
        # Scale the stroke so it stays visible at 16px without going chunky at 24px.
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
    # A wide shoulder tapering to a point: that shape reads as a thumbtack.
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
    """App-wide tooltip stylesheet, applied once to the QApplication."""
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
    """Theme dict for `name`, falling back to DEFAULT_THEME."""
    return config.THEMES.get(name, config.THEMES[config.DEFAULT_THEME])


def apply_theme_to_window(window, theme: dict) -> None:
    """Applies bg color, title bar color, and text color to a StickyNote window."""
    window._apply_theme(theme)
