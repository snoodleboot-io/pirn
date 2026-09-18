"""``FusionRetriever`` — concurrent multi-query retrieval fused with RRF.

The retrieval stage of RAG-Fusion. Given a list of query variants, it searches
the :class:`MemoryStore` for each variant **concurrently**, builds one ranked
id list per variant, and fuses them with Reciprocal Rank Fusion. Documents are
de-duplicated by identity and returned in fused-score order, each carrying its
``fusion_score``.

The fan-out is expressed as a graph rather than a hand-rolled
``asyncio.gather`` over a semaphore: one
:class:`~pirn_agents.specializations.rag.variant_search.VariantSearch` knot
per query variant, wired into an :class:`~pirn.nodes.aggregator.Aggregator`
that fuses their rankings. The engine schedules ready siblings concurrently
(PIR-841), so every variant's search gets its own ``Result``, history record,
lineage row and admission slot.

Every search knot carries the same ``concurrency_group`` and
``max_concurrency`` is that group's cap: ``process()`` declares it through
:class:`~pirn_agents.specializations.base.inner_group_limit.InnerGroupLimit`
and ``_inner_concurrency()`` hands it to the inner run, the lever
:class:`~pirn_agents.batch.map_agent.MapAgent` and
:class:`~pirn_agents.specializations.document_processing.ingestion_runner.IngestionRunner`
use. Until PIR-873 the fan-out was a single knot with a core
:class:`~pirn.core.map.Map` marker, whose per-element invocations are one
``asyncio.gather`` *inside* that knot: they shared one lineage row and one
admission slot, so the group cap could not bound them and
``max_concurrency`` was validated and then discarded behind a docstring
claiming core could not enforce it.

Algorithm:
    1. Validate ``queries`` (list of str), ``store`` (:class:`MemoryStore`),
       ``top_k``, ``max_concurrency``, and ``rrf_k`` (positive ints).
    2. Declare the search group's cap from ``max_concurrency``.
    3. Build one ``VariantSearch`` knot per query variant, all in that group.
    4. An :class:`~pirn.nodes.aggregator.Aggregator` keys each hit by its ``id``
       (or a stable fallback), records the first-seen mapping, builds per-query
       ranked key lists, and fuses them via
       :meth:`~pirn_agents.retrieval.reciprocal_rank_fusion.ReciprocalRankFusion.fuse`.
    5. Return the top ``top_k`` fused documents, each with a ``fusion_score``.

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
from typing import Any, ClassVar

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator

from pirn_agents.interfaces.retriever import Retriever
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.base.inner_group_limit import InnerGroupLimit
from pirn_agents.specializations.rag.fuse_variant_hits import FuseVariantHits
from pirn_agents.specializations.rag.variant_search import VariantSearch


class FusionRetriever(AgentPipeline, Retriever):
    """Search each query variant concurrently and fuse the rankings with RRF."""

    #: Per-run carrier for the search group's cap (never instance state).
    _group_limit: ClassVar[InnerGroupLimit] = InnerGroupLimit("fusion_retriever_search")

    def _inner_concurrency(self) -> ConcurrencyLimits | None:
        """This run's search-group cap, or ``None`` when no search runs.

        Read by ``SubTapestry._run_inner`` after ``process()`` has declared it;
        the cap rides the run's own context, never this shared knot.
        """
        return type(self)._group_limit.current()

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
            max_concurrency: Maximum searches in flight at once; the cap on
                the searches' concurrency group.
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
        type(self)._group_limit.declare(members=len(queries), max_concurrency=max_concurrency)
        if not queries:
            return Parameter("empty", list[Any], default=[], _config=KnotConfig(id="empty"))

        fetch = top_k * 2
        searches: dict[str, Knot] = {
            f"search_{index}": VariantSearch(
                query=query,
                store=store,
                top_k=fetch,
                _config=KnotConfig(
                    id=f"search_{index}",
                    concurrency_group=type(self)._group_limit.group,
                ),
            )
            for index, query in enumerate(queries)
        }
        return Aggregator(
            combine=functools.partial(FuseVariantHits.aggregate, len(queries), rrf_k, top_k),
            _config=KnotConfig(id="fuse"),
            **searches,
        )
