"""``MissingCassetteEntryError`` — a replay found no recorded entry for a key."""

from __future__ import annotations


class MissingCassetteEntryError(LookupError):
    """Raised in replay mode when a call's key has no (further) recorded entry.

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
