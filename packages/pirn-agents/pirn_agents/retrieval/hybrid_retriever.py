"""``HybridRetriever`` — concurrent dense + lexical retrieval fused with RRF.

A :class:`~pirn.nodes.sub_tapestry.SubTapestry` that retrieves from a dense
:class:`~pirn_agents.retrieval.vector_stores.vector_memory_store.VectorMemoryStore` and a
lexical :class:`~pirn_agents.retrieval.bm25_index.Bm25Index` **concurrently**,
then fuses the two rankings with Reciprocal Rank Fusion. Each arm is its own
knot (:class:`~pirn_agents.retrieval._dense_ids._DenseIds`,
:class:`~pirn_agents.retrieval._lexical_ids._LexicalIds`) wired into an
:class:`~pirn.nodes.aggregator.Aggregator`, so the engine schedules both arms
concurrently instead of a hand-rolled ``asyncio.gather`` (PIR-867) — dense
retrieval is async I/O and BM25 scoring is CPU-bound, so the lexical arm still
offloads to a worker thread internally, exactly as before.

Algorithm:
    1. Validate ``lexical``, ``top_k``, and ``candidate_multiplier``.
    2. Wire a ``_DenseIds`` knot (embeds ``query`` and queries the dense
       store) and a ``_LexicalIds`` knot (BM25 search on a worker thread) as
       the parents of an ``Aggregator``.
    3. The combine fuses the two ranked id lists with
       :func:`~pirn_agents.retrieval.reciprocal_rank_fusion.reciprocal_rank_fusion`.
    4. Return the top ``top_k`` fused hits as ``{"id", "score"}`` mappings.

Math:
    The fusion score itself is computed by
    :func:`~pirn_agents.retrieval.reciprocal_rank_fusion.reciprocal_rank_fusion`
    (see that module for the full derivation); in short, for a document ``d``
    appearing at rank :math:`r_i(d)` in ranking :math:`i` (dense or lexical):

    $$
    \\text{score}(d) = \\sum_i \\frac{1}{k + r_i(d)}
    $$

    where :math:`k` is ``rrf_k`` (default ``60``, the value used in the original
    RRF paper) and a document absent from a ranking contributes ``0`` for that
    ranking.
"""

from __future__ import annotations

import functools
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.retrieval._dense_ids import _DenseIds
from pirn_agents.retrieval._lexical_ids import _LexicalIds
from pirn_agents.retrieval.bm25_index import Bm25Index
from pirn_agents.retrieval.embeddings.embedding_provider import EmbeddingProvider
from pirn_agents.retrieval.hybrid_retriever_base import HybridRetrieverBase
from pirn_agents.retrieval.reciprocal_rank_fusion import reciprocal_rank_fusion
from pirn_agents.retrieval.vector_stores.vector_memory_store import VectorMemoryStore


class HybridRetriever(SubTapestry, HybridRetrieverBase):
    """Fuse dense and lexical retrieval concurrently via Reciprocal Rank Fusion."""

    def __init__(
        self,
        *,
        query: Knot | str,
        store: Knot | VectorMemoryStore,
        lexical: Knot | Any,
        embedder: Knot | EmbeddingProvider,
        _config: KnotConfig,
        top_k: Knot | int = 5,
        candidate_multiplier: Knot | int = 4,
        rrf_k: Knot | int = 60,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            store=store,
            lexical=lexical,
            embedder=embedder,
            top_k=top_k,
            candidate_multiplier=candidate_multiplier,
            rrf_k=rrf_k,
            _config=_config,
            **kwargs,
        )

    # HybridRetrieverBase.process() is annotated -> list[Mapping[str, Any]] (the
    # retriever family's umbrella contract); SubTapestry.process() is -> Knot.
    # This concrete is a SubTapestry now, so its true contract is -> Knot, same
    # shape mismatch Gate.process() carries against Knot.process() and silences
    # the same way.
    async def process(  # type: ignore[override]
        self,
        query: str,
        store: VectorMemoryStore,
        lexical: Any,
        embedder: EmbeddingProvider,
        top_k: int = 5,
        candidate_multiplier: int = 4,
        rrf_k: int = 60,
        **_: Any,
    ) -> Knot:
        """Wire the dense and lexical arms and return the fusing sink knot.

        Args:
            query: The user query string.
            store: The dense vector store to query.
            lexical: The BM25 lexical index to search.
            embedder: The provider used to embed the query for dense retrieval.
            top_k: Number of fused hits to return.
            candidate_multiplier: Over-fetch factor per arm before fusion, so
                fusion sees more than ``top_k`` from each retriever.
            rrf_k: The RRF damping constant.

        Returns:
            The sink of the inner pipeline: an :class:`Aggregator` over the
            dense and lexical arms, whose output is up to ``top_k``
            ``{"id", "score"}`` mappings ordered by fused score.

        Raises:
            TypeError: If ``lexical`` is not a :class:`Bm25Index`.
            ValueError: If ``top_k`` or ``candidate_multiplier`` is not a
                positive integer.
        """
        if not isinstance(lexical, Bm25Index):
            raise TypeError(
                f"HybridRetriever: lexical must be a Bm25Index, got {type(lexical).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"HybridRetriever: top_k must be a positive int, got {top_k!r}")
        if not isinstance(candidate_multiplier, int) or candidate_multiplier <= 0:
            raise ValueError(
                f"HybridRetriever: candidate_multiplier must be a positive int, "
                f"got {candidate_multiplier!r}"
            )
        fetch = top_k * candidate_multiplier
        dense = _DenseIds(
            store=store, embedder=embedder, query=query, fetch=fetch, _config=KnotConfig(id="dense")
        )
        lexical_ids = _LexicalIds(
            lexical=lexical, query=query, fetch=fetch, _config=KnotConfig(id="lexical")
        )
        return Aggregator(
            combine=functools.partial(self._fuse, top_k=top_k, rrf_k=rrf_k),
            dense=dense,
            lexical=lexical_ids,
            _config=KnotConfig(id="fuse"),
        )

    @staticmethod
    def _fuse(
        *, dense: list[str], lexical: list[str], top_k: int, rrf_k: int
    ) -> list[Mapping[str, Any]]:
        """Fuse the dense and lexical rankings and return the top ``top_k`` hits."""
        fused = reciprocal_rank_fusion([dense, lexical], k=rrf_k)
        return [{"id": identifier, "score": score} for identifier, score in fused[:top_k]]
