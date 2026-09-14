"""``TopKByScore`` — Reduce ``combine`` target picking the top-K documents."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class TopKByScore:
    """Reduce ``combine`` target: pick the top-K ``(score, document)`` pairs."""

    @staticmethod
    def combine(
        items: list[tuple[float, Mapping[str, Any]]], *, top_k: int
    ) -> list[Mapping[str, Any]]:
        """Sort ``items`` by descending score and keep the top ``top_k`` documents.

        Args:
            items: ``(score, document)`` pairs, one per scored document.
            top_k: Maximum number of documents to keep.

        Returns:
            Up to ``top_k`` documents ordered by descending score.
        """
        ranked = sorted(items, key=lambda pair: pair[0], reverse=True)
        return [doc for _, doc in ranked[:top_k]]
