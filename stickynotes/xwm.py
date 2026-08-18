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


# EWMH _NET_WM_STATE atoms we manage. Both are per-window states the window
# manager owns; we ask it to change them rather than setting them ourselves.
_STATE_ABOVE = "_NET_WM_STATE_ABOVE"
_STATE_SKIP_TASKBAR = "_NET_WM_STATE_SKIP_TASKBAR"
_STATE_SKIP_PAGER = "_NET_WM_STATE_SKIP_PAGER"


def _send_wm_state(widget, atom_names, enabled: bool) -> bool:
    """Ask the WM to add or remove up to two _NET_WM_STATE atoms on `widget`.

    Deliberately NOT Qt's window flags. Changing flags on an already-visible
    window makes Qt destroy and recreate the native X window, which would
    (a) drop the USPosition hint set by mark_position_user_requested below,
    reintroducing the Mutter position-override bug, (b) reset geometry, and
    (c) visibly flicker. The EWMH client message changes WM-held state without
    touching the window at all.

    Sends to the ROOT window, not our own: per EWMH the window manager owns
    _NET_WM_STATE and listens for change requests on root. Requires the window
    to already be MAPPED — Mutter ignores these for unmapped windows, and in
    fact clears _NET_WM_STATE entirely on unmap. See set_initial_wm_states for
    the before-first-map path, and StickyNote.showEvent for re-assertion.
    """
    try:
        from Xlib import X, display
        from Xlib.protocol import event
    except ImportError:
        return False

    try:
        win_id = int(widget.winId())
        if win_id == 0:
            return False  # native Wayland, or creation failed

        d = display.Display()
        try:
            xwin = d.create_resource_object("window", win_id)
            atoms = [d.intern_atom(n) for n in atom_names[:2]]
            while len(atoms) < 2:
                atoms.append(0)

            # EWMH _NET_WM_STATE message data:
            #   [0] action — 1 = _NET_WM_STATE_ADD, 0 = _NET_WM_STATE_REMOVE
            #   [1] first property to change
            #   [2] second property (0 = none)
            #   [3] source indication — 1 = normal application
            #   [4] unused
            msg = event.ClientMessage(
                window=xwin,
                client_type=d.intern_atom("_NET_WM_STATE"),
                data=(32, [1 if enabled else 0, atoms[0], atoms[1], 1, 0]),
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
        # must never take the app down. The window just keeps its old state.
        return False


def set_always_on_top(widget, enabled: bool) -> bool:
    """Keep the window above others (_NET_WM_STATE_ABOVE).

    Persistent WM state, not a one-shot hint: it survives workspace switches,
    minimise/restore and other windows raising, until something removes it.
    """
    return _send_wm_state(widget, [_STATE_ABOVE], enabled)


def set_skip_taskbar(widget, enabled: bool) -> bool:
    """Hide the window from the dock/taskbar and pager.

    SKIP_PAGER rides along with SKIP_TASKBAR because a window absent from the
    dock but still listed in the workspace switcher is a half-done job.

    Caller beware: under Mutter this also removes the window from Alt-Tab —
    the same flag drives both, and EWMH offers no way to separate them.
    """
    return _send_wm_state(
        widget, [_STATE_SKIP_TASKBAR, _STATE_SKIP_PAGER], enabled
    )


def set_initial_wm_states(widget, above: bool = False,
                          skip_taskbar: bool = False) -> bool:
    """Write _NET_WM_STATE directly, for a window that has NOT been shown yet.

    EWMH requires the WM to honour whatever _NET_WM_STATE is present on the
    window when it maps it, and Mutter does. That matters for appearance:
    applying these via client message after show() means a pinned note is
    briefly not-on-top, and a hidden note flashes into the dock before
    vanishing. Setting the property pre-map avoids both.

    Replaces the whole property, so every desired state must be passed at once
    — hence the flags rather than one call per state.
    """
    try:
        from Xlib import Xatom, display
    except ImportError:
        return False

    names = []
    if above:
        names.append(_STATE_ABOVE)
    if skip_taskbar:
        names.extend((_STATE_SKIP_TASKBAR, _STATE_SKIP_PAGER))
    if not names:
        return True  # nothing to assert; leaving the property unset is correct

    try:
        win_id = int(widget.winId())
        if win_id == 0:
            return False

        d = display.Display()
        try:
            xwin = d.create_resource_object("window", win_id)
            xwin.change_property(
                d.intern_atom("_NET_WM_STATE"), Xatom.ATOM, 32,
                [d.intern_atom(n) for n in names],
            )
            d.sync()
            return True
        finally:
            d.close()
    except Exception:
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
