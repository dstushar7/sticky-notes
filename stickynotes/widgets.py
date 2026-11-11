"""Reusable widgets: ToggleSwitch, MenuRow and FloatingButton."""

from enum import Enum
from PyQt6.QtCore import Qt, QSize, QRectF, pyqtSignal, QPropertyAnimation, pyqtProperty, QEasingCurve
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QPushButton, QGraphicsDropShadowEffect, QAbstractButton, QWidget, QHBoxLayout, QLabel,
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
    """A translucent rounded pill button for the title bar and the format toolbar.
    Shortcuts in its tooltip are display-only; the real bindings live on the note.
    """

    class Tone(Enum):
        TITLE_BAR = "title_bar"
        TOOLBAR = "toolbar"

    # Smaller than the bar so the drop shadow isn't clipped.
    TITLE_BAR_SIZE = 28

    # Translucent "glass" colours; the charcoal theme uses the dark set.
    _GLASS_LIGHT = {
        "idle":    "rgba(255, 255, 255, 0.55)",
        "hover":   "rgba(255, 255, 255, 0.75)",
        "pressed": "rgba(255, 255, 255, 0.40)",
        "checked": "rgba(255, 255, 255, 0.85)",
        "border":  "rgba(0, 0, 0, 0.08)",
    }
    _GLASS_DARK = {
        "idle":    "rgba(255, 255, 255, 0.10)",
        "hover":   "rgba(255, 255, 255, 0.22)",
        "pressed": "rgba(255, 255, 255, 0.06)",
        "checked": "rgba(255, 255, 255, 0.28)",
        "border":  "rgba(255, 255, 255, 0.15)",
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
            self._install_shadow()

    def _install_shadow(self):
        """Soft drop shadow (config.SHADOW_BUTTON_CHIP)."""
        eff = QGraphicsDropShadowEffect(self)
        blur, offset_y, alpha = config.SHADOW_BUTTON_CHIP
        eff.setBlurRadius(blur)
        eff.setOffset(0, offset_y)
        eff.setColor(QColor(0, 0, 0, alpha))
        self.setGraphicsEffect(eff)

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
