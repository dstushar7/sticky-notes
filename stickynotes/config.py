# stickynotes/config.py

APP_NAME = "StickyNotesApp"
ORG_NAME = "dstushar7"

# v4 palette: same seven colours, a touch softer, with text tinted toward each
# hue so a note reads as paper rather than plastic. Every text/body pair clears
# WCAG AA (4.5:1). "dark" marks the one theme that needs light chrome.
#
# DATA SAFETY: notes store the theme by NAME (e.g. "yellow"), never by colour,
# so changing these values only changes how existing notes look. Never rename
# or remove a key here — a note saved with an unknown name falls back to
# DEFAULT_THEME (see utils.get_theme), which would silently recolour it.
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
TITLE_BAR_HEIGHT = 38           # unchanged since v3: a collapsed note's saved height derives from it
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

# Persistence timing
SAVE_DEBOUNCE_MS = 500       # delay after the last move/resize before flushing to QSettings

# How long after an edge-resize goes quiet before the note's size is locked
# again (see StickyNote._lock_size). Long enough that a pause mid-drag doesn't
# freeze the resize under the pointer, short enough to close the window in
# which a tiling shortcut could still act on the note.
SIZE_RELOCK_DELAY_MS = 1500

# Delete confirmation
DELETE_CONFIRM_WINDOW_MS = 4000   # how long the "armed" state stays armed before reverting

# Shape tokens
CORNER_RADIUS_PX = 12        # note body + title bar; matches current GNOME/Ubuntu windows
PANEL_RADIUS_PX = 14         # options menu, toast

# Per-note opacity (v4). Only the note's paper fades — text, checkboxes and
# buttons stay solid — and only while the note is idle: hovering it or typing
# in it shows it at 100%. Stored per note under notes/<id>/opacity; a note
# without the key (every note saved before v4) is fully opaque.
OPACITY_MIN = 50             # below this, light notes stop reading as notes
OPACITY_MAX = 100
OPACITY_STEP = 5
OPACITY_FADE_MS = 180        # idle <-> solid transition

# How long a deleted note can be brought back from the "Note deleted · Undo"
# toast. The note's saved values are held in memory only for this window;
# deletion itself is unchanged (the QSettings group is removed immediately).
UNDO_DELETE_MS = 6000

# "Bring forward" glow when a note is picked from All notes / the tray menu.
FLASH_MS = 900

# How often the idle footer's "Edited 5 min ago" refreshes.
EDITED_LABEL_REFRESH_MS = 30_000

# Tray menu: how many recently edited notes are listed directly.
TRAY_MENU_RECENT_COUNT = 5

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

# QSettings key for the app-global "hide notes from the dock" preference.
# App-level, deliberately not per-note: the dock shows an app as running if ANY
# of its windows is listed, so hiding only some notes would achieve nothing.
SETTING_HIDE_FROM_DOCK = "hide_from_dock"

# QSettings key for the last app version this user launched. Drives the
# one-time "What's new" note (see whats_new.py).
SETTING_LAST_SEEN_VERSION = "last_seen_version"

# QSettings key (v4) for the colour of notes created from the tray / All notes.
# Absent for every pre-v4 install, which reads as DEFAULT_THEME — the same
# colour those versions always used. The + on a note still copies that note.
SETTING_DEFAULT_THEME = "default_theme"

# Share: how long the Share button reads "✓ Copied" before the panel closes.
SHARE_COPIED_FEEDBACK_MS = 1500

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

# App chrome (options menu, All notes, Settings, Receive, toast) follows the
# desktop's light/dark preference; notes keep their own colours either way.
# Picked at runtime by utils.chrome_palette(). Opaque on purpose — see the
# XWayland translucency note on the options menu.
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
# Primary buttons: the sticky-note yellow with near-black text, used sparingly
# so it never competes with the notes themselves.
ACCENT = "#F5C400"
ON_ACCENT = "#1A1A1A"
DONATE_GREEN = "#1E7B3C"
