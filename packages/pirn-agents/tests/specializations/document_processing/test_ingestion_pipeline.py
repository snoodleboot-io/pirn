"""End-to-end tests for :class:`IngestionPipeline` (F25-S5 / PIR-585, PIR-636).

Runs the composed pipeline over stub source/loader/chunker/store doubles and
verifies the stored output and the returned :class:`IngestionReport`, plus
per-document failure isolation and constructor/type validation. No real service
or backend is touched.
"""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.document_processing.chunking.fixed_size_chunking_strategy import (
    FixedSizeChunkingStrategy,
)
from pirn_agents.specializations.document_processing.incremental.incremental_upserter import (
    IncrementalUpserter,
)
from pirn_agents.specializations.document_processing.ingestion_pipeline import IngestionPipeline
from pirn_agents.specializations.document_processing.ingestion_report import IngestionReport
from pirn_agents.specializations.document_processing.loaders.loaded_document import (
    LoadedDocument,
)
from pirn_agents.specializations.document_processing.loaders.loader import Loader
from pirn_agents.specializations.document_processing.loaders.markdown_loader import (
    MarkdownLoader,
)
from pirn_agents.specializations.document_processing.sources.source_connector import (
    SourceConnector,
)
from pirn_agents.specializations.document_processing.sources.source_document import (
    SourceDocument,
)
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


class _ExplodingLoader(Loader):
    """Loader that raises for a specific source id, else returns its text."""

    def __init__(self, *, fail_source_id: str) -> None:
        self._fail = fail_source_id

    async def load(self, data: bytes, *, source_id: str | None = None) -> LoadedDocument:
        if source_id == self._fail:
            raise ValueError("boom")
        return LoadedDocument(text=data.decode("utf-8"), source_id=source_id)


def _docs() -> list[SourceDocument]:
    return [
        SourceDocument.create(source_id="d1", data=b"# A\n\nHello world content here."),
        SourceDocument.create(source_id="d2", data=b"Second document body text."),
    ]


class TestIngestionPipelineEndToEnd(unittest.IsolatedAsyncioTestCase):
    async def test_runs_and_stores_output(self) -> None:
        store = _DictMemoryStore()
        upserter = IncrementalUpserter(store=store, embedder=StubEmbeddingProvider(dimension=3))
        with Tapestry() as tap:
            IngestionPipeline(
                source_connector=_StubSource(_docs()),
                loader=MarkdownLoader(),
                chunking_strategy=FixedSizeChunkingStrategy(chunk_size=8, chunk_overlap=0),
                upserter=upserter,
                _config=KnotConfig(id="ingest"),
            )
        run = await tap.run(RunRequest())
        assert run.succeeded
        report = run.outputs["ingest"]
        assert isinstance(report, IngestionReport)
        assert report.documents_processed == 2
        assert report.chunks_embedded > 0
        assert report.errors == ()
        # Stored output: a manifest per doc and chunk records with embeddings.
        assert "d1:manifest" in store.entries
        assert "d2:manifest" in store.entries
        chunk_records = [v for k, v in store.entries.items() if not k.endswith(":manifest")]
        assert chunk_records
        assert all("embedding" in record for record in chunk_records)

    async def test_reingest_unchanged_embeds_nothing(self) -> None:
        store = _DictMemoryStore()
        upserter = IncrementalUpserter(store=store, embedder=StubEmbeddingProvider(dimension=3))

        def _pipeline() -> None:
            IngestionPipeline(
                source_connector=_StubSource(_docs()),
                loader=MarkdownLoader(),
                chunking_strategy=FixedSizeChunkingStrategy(chunk_size=8, chunk_overlap=0),
                upserter=upserter,
                _config=KnotConfig(id="ingest"),
            )

        with Tapestry() as tap:
            _pipeline()
        await tap.run(RunRequest())
        with Tapestry() as tap2:
            _pipeline()
        run2 = await tap2.run(RunRequest())
        report = run2.outputs["ingest"]
        assert report.chunks_embedded == 0
        assert report.chunks_unchanged > 0

    async def test_per_document_failure_isolated(self) -> None:
        store = _DictMemoryStore()
        upserter = IncrementalUpserter(store=store, embedder=StubEmbeddingProvider(dimension=3))
        with Tapestry() as tap:
            IngestionPipeline(
                source_connector=_StubSource(_docs()),
                loader=_ExplodingLoader(fail_source_id="d1"),
                chunking_strategy=FixedSizeChunkingStrategy(chunk_size=8, chunk_overlap=0),
                upserter=upserter,
                _config=KnotConfig(id="ingest"),
            )
        run = await tap.run(RunRequest())
        assert run.succeeded
        report = run.outputs["ingest"]
        assert report.documents_processed == 1  # only d2 succeeded
        assert report.errors == (("d1", "boom"),)

    async def test_serial_concurrency_still_processes_all(self) -> None:
        store = _DictMemoryStore()
        upserter = IncrementalUpserter(store=store, embedder=StubEmbeddingProvider(dimension=3))
        with Tapestry() as tap:
            IngestionPipeline(
                source_connector=_StubSource(_docs()),
                loader=MarkdownLoader(),
                chunking_strategy=FixedSizeChunkingStrategy(chunk_size=8, chunk_overlap=0),
                upserter=upserter,
                max_concurrency=1,
                _config=KnotConfig(id="ingest"),
            )
        run = await tap.run(RunRequest())
        assert run.outputs["ingest"].documents_processed == 2


class TestIngestionPipelineValidation(unittest.IsolatedAsyncioTestCase):
    def _pipeline(self) -> IngestionPipeline:
        store = _DictMemoryStore()
        with Tapestry():
            return IngestionPipeline(
                source_connector=_StubSource([]),
                loader=MarkdownLoader(),
                chunking_strategy=FixedSizeChunkingStrategy(),
                upserter=IncrementalUpserter(store=store, embedder=StubEmbeddingProvider()),
                _config=KnotConfig(id="ingest"),
            )

    async def test_rejects_wrong_loader(self) -> None:
        pipeline = self._pipeline()
        store = _DictMemoryStore()
        with self.assertRaisesRegex(TypeError, "loader must be a Loader"):
            await pipeline.process(
                source_connector=_StubSource([]),
                loader=object(),  # type: ignore[arg-type]
                chunking_strategy=FixedSizeChunkingStrategy(),
                upserter=IncrementalUpserter(store=store, embedder=StubEmbeddingProvider()),
            )

    async def test_rejects_bad_concurrency(self) -> None:
        pipeline = self._pipeline()
        store = _DictMemoryStore()
        with self.assertRaisesRegex(ValueError, "max_concurrency"):
            await pipeline.process(
                source_connector=_StubSource([]),
                loader=MarkdownLoader(),
                chunking_strategy=FixedSizeChunkingStrategy(),
                upserter=IncrementalUpserter(store=store, embedder=StubEmbeddingProvider()),
                max_concurrency=0,
            )


if __name__ == "__main__":
    unittest.main()
