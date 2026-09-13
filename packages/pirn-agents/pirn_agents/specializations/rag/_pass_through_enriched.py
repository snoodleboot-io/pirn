"""``_PassThroughEnriched`` — Reduce ``combine`` target for enriched chunks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class _PassThroughEnriched:
    """Reduce ``combine`` target: surface the enriched documents unchanged."""

    @staticmethod
    def combine(items: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        """Return ``items`` as a plain list, preserving Map's input order."""
        return list(items)
