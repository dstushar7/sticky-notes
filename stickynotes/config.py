
APP_NAME = "StickyNotesApp"
ORG_NAME = "dstushar7"

# Notes store the theme by name, so colour values can change freely; never rename or
# remove a key (unknown names fall back to DEFAULT_THEME). Text/body pairs meet WCAG AA.
THEMES = {
    "yellow":   {"name": "Yellow",   "bg": "#FFF39C", "title": "#FBE36E", "text": "#2B2410", "dark": False},
    "green":    {"name": "Green",    "bg": "#C6EFCF", "title": "#A3E2B2", "text": "#12291A", "dark": False},
    "pink":     {"name": "Pink",     "bg": "#FBCAD5", "title": "#F6A9BC", "text": "#36111B", "dark": False},
    "purple":   {"name": "Purple",   "bg": "#E0CCFB", "title": "#CBAAF7", "text": "#24113D", "dark": False},
    "blue":     {"name": "Blue",     "bg": "#C4EAFC", "title": "#9AD8F6", "text": "#0E2633", "dark": False},
    "gray":     {"name": "Gray",     "bg": "#E6E6E6", "title": "#CFCFCF", "text": "#1E1E1E", "dark": False},
    "charcoal": {"name": "Charcoal", "bg": "#3C3D41", "title": "#2E2F33", "text": "#F1F1F1", "dark": True},
}
DEFAULT_THEME = "yellow"
TITLE_BAR_HEIGHT = 38           # a collapsed note's saved height depends on it
SHADOW_GUTTER = 12          # transparent margin for the drop shadow
RESIZE_ZONE = 16            # >= SHADOW_GUTTER so the grip reaches the visible edge
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
TITLE_DRAG_SPACER_WIDTH = 40  # drag/collapse area right of the title

# Tray menu

# Persistence timing
SAVE_DEBOUNCE_MS = 500       # after the last move/resize

# Quiet time after an edge resize before the size locks again (StickyNote._lock_size).
SIZE_RELOCK_DELAY_MS = 1500

# Delete confirmation
DELETE_CONFIRM_WINDOW_MS = 4000   # how long Delete stays armed

# Shape tokens
CORNER_RADIUS_PX = 12        # matches current GNOME/Ubuntu windows
PANEL_RADIUS_PX = 14         # options menu, toast

# Per-note opacity: only the paper fades, and only while the note is idle.
# Notes saved before v4 have no value and stay opaque.
OPACITY_MIN = 50             # below this, light notes stop reading as notes
OPACITY_MAX = 100
OPACITY_STEP = 5
OPACITY_FADE_MS = 180        # idle <-> solid transition

# How long the "Note deleted · Undo" toast can bring a note back.
UNDO_DELETE_MS = 6000

# Glow when a note is picked from All notes or the tray menu.
FLASH_MS = 900

# How often the idle footer's "Edited 5 min ago" refreshes.
EDITED_LABEL_REFRESH_MS = 30_000

# How many recently edited notes the tray menu lists.
TRAY_MENU_RECENT_COUNT = 5

# Shadow profiles: (blur radius, y offset, alpha 0-255).
SHADOW_BUTTON_CHIP    = (6,  2, 90)
SHADOW_BODY_EXPANDED  = (24, 5, 130)
SHADOW_BODY_COLLAPSED = (14, 4, 175)
SHADOW_PANEL          = (16, 4, 80)

# App-wide, not per note: the dock lists the app if any one of its windows is listed.
SETTING_HIDE_FROM_DOCK = "hide_from_dock"

# Last version launched; drives the one-time What's new note.
SETTING_LAST_SEEN_VERSION = "last_seen_version"

# Colour for notes created from the tray or All notes (absent before v4 = DEFAULT_THEME).
SETTING_DEFAULT_THEME = "default_theme"

# How long Share shows "Copied" before the menu closes.
SHARE_COPIED_FEEDBACK_MS = 1500

