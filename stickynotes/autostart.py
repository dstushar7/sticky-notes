# stickynotes/autostart.py
#
# XDG autostart toggle. Writes/removes ~/.config/autostart/stickynotes.desktop.
# Honored by GNOME, KDE, XFCE, and most Linux desktop environments.
#
# Snap caveat: under strict snap confinement the XDG paths are redirected
# into ~/snap/<name>/current/.config/ which the desktop session ignores
# at login. The UI uses is_snap_runtime() to disable the toggle in snap
# rather than silently writing a no-op file.

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
    # Under strict snap confinement HOME and XDG_CONFIG_HOME are redirected
    # into ~/snap/<name>/current/.config, which the desktop session never
    # reads at login. The personal-files plug grants write to the REAL
    # ~/.config/autostart, so target that explicitly via SNAP_REAL_HOME.
    if is_snap_runtime():
        real_home = os.environ.get("SNAP_REAL_HOME") or str(Path.home())
        return Path(real_home) / ".config" / "autostart"
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
    """Self-cleaning Exec= line.

    The desktop session ultimately runs:
        /bin/sh -c '<inner>'
    where <inner> is:
        if [ -x <binary> ]; then exec <argv...>; else rm -f <desktop>; fi

    If the launcher disappears (source folder deleted, snap removed, etc.)
    the autostart entry quietly removes itself on the next login attempt
    instead of failing forever.
    """
    argv = _exec_argv()
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
