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
    this entirely (they have no race to smooth).

    Polls until XWayland is actually ready — slow laptops can take many
    seconds to bring it up. Hard ceiling of 5 minutes is a pure safety
    net for genuinely broken sessions; in practice XWayland appears in
    seconds. Heartbeat log to stderr every 5 s so journalctl can show
    exactly how long the wait took (or that we're stuck)."""
    if "--autostart" not in sys.argv:
        return
    if os.environ.get("XDG_SESSION_TYPE") != "wayland":
        return

    HARD_CAP_SEC = 300.0
    HEARTBEAT_SEC = 5.0
    POLL_SEC = 0.1

    waited = 0.0
    last_log = 0.0
    while waited < HARD_CAP_SEC:
        if os.path.exists("/tmp/.X11-unix/X0"):
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


def main():
    """Main function to initialize and run the application."""
    app = QApplication(sys.argv)

    # Diagnostic: log the actual platform Qt loaded. Useful for spotting
    # autostart-on-Wayland regressions — if this prints "wayland" instead
    # of "xcb" we know xcb failed to initialize and we'll have no
    # absolute window positioning this session.
    if "--autostart" in sys.argv:
        print(
            f"[stickynotes] Qt platform: {app.platformName()}",
            file=sys.stderr, flush=True,
        )

    # Stable app identity. On Wayland, Mutter uses the app_id (derived
    # from these) to remember per-app window positions across sessions.
    # Without these, every note re-spawns at the compositor's default spot.
    app.setOrganizationName(config.ORG_NAME)
    app.setApplicationName(config.APP_NAME)
    app.setApplicationDisplayName("Sticky Notes")
    app.setDesktopFileName("stickynotes")

    # Style tooltips app-wide before any window exists, so the first tooltip
    # shown is already themed. Currently the only app-level stylesheet — if
    # more are ever added, concatenate rather than overwriting this one.
    app.setStyleSheet(utils.tooltip_stylesheet())

    _ = TrayManager(app)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()