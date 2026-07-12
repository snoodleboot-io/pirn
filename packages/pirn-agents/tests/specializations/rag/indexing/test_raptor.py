"""Tests for the RAPTOR tree builder + collapsed-tree retriever."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.indexing.raptor_retriever import RaptorRetriever
from pirn_agents.specializations.rag.indexing.raptor_tree import RaptorTree
from pirn_agents.specializations.rag.indexing.raptor_tree_builder import RaptorTreeBuilder
from pirn_agents.vector_stores.in_memory_vector_store import InMemoryVectorStore
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
        llm = StubLLMProvider(["summary text"])
        tree = await _build(store, embedder, llm)
        assert isinstance(tree, RaptorTree)
        assert tree.reused is False
        # 4 leaves + 2 + 1 summaries across 3 levels.
        assert tree.level_count >= 2
        assert tree.node_count > 4

    async def test_rebuild_is_reused_without_llm_calls(self) -> None:
        embedder = StubEmbeddingProvider(dimension=4)
        store = InMemoryVectorStore(embedder=embedder)
        llm = StubLLMProvider(["summary text"])
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
        llm = StubLLMProvider(["summary text"])
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
