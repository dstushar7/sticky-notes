# stickynotes/whats_new.py
#
# One-time "What's new" notes for feature releases.
#
# TO ANNOUNCE A RELEASE: add an entry to RELEASES below, keyed by the version
# in stickynotes/__init__.py. Nothing else needs to change. Bug-fix releases
# simply get no entry and show nothing.
#
# Who sees it (decided in TrayManager at launch):
#   * upgrading users, once, on the first launch of the new version — even
#     an autostart launch, since that's how most people start the app
#   * never a first-time user: they get the welcome note instead
# Someone skipping releases (3.6 -> 3.8) gets ONE note covering every entry
# they missed, newest first, rather than a pile of notes.
#
# Body is note HTML: <p>, <b>, <i>, <u>, <s>, <ul>/<li>. Keep it short — it
# opens as a normal sticky note the user reads and deletes.

from typing import NamedTuple, Optional


class Release(NamedTuple):
    title: str
    body: str


RELEASES = {
    "3.6.0": Release(
        title="What's new in 3.6",
        body=(
            "<p><b>Share notes with anyone</b></p>"
            "<ul>"
            "<li>Click <b>•••</b> → <b>Share</b> to copy a note as text</li>"
            "<li>Send it on Slack, Teams, WhatsApp or email</li>"
            "<li>They click <b>•••</b> → <b>Receive</b> (or the tray menu) "
            "and paste it — same title, text and color</li>"
            "</ul>"
            "<p>Try it on this note. Delete it whenever you like.</p>"
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

    `last_seen` is None for installs that predate version tracking; they're
    treated as older than every entry, so they get the current announcement.
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
