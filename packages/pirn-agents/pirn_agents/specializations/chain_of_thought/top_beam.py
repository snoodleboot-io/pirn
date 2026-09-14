"""``TopBeam`` — Reduce ``combine`` target keeping the top-scoring beam."""

from __future__ import annotations


class TopBeam:
    """Reduce ``combine`` target: keep the top-``beam_width`` scoring candidates."""

    @staticmethod
    def combine(items: list[tuple[str, float]], *, beam_width: int) -> list[tuple[str, float]]:
        """Sort ``items`` by descending score and keep the top ``beam_width``."""
        return sorted(items, key=lambda pair: pair[1], reverse=True)[:beam_width]
