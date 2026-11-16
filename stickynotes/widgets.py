"""Reusable widgets: ToggleSwitch, MenuRow, FloatingButton and GlassSurface."""

import math
from enum import Enum
from PyQt6.QtCore import Qt, QSize, QRectF, QPointF, pyqtSignal, QPropertyAnimation, pyqtProperty, QEasingCurve
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QLinearGradient, QPen, QBrush
from PyQt6.QtWidgets import (
    QPushButton, QAbstractButton, QWidget, QHBoxLayout, QLabel,
    QSizePolicy,
)

from . import config


class ToggleSwitch(QAbstractButton):
    """A small on/off switch, coloured from its window's chrome palette."""

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self._pal = pal
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(42, 24)
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def sizeHint(self) -> QSize:
        return QSize(42, 24)

    def _get_knob(self) -> float:
        return self._pos

    def _set_knob(self, value: float):
        self._pos = value
        self.update()

    knob = pyqtProperty(float, _get_knob, _set_knob)

    def _animate(self, checked: bool):
        self._anim.stop()
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def setChecked(self, checked: bool):   # noqa: N802 (Qt naming)
        super().setChecked(checked)
        self._anim.stop()
        self._pos = 1.0 if checked else 0.0
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = QColor(self._pal["switch_on"])
        off = QColor(self._pal["switch_off"])
        t = self._pos
        track = QColor(
            int(off.red() + (on.red() - off.red()) * t),
            int(off.green() + (on.green() - off.green()) * t),
            int(off.blue() + (on.blue() - off.blue()) * t),
        )
        if not self.isEnabled():
            track.setAlpha(110)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 12, 12)
        knob = QRectF(3 + t * (self.width() - 24), 3, 18, 18)
        p.setBrush(QColor(255, 255, 255, 255 if self.isEnabled() else 170))
        p.drawEllipse(knob)
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QColor(config.ACCENT))
            p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 12, 12)


