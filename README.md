
# 🗒️ Sticky Notes

![Python](https://img.shields.io/badge/python-3.10+-blue?logo=python)
![PyQt6](https://img.shields.io/badge/PyQt6-GUI-green)
![License: MIT](https://img.shields.io/badge/license-MIT-yellow)
![Installed size](https://img.shields.io/badge/installed%20size-~26%20MB-brightgreen)

A desktop **Sticky Notes** app for Linux, built with **Python** and **PyQt6** — frameless, glass-styled, outrageously pretty, and featherweight (~26 MB installed).  
Jot down thoughts, ideas, and reminders right on your desktop with rich text, 7 color themes, and a one-click collapse-to-pill UI.  
Notes save locally and are restored exactly where you left them between sessions.

---

## 🚀 Features

- 🖊️ Create multiple sticky notes effortlessly via the `+` button or tray menu
- 🏷️ **Editable note titles** — click the title pill to rename; a smart default auto-fills from the first body line until you set a custom name
- 💾 Auto-saves note content, title, position, size, theme, and last-edited time every 5 seconds
- 🎨 **7 color themes** — Yellow, Green, Pink, Purple, Blue, Gray, Charcoal
- 🫥 **Per-note opacity** — `•••` → Opacity slider (50–100%). Only the paper fades; text stays solid, and the note turns solid while you hover or type in it
- 🧘 **Calm notes** — the formatting toolbar appears only on the note you're typing in; at rest a note shows when it was last edited
- 🗂️ **All notes** — tray → All notes… lists every note with search and a colour filter; click one to bring it forward
- ↩️ **Undo delete** — a "Note deleted · Undo" toast gives you a few seconds to change your mind
- ✍️ **Rich text formatting** — Bold (`Ctrl+B`), Italic (`Ctrl+I`), Underline (`Ctrl+U`), Strikethrough (`Ctrl+Shift+S`)
- 📋 **Bullet lists with nested sublists** — Toggle with `Ctrl+Shift+L`; `Tab` indents to a sublist (style cycles ●→○→■), `Shift+Tab` outdents; `Enter` continues, `Shift+Enter` breaks out
- 🔢 **Typed lists continue themselves** — start a line with `1.`, `a.`, `A)`, `-`, `*` or `•` and `Enter` starts the next item (`2.`, `b.` … or the same bullet, same indent), like WhatsApp; numbers and letters below renumber themselves when you add, delete or nest an item; `Tab` / `Shift+Tab` nests an item; `Enter` on an empty item steps out a level, then ends the list
- 🪄 **Collapse / expand** — double-click anywhere on the title bar outside the title to collapse a note to just its header
- 📤 **Share & Receive** — `•••` → Share copies a note as a short piece of text; paste it in any chat, and the other person adds it with `•••` → Receive (or the tray menu). Same title, text, formatting and color — no account, no cloud
- 🖱️ **Resizable from all 8 edges and corners** — no OS chrome needed
- 🧩 System tray integration listing your five most recently edited notes
- 👁️ "Show All Notes" support to bring all notes to the front
- 🚀 **Launch on system startup** — on by default for new installs; toggle in Settings to disable. The app auto-launches quietly to your tray on login, restores your saved notes, and never pops a blank window at you when there's nothing to show
- 🟢 Packaged as a **Snap app** for easy Linux installation

---

## ⚙️ Installation

### 🧩 Option 1 – From the Snap Store (Recommended)

```bash
sudo snap install stickynotes-dabobroto
```

---

### 💻 Option 2 – Run from Source (Development Mode)

1. Clone the repository:

    ```bash
    git clone https://github.com/dstushar7/sticky-notes.git
    cd sticky-notes
    ```

2. Create a virtual environment and install dependencies:

    ```bash
    python3 -m venv stickyenv
    source stickyenv/bin/activate
    pip install -r requirements.txt
    ```

3. Run the app:

    ```bash
    python3 run_stickynotes.py
    ```

---

## 🏃 Usage

Once launched, a sticky notes icon appears in your **system tray**.  
Right-click the tray icon to:

- 📝 **New note** — creates a note in your chosen colour (Settings → General)
- 🗂️ **All notes…** — every note, searchable, filterable by colour
- 👁️ **Bring all to front** — raises every note
- ↙️ **Receive a note…** — add a note someone shared with you
- 🕘 **Recent** — your five most recently edited notes; click one to jump to it
- ⚙️ **Settings…** — General (startup, dock, colour for new notes), Shortcuts, and About in one window
- ❌ **Quit**

### Inside each note

| Action | How |
|--------|-----|
| **New note (same color)** | Click the `+` button in the title bar |
| **Rename note** | Click the title text in the title bar; press Enter to commit, Escape to cancel, or click away |
| **Color / opacity / share / delete** | Click the `•••` button → options menu (shows on hover) |
| **Keep on top** | Pin button in the title bar (shows on hover; stays visible while pinned) |
| **Bold** | `Ctrl+B` |
| **Italic** | `Ctrl+I` |
| **Underline** | `Ctrl+U` |
| **Strikethrough** | `Ctrl+Shift+S` |
| **Bullet list on/off** | `Ctrl+Shift+L` |
| **Continue list item** | `Enter` |
| **Break out of list** | `Shift+Enter` |
| **Continue a typed `1.` / `a.` / `-` list** | `Enter` (on an empty item: step out a level / end the list) |
| **Nest / un-nest a typed item** | `Tab` / `Shift+Tab` on a typed `1.` / `a.` / `-` line |
| **Indent (sublist)** | `Tab` while in a list |
| **Outdent** | `Shift+Tab` while in a list |
| **Collapse / expand** | Double-click the title bar outside the title (disabled while collapsed) |
| **Drag window** | Click and drag the title bar outside the title |
| **Resize window** | Drag any edge or corner (16 px grab zone) |

---

## 🪟 UI Overview

Each note is a frameless, rounded-corner window with a drop shadow. The
`+` / `•••` buttons render as floating glass chips on top of the title
bar; the title itself is a click-to-edit pill, and the empty space
between is the drag / collapse target.

```
┌──────────────────────────────────────────┐
│  [+]   ╭ Title ╮ 1/3   drag area [📌][•••]│  ← title bar; pin/••• on hover,
├──────────────────────────────────────────┤     1/3 = checklist progress (collapsed)
│   Your note text here…                   │  ← text area
│   ☑ ~~done item~~                        │
│                                          │
│   🕘 Edited 12 min ago                   │  ← at rest
│     [B] [I] [U] [S] │ [≣] [☑]            │  ← while typing in this note
└──────────────────────────────────────────┘
```

Clicking `•••` opens the options menu beside the note:

```
┌─────────────────────────────────┐
│  ● ● ● ● ● ● ●                  │  ← colours
│  Opacity                  [70%] │
│  ────────●──────────            │  ← live preview on the note
│  Keep on top                    │
│  Collapse        Double-click bar│
│  Share…            Copies as text│
│  Receive a note…                │
│  Delete note   (click twice)    │
└─────────────────────────────────┘
```

---

## 🧱 Project Structure

```
sticky-notes/
│
├── snap/
│   └── snapcraft.yaml       # Snap packaging configuration
│
├── stickynotes/             # Main Python package
│   ├── __init__.py
│   ├── config.py            # App constants, THEMES dict, sizing constants
│   ├── note_window.py       # NoteTextEdit, ChecklistHighlighter, OptionsPanel, TitleBar, FormatBar, NoteFooter, StickyNote
│   ├── chrome.py            # All notes, Settings (General/Shortcuts/About), Receive, Undo toast
│   ├── widgets.py           # FloatingButton, ToggleSwitch, MenuRow
│   ├── tray_manager.py      # Tray icon, note lifecycle, dynamic "Show Note" submenu
│   ├── autostart.py         # XDG autostart entry management
│   └── utils.py             # Icon creation, get_theme(), apply_theme_to_window()
│
├── run_stickynotes.py       # Entry script to launch the app
├── requirements.txt         # Dependency list
├── .gitignore
├── LICENSE
└── README.md
```

---

## 🧩 Requirements

- 🐍 Python **3.10+**
- 🪟 PyQt6 **6.5+**

```bash
pip install -r requirements.txt
```

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+B` | Bold |
| `Ctrl+I` | Italic |
| `Ctrl+U` | Underline |
| `Ctrl+Shift+S` | Strikethrough |
| `Ctrl+Shift+L` | Toggle bullet list |
| `Tab` | Indent (sublist) inside a list |
| `Shift+Tab` | Outdent inside a list |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` | Redo |
| `Ctrl+A` | Select all |

All formatting actions are also available via the **bottom toolbar** on each note: `B` `I` `U` `S` `•`. Buttons highlight when the cursor is in already-formatted text.

---

## 🎨 Themes

| Name | Background | Title Bar |
|------|-----------|-----------|
| Yellow *(default)* | `#FFF39C` | `#FBE36E` |
| Green | `#C6EFCF` | `#A3E2B2` |
| Pink | `#FBCAD5` | `#F6A9BC` |
| Purple | `#E0CCFB` | `#CBAAF7` |
| Blue | `#C4EAFC` | `#9AD8F6` |
| Gray | `#E6E6E6` | `#CFCFCF` |
| Charcoal | `#3C3D41` | `#2E2F33` |

Each theme's text is tinted toward its colour (e.g. `#2B2410` on yellow); every pair clears WCAG AA contrast. Charcoal uses light text (`#F1F1F1`). Notes store the theme by name, so palette changes never touch saved notes.

---

## 🧰 Technologies Used

- **[Python 3.10+](https://www.python.org/)**
- **[PyQt6](https://www.riverbankcomputing.com/software/pyqt/)** for GUI
- **[Snapcraft](https://snapcraft.io/)** for packaging and distribution

---

## 🛠️ Local Development

```bash
git checkout -b feature/your-feature
# make changes
git add .
git commit -m "feat: describe your change"
git push origin feature/your-feature
# open a pull request
```

---

## 📜 License

This project is licensed under the **MIT License**.  
See the [LICENSE](./LICENSE) file for details.

> License © 2025 **Tushar D. (@dstushar7)** — Open for community contributions.

---

## ™️ Name, Icon, and App Identity

The **code** is MIT licensed — fork it, modify it, ship it, sell it. That grant is
deliberate and it is not going to be narrowed.

The MIT licence grants **copyright** permissions. It does not grant trademark or
branding rights, and those are not being licensed here. Specifically **not**
covered by the MIT grant:

- The **application icon** ([`snap/gui/stickynotes.png`](./snap/gui/stickynotes.png))
- The **`stickynotes-dabobroto`** Snap Store package name
- The **`com.dabobrotosarkar.StickyNotes`** application ID and the
  `com.dabobrotosarkar` / `dabobrotosarkar.com` namespace
  (see [the AppStream metainfo](./com.dabobrotosarkar.StickyNotes.metainfo.xml))

To be clear about scope: no claim is made over the plain words "sticky notes,"
which are generic and describe a whole category of software. Call your fork a
sticky notes app all you like.

**If you redistribute a modified build, please rebrand it** — use your own name,
your own icon, and your own application ID under a namespace you control. This is
the same arrangement Firefox and Chromium use, and it exists for one practical
reason: so a user can tell whose build is running on their desktop. That matters
more than usual for this app, because it can place notes on a user's screen and
open links from its About dialog. Those capabilities should be attributable to
whoever actually shipped the binary.

Official builds are published only by the author. Anything else is a fork,
and should look like one.

---

## 👨‍💻 Author

**Tushar D. (@dstushar7)**  
🔗 [GitHub Profile](https://github.com/dstushar7)

---

**Feedback and pull requests are always welcome — let's build together!**
