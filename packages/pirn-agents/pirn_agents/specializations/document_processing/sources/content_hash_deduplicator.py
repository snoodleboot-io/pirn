"""``ContentHashDeduplicator`` — content-address dedup shared by all connectors (F25-S3).

A tiny stateful helper that both source connectors run each fetched object
through before yielding it: it hashes the bytes through core's
:meth:`~pirn.core.content_hasher.ContentHasher.hash` and skips any object whose
hash it has already seen, so identical content is never re-ingested regardless of
which key or URL it arrived under.

The digest is core's, not a private ``hashlib`` call: one definition of content
identity across the workspace, so a dedup key and a lineage key for the same
bytes agree (PIR-874). The configurable ``algorithm`` argument is gone with it —
nothing passed anything but the default, and a per-instance algorithm is exactly
the second definition this removes.
"""

from __future__ import annotations

from pirn.core.content_hasher import ContentHasher
from pirn.core.pirn_opaque_value import PirnOpaqueValue


class ContentHashDeduplicator(PirnOpaqueValue):
    """Track seen content hashes and report whether bytes are newly seen."""

    def __init__(self) -> None:
        """Initialise an empty deduplicator."""
        self._seen: set[str] = set()

    @staticmethod
    def digest(data: bytes) -> str:
        """Return core's content hash of ``data``."""
        return ContentHasher.hash(bytes(data))

    def is_new(self, data: bytes) -> bool:
        """Return whether ``data`` is unseen, recording its hash when it is.

        Args:
            data: The content bytes to check.

        Returns:
            ``True`` the first time this content is seen (and records it);
            ``False`` on every subsequent identical content.
        """
        content_hash = self.digest(data)
        if content_hash in self._seen:
            return False
        self._seen.add(content_hash)
        return True

    @property
    def seen_count(self) -> int:
        """Return the number of distinct content hashes recorded so far."""
        return len(self._seen)