class MenuRow(QWidget):
    """One popup-menu row: icon, label and a right-aligned hint."""
    clicked = pyqtSignal()

    def __init__(self, text: str, hint: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("menuRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(36)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(12)
        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(18, 18)
        self.text_label = QLabel(text, self)
        self.hint_label = QLabel(hint, self)
        self.hint_label.setObjectName("menuHint")
        self.hint_label.setVisible(bool(hint))
        lay.addWidget(self.icon_label)
        lay.addWidget(self.text_label, 1)
        lay.addWidget(self.hint_label)
        self.setAccessibleName(text)

    def set_icon(self, icon, size: int = 18):
        self.icon_label.setPixmap(icon.pixmap(QSize(size, size)))

    def set_text(self, text: str):
        self.text_label.setText(text)
        self.setAccessibleName(text)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class FloatingButton(QPushButton):
    """A frosted pill button for the title bar and the format toolbar.
    Shortcuts in its tooltip are display-only; the real bindings live on the note.
    """

    class Tone(Enum):
        TITLE_BAR = "title_bar"
        TOOLBAR = "toolbar"

    TITLE_BAR_SIZE = 28

    # Frosted pills: a white wash with a brighter rim. The charcoal theme uses the dark set.
    _GLASS_LIGHT = {
        "idle":    "rgba(255, 255, 255, 0.30)",
        "hover":   "rgba(255, 255, 255, 0.58)",
        "pressed": "rgba(255, 255, 255, 0.22)",
        "checked": "rgba(255, 255, 255, 0.78)",
        "border":  "rgba(255, 255, 255, 0.45)",
    }
    _GLASS_DARK = {
        "idle":    "rgba(255, 255, 255, 0.10)",
        "hover":   "rgba(255, 255, 255, 0.20)",
        "pressed": "rgba(255, 255, 255, 0.06)",
        "checked": "rgba(255, 255, 255, 0.30)",
        "border":  "rgba(255, 255, 255, 0.16)",
    }

    def __init__(
        self,
        label: str = "",
        *,
        tone: "FloatingButton.Tone" = Tone.TITLE_BAR,
        checkable: bool = False,
        extra_css: str = "",
        font_css: str = "",
        tooltip: str = "",
        shortcut: str = "",
        hint: str = "",
        parent=None,
    ):
        super().__init__(label, parent)
        self._tone = tone
        self._extra_css = extra_css
        self._font_css = font_css
        # Keep keyboard focus in the text, or Ctrl+B/I/U stop working after a click.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCheckable(checkable)
        if tooltip:
            self.setAccessibleName(tooltip)
            visible = tooltip
            if shortcut:
                visible = f"{visible} ({shortcut})"
            if hint:
                visible = f"{visible} — {hint}"
            self.setToolTip(visible)
        if tone == FloatingButton.Tone.TITLE_BAR:
            self.setFixedSize(self.TITLE_BAR_SIZE, self.TITLE_BAR_SIZE)

    def set_extra_css(self, extra_css: str):
        """Replace the per-button CSS (e.g. bold); call apply_theme afterwards."""
        self._extra_css = extra_css

    def set_font_css(self, font_css: str):
        """Set the button's font-size CSS; call apply_theme afterwards."""
        self._font_css = font_css

    def apply_theme(self, text_color: str, is_dark_theme: bool):
        """Rebuild the stylesheet. Called on theme changes and resizes, since the radius scales."""
        glass = self._GLASS_DARK if is_dark_theme else self._GLASS_LIGHT
        # Clamped so the radius suits both 24px and 44px buttons.
        radius = max(6, min(12, int(self.height() * 0.27)))
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {glass['idle']};
                border: 1px solid {glass['border']};
                border-radius: {radius}px;
                color: {text_color};
                {self._font_css}
                {self._extra_css}
            }}
            QPushButton:hover {{
                background-color: {glass['hover']};
            }}
            QPushButton:pressed {{
                background-color: {glass['pressed']};
            }}
            QPushButton:checked {{
                background-color: {glass['checked']};
            }}
        """)

    @classmethod
    def apply_theme_to_all(cls, buttons, text_color: str, is_dark_theme: bool):
        """Bulk re-skin helper for a group of buttons sharing one palette."""
        for btn in buttons:
            btn.apply_theme(text_color, is_dark_theme)


class GlassSurface(QWidget):
    """A note's glass, painted in one pass so the layers never stack unevenly:
    frost, colour tint, a diagonal sheen, the title bar's sheen and hairline, then a
    bright inner edge. The title bar and body on top of it paint no background.
    Values live in config (GLASS_*).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tint = QColor("#FDEB85")
        self._tint_alpha = 1.0
        self._dark = False
        self._typing = False

    def set_theme(self, theme: dict):
        """Tint with the body and bar colours mixed half and half: the bar colour alone
        is too strong for a whole note, the body colour alone washes out as glass."""
        a, b = QColor(theme["bg"]), QColor(theme["title"])
        self._tint = QColor((a.red() + b.red()) // 2, (a.green() + b.green()) // 2,
                            (a.blue() + b.blue()) // 2)
        self._dark = bool(theme.get("dark"))
        self.update()

    def set_tint_alpha(self, alpha: float):
        self._tint_alpha = max(0.0, min(1.0, alpha))
        self.update()

    def set_typing(self, typing: bool):
        if typing != self._typing:
            self._typing = typing
            self.update()

    def coverage(self) -> float:
        """How much of what's behind the note the frost and tint hide (0..1)."""
        frost = (config.GLASS_FROST_DARK if self._dark else config.GLASS_FROST_LIGHT)[1]
        return 1.0 - (1.0 - self._tint_alpha) * (1.0 - frost)

    def paintEvent(self, _event):   # noqa: N802 (Qt naming)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.paint_glass(p)

    def paint_glass(self, p: QPainter):
        """Paint the whole surface in this widget's coordinates. Also called by the note
        body to restore the glass under a checkbox, with the painter clipped to that spot."""
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        dark = self._dark
        r = float(min(config.CORNER_RADIUS_PX, w / 2, h / 2))
        rect = QRectF(0, 0, w, h)
        shape = QPainterPath()
        shape.addRoundedRect(rect, r, r)

        def white(alpha: float) -> QColor:
            c = QColor(255, 255, 255)
            c.setAlphaF(max(0.0, min(1.0, alpha)))
            return c

        frost_hex, frost_alpha = config.GLASS_FROST_DARK if dark else config.GLASS_FROST_LIGHT
        frost = QColor(frost_hex)
        frost.setAlphaF(frost_alpha)
        p.fillPath(shape, frost)

        tint = QColor(self._tint)
        tint.setAlphaF(self._tint_alpha)
        p.fillPath(shape, tint)

        # Diagonal sheen, laid out like a CSS linear-gradient at the same angle.
        strength = config.GLASS_SHEEN_DARK if dark else config.GLASS_SHEEN_LIGHT
        angle = math.radians(config.GLASS_SHEEN_ANGLE_DEG)
        dx, dy = math.sin(angle), -math.cos(angle)
        half = (abs(w * dx) + abs(h * dy)) / 2
        centre = QPointF(w / 2, h / 2)
        sheen = QLinearGradient(centre - QPointF(dx, dy) * half, centre + QPointF(dx, dy) * half)
        sheen.setColorAt(0.0, white(strength))
        sheen.setColorAt(0.34, white(strength * 0.25))
        sheen.setColorAt(0.62, white(0.0))
        sheen.setColorAt(1.0, white(0.0))
        p.fillPath(shape, sheen)

        # Title bar: a soft sheen in place of a darker strip, and a hairline below it
        # (no hairline on a collapsed note, which is all bar).
        bar_h = min(float(config.TITLE_BAR_HEIGHT), float(h))
        top, bottom = config.GLASS_BAR_SHEEN_DARK if dark else config.GLASS_BAR_SHEEN_LIGHT
        bar_sheen = QLinearGradient(0, 0, 0, bar_h)
        bar_sheen.setColorAt(0.0, white(top))
        bar_sheen.setColorAt(1.0, white(bottom))
        bar_rect = QPainterPath()
        bar_rect.addRect(QRectF(0, 0, w, bar_h))
        p.fillPath(shape.intersected(bar_rect), bar_sheen)
        if h > bar_h + r:
            line_hex, line_alpha = config.GLASS_BAR_LINE_DARK if dark else config.GLASS_BAR_LINE_LIGHT
            line = QColor(line_hex)
            line.setAlphaF(line_alpha)
            p.fillRect(QRectF(0, bar_h - 1, w, 1), line)

        # Inner edge, brightest along the top like light catching the rim.
        side = config.GLASS_EDGE_TYPING_ALPHA if self._typing else config.GLASS_EDGE_ALPHA
        edge = QLinearGradient(0, 0, 0, h)
        edge.setColorAt(0.0, white(max(side, config.GLASS_EDGE_TOP_ALPHA)))
        edge.setColorAt(min(0.99, r / h), white(side))
        edge.setColorAt(1.0, white(side))
        width = 1.5 if self._typing else 1.0
        p.setPen(QPen(QBrush(edge), width))
        p.setBrush(Qt.BrushStyle.NoBrush)
        inset = width / 2
        p.drawRoundedRect(rect.adjusted(inset, inset, -inset, -inset), r - inset, r - inset)
