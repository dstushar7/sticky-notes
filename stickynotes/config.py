# stickynotes/config.py

APP_NAME = "StickyNotesApp"
ORG_NAME = "dstushar7"

THEMES = {
    "yellow":   {"bg": "#FFF176", "title": "#F9E44A", "text": "#1a1a1a"},
    "green":    {"bg": "#B5EBBF", "title": "#8FD9A0", "text": "#1a1a1a"},
    "pink":     {"bg": "#F9B8C6", "title": "#F48FAA", "text": "#1a1a1a"},
    "purple":   {"bg": "#D8B8F9", "title": "#BC8FF5", "text": "#1a1a1a"},
    "blue":     {"bg": "#B3E5FC", "title": "#80D0F5", "text": "#1a1a1a"},
    "gray":     {"bg": "#E0E0E0", "title": "#BDBDBD", "text": "#1a1a1a"},
    "charcoal": {"bg": "#4A4A4A", "title": "#333333", "text": "#f0f0f0"},
}
DEFAULT_THEME = "yellow"
TITLE_BAR_HEIGHT = 38           # taller bar gives the floating chip buttons room to cast a shadow
SHADOW_GUTTER = 12          # transparent margin for the drop shadow
RESIZE_ZONE = 16            # >= SHADOW_GUTTER so resize grip reaches the visible note edge
MIN_NOTE_WIDTH = 160
MIN_NOTE_HEIGHT = 160
AUTOSAVE_INTERVAL_MS = 5000
FONT_FAMILY = "Segoe UI, Ubuntu, Sans Serif"
FONT_SIZE = 13
COLLAPSE_ANIMATION_MS = 150
LIST_INDENT_PX = 18         # bullet/sublist indent (Qt default is 40)

# Note titles
DEFAULT_NOTE_TITLE = "New Note"
MAX_TITLE_LENGTH = 40       # strict cap; enforced by the QLineEdit and tray menu
AUTO_SEED_WORD_COUNT = 2    # words pulled from the first body line as the smart default
TITLE_DRAG_SPACER_WIDTH = 40  # reserved drag/collapse grab area on the right of the title

# Tray menu
TRAY_MENU_NOTE_LIMIT = 10   # max number of notes listed in the tray menu

# Persistence timing
SAVE_DEBOUNCE_MS = 500       # delay after the last move/resize before flushing to QSettings

# Delete confirmation
DELETE_CONFIRM_WINDOW_MS = 4000   # how long the "armed" state stays armed before reverting

# Shape tokens
CORNER_RADIUS_PX = 8         # rounded-corner radius used by the note body, title bar, panels

# Shadow profiles — (blur radius, vertical offset, alpha 0–255) tuples.
# Each profile is tuned for the silhouette it sits behind:
#   BUTTON_CHIP — small chip on top of the title bar, blur fits inside the bar's vertical breathing room
#   BODY_EXPANDED — roomy soft shadow for the full note window
#   BODY_COLLAPSED — tighter denser shadow so the floating-pill feel survives without the body's silhouette
#   PANEL — softer mid-range shadow for the options popup
SHADOW_BUTTON_CHIP    = (6,  2, 90)
SHADOW_BODY_EXPANDED  = (24, 5, 130)
SHADOW_BODY_COLLAPSED = (14, 4, 175)
SHADOW_PANEL          = (16, 4, 80)

# Legacy context-menu colors kept for tray menu styling
MENU_BACKGROUND_COLOR = "#ffffff"
MENU_TEXT_COLOR = "#000000"
MENU_TEXT_DISABLED_COLOR = "#999999"
MENU_HOVER_BACKGROUND_COLOR = "#0078d4"
MENU_HOVER_TEXT_COLOR = "#ffffff"
MENU_BORDER_COLOR = "#ccc"
MENU_SEPARATOR_COLOR = "#dddddd"
