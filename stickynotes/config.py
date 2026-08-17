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

# Bound shortcuts — single source of truth for every QShortcut the app installs.
#
# Consumed by StickyNote._setup_shortcuts (which binds them), FormatBar (which
# shows them in tooltips), and SHORTCUT_REFERENCE below (which lists them in the
# Keyboard Shortcuts dialog). One dict means a rebinding can't leave any of
# those three advertising a key that no longer works.
#
# The formatting keys match FormatBar button attribute names (bold_btn -> "bold").
SHORTCUTS = {
    "new_note":  "Ctrl+N",
    "bold":      "Ctrl+B",
    "italic":    "Ctrl+I",
    "underline": "Ctrl+U",
    "strike":    "Ctrl+Shift+S",
    "bullet":    "Ctrl+Shift+L",
    "checklist": "Ctrl+Shift+K",
}

# Reference table rendered by ShortcutsDialog: [(section, [(keys, what)])].
#
# Deliberately broader than SHORTCUTS. The genuinely undiscoverable interactions
# in this app aren't QShortcuts at all — Tab/Shift+Tab/Shift+Enter are handled in
# NoteTextEdit.keyPressEvent, and collapse/rename/resize are mouse gestures. A
# dialog that listed only the bound keys would omit exactly the features users
# never find. Bound entries index SHORTCUTS so they can't drift.
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
        # No ●→○→■ glyphs here: U+25A0 falls through to an emoji font on common
        # Linux setups and renders as a coloured box. Described in words instead.
        ("Tab",               "Indent to a sublist (bullet style changes each level)"),
        ("Shift+Tab",         "Outdent"),
        ("Shift+Enter",       "Break out of the list"),
    ]),
]

# Shown under the Lists section. Tab does nothing outside a list (it inserts a
# plain tab), so without this the entry reads as broken.
SHORTCUT_REFERENCE_FOOTNOTE = (
    "Tab, Shift+Tab, and Shift+Enter apply while the cursor is inside a list."
)

# Keycap chips in ShortcutsDialog. Unlike notes, dialogs inherit the SYSTEM
# palette, which may be light or dark — so these can't be a single hardcoded
# pair. A light chip with no explicit text colour renders invisible on a dark
# desktop theme (light text on a light chip), which is exactly what happens if
# you only style the background. Picked at runtime from the dialog's own palette.
KEYCAP_LIGHT = {"bg": "#f0f0f0", "border": "#d8d8d8", "text": "#333333"}
KEYCAP_DARK  = {"bg": "#3a3a3a", "border": "#555555", "text": "#f0f0f0"}

# Tooltips — app-wide chrome, deliberately NOT per-theme.
#
# Every button on a note is icon-only or a single letter, so tooltips are the
# only thing naming them. One consistent style across all seven themes reads
# as app chrome; a tooltip that recolored itself per note would read as content
# and compete with the note it's describing.
#
# Colors are borrowed from the charcoal theme (title/text) so the tooltip sits
# inside the existing palette instead of introducing an eighth set of colors.
# Fully OPAQUE on purpose: tooltips are separate top-level windows, so the same
# XWayland translucency caveat documented in _DeleteButton._apply_idle_style
# applies — an rgba background here can let content bleed through.
TOOLTIP_BACKGROUND_COLOR = "#333333"   # charcoal theme's title color
TOOLTIP_TEXT_COLOR = "#f0f0f0"         # charcoal theme's text color
TOOLTIP_BORDER_COLOR = "#5f5f5f"       # lighter than bg so the edge reads on dark notes too
TOOLTIP_CORNER_RADIUS_PX = 4           # deliberately tighter than CORNER_RADIUS_PX: tooltip
                                       # windows aren't shaped, so a large radius exposes
                                       # square-corner artifacts on some compositors
TOOLTIP_FONT_SIZE_PT = 9               # matches the secondary-text size used in AboutDialog
# Horizontal only. Qt already applies its own vertical margin inside the tooltip
# window, so adding vertical padding on top double-counts it — "5px 8px" renders
# a one-line tooltip 47px tall vs 33px here, which reads visibly puffy.
TOOLTIP_PADDING = "0px 6px"

# Legacy context-menu colors kept for tray menu styling
MENU_BACKGROUND_COLOR = "#ffffff"
MENU_TEXT_COLOR = "#000000"
MENU_TEXT_DISABLED_COLOR = "#999999"
MENU_HOVER_BACKGROUND_COLOR = "#0078d4"
MENU_HOVER_TEXT_COLOR = "#ffffff"
MENU_BORDER_COLOR = "#ccc"
MENU_SEPARATOR_COLOR = "#dddddd"
