"""Benchmark: rerank + compression vs naive top-k (S7-T3).

A fixture where the single relevant document is buried at the bottom of the
retriever's ranking. Naive top-1 (retrieval order) misses it; the rerank stack
promotes it under the same budget, so answer-relevant recall goes from 0 to 1.

``Reranker`` is a ``SubTapestry`` (ADR agents-speaks-core): its ``process()``
builds a ``Map``-fan-out-then-``Reduce`` graph and returns the ``Reduce`` sink
knot, not the resolved top-K list. Calling ``.process()`` on a bare
``Reranker.__new__`` instance (as this benchmark used to) hands back that sink
knot instead of a list, so the recall check silently passed on a truthy `Knot`
rather than the actual reranked documents. Wiring and running it through a
real ``Tapestry`` resolves the graph and gives back the real value.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.retrieval.rerank.reranker_backend import RerankerBackend
from pirn_agents.specializations.rag.reranker import Reranker
from tests.specializations.conftest import StubMemoryStore


class _RelevanceReranker(RerankerBackend):
    def __init__(self, target: str) -> None:
        self._target = target

    async def score(self, query: str, documents: Sequence[Mapping[str, Any]]) -> list[float]:
        return [1.0 if doc.get("id") == self._target else 0.0 for doc in documents]


async def _drain(store: MemoryStore, query: str, top_k: int) -> list[Mapping[str, Any]]:
    return list(await store.search(query, top_k=top_k))


@pytest.mark.benchmark
async def test_rerank_recovers_buried_relevant_doc() -> None:
    # Relevant doc "gold" is ranked last by the retriever.
    memory = StubMemoryStore(
        [{"id": f"d{i}", "text": "filler"} for i in range(9)] + [{"id": "gold", "text": "answer"}]
    )
    candidates = await _drain(memory, "q", top_k=10)

    budget = 1
    naive_top = candidates[:budget]
    naive_recall = 1.0 if any(d["id"] == "gold" for d in naive_top) else 0.0

    with Tapestry() as t:
        Reranker(
            query="q",
            documents=candidates,
            reranker=_RelevanceReranker("gold"),
            top_k=budget,
            _config=KnotConfig(id="rerank"),
        )
    result = await t.run(RunRequest())
    reranked = result.outputs["rerank"]
    rerank_recall = 1.0 if any(d["id"] == "gold" for d in reranked) else 0.0

    assert naive_recall == 0.0
    assert rerank_recall == 1.0
    print(
        f"[benchmark] contextual_rerank budget={budget} naive_recall={naive_recall:.2f} "
        f"rerank_recall={rerank_recall:.2f} candidates={len(candidates)}"
    )
