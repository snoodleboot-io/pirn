"""``RerankerBackend`` — the provider-neutral reranking-score base class.

A reranker backend scores how relevant each candidate document is to a query.
The RAG :class:`pirn_agents.specializations.rag.reranker.Reranker` knot depends
on this base rather than on any concrete model, so a cross-encoder, an LLM-based
scorer, or a test stub are all interchangeable.

The base raises :class:`NotImplementedError` for :meth:`score` (the house
interface style — never :class:`typing.Protocol`) and is opaque
(:class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`) because a concrete
backend holds live model state: it drops into the pirn graph as a config value
by ``isinstance`` — the very check the knot uses to validate an injected
backend — without descending into the content-addressed hash. Model on the
sibling :class:`~pirn.core.providers.llm_provider.LLMProvider`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class RerankerBackend(PirnOpaqueValue):
    """Abstract relevance scorer over ``(query, documents)``."""

    async def score(self, query: str, documents: Sequence[Mapping[str, Any]]) -> list[float]:
        """Return one relevance score per document, in input order.

        Args:
            query: The query the documents are scored against.
            documents: The candidate documents to score.

        Returns:
            One float score per document, aligned with ``documents``; a larger
            score means more relevant.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement score()")
