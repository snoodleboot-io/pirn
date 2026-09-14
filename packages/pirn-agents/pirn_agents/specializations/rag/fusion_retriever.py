# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style
"""``FusionRetriever`` — concurrent multi-query retrieval fused with RRF.

The retrieval stage of RAG-Fusion. Given a list of query variants, it searches
the :class:`MemoryStore` for each variant **concurrently**, builds one ranked
id list per variant, and fuses them with Reciprocal Rank Fusion. Documents are
de-duplicated by identity and returned in fused-score order, each carrying its
``fusion_score``.

The fan-out is expressed as a graph rather than a hand-rolled
``asyncio.gather`` over a semaphore: each query variant becomes its own
:class:`~pirn_agents.specializations.rag.variant_search.VariantSearch`
invocation, fanned out with a core :class:`~pirn.nodes.map_markers.Map`, and
folded into the fused ranking with a :class:`~pirn.nodes.reduce_.Reduce`. The
engine schedules the per-variant searches concurrently — every ready sibling
starts as its own task (PIR-841) — so retrieval runs *through* the engine,
with its own ``Result``, history record, and lineage per variant. Each search
knot carries a ``concurrency_group`` so a run-level
:class:`~pirn.core.concurrency.concurrency_limits.ConcurrencyLimits` can bound
in-flight searches; ``max_concurrency`` stays a validated, accepted parameter
recorded on that group (bounding a *container* knot's own inner run this way
is not yet enforced by core — see ``ConcurrencyLimits`` PIR-841 slice 2/3 —
so, until that lands, ``max_concurrency`` documents the intended budget rather
than strictly capping it).

Algorithm:
    1. Validate ``queries`` (list of str), ``store`` (:class:`MemoryStore`),
       ``top_k``, ``max_concurrency``, and ``rrf_k`` (positive ints).
    2. Fan out one ``VariantSearch`` invocation per query variant.
    3. A :class:`~pirn.nodes.reduce_.Reduce` keys each hit by its ``id`` (or a
       stable fallback), records the first-seen mapping, builds per-query
       ranked key lists, and fuses them via
       :meth:`~pirn_agents.retrieval.reciprocal_rank_fusion.ReciprocalRankFusion.fuse`.
    4. Return the top ``top_k`` fused documents, each with a ``fusion_score``.

Math:
    Reciprocal Rank Fusion score for document :math:`d` across query variants
    :math:`Q`, with :math:`\\text{rank}_q(d)` the 1-indexed rank of :math:`d`
    in variant :math:`q`'s ranking (or omitted if unranked):

    $$
    \\text{RRF}(d) = \\sum_{q \\in Q} \\frac{1}{k + \\text{rank}_q(d)}
    $$

References:
    - Cormack, Clarke & Buettcher, "Reciprocal Rank Fusion" (SIGIR 2009).
"""

from __future__ import annotations

import functools
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.map_markers import Map
from pirn.nodes.reduce_ import Reduce

from pirn_agents.interfaces.retriever import Retriever
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.rag.fuse_variant_hits import FuseVariantHits
from pirn_agents.specializations.rag.variant_search import VariantSearch


class FusionRetriever(AgentPipeline, Retriever):
    """Search each query variant concurrently and fuse the rankings with RRF."""

    def __init__(
        self,
        *,
        queries: Knot | list[str],
        store: Knot | MemoryStore,
        _config: KnotConfig,
        top_k: Knot | int = 5,
        max_concurrency: Knot | int = 4,
        rrf_k: Knot | int = 60,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            queries=queries,
            store=store,
            top_k=top_k,
            max_concurrency=max_concurrency,
            rrf_k=rrf_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        queries: list[str],
        store: MemoryStore,
        top_k: int = 5,
        max_concurrency: int = 4,
        rrf_k: int = 60,
        **_: Any,
    ) -> Knot:
        """Build the per-variant search graph and return its RRF-fusing sink knot.

        Args:
            queries: The query variants to search for.
            store: The memory store searched once per variant.
            top_k: Number of fused documents to return.
            max_concurrency: Intended in-flight search budget (see module
                docstring for the current enforcement caveat).
            rrf_k: The RRF damping constant.

        Returns:
            The sink knot whose output is up to ``top_k`` document mappings
            ordered by fused score, each with a ``fusion_score`` key.

        Raises:
            TypeError: If ``store`` is not a MemoryStore or ``queries`` is not a list.
            ValueError: If ``top_k``/``max_concurrency``/``rrf_k`` are not positive ints.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"FusionRetriever: store must be a MemoryStore, got {type(store).__name__}"
            )
        if not isinstance(queries, list):
            raise TypeError(
                f"FusionRetriever: queries must be a list, got {type(queries).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"FusionRetriever: top_k must be a positive int, got {top_k!r}")
        if not isinstance(max_concurrency, int) or max_concurrency <= 0:
            raise ValueError(
                f"FusionRetriever: max_concurrency must be a positive int, got {max_concurrency!r}"
            )
        if not isinstance(rrf_k, int) or rrf_k <= 0:
            raise ValueError(f"FusionRetriever: rrf_k must be a positive int, got {rrf_k!r}")
        if not queries:
            return Parameter("empty", list[Any], default=[], _config=KnotConfig(id="empty"))

        fetch = top_k * 2
        queries_knot = Parameter(
            "queries", list[str], default=queries, _config=KnotConfig(id="queries")
        )
        searched = VariantSearch(
            query=Map(queries_knot),
            store=store,
            top_k=fetch,
            _config=KnotConfig(id="search_each", concurrency_group="fusion_retriever_search"),
        )
        return Reduce(
            of=searched,
            combine=functools.partial(FuseVariantHits.combine, rrf_k=rrf_k, top_k=top_k),
            _config=KnotConfig(id="fuse"),
        )
