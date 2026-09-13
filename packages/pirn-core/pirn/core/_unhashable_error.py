"""``_UnhashableError`` — internal sentinel raised by ``_ContentHasher`` to bail on opaque values."""

from __future__ import annotations


class _UnhashableError(Exception):
    """Internal sentinel used by ``_ContentHasher._canonicalise`` to bail on opaque values."""

    sentinel = "unhashable"
