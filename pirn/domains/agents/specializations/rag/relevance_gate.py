"""``RelevanceGate`` — keep retrieved docs above a relevance threshold.

Scores each retrieved entry against the query (a simple
case-insensitive token-overlap ratio is used as the default scorer)
and forwards only the entries whose score meets ``threshold``. Returns
an empty list when nothing clears the bar so downstream knots can
trigger a fallback path.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


def _default_scorer(query: str, doc: Mapping[str, Any]) -> float:
    query_tokens = {tok for tok in query.lower().split() if tok}
    if not query_tokens:
        return 0.0
    doc_text_parts: list[str] = []
    for value in doc.values():
        if isinstance(value, str):
            doc_text_parts.append(value)
        else:
            doc_text_parts.append(str(value))
    doc_tokens = {
        tok for part in doc_text_parts for tok in part.lower().split() if tok
    }
    if not doc_tokens:
        return 0.0
    overlap = query_tokens & doc_tokens
    return len(overlap) / len(query_tokens)


class RelevanceGate(Knot):
    """Filter retrieved docs by a relevance score against the query."""

    def __init__(
        self,
        *,
        query: Knot | str,
        retrieved: Knot,
        _config: KnotConfig,
        threshold: float = 0.5,
        scorer: Callable[[str, Mapping[str, Any]], float] | None = None,
        **kwargs: Any,
    ) -> None:
        if not isinstance(threshold, (int, float)):
            raise TypeError(
                "RelevanceGate: threshold must be a number, "
                f"got {type(threshold).__name__}"
            )
        if not 0.0 <= float(threshold) <= 1.0:
            raise ValueError(
                "RelevanceGate: threshold must be in [0.0, 1.0], "
                f"got {threshold!r}"
            )
        if scorer is not None and not callable(scorer):
            raise TypeError(
                "RelevanceGate: scorer must be callable or None, "
                f"got {type(scorer).__name__}"
            )
        self._scorer = scorer or _default_scorer
        super().__init__(
            query=query,
            retrieved=retrieved,
            threshold=float(threshold),
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        retrieved: list[Mapping[str, Any]],
        threshold: float,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        if not isinstance(query, str):
            raise TypeError(
                "RelevanceGate: query must be a string, "
                f"got {type(query).__name__}"
            )
        kept: list[Mapping[str, Any]] = []
        for index, doc in enumerate(retrieved):
            if not isinstance(doc, Mapping):
                raise TypeError(
                    f"RelevanceGate: retrieved[{index}] must be a Mapping, "
                    f"got {type(doc).__name__}"
                )
            if self._scorer(query, doc) >= threshold:
                kept.append(doc)
        return kept
