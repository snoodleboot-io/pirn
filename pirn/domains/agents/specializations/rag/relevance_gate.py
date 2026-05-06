"""``RelevanceCheck`` — keep retrieved docs above a relevance threshold.

Scores each retrieved entry against the query (a simple
case-insensitive token-overlap ratio is used as the default scorer)
and forwards only the entries whose score meets ``threshold``. Returns
an empty list when nothing clears the bar so downstream knots can
trigger a fallback path.

Algorithm:
    1. Receive ``query`` string, ``retrieved`` list of Mappings, and
       ``threshold`` float in [0.0, 1.0].
    2. Validate that ``query`` is a string.
    3. For each document, validate it is a Mapping then call the scorer.
       Default scorer: token-overlap ratio =
       |query_tokens ∩ doc_tokens| / |query_tokens|.
    4. Keep only documents whose score >= ``threshold``.
    5. Return the filtered list (may be empty).

Math:
    Default token-overlap score for a document *d* against query *q*:

    .. math::

        s(q, d) = \\frac{|T(q) \\cap T(d)|}{|T(q)|}

    where :math:`T(x)` is the set of lowercase whitespace-split tokens
    of string *x*, and :math:`s = 0` when :math:`T(q) = \\emptyset`.

References:
    - Token-overlap as a lightweight relevance proxy is described in
      Manning et al., "Introduction to Information Retrieval", Ch. 1:
      https://nlp.stanford.edu/IR-book/
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class RelevanceCheck(Knot):
    """Filter retrieved docs by a relevance score against the query."""

    def __init__(
        self,
        *,
        query: Knot | str,
        retrieved: Knot,
        _config: KnotConfig,
        threshold: Knot | float = 0.5,
        scorer: Knot | Callable[[str, Mapping[str, Any]], float] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            retrieved=retrieved,
            threshold=threshold,
            scorer=scorer,
            _config=_config,
            **kwargs,
        )

    @staticmethod
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

    async def process(
        self,
        query: str,
        retrieved: list[Mapping[str, Any]],
        threshold: float,
        scorer: Callable[[str, Mapping[str, Any]], float] | None = None,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Score each retrieved doc against the query and return only those meeting the threshold.

        Args:
            query: The query string used as the reference for scoring each document.
            retrieved: The list of candidate document Mappings to score and filter.
            threshold: The minimum score a document must achieve to be kept.
            scorer: Optional callable scorer; defaults to token-overlap ratio.

        Returns:
            A list of documents whose relevance score is at or above the threshold.

        Raises:
            TypeError: If query is not a string, threshold is not a number,
                scorer is not callable or None, or any retrieved element is not a Mapping.
            ValueError: If threshold is outside [0.0, 1.0].
        """
        if not isinstance(query, str):
            raise TypeError(
                "RelevanceCheck: query must be a string, "
                f"got {type(query).__name__}"
            )
        if not isinstance(threshold, (int, float)):
            raise TypeError(
                "RelevanceCheck: threshold must be a number, "
                f"got {type(threshold).__name__}"
            )
        if not 0.0 <= float(threshold) <= 1.0:
            raise ValueError(
                "RelevanceCheck: threshold must be in [0.0, 1.0], "
                f"got {threshold!r}"
            )
        if scorer is not None and not callable(scorer):
            raise TypeError(
                "RelevanceCheck: scorer must be callable or None, "
                f"got {type(scorer).__name__}"
            )
        active_scorer = scorer if scorer is not None else RelevanceCheck._default_scorer
        kept: list[Mapping[str, Any]] = []
        for index, doc in enumerate(retrieved):
            if not isinstance(doc, Mapping):
                raise TypeError(
                    f"RelevanceCheck: retrieved[{index}] must be a Mapping, "
                    f"got {type(doc).__name__}"
                )
            if active_scorer(query, doc) >= threshold:
                kept.append(doc)
        return kept