# Every bound shortcut, used for binding, tooltips and the shortcuts list alike.
SHORTCUTS = {
    "new_note":  "Ctrl+N",
    "bold":      "Ctrl+B",
    "italic":    "Ctrl+I",
    "underline": "Ctrl+U",
    "strike":    "Ctrl+Shift+S",
    "bullet":    "Ctrl+Shift+L",
    "checklist": "Ctrl+Shift+K",
}

# The shortcuts list in Settings. Also lists gestures and in-list keys that aren't
# QShortcuts, since those are the ones people miss.
SHORTCUT_REFERENCE = [
    ("Notes", [
        (SHORTCUTS["new_note"],     "New note"),
        ("Double-click title bar",  "Collapse or expand a note"),
        ("Click the title",         "Rename a note"),
        ("Drag any edge or corner", "Resize a note"),
    ]),
    ("Formatting", [
        (SHORTCUTS["bold"],      "Bold"),
        (SHORTCUTS["italic"],    "Italic"),
        (SHORTCUTS["underline"], "Underline"),
        (SHORTCUTS["strike"],    "Strikethrough"),
    ]),
    ("Lists", [
        (SHORTCUTS["bullet"], "Toggle bullet list"),
        (SHORTCUTS["checklist"], "Toggle checklist"),
        ("Click a checkbox",  "Tick or untick that item"),
        # No ●○■ glyphs: some fonts draw U+25A0 as a coloured emoji box.
        ("Tab",               "Indent to a sublist (bullet style changes each level)"),
        ("Shift+Tab",         "Outdent"),
        ("Shift+Enter",       "Break out of the list"),
    ]),
]

# Tab only indents inside a list; without this note it looks broken.
SHORTCUT_REFERENCE_FOOTNOTE = (
    "Tab, Shift+Tab, and Shift+Enter apply while the cursor is inside a list."
)

# Keycap colours, picked from the window's light or dark system palette.
KEYCAP_LIGHT = {"bg": "#f0f0f0", "border": "#d8d8d8", "text": "#333333"}
KEYCAP_DARK  = {"bg": "#3a3a3a", "border": "#555555", "text": "#f0f0f0"}

# Tooltips: one app-wide style in the charcoal theme's colours. Opaque, because
# translucent top-level windows bleed through under XWayland.
TOOLTIP_BACKGROUND_COLOR = "#333333"   # charcoal theme's title color
TOOLTIP_TEXT_COLOR = "#f0f0f0"         # charcoal theme's text color
TOOLTIP_BORDER_COLOR = "#5f5f5f"       # lighter than bg so the edge reads on dark notes too
TOOLTIP_CORNER_RADIUS_PX = 4           # tooltip windows aren't shaped; a big radius shows square corners
TOOLTIP_FONT_SIZE_PT = 9               # secondary text size
# Horizontal only: Qt adds its own vertical margin.
TOOLTIP_PADDING = "0px 6px"

# App chrome follows the desktop's light/dark preference; notes keep their colours.
CHROME_LIGHT = {
    "window": "#FAFAFA", "surface": "#FFFFFF", "raised": "#F1F2F4", "hover": "#E9EBEE",
    "line": "#DEE1E6", "text": "#1B1D21", "muted": "#5F6672",
    "danger": "#C62828", "danger_soft": "#FDECEC", "ok": "#1E7B3C",
    "switch_on": "#3A7D44", "switch_off": "#CDD1D7",
}
CHROME_DARK = {
    "window": "#1F2126", "surface": "#2A2D33", "raised": "#33363D", "hover": "#3E424A",
    "line": "#3A3E46", "text": "#ECEEF1", "muted": "#A3A9B4",
    "danger": "#FF8A80", "danger_soft": "#43211F", "ok": "#6FD38F",
    "switch_on": "#4F9A5A", "switch_off": "#555A63",
}
# Primary buttons only, so the accent never competes with the notes.
ACCENT = "#F5C400"
ON_ACCENT = "#1A1A1A"
DONATE_GREEN = "#1E7B3C"
