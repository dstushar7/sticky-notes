
# 🗒️ Sticky Notes

![Python](https://img.shields.io/badge/python-3.10+-blue?logo=python)
![PyQt6](https://img.shields.io/badge/PyQt6-GUI-green)
![License: MIT](https://img.shields.io/badge/license-MIT-yellow)

A desktop **Sticky Notes** app built with **Python** and **PyQt6**, styled to match the look and feel of **Windows 11 Sticky Notes** — running natively on Linux.  
Jot down thoughts, ideas, and reminders right on your desktop with rich text, color themes, and a clean frameless UI.  
Notes are automatically saved and fully restored between sessions.

---

## 🚀 Features

- 🖊️ Create multiple sticky notes effortlessly via the `+` button or tray menu
- 💾 Auto-saves note content, position, size, theme, and state every 5 seconds
- 🎨 **7 color themes** — Yellow, Green, Pink, Purple, Blue, Gray, Charcoal
- ✍️ **Rich text formatting** — Bold (`Ctrl+B`), Italic (`Ctrl+I`), Underline (`Ctrl+U`)
- 📋 **Bullet lists with nested sublists** — Toggle with `Ctrl+Shift+L`; `Tab` indents to a sublist (style cycles ●→○→■), `Shift+Tab` outdents; `Enter` continues, `Shift+Enter` breaks out
- 🪄 **Collapse / expand** — double-click the title bar to collapse a note to just its header
- 🖱️ **Resizable from all 8 edges and corners** — no OS chrome needed
- 🧩 System tray integration for quick access
- 👁️ "Show All Notes" support to bring all notes to the front
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
- ❌ **Quit the Application**

### Inside each note

| Action | How |
|--------|-----|
| **New note (same color)** | Click the `+` button in the title bar |
| **Color / delete** | Click the `•••` button → options panel |
| **Bold** | `Ctrl+B` |
| **Italic** | `Ctrl+I` |
| **Underline** | `Ctrl+U` |
| **Bullet list on/off** | `Ctrl+Shift+L` |
| **Continue list item** | `Enter` |
| **Break out of list** | `Shift+Enter` |
| **Indent (sublist)** | `Tab` while in a list |
| **Outdent** | `Shift+Tab` while in a list |
| **Collapse / expand** | Double-click the title bar spacer |
| **Drag window** | Click and drag the title bar spacer |
| **Resize window** | Drag any edge or corner (16 px grab zone) |

---

## 🪟 UI Overview

Each note is a frameless, rounded-corner window with a drop shadow:

```
┌──────────────────────────────────┐
│  +    [  drag handle  ]      ••• │  ← title bar (theme color)
├──────────────────────────────────┤
│                                  │
│   Your note text here…           │  ← text area (transparent)
│                                  │
└──────────────────────────────────┘
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
│   ├── note_window.py       # NoteTextEdit, TitleBar, OptionsPanel, StickyNote
│   ├── tray_manager.py      # Manages tray icon and note lifecycle
│   └── utils.py             # Icon creation, get_theme(), apply_theme_to_window()
│
├── run_stickynotes.py       # Entry script to launch the app
├── requirements.txt         # Dependency list
├── CHANGES.md               # Session changelog
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
