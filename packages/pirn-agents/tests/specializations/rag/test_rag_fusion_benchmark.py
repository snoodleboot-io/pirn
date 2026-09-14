"""Benchmark: RAG-Fusion recall/latency vs naive retrieval (S2-T3).

A fixture corpus where each query variant surfaces a different relevant document
(``only-a``, ``only-b``, ``only-c``). Naive retrieval issues one query and sees
one relevant doc; RAG-Fusion fans out the variants concurrently and recovers the
full relevant set, so its recall strictly beats naive while latency stays
bounded by the concurrency budget.

``FusionRetriever`` is a ``SubTapestry`` (ADR agents-speaks-core): its
``process()`` builds a per-variant search graph and returns its RRF-fusing
``Reduce`` sink knot, not the resolved fused list. Calling ``.process()`` on a
bare ``FusionRetriever.__new__`` instance (as this benchmark used to) hands
back that sink knot instead of a list of documents, so the recall check
iterated a `Knot`, not the actual fused results. Wiring and running it
through a real ``Tapestry`` resolves the graph and gives back the real value.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.memory.stores.memory_store import MemoryStore
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

    async def search(self, query: str, *, top_k: int = 10) -> Sequence[Mapping[str, Any]]:
        # MemoryStore.search()'s contract (PIR-856) is a single await away
        # from a concrete, len()-able sequence -- never an async iterator or
        # generator (see the interface docstring).
        return self._corpus.get(query, [])[:top_k]

    async def forget(self, key: str) -> None:
        return None

    async def close(self) -> None:
        return None


async def _run_fusion_retriever(**kwargs: Any) -> list[Mapping[str, Any]]:
    with Tapestry() as t:
        FusionRetriever(_config=KnotConfig(id="fuse-bench"), **kwargs)
    result = await t.run(RunRequest())
    return result.outputs["fuse-bench"]


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
    naive = await _run_fusion_retriever(queries=[variants[0]], store=store, top_k=10)
    naive_recall = len({r["id"] for r in naive} & relevant) / len(relevant)

    # Fusion: all variants concurrently.
    start = time.perf_counter()
    fused = await _run_fusion_retriever(queries=variants, store=store, top_k=10, max_concurrency=4)
    elapsed = time.perf_counter() - start
    fusion_recall = len({r["id"] for r in fused} & relevant) / len(relevant)

    assert fusion_recall > naive_recall
    assert fusion_recall == 1.0
    print(
        f"[benchmark] rag_fusion naive_recall={naive_recall:.2f} "
        f"fusion_recall={fusion_recall:.2f} variants={len(variants)} "
        f"latency={elapsed * 1e3:.3f}ms"
    )
