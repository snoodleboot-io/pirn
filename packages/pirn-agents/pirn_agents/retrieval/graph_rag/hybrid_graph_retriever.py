"""``HybridGraphRetriever`` — fuse graph traversal with vector similarity (RRF).

A :class:`Knot` that produces a single ranked context by combining two arms:

* **graph arm** — the :class:`Subgraph` produced by an upstream, fully-wired
  :class:`~pirn_agents.retrieval.graph_rag.graph_traversal.GraphTraversal` knot
  (its own ``store``/``budget``/``start_ids``/``direction``/``edge_types`` are
  bound when *that* knot is constructed), ranked by proximity (BFS order);
* **vector arm** — the F4-backed
  :class:`~pirn_agents.retrieval.graph_rag.node_embedding_index.NodeEmbeddingIndex`, which
  ranks nodes by embedding similarity to the query text.

The two rankings are fused with Reciprocal Rank Fusion — the same scale-free
fusion used by the dense+lexical :class:`HybridRetriever` — so no cross-arm score
calibration is needed. The vector arm is **opt-in**: when no embedding index is
supplied (or it holds no nodes), the retriever falls back cleanly to the graph
arm alone, still returning RRF-scored hits so the output shape is identical.

Algorithm:
    1. The engine resolves ``traversal`` — an upstream
       :class:`~pirn_agents.retrieval.graph_rag.graph_traversal.GraphTraversal`
       knot — into its :class:`Subgraph` output *before* this knot's
       ``process()`` runs, exactly like any other parent. There is no
       call-time re-invocation of the traversal here (PIR-867): the graph arm
       is a genuine graph edge, not a value threaded through by hand.
    2. Validate ``top_k`` / ``candidate_multiplier``.
    3. Extract the graph-arm ranking from ``traversal.node_ids()``.
    4. When no usable ``embedding_index`` is supplied, fuse the single
       graph-arm ranking (a no-op fusion that keeps the output shape uniform)
       and return the top ``top_k`` hits.
    5. Otherwise rank ``top_k * candidate_multiplier`` nodes from the vector
       arm and fuse both rankings.

Math:
    Fusion is delegated to
    :meth:`~pirn_agents.retrieval.reciprocal_rank_fusion.ReciprocalRankFusion.fuse`.
    For each node id :math:`d` appearing in one or both of the graph-arm and
    vector-arm rankings :math:`R`, with damping constant ``rrf_k`` and
    0-based rank :math:`\\text{rank}_r(d)` of :math:`d` in ranking :math:`r`:

    $$
    \\text{RRF}(d) = \\sum_{r \\in R} \\frac{1}{\\text{rrf\\_k} + \\text{rank}_r(d)}
    $$

    A node absent from a ranking contributes nothing from that ranking's term
    (there is no rank to sum). Nodes are returned in descending
    :math:`\\text{RRF}(d)`, ties broken by first appearance across the input
    rankings. The vector arm is over-fetched by ``candidate_multiplier`` (top
    ``top_k * candidate_multiplier`` hits) before fusion, so the final
    RRF-ordered cut is less sensitive to the vector arm's own ranking noise
    near the boundary.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.retrieval.graph_rag.graph_traversal import GraphTraversal
from pirn_agents.retrieval.graph_rag.node_embedding_index import NodeEmbeddingIndex
from pirn_agents.retrieval.graph_rag.subgraph import Subgraph
from pirn_agents.retrieval.hybrid_retriever_base import HybridRetrieverBase
from pirn_agents.retrieval.reciprocal_rank_fusion import ReciprocalRankFusion


class HybridGraphRetriever(HybridRetrieverBase[list[Mapping[str, Any]]]):
    """Fuse graph-neighborhood and vector-similarity node rankings via RRF."""

    def __init__(
        self,
        *,
        query_text: Knot | str,
        traversal: GraphTraversal,
        _config: KnotConfig,
        embedding_index: Knot | NodeEmbeddingIndex | None = None,
        top_k: Knot | int = 5,
        candidate_multiplier: Knot | int = 4,
        rrf_k: Knot | int = 60,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query_text=query_text,
            traversal=traversal,
            embedding_index=embedding_index,
            top_k=top_k,
            candidate_multiplier=candidate_multiplier,
            rrf_k=rrf_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query_text: str,
        traversal: Subgraph,
        embedding_index: NodeEmbeddingIndex | None = None,
        top_k: int = 5,
        candidate_multiplier: int = 4,
        rrf_k: int = 60,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Return up to ``top_k`` fused ``{"id", "score"}`` node hits.

        Args:
            query_text: The query embedded for the vector arm.
            traversal: The graph arm's already-resolved :class:`Subgraph`
                (the output of the upstream ``GraphTraversal`` knot).
            embedding_index: Optional vector arm; when ``None`` or empty the
                retriever falls back to graph-only ranking.
            top_k: Number of fused hits to return.
            candidate_multiplier: Over-fetch factor for the vector arm.
            rrf_k: The RRF damping constant.

        Returns:
            Up to ``top_k`` ``{"id", "score"}`` mappings ordered by fused score.

        Raises:
            ValueError: If ``top_k`` or ``candidate_multiplier`` is not positive.
        """
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"HybridGraphRetriever: top_k must be a positive int, got {top_k!r}")
        if not isinstance(candidate_multiplier, int) or candidate_multiplier <= 0:
            raise ValueError(
                f"HybridGraphRetriever: candidate_multiplier must be a positive int, "
                f"got {candidate_multiplier!r}"
            )

        graph_ids = traversal.node_ids()

        if not self._vector_enabled(embedding_index):
            # Clean graph-only fallback: RRF over the single graph ranking keeps
            # the returned score shape identical to the fused path.
            fused = ReciprocalRankFusion.fuse([graph_ids], k=rrf_k)
            return [{"id": identifier, "score": score} for identifier, score in fused[:top_k]]

        assert embedding_index is not None
        vector_ids = await embedding_index.ranked_node_ids(
            query_text, top_k=top_k * candidate_multiplier
        )
        fused = ReciprocalRankFusion.fuse([graph_ids, vector_ids], k=rrf_k)
        return [{"id": identifier, "score": score} for identifier, score in fused[:top_k]]

    @staticmethod
    def _vector_enabled(embedding_index: NodeEmbeddingIndex | None) -> bool:
        """Return whether the vector arm should run (present and non-empty)."""
        if embedding_index is None:
            return False
        if embedding_index.is_empty():
            return False
        return True
