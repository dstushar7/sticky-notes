#!/usr/bin/env python3

import os
import sys
import time

# Force X11 (XWayland on Wayland): Wayland doesn't let apps place their own windows.
# Assign, don't setdefault: the snap's GNOME extension pre-sets it to wayland.
os.environ["QT_QPA_PLATFORM"] = "xcb;wayland"


def _wait_for_xwayland_on_autostart():
    """On Wayland, wait for XWayland before an autostart launch: it starts lazily at
    login, and connecting too early loses the notes' saved positions.
    """
    if "--autostart" not in sys.argv:
        return
    if os.environ.get("XDG_SESSION_TYPE") != "wayland":
        return

    HARD_CAP_SEC = 300.0
    HEARTBEAT_SEC = 5.0
    POLL_SEC = 0.1

    # This session's display, not always :0 (SDDM can hold :0; Flatpak remaps to :99).
    display = os.environ.get("DISPLAY", "")
    number = display.rpartition(":")[2].split(".")[0] if ":" in display else ""
    socket_path = f"/tmp/.X11-unix/X{number if number.isdigit() else '0'}"

    waited = 0.0
    last_log = 0.0
    while waited < HARD_CAP_SEC:
        if os.path.exists(socket_path):
            time.sleep(0.5)  # let XWayland finish accepting connections
            print(
                f"[stickynotes] XWayland ready after {waited:.1f}s",
                file=sys.stderr, flush=True,
            )
            return
        time.sleep(POLL_SEC)
        waited += POLL_SEC
        if waited - last_log >= HEARTBEAT_SEC:
            print(
                f"[stickynotes] waiting for XWayland… ({waited:.0f}s)",
                file=sys.stderr, flush=True,
            )
            last_log = waited

    print(
        "[stickynotes] XWayland did not appear within 5 min; continuing "
        "(positioning may not work this session)",
        file=sys.stderr, flush=True,
    )


_wait_for_xwayland_on_autostart()

from PyQt6.QtWidgets import QApplication
from stickynotes.tray_manager import TrayManager
from stickynotes import config
from stickynotes import utils
from stickynotes import autostart


def main():
    app = QApplication(sys.argv)

    # Logged so a fallback to native Wayland (no note positioning) shows in the journal.
    if "--autostart" in sys.argv:
        print(
            f"[stickynotes] Qt platform: {app.platformName()}",
            file=sys.stderr, flush=True,
        )

    # Stable identity; Mutter remembers per-app window positions by it.
    app.setOrganizationName(config.ORG_NAME)
    app.setApplicationName(config.APP_NAME)
    app.setApplicationDisplayName("Sticky Notes")
    # Must match the installed .desktop file name (the app ID under Flatpak).
    app.setDesktopFileName(
        autostart.FLATPAK_APP_ID if autostart.is_flatpak_runtime() else "stickynotes")

    # Before any window exists, so the first tooltip is already themed.
    app.setStyleSheet(utils.tooltip_stylesheet())

    _ = TrayManager(app)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()