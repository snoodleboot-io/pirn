"""``MissingCassetteEntryError`` — a replay found no recorded entry for a key."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class MissingCassetteEntryError(PirnError, LookupError):
    """Raised in replay mode when a call's key has no (further) recorded entry.

    Subclasses :class:`~pirn.exceptions.pirn_error.PirnError` in addition to
    ``LookupError`` so every existing ``except LookupError`` handler keeps
    working unchanged, while new code can narrow to ``PirnError``.

    Replay must never silently fall back to a live call: an absent entry means
    the cassette is stale or the run diverged, and the caller is told exactly
    which key/kind was missing so the cassette can be re-recorded.

    Attributes
    ----------
    key:
        The content key that had no recorded output left to serve.
    kind:
        The interaction kind (value) that was being replayed.
    """

    def __init__(self, key: str, kind: str) -> None:
        self.key = key
        self.kind = kind
        super().__init__(
            f"no recorded cassette entry for key {key!r} (kind {kind!r}); "
            "the cassette is missing this interaction — re-record in RECORD mode"
        )
