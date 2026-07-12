"""``ContentHashDeduplicator`` — content-address dedup shared by all connectors (F25-S3).

A tiny stateful helper that both source connectors run each fetched object
through before yielding it: it hashes the bytes (SHA-256 by default) and skips
any object whose hash it has already seen, so identical content is never
re-ingested regardless of which key or URL it arrived under.
"""

from __future__ import annotations

import hashlib

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class ContentHashDeduplicator(PirnOpaqueValue):
    """Track seen content hashes and report whether bytes are newly seen."""

    def __init__(self, *, algorithm: str = "sha256") -> None:
        """Initialise an empty deduplicator.

        Args:
            algorithm: A :mod:`hashlib` algorithm name used to hash content.

        Raises:
            ValueError: If ``algorithm`` is not available in :mod:`hashlib`.
        """
        if algorithm not in hashlib.algorithms_available:
            raise ValueError(f"ContentHashDeduplicator: unknown hash algorithm {algorithm!r}")
        self._algorithm = algorithm
        self._seen: set[str] = set()

    def digest(self, data: bytes) -> str:
        """Return the hex digest of ``data`` under the configured algorithm."""
        return hashlib.new(self._algorithm, bytes(data)).hexdigest()

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
