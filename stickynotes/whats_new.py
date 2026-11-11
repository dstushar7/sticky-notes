# One-time "What's new" notes. To announce a feature release, add an entry keyed by
# the version in __init__.py; bug-fix releases get none. Someone who skips releases
# gets one note covering everything they missed.

from typing import NamedTuple, Optional


class Release(NamedTuple):
    title: str
    body: str


RELEASES = {
    "4.0.0": Release(
        title="What's new in 4.0",
        body=(
            "<p><b>Sticky Notes got a fresh coat of paint.</b> "
            "Your notes are all here, exactly as you left them.</p>"
            "<ul>"
            "<li><b>Calmer notes:</b> the formatting buttons only appear on the "
            "note you're typing in</li>"
            "<li><b>Opacity:</b> ••• has a slider to make a note see-through. "
            "Hover over it and it turns solid again</li>"
            "<li><b>All notes</b> in the tray menu: search and find any note</li>"
            "<li>Deleted something by mistake? Hit <b>Undo</b></li>"
            "<li>Settings, shortcuts and About now live in one window</li>"
            "</ul>"
            "<p>You can delete this note.</p>"
        ),
    ),
    "3.6.0": Release(
        title="What's new in 3.6",
        body=(
            "<p><b>You can share notes now!</b></p>"
            "<p>I needed to send a task list to a colleague, so I built this feature.</p>"
            "<ul>"
            "<li><b>•••</b> → <b>↗ Share</b> copies the note</li>"
            "<li>Paste it anywhere: Slack, Teams, WhatsApp, email</li>"
            "<li>They hit <b>•••</b> → <b>↙ Receive</b> and it pops up, "
            "checkboxes and all</li>"
            "</ul>"
            "<p>No account, no cloud. They just need this app too.</p>"
            "<p>Happy sharing! You can delete this note.</p>"
        ),
    ),
}


def _parse(version: str) -> Optional[tuple]:
    try:
        return tuple(int(part) for part in version.split("."))
    except (AttributeError, ValueError):
        return None


def pending(last_seen: Optional[str], current: str) -> Optional[Release]:
    """The note to show after upgrading from `last_seen` to `current`, or None.
    Installs from before version tracking (None) count as older than every entry.
    """
    now = _parse(current)
    if now is None:
        return None
    since = _parse(last_seen) if last_seen else ()
    if since is None:
        return None   # unreadable stored version — say nothing rather than guess

    missed = []
    for key, release in RELEASES.items():
        version = _parse(key)
        if version and since < version <= now:
            missed.append((version, release))
    missed.sort(key=lambda item: item[0], reverse=True)
    due = [release for _, release in missed]

    if not due:
        return None
    if len(due) == 1:
        return due[0]
    # Several missed releases: newest title, each release's body in turn.
    return Release(
        title=due[0].title,
        body="".join(f"<p><b>{r.title}</b></p>{r.body}" for r in due),
    )
