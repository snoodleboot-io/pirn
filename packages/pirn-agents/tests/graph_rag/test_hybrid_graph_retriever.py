"""Tests for the :class:`HybridGraphRetriever` knot (S5 graph+vector fusion).

Uses stub doubles — a scripted ``NodeEmbeddingIndex`` for the vector arm and a
real :class:`GraphTraversal` over an :class:`InMemoryGraphStore` for the graph
arm — to verify merge/rank correctness and the no-embeddings fallback path.
"""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.graph_rag.graph_traversal import GraphTraversal
from pirn_agents.graph_rag.hybrid_graph_retriever import HybridGraphRetriever
from pirn_agents.graph_rag.traversal_budget import TraversalBudget
from pirn_agents.graph_stores.graph_edge import GraphEdge
from pirn_agents.graph_stores.graph_node import GraphNode
from pirn_agents.graph_stores.in_memory_graph_store import InMemoryGraphStore


class StubNodeEmbeddingIndex:
    """Scripted vector arm returning a fixed ranking (implements the protocol)."""

    def __init__(self, ranked: list[str], *, empty: bool = False) -> None:
        self._ranked = ranked
        self._empty = empty
        self.queries: list[str] = []

    async def ranked_node_ids(self, query_text: str, *, top_k: int) -> list[str]:
        self.queries.append(query_text)
        return self._ranked[:top_k]

    def is_empty(self) -> bool:
        return self._empty


def _make_traversal() -> GraphTraversal:
    with Tapestry():
        knot = GraphTraversal.__new__(GraphTraversal)
        object.__setattr__(knot, "_config", KnotConfig(id="t"))
    return knot


def _make_retriever() -> HybridGraphRetriever:
    with Tapestry():
        knot = HybridGraphRetriever.__new__(HybridGraphRetriever)
        object.__setattr__(knot, "_config", KnotConfig(id="hybrid-graph"))
    return knot


async def _store() -> InMemoryGraphStore:
    """a->b (graph arm surfaces a, b)."""
    store = InMemoryGraphStore()
    await store.upsert_nodes([GraphNode.create(id=n, type="N") for n in ("a", "b", "c")])
    await store.upsert_edges([GraphEdge.create(source_id="a", target_id="b", type="R")])
    return store


class TestHybridGraphRetriever(unittest.IsolatedAsyncioTestCase):
    async def test_fuses_graph_and_vector_arms(self) -> None:
        store = await _store()
        retriever = _make_retriever()
        # Vector arm surfaces "c" (isolated node the graph arm never reaches) and
        # re-ranks "a"; fusion must merge both arms into one ranking.
        index = StubNodeEmbeddingIndex(["c", "a"])

        results = await retriever.process(
            query_text="find c",
            start_ids=["a"],
            store=store,
            traversal=_make_traversal(),
            budget=TraversalBudget.create(max_depth=1),
            embedding_index=index,
            top_k=3,
            direction="out",
        )

        ids = [hit["id"] for hit in results]
        assert set(ids) == {"a", "b", "c"}
        # "a" is in both arms, so it ranks first.
        assert ids[0] == "a"
        scores = [hit["score"] for hit in results]
        assert scores == sorted(scores, reverse=True)
        assert index.queries == ["find c"]

    async def test_falls_back_to_graph_only_when_no_index(self) -> None:
        store = await _store()
        retriever = _make_retriever()

        results = await retriever.process(
            query_text="q",
            start_ids=["a"],
            store=store,
            traversal=_make_traversal(),
            budget=TraversalBudget.create(max_depth=1),
            embedding_index=None,
            top_k=5,
            direction="out",
        )

        ids = {hit["id"] for hit in results}
        assert ids == {"a", "b"}
        assert "c" not in ids

    async def test_empty_index_skips_vector_arm(self) -> None:
        store = await _store()
        retriever = _make_retriever()
        index = StubNodeEmbeddingIndex(["c"], empty=True)

        results = await retriever.process(
            query_text="q",
            start_ids=["a"],
            store=store,
            traversal=_make_traversal(),
            budget=TraversalBudget.create(max_depth=1),
            embedding_index=index,
            top_k=5,
            direction="out",
        )

        ids = {hit["id"] for hit in results}
        assert "c" not in ids
        # Vector arm must not be queried when the index reports itself empty.
        assert index.queries == []

    async def test_respects_top_k(self) -> None:
        store = await _store()
        retriever = _make_retriever()
        index = StubNodeEmbeddingIndex(["c", "a", "b"])

        results = await retriever.process(
            query_text="q",
            start_ids=["a"],
            store=store,
            traversal=_make_traversal(),
            budget=TraversalBudget.create(max_depth=1),
            embedding_index=index,
            top_k=1,
            direction="out",
        )

        assert len(results) == 1

    async def test_rejects_bad_embedding_index(self) -> None:
        store = await _store()
        retriever = _make_retriever()
        with self.assertRaisesRegex(TypeError, "embedding_index must implement NodeEmbeddingIndex"):
            await retriever.process(
                query_text="q",
                start_ids=["a"],
                store=store,
                traversal=_make_traversal(),
                budget=TraversalBudget.create(),
                embedding_index=123,  # type: ignore[arg-type]
            )

    async def test_rejects_bad_traversal(self) -> None:
        store = await _store()
        retriever = _make_retriever()
        with self.assertRaisesRegex(TypeError, "traversal must be a GraphTraversal"):
            await retriever.process(
                query_text="q",
                start_ids=["a"],
                store=store,
                traversal="nope",  # type: ignore[arg-type]
                budget=TraversalBudget.create(),
            )

    async def test_rejects_non_positive_top_k(self) -> None:
        store = await _store()
        retriever = _make_retriever()
        with self.assertRaisesRegex(ValueError, "top_k must be a positive int"):
            await retriever.process(
                query_text="q",
                start_ids=["a"],
                store=store,
                traversal=_make_traversal(),
                budget=TraversalBudget.create(),
                top_k=0,
            )


if __name__ == "__main__":
    unittest.main()
