"""``_CombineExpansions`` — Reduce ``combine`` target folding thoughts."""

from __future__ import annotations


class _CombineExpansions:
    """Reduce ``combine`` target: fold each thought into a new candidate path."""

    @staticmethod
    def combine(items: list[tuple[str, str]]) -> list[tuple[str, float]]:
        """Join each ``(parent_path, thought)`` pair into a scored-0.0 candidate."""
        return [(f"{parent_path}\n{thought}", 0.0) for parent_path, thought in items]
