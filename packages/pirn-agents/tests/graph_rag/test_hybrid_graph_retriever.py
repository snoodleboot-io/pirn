"""Tests for the :class:`HybridGraphRetriever` knot (S5 graph+vector fusion).

Uses stub doubles — a scripted ``NodeEmbeddingIndex`` for the vector arm and a
real :class:`GraphTraversal` over an :class:`InMemoryGraphStore` for the graph
arm — to verify merge/rank correctness and the no-embeddings fallback path.

PIR-867: ``HybridGraphRetriever`` used to await its ``traversal`` knot's
``process()`` directly, re-passing ``store``/``budget``/``direction``/
``edge_types``/``start_ids`` at call time — a bare ``Knot`` subclass used as a
*value* type, which made ``Knot._build_adapters`` raise the moment the class
was constructed through its real ``__init__`` (see the removed PIR-856 note in
``hybrid_graph_retriever.py``'s git history). ``GraphTraversal`` is wired as a
genuine upstream parent now, fully configured at its own construction; these
tests build it that way and run the retriever through a real ``Tapestry``.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.retrieval.graph_rag.graph_traversal import GraphTraversal
from pirn_agents.retrieval.graph_rag.hybrid_graph_retriever import HybridGraphRetriever
from pirn_agents.retrieval.graph_rag.node_embedding_index import NodeEmbeddingIndex
from pirn_agents.retrieval.graph_rag.traversal_budget import TraversalBudget
from pirn_agents.retrieval.graph_stores.graph_edge import GraphEdge
from pirn_agents.retrieval.graph_stores.graph_node import GraphNode
from pirn_agents.retrieval.graph_stores.in_memory_graph_store import InMemoryGraphStore


class StubNodeEmbeddingIndex(NodeEmbeddingIndex):
    """Scripted vector arm returning a fixed ranking (implements the base)."""

    def __init__(self, ranked: list[str], *, empty: bool = False) -> None:
        self._ranked = ranked
        self._empty = empty
        self.queries: list[str] = []

    async def ranked_node_ids(self, query_text: str, *, top_k: int) -> list[str]:
        self.queries.append(query_text)
        return self._ranked[:top_k]

    def is_empty(self) -> bool:
        return self._empty


async def _store() -> InMemoryGraphStore:
    """a->b (graph arm surfaces a, b)."""
    store = InMemoryGraphStore()
    await store.upsert_nodes([GraphNode.create(id=n, type="N") for n in ("a", "b", "c")])
    await store.upsert_edges([GraphEdge.create(source_id="a", target_id="b", type="R")])
    return store


class TestHybridGraphRetriever(unittest.IsolatedAsyncioTestCase):
    async def _run(
        self,
        *,
        store: InMemoryGraphStore,
        embedding_index: NodeEmbeddingIndex | None,
        top_k: int = 5,
        direction: str = "out",
        max_depth: int = 1,
        query_text: str = "q",
    ) -> list[dict[str, Any]]:
        with Tapestry() as t:
            traversal = GraphTraversal(
                start_ids=["a"],
                store=store,
                budget=TraversalBudget.create(max_depth=max_depth),
                direction=direction,
                edge_types=None,
                _config=KnotConfig(id="traversal"),
            )
            HybridGraphRetriever(
                query_text=query_text,
                traversal=traversal,
                embedding_index=embedding_index,
                top_k=top_k,
                _config=KnotConfig(id="hybrid"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        return result.outputs["hybrid"]

    async def test_fuses_graph_and_vector_arms(self) -> None:
        store = await _store()
        # Vector arm surfaces "c" (isolated node the graph arm never reaches) and
        # re-ranks "a"; fusion must merge both arms into one ranking.
        index = StubNodeEmbeddingIndex(["c", "a"])

        results = await self._run(store=store, embedding_index=index, top_k=3, query_text="find c")

        ids = [hit["id"] for hit in results]
        assert set(ids) == {"a", "b", "c"}
        # "a" is in both arms, so it ranks first.
        assert ids[0] == "a"
        scores = [hit["score"] for hit in results]
        assert scores == sorted(scores, reverse=True)
        assert index.queries == ["find c"]

    async def test_falls_back_to_graph_only_when_no_index(self) -> None:
        store = await _store()

        results = await self._run(store=store, embedding_index=None, top_k=5)

        ids = {hit["id"] for hit in results}
        assert ids == {"a", "b"}
        assert "c" not in ids

    async def test_empty_index_skips_vector_arm(self) -> None:
        store = await _store()
        index = StubNodeEmbeddingIndex(["c"], empty=True)

        results = await self._run(store=store, embedding_index=index, top_k=5)

        ids = {hit["id"] for hit in results}
        assert "c" not in ids
        # Vector arm must not be queried when the index reports itself empty.
        assert index.queries == []

    async def test_respects_top_k(self) -> None:
        store = await _store()
        index = StubNodeEmbeddingIndex(["c", "a", "b"])

        results = await self._run(store=store, embedding_index=index, top_k=1)

        assert len(results) == 1

    async def test_rejects_bad_embedding_index(self) -> None:
        with Tapestry():
            knot = HybridGraphRetriever.__new__(HybridGraphRetriever)
            object.__setattr__(knot, "_config", KnotConfig(id="x"))
        store = await _store()
        traversal_subgraph = await GraphTraversal.__new__(GraphTraversal).process(
            start_ids=["a"],
            store=store,
            budget=TraversalBudget.create(),
        )
        with self.assertRaises((TypeError, AttributeError)):
            await knot.process(
                query_text="q",
                traversal=traversal_subgraph,
                embedding_index=123,  # type: ignore[arg-type]
            )

    async def test_rejects_non_positive_top_k(self) -> None:
        with Tapestry():
            knot = HybridGraphRetriever.__new__(HybridGraphRetriever)
            object.__setattr__(knot, "_config", KnotConfig(id="x"))
        store = await _store()
        traversal_subgraph = await GraphTraversal.__new__(GraphTraversal).process(
            start_ids=["a"],
            store=store,
            budget=TraversalBudget.create(),
        )
        with self.assertRaisesRegex(ValueError, "top_k must be a positive int"):
            await knot.process(
                query_text="q",
                traversal=traversal_subgraph,
                top_k=0,
            )


if __name__ == "__main__":
    unittest.main()
