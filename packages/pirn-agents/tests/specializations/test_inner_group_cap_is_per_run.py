"""Behaviour tests: a container's inner concurrency cap belongs to its run.

``IngestionRunner`` and ``OrchestratorWorkers`` decide the cap of their inner
run from a ``max_concurrency`` input, and the framework asks for it afterwards
through ``_inner_concurrency()``. Before PIR-873 they parked the value on the
knot (``self._mutable_max_concurrency``). A knot object is shared by every run
of the tapestry it belongs to, so two concurrent runs overwrote each other and
one of them executed under the other's budget.

Each test drives two runs of the *same* knot as two asyncio tasks, interleaved
so the second run's ``process()`` lands between the first run's ``process()``
and its ``_inner_concurrency()`` — the exact window the old code lost. The
assertion is on the cap each run reads back, not on how it is stored.
"""

from __future__ import annotations

import asyncio
import unittest
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.document_processing.chunking.fixed_size_chunking_strategy import (
    FixedSizeChunkingStrategy,
)
from pirn_agents.specializations.document_processing.incremental.incremental_upserter import (
    IncrementalUpserter,
)
from pirn_agents.specializations.document_processing.ingestion_runner import IngestionRunner
from pirn_agents.specializations.document_processing.loaders.markdown_loader import MarkdownLoader
from pirn_agents.specializations.document_processing.sources.source_connector import (
    SourceConnector,
)
from pirn_agents.specializations.document_processing.sources.source_document import SourceDocument
from pirn_agents.specializations.multi_agent.orchestrator_workers import OrchestratorWorkers
from pirn_agents.testing.stub_tool import StubTool
from tests.specializations.conftest import StubEmbeddingProvider


class _SilentStore(MemoryStore):
    """Dict-backed store; the ingestion runner never reaches it in these tests."""

    def __init__(self) -> None:
        self.entries: dict[str, Mapping[str, Any]] = {}

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self.entries[key] = dict(value)

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return self.entries.get(key)

    async def search(self, query: str, *, top_k: int = 10) -> Sequence[Mapping[str, Any]]:
        return []

    async def forget(self, key: str) -> None:
        self.entries.pop(key, None)

    async def close(self) -> None:
        return None


class _StubSource(SourceConnector):
    def __init__(self, count: int) -> None:
        self._count = count

    async def fetch(self) -> AsyncIterator[SourceDocument]:
        for index in range(self._count):
            yield SourceDocument.create(source_id=f"d{index}", data=b"body text")

    @property
    def errors(self) -> tuple[tuple[str, str], ...]:
        return ()


class _Interleaver:
    """Forces run A's ``_inner_concurrency()`` to land after run B's ``process()``."""

    def __init__(self) -> None:
        self.b_has_planned = asyncio.Event()
        self.a_has_planned = asyncio.Event()


class TestIngestionRunnerCapIsPerRun(unittest.IsolatedAsyncioTestCase):
    def _runner(self) -> IngestionRunner:
        with Tapestry():
            return IngestionRunner(
                source_connector=_StubSource(2),
                loader=MarkdownLoader(),
                chunking_strategy=FixedSizeChunkingStrategy(chunk_size=8, chunk_overlap=0),
                upserter=IncrementalUpserter(
                    store=_SilentStore(), embedder=StubEmbeddingProvider(dimension=3)
                ),
                max_concurrency=1,
                _config=KnotConfig(id="runner"),
            )

    async def _plan(
        self, runner: IngestionRunner, cap: int, mine: asyncio.Event, theirs: asyncio.Event
    ) -> ConcurrencyLimits | None:
        with Tapestry():
            await runner.process(
                source_connector=_StubSource(2),
                loader=MarkdownLoader(),
                chunking_strategy=FixedSizeChunkingStrategy(chunk_size=8, chunk_overlap=0),
                upserter=IncrementalUpserter(
                    store=_SilentStore(), embedder=StubEmbeddingProvider(dimension=3)
                ),
                max_concurrency=cap,
            )
        mine.set()
        await theirs.wait()
        return runner._inner_concurrency()

    async def test_two_concurrent_runs_keep_their_own_caps(self) -> None:
        runner = self._runner()
        gate = _Interleaver()
        slow, fast = await asyncio.gather(
            asyncio.create_task(self._plan(runner, 2, gate.a_has_planned, gate.b_has_planned)),
            asyncio.create_task(self._plan(runner, 7, gate.b_has_planned, gate.a_has_planned)),
        )
        assert slow == ConcurrencyLimits(groups={"ingest_docs": 2})
        assert fast == ConcurrencyLimits(groups={"ingest_docs": 7})

    async def test_a_run_with_no_documents_declares_no_group(self) -> None:
        runner = self._runner()
        with Tapestry():
            await runner.process(
                source_connector=_StubSource(0),
                loader=MarkdownLoader(),
                chunking_strategy=FixedSizeChunkingStrategy(chunk_size=8, chunk_overlap=0),
                upserter=IncrementalUpserter(
                    store=_SilentStore(), embedder=StubEmbeddingProvider(dimension=3)
                ),
                max_concurrency=4,
            )
        assert runner._inner_concurrency() is None


class TestOrchestratorWorkersCapIsPerRun(unittest.IsolatedAsyncioTestCase):
    def _orchestrator(self) -> OrchestratorWorkers:
        with Tapestry():
            return OrchestratorWorkers(
                tasks=["a", "b"],
                worker=StubTool(name="w", description="d", result="r"),
                max_concurrency=1,
                _config=KnotConfig(id="orchestrator"),
            )

    async def _plan(
        self,
        orchestrator: OrchestratorWorkers,
        cap: int,
        mine: asyncio.Event,
        theirs: asyncio.Event,
    ) -> ConcurrencyLimits | None:
        with Tapestry():
            await orchestrator.process(
                tasks=["a", "b"],
                worker=StubTool(name="w", description="d", result="r"),
                max_concurrency=cap,
            )
        mine.set()
        await theirs.wait()
        return orchestrator._inner_concurrency()

    async def test_two_concurrent_runs_keep_their_own_caps(self) -> None:
        orchestrator = self._orchestrator()
        gate = _Interleaver()
        first, second = await asyncio.gather(
            asyncio.create_task(
                self._plan(orchestrator, 3, gate.a_has_planned, gate.b_has_planned)
            ),
            asyncio.create_task(
                self._plan(orchestrator, 9, gate.b_has_planned, gate.a_has_planned)
            ),
        )
        assert first == ConcurrencyLimits(groups={"orchestrator_workers": 3})
        assert second == ConcurrencyLimits(groups={"orchestrator_workers": 9})

    async def test_a_run_with_no_tasks_declares_no_group(self) -> None:
        orchestrator = self._orchestrator()
        with Tapestry():
            await orchestrator.process(
                tasks=[],
                worker=StubTool(name="w", description="d", result="r"),
                max_concurrency=5,
            )
        assert orchestrator._inner_concurrency() is None


if __name__ == "__main__":
    unittest.main()
