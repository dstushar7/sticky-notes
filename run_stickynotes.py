#!/usr/bin/env python3
# run_stickynotes.py

import os
import sys
import time

# Force xcb (X11) everywhere — natively on X11, via XWayland on Wayland.
# Must be set before QApplication is constructed; Qt reads it during init.
# Unconditional assignment (NOT setdefault): the snap GNOME extension's
# launcher pre-sets QT_QPA_PLATFORM=wayland on Wayland sessions, so we
# have to overwrite it. Without this, Qt would load the wayland plugin
# and lose absolute window positioning (notes wouldn't restore position,
# decorated dialogs wouldn't be movable).
os.environ["QT_QPA_PLATFORM"] = "xcb;wayland"


def _wait_for_xwayland_on_autostart():
    """Smooth a known Qt + GNOME-Wayland race on first login.

    snap autostart fires while the session is still booting; XWayland on
    GNOME Mutter starts lazily and isn't always ready at that moment.
    Without this wait, Qt's xcb plugin either falls back to native wayland
    (where absolute positioning is unsupported) or initializes against a
    half-ready X server — either way, restored notes land at default
    positions instead of where the user left them.

    Scoped tight: only runs on (a) autostart launches with --autostart in
    argv AND (b) Wayland sessions. Manual launches and X11 sessions skip
    this entirely (they have no race to smooth)."""
    if "--autostart" not in sys.argv:
        return
    if os.environ.get("XDG_SESSION_TYPE") != "wayland":
        return
    # Poll for the XWayland socket; bail out as soon as it appears, with a
    # tiny extra pause to let XWayland finish accepting connections.
    # Capped at ~5 s so we never block login indefinitely.
    for _ in range(50):
        if os.path.exists("/tmp/.X11-unix/X0"):
            time.sleep(0.5)
            return
        time.sleep(0.1)


_wait_for_xwayland_on_autostart()

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