
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
- ✍️ **Rich text formatting** — Bold (`Ctrl+B`), Italic (`Ctrl+I`), Underline (`Ctrl+U`), Strikethrough (`Ctrl+Shift+S`)
- 📋 **Bullet lists with nested sublists** — Toggle with `Ctrl+Shift+L`; `Tab` indents to a sublist (style cycles ●→○→■), `Shift+Tab` outdents; `Enter` continues, `Shift+Enter` breaks out
- 🪄 **Collapse / expand** — double-click anywhere on the title bar outside the title to collapse a note to just its header
- 🖱️ **Resizable from all 8 edges and corners** — no OS chrome needed
- 🧩 System tray integration with a **Show Note ▶** submenu listing open notes, sorted by most recently edited
- 👁️ "Show All Notes" support to bring all notes to the front
- 🚀 **Launch on system startup** — the Snap build auto-starts at login after its first launch (managed by Snap; disable via your desktop's Startup Applications). The source build offers a Settings toggle backed by a self-cleaning XDG autostart entry that removes itself if the app is uninstalled
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

- 📝 **New Note** — creates a note in the default Yellow theme
- 👁️ **Show All Notes** — brings every note to the front
- 📂 **Show Note ▶** — submenu listing each open note by title, most recently edited first; click an entry to jump straight to that note
- ⚙️ **Settings…** — startup behavior (a "Launch on system startup" toggle in the source build; the Snap auto-starts at login and shows how to turn it off)
- ❌ **Quit the Application**

### Inside each note

| Action | How |
|--------|-----|
| **New note (same color)** | Click the `+` button in the title bar |
| **Rename note** | Click the title text in the title bar; press Enter to commit, Escape to cancel, or click away |
| **Color / delete** | Click the `•••` button → options panel |
| **Bold** | `Ctrl+B` |
| **Italic** | `Ctrl+I` |
| **Underline** | `Ctrl+U` |
| **Strikethrough** | `Ctrl+Shift+S` |
| **Bullet list on/off** | `Ctrl+Shift+L` |
| **Continue list item** | `Enter` |
| **Break out of list** | `Shift+Enter` |
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
│  [+]   ╭ Title ╮     drag area     [•••] │  ← title bar (theme color)
├──────────────────────────────────────────┤
│                                          │
│   Your note text here…                   │  ← text area (body color)
│                                          │
│            [B] [I] [U] [S] [≣]           │  ← format bar (theme color)
└──────────────────────────────────────────┘
```

Clicking `•••` opens a floating options panel:

```
┌─────────────────────────────────┐
│  🟡  🟢  🩷  🟣  🔵  ⬜  ⬛      │  ← color swatches (circle buttons)
│  🗑  Delete Note                 │
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
│   ├── note_window.py       # NoteTextEdit, EditableTitleLabel, DragHandle, TitleBar, FormatBar, OptionsPanel, StickyNote, SettingsDialog
│   ├── widgets.py           # FloatingButton — reusable glass-pill push button
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
| Yellow *(default)* | `#FFF176` | `#F9E44A` |
| Green | `#B5EBBF` | `#8FD9A0` |
| Pink | `#F9B8C6` | `#F48FAA` |
| Purple | `#D8B8F9` | `#BC8FF5` |
| Blue | `#B3E5FC` | `#80D0F5` |
| Gray | `#E0E0E0` | `#BDBDBD` |
| Charcoal | `#4A4A4A` | `#333333` |

Charcoal uses light text (`#f0f0f0`); all other themes use dark text (`#1a1a1a`).

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

## 👨‍💻 Author

**Tushar D. (@dstushar7)**  
🔗 [GitHub Profile](https://github.com/dstushar7)

---

**Feedback and pull requests are always welcome — let's build together!**
