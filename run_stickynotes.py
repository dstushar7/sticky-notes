#!/usr/bin/env python3
# run_stickynotes.py

import os
# Force xcb (X11) everywhere — natively on X11, via XWayland on Wayland.
# Must be set before QApplication is constructed; Qt reads it during init.
# Unconditional assignment (NOT setdefault): the snap GNOME extension's
# launcher pre-sets QT_QPA_PLATFORM=wayland on Wayland sessions, so we
# have to overwrite it. Without this, Qt would load the wayland plugin
# and lose absolute window positioning (notes wouldn't restore position,
# decorated dialogs wouldn't be movable).
os.environ["QT_QPA_PLATFORM"] = "xcb;wayland"

import sys
from PyQt6.QtWidgets import QApplication
from stickynotes.tray_manager import TrayManager
from stickynotes import config


def main():
    """Main function to initialize and run the application."""
    app = QApplication(sys.argv)

    # Stable app identity. On Wayland, Mutter uses the app_id (derived
    # from these) to remember per-app window positions across sessions.
    # Without these, every note re-spawns at the compositor's default spot.
    app.setOrganizationName(config.ORG_NAME)
    app.setApplicationName(config.APP_NAME)
    app.setApplicationDisplayName("Sticky Notes")
    app.setDesktopFileName("stickynotes")

    _ = TrayManager(app)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()