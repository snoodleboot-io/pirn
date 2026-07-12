"""``HybridGraphRetriever`` — fuse graph traversal with vector similarity (RRF).

A :class:`Knot` that produces a single ranked context by combining two arms:

* **graph arm** — a bounded :class:`GraphTraversal` neighborhood from the seed
  set, whose collected nodes are ranked by proximity (BFS order);
* **vector arm** — the F4-backed
  :class:`~pirn_agents.graph_rag.node_embedding_index.NodeEmbeddingIndex`, which
  ranks nodes by embedding similarity to the query text.

The two rankings are fused with Reciprocal Rank Fusion — the same scale-free
fusion used by the dense+lexical :class:`HybridRetriever` — so no cross-arm score
calibration is needed. The vector arm is **opt-in**: when no embedding index is
supplied (or it holds no nodes), the retriever falls back cleanly to the graph
arm alone, still returning RRF-scored hits so the output shape is identical.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.graph_rag.graph_traversal import GraphTraversal
from pirn_agents.graph_rag.node_embedding_index import NodeEmbeddingIndex
from pirn_agents.graph_rag.traversal_budget import TraversalBudget
from pirn_agents.graph_stores.graph_store import GraphStore
from pirn_agents.retrieval.reciprocal_rank_fusion import reciprocal_rank_fusion


class HybridGraphRetriever(Knot):
    """Fuse graph-neighborhood and vector-similarity node rankings via RRF."""

    def __init__(
        self,
        *,
        store: Knot | GraphStore,
        traversal: Knot | GraphTraversal,
        budget: Knot | TraversalBudget,
        _config: KnotConfig,
        embedding_index: Knot | NodeEmbeddingIndex | None = None,
        top_k: Knot | int = 5,
        candidate_multiplier: Knot | int = 4,
        rrf_k: Knot | int = 60,
        direction: Knot | str = "both",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            store=store,
            traversal=traversal,
            budget=budget,
            embedding_index=embedding_index,
            top_k=top_k,
            candidate_multiplier=candidate_multiplier,
            rrf_k=rrf_k,
            direction=direction,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query_text: str,
        start_ids: Sequence[str],
        store: GraphStore,
        traversal: GraphTraversal,
        budget: TraversalBudget,
        embedding_index: NodeEmbeddingIndex | None = None,
        top_k: int = 5,
        candidate_multiplier: int = 4,
        rrf_k: int = 60,
        direction: str = "both",
        edge_types: Sequence[str] | None = None,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Return up to ``top_k`` fused ``{"id", "score"}`` node hits.

        Args:
            query_text: The query embedded for the vector arm.
            start_ids: The seed node ids for the graph arm.
            store: The graph store traversed.
            traversal: The bounded traversal knot for the graph arm.
            budget: The traversal depth / fanout / size bounds.
            embedding_index: Optional vector arm; when ``None`` or empty the
                retriever falls back to graph-only ranking.
            top_k: Number of fused hits to return.
            candidate_multiplier: Over-fetch factor for the vector arm.
            rrf_k: The RRF damping constant.
            direction: Neighbor direction for the graph arm.
            edge_types: Optional edge-type whitelist for the graph arm.

        Returns:
            Up to ``top_k`` ``{"id", "score"}`` mappings ordered by fused score.

        Raises:
            TypeError: If ``query_text``/``store``/``traversal``/``budget`` or a
                supplied ``embedding_index`` is the wrong type.
            ValueError: If ``top_k`` or ``candidate_multiplier`` is not positive.
        """
        if not isinstance(query_text, str):
            raise TypeError(
                f"HybridGraphRetriever: query_text must be a str, got {type(query_text).__name__}"
            )
        if not isinstance(store, GraphStore):
            raise TypeError(
                f"HybridGraphRetriever: store must be a GraphStore, got {type(store).__name__}"
            )
        if not isinstance(traversal, GraphTraversal):
            raise TypeError(
                f"HybridGraphRetriever: traversal must be a GraphTraversal, "
                f"got {type(traversal).__name__}"
            )
        if not isinstance(budget, TraversalBudget):
            raise TypeError(
                f"HybridGraphRetriever: budget must be a TraversalBudget, "
                f"got {type(budget).__name__}"
            )
        if embedding_index is not None and not isinstance(embedding_index, NodeEmbeddingIndex):
            raise TypeError(
                f"HybridGraphRetriever: embedding_index must implement NodeEmbeddingIndex, "
                f"got {type(embedding_index).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"HybridGraphRetriever: top_k must be a positive int, got {top_k!r}")
        if not isinstance(candidate_multiplier, int) or candidate_multiplier <= 0:
            raise ValueError(
                f"HybridGraphRetriever: candidate_multiplier must be a positive int, "
                f"got {candidate_multiplier!r}"
            )

        subgraph = await traversal.process(
            start_ids=start_ids,
            store=store,
            budget=budget,
            direction=direction,
            edge_types=edge_types,
        )
        graph_ids = subgraph.node_ids()

        if not self._vector_enabled(embedding_index):
            # Clean graph-only fallback: RRF over the single graph ranking keeps
            # the returned score shape identical to the fused path.
            fused = reciprocal_rank_fusion([graph_ids], k=rrf_k)
            return [{"id": identifier, "score": score} for identifier, score in fused[:top_k]]

        assert embedding_index is not None
        vector_ids = await embedding_index.ranked_node_ids(
            query_text, top_k=top_k * candidate_multiplier
        )
        fused = reciprocal_rank_fusion([graph_ids, vector_ids], k=rrf_k)
        return [{"id": identifier, "score": score} for identifier, score in fused[:top_k]]

    @staticmethod
    def _vector_enabled(embedding_index: NodeEmbeddingIndex | None) -> bool:
        """Return whether the vector arm should run (present and non-empty)."""
        if embedding_index is None:
            return False
        is_empty = getattr(embedding_index, "is_empty", None)
        if callable(is_empty) and is_empty():
            return False
        return True
