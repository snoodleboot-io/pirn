"""``IngestionPipeline`` — the composable RAG ingestion knot (F25-S5 / PIR-585).

A :class:`SubTapestry` that composes the F25 building blocks end to end:

    source connector (S3) -> loader (S1) -> chunking strategy (S2)
        -> incremental upsert-by-hash into a MemoryStore (S4)

Every stage is injected as a provider-neutral component, so the same pipeline
ingests from object storage or a web crawl, parses any supported format, chunks
with any strategy, and re-embeds only changed content. Documents are processed
concurrently (bounded by ``max_concurrency``) and each document's chunks are
embedded in one batched call (F4); see :class:`_IngestionRunner`. The run returns
an :class:`IngestionReport`.

Example::

    pipeline = IngestionPipeline(
        source_connector=ObjectStoreSourceConnector(blob_store=store, prefix="docs/"),
        loader=MarkdownLoader(),
        chunking_strategy=RecursiveCharacterChunkingStrategy(),
        upserter=IncrementalUpserter(store=memory_store, embedder=embedder),
        _config=KnotConfig(id="ingest"),
    )
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.specializations.document_processing._ingestion_runner import _IngestionRunner
from pirn_agents.specializations.document_processing.chunking.chunking_strategy import (
    ChunkingStrategy,
)
from pirn_agents.specializations.document_processing.incremental.incremental_upserter import (
    IncrementalUpserter,
)
from pirn_agents.specializations.document_processing.loaders.loader import Loader
from pirn_agents.specializations.document_processing.sources.source_connector import (
    SourceConnector,
)


class IngestionPipeline(SubTapestry):
    """Compose source → load → chunk → incremental upsert; return an :class:`IngestionReport`."""

    def __init__(
        self,
        *,
        source_connector: Knot | SourceConnector,
        loader: Knot | Loader,
        chunking_strategy: Knot | ChunkingStrategy,
        upserter: Knot | IncrementalUpserter,
        _config: KnotConfig,
        max_concurrency: Knot | int = 8,
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
        max_concurrency: int = 8,
        **_: Any,
    ) -> Knot:
        """Build the inner ETL runner and return it as the pipeline's sink.

        Args:
            source_connector: The source yielding documents to ingest.
            loader: The loader turning source bytes into normalized documents.
            chunking_strategy: The strategy splitting document text into chunks.
            upserter: The incremental upserter embedding/storing only deltas.
            max_concurrency: Maximum documents processed simultaneously.

        Returns:
            The terminal :class:`_IngestionRunner` knot whose output is the
            :class:`IngestionReport`.

        Raises:
            TypeError: If any injected component is the wrong type.
            ValueError: If ``max_concurrency`` is less than 1.
        """
        if not isinstance(source_connector, SourceConnector):
            raise TypeError(
                "IngestionPipeline: source_connector must be a SourceConnector, "
                f"got {type(source_connector).__name__}"
            )
        if not isinstance(loader, Loader):
            raise TypeError(
                f"IngestionPipeline: loader must be a Loader, got {type(loader).__name__}"
            )
        if not isinstance(chunking_strategy, ChunkingStrategy):
            raise TypeError(
                "IngestionPipeline: chunking_strategy must be a ChunkingStrategy, "
                f"got {type(chunking_strategy).__name__}"
            )
        if not isinstance(upserter, IncrementalUpserter):
            raise TypeError(
                "IngestionPipeline: upserter must be an IncrementalUpserter, "
                f"got {type(upserter).__name__}"
            )
        if max_concurrency < 1:
            raise ValueError(
                f"IngestionPipeline: max_concurrency must be >= 1, got {max_concurrency}"
            )
        return _IngestionRunner(
            source_connector=source_connector,
            loader=loader,
            chunking_strategy=chunking_strategy,
            upserter=upserter,
            max_concurrency=max_concurrency,
            _config=KnotConfig(id="ingest-run"),
        )
