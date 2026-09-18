"""``DocumentIngest`` — load, chunk, and upsert one source document.

Internal per-document knot for
:class:`~pirn_agents.specializations.document_processing.ingestion_runner.IngestionRunner`'s
fan-out (PIR-867): each document's ETL is independent of every other
document's, so it is one node per document rather than a hand-rolled
``asyncio.gather`` over bare coroutines. A failure on this document *raises*:
the engine records it as this knot's ``Err`` with its type and traceback, and
:class:`~pirn_agents.specializations.document_processing.document_ingest_fold.DocumentIngestFold`
— wired over it with ``RECEIVE_ERRORS`` — turns that ``Result`` into the
errored :class:`~pirn_agents.specializations.document_processing.document_outcome.DocumentOutcome`
the runner folds into the final report. The isolation is unchanged (one bad
document never fails the run or its siblings); what used to be a hand-rolled
``except Exception`` that discarded the type and traceback is now the engine's
own ``Result`` (PIR-873).

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.document_processing.chunking.chunking_strategy import (
    ChunkingStrategy,
)
from pirn_agents.specializations.document_processing.document_outcome import DocumentOutcome
from pirn_agents.specializations.document_processing.incremental.incremental_upserter import (
    IncrementalUpserter,
)
from pirn_agents.specializations.document_processing.loaders.loader import Loader
from pirn_agents.specializations.document_processing.sources.source_document import (
    SourceDocument,
)


class DocumentIngest(Knot):
    """Load, chunk, and upsert one document; isolate its failure as an outcome."""

    def __init__(
        self,
        *,
        document: Knot | SourceDocument,
        loader: Knot | Loader,
        chunking_strategy: Knot | ChunkingStrategy,
        upserter: Knot | IncrementalUpserter,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            document=document,
            loader=loader,
            chunking_strategy=chunking_strategy,
            upserter=upserter,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        document: SourceDocument,
        loader: Loader,
        chunking_strategy: ChunkingStrategy,
        upserter: IncrementalUpserter,
        **_: Any,
    ) -> DocumentOutcome:
        """Load, chunk, and upsert ``document``.

        Args:
            document: The source document to ingest.
            loader: The loader turning its bytes into normalized text.
            chunking_strategy: The strategy splitting that text into chunks.
            upserter: The incremental upserter embedding and storing the deltas.

        Returns:
            This document's delta counts.

        Raises:
            Exception: Whatever the loader, chunker or upserter raises. The
                engine records it as this knot's ``Err``; ``DocumentIngestFold``
                turns that into an errored outcome so the siblings still run.
        """
        loaded = await loader.load(document.data, source_id=document.source_id)
        chunks = await chunking_strategy.chunk(loaded.text)
        plan = await upserter.upsert(document.source_id, chunks)
        return DocumentOutcome(
            source_id=document.source_id,
            embedded=plan.embedded_count,
            unchanged=plan.unchanged_count,
            removed=plan.removed_count,
        )
