"""Content-addressed hashing of values.

Thin wrapper module kept for external callers; delegates to
:class:`pirn.core._content_hasher._ContentHasher`, which holds the actual
canonicalisation logic and the ``TypeAdapter`` cache — mirrors the
``CycleDetector`` / ``detect_cycle`` split in
:mod:`pirn.engine.shed.shed`.
"""

from __future__ import annotations

from typing import Any

from pirn.core._content_hasher import _ContentHasher


def content_hash(value: Any, *, strict: bool = False) -> str:
    """Return a stable hex sha256 of ``value`` suitable for lineage joins.

    Thin wrapper kept for external callers; delegates to
    ``_ContentHasher.hash``.

    Args:
        value: The value to hash.
        strict: When ``True``, raise
            :class:`~pirn.exceptions.unhashable_value_error.UnhashableValueError`
            (naming the innermost value that defeated canonicalisation)
            instead of returning a ``sha256:unhashable:<type>`` sentinel for
            a value with no canonical form. Defaults to ``False``.

    Raises:
        UnhashableValueError: If ``strict`` is ``True`` and ``value``
            contains a leaf with no canonical form (no ``__pirn_canonical__``
            hook, no pydantic core schema, not a recognised container).
    """
    return _ContentHasher.hash(value, strict=strict)
