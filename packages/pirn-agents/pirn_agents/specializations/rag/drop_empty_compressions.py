"""``DropEmptyCompressions`` — Reduce ``combine`` target for compression."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class DropEmptyCompressions:
    """Reduce ``combine`` target: drop documents compressed to nothing."""

    @staticmethod
    def combine(items: list[Mapping[str, Any] | None]) -> list[Mapping[str, Any]]:
        """Return ``items`` with every ``None`` (fully-compressed-away document) dropped."""
        return [doc for doc in items if doc is not None]
