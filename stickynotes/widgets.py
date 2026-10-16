# stickynotes/widgets.py
"""
Reusable widgets that aren't tied to a single screen.

Currently houses FloatingButton — a QPushButton variant with a translucent
"glass" idle state, hover/pressed/checked transitions tuned to feel macOS-like,
and an optional drop shadow for the standalone title-bar buttons.
"""

from enum import Enum
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QPushButton, QGraphicsDropShadowEffect

from . import config


class FloatingButton(QPushButton):
    """A clean, modern flat QPushButton with subtle hover/pressed states.

    Tones:
      * TITLE_BAR — fixed 28×28 square, clean borderless flat button.
      * TOOLBAR — variable size, matches the format bar.
      * CLOSE — close button on title bar with standard red hover feedback.
    """

    class Tone(Enum):
        TITLE_BAR = "title_bar"
        TOOLBAR = "toolbar"
        CLOSE = "close"

    TITLE_BAR_SIZE = 28

    # Clean flat design tokens — idle state is completely transparent and borderless.
    _FLAT_LIGHT = {
        "idle":    "transparent",
        "hover":   "rgba(0, 0, 0, 0.08)",
        "pressed": "rgba(0, 0, 0, 0.16)",
        "checked": "rgba(0, 0, 0, 0.12)",
        "border":  "none",
    }
    _FLAT_DARK = {
        "idle":    "transparent",
        "hover":   "rgba(255, 255, 255, 0.12)",
        "pressed": "rgba(255, 255, 255, 0.22)",
        "checked": "rgba(255, 255, 255, 0.18)",
        "border":  "none",
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
        self._text_color = "#1a1a1a"
        self._is_dark_theme = False

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
        if tone in (FloatingButton.Tone.TITLE_BAR, FloatingButton.Tone.CLOSE):
            self.setFixedSize(self.TITLE_BAR_SIZE, self.TITLE_BAR_SIZE)
        self.apply_theme(self._text_color, self._is_dark_theme)

    def _install_shadow(self):
        """Deprecated: shadows removed in favor of clean modern flat aesthetic."""
        pass

    def enterEvent(self, event):
        super().enterEvent(event)
        if self._tone == FloatingButton.Tone.CLOSE and not self.icon().isNull():
            from . import utils
            sz = self.iconSize().width() or 16
            self.setIcon(utils.create_close_icon("#ffffff", sz))

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if self._tone == FloatingButton.Tone.CLOSE and not self.icon().isNull():
            from . import utils
            sz = self.iconSize().width() or 16
            self.setIcon(utils.create_close_icon(self._text_color, sz))

    def set_extra_css(self, extra_css: str):
        self._extra_css = extra_css

    def set_font_css(self, font_css: str):
        self._font_css = font_css

    def apply_theme(self, text_color: str, is_dark_theme: bool):
        self._text_color = text_color
        self._is_dark_theme = is_dark_theme
        palette = self._FLAT_DARK if is_dark_theme else self._FLAT_LIGHT
        radius = max(4, min(8, int(self.height() * 0.18)))

        if self._tone == FloatingButton.Tone.CLOSE:
            hover_bg = "rgba(232, 17, 35, 0.90)"
            pressed_bg = "#c42b1c"
            hover_color = "#ffffff"
        else:
            hover_bg = palette['hover']
            pressed_bg = palette['pressed']
            hover_color = text_color

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {palette['idle']};
                border: {palette['border']};
                border-radius: {radius}px;
                color: {text_color};
                {self._font_css}
                {self._extra_css}
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
                color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {pressed_bg};
                color: {hover_color};
            }}
            QPushButton:checked {{
                background-color: {palette['checked']};
            }}
        """)

    @classmethod
    def apply_theme_to_all(cls, buttons, text_color: str, is_dark_theme: bool):
        for btn in buttons:
            btn.apply_theme(text_color, is_dark_theme)
