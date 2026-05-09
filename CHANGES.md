# Session Changelog — Windows 11 UI Redesign

**Date:** 2026-05-09  
**Branch:** main  
**Author:** dstushar7

This document records every code-level change made during the Windows 11 Sticky Notes UI redesign session.

---

## Files Modified

### `stickynotes/config.py`

**Before:** Flat color constants (`NOTE_BACKGROUND_COLOR`, `NOTE_TEXT_COLOR`, `NOTE_BORDER_COLOR`) with no theming system.

**After:**
- Replaced individual color constants with a `THEMES` dict containing 7 named themes (yellow, green, pink, purple, blue, gray, charcoal). Each theme entry has `bg`, `title`, and `text` keys.
- Added layout/sizing constants: `TITLE_BAR_HEIGHT = 32`, `RESIZE_ZONE = 8`, `MIN_NOTE_WIDTH = 160`, `MIN_NOTE_HEIGHT = 160`.
- Added behavior constants: `AUTOSAVE_INTERVAL_MS = 5000`, `COLLAPSE_ANIMATION_MS = 150`.
- Added typography constants: `FONT_FAMILY`, `FONT_SIZE = 13`.
- Added `DEFAULT_THEME = "yellow"`.
- Kept legacy context-menu color constants for tray menu compatibility.

---

### `stickynotes/utils.py`

**Before:** Only contained `create_tray_icon()`, which used the old single background color constant.

**After:**
- `create_tray_icon()` now uses `config.THEMES[config.DEFAULT_THEME]["bg"]`.
- Added `get_theme(name: str) -> dict` — returns a theme dict, falls back to `DEFAULT_THEME` if the name is unknown. Prevents KeyErrors when loading old or corrupted saves.
- Added `apply_theme_to_window(window, theme: dict) -> None` — centralizes theme application by delegating to `window._apply_theme(theme)`.

---

### `stickynotes/note_window.py`

This file was fully rewritten. The old `StickyNote(QMainWindow)` is replaced with a new class hierarchy.

#### New class: `NoteTextEdit(QTextEdit)`
- Thin subclass of `QTextEdit`.
- Overrides `keyPressEvent` to intercept `Shift+Enter` when the cursor is inside a list: inserts a new paragraph outside the list (breaks out of the list) rather than inserting a line break within it.

#### New class: `OptionsPanel(QWidget)`
- A floating `Qt.WindowType.Popup | FramelessWindowHint` widget — not a `QMenu`.
- Automatically closes when the user clicks anywhere outside it (Popup flag handles this).
- **Row 1:** Seven 28×28 px circular color-swatch `QPushButton`s, one per theme. The currently active theme shows a `✓` checkmark. Hovering shows a white border ring.
- **Row 2:** "🗑 Delete Note" button (emits `deleteRequested`) and "📌 Always on Top" toggle button (emits `alwaysOnTopToggled(bool)`).
- Emits `themeSelected(str)` when a swatch is clicked, then closes itself.
- Has a `QGraphicsDropShadowEffect` and 8 px rounded corners via stylesheet.
- Fixed width: 220 px. Positioned just below and right-aligned to the `•••` button.

#### New class: `DragHandle(QWidget)`
- Expanding spacer widget that sits between the `+` and `•••` buttons in the title bar.
- `mousePressEvent` / `mouseMoveEvent`: implements click-and-drag window repositioning using `event.globalPosition()` and `window().move()`.
- `mouseDoubleClickEvent`: calls `window().toggle_collapse()` to collapse or expand the note.

#### New class: `TitleBar(QWidget)`
- Fixed height: 32 px. Object name `"titleBar"` for stylesheet targeting.
- Layout (left to right): `add_btn (+)` → `DragHandle` → `opts_btn (•••)`.
- `add_btn`: 32×32 px, font size 18 px, emits `newNoteRequested`.
- `opts_btn`: 32×32 px, font size 11 px, emits `optionsRequested`.
- `apply_colors(title_bg)`: restyled every time the theme changes — sets the `#titleBar` background, button transparency, and drag handle color.

#### Updated class: `StickyNote(QWidget)` (was `QMainWindow`)

**Constructor signature change:**
```python
# Old
StickyNote(note_id, content, geometry, parent)

# New
StickyNote(note_id, content, geometry_data, theme, always_on_top, collapsed, parent)
```

**Window flags:**
- `Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window`
- `Qt.WidgetAttribute.WA_TranslucentBackground`
- Drop shadow via `QGraphicsDropShadowEffect` on the `bg_widget` container.

**Layout:**
- Outer `QVBoxLayout` (no margins) → `bg_widget` (object name `noteBackground`, rounded corners 8 px).
- Inside `bg_widget`: `TitleBar` (fixed 32 px) + `NoteTextEdit` (fills remaining space).

**Theme application (`_apply_theme`):**
- Sets `bg_widget` background color and border radius.
- Calls `title_bar.apply_colors(title_bg)`.
- Sets `NoteTextEdit` text color, transparent background, no border, 8 px padding, and font.

