"""``UnionSubQuestionHits`` — ``Aggregator`` combine target unioning hits."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class UnionSubQuestionHits:
    """``Aggregator`` combine target: union per-sub-question hits, deduplicated."""

    @staticmethod
    def aggregate(
        count: int, **searches: tuple[str, list[Mapping[str, Any]]]
    ) -> list[Mapping[str, Any]]:
        """Union the fan-out's per-sub-question searches in sub-question order.

        Args:
            count: How many ``search_{i}`` parents the aggregator has.
            **searches: Each ``SubQuestionSearch``'s ``(sub_question, hits)``
                pair, keyed ``search_{i}``.

        Returns:
            The deduplicated hits, in first-seen order.
        """
        return UnionSubQuestionHits.combine([searches[f"search_{index}"] for index in range(count)])

    @staticmethod
    def combine(items: list[tuple[str, list[Mapping[str, Any]]]]) -> list[Mapping[str, Any]]:
        """Union ``items`` into a single deduplicated, first-seen-order list.

        Args:
            items: ``(sub_question, hits)`` pairs, one per sub-question, in
                the sub-questions' original order.

        Returns:
            The deduplicated hits, each carrying which sub-question first
            retrieved it.
        """
        merged: dict[str, Mapping[str, Any]] = {}
        for sub_question, hits in items:
            for hit in hits:
                key = UnionSubQuestionHits._doc_key(hit)
                if key not in merged:
                    enriched = dict(hit)
                    enriched.setdefault("sub_question", sub_question)
                    merged[key] = enriched
        return list(merged.values())

    @staticmethod
    def _doc_key(hit: Mapping[str, Any]) -> str:
        """Return a stable identity key for a retrieved hit."""
        identifier = hit.get("id")
        if identifier is not None:
            return str(identifier)
        return repr(sorted((str(k), str(v)) for k, v in hit.items()))
