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


class FloatingButton(QPushButton):
    """A QPushButton that paints as a translucent rounded pill.

    Two tones:
      * TITLE_BAR — fixed 32×32, carries a soft drop shadow so the button
        reads as a tactile floating chip on top of the title bar.
      * TOOLBAR — variable size (the format bar resizes its buttons with
        the note width), no shadow because adjacent buttons would otherwise
        pile shadows visually.

    Theming flows through `apply_theme(text_color, is_dark_theme)`. Call it
    after construction and again on every theme switch. `extra_css` is the
    per-button "personality" stylesheet (e.g. `font-weight: bold`) that
    survives every re-skin.
    """

    class Tone(Enum):
        TITLE_BAR = "title_bar"
        TOOLBAR = "toolbar"

    # Square chip dimension for title-bar tone buttons. Smaller than the bar
    # height so the drop shadow has vertical room to render before being
    # clipped by the title-bar bounds.
    TITLE_BAR_SIZE = 28

    # Translucent-white "glass" tokens. The same alpha values are reused for
    # every light theme; charcoal flips to a low-alpha white-on-dark recipe.
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
        parent=None,
    ):
        super().__init__(label, parent)
        self._tone = tone
        self._extra_css = extra_css
        self._font_css = font_css
        # Don't steal keyboard focus from the QTextEdit — otherwise Ctrl+B/I/U
        # shortcuts stop working once you click a toolbar button.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCheckable(checkable)
        if tone == FloatingButton.Tone.TITLE_BAR:
            self.setFixedSize(self.TITLE_BAR_SIZE, self.TITLE_BAR_SIZE)
            self._install_shadow()

    def _install_shadow(self):
        """Soft drop shadow for the floating-chip look. Blur is kept small
        so the shadow fits inside the title bar's vertical breathing room
        (~5 px above/below) without being clipped; alpha is tuned so it
        reads at a glance without darkening the bar visually."""
        eff = QGraphicsDropShadowEffect(self)
        eff.setBlurRadius(6)
        eff.setOffset(0, 2)
        eff.setColor(QColor(0, 0, 0, 90))
        self.setGraphicsEffect(eff)

    def set_extra_css(self, extra_css: str):
        """Replace the per-button personality CSS (e.g. font-weight: bold).
        Caller should invoke apply_theme afterwards to repaint."""
        self._extra_css = extra_css

    def set_font_css(self, font_css: str):
        """Set the font-size declaration for the button (e.g. 'font-size:
        14px;'). Used by FormatBar when scaling toolbar buttons. Caller
        should invoke apply_theme afterwards to repaint."""
        self._font_css = font_css

    def apply_theme(self, text_color: str, is_dark_theme: bool):
        """Rebuild the stylesheet using the current size, theme palette, and
        any per-button extra CSS. Safe to call repeatedly — used on theme
        change AND whenever the button is resized (so border-radius scales)."""
        glass = self._GLASS_DARK if is_dark_theme else self._GLASS_LIGHT
        # Border-radius scales with size — clamped so toolbar buttons stay
        # readable both at 24px (narrow note) and 44px (wide note).
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
