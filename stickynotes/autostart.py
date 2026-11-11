# stickynotes/autostart.py
#
# XDG autostart toggle. Writes/removes ~/.config/autostart/stickynotes.desktop.
# Honored by GNOME, KDE, XFCE, and most Linux desktop environments.
#
# Under strict snap confinement the XDG paths redirect to
# $SNAP_USER_DATA/.config/autostart — exactly where snapd's session agent
# looks. It links per-snap entries into the real ~/.config/autostart at
# session start, so the same code path works for both source and snap
# builds without any interface plug.
#
# Under Flatpak the sandbox's ~/.config is private, so the file written here
# only records the preference; login autostart itself is requested from the
# host via the XDG Background portal (is_flatpak_runtime / set_enabled).

import os
import sys
from pathlib import Path

_DESKTOP_FILENAME = "stickynotes.desktop"
_OWN_SNAP_NAME = "stickynotes-dabobroto"
_OWN_SNAP_APP = "stickynotes"


# ---------------------------------------------------------------------------
# Snap detection
# ---------------------------------------------------------------------------

def is_snap_runtime() -> bool:
    """True iff we're running under our own snap (not a parent snap like VS Code).

    $SNAP_NAME can leak from a parent snap, so match against our own name
    rather than trusting any non-empty value.
    """
    return os.environ.get("SNAP_NAME") == _OWN_SNAP_NAME


FLATPAK_APP_ID = "com.dabobrotosarkar.StickyNotes"


def is_flatpak_runtime() -> bool:
    """True iff we're running as our own Flatpak.

    Inside the sandbox ~/.config is private to the app, so the autostart
    entry this module writes is never seen by the desktop session. Login
    autostart has to be requested from the host through the XDG Background
    portal instead (see _request_portal_autostart).
    """
    return os.environ.get("FLATPAK_ID") == FLATPAK_APP_ID


def _request_portal_autostart(enabled: bool) -> None:
    """Ask the XDG Background portal to add or remove our login autostart.

    The portal writes (or deletes) the real entry in the host's
    ~/.config/autostart, running `flatpak run ... stickynotes --autostart`.

    Raises OSError when the desktop can't do it — e.g. XFCE without
    xdg-desktop-portal-xapp has no Background portal at all — so callers
    keep the switch off and say why, instead of claiming autostart is on.
    The call is synchronous but quick: the portal answers at once with a
    request handle, and the desktop applies (or asks about) it afterwards.
    """
    try:
        from PyQt6.QtCore import QMetaType
        from PyQt6.QtDBus import QDBus, QDBusArgument, QDBusConnection, QDBusMessage
    except ImportError as e:
        raise OSError(f"D-Bus support is missing ({e})") from e
    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        raise OSError("no connection to the desktop session")
    # Options are a{sv}: PyQt already wraps each dict value in a variant, so
    # pass plain values (wrapping them in QDBusVariant sends 'v' inside 'v',
    # which the portal rejects). 'commandline' must be an array of strings
    # ('as'); a plain Python list would go out as 'av', hence QDBusArgument.
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


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _autostart_dir() -> Path:
    # Under snap, HOME / XDG_CONFIG_HOME are redirected to
    # $SNAP_USER_DATA/.config — exactly where snapd's session agent looks
    # before linking entries into the real ~/.config/autostart at login.
    # Outside snap this is just the standard XDG path.
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart"


def _desktop_path() -> Path:
    return _autostart_dir() / _DESKTOP_FILENAME


def _exec_argv() -> list[str]:
    """Argv to invoke when autostart fires.

    The trailing --autostart marker lets the launched app distinguish a
    login-time autostart from a manual user launch. TrayManager uses
    this to skip creating a blank starter note when the user has no
    saved notes — so logging in to an empty state stays quiet instead
    of flashing up a useless empty window every time.
    """
    if is_snap_runtime():
        return [f"/snap/bin/{_OWN_SNAP_NAME}.{_OWN_SNAP_APP}", "--autostart"]
    entry = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
    if entry and entry.endswith("run_stickynotes.py"):
        return [sys.executable, entry, "--autostart"]
    # Last-resort fallback — at least the interpreter is correct.
    return [sys.executable, "--autostart"]


# ---------------------------------------------------------------------------
# Quoting helpers
# ---------------------------------------------------------------------------

def _sh_single_quote(s: str) -> str:
    """Wrap s as a single-quoted POSIX shell literal (handles embedded ')."""
    return "'" + s.replace("'", "'\\''") + "'"


def _xdg_quote(s: str) -> str:
    """Wrap s in double quotes per XDG Desktop Entry Exec= field rules.

    Inside double quotes, these chars need a leading backslash:
        "  \\  $  `
    Order matters: escape `\\` first, then the other reserved chars.
    """
    escaped = (
        s.replace("\\", "\\\\")
         .replace('"', '\\"')
         .replace("$", "\\$")
         .replace("`", "\\`")
    )
    return f'"{escaped}"'


def _exec_line() -> str:
    """Build the Exec= value for the autostart desktop entry.

    Under snap: a plain XDG Exec line — just the namespaced /snap/bin/...
    command. snapd's session-agent syncs the desktop file from
    $SNAP_USER_DATA/.config/autostart/ into ~/.config/autostart/ at login,
    and we suspect it filters out non-trivial Exec lines (sh -c wrappers
    in particular). snapd also handles cleanup of synced entries when the
    snap is removed, so the source-build's self-cleaning logic is moot.

    Outside snap: a self-cleaning /bin/sh -c '<inner>' wrapper that removes
    the autostart entry if the launcher binary has disappeared (source
    folder deleted, venv removed, etc.), so a stale entry doesn't fail
    silently at every login.
    """
    argv = _exec_argv()

    if is_snap_runtime():
        # Plain space-joined argv. snapd parses Exec=, discards the binary
        # token, and appends remaining args to the <snap>.<app> wrapper
        # invocation. No XDG quoting needed — neither the snap path nor
        # --autostart contains shell-special characters.
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_enabled() -> bool:
    return _desktop_path().is_file()


def set_enabled(enabled: bool) -> None:
    """Enable or disable the autostart entry. Raises OSError on I/O failure.

    Under Flatpak the local file is only our own record of the preference
    (it lives in the sandbox, invisible to the session); the real login
    entry is requested from the host through the Background portal.
    """
    if is_flatpak_runtime():
        try:
            _request_portal_autostart(enabled)
        except OSError:
            if enabled:
                # Drop any earlier record too, so the switch never shows
                # "on" for an autostart the desktop isn't going to do.
                _desktop_path().unlink(missing_ok=True)
                raise
            # Disabling: there is nothing on the host to remove if the
            # portal is missing, so still clear our own record below.
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
        # Write the file directly; only create the parent directory if it's
        # genuinely missing. Avoids a redundant mkdir on every toggle when
        # ~/.config/autostart already exists (the common case). The snap
        # personal-files grant covers the directory, so the fallback mkdir
        # also succeeds under confinement.
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
