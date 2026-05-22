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
    """Argv to invoke when autostart fires."""
    if is_snap_runtime():
        return [f"/snap/bin/{_OWN_SNAP_NAME}.{_OWN_SNAP_APP}"]
    entry = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
    if entry and entry.endswith("run_stickynotes.py"):
        return [sys.executable, entry]
    # Last-resort fallback — at least the interpreter is correct.
    return [sys.executable]


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
        # Single-token /snap/bin/<snap>.<app> — no quoting needed
        # (snap/app names can't contain shell-special characters).
        return argv[0]

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
    """Enable or disable the autostart entry. Raises OSError on I/O failure."""
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
