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


def set_always_on_top(widget, enabled: bool) -> bool:
    """Add or remove _NET_WM_STATE_ABOVE on the widget's X11 window.

    Deliberately NOT Qt's WindowStaysOnTopHint. Changing window flags on an
    already-visible window makes Qt destroy and recreate the native X window,
    which would (a) drop the USPosition hint set by
    mark_position_user_requested below, reintroducing the Mutter
    position-override bug, (b) reset geometry, and (c) visibly flicker. The
    EWMH client message changes WM-held state without touching the window at
    all — no recreation, no lost properties, no flicker.

    Sends to the ROOT window (not our own): per EWMH, the window manager owns
    _NET_WM_STATE and listens for change requests on root. Requires the window
    to already be mapped, so callers apply this after show() — see
    StickyNote.showEvent.

    The state is persistent WM state, not a one-shot hint: it survives
    workspace switches, minimise/restore, and other windows raising, until
    something removes it.

    Best-effort, matching the rest of this module: returns False and changes
    nothing on native Wayland, without python-xlib, or if the WM ignores us.
    """
    try:
        from Xlib import X, display
        from Xlib.protocol import event
    except ImportError:
        return False

    try:
        # winId() forces native window creation if it hasn't happened yet.
        win_id = int(widget.winId())
        if win_id == 0:
            return False  # native Wayland, or creation failed

        d = display.Display()
        try:
            xwin = d.create_resource_object("window", win_id)
            net_wm_state = d.intern_atom("_NET_WM_STATE")
            above = d.intern_atom("_NET_WM_STATE_ABOVE")

            # EWMH _NET_WM_STATE message data:
            #   [0] action — 1 = _NET_WM_STATE_ADD, 0 = _NET_WM_STATE_REMOVE
            #   [1] first property to change
            #   [2] second property (0 = none)
            #   [3] source indication — 1 = normal application
            #   [4] unused
            action = 1 if enabled else 0
            msg = event.ClientMessage(
                window=xwin,
                client_type=net_wm_state,
                data=(32, [action, above, 0, 1, 0]),
            )
            d.screen().root.send_event(
                msg,
                event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask,
            )
            d.sync()
            return True
        finally:
            d.close()
    except Exception:
        # Same contract as mark_position_user_requested: a failed window hint
        # must never take the app down. The note just won't stay on top.
        return False


def mark_position_user_requested(widget) -> bool:
    """Set the USPosition (and USSize) flag on the widget's X11
    WM_NORMAL_HINTS property. Call this AFTER move()/setGeometry but
    BEFORE show() so the hint is in place when the WM first maps the
    window. Returns True if the hint was applied, False if we silently
    skipped (no X11 connection available, no python-xlib, etc.).

    NOTE: this is belt-and-braces, not the mechanism positioning relies on.
    Qt's xcb backend already sets USPosition|USSize itself on any window it
    positions explicitly — verified for both the move() and restoreGeometry()
    paths — and this function is only called when geometry_data is not None,
    i.e. exactly those cases. It re-asserts flags Qt has already set."""
    try:
        from Xlib import Xutil, display
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
            #
            # These live in Xlib.Xutil, NOT Xlib.X. Reading them off X raises
            # AttributeError, which the `except Exception` below silently
            # swallowed — so this function returned False and set nothing at all
            # until this was corrected.
            hints.flags |= Xutil.USPosition | Xutil.USSize
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
