"""Full-pipeline throughput benchmark (F25-S5-T3 / PIR-636).

Runs the composed :class:`IngestionPipeline` over a batch of in-memory stub
documents and records documents-per-second, confirming the end-to-end ETL
(source → load → chunk → incremental upsert) runs concurrently and completes in
bounded time with no real backend.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.document_processing.chunking.recursive_character_chunking_strategy import (
    RecursiveCharacterChunkingStrategy,
)
from pirn_agents.specializations.document_processing.incremental.incremental_upserter import (
    IncrementalUpserter,
)
from pirn_agents.specializations.document_processing.ingestion_pipeline import IngestionPipeline
from pirn_agents.specializations.document_processing.loaders.markdown_loader import (
    MarkdownLoader,
)
from pirn_agents.specializations.document_processing.sources.source_connector import (
    SourceConnector,
)
from pirn_agents.specializations.document_processing.sources.source_document import (
    SourceDocument,
)
from tests.benchmarks.conftest import BenchmarkRecorder
from tests.specializations.conftest import StubEmbeddingProvider


class _DictMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self.entries: dict[str, Mapping[str, Any]] = {}

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self.entries[key] = dict(value)

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return self.entries.get(key)

    async def search(self, query: str, *, top_k: int = 10) -> AsyncIterator[Mapping[str, Any]]:
        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            for entry in list(self.entries.values())[:top_k]:
                yield entry

        return _aiter()

    async def forget(self, key: str) -> None:
        self.entries.pop(key, None)

    async def close(self) -> None:
        return None


class _StubSource(SourceConnector):
    def __init__(self, documents: Sequence[SourceDocument]) -> None:
        self._documents = list(documents)

    async def fetch(self) -> AsyncIterator[SourceDocument]:
        for document in self._documents:
            yield document

    @property
    def errors(self) -> tuple[tuple[str, str], ...]:
        return ()


@pytest.mark.benchmark
async def test_pipeline_throughput(benchmark_recorder: BenchmarkRecorder) -> None:
    doc_count = 100
    body = (
        "Retrieval augmented generation grounds a model in a corpus. "
        "Chunking decides what a retriever can recall.\n\n"
    ) * 5
    documents = [
        SourceDocument.create(source_id=f"doc-{i}", data=f"# Doc {i}\n\n{body}".encode())
        for i in range(doc_count)
    ]
    store = _DictMemoryStore()
    upserter = IncrementalUpserter(store=store, embedder=StubEmbeddingProvider(dimension=8))

    with Tapestry() as tap:
        IngestionPipeline(
            source_connector=_StubSource(documents),
            loader=MarkdownLoader(),
            chunking_strategy=RecursiveCharacterChunkingStrategy(chunk_size=200, chunk_overlap=20),
            upserter=upserter,
            max_concurrency=16,
            _config=KnotConfig(id="ingest"),
        )
    start = time.perf_counter()
    run = await tap.run(RunRequest())
    elapsed = time.perf_counter() - start

    assert run.succeeded
    report = run.outputs["ingest"]
    assert report.documents_processed == doc_count
    assert elapsed < 5.0
    docs_per_sec = doc_count / elapsed if elapsed else 0.0

    benchmark_recorder.record(
        "IngestionPipelineThroughput",
        documents=float(doc_count),
        chunks_embedded=float(report.chunks_embedded),
        seconds=elapsed,
        docs_per_sec=docs_per_sec,
    )


if __name__ == "__main__":
    import unittest

    unittest.main()
