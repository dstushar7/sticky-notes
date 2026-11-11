# X11 window-manager hints via python-xlib. Best effort: does nothing outside
# X11/XWayland and never raises.

from __future__ import annotations


_STATE_ABOVE = "_NET_WM_STATE_ABOVE"
_STATE_SKIP_TASKBAR = "_NET_WM_STATE_SKIP_TASKBAR"
_STATE_SKIP_PAGER = "_NET_WM_STATE_SKIP_PAGER"


def _send_wm_state(widget, atom_names, enabled: bool) -> bool:
    """Ask the WM to add or remove _NET_WM_STATE atoms on a mapped window.
    Not through Qt window flags: changing those recreates the X window (flicker, lost hints).
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

            # [action: 1 add / 0 remove, atom, second atom or 0, source 1 = application, 0]
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
        # A failed hint must never crash the app.
        return False


def set_always_on_top(widget, enabled: bool) -> bool:
    """Keep the window above others (_NET_WM_STATE_ABOVE)."""
    return _send_wm_state(widget, [_STATE_ABOVE], enabled)


def set_skip_taskbar(widget, enabled: bool) -> bool:
    """Hide the window from the dock, taskbar and pager. Under Mutter this hides it from Alt-Tab too."""
    return _send_wm_state(
        widget, [_STATE_SKIP_TASKBAR, _STATE_SKIP_PAGER], enabled
    )


def set_initial_wm_states(widget, above: bool = False,
                          skip_taskbar: bool = False) -> bool:
    """Set _NET_WM_STATE before the first map, so a pinned or hidden note never flickers.
    Replaces the whole property: pass every wanted state at once.
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


# Motif WM hints (values from MwmUtil.h); Mutter, KWin and xfwm4 read them.
_MWM_HINTS_FUNCTIONS = 1 << 0
_MWM_HINTS_DECORATIONS = 1 << 1
_MWM_FUNC_RESIZE = 1 << 1
_MWM_FUNC_MOVE = 1 << 2
_MWM_FUNC_MINIMIZE = 1 << 3
_MWM_FUNC_CLOSE = 1 << 5


def disable_maximize(widget) -> bool:
    """Remove the window's maximize function, which also stops edge tiling.
    A maximized note ignores resizes, so collapsing it left an invisible full-screen window.
    """
    try:
        from Xlib import display
    except ImportError:
        return False

    try:
        win_id = int(widget.winId())
        if win_id == 0:
            return False

        d = display.Display()
        try:
            xwin = d.create_resource_object("window", win_id)
            atom = d.intern_atom("_MOTIF_WM_HINTS")
            # [flags, functions, decorations, input_mode, status]
            xwin.change_property(atom, atom, 32, [
                _MWM_HINTS_FUNCTIONS | _MWM_HINTS_DECORATIONS,
                _MWM_FUNC_RESIZE | _MWM_FUNC_MOVE
                | _MWM_FUNC_MINIMIZE | _MWM_FUNC_CLOSE,
                0, 0, 0,
            ])
            d.sync()
            return True
        finally:
            d.close()
    except Exception:
        return False


def mark_position_user_requested(widget) -> bool:
    """Mark the geometry as user-requested (USPosition/USSize) so the WM keeps it.
    Belt and braces: Qt usually sets these already. Returns whether the hint landed.
    """
    try:
        from Xlib import Xutil, display
    except ImportError:
        return False

    try:
        # winId() creates the native window if it doesn't exist yet.
        win_id = int(widget.winId())
        if win_id == 0:
            return False  # Not on X11 (native Wayland), or creation failed.

        d = display.Display()
        try:
            xwin = d.create_resource_object("window", win_id)
            hints = xwin.get_wm_normal_hints()
            if hints is None:
                # No hints to OR into; don't invent a hints struct.
                return False
            # These constants live in Xlib.Xutil, not Xlib.X.
            hints.flags |= Xutil.USPosition | Xutil.USSize
            xwin.set_wm_normal_hints(hints)
            d.sync()
            return True
        finally:
            d.close()
    except Exception:
        # Best effort: a failed hint must not break the app.
        return False
