"""``RerankerBackend`` — the provider-neutral reranking-score protocol.

A reranker backend scores how relevant each candidate document is to a query.
The RAG :class:`pirn_agents.specializations.rag.reranker.Reranker` knot depends
on this protocol rather than on any concrete model, so a cross-encoder, an
LLM-based scorer, or a test stub are all interchangeable. It is
:func:`~typing.runtime_checkable` so the knot can ``isinstance``-validate an
injected backend.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RerankerBackend(Protocol):
    """A relevance scorer over ``(query, documents)``."""

    async def score(self, query: str, documents: Sequence[Mapping[str, Any]]) -> list[float]:
        """Return one relevance score per document, in input order.

        Args:
            query: The query the documents are scored against.
            documents: The candidate documents to score.

        Returns:
            One float score per document, aligned with ``documents``; a larger
            score means more relevant.
        """
        ...
