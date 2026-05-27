# stickynotes/xwm.py
#
# Tiny X11 helper: tag a window's WM_NORMAL_HINTS with USPosition so the
# compositor (Mutter especially) treats the requested position as user-
# specified rather than program-specified, and honors it during the
# initial window map instead of applying its own placement strategy.
#
# Why this exists: on Wayland-via-XWayland under GNOME, Mutter overrides
# client-requested positions on initial map of "program-placed" windows.
# Subsequent move() calls are honored (that's why our previous deferred-
# reapply produced a visible jump), but the initial map is overridden.
# USPosition is the ICCCM-blessed way to say "the user explicitly asked
# for this position; do not override." All compliant X11 WMs respect it,
# including Mutter for both native X11 and XWayland surfaces.
#
# Best-effort: silently no-op outside X11/XWayland or if python-xlib
# isn't importable. Never crashes the app over a positioning hint.

from __future__ import annotations


def mark_position_user_requested(widget) -> bool:
    """Set the USPosition (and USSize) flag on the widget's X11
    WM_NORMAL_HINTS property. Call this AFTER move()/setGeometry but
    BEFORE show() so the hint is in place when the WM first maps the
    window. Returns True if the hint was applied, False if we silently
    skipped (no X11 connection available, no python-xlib, etc.)."""
    try:
        from Xlib import X, display
    except ImportError:
        return False

    try:
        # winId() triggers native window creation if it hasn't happened
        # yet — we need a real X11 window id to attach properties to.
        win_id = int(widget.winId())
        if win_id == 0:
            return False  # Not on X11 (native Wayland), or creation failed.

        d = display.Display()
        try:
            xwin = d.create_resource_object("window", win_id)
            hints = xwin.get_wm_normal_hints()
            if hints is None:
                # Qt almost always sets WM_NORMAL_HINTS before we get here
                # (with PPosition/PSize). If it didn't, there's nothing to
                # OR our flag into — bail rather than synthesize a hints
                # struct from scratch with garbage size fields.
                return False
            # USPosition (bit 0) + USSize (bit 1) — both flags together
            # mean "user explicitly asked for this geometry, honor it."
            hints.flags |= X.USPosition | X.USSize
            xwin.set_wm_normal_hints(hints)
            d.sync()
            return True
        finally:
            d.close()
    except Exception:
        # Best-effort: any failure (X11 unavailable, Qt-Xlib mismatch,
        # weird WM state) just means the hint didn't land. The app keeps
        # working — positions just won't survive Mutter's override on
        # autostart, same as before this helper existed.
        return False
