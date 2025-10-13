# 🗒️ Sticky Notes

A simple and elegant desktop **Sticky Notes app** built with **Python** and **PyQt6**.  
Quickly jot down thoughts, ideas, and reminders — right on your desktop. Notes are automatically saved and restored when you reopen the app.

---

## 🚀 Features

- 🖊️ Create multiple sticky notes effortlessly.
- 💾 Auto-saves note content and positions between sessions.
- 🎨 Minimalist, clean design with a sticky-note look.
- 🧩 Built with **PyQt6**, ensuring cross-platform compatibility.
- 🟢 Packaged as a **Snap app** for easy installation on Ubuntu and Linux.

<!-- ---

## 📸 Screenshot (Optional)

*(You can replace this placeholder image link with your own screenshot later.)*

![Screenshot of Sticky Notes](https://via.placeholder.com/800x400?text=Sticky+Notes+App+Preview)

--- -->

## ⚙️ Installation

### 🧩 Option 1 – From Snap Store (Recommended)

Once published, you can install it directly from the Ubuntu App Center or via the terminal:

```bash
sudo snap install sticky-notes
```

*(Replace `sticky-notes` with your actual published Snap name if different.)*

### 💻 Option 2 – Run from Source (Development Mode)

1. Clone this repository:

    ```bash
    git clone https://github.com/dstushar7/sticky-notes.git
    cd sticky-notes
    ```

2. Set up a Python virtual environment and install dependencies:

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install PyQt6
    ```

3. Run the app:

    ```bash
    python3 main.py
    ```

---

## 🧱 Project Structure

```
sticky-notes/
│
├── main.py               # Main application code
├── snap/
│   └── snapcraft.yaml    # Snap packaging configuration
├── LICENSE               # Open-source license
└── README.md             # Documentation
```

---

## 🧰 Technologies Used

- **Python 3.10+**
- **PyQt6** for the GUI
- **Snapcraft** for packaging and distribution

---

## 🛠️ Local Development

If you want to modify or enhance the app:
- Fork this repository
- Create a new branch:
  ```bash
  git checkout -b feature/new-feature
  ```
- Make your changes and commit:
  ```bash
  git commit -m "Add new feature"
  ```
- Push changes and open a Pull Request

---

## 📜 License

This project is licensed under the **MIT License** — see the [LICENSE](./LICENSE) file for details.

---

## 💡 Future Enhancements

- 🌈 Customizable note colors and themes
- 🌐 Cloud sync between devices
- 📅 Reminder notifications
- 📁 Better note organization (folders, tags)

---

## 👨‍💻 Author

**Tushar D. (@dstushar7)**  
🔗 [GitHub Profile](https://github.com/dstushar7)

Feel free to **open issues**, **submit pull requests**, or **suggest features** — community contributions are always welcome!

---