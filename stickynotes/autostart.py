# Login autostart through an XDG autostart entry. Under snap, snapd syncs the
# entry to the host; under Flatpak, the Background portal creates it.

import os
import sys
from pathlib import Path

_DESKTOP_FILENAME = "stickynotes.desktop"
_OWN_SNAP_NAME = "stickynotes-dabobroto"
_OWN_SNAP_APP = "stickynotes"


def is_snap_runtime() -> bool:
    """True only under our own snap: $SNAP_NAME leaks in from parent snaps like VS Code."""
    return os.environ.get("SNAP_NAME") == _OWN_SNAP_NAME


FLATPAK_APP_ID = "com.dabobrotosarkar.StickyNotes"


def is_flatpak_runtime() -> bool:
    """True only under our own Flatpak."""
    return os.environ.get("FLATPAK_ID") == FLATPAK_APP_ID


def _request_portal_autostart(enabled: bool) -> None:
    """Ask the Background portal to add or remove the host's autostart entry.
    Raises OSError when the desktop has none (e.g. XFCE without xdg-desktop-portal-xapp).
    """
    try:
        from PyQt6.QtCore import QMetaType
        from PyQt6.QtDBus import QDBus, QDBusArgument, QDBusConnection, QDBusMessage
    except ImportError as e:
        raise OSError(f"D-Bus support is missing ({e})") from e
    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        raise OSError("no connection to the desktop session")
    # Plain values: PyQt wraps a{sv} values itself, and QDBusVariant would nest them.
    # 'commandline' must be 'as'; a Python list would be sent as 'av'.
    commandline = QDBusArgument()
    commandline.add(["stickynotes", "--autostart"], QMetaType.Type.QStringList.value)
    options = {
        "reason": "Open Sticky Notes quietly in the tray when you log in",
        "autostart": bool(enabled),
        "commandline": commandline,
        "dbus-activatable": False,
    }
    msg = QDBusMessage.createMethodCall(
        "org.freedesktop.portal.Desktop",
        "/org/freedesktop/portal/desktop",
        "org.freedesktop.portal.Background",
        "RequestBackground",
    )
    msg.setArguments(["", options])
    reply = bus.call(msg, QDBus.CallMode.Block, 2000)
    if reply.type() == QDBusMessage.MessageType.ErrorMessage:
        if reply.errorName() in ("org.freedesktop.DBus.Error.UnknownMethod",
                                 "org.freedesktop.DBus.Error.UnknownInterface",
                                 "org.freedesktop.DBus.Error.ServiceUnknown"):
            raise OSError("this desktop can't start Flatpak apps at login. "
                          "Add Sticky Notes to your startup applications instead")
        raise OSError(reply.errorMessage() or reply.errorName())


def _autostart_dir() -> Path:
    # Under snap this resolves into $SNAP_USER_DATA, where snapd's session agent looks.
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart"


def _desktop_path() -> Path:
    return _autostart_dir() / _DESKTOP_FILENAME


def _exec_argv() -> list[str]:
    """Command for the autostart entry; --autostart makes the app start quietly in the tray."""
    if is_snap_runtime():
        return [f"/snap/bin/{_OWN_SNAP_NAME}.{_OWN_SNAP_APP}", "--autostart"]
    entry = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
    if entry and entry.endswith("run_stickynotes.py"):
        return [sys.executable, entry, "--autostart"]
    # Last-resort fallback — at least the interpreter is correct.
    return [sys.executable, "--autostart"]


def _sh_single_quote(s: str) -> str:
    """Wrap s as a single-quoted POSIX shell literal (handles embedded ')."""
    return "'" + s.replace("'", "'\\''") + "'"


def _xdg_quote(s: str) -> str:
    """Double-quote s for a desktop entry's Exec= field."""
    escaped = (
        s.replace("\\", "\\\\")
         .replace('"', '\\"')
         .replace("$", "\\$")
         .replace("`", "\\`")
    )
    return f'"{escaped}"'


def _exec_line() -> str:
    """The Exec= line. Snap: the plain /snap/bin command, which snapd rewrites.
    Elsewhere: a sh wrapper that deletes the entry once the launcher is gone.
    """
    argv = _exec_argv()

    if is_snap_runtime():
        # snapd swaps the binary for its own wrapper and keeps the arguments.
        return " ".join(argv)

    binary = argv[0]
    desktop = str(_desktop_path())

    quoted_argv = " ".join(_sh_single_quote(a) for a in argv)
    inner = (
        f"if [ -x {_sh_single_quote(binary)} ]; then "
        f"exec {quoted_argv}; "
        f"else rm -f {_sh_single_quote(desktop)}; fi"
    )
    return f"/bin/sh -c {_xdg_quote(inner)}"


def is_enabled() -> bool:
    return _desktop_path().is_file()


def set_enabled(enabled: bool) -> None:
    """Turn autostart on or off. Raises OSError on failure.
    Under Flatpak the local file only records the choice; the portal does the real work.
    """
    if is_flatpak_runtime():
        try:
            _request_portal_autostart(enabled)
        except OSError:
            if enabled:
                # Clear any old record so the switch never shows a stale "on".
                _desktop_path().unlink(missing_ok=True)
                raise
            # Without a portal there is nothing on the host to remove; still clear our record.
    path = _desktop_path()
    if enabled:
        contents = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Sticky Notes\n"
            f"Exec={_exec_line()}\n"
            "X-GNOME-Autostart-enabled=true\n"
            "Terminal=false\n"
            "Categories=Utility;\n"
        )
        try:
            path.write_text(contents)
        except FileNotFoundError:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
