"""Metadata-filter matching shared by in-memory and adapter query paths.

A metadata filter is a mapping of ``field -> expected``. A record matches when,
for every entry, its metadata satisfies the predicate:

* a scalar ``expected`` matches by equality;
* a list/tuple/set ``expected`` matches by membership (``field in expected``).

This is the neutral semantics the numpy in-memory store applies directly and
that external adapters translate into their backend's native filter language.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def matches_metadata_filter(
    metadata: Mapping[str, Any], metadata_filter: Mapping[str, Any] | None
) -> bool:
    """Return whether ``metadata`` satisfies every entry of ``metadata_filter``.

    Args:
        metadata: The record's metadata mapping.
        metadata_filter: The filter mapping, or ``None`` for "match everything".

    Returns:
        ``True`` if the filter is ``None``/empty or every predicate holds.
    """
    if not metadata_filter:
        return True
    for key, expected in metadata_filter.items():
        actual = metadata.get(key)
        if isinstance(expected, list | tuple | set):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True
