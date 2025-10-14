
# 🗒️ Sticky Notes

![Python](https://img.shields.io/badge/python-3.10+-blue?logo=python)
![PyQt6](https://img.shields.io/badge/PyQt6-GUI-green)
![License: MIT](https://img.shields.io/badge/license-MIT-yellow)

A simple and elegant desktop **Sticky Notes** app built with **Python** and **PyQt6**.  
Quickly jot down thoughts, ideas, and reminders — right on your desktop.  
Notes are automatically saved and restored between sessions.

---

## 🚀 Features

- 🖊️ Create multiple sticky notes effortlessly  
- 💾 Auto-saves note content and position between sessions  
- 🎨 Light, clean, and distraction-free design  
- 🧩 System tray integration for quick access  
- 👁️ “Show All Notes” support to quickly bring all notes to front  
- 🌈 Theme-ready color architecture (Light & Dark support coming soon!)  
- 🟢 Packaged as a **Snap app** for easy Linux installation  

---

## ⚙️ Installation

### 🧩 Option 1 – From the Snap Store (Recommended)

Once published, you’ll be able to install it directly from the Ubuntu Software Center or via terminal:

```bash
sudo snap install sticky-notes
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
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3. Run the app:

    ```bash
    python3 run_stickynotes.py
    ```

---

## 🏃 Usage

Once launched, a sticky notes icon 🗒️ appears in your **system tray**.  
Right-click the tray icon to:

- 📝 **Create New Note**
- 👁️ **Show All Notes**
- ❌ **Quit the Application**

Within each note:
- Right-click inside the note to open its quick actions.
- Choose **📝 New Note** or **🗑️ Delete Note** directly from the context menu.

Notes automatically save their text and size — even if you close and reopen the app.

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
│   ├── config.py            # App configuration and theme constants
│   ├── note_window.py       # Sticky Note window class
│   ├── tray_manager.py      # Manages tray icon and logic
│   └── utils.py             # Helper functions (e.g., icon creation)
│
├── run_stickynotes.py       # Entry script to launch the app
├── requirements.txt         # Dependency list
├── .gitignore               # Ignored files for version control
├── LICENSE                  # Open source license
└── README.md                # Documentation
```

---

## 🧩 Requirements

- 🐍 Python **3.10+**
- 🪟 PyQt6 **6.5+**

The dependencies are listed in [requirements.txt](./requirements.txt):

```
PyQt6>=6.5
```

Install them with:
```bash
pip install -r requirements.txt
```

---

## 🧰 Technologies Used

- **[Python 3.10+](https://www.python.org/)**  
- **[PyQt6](https://www.riverbankcomputing.com/software/pyqt/)** for GUI interface  
- **[Snapcraft](https://snapcraft.io/)** for app packaging and distribution  

---

## 🛠️ Local Development

To contribute or customize:

```bash
# Create a new branch for your changes
git checkout -b feature/your-feature

# After changes
git add .
git commit -m "Add new feature"

# Push and open a PR
git push origin feature/your-feature
```

Suggested areas for contribution:
- 🌈 Add Dark/Light theme switch
- 🖋️ Text formatting (bold, italics)
- 📅 Reminder and notification features
- 📁 Note organization (tags/folders)

---

## 🧾 .gitignore Recommendations

Make sure `.gitignore` includes:

```
venv/
__pycache__/
*.pyc
*.log
*.snap
.DS_Store
```

This keeps your repository clean when committed to GitHub.

---

<!-- ## 🖼️ Screenshot

*(Optional: replace this placeholder once you capture your app’s look)*

![Screenshot of Sticky Notes](https://via.placeholder.com/800x400?text=Sticky+Notes+App+Preview)

-->

## 📜 License

This project is licensed under the **MIT License**.  
See the [LICENSE](./LICENSE) file for details.  

> License © 2025 **Tushar D. (@dstushar7)** — Open for community contributions.

---

## 💡 Future Enhancements

- 🌈 Customizable note colors and full theme switching  
- 📅 Reminder & notification integration  
- 🔄 Cloud sync across devices  
- 📁 Folder & tagging support for better organization  
- 🧰 Optional toolbar actions (font, text size, pinning)  

---

## 👨‍💻 Author

**Tushar D. (@dstushar7)**  
🔗 [GitHub Profile](https://github.com/dstushar7)

---

## 🥳 Final Notes

Sticky Notes is designed to be simple, fast, and reliable —  
your go‑to place for quick thoughts, todos, and ideas.

**Feedback and pull requests are always welcome — let’s build together!**
