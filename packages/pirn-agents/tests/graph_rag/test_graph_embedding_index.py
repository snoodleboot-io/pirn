"""Tests for :class:`GraphEmbeddingIndex` (S5-T1 node/edge embeddings via F4)."""

from __future__ import annotations

import unittest
from collections.abc import Sequence

from pirn_agents.embedding_provider import EmbeddingProvider
from pirn_agents.graph_rag.graph_embedding_index import GraphEmbeddingIndex
from pirn_agents.graph_stores.graph_edge import GraphEdge
from pirn_agents.graph_stores.graph_node import GraphNode


class KeywordEmbedder(EmbeddingProvider):
    """Deterministic F4-style embedder: per-word counts over a fixed vocab."""

    def __init__(self, vocab: Sequence[str]) -> None:
        self._vocab = [w.lower() for w in vocab]

    async def embed(self, texts: Sequence[str], *, model: str | None = None) -> list[list[float]]:
        return [[float(text.lower().split().count(word)) for word in self._vocab] for text in texts]

    async def close(self) -> None:
        return None


def _node(node_id: str, keyword: str) -> GraphNode:
    return GraphNode.create(id=node_id, type="N", properties={"name": keyword})


class TestGraphEmbeddingIndex(unittest.IsolatedAsyncioTestCase):
    async def test_ranks_nodes_by_query_similarity(self) -> None:
        index = GraphEmbeddingIndex(embedder=KeywordEmbedder(["alpha", "beta", "gamma"]))
        await index.index_nodes([_node("n1", "alpha"), _node("n2", "beta"), _node("n3", "gamma")])

        ranked = await index.ranked_node_ids("alpha", top_k=3)

        assert ranked[0] == "n1"

    async def test_is_empty_tracks_indexing(self) -> None:
        index = GraphEmbeddingIndex(embedder=KeywordEmbedder(["alpha"]))
        assert index.is_empty() is True
        await index.index_nodes([_node("n1", "alpha")])
        assert index.is_empty() is False

    async def test_edge_vectors_excluded_from_node_ranking(self) -> None:
        index = GraphEmbeddingIndex(embedder=KeywordEmbedder(["alpha", "beta"]))
        await index.index_nodes([_node("n1", "alpha")])
        # Edge text "alpha REL beta" also matches the query, but edges are tagged
        # kind="edge" and must not appear in the node ranking.
        await index.index_edges([GraphEdge.create(source_id="alpha", target_id="beta", type="REL")])

        ranked = await index.ranked_node_ids("alpha", top_k=5)

        assert "alpha|REL|beta" not in ranked
        assert ranked == ["n1"]

    async def test_rejects_non_positive_top_k(self) -> None:
        index = GraphEmbeddingIndex(embedder=KeywordEmbedder(["alpha"]))
        with self.assertRaisesRegex(ValueError, "top_k must be a positive int"):
            await index.ranked_node_ids("alpha", top_k=0)

    def test_rejects_bad_embedder(self) -> None:
        with self.assertRaisesRegex(TypeError, "embedder must be an EmbeddingProvider"):
            GraphEmbeddingIndex(embedder="nope")  # type: ignore[arg-type]

    async def test_empty_index_calls_return_cleanly(self) -> None:
        index = GraphEmbeddingIndex(embedder=KeywordEmbedder(["alpha"]))
        await index.index_nodes([])
        await index.index_edges([])
        assert await index.ranked_node_ids("alpha", top_k=3) == []
        await index.close()


if __name__ == "__main__":
    unittest.main()
