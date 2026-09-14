"""``DocumentIngest`` — load, chunk, and upsert one source document.

Internal per-document knot for
:class:`~pirn_agents.specializations.document_processing._ingestion_runner.IngestionRunner`'s
fan-out (PIR-867): each document's ETL is independent of every other
document's, so it is one node per document rather than a hand-rolled
``asyncio.gather`` over bare coroutines. A failure on this document is
isolated here — caught and carried back as an errored
:class:`~pirn_agents.specializations.document_processing._document_outcome.DocumentOutcome`
rather than raised — so one bad document never fails the run or its
siblings; the runner folds the isolated outcomes into the final report.

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.document_processing._document_outcome import DocumentOutcome
from pirn_agents.specializations.document_processing.chunking.chunking_strategy import (
    ChunkingStrategy,
)
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
        """Load, chunk, and upsert ``document``, isolating any failure.

        Returns:
            The delta counts on success, or an errored outcome carrying the
            failure's message when this document's ETL raised.
        """
        try:
            loaded = await loader.load(document.data, source_id=document.source_id)
            chunks = await chunking_strategy.chunk(loaded.text)
            plan = await upserter.upsert(document.source_id, chunks)
        except Exception as exc:
            return DocumentOutcome(source_id=document.source_id, error=str(exc))
        return DocumentOutcome(
            source_id=document.source_id,
            embedded=plan.embedded_count,
            unchanged=plan.unchanged_count,
            removed=plan.removed_count,
        )
