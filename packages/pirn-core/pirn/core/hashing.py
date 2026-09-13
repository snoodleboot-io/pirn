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


def content_hash(value: Any) -> str:
    """Return a stable hex sha256 of ``value`` suitable for lineage joins.

    Thin wrapper kept for external callers; delegates to
    ``_ContentHasher.hash``.
    """
    return _ContentHasher.hash(value)
