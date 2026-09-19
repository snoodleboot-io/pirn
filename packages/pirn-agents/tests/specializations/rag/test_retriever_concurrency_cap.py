"""Behaviour tests: ``max_concurrency`` actually bounds the retrievers' searches.

``FusionRetriever`` and ``SubQuestionRetriever`` accepted ``max_concurrency``,
validated it, and then threw it away — their module docstrings claimed core
could not cap a container's own inner run, which has not been true since the
inner admission gate was chained under the enclosing run's. Every variant
search therefore ran at once no matter what the caller asked for (PIR-873).

The store double below records the high-water mark of simultaneously in-flight
searches, so each test asserts on observed concurrency rather than on the
presence of a group name.
"""

from __future__ import annotations

import asyncio
import unittest
from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.rag.fusion_retriever import FusionRetriever
from pirn_agents.specializations.rag.sub_question_retriever import SubQuestionRetriever


class _PeakTrackingStore(MemoryStore):
    """Records the largest number of ``search`` calls in flight at one time."""

    def __init__(self) -> None:
        self.in_flight = 0
        self.peak = 0

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        return None

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return None

    async def forget(self, key: str) -> None:
        return None

    async def close(self) -> None:
        return None

    async def search(self, query: str, *, top_k: int = 10) -> Sequence[Mapping[str, Any]]:
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            # Two suspension points: enough for every admitted sibling to be
            # observed in flight together when the gate lets them through.
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            return [{"id": f"{query}-doc", "text": query}]
        finally:
            self.in_flight -= 1


_QUERIES = ["alpha", "beta", "gamma", "delta"]


class TestFusionRetrieverConcurrencyCap(unittest.IsolatedAsyncioTestCase):
    async def _peak(self, max_concurrency: int) -> int:
        store = _PeakTrackingStore()
        with Tapestry() as tapestry:
            FusionRetriever(
                queries=list(_QUERIES),
                store=store,
                top_k=2,
                max_concurrency=max_concurrency,
                _config=KnotConfig(id="fusion"),
            )
        result = await tapestry.run(RunRequest())
        assert result.succeeded, result.exceptions
        return store.peak

    async def test_a_cap_of_one_serialises_the_variant_searches(self) -> None:
        assert await self._peak(1) == 1

    async def test_a_cap_of_two_admits_at_most_two_at_a_time(self) -> None:
        assert await self._peak(2) <= 2

    async def test_a_wide_cap_lets_the_variants_overlap(self) -> None:
        assert await self._peak(len(_QUERIES)) > 1


class TestSubQuestionRetrieverConcurrencyCap(unittest.IsolatedAsyncioTestCase):
    async def _peak(self, max_concurrency: int) -> int:
        store = _PeakTrackingStore()
        with Tapestry() as tapestry:
            SubQuestionRetriever(
                sub_questions=list(_QUERIES),
                store=store,
                top_k=2,
                max_concurrency=max_concurrency,
                _config=KnotConfig(id="subq"),
            )
        result = await tapestry.run(RunRequest())
        assert result.succeeded, result.exceptions
        return store.peak

    async def test_a_cap_of_one_serialises_the_sub_question_searches(self) -> None:
        assert await self._peak(1) == 1

    async def test_a_cap_of_two_admits_at_most_two_at_a_time(self) -> None:
        assert await self._peak(2) <= 2

    async def test_a_wide_cap_lets_the_sub_questions_overlap(self) -> None:
        assert await self._peak(len(_QUERIES)) > 1


if __name__ == "__main__":
    unittest.main()
