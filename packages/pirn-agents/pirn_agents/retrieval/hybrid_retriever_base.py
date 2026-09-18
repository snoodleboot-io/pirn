"""``HybridRetrieverBase`` — shared contract for RRF hybrid retrievers.

The common base behind the two hybrid retrievers in this package —
:class:`~pirn_agents.retrieval.hybrid_retriever.HybridRetriever` (dense + lexical)
and
:class:`~pirn_agents.retrieval.graph_rag.hybrid_graph_retriever.HybridGraphRetriever`
(graph + vector). Both fuse two candidate rankings with Reciprocal Rank Fusion
and return up to ``top_k`` ``{"id", "score"}`` hits, so they share a single
:class:`~pirn.core.knot.Knot` contract rather than each extending ``Knot``
independently.

Following the house interface style (never :class:`typing.Protocol`), this base
raises :class:`NotImplementedError` from :meth:`process`; every concrete hybrid
retriever overrides it with its own arm-specific retrieval and fusion.

Both concretes *produce* the same ``{"id", "score"}`` hits, but their
``process()`` returns differ in shape: ``HybridGraphRetriever`` is a leaf knot
whose ``process()`` returns the hits directly, while ``HybridRetriever`` is a
``SubTapestry`` whose ``process()`` returns the inner graph whose sink yields
them. The base is therefore generic in ``process()``'s return type
(``HybridRetrieverBase[list[Mapping[str, Any]]]`` for a leaf,
``HybridRetrieverBase[Knot]`` for a container), so each concrete keeps a
checked return contract instead of one the container cannot honour.
"""

from __future__ import annotations

from typing import Any, ClassVar, Generic, TypeVar

from pirn_agents.interfaces.retriever import Retriever

ProcessReturnT = TypeVar("ProcessReturnT")


class HybridRetrieverBase(Retriever, Generic[ProcessReturnT]):
    """Shared base for hybrid retrievers that fuse two rankings via RRF."""

    # ``process`` below is declared in the gradual parameter form; see
    # ``Knot._dynamic_process_signature`` for why (PIR-833).
    _dynamic_process_signature: ClassVar[bool] = True

    async def process(self, *args: Any, **_: Any) -> ProcessReturnT:
        """Retrieve two candidate rankings and fuse them into ``top_k`` hits.

        Returns:
            For a leaf retriever, up to ``top_k`` ``{"id", "score"}`` mappings
            ordered by fused score; for a ``SubTapestry`` retriever, the inner
            graph whose sink produces them.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement process()")
