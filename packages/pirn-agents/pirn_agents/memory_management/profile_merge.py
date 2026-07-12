"""Merge new session data into a profile without clobbering unrelated fields.

The S3 merge primitive, kept pure so it is trivially testable and reusable. It
combines an ``existing`` profile-field mapping with ``incoming`` session data:

* keys present only in ``existing`` are preserved untouched (no clobber);
* keys present in ``incoming`` update the profile;
* keys present in both whose *values are themselves mappings* are merged
  recursively, so a nested update (e.g. ``preferences.theme``) does not drop
  sibling nested keys (``preferences.language``).

The inputs are never mutated; a fresh nested ``dict`` is returned.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def merge_profile_fields(
    existing: Mapping[str, Any],
    incoming: Mapping[str, Any],
) -> dict[str, Any]:
    """Return ``existing`` deep-merged with ``incoming`` (incoming wins on scalars).

    Args:
        existing: The current profile fields.
        incoming: The new session data to fold in.

    Returns:
        A new mapping with unrelated existing keys preserved and overlapping
        mapping values merged recursively.

    Raises:
        TypeError: If either argument is not a mapping.
    """
    if not isinstance(existing, Mapping):
        raise TypeError(
            f"merge_profile_fields: existing must be a Mapping, got {type(existing).__name__}"
        )
    if not isinstance(incoming, Mapping):
        raise TypeError(
            f"merge_profile_fields: incoming must be a Mapping, got {type(incoming).__name__}"
        )
    merged: dict[str, Any] = dict(existing)
    for key, incoming_value in incoming.items():
        current = merged.get(key)
        if isinstance(current, Mapping) and isinstance(incoming_value, Mapping):
            merged[key] = merge_profile_fields(current, incoming_value)
        else:
            merged[key] = incoming_value
    return merged
