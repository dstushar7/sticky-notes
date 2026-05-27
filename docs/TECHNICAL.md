# Sticky Notes — Technical Documentation

> Version: **3.2.6** · License: MIT · Source: [github.com/dstushar7/sticky-notes](https://github.com/dstushar7/sticky-notes) · Store: [snapcraft.io/stickynotes-dabobroto](https://snapcraft.io/stickynotes-dabobroto)

This document is the engineering companion to the codebase: it explains **what** the app is, **how** the code is organized, **why** every non-obvious decision was made, and what trade-offs were accepted along the way. It is written for new contributors and future maintainers, not end users — for the user-facing description see [`README.md`](../README.md) and the Snap Store listing.

---

## Table of contents

1. [Project goals and positioning](#1-project-goals-and-positioning)
2. [Tech stack and dependencies](#2-tech-stack-and-dependencies)
3. [Repository layout](#3-repository-layout)
4. [High-level architecture](#4-high-level-architecture)
5. [Module deep dives](#5-module-deep-dives)
6. [Data model and persistence](#6-data-model-and-persistence)
7. [UI design system](#7-ui-design-system)
8. [Keyboard, formatting, and list semantics](#8-keyboard-formatting-and-list-semantics)
9. [Display-server compatibility (X11 / Wayland / XWayland)](#9-display-server-compatibility-x11--wayland--xwayland)
10. [Autostart](#10-autostart)
11. [System tray integration](#11-system-tray-integration)
12. [Snap packaging](#12-snap-packaging)
13. [Build and release pipeline](#13-build-and-release-pipeline)
14. [Marketing and store listing](#14-marketing-and-store-listing)
15. [Known limitations and accepted trade-offs](#15-known-limitations-and-accepted-trade-offs)
16. [Future work](#16-future-work)

---

## 1. Project goals and positioning

### What the app is

Sticky Notes is a **frameless, glass-styled, tray-resident sticky-notes desktop app for Linux**. The user creates as many notes as they like; each note is its own draggable, resizable, rounded-corner window with a custom title bar, rich-text body, and a translucent format toolbar. Notes persist content, geometry, theme, title, collapse state, and last-edited time across sessions.

The functional surface is intentionally narrow: it is **only** a sticky-notes app. There is no cloud sync, no account system, no folders, no tags, no search, no markdown, no encryption, no telemetry, no multi-language support, no mobile. The lack of features is a positioning decision, not a backlog.

### Why this exists

The Linux sticky-notes space is dominated by two patterns:

- **Old-feeling GNOME panel applets** — functional but visually anchored in ~2006 aesthetics.
- **Heavy "second brain" feature-creep apps** — sticky notes that have grown into wikis, knowledge bases, or task managers with sync layers and account systems.

Sticky Notes targets the gap between them: a *new-looking, single-purpose* tool for users who want a tray app for ephemeral notes and nothing else. The brand voice (Snap Store description, README intro, in-app About text) deliberately leans into "deliberately minimal, deliberately pretty."

### Target users

- Linux desktop users who already think in terms of sticky notes on a physical desk.
- Developers, students, designers — people who keep TODOs, snippets, grocery lists, and one-off thoughts.
- Users who explicitly *do not* want cloud sync, accounts, or feature creep in a notes app.

### Non-goals

- Cross-device sync.
- Markdown rendering or links (deliberate — keeps the QTextEdit lightweight).
- Always-on-top (Wayland forbids it client-side; not worth platform-specific implementation).
- Multi-language UI (English only; would balloon the snap and complicate maintenance for solo dev).
- Windows / macOS port (would dilute the "Linux-native, properly trimmed" positioning).

---

## 2. Tech stack and dependencies

### Runtime

| Component | Version | Why |
|---|---|---|
| **Python** | 3.10+ | Modern typing (`X | Y`), structural pattern matching is optional but available. 3.10 is the floor of Ubuntu 22.04 LTS. |
| **PyQt6** | 6.9.1 (pinned) | Mature widget toolkit, excellent X11/Wayland support, native look-and-feel, signal/slot model fits the app's event-driven shape. Qt 6 was chosen over Qt 5 for long-term support (Qt 5 EOL'd in 2025 for open-source). |
| **PyQt6-Qt6** | 6.9.2 (pinned) | Bundled Qt6 runtime; locked to a known-good version because Qt updates have occasionally regressed Wayland behavior. |
| **PyQt6_sip** | 13.10.2 (pinned) | The sip glue that PyQt6 builds on; pinned for ABI stability. |
| **python-xlib** | 0.33 | Pure-Python X11 client library used solely to set `WM_NORMAL_HINTS / USPosition` on note windows (see [Display-server compatibility](#9-display-server-compatibility-x11--wayland--xwayland)). MIT-licensed, no compiled deps. |

### Packaging and distribution

| Tool | Why |
|---|---|
| **Snapcraft** (core24) | Single-package, cross-distro distribution. Auto-update via the Snap Store. Strict confinement is acceptable for this app's scope. |
| **`extensions: [gnome]`** | Pulls in the GNOME platform/runtime content snap so we ship only the app-specific bits. Gives the snap access to GTK/GNOME look, fonts, and XDG paths without bundling them. |
| **GitHub Actions** + `snapcore/action-build` + `snapcore/action-publish` | CI builds and publishes on push to `main`. |

### Why these and not alternatives

- **PyQt6 vs PySide6**: PyQt6 has a slightly more permissive licensing model for non-commercial open-source via GPL/Riverbank's terms; the codebase is GPL-compatible (MIT). Either would have worked; PyQt6 was picked for familiarity.
- **Qt vs GTK4 + LibAdwaita**: GTK4/LibAdwaita is the "GNOME-native" choice. Rejected because Qt's `QTextEdit` rich-text model is more mature, and Qt's cross-platform widget abstraction makes per-window decorations and the glass-pill aesthetic easier to implement.
- **Electron**: Rejected. The whole brand is "~26 MB installed." An Electron app starts at ~150 MB minimum.
- **Flatpak vs Snap**: Snap was chosen because Ubuntu (the dev's primary target) ships Snap Store out of the box, and Snap's strict-confinement model maps cleanly to the app's narrow capability requirements (just `home` + a `personal-files` candidate that we deferred — see [Autostart](#10-autostart)).

---

## 3. Repository layout

```
sticky-notes/
├── snap/
│   ├── snapcraft.yaml         # Snap build manifest + listing copy
│   ├── gui/
│   │   ├── stickynotes.desktop  # XDG desktop entry (menu + autostart source)
│   │   └── stickynotes.png      # App icon (used by desktop entry + tray)
│   └── qt6-launch              # Helper launcher (if needed by extension)
│
├── stickynotes/                # Main Python package
│   ├── __init__.py             # Just __version__ = "3.2.6"
│   ├── config.py               # All constants: themes, sizing, animation, paths
│   ├── utils.py                # Icon creation, theme lookup, helpers
│   ├── widgets.py              # FloatingButton (reusable glass-pill button)
│   ├── note_window.py          # The big module — all widgets except FloatingButton
│   ├── tray_manager.py         # Tray icon, note lifecycle, dynamic menu
│   ├── autostart.py            # XDG autostart desktop-file management
│   └── xwm.py                  # X11 USPosition helper (Wayland positioning fix)
│
├── run_stickynotes.py          # Entry point — Qt app bootstrap + platform env
├── requirements.txt            # pip deps for source builds
├── docs/
│   └── TECHNICAL.md            # This file
├── README.md                   # User-facing project documentation
├── LICENSE                     # MIT
└── .github/workflows/          # CI: build snap, push to edge on main
```

### `note_window.py` is large by design

The classes in `note_window.py` are tightly coupled: `StickyNote` owns a `TitleBar`, a `NoteTextEdit`, a `FormatBar`, and an `OptionsPanel`, all of which interact via Qt signals and shared state (theme, geometry, collapse). Splitting them into separate files would create a sprawl of cross-module imports for very little gain. The trade-off is one ~1700-line file vs five highly-coupled smaller files; one file won.

The same module also houses `AboutDialog` and `SettingsDialog` — both are simple `QDialog` subclasses with no relationship to the note-window classes other than living in the same UI layer. They sit there because creating a `dialogs.py` for two small classes felt premature.

---

## 4. High-level architecture

```
                ┌────────────────────────────────────────────────┐
                │            run_stickynotes.py (entry)          │
                │  - Force QT_QPA_PLATFORM=xcb;wayland            │
                │  - Optionally wait for XWayland on autostart    │
                │  - Construct QApplication + TrayManager         │
                └────────────────────────────────────────────────┘
                                       │
                                       ▼
                ┌────────────────────────────────────────────────┐
                │              TrayManager (singleton)            │
                │  - QSystemTrayIcon + dynamic QMenu              │
                │  - Owns the dict of open StickyNote instances   │
                │  - Loads/restores notes from QSettings on init  │
                │  - Handles welcome note + autostart-default-on  │
                │  - Self-heals stale autostart .desktop files    │
                │  - Schedules deferred reapply on Wayland        │
                └────────────────────────────────────────────────┘
                       │            │            │            │
            ┌──────────┘            │            │            └──────────┐
            ▼                       ▼            ▼                       ▼
  ┌─────────────────┐   ┌─────────────────┐  ┌───────────┐    ┌─────────────────┐
  │ StickyNote × N  │   │ SettingsDialog  │  │ AboutDlg  │    │ autostart.py    │
  │ (one window     │   │ (modeless)      │  │           │    │ (XDG .desktop   │
  │  per note)      │   │ - autostart cb  │  │ - version │    │   write/remove) │
  │ - TitleBar      │   └─────────────────┘  │ - links   │    └─────────────────┘
  │ - NoteTextEdit  │                        └───────────┘
  │ - FormatBar     │                                                ▲
  │ - OptionsPanel  │                                                │
  │ - Geometry +    │                                                │
  │   persistence   │       ┌────────────────────────────────────────┘
  │ - Theme + paint │       │
  └─────────────────┘       │
            │               │
            ▼               │
  ┌─────────────────┐       │
  │ QSettings (INI) │◄──────┘
  │ ~/.config/      │   (read on TrayManager.__init__,
  │  dstushar7/     │    written by StickyNote._save())
  │  StickyNotesApp │
  │  .conf          │
  └─────────────────┘
```

### Process lifecycle

1. `run_stickynotes.py` is invoked.
2. **Before any PyQt6 import**, `os.environ["QT_QPA_PLATFORM"] = "xcb;wayland"` is set. This is critical and must happen before Qt initializes (see [§9](#9-display-server-compatibility-x11--wayland--xwayland)).
3. If launched via `--autostart` (the flag is added to the autostart desktop file's `Exec=` line) AND the session is Wayland, `_wait_for_xwayland_on_autostart()` polls for `/tmp/.X11-unix/X0` to exist. This is a workaround for a known XWayland-readiness race documented in upstream Qt and CopyQ issues.
4. `QApplication(sys.argv)` is constructed.
5. App-level identity is set: `setOrganizationName`, `setApplicationName`, `setApplicationDisplayName`, `setDesktopFileName`. The last two power Mutter's per-app window-grouping logic.
6. `TrayManager(app)` is constructed:
   - Builds the tray icon and dynamic menu.
   - Calls `_load_notes()` which iterates over the `notes` group in `QSettings` and creates one `StickyNote` per stored entry.
   - Runs the **first-launch / autostart-silent / welcome-note** decision tree (see [§10](#10-autostart)).
   - Runs the **autostart self-heal** (rewrites the autostart `.desktop` file with current Exec format so users upgrading from older versions get their entry migrated automatically).
7. `app.exec()` enters the Qt event loop. The app is now alive in the tray.
8. On `app.aboutToQuit` (graceful quit, session logout, OS shutdown), `_save_all_notes` flushes every open note's state to QSettings.

### Inter-component communication

The app is signal-driven (Qt's signal/slot system). Key signals:

| Emitter | Signal | Receiver | Purpose |
|---|---|---|---|
| `StickyNote` | `noteDeleted(str)` | `TrayManager._handle_note_deletion` | Remove note from QSettings + open_notes dict |
| `StickyNote` | `newNoteRequested(str theme_name)` | `TrayManager._new_note_from_signal` | Click the `+` button → new note in same theme |
| `EditableTitleLabel` | `committed(str)` | `StickyNote._on_title_committed` | Title edit committed (Enter or focus loss) |
| `FormatBar` | `boldClicked` / `italicClicked` / etc. | `StickyNote._toggle_bold` / etc. | Format-bar button → toggle character formatting |
| `OptionsPanel` | `themeSelected(str)` | `StickyNote._change_theme` | Pick a swatch in the popup |
| `OptionsPanel` | `deleteRequested` | `StickyNote._handle_delete` | Click "Delete Note" (after two-click confirm) |
| `QApplication` | `aboutToQuit` | `TrayManager._save_all_notes` | Flush all notes before process exit |

---

## 5. Module deep dives

### 5.1 `run_stickynotes.py` — Entry point

Single responsibility: set up the Qt environment correctly, then hand off to `TrayManager`.

Order-critical operations:

1. `os.environ["QT_QPA_PLATFORM"] = "xcb;wayland"` — must run **before** PyQt6 is imported. Qt reads this env var during `QGuiApplication` initialization. Setting it after `from PyQt6 import ...` (which imports `QGuiApplication`) would be too late. **`os.environ[...] = ...` is intentional, not `setdefault`** — the snap GNOME extension's launcher script pre-sets `QT_QPA_PLATFORM=wayland` based on `XDG_SESSION_TYPE`, and `setdefault` would have been a no-op. We need to overwrite.

2. `_wait_for_xwayland_on_autostart()` — only runs when `--autostart in sys.argv` and `XDG_SESSION_TYPE == "wayland"`. Polls `/tmp/.X11-unix/X0` for up to 5 minutes (with heartbeat log every 5 s). On Mutter/GNOME, XWayland starts lazily; if our autostart fires before the X server socket exists, Qt's xcb plugin falls back to the native wayland plugin where absolute positioning isn't supported. The poll closes that window.

3. Late imports — `from PyQt6...` only happens **after** the env var is set and the wait completed. This guarantees Qt sees the correct platform.

4. `main()`:
   - Constructs `QApplication`.
   - Diagnostic stderr log of `app.platformName()` (only when `--autostart` is in argv) — visible via `journalctl --user | grep stickynotes`, useful for confirming xcb actually loaded on autostart-on-Wayland.
   - Sets the four identity strings (`OrganizationName`, `ApplicationName`, `ApplicationDisplayName`, `DesktopFileName`). The last is what Mutter uses to associate the app with the `.desktop` file under `meta/gui/`.
   - Constructs `TrayManager(app)` and enters `app.exec()`.

### 5.2 `stickynotes/config.py` — Constants

Holds every tunable in one place. No logic, just module-level assignments. Organized by concern:

| Section | Contents |
|---|---|
| **Identity** | `APP_NAME`, `ORG_NAME` (used by `QSettings`) |
| **Themes** | `THEMES` dict (7 entries) + `DEFAULT_THEME = "yellow"` |
| **Window sizing** | `TITLE_BAR_HEIGHT`, `SHADOW_GUTTER`, `RESIZE_ZONE`, `MIN_NOTE_WIDTH`, `MIN_NOTE_HEIGHT` |
| **Timing** | `AUTOSAVE_INTERVAL_MS=5000`, `SAVE_DEBOUNCE_MS=500`, `COLLAPSE_ANIMATION_MS=150`, `DELETE_CONFIRM_WINDOW_MS=4000` |
| **Typography** | `FONT_FAMILY = "Segoe UI, Ubuntu, Sans Serif"`, `FONT_SIZE=13`, `LIST_INDENT_PX=18` |
| **Title** | `DEFAULT_NOTE_TITLE="New Note"`, `MAX_TITLE_LENGTH=40`, `AUTO_SEED_WORD_COUNT=2`, `TITLE_DRAG_SPACER_WIDTH=40` |
| **Tray** | `TRAY_MENU_NOTE_LIMIT=10` (max entries in "Show Note ▶" submenu) |
| **Shape tokens** | `CORNER_RADIUS_PX=8` (universally used for rounded corners) |
| **Shadow profiles** | Four `(blur_radius, vertical_offset, alpha_0_255)` tuples: `SHADOW_BUTTON_CHIP=(6,2,90)`, `SHADOW_BODY_EXPANDED=(24,5,130)`, `SHADOW_BODY_COLLAPSED=(14,4,175)`, `SHADOW_PANEL=(16,4,80)` |
| **Menu colors** | Legacy tray-menu styling (`MENU_BACKGROUND_COLOR`, etc.) |

### 5.3 `stickynotes/utils.py` — Helpers

Three responsibilities:

- `create_tray_icon()` — programmatically draws the tray icon as a `QPixmap` (no PNG embed needed for the tray specifically; the snap-store-listing icon at `snap/gui/stickynotes.png` is separate).
- `get_theme(name) -> dict` — looks up the theme dict from `config.THEMES`, falling back to `DEFAULT_THEME` if unknown.
- `apply_theme_to_window(...)` — utility that applies theme colors to a window's stylesheet (used by some legacy paths).
- `create_bullet_list_icon(color, size)` — paints the bullet-list toggle icon at runtime in the requested color (so it matches the current theme's text color).

### 5.4 `stickynotes/widgets.py` — `FloatingButton`

A reusable `QPushButton` subclass that renders as a **translucent rounded pill** with theme-aware glass styling. The note's `+` and `•••` buttons and all five format-bar buttons are `FloatingButton` instances.

Two tones:

- `Tone.TITLE_BAR` — fixed 28×28 px chip with a soft drop shadow. The shadow is intentional — it makes the button read as a tactile floating chip on top of the title-bar color band.
- `Tone.TOOLBAR` — variable size (the format bar scales buttons with note width). No drop shadow because adjacent buttons would pile shadows visually.

Glass palette tokens are RGBA values defined as class attributes:

```python
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
```

The light tokens are used for all themes except `charcoal`; charcoal flips to the dark tokens so buttons remain visible on the dark background.

`apply_theme(text_color, is_dark_theme)` rebuilds the stylesheet with the current geometry and palette. Border-radius scales with button size (`max(6, min(12, height * 0.27))`) so toolbar buttons stay readable at both 24 px (narrow note) and 44 px (wide note).

`FocusPolicy.NoFocus` is set on all `FloatingButton` instances. Without it, clicking a format-bar button would steal focus from the `QTextEdit`, breaking subsequent `Ctrl+B`/`I`/`U` shortcuts.

### 5.5 `stickynotes/note_window.py` — The big module

#### Classes, in their order of declaration:

##### `NoteTextEdit(QTextEdit)`
The note body. A standard `QTextEdit` with rich text enabled (`setAcceptRichText(True)`) and:
- `setFrameShape(NoFrame)` — no inner border (the note window itself provides the frame).
- `setHorizontalScrollBarPolicy(ScrollBarAlwaysOff)` — sticky notes don't scroll horizontally.
- `setVerticalScrollBarPolicy(ScrollBarAsNeeded)` — vertical scroll appears only if content overflows.
- `document().setIndentWidth(LIST_INDENT_PX)` — tighter list indentation than Qt's 40 px default (notes are narrow, so 18 px is enough visual hierarchy).

The text-edit also handles keyboard shortcuts for bullet-list nesting (`Tab` / `Shift+Tab` / `Shift+Enter`); see [§8](#8-keyboard-formatting-and-list-semantics).

##### `_DeleteButton(QPushButton)`
Destructive-action button with a **two-click confirm pattern**:
- Idle state: pale-red translucent background, "🗑 Delete Note" label.
- First click: arms the button. Label becomes "✓ Click again to confirm", background becomes a solid loud red.
- Second click within `DELETE_CONFIRM_WINDOW_MS` (4 s): emits `confirmed` signal.
- Timer expires or panel closes: disarms back to idle.

The opaque hex colors (`#fceaec`, `#f9dadc`, `#f5c6c8`, etc.) are pre-composited equivalents of the original `rgba(220, 50, 60, α)` translucent values against the `OptionsPanel`'s white background. The switch from `rgba` to opaque was necessary because under Wayland-via-XWayland, the `OptionsPanel`'s `WA_TranslucentBackground` doesn't reliably paint the white panel BG under child widgets — translucent children would let the note's text bleed through. See [§7](#7-ui-design-system) for the full story.

##### `OptionsPanel(QWidget)`
The popup that opens when `•••` is clicked. Frameless popup window (`Qt.WindowType.Popup | FramelessWindowHint`) with `WA_TranslucentBackground` so the rounded-corner cutouts are genuinely transparent. Three rows:
1. 7 color swatches (one per theme) as 28×28 px circular buttons. The current theme has a check-mark.
2. A 1-px separator (opaque `#e6e6e6`).
3. The two-click `_DeleteButton`.

The panel parents itself to the originating note (`parent=self`) so xdg_popup has an anchor surface to position against on native Wayland. Without that parent, the popup either falls back to a parentless toplevel (uncontrolled position) or lands at the compositor default.

`dismissed(object)` signal fires on every dismissal path so the owning `StickyNote` can clear its reference (the panel uses `deleteLater()` to free itself).

##### `EditableTitleLabel(QWidget)`
A click-to-edit pill that swaps between a read-only `QLabel` and a `QLineEdit` via `QStackedLayout`. Lives in the center of the title bar. Behavior:
- Single click → enter edit mode (`QLineEdit` focused, all text selected).
- `Enter` or focus loss → commit via `committed(str)` signal.
- `Escape` → cancel without emitting.
- `set_editable(False)` commits any in-progress edit and disables click + hover affordance — used when the note is collapsed (collapsed pills have no clickable title).

`MAX_TITLE_LENGTH = 40` is enforced both by the `QLineEdit`'s max-length and a defensive truncate in the tray-menu population logic (with `…` ellipsis).

##### `DragHandle(QWidget)`
The empty space between the title pill and the right-side `•••` button. Two roles:
- Single click + drag → calls `windowHandle().startSystemMove()` (delegates window-move to the WM, which is the Wayland-friendly path).
- Double click → toggles collapse via the `doubleClicked` signal.

The handle is intentionally a separate widget (not just dead space in the title bar) so we can install event filters and reliably distinguish drag-start from button-click.

##### `TitleBar(QWidget)`
Owns the title-bar layout: `[+] [pill] [drag area] [•••]`. Emits three signals upward to `StickyNote`:
- `newNoteRequested` — `+` clicked.
- `optionsRequested` — `•••` clicked.
- `titleCommitted(str)` — title edit committed.

`apply_colors(...)` propagates theme colors to all children. The drop-shadow chip styling for `+`/`•••` is configured here via `FloatingButton.Tone.TITLE_BAR`.

##### `FormatBar(QWidget)`
Bottom bar with five `FloatingButton`s in `Tone.TOOLBAR`: **B**, **I**, **U**, **S**, **•** (bullet list). All checkable so they reflect the cursor's current formatting state. Buttons scale with note width via `apply_size(btn_size)` — clamped between 24 and 44 px. Font size and bullet icon also rescale.

The bar surface uses the theme's `title` color (same as the title bar) for visual cohesion. The bullet button uses a runtime-painted icon (recolored per theme via `utils.create_bullet_list_icon`).

##### `StickyNote(QWidget)`
The main note window. Frameless toplevel (`Qt.WindowType.Window | FramelessWindowHint`) with `WA_TranslucentBackground` so the rounded corners and drop shadow can extend past the bg widget. Composition:

```
StickyNote (frameless toplevel, transparent)
  └ outer QVBoxLayout (margin = SHADOW_GUTTER on all sides)
      └ bg_widget (rounded-corner painted body)
          └ bg_layout (vertical, zero margin)
              ├ TitleBar
              ├ NoteTextEdit (expands)
              └ FormatBar
```

The outer margin gives the drop-shadow room to render without being clipped by the window edge.

Constructor parameters:

```python
StickyNote(
    note_id: str | None,        # UUID; generated if None
    content: str,                # HTML or plain text (auto-detected by leading '<')
    geometry_data: tuple | QByteArray | bytes | str | None,
    theme: str,                  # one of THEMES keys
    collapsed: bool,
    title: str | None,
    last_edited: str | None,     # ISO-8601 UTC string
)
```

The `geometry_data` parameter supports two encodings:
- **`QByteArray`** (preferred) — the output of `self.saveGeometry()`. This is the format Wayland compositors honor at window mapping, and the format produced by current saves.
- **`(x, y, w, h)` tuple** — legacy format from an early version that stored raw coordinates. Kept for migration of notes saved during that window.

Content detection (`content.strip().startswith("<")` → `setHtml`, else `setPlainText`) is straightforward; the welcome note ([§10](#10-autostart)) is constructed with explicit HTML so the format-toggle logic works correctly on it (a `setPlainText` regression was observed and fixed in v3.2.1).

##### `AboutDialog(QDialog)` and `SettingsDialog(QDialog)`
Two simple modeless dialogs:

- **About**: app icon (48×48 px), name, version (pulled from `stickynotes.__version__`), tagline, copyright + license, three link buttons (Source / Snap Store / Report a bug, via `QDesktopServices.openUrl`), and a mailto footer.
- **Settings**: single checkbox — "Launch on system startup" — that calls `autostart.set_enabled(checked)`. The toggle is initialized from `autostart.is_enabled()` (a filesystem check) so it always reflects the actual on-disk state.

Both use the reuse-once instance pattern in `TrayManager` (`_about_dialog`, `_settings_dialog`) so repeated tray clicks refocus the existing dialog rather than stacking new windows.

### 5.6 `stickynotes/tray_manager.py` — `TrayManager`

The application's lifecycle owner. Responsibilities:

1. **Tray icon + menu** — `QSystemTrayIcon` plus a dynamic `QMenu` that is rebuilt every time it's about to show (`aboutToShow` signal). The menu has: New Note, Show All Notes, Show Note ▶ submenu, separator, Settings, About Sticky Notes…, separator, Quit.

2. **Note dictionary** — `self.open_notes: dict[str, StickyNote]` keyed by note ID. Notes signal `noteDeleted(id)` on user-confirmed delete; the manager removes the QSettings group and pops from the dict.

3. **Note loading on startup** — `_load_notes()` iterates `QSettings.beginGroup("notes")` and reconstructs each saved note via `_create_new_note(...)`, passing all stored fields.

4. **First-launch / autostart-silent / welcome-note logic** — see [§10](#10-autostart) for the full decision tree.

5. **Autostart self-heal** — on every launch, if `autostart.is_enabled()`, call `autostart.set_enabled(True)` to rewrite the desktop file with the current code's `Exec=` format. This migrates users upgrading from older versions whose `.desktop` file was written before `--autostart` was added.

6. **Deferred position reapply (Wayland safety net)** — in `_create_new_note`, when running on autostart-on-Wayland and the note has stored geometry, `QTimer.singleShot(2000, note._reapply_initial_position)` is scheduled. This works around Mutter's tendency to override client-requested positions on initial window map. The newer `xwm.mark_position_user_requested()` is the primary fix; the 2-second reapply remains as a safety net.

7. **Tray menu submenu population** — `_populate_show_note_submenu(submenu)`:
   - Empty state: a disabled `(no saved notes)` entry.
   - Otherwise: up to `TRAY_MENU_NOTE_LIMIT` (default 10) notes, sorted by `last_edited` descending. Titles longer than `MAX_TITLE_LENGTH` are elided defensively. Hidden overflow shows as a disabled `+N more…` entry.

8. **Module-level `_AUTOSTART_ON_WAYLAND` flag** — computed once at import:
   ```python
   _AUTOSTART_ON_WAYLAND = (
       "--autostart" in sys.argv
       and os.environ.get("XDG_SESSION_TYPE") == "wayland"
   )
   ```
   Used to scope the deferred-reapply path so manual launches and X11 sessions skip the safety net entirely.

### 5.7 `stickynotes/autostart.py` — XDG autostart helper

A small module that encapsulates writing/removing `~/.config/autostart/stickynotes.desktop`. Two public functions:

- `is_enabled() -> bool` — returns `_desktop_path().is_file()`. No caching — every call hits the filesystem so the in-app toggle state always matches reality.
- `set_enabled(enabled: bool)` — writes or removes the desktop file. Raises `OSError` on I/O failure (handled in `SettingsDialog._on_autostart_toggled`).

Private helpers handle:

- `is_snap_runtime()` — `os.environ.get("SNAP_NAME") == "stickynotes-dabobroto"`. We match the specific snap name, not just any non-empty `SNAP_NAME`, because nested snaps (e.g., running our app from inside VS Code's snap) can leak the parent's env vars.
- `_exec_argv()` — builds the argv list for the desktop file's `Exec=` line. Under snap: `["/snap/bin/stickynotes-dabobroto.stickynotes", "--autostart"]`. Under source: `[sys.executable, run_stickynotes.py_path, "--autostart"]`. The `--autostart` flag is the signal that `TrayManager` uses to detect autostart launches.
- `_exec_line()` — formats the argv into a desktop-entry `Exec=` value. Under snap returns a space-joined plain string (snapd's autostart code parses Exec args and appends them to `<snap>.<app>`, ignoring the binary path). Outside snap, wraps the argv in a self-cleaning `/bin/sh -c '...'` form that auto-removes the autostart entry if the launcher binary disappears — useful for source builds where the user might delete the source folder.
- `_autostart_dir()` — returns `Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "autostart"`. Under snap confinement this redirects to `$SNAP_USER_DATA/.config/autostart` — exactly where snapd's session agent looks for autostart entries that match the snap's `autostart:` attribute.

### 5.8 `stickynotes/xwm.py` — X11 window-manager hints

A 50-line module exposing one function:

```python
mark_position_user_requested(widget) -> bool
```

Sets the `USPosition` + `USSize` flags (bits 0 and 1) on the widget's `WM_NORMAL_HINTS` X11 property via python-xlib. This is the **ICCCM-blessed signal** that tells the window manager "this position was explicitly user-requested, do not override it with your placement strategy." Mutter (and every other compliant X11 WM) honors it for both native X11 and XWayland surfaces.

Best-effort — silently returns `False` if python-xlib isn't importable, the widget has no X11 winId (native Wayland session), or anything throws. Never crashes the app over a hint.

Called from `StickyNote.__init__` after geometry application but before `show()` so the hint is in place when the WM first maps the window. See [§9](#9-display-server-compatibility-x11--wayland--xwayland) for why this matters.

---

## 6. Data model and persistence

### Storage backend

All persistent state lives in **QSettings** at:

- **Source build**: `~/.config/dstushar7/StickyNotesApp.conf` (Qt's default INI format on Linux).
- **Snap build**: `~/snap/stickynotes-dabobroto/current/.config/dstushar7/StickyNotesApp.conf` (XDG paths are redirected to `$SNAP_USER_DATA` under confinement).

No SQLite, no JSON file we manage ourselves, no cloud sync. QSettings handles atomic write, fsync, and concurrent-access safety on its own.

### Note schema

Each note is stored as a subgroup of `notes/`:

```ini
[notes]
<note-uuid>/content="<p>The HTML body of the note...</p>"
<note-uuid>/geometry=@ByteArray(\x01\xd9...)    # output of saveGeometry()
<note-uuid>/theme=yellow
<note-uuid>/collapsed=false
<note-uuid>/title=Groceries
<note-uuid>/last_edited=2026-05-23T01:17:42+00:00
```

The note ID is a UUID4 generated at note creation and never changes — it's the stable identity used by tray menus, the `noteDeleted` signal, and the open_notes dict.

### Top-level keys

```ini
first_launch_completed=true
```

A single boolean that distinguishes a true first install (no key set) from any subsequent launch. Used by the welcome-note + default-on-autostart logic in `TrayManager.__init__`. See [§10](#10-autostart).

### Save and load semantics

**Save path** (`StickyNote._save`):

```python
def _save(self):
    if self._is_being_deleted:
        return
    settings = QSettings(config.ORG_NAME, config.APP_NAME)
    settings.beginGroup("notes")
    settings.setValue(f"{self.note_id}/content",     self.text_edit.toHtml())
    settings.setValue(f"{self.note_id}/geometry",    self.saveGeometry())
    settings.setValue(f"{self.note_id}/theme",       self._theme_name)
    settings.setValue(f"{self.note_id}/collapsed",   self._is_collapsed)
    settings.setValue(f"{self.note_id}/title",       self._title)
    settings.setValue(f"{self.note_id}/last_edited", self._last_edited)
    settings.endGroup()
```

Three triggers fire `_save()`:

1. **Debounced** — `self._save_debounce` is a `SAVE_DEBOUNCE_MS` (500 ms) single-shot QTimer that's reset every time the user moves or resizes the note. The save fires 500 ms after the *last* drag/resize, so a continuous drag produces exactly one save at the end.
2. **Periodic autosave** — every `AUTOSAVE_INTERVAL_MS` (5 s), the note content is saved unconditionally. Catches edits that don't trigger the debounce (typing).
3. **Quit** — `QApplication.aboutToQuit` is connected to `TrayManager._save_all_notes`, which iterates and calls `_save()` on every open note. This fires on graceful Quit, session logout, and OS shutdown.

**Load path** (`TrayManager._load_notes`):

```python
settings = QSettings(config.ORG_NAME, config.APP_NAME)
settings.beginGroup("notes")
for note_id in settings.childGroups():
    content   = settings.value(f"{note_id}/content", "")
    theme     = settings.value(f"{note_id}/theme", config.DEFAULT_THEME)
    collapsed = settings.value(f"{note_id}/collapsed", False, type=bool)
    title     = settings.value(f"{note_id}/title", None)
    last_edited = settings.value(f"{note_id}/last_edited", None)
    geometry  = settings.value(f"{note_id}/geometry")
    if geometry is None:
        # Fall back to (x, y, w, h) ints — legacy format
        x = settings.value(f"{note_id}/x")
        ...
    self._create_new_note(note_id, content, geometry, theme, collapsed, title, last_edited)
```

### Title semantics

The title field has a subtle two-mode behavior:

- **Smart default**: if the title is empty/null, derive it from the first body line, truncated to `AUTO_SEED_WORD_COUNT` (2) words. This is what gives new notes a useful title without the user typing anything explicit.
- **User-committed**: once the user clicks the title pill and presses Enter, the title is locked. Body changes no longer auto-update the title; the user has named the note.

The lock is implicit — once `_title_is_default` becomes False (after first user commit), title-from-body derivation stops.

### Last-edited timestamp

ISO-8601 UTC string set on every content change (debounced). Used solely by the tray menu's "Show Note ▶" submenu to sort entries newest-first. Not visible in the UI elsewhere.

---

## 7. UI design system

### The "glass" aesthetic

The visual identity rests on three primitives:

1. **Frameless rounded windows** with soft drop shadows.
2. **Glass-pill buttons** — translucent rounded rectangles that fade with state.
3. **Themed color bands** — title bar and format bar share a slightly-darker shade than the note body.

### Themes

Seven themes, six light + one dark:

| Name | Body bg | Title bg | Text |
|---|---|---|---|
| Yellow *(default)* | `#FFF176` | `#F9E44A` | `#1a1a1a` |
| Green | `#B5EBBF` | `#8FD9A0` | `#1a1a1a` |
| Pink | `#F9B8C6` | `#F48FAA` | `#1a1a1a` |
| Purple | `#D8B8F9` | `#BC8FF5` | `#1a1a1a` |
| Blue | `#B3E5FC` | `#80D0F5` | `#1a1a1a` |
| Gray | `#E0E0E0` | `#BDBDBD` | `#1a1a1a` |
| Charcoal | `#4A4A4A` | `#333333` | `#f0f0f0` |

The pattern is `body` lighter than `title` so the title bar reads as a distinct band. Charcoal flips the text color to light because the bg is dark.

`StickyNote._apply_theme(theme)` propagates these values to: the `bg_widget` stylesheet (rounded body), the `TitleBar` (title-bg color + button tint), the `FormatBar` (same title-bg + button tint), and the `NoteTextEdit` (text color, transparent bg so the body color shows through).

### Drop shadows

Implemented via `QGraphicsDropShadowEffect` with profiles defined in `config.py`:

```python
SHADOW_BUTTON_CHIP    = (blur=6,  offset_y=2, alpha=90)
SHADOW_BODY_EXPANDED  = (blur=24, offset_y=5, alpha=130)
SHADOW_BODY_COLLAPSED = (blur=14, offset_y=4, alpha=175)
SHADOW_PANEL          = (blur=16, offset_y=4, alpha=80)
```

Two shadow profiles for the note body (expanded vs collapsed) because the floating-pill shape needs a tighter, denser shadow to retain its tactile quality without the body's larger silhouette providing visual mass.

### Collapse-to-pill animation

Triggered by double-clicking the title bar's drag area. Uses `QParallelAnimationGroup` to animate window size + content opacity over `COLLAPSE_ANIMATION_MS` (150 ms). The text edit + format bar fade and shrink in lockstep; the title bar (with its `+`, title pill, drag area, `•••`) remains visible. The shadow profile swaps from `SHADOW_BODY_EXPANDED` to `SHADOW_BODY_COLLAPSED` on collapse and back on expand.

### Title pill

A child `EditableTitleLabel` widget sized to its content (`QSizePolicy.Maximum, Fixed`). The pill never grows beyond its text — long titles are elided in the menu, not in the pill. Hover affordance: subtle background overlay (`hover_overlay` color computed from theme).

### Options panel

Frameless popup (`Qt.WindowType.Popup | FramelessWindowHint`) with `WA_TranslucentBackground`. Painted as a rounded white rectangle (`QWidget#optionsPanel { background: #ffffff; border-radius: 8px; }`) with a soft drop shadow. The translucent-window trick is what enables the four rounded-corner cutouts (areas outside the border-radius) to be genuinely transparent rather than rendered as opaque widget background.

**Why translucent children inside the panel had to be made opaque** (v3.2.5 / 3.2.6 era): On Wayland-via-XWayland under Mutter, the combination of `WA_TranslucentBackground` + stylesheet-painted background was observed to *not reliably* paint the white panel BG under child widgets. The `_DeleteButton`'s original `rgba(220, 50, 60, 0.10)` background let the underlying note's text bleed through, producing "Delete Note" text overlaid on the note's content — visually broken. Fix: replace every translucent child color with its pre-composited opaque equivalent against `#ffffff`. Same visual result on a healthy compositor, no bleed-through on the broken-rendering path.

### Tray icon

Drawn programmatically at runtime via `utils.create_tray_icon()` (not loaded from a PNG). Gives crisp rendering at any DPI and keeps the snap a few KB smaller.

---

## 8. Keyboard, formatting, and list semantics

### Format shortcuts (all `Ctrl`-prefixed for muscle-memory parity with most editors)

| Shortcut | Action |
|---|---|
| `Ctrl+B` | Bold |
| `Ctrl+I` | Italic |
| `Ctrl+U` | Underline |
| `Ctrl+Shift+S` | Strikethrough |
| `Ctrl+Shift+L` | Toggle bullet list (enter/leave) |
| `Tab` (in list) | Indent to sublist; cycles bullet style |
| `Shift+Tab` (in list) | Outdent |
| `Enter` (in list) | Continue list item |
| `Shift+Enter` (in list) | Break out of list |
| `Ctrl+Z` / `Ctrl+Y` | Undo / Redo (native QTextEdit) |
| `Ctrl+A` | Select all |

### Bullet style cycling

Sublists cycle visual style across three levels:

```
Level 1: ● (disc)
Level 2: ○ (circle)
Level 3: ■ (square)
```

Implemented in `NoteTextEdit.keyPressEvent`'s `Tab` handler by inspecting the current `QTextList`'s style and creating a new `QTextListFormat` with the next style up the chain.

### Format-bar checked state

`StickyNote._refresh_format_bar` is wired to `text_edit.cursorPositionChanged` and `text_edit.currentCharFormatChanged`. When the cursor lands in already-formatted text, the corresponding format-bar button is `setChecked(True)` so the user sees the current state at a glance.

### Title editing

Click the title pill → enters edit mode (line edit replaces the label via `QStackedLayout`). `Enter` commits; `Escape` cancels. The commit emits `titleCommitted(str)`. Inside `StickyNote._on_title_committed`:

1. Strip whitespace and clamp to `MAX_TITLE_LENGTH`.
2. If non-empty, set `_title` and mark `_title_is_default = False` (locks title from body derivation).
3. Re-render the pill.

If the user commits an empty string, the title falls back to the smart-default (body-derived) behavior — useful escape hatch to "reset" a title.

### Two-click delete

Implemented in `_DeleteButton`. First click arms (visual flash to loud red, label change). Within `DELETE_CONFIRM_WINDOW_MS` (4 s), a second click confirms. Outside the window, a 4-second `QTimer` disarms. Closing the panel also disarms. The pattern is a deliberate friction layer for a destructive action that has no undo.

---

## 9. Display-server compatibility (X11 / Wayland / XWayland)

This section captures the most non-obvious engineering work in the codebase. It exists because **Wayland's protocol forbids client applications from setting absolute window positions**, by design.

### The problem

A sticky-notes app needs to restore each note's position across sessions. On X11 this is trivial: `widget.move(x, y)` works, full stop. On Wayland it does not work: the protocol has no equivalent of `XMoveWindow`, and Mutter (the GNOME compositor) deliberately ignores client-requested positions for toplevel windows. This is not a missing-feature — it is a deliberate architectural choice by Wayland's designers and is unlikely to change.

### The strategy

**Force xcb (X11) everywhere**, including on Wayland sessions where xcb runs through XWayland. Both display servers then route through the same X11 client code path, where absolute positioning works as expected.

```python
# run_stickynotes.py
os.environ["QT_QPA_PLATFORM"] = "xcb;wayland"
```

The `xcb;wayland` value is a Qt platform-plugin fallback chain: try xcb first; if it can't load (e.g., a pure-Wayland system without XWayland), fall back to the wayland plugin. The fallback exists so the app at least *starts* on those rare setups; absolute positioning won't work there, but the app remains usable.

**Why assignment, not `setdefault`**: The snap GNOME extension's launcher pre-sets `QT_QPA_PLATFORM=wayland` based on `XDG_SESSION_TYPE`. `setdefault` would see the variable already set and do nothing. We need to overwrite.

**Why before any PyQt6 import**: Qt reads this env var during `QGuiApplication` initialization. Setting it after `from PyQt6.QtWidgets import QApplication` would be too late (the import chain triggers QGuiApplication).

### The XWayland startup race

On GNOME Wayland with snap autostart, a race exists:

1. `snapd.session-agent` fires the autostart entry during session start.
2. Our process boots and runs the env-var setup.
3. Qt initializes and tries to load the xcb plugin.
4. **xcb needs the XWayland socket** (`/tmp/.X11-unix/X0`) to exist.
5. **XWayland starts lazily on GNOME**, often only after the first X11 client requests it.

If steps 3 happens before XWayland is fully up, Qt's xcb plugin either fails to load (falls back to wayland → no absolute positioning) or initializes against a half-ready X server (positioning calls fail silently).

**Mitigation**: `_wait_for_xwayland_on_autostart()` in `run_stickynotes.py` polls for `/tmp/.X11-unix/X0` for up to 5 minutes (heartbeat log every 5 s), but bails out immediately when the socket appears (with a 0.5-second grace pause for XWayland to finish accepting connections). Scoped to autostart-on-Wayland only — manual launches and X11 sessions skip the poll entirely.

In practice, the socket exists in 0 seconds on most setups (XWayland is up already), so the poll is a no-op safety net.

### Mutter's initial-window-placement override

A *second* Wayland-specific bug exists: even when xcb loads cleanly and `widget.move(x, y)` is called with correct coordinates, Mutter **overrides client-requested positions during the initial window map** for autostart launches. The override happens at window-map time, not based on session phase or timing.

We observed three failed mitigations:

1. **Deferred reapply** (3.2.5): show the window at default → 2 s later, call `move()` again → Mutter honors it because it's a *subsequent* move, not initial map. Works, but produces a visible "notes jump to correct positions" animation that's bad UX.
2. **Deferred show** (3.2.6, reverted): hold `show()` for 2 s so it happens past the session-startup phase → didn't work, because Mutter's override is tied to *initial map*, not session time.
3. **QSettings sync()** (3.2.7, reverted): force-flush saves to disk on every save → orthogonal to the bug; positions were already saving correctly.

The **actual fix** (v3.2.6) is the `USPosition` X11 hint, implemented in `stickynotes/xwm.py`:

```python
# Set USPosition | USSize on WM_NORMAL_HINTS
hints = xwin.get_wm_normal_hints()
hints.flags |= X.USPosition | X.USSize
xwin.set_wm_normal_hints(hints)
```

The ICCCM (Inter-Client Communication Conventions Manual) defines `USPosition` (bit 0 of `WM_NORMAL_HINTS.flags`) as "user-specified position." Mutter — like every other compliant X11 WM — honors `USPosition` over its own placement strategy. Qt's `move()` / `setGeometry()` does not set this hint by default (the default is `PPosition` = program-specified position, which the WM treats as a *suggestion*).

The hint is applied in `StickyNote.__init__` after geometry application but **before** `show()`, so it's in place when the WM first maps the window. Only set when `geometry_data is not None` (new notes have no saved position to user-tag).

The deferred-reapply safety net from 3.2.5 is **still in place** — if `USPosition` somehow fails to take effect on a given setup (Mutter version quirk, unusual compositor, etc.), the 2-second reapply still catches it. Either the first map is correct (USPosition worked) or the safety net corrects it within 2 s (USPosition didn't, but the bug was at least mitigated). Defense in depth.

### Diagnostic logging on autostart

`run_stickynotes.py` prints the actual loaded Qt platform name when `--autostart` is in argv:

```
[stickynotes] Qt platform: xcb
[stickynotes] XWayland ready after 0.0s
```

Visible via `journalctl --user | grep stickynotes`. Used during debugging — if the line ever prints `wayland` instead of `xcb`, we know xcb failed to initialize.

---

## 10. Autostart

### Why this is non-trivial

The app needs to launch automatically at login because that's the natural workflow for a sticky-notes app (you don't want to manually launch your notes every morning). Implementing this across both source builds and snap builds, across X11 and Wayland sessions, with sensible defaults for new users, was a significant chunk of the project's history.

### Mechanism

Two distinct paths, depending on how the app was installed:

#### Source build (`pip install`, run from `run_stickynotes.py`)

Standard **XDG autostart** specification. We write a `.desktop` file to `~/.config/autostart/stickynotes.desktop`. The desktop session reads this directory at login and launches every entry. Implemented in `stickynotes/autostart.py`.

The `Exec=` line uses a **self-cleaning wrapper**:

```
Exec=/bin/sh -c "if [ -x '/path/to/python3' ]; then exec '/path/to/python3' '/path/to/run_stickynotes.py' '--autostart'; else rm -f '/home/user/.config/autostart/stickynotes.desktop'; fi"
```

If the user deletes the source folder or the venv's Python disappears, the autostart entry auto-removes itself at next login attempt instead of failing every session. Defensive against orphaned entries from old installs.

#### Snap build

The snap's `snapcraft.yaml` declares an `autostart:` app attribute:

```yaml
apps:
  stickynotes:
    command: bin/python3 $SNAP/run_stickynotes.py
    extensions: [gnome]
    desktop: gui/stickynotes.desktop
    autostart: stickynotes.desktop
    plugs: [home]
    environment:
      QT_QPA_PLATFORM: xcb;wayland
```

snapd's autostart documentation specifies: applications place a `.desktop` file under `$SNAP_USER_DATA/.config/autostart/<filename>` matching the `autostart:` attribute's value. snapd's session agent watches that directory and launches the app on session start via the app's command wrapper (`<snap-name>.<app-name>`).

Under snap confinement, `XDG_CONFIG_HOME` is redirected to `$SNAP_USER_DATA/.config`. The same `autostart.py` code that writes `~/.config/autostart/stickynotes.desktop` on source builds ends up writing to `$SNAP_USER_DATA/.config/autostart/stickynotes.desktop` under snap — which is exactly where snapd's session agent looks. No code branching needed.

Under snap, the `Exec=` line is simpler — just the snap command + `--autostart`:

```
Exec=/snap/bin/stickynotes-dabobroto.stickynotes --autostart
```

snapd's autostart code parses the args from `Exec=`, discards the binary path, and runs `<snap>.<app> <args>`. So `--autostart` reaches `sys.argv` as expected.

### The `--autostart` flag in detail

A command-line argument we add to the autostart `.desktop` file's `Exec=` line. Its purpose is purely **internal signalling**: it lets the launched process know "I was started by autostart, not by user click." Used in two places:

1. **`TrayManager.__init__`** — to decide whether to show a welcome note / blank starter / silent tray on empty state.
2. **`run_stickynotes.py`** — to decide whether to run the XWayland-readiness wait.
3. **`tray_manager.py:_AUTOSTART_ON_WAYLAND`** — module-level flag derived from `"--autostart" in sys.argv and XDG_SESSION_TYPE == "wayland"`.

Manual launches (from app menu, terminal, tray "New Note") don't have this flag → all autostart-specific logic skips.

### First-launch flag and welcome note

`TrayManager.__init__` runs this decision tree when `_load_notes()` returns no notes:

```python
if not self.open_notes:
    settings = QSettings(config.ORG_NAME, config.APP_NAME)
    is_first_ever = not settings.value("first_launch_completed", False, type=bool)
    is_autostart  = "--autostart" in sys.argv

    if is_first_ever:
        self._create_welcome_note()
        # Default autostart ON for new installs (better UX).
        try:
            autostart.set_enabled(True)
        except OSError:
            pass
    elif not is_autostart:
        self._create_new_note()
    # else: autostart with no saved notes → silent tray (no popup).

    settings.setValue("first_launch_completed", True)
```

Four scenarios, four behaviors:

| Scenario | `is_first_ever` | `is_autostart` | Result |
|---|---|---|---|
| Brand-new install, manual first launch | `True` | `False` | Welcome note (centered, 460×380, HTML body with onboarding tips) + autostart auto-enabled |
| Manual launch, no saved notes | `False` | `False` | Blank starter note (user opened the app for a reason) |
| Autostart launch with saved notes | `False` | `True` | Saved notes restored, no extra note |
| Autostart launch, no saved notes | `False` | `True` | **Silent tray** — no popup |

The fourth scenario is the entire reason the `--autostart` flag exists. Without it, every login on an empty state would flash up an unwanted blank note — the exact "gets in your way" behavior the app is positioned against.

### Welcome note content

```python
body = (
    "<p>A few quick tips:</p>"
    "<ul>"
    "<li>Double-click the title bar to collapse to a pill</li>"
    "<li>Ctrl+B, Ctrl+I, Ctrl+U for bold, italic, underline</li>"
    "<li>Click the + button to add another note</li>"
    "<li>Click ••• to switch themes or delete</li>"
    "</ul>"
    "<p>Click the title to rename. Edit or delete this note whenever.</p>"
)
```

**HTML, not plain text.** A v3.2.0 regression had this as plain text, which loaded via `setPlainText` and put the document into an unspecified char-format state where `Ctrl+B`/`I`/`U` toggles would apply but couldn't reverse. HTML loads via `setHtml` (the same path restored notes use), giving every character an explicit char format so toggles work bidirectionally from the first press.

Centered on the primary screen at 460×380 px so the tips fit without scrolling (the default new-note size clips them).

### Autostart self-heal

Every launch, `TrayManager.__init__` runs:

```python
if autostart.is_enabled():
    try:
        autostart.set_enabled(True)
    except OSError:
        pass
```

If the user previously enabled autostart on an older version that wrote a different `Exec=` format (e.g., before `--autostart` was added), the existing `.desktop` file in `$SNAP_USER_DATA` survives snap upgrades unchanged. The self-heal rewrites it with the current code's format on first launch, migrating users transparently. Idempotent for users whose file is already correct.

### Settings toggle

The Settings dialog has one checkbox: "Launch on system startup". Reads `autostart.is_enabled()` at construction (filesystem check); toggling calls `autostart.set_enabled(checked)`. The toggle always reflects the actual on-disk state.

Defaults to **on for new installs** (auto-enabled in the first-launch branch above) — better UX than requiring the user to discover Settings. Existing users keep their preference (the `is_first_ever` guard ensures the auto-enable never re-fires for users who have already been onboarded).

---

## 11. System tray integration

### Tray icon

Drawn at runtime in `utils.create_tray_icon()` using `QPixmap` + `QPainter`. Always crisp at any DPI; no PNG file shipped for the tray specifically (the snap-store icon at `snap/gui/stickynotes.png` is separate and serves a different purpose — Snap Store listing thumbnail + app-grid icon).

### Dynamic menu

Built fresh every time the menu is about to show (`menu.aboutToShow.connect(self._rebuild_menu)`). This is essential — the "Show Note ▶" submenu lists open notes by current title, sorted by last-edited descending. If the menu was built once at startup, edited titles wouldn't show up; recently-edited notes wouldn't bubble up to the top.

Menu layout:

```
┌─────────────────────────┐
│  New Note               │  ← create blank note in default theme
│  Show All Notes         │  ← bring every note to front
│  Show Note            ▶ │  ← submenu, see below
├─────────────────────────┤
│  Settings               │  ← open SettingsDialog
│  About Sticky Notes…    │  ← open AboutDialog
├─────────────────────────┤
│  Quit                   │
└─────────────────────────┘
```

### "Show Note ▶" submenu

`_populate_show_note_submenu(submenu)`:

- **No saved notes**: a single disabled entry: `(no saved notes)`.
- **One or more notes**: sorted by `last_edited` descending, capped at `TRAY_MENU_NOTE_LIMIT` (10). Each entry's label is the note title (or `DEFAULT_NOTE_TITLE = "New Note"` if blank), elided to `MAX_TITLE_LENGTH` (40) chars with a trailing `…`. Clicking an entry calls `_focus_note(note_id)` — shows, raises, and activates that specific note.
- **Overflow**: if more than 10 notes are saved, a disabled `+N more…` entry indicates the hidden count.

### Reuse-once dialogs

`SettingsDialog` and `AboutDialog` use the same pattern in `TrayManager`:

```python
def _show_settings(self):
    if self._settings_dialog is not None and self._settings_dialog.isVisible():
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()
        return
    dlg = SettingsDialog()
    dlg.finished.connect(lambda _r: setattr(self, "_settings_dialog", None))
    self._settings_dialog = dlg
    dlg.show()
```

Repeated clicks refocus the existing dialog instead of stacking new windows. `finished` is wired to clear the reference so a closed-and-reopened cycle works.

### `aboutToQuit` flush

`self.app.aboutToQuit.connect(self._save_all_notes)`. Critical because `QApplication.quit()` (used by the tray "Quit" menu entry) does not call `closeEvent` on individual windows — without this, any unsaved geometry would be lost.

---

## 12. Snap packaging

### Why Snap

- **Single-package, cross-distro**: one `.snap` file works on Ubuntu, Fedora, Manjaro, openSUSE, etc.
- **Auto-update**: Snap Store handles updates on the user's machine without our involvement.
- **Sandboxed**: strict confinement is acceptable for an app with this narrow scope (read/write `~`, no network, no system access).
- **Available out of the box on Ubuntu**: the dev's primary target.

### `core24` base

Built on Ubuntu 24.04 LTS (`base: core24`). The base provides Python 3.12. `core22` (Ubuntu 22.04) would also work but `core24` is the latest LTS at time of writing and supports newer PyQt6 versions cleanly.

### `extensions: [gnome]`

This single line pulls in the `gnome-46-2404` content snap as a runtime dependency. It provides:

- The GNOME platform (GTK4 + LibAdwaita, even though we use Qt — gives us system theming).
- Standard fonts.
- Mesa / OpenGL stack.
- The `desktop-launch` command-chain wrapper that handles desktop integration, env-var setup, and Wayland/X11 platform selection.

Without it, the snap would have to bundle ~200 MB of GNOME/GTK runtime. With it, the snap is **~26 MB installed**.

### Aggressive pruning strategy

`override-prime` in `snapcraft.yaml` runs after `craftctl default` and deletes everything we don't need from the bundled PyQt6 wheels and Qt6 shared libraries. Three pruning categories:

#### 1. Drop PyQt6 sub-modules we don't use

```bash
for mod in QtQuick QtQml QtOpenGL QtNetwork QtMultimedia QtMultimediaWidgets \
           QtBluetooth QtSql QtDesigner QtTest QtPdf QtPdfWidgets QtPrintSupport \
           QtPositioning QtSensors QtSerialPort QtWebChannel QtWebSockets \
           QtXml QtSvg QtSvgWidgets QtQuick3D QtQuickWidgets QtRemoteObjects \
           QtNfc QtDBus QtHelp QtCharts QtDataVisualization QtSpatialAudio \
           QtTextToSpeech Qt3DCore Qt3DRender Qt3DInput Qt3DLogic Qt3DAnimation \
           Qt3DExtras QtQuickControls2; do
  rm -f "$PYQT6/${mod}.abi3.so"
done
```

We use only `QtCore`, `QtGui`, `QtWidgets` (plus `QtSvgWidgets` indirectly via Qt's XcbQpa, which we keep separately). Everything else is gone.

#### 2. Drop unused Qt6 shared libraries

```bash
find "$QT6LIB" -maxdepth 1 -name 'libQt6*.so*' \
  ! -name 'libQt6Core.so*' \
  ! -name 'libQt6Gui.so*' \
  ! -name 'libQt6Widgets.so*' \
  ! -name 'libQt6DBus.so*' \
  ! -name 'libQt6XcbQpa.so*' \
  ! -name 'libQt6OpenGL.so*' \
  ! -name 'libQt6WaylandClient.so*' \
  ! -name 'libQt6WaylandEglClientHwIntegration.so*' \
  -delete
```

Six core Qt libraries kept. Two Wayland-specific ones kept — without them, the wayland/wayland-egl platform plugin fails to load, and the snap only starts on X11/XWayland sessions (a regression we hit during Wayland-compat work).

#### 3. Drop QML, translations, libavcodec, etc.

```bash
rm -rf "$PYQT6/Qt6/qml"
rm -rf "$PYQT6/Qt6/translations"
rm -rf "$PYQT6/Qt6/resources"
rm -f  "$QT6LIB"/libav*.so* "$QT6LIB"/libsw*.so*    # libavcodec / libswresample / etc. — ~15 MB
```

`libav*` and `libsw*` are FFmpeg-derived libraries for QtMultimedia. We dropped QtMultimedia, so these are dead weight (~15 MB saved).

#### 4. Plugin folder pruning

```bash
find "$QT6PLUG" -mindepth 1 -maxdepth 1 -type d \
  ! -name 'platforms' \
  ! -name 'platforminputcontexts' \
  ! -name 'platformthemes' \
  ! -name 'styles' \
  ! -name 'imageformats' \
  ! -name 'iconengines' \
  ! -name 'xcbglintegrations' \
  ! -name 'wayland-*' \
  -exec rm -rf {} +
```

Keep the platform plugins (xcb, wayland), input contexts (for IBus/Fcitx), platform themes (for GNOME/KDE integration), basic styles, image formats, icon engines, XCB GL integration, and Wayland-related plugins. Everything else (QML controls, multimedia plugins, etc.) is gone.

#### 5. Drop PyQt6 dev artifacts

```bash
rm -rf "$PYQT6/bindings"   # .pyi/.sip stub files
rm -rf "$PYQT6/uic"        # Qt Designer .ui compiler
```

Useful for development, useless at runtime.

#### 6. Strip pip/setuptools/wheel

```bash
rm -rf $CRAFT_PRIME/lib/python*/site-packages/pip*
rm -rf $CRAFT_PRIME/lib/python*/site-packages/setuptools*
rm -rf $CRAFT_PRIME/lib/python*/site-packages/wheel*
rm -rf $CRAFT_PRIME/lib/python*/site-packages/_distutils_hack
```

These ship with the python plugin's Python interpreter; we don't need any of them at runtime.

### `confinement: strict`

Strict confinement (the safest model). The app's manifested capabilities are minimal:

- `extensions: [gnome]` → implicit `home`, `desktop`, `desktop-legacy`, `wayland`, `x11`, `opengl`, `gsettings` plugs.
- Explicit `plugs: [home]` — redundant since gnome extension provides it, but kept for clarity.

We avoided adding `personal-files` for the autostart entry (which would require Snap Store manual review and an auto-connect approval flow) by writing autostart entries to `$SNAP_USER_DATA/.config/autostart/` — which is inside the snap's own data dir, accessible without any extra interface, and which snapd's session agent monitors per the `autostart:` snapcraft attribute.

### App identity in `snapcraft.yaml`

```yaml
name: stickynotes-dabobroto    # snap name (must be globally unique on Snap Store)
title: Sticky Notes            # display name in store listing
icon: snap/gui/stickynotes.png # store thumbnail + app-grid icon
license: MIT
contact: contact@dabobrotosarkar.com
website: https://dabobrotosarkar.com/
source-code: https://github.com/dstushar7/sticky-notes
issues: https://github.com/dstushar7/sticky-notes/issues
grade: stable
```

The snap name has a suffix (`-dabobroto`) because `stickynotes` was already taken on Snap Store. Trade-off accepted; the store listing display name is just "Sticky Notes."

---

## 13. Build and release pipeline

### GitHub Actions

CI configured in `.github/workflows/` runs on push to `main`:

1. `snapcore/action-build@v1` — builds the snap using snapcraft inside a managed LXD container (Ubuntu 24.04).
2. `snapcore/action-publish@v1` — uploads the resulting `.snap` to the Snap Store and releases to the `edge` channel.

Subsequent promotion to `candidate` / `stable` is done manually via the Snap Store dashboard (`snapcraft release stickynotes-dabobroto <revision> candidate`).

### Channel strategy

- **edge**: every successful build from `main`. Used for personal testing on the dev's machine.
- **candidate**: manually promoted from edge once smoke-tested.
- **stable**: manually promoted from candidate once known-good for at least a few days.

The user-facing default is `stable`. Edge users have explicitly opted in via `snap install --edge`.

### Versioning

Semantic versioning, tracked in two places that **must stay in sync**:

- `stickynotes/__init__.py`: `__version__ = "X.Y.Z"`
- `snap/snapcraft.yaml`: `version: 'X.Y.Z'`

The `AboutDialog` reads `stickynotes.__version__` so the in-app version is always honest about what's actually shipped.

Convention applied during development:

- **PATCH** (`x.y.Z`): bug fixes, dependency bumps, marketing-copy edits, internal refactors.
- **MINOR** (`x.Y.0`): new user-facing functionality (e.g., About dialog → 3.2.0, autostart → 3.1.0).
- **MAJOR** (`X.0.0`): breaking schema changes or major architectural shifts.

The version evolved over many small iterations during the project's development (~30 versions between 3.0.0 and 3.2.6) — visible-to-users behavior change cycle was rapid, especially for the autostart + Wayland-positioning saga.

### Local testing

```bash
# Smoke test on source
python3 -m venv stickyenv
source stickyenv/bin/activate
pip install -r requirements.txt
python3 run_stickynotes.py

# Build snap locally
snapcraft

# Install local snap without uploading
sudo snap install --dangerous stickynotes-dabobroto_X.Y.Z_amd64.snap

# Verify version on installed snap
snap list stickynotes-dabobroto
```

---

## 14. Marketing and store listing

### Voice

The Snap Store summary, description, in-app About text, and README intro all share a single voice we internally call "playfully savage." Examples:

- Summary: "The lightest, prettiest sticky notes app on Linux. No cloud, no nonsense."
- Description opening: "Sticky notes. That's it. That's the app."
- Description differentiator: "Oh, and the whole thing is about 26 MB installed — while the competition ships half an operating system just to show you a yellow square."
- Description "What it deliberately does NOT do" section: "Sync to a cloud you never asked for / Make you create an account to write the word 'milk' / Phone home, track you, or ship a single line of telemetry / Pretend to be a wiki, a knowledge base, or your second brain."

The voice is brand strategy: differentiating against the two competing patterns (old-feeling clones, feature-creeping "second brain" apps) by being **explicitly anti-bloat**. Each "deliberately does NOT do" bullet is a positioning signal against a specific competitor pattern.

### Description structure

In order:

1. **Hook** — two short paragraphs setting the anti-bloat tone.
2. **Footprint flex** — "about 26 MB installed."
3. **"Nice to look at"** — visual differentiators (frameless, 7 themes, glass buttons, collapse-to-pill).
4. **"Nice to use"** — functional features (rich text, shortcuts, smart titles, autostart, two-click delete).
5. **"What it deliberately does NOT do"** — explicit anti-features.
6. **"Where your notes live"** — privacy reassurance, no encryption-theater overclaiming.
7. **Sign-off** — "Free, tiny, and it does one thing properly."

### Screenshots

The Snap Store listing carousel uses ~5 screenshots:

1. **Hero / beauty flex** — 3 notes (yellow, blue, charcoal) fanned over a clean wallpaper, front note expanded showing formatted bullet list + glass toolbar.
2. **Theme wall** — all 7 themes tiled in a grid.
3. **Collapse-to-pill** — same note expanded and as the collapsed pill, side by side.
4. **In context** — a note with a real to-do list beside a code editor or browser.
5. **Tray menu** — system-tray menu open showing New Note / Show Note submenu.

Same wallpaper across the set for cohesion. Real-looking content, never lorem ipsum.

### Icon

`snap/gui/stickynotes.png` — the snap-store thumbnail + app-grid icon. PNG, ~137 KB. The runtime tray icon is drawn programmatically (different visual constraints; needs to render small + crisp at any DPI).

---

## 15. Known limitations and accepted trade-offs

| Limitation | Why we accept it | Mitigation in place |
|---|---|---|
| **No always-on-top** | Native Wayland protocol has no client-side "always on top" mechanism. Implementing for X11 only would create inconsistent behavior across display servers. | None — feature deliberately omitted. |
| **Autostart-on-Wayland position-restore relies on XWayland + USPosition** | Wayland forbids absolute positioning by design. We sidestep via XWayland (`QT_QPA_PLATFORM=xcb;wayland`). On rare setups without XWayland or with patched Mutter that ignores USPosition, positions may not restore. | XWayland-readiness poll, USPosition hint, deferred-reapply safety net at 2 s. |
| **Bullet styles cycle through only 3 levels** | Visual hierarchy beyond 3 levels gets unreadable in narrow notes. | Three is enough for actual sticky-note use. |
| **No search across notes** | Sticky-note quantity is typically <20 per user. Search would be visual clutter for a feature most users wouldn't use. | "Show Note ▶" submenu in tray (sorted by last-edited) acts as a lightweight finder. |
| **No tags / folders** | Same reason as search — premature organization for a low-quantity tool. | Title-as-identifier is sufficient. |
| **English only** | Internationalization would balloon the snap (Qt translation files + per-locale handling) and complicate maintenance for solo dev. | Voice is plain English, easy to skim even for non-native speakers. |
| **No cloud sync** | Brand position. Adding it would invalidate every "no cloud, no account" claim. | None. |
| **Linux only** | Brand position ("for Linux"). Cross-platform port would dilute focus. | None. |

### Mutter-specific behaviors we work around

| Behavior | Workaround |
|---|---|
| Wayland forbids absolute positioning | `QT_QPA_PLATFORM=xcb;wayland` + python-xlib USPosition hint |
| XWayland starts lazily on GNOME Wayland | `/tmp/.X11-unix/X0` poll on autostart |
| Mutter overrides client positions on initial window map | `USPosition` flag in `WM_NORMAL_HINTS` |
| Mutter's `WA_TranslucentBackground` + child stylesheet rendering quirk on XWayland | Opaque colors instead of `rgba()` for translucent-on-white child widgets |

### Save reliability under SIGKILL

Currently, `_save()` calls `QSettings.setValue(...)` without explicit `settings.sync()`. On graceful quit, Qt has time to flush its internal cache to disk. On OS-level shutdown with the app still running, the session manager's grace period (typically 2–5 s) may not be enough for Qt to flush before SIGKILL, theoretically losing the most-recent save.

We tested adding `settings.sync()` to force flush (v3.2.7) but reverted because empirically saves were already persisting reliably enough (probably because the 5-second autosave + 500 ms debounce + `aboutToQuit` handler catch most cases). The accepted trade-off: if the user moves a note <500 ms before shutdown, that specific position change may be lost. Acceptable for a sticky-notes app.

If this proves problematic in user reports, re-adding `settings.sync()` is a one-line change.

---

## 16. Future work

### Watching for, not yet actionable

- **`xdg-session-management-v1`** — merged into wayland-protocols 1.48 in March 2026. Designed for session-restore (window positions across logins). Qt 6 does not expose it yet; once it does, we can drop the XWayland-detour entirely on capable compositors.
- **`xdg-toplevel-tag-v1`** — merged into Mutter for GNOME 49. Lets clients tag windows with stable identifiers for compositor-side position restoration. Qt support pending.

### Potentially worthwhile

- **Markdown link rendering** — preserve plain URLs as clickable links. Would require a small `QTextDocument` post-process pass; no major architectural impact.
- **Pin / unpin notes** — designate certain notes as always-visible in the tray menu regardless of edit-time order. Minor UI change.
- **Note grouping** — light tags or colored badges. Increases UI complexity; reserve for after user requests, not pre-emptively.

### Deliberately out of scope

- Cloud sync.
- Mobile / web client.
- Encryption.
- AI-anything.
- Cross-platform port.
- Multi-user support.
- Plugin system.

These remain out-of-scope to preserve the project's identity as a small, single-purpose, Linux-native, no-nonsense sticky-notes app. Drift toward any of these would require a strategic re-positioning and likely a rename / brand change.

---

## Appendix A — Useful local commands

```bash
# Run from source
python3 run_stickynotes.py

# Run from source with the autostart flag (simulates autostart behavior)
python3 run_stickynotes.py --autostart

# Build snap
snapcraft

# Install local snap (skip store)
sudo snap install --dangerous stickynotes-dabobroto_X.Y.Z_amd64.snap

# Refresh from edge
sudo snap refresh stickynotes-dabobroto --edge

# Inspect installed snap's bundled autostart .desktop
cat ~/snap/stickynotes-dabobroto/current/.config/autostart/stickynotes.desktop

# Watch the app's stderr in journal (useful for autostart diagnostics)
journalctl --user -f | grep stickynotes

# What platform did Qt actually load?
QT_DEBUG_PLUGINS=1 stickynotes-dabobroto.stickynotes 2>&1 | grep -i "loaded library\|qt.qpa.*platform" | head

# Where is QSettings stored?
ls -la ~/snap/stickynotes-dabobroto/current/.config/dstushar7/
# or for source build:
ls -la ~/.config/dstushar7/

# Inspect the autostart entry
cat ~/snap/stickynotes-dabobroto/current/.config/autostart/stickynotes.desktop
```

## Appendix B — Glossary

| Term | Definition |
|---|---|
| **XWayland** | A compatibility layer that runs X11 clients on a Wayland session by translating X11 protocol to Wayland. Started on demand by Mutter under GNOME. |
| **xcb** | The X protocol C-language Binding — Qt's X11 platform plugin uses xcb to talk to X servers (including XWayland). |
| **USPosition / PPosition** | ICCCM `WM_NORMAL_HINTS` flags. USPosition = user-specified position (WM should honor). PPosition = program-specified position (WM treats as suggestion). |
| **autostart attribute** | Snapcraft `apps.<name>.autostart` — declares a `.desktop` file used by snapd's session agent to start the app at session login. |
| **`$SNAP_USER_DATA`** | Per-user data directory inside snap confinement (`~/snap/<name>/current`). Writable, persists across snap updates. |
| **`extensions: [gnome]`** | Snapcraft mechanism for declaring runtime dependency on the GNOME platform content snap. Provides GTK, fonts, Mesa, etc. |
| **strict confinement** | Snap's most restrictive sandbox mode. App can only access what it explicitly requests via interfaces (plugs). |
| **debounce** | Delaying an action until N ms after the last triggering event. Used for save-on-edit to coalesce a continuous typing burst into one save. |
| **glass / floating pill** | Visual design term for the translucent rounded-rectangle button style used throughout the app. |
| **collapse-to-pill** | Animation that shrinks an expanded note window into just its title bar (a horizontal "pill"). Reversible by another double-click. |

---

*End of document. Last updated for v3.2.6. Maintained by the same person who wrote the code; corrections welcome via GitHub issues.*
