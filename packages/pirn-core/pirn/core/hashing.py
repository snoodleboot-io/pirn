"""Content-addressed hashing of values.

Thin alias module kept for external callers; the actual canonicalisation
logic and the ``TypeAdapter`` cache live on
:class:`pirn.core._content_hasher._ContentHasher`.

``content_hash(value, *, strict=False)`` returns a stable hex sha256 of
``value`` suitable for lineage joins. With ``strict=True`` it raises
:class:`~pirn.exceptions.unhashable_value_error.UnhashableValueError`
(naming the innermost value that defeated canonicalisation) instead of
returning a ``sha256:unhashable:<type>`` sentinel for a value with no
canonical form (no ``__pirn_canonical__`` hook, no pydantic core schema, not
a recognised container).
"""

from __future__ import annotations

from pirn.core._content_hasher import _ContentHasher

#: Public name for :meth:`_ContentHasher.hash` (bare alias, not a ``def``).
content_hash = _ContentHasher.hash