**Persistence (`_save` / `closeEvent`):**
- Now saves `toHtml()` instead of `toPlainText()` — preserves bold, italic, underline, and bullet list formatting.
- Also persists: `theme` (string key), `always_on_top` (bool), `collapsed` (bool).
- `closeEvent` calls `_save()` unless `_is_being_deleted` is set.
- Autosave timer fires every 5 000 ms.

**Content loading:**
- Detects HTML vs plain text by checking `content.strip().startswith("<")`.
- Plain-text notes are loaded with `setPlainText()` — no data loss for existing saves.

**8-zone resize (event filter):**
- `eventFilter` is installed on every child `QWidget` after construction.
- Zone detection: outer 8 px on each edge and all four corners, using `_get_resize_zone(local_pos)`.
- On `MouseButtonPress` in a resize zone: captures `_resize_start_global` and `_resize_start_geo`, sets cursor, returns `True` (event consumed).
- On `MouseMove` while resizing: calls `_do_resize(gpos)` which computes the new `QRect` while enforcing `MIN_NOTE_WIDTH` / `MIN_NOTE_HEIGHT`.
- On `MouseButtonRelease`: clears resize state and resets cursor.
- When not resizing: updates the cursor shape as the mouse moves over different zones.
- Cursor shapes: `SizeVerCursor` (N/S), `SizeHorCursor` (E/W), `SizeBDiagCursor` (NE/SW), `SizeFDiagCursor` (NW/SE).

**Collapse / expand animation:**
- Uses `QParallelAnimationGroup` with two `QPropertyAnimation` targets (`minimumHeight` and `maximumHeight`) to animate height smoothly in 150 ms with `OutCubic` easing.
- `_collapse()`: saves current height, sets `minimumHeight = 0` to allow shrinking, animates both constraints to `TITLE_BAR_HEIGHT`, hides `text_edit` on `finished`.
- `_expand()`: shows `text_edit`, animates both constraints back to `_pre_collapse_height`, restores `setMinimumSize` / `setMaximumSize` to defaults on `finished`.
- `_collapse_immediately()`: used on load (no animation) — hides text edit, fixes height to `TITLE_BAR_HEIGHT`.

**Bullet list toggle (`_toggle_bullet_list`):**
- If cursor is in a list: iterates selected blocks, calls `list.remove(block)` and resets `blockFormat` indent to 0.
- If cursor is not in a list: calls `cursor.createList(QTextListFormat.Style.ListDisc)`.

**Options panel integration:**
- `_show_options_panel()`: toggles the panel (clicking `•••` again closes it); connects panel signals to `_change_theme`, `_handle_delete`, `_set_always_on_top`.
- `_change_theme(name)`: calls `_apply_theme`, saves, clears panel reference.
- `_set_always_on_top(enabled)`: toggles `WindowStaysOnTopHint`, calls `show()` to apply the flag, saves.

**Signal change:**
- `newNoteRequested` now emits `str` (theme name) instead of no argument, so the new note matches the current note's color.

---

### `stickynotes/tray_manager.py`

**`_create_new_note` signature:**
```python
# Old
_create_new_note(note_id, content, geometry)

# New
_create_new_note(note_id, content, geometry_data, theme, always_on_top, collapsed)
```

- `theme` defaults to `config.DEFAULT_THEME` if not supplied.

**`_new_note_from_signal(theme_name: str)`:**
- New slot connected to `StickyNote.newNoteRequested`. Forwards the theme name so the new note inherits the originating note's color.

**`_load_notes`:**
- Now reads `theme`, `always_on_top`, `collapsed` from `QSettings` in addition to `content` and `geometry`.
- `always_on_top` and `collapsed` use `type=bool` in `settings.value()` to avoid string-vs-bool issues across platforms.

**Tray "New Note" action:**
- Still calls `_create_new_note()` with no arguments, so it defaults to `DEFAULT_THEME` (Yellow) as specified.

---

## What Was NOT Changed

| Item | Status |
|------|--------|
| `snap/snapcraft.yaml` | Untouched |
| `run_stickynotes.py` | Untouched |
| `requirements.txt` | Untouched — PyQt6 ≥ 6.5 covers all new APIs used |
| `stickynotes/__init__.py` | Untouched |
| Tray icon right-click menu | Preserved (New Note / Show All / Quit) |
| Note auto-save behavior | Preserved and extended |
| Note position/size persistence | Preserved |

---

## Migration Notes for Existing Saves

Old saves store plain text under `{note_id}/content` in `QSettings`. On first load after this update:
- The content string is checked: if it does **not** start with `<`, it is loaded with `setPlainText()`.
- On the next autosave (within 5 seconds), it is re-saved as HTML.
- No data is lost.

Old saves have no `theme`, `always_on_top`, or `collapsed` keys — `QSettings.value()` falls back to `config.DEFAULT_THEME`, `False`, and `False` respectively.

---

## Known Limitations

- On Linux compositors that do not support `WA_TranslucentBackground` (e.g., plain X11 without a compositor), rounded corners and drop shadow may not render — this is a platform limitation.
- The right-click context menu (cut/copy/paste/undo/redo) was removed since all note actions moved to the `•••` panel. Standard clipboard shortcuts (`Ctrl+X/C/V/Z`) still work.
- Nested or mixed-indent bullet lists are not handled in `_remove_list` — only top-level `ListDisc` lists are toggled.
