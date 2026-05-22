#!/usr/bin/env python3
# run_stickynotes.py

import os
# Force xcb (X11) everywhere — natively on X11, via XWayland on Wayland.
# Must be set before QApplication is constructed; Qt reads it during init.
# Setting it here in Python wins over the snap GNOME extension launcher,
# which otherwise sets QT_QPA_PLATFORM=wayland based on $XDG_SESSION_TYPE
# and clobbers the apps.<name>.environment block in snapcraft.yaml.
# setdefault leaves it user-overridable for the rare wayland-only setup.
os.environ.setdefault("QT_QPA_PLATFORM", "xcb;wayland")

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