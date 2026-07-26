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
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.interfaces.retriever import Retriever


class HybridRetrieverBase(Retriever):
    """Shared base for hybrid retrievers that fuse two rankings via RRF."""

    async def process(self, **kwargs: Any) -> list[Mapping[str, Any]]:
        """Retrieve two candidate rankings and fuse them into ``top_k`` hits.

        Returns:
            Up to ``top_k`` ``{"id", "score"}`` mappings ordered by fused score.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement process()")
