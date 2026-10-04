# stickynotes/sharing.py
#
# Share / Receive: a whole note as one pasteable piece of text.
#
#   Sticky Note: Groceries (paste into Sticky Notes → Receive)
#   SN1:eJyNVE1v2zAM/StEDsFxQgEbMAzsuA7Yo2EbsF4Gmab2Vt1y5F9e3Q9rk…
#
# The first line is for humans who don't have the app. The token is
# "SN<format version>:" + base64(zlib(JSON)). It is ENCODED, not encrypted —
# anyone holding the text can read the note, and the UI says so.
#
# Design notes:
#   * Standard base64, not the URL-safe alphabet: "_" would be eaten by
#     Slack/WhatsApp italics. "+/=" pass through chat apps untouched.
#   * zlib carries an Adler-32 checksum, so a truncated or altered copy fails
#     to decode instead of producing a garbled note.
#   * Only content travels: title, colour, body. Never the note id (the
#     receiver always gets a fresh one, so receiving your own note can't
#     overwrite it), position, size, pin or collapse state.
#   * Received text is untrusted: decompression is size-capped and the body
#     goes through richtext.sanitized_html, the same rules as a paste.
#   * FORMAT_VERSION lets a future format (e.g. password-protected) ship
#     without breaking old strings; older apps reject newer ones by name.

import base64
import binascii
import json
import re
import zlib
from dataclasses import dataclass
from typing import Optional

from . import config
from .richtext import sanitized_html

FORMAT_VERSION = 1

# Upper bound on the decompressed payload. A typical note is a few KB; this
# only exists so a crafted string can't decompress into gigabytes.
MAX_PAYLOAD_BYTES = 1_000_000

# The token may be split across lines by email clients that hard-wrap, so
# whitespace is allowed inside it; _candidates() works out where it ends.
_TOKEN_RE = re.compile(r"SN(\d+):([A-Za-z0-9+/=\s]+)")

# User-facing messages, shown as-is by the Receive dialog.
MSG_NOT_A_SHARE = "This doesn't look like a shared note."
MSG_DAMAGED = "This shared note is incomplete or damaged. Ask for it again."
MSG_NEWER = "Made with a newer version of Sticky Notes. Please update."
MSG_TOO_BIG = "This shared note is too large to open."


class ShareError(ValueError):
    """Decoding failed. str(error) is a message fit to show the user."""


class _Damaged(Exception):
    """Internal: this candidate span didn't decode; try a shorter one."""


@dataclass(frozen=True)
class SharedNote:
    title: Optional[str]   # None = still on the auto-title from the first line
    theme: str
    body_html: str


def encode_note(title: str, title_is_auto: bool, theme: str, body_html: str) -> str:
    """The text Share puts on the clipboard."""
    payload = {
        "title": title,
        "auto_title": bool(title_is_auto),
        "theme": theme,
        "body": body_html,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    code = base64.b64encode(zlib.compress(raw.encode("utf-8"), 9)).decode("ascii")
    return (
        f"Sticky Note: {title} (paste into Sticky Notes → Receive)\n"
        f"SN{FORMAT_VERSION}:{code}"
    )


def decode_note(text: str) -> SharedNote:
    """Parse text pasted into Receive. Raises ShareError with a user message.

    The token can sit anywhere in `text` — the human header line, a chat
    client's "Forwarded message" preamble or a trailing "thanks!" are all
    ignored.
    """
    match = _TOKEN_RE.search(text or "")
    if match is None:
        raise ShareError(MSG_NOT_A_SHARE)
    if int(match.group(1)) > FORMAT_VERSION:
        raise ShareError(MSG_NEWER)

    for code in _candidates(match.group(2)):
        try:
            return _parse(code)
        except _Damaged:
            continue
    raise ShareError(MSG_DAMAGED)


def _candidates(span: str):
    """Possible token extents, longest first.

    Whitespace is allowed inside the token (hard-wrapped email), but that means
    a following line made only of base64-safe characters ("Thanks") gets
    swallowed too. Dropping trailing whitespace-separated chunks one at a time
    finds the real end; the zlib checksum rejects every wrong guess.
    """
    chunks = span.split()
    for end in range(len(chunks), 0, -1):
        yield "".join(chunks[:end])


def _parse(code: str) -> SharedNote:
    try:
        compressed = base64.b64decode(code, validate=True)
    except (binascii.Error, ValueError):
        raise _Damaged()

    inflater = zlib.decompressobj()
    try:
        raw = inflater.decompress(compressed, MAX_PAYLOAD_BYTES)
    except zlib.error:
        raise _Damaged()
    if inflater.unconsumed_tail:
        raise ShareError(MSG_TOO_BIG)
    if not inflater.eof:
        raise _Damaged()   # truncated: the stream never reached its end

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise _Damaged()
    if not isinstance(payload, dict):
        raise _Damaged()

    title = payload.get("title")
    theme = payload.get("theme")
    body = payload.get("body")
    auto_title = payload.get("auto_title", False)
    if not (isinstance(title, str) and isinstance(theme, str)
            and isinstance(body, str) and isinstance(auto_title, bool)):
        raise _Damaged()

    title = title.strip()[:config.MAX_TITLE_LENGTH]
    return SharedNote(
        title=None if (auto_title or not title) else title,
        # Unknown colour (e.g. renamed in a later redesign) -> default theme.
        theme=theme if theme in config.THEMES else config.DEFAULT_THEME,
        body_html=sanitized_html(body),
    )
