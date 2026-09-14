"""``content_digest`` — a stable content hash for record/replay keying.

The cassette keys every LLM/tool/retrieval I/O by a digest of the *request*
payload, mirroring the content-addressed DAG: identical requests collapse to
the same key, and any change to the payload yields a different one.
Time-travel diffing reuses the same digest to detect changed inputs/outputs
between two runs.

The canonicalisation is core's own :meth:`pirn.core.content_hasher.ContentHasher.hash` in
``strict`` mode — the one hashing path every pirn domain agrees on. A leaf
with no canonical form (no ``__pirn_canonical__``, no pydantic core schema,
not a recognised container) raises
:class:`~pirn.exceptions.unhashable_value_error.UnhashableValueError` (a
``TypeError``) at record time rather than keying on a memory address that
could never replay (PIR-785).
"""

from __future__ import annotations

from typing import Any

from pirn.core.content_hasher import ContentHasher


class ContentDigest:
    """Namespace for the stable record/replay content-digest primitive."""

    @staticmethod
    def digest(payload: Any) -> str:
        """Return the ``sha256:``-prefixed content hash of ``payload``.

        Args:
            payload: Any value core's content hasher can canonicalise. Mapping
                keys are sorted, so the digest is independent of key order.

        Returns:
            ``ContentHasher.hash(payload, strict=True)``.

        Raises:
            UnhashableValueError: If ``payload`` contains a leaf with no
                canonical form.
        """
        return ContentHasher.hash(payload, strict=True)
