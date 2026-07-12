"""``_IngestionRunner`` — the terminal knot that runs the ETL (F25-S5 / PIR-633).

Internal terminal :class:`Knot` for :class:`IngestionPipeline`. It pulls every
:class:`SourceDocument` from the source connector, then for each document runs
load → chunk → incremental upsert. Documents are processed concurrently under a
bounded :class:`asyncio.Semaphore` (the same bounded-concurrency lever
:class:`~pirn_agents.parallel_tool_executor.ParallelToolExecutor` uses), and
each document's chunks are embedded in one batched call by the F4 embedding
provider held inside the upserter. A failure on any one source is isolated and
recorded on the returned :class:`IngestionReport` rather than aborting the run.

Internal API.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.document_processing._document_outcome import _DocumentOutcome
from pirn_agents.specializations.document_processing.chunking.chunking_strategy import (
    ChunkingStrategy,
)
from pirn_agents.specializations.document_processing.incremental.incremental_upserter import (
    IncrementalUpserter,
)
from pirn_agents.specializations.document_processing.ingestion_report import IngestionReport
from pirn_agents.specializations.document_processing.loaders.loader import Loader
from pirn_agents.specializations.document_processing.sources.source_connector import (
    SourceConnector,
)
from pirn_agents.specializations.document_processing.sources.source_document import (
    SourceDocument,
)


class _IngestionRunner(Knot):
    """Fetch, load, chunk, and upsert every source document concurrently."""

    def __init__(
        self,
        *,
        source_connector: Knot | SourceConnector,
        loader: Knot | Loader,
        chunking_strategy: Knot | ChunkingStrategy,
        upserter: Knot | IncrementalUpserter,
        max_concurrency: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_connector=source_connector,
            loader=loader,
            chunking_strategy=chunking_strategy,
            upserter=upserter,
            max_concurrency=max_concurrency,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        source_connector: SourceConnector,
        loader: Loader,
        chunking_strategy: ChunkingStrategy,
        upserter: IncrementalUpserter,
        max_concurrency: int,
        **_: Any,
    ) -> IngestionReport:
        """Run the ETL over every source document and return the aggregate report.

        Args:
            source_connector: The source yielding :class:`SourceDocument`s.
            loader: The loader turning bytes into a normalized document.
            chunking_strategy: The strategy splitting document text into chunks.
            upserter: The incremental upserter embedding/storing the deltas.
            max_concurrency: Maximum documents processed simultaneously.

        Returns:
            The :class:`IngestionReport` aggregating counts and isolated errors.

        Raises:
            ValueError: If ``max_concurrency`` is less than 1.
        """
        if max_concurrency < 1:
            raise ValueError(
                f"_IngestionRunner: max_concurrency must be >= 1, got {max_concurrency}"
            )
        documents = [doc async for doc in source_connector.fetch()]
        semaphore = asyncio.Semaphore(max_concurrency)
        outcomes = await asyncio.gather(
            *(
                self._ingest_one(doc, loader, chunking_strategy, upserter, semaphore)
                for doc in documents
            )
        )
        processed = 0
        embedded = 0
        unchanged = 0
        removed = 0
        errors: list[tuple[str, str]] = list(source_connector.errors)
        for outcome in outcomes:
            if outcome.error is not None:
                errors.append((outcome.source_id, outcome.error))
                continue
            processed += 1
            embedded += outcome.embedded
            unchanged += outcome.unchanged
            removed += outcome.removed
        return IngestionReport(
            documents_processed=processed,
            chunks_embedded=embedded,
            chunks_unchanged=unchanged,
            chunks_removed=removed,
            errors=tuple(errors),
        )

    async def _ingest_one(
        self,
        document: SourceDocument,
        loader: Loader,
        chunking_strategy: ChunkingStrategy,
        upserter: IncrementalUpserter,
        semaphore: asyncio.Semaphore,
    ) -> _DocumentOutcome:
        """Load, chunk, and upsert one document under the concurrency bound."""
        async with semaphore:
            try:
                loaded = await loader.load(document.data, source_id=document.source_id)
                chunks = await chunking_strategy.chunk(loaded.text)
                plan = await upserter.upsert(document.source_id, chunks)
            except Exception as exc:
                return _DocumentOutcome(source_id=document.source_id, error=str(exc))
            return _DocumentOutcome(
                source_id=document.source_id,
                embedded=plan.embedded_count,
                unchanged=plan.unchanged_count,
                removed=plan.removed_count,
            )
