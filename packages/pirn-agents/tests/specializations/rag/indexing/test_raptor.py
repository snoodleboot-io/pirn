"""Tests for the RAPTOR tree builder + collapsed-tree retriever."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.retrieval.vector_stores.in_memory_vector_store import InMemoryVectorStore
from pirn_agents.specializations.rag.indexing.raptor_assembler import RaptorAssembler
from pirn_agents.specializations.rag.indexing.raptor_retriever import RaptorRetriever
from pirn_agents.specializations.rag.indexing.raptor_tree import RaptorTree
from pirn_agents.specializations.rag.indexing.raptor_tree_builder import RaptorTreeBuilder
from tests.specializations.conftest import StubEmbeddingProvider, StubLLMProvider

_DOC = "aaaaaaaaaa bbbbbbbbbb cccccccccc dddddddddd"


def _retriever() -> RaptorRetriever:
    with Tapestry():
        knot = RaptorRetriever.__new__(RaptorRetriever)
        object.__setattr__(knot, "_config", KnotConfig(id="raptor-retrieve"))
    return knot


async def _build(store: InMemoryVectorStore, embedder: StubEmbeddingProvider, llm: StubLLMProvider):
    with Tapestry() as t:
        RaptorTreeBuilder(
            text=_DOC,
            llm=llm,
            embedder=embedder,
            store=store,
            leaf_chunk_size=10,
            chunk_overlap=0,
            cluster_size=2,
            max_levels=3,
            _config=KnotConfig(id="raptor"),
        )
    result = await t.run(RunRequest())
    assert result.succeeded
    return result.outputs["raptor"]


class TestRaptor(unittest.IsolatedAsyncioTestCase):
    async def test_builds_multi_level_tree(self) -> None:
        embedder = StubEmbeddingProvider(dimension=4)
        store = InMemoryVectorStore(embedder=embedder)
        llm = StubLLMProvider(["summary text"], repeat_last=True)
        tree = await _build(store, embedder, llm)
        assert isinstance(tree, RaptorTree)
        assert tree.reused is False
        # 4 leaves + 2 + 1 summaries across 3 levels.
        assert tree.level_count >= 2
        assert tree.node_count > 4

    async def test_rebuild_is_reused_without_llm_calls(self) -> None:
        embedder = StubEmbeddingProvider(dimension=4)
        store = InMemoryVectorStore(embedder=embedder)
        llm = StubLLMProvider(["summary text"], repeat_last=True)
        first = await _build(store, embedder, llm)
        calls_after_first = len(llm.calls)
        assert calls_after_first > 0
        second = await _build(store, embedder, llm)
        assert second.reused is True
        assert second.content_hash == first.content_hash
        # No new summary calls on the content-addressed rebuild.
        assert len(llm.calls) == calls_after_first

    async def test_collapsed_retrieval_excludes_meta(self) -> None:
        embedder = StubEmbeddingProvider(dimension=4)
        store = InMemoryVectorStore(embedder=embedder)
        llm = StubLLMProvider(["summary text"], repeat_last=True)
        await _build(store, embedder, llm)
        leaf = await store.get(
            "raptor:" + (await _build(store, embedder, llm)).content_hash + ":0:0"
        )
        assert leaf is not None and leaf.document is not None
        results = await _retriever().process(
            query=leaf.document,
            store=store,
            embedder=StubEmbeddingProvider(dimension=4),
            top_k=10,
        )
        assert results
        assert all(not r["id"].endswith(":meta") for r in results)


class _CountingStore(InMemoryVectorStore):
    """Counts upserts, so a test can pin the single final write."""

    upserts: int = 0

    async def upsert(self, records: Any) -> None:
        self.upserts += 1
        await super().upsert(records)


class TestRaptorPerSummaryLineage(unittest.IsolatedAsyncioTestCase):
    """Each cluster summary is its own knot, and the levels are one chained run.

    Run shape asserted below::

        asm                         the assembler's own row
          levels                    the one inner run it opens
            level_1, level_2        iteration knots of the RaptorLevelLoop
              <prefix>:N:i, vectors one summary knot per cluster, one embed knot


    PIR-872 gave every cluster summary its own knot. PIR-874 then replaced the
    ``while`` loop that started a *separate* nested run per level with a single
    ``RaptorLevelLoop`` run whose iterations are the levels — so level 2's rows
    are chained to level 1's instead of sitting in an unrelated run — and made
    each level's embedding call a knot rather than an ``await``.
    """

    @staticmethod
    async def _levels(history: InMemoryHistory, run_id: str) -> list[Any]:
        """Return the per-level runs under the assembler's single climb run."""
        (inner,) = await history.children_of(run_id)
        (loop,) = await history.children_of(inner.run_id)
        return list(await history.children_of(loop.run_id))

    @staticmethod
    async def _assemble(
        store: InMemoryVectorStore, llm: StubLLMProvider
    ) -> tuple[Any, InMemoryHistory]:
        history = InMemoryHistory()
        with Tapestry(history=history) as t:
            RaptorAssembler(
                chunks=["a", "b", "c", "d"],
                llm=llm,
                embedder=StubEmbeddingProvider(dimension=4),
                store=store,
                cluster_size=2,
                max_levels=3,
                _config=KnotConfig(id="asm"),
            )
        return await t.run(RunRequest()), history

    async def test_every_summary_call_has_its_own_lineage_row(self) -> None:
        # Arrange
        store = _CountingStore(embedder=StubEmbeddingProvider(dimension=4))
        llm = StubLLMProvider(["summary text"], repeat_last=True)

        # Act
        result, history = await self._assemble(store, llm)

        # Assert: one inner run for the whole climb, 2 + 1 summary knots across
        # its two level iterations, one upsert.
        assert result.succeeded, result.exceptions
        tree = result.outputs["asm"]
        prefix = f"raptor:{tree.content_hash}"
        (climb,) = await history.children_of(result.run_id)
        assert climb.parent_knot_id == "asm"
        (row,) = [r for r in result.lineage if r.knot_id == "asm"]
        assert row.extra["inner_run_id"] == climb.run_id
        # Every summary knot is named after the node it produces, and both
        # levels' summaries are rows of iterations of this one climb.
        summary_ids = sorted(
            lineage.knot_id
            for level in await self._levels(history, result.run_id)
            for lineage in level.lineage
            if lineage.knot_id.startswith(prefix)
        )
        assert summary_ids == [f"{prefix}:1:0", f"{prefix}:1:1", f"{prefix}:2:0"]
        assert len(llm.calls) == 3
        assert store.upserts == 1
        assert tree.node_count == 7

    async def test_each_level_is_an_iteration_of_one_run(self) -> None:
        """Levels are chained, not unrelated: one climb run, one child per level."""
        store = _CountingStore(embedder=StubEmbeddingProvider(dimension=4))
        llm = StubLLMProvider(["summary text"], repeat_last=True)

        result, history = await self._assemble(store, llm)

        assert result.succeeded, result.exceptions
        (climb,) = await history.children_of(result.run_id)
        (loop,) = await history.children_of(climb.run_id)
        assert [row.knot_id for row in loop.lineage] == [
            "level_1",
            "level_2",
            "__loop_terminal__",
        ]
        levels = await self._levels(history, result.run_id)
        assert len(levels) == 2
        assert all(level.succeeded for level in levels)

    async def test_each_level_embeds_through_a_knot(self) -> None:
        """The per-level ``embed`` was an await in the loop; it is a knot now."""
        store = _CountingStore(embedder=StubEmbeddingProvider(dimension=4))
        llm = StubLLMProvider(["summary text"], repeat_last=True)

        result, history = await self._assemble(store, llm)

        assert result.succeeded, result.exceptions
        embeddings = [
            lineage.knot_id
            for level in await self._levels(history, result.run_id)
            for lineage in level.lineage
            if lineage.knot_id == "vectors"
        ]
        assert embeddings == ["vectors", "vectors"]

    async def test_a_reused_tree_starts_no_inner_run(self) -> None:
        store = _CountingStore(embedder=StubEmbeddingProvider(dimension=4))
        llm = StubLLMProvider(["summary text"], repeat_last=True)
        await self._assemble(store, llm)

        result, history = await self._assemble(store, llm)

        assert result.outputs["asm"].reused is True
        assert await history.children_of(result.run_id) == []
        assert store.upserts == 1

    async def test_a_failed_summary_fails_the_assembly_without_upserting(self) -> None:
        store = _CountingStore(embedder=StubEmbeddingProvider(dimension=4))

        result, history = await self._assemble(store, StubLLMProvider([]))

        assert not result.succeeded
        (record,) = [e for e in result.exceptions if e.knot_id == "asm"]
        assert "exceeds the 0 scripted" in record.message
        assert store.upserts == 0
        (child,) = await history.children_of(result.run_id)
        assert not child.succeeded
