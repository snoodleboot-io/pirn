"""Benchmark: RAG-Fusion recall/latency vs naive retrieval (S2-T3).

A fixture corpus where each query variant surfaces a different relevant document
(``only-a``, ``only-b``, ``only-c``). Naive retrieval issues one query and sees
one relevant doc; RAG-Fusion fans out the variants concurrently and recovers the
full relevant set, so its recall strictly beats naive while latency stays
bounded by the concurrency budget.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Mapping
from typing import Any

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.rag.fusion_retriever import FusionRetriever


class _FixtureStore(MemoryStore):
    def __init__(self) -> None:
        self._corpus: dict[str, list[Mapping[str, Any]]] = {
            "capital of france": [{"id": "paris", "text": "Paris is the capital."}],
            "french capital city": [
                {"id": "paris", "text": "Paris is the capital."},
                {"id": "seine", "text": "The Seine runs through Paris."},
            ],
            "where is the eiffel tower": [
                {"id": "eiffel", "text": "The Eiffel Tower is in Paris."}
            ],
        }

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        return None

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return None

    async def search(self, query: str, *, top_k: int = 10) -> AsyncIterator[Mapping[str, Any]]:
        hits = self._corpus.get(query, [])

        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            for hit in hits[:top_k]:
                yield hit

        return _aiter()

    async def forget(self, key: str) -> None:
        return None

    async def close(self) -> None:
        return None


def _retriever() -> FusionRetriever:
    with Tapestry():
        knot = FusionRetriever.__new__(FusionRetriever)
        object.__setattr__(knot, "_config", KnotConfig(id="fuse-bench"))
    return knot


@pytest.mark.benchmark
async def test_fusion_beats_naive_recall() -> None:
    store = _FixtureStore()
    relevant = {"paris", "seine", "eiffel"}
    variants = [
        "capital of france",
        "french capital city",
        "where is the eiffel tower",
    ]

    # Naive: single query.
    naive = await _retriever().process(queries=[variants[0]], store=store, top_k=10)
    naive_recall = len({r["id"] for r in naive} & relevant) / len(relevant)

    # Fusion: all variants concurrently.
    start = time.perf_counter()
    fused = await _retriever().process(queries=variants, store=store, top_k=10, max_concurrency=4)
    elapsed = time.perf_counter() - start
    fusion_recall = len({r["id"] for r in fused} & relevant) / len(relevant)

    assert fusion_recall > naive_recall
    assert fusion_recall == 1.0
    print(
        f"[benchmark] rag_fusion naive_recall={naive_recall:.2f} "
        f"fusion_recall={fusion_recall:.2f} variants={len(variants)} "
        f"latency={elapsed * 1e3:.3f}ms"
    )
