"""``_BackendRerank`` — rank documents with a provider-neutral backend."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.retrieval.rerank.reranker_backend import RerankerBackend


class _BackendRerank(Knot):
    """Rank documents with a provider-neutral :class:`RerankerBackend` in one call."""

    def __init__(
        self,
        *,
        query: Knot | str,
        documents: Knot | list[Mapping[str, Any]],
        reranker: Knot | RerankerBackend,
        top_k: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            documents=documents,
            reranker=reranker,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        documents: list[Mapping[str, Any]],
        reranker: RerankerBackend,
        top_k: int,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Score ``documents`` with ``reranker`` and return the top ``top_k``.

        Args:
            query: The relevance reference query.
            documents: The documents to score and rank.
            reranker: The scoring backend.
            top_k: The maximum number of documents to return.

        Returns:
            Up to ``top_k`` documents ordered by descending backend score.
        """
        scores = await reranker.score(query, documents)
        ranked = sorted(
            zip(scores, range(len(documents)), documents, strict=True),
            key=lambda triple: (triple[0], -triple[1]),
            reverse=True,
        )
        return [doc for _, _, doc in ranked[:top_k]]
