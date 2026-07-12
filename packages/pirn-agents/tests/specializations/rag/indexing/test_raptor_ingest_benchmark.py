"""Benchmark: RAPTOR ingest-time tree reuse / caching (S8-T3).

Building a RAPTOR tree is expensive (an LLM summary per cluster). Because the
tree is content-addressed, a second ingest of identical content is skipped
entirely: it issues zero LLM summary calls and returns almost immediately. This
benchmark measures the first (cold) build against the second (reused) build.
"""

from __future__ import annotations

import time

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.indexing.raptor_tree_builder import RaptorTreeBuilder
from pirn_agents.vector_stores.in_memory_vector_store import InMemoryVectorStore
from tests.specializations.conftest import StubEmbeddingProvider, StubLLMProvider

_DOC = " ".join(f"chunk{i:02d}aaaa" for i in range(16))


async def _build(store: InMemoryVectorStore, embedder: StubEmbeddingProvider, llm: StubLLMProvider):
    with Tapestry() as t:
        RaptorTreeBuilder(
            text=_DOC,
            llm=llm,
            embedder=embedder,
            store=store,
            leaf_chunk_size=12,
            cluster_size=2,
            max_levels=4,
            _config=KnotConfig(id="raptor"),
        )
    result = await t.run(RunRequest())
    assert result.succeeded
    return result.outputs["raptor"]


@pytest.mark.benchmark
async def test_raptor_rebuild_skips_summaries() -> None:
    embedder = StubEmbeddingProvider(dimension=4)
    store = InMemoryVectorStore(embedder=embedder)
    llm = StubLLMProvider(["summary"])

    start = time.perf_counter()
    first = await _build(store, embedder, llm)
    cold = time.perf_counter() - start
    cold_calls = len(llm.calls)

    start = time.perf_counter()
    second = await _build(store, embedder, llm)
    warm = time.perf_counter() - start
    warm_calls = len(llm.calls) - cold_calls

    assert first.reused is False
    assert second.reused is True
    assert cold_calls > 0
    assert warm_calls == 0
    print(
        f"[benchmark] raptor_ingest nodes={first.node_count} levels={first.level_count} "
        f"cold_calls={cold_calls} cold={cold * 1e3:.1f}ms warm_calls={warm_calls} "
        f"warm={warm * 1e3:.1f}ms"
    )
