#!/usr/bin/env python3
# run_stickynotes.py

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