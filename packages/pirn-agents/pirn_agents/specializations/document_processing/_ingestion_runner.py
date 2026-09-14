"""``_IngestionRunner`` — the terminal knot that runs the ETL (F25-S5 / PIR-633).

Internal terminal :class:`~pirn_agents.specializations.base.agent_pipeline.AgentPipeline`
for :class:`IngestionPipeline`. It pulls every :class:`SourceDocument` from
the source connector, then wires one
:class:`~pirn_agents.specializations.document_processing._document_ingest._DocumentIngest`
knot per document — each running load → chunk → incremental upsert — into an
:class:`~pirn.nodes.aggregator.Aggregator` (PIR-867; before this, documents
were processed under a hand-rolled ``asyncio.Semaphore`` and
``asyncio.gather``, so no document's ETL had its own lineage row). Bounded
concurrency is now a :class:`~pirn.core.concurrency.concurrency_limits.ConcurrencyLimits`
group cap on the inner run — the same lever
:class:`~pirn_agents.batch.map_agent.MapAgent` uses — rather than a semaphore
held inside the knot. A failure on any one source is isolated by
``_DocumentIngest`` and recorded on the returned :class:`IngestionReport`
rather than aborting the run.

Internal API.
"""

from __future__ import annotations

import functools
from typing import Any, ClassVar

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator

from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.document_processing._document_ingest import _DocumentIngest
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


class _IngestionRunner(AgentPipeline):
    """Fetch every source document and wire one ingest knot per document."""

    _concurrency_group: ClassVar[str] = "ingest_docs"

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
        # Read by `_inner_concurrency` after `process()` recomputes them for
        # this run; initialised here only so the attributes exist before the
        # first `process()` call (mirrors `MapAgent.__init__`).
        self._mutable_live_documents = 0
        self._mutable_max_concurrency = 1
        super().__init__(
            source_connector=source_connector,
            loader=loader,
            chunking_strategy=chunking_strategy,
            upserter=upserter,
            max_concurrency=max_concurrency,
            _config=_config,
            **kwargs,
        )

    def _inner_concurrency(self) -> ConcurrencyLimits | None:
        """The document group's cap, or ``None`` when nothing runs.

        Read by ``SubTapestry._run_inner`` after ``process()`` has already
        set ``self._mutable_live_documents`` / ``self._mutable_max_concurrency``
        — the same "compute during process(), consult after" ordering
        ``MapAgent._inner_concurrency`` uses.
        """
        if self._mutable_live_documents <= 0:
            return None
        return ConcurrencyLimits(groups={self._concurrency_group: self._mutable_max_concurrency})

    async def process(
        self,
        source_connector: SourceConnector,
        loader: Loader,
        chunking_strategy: ChunkingStrategy,
        upserter: IncrementalUpserter,
        max_concurrency: int,
        **_: Any,
    ) -> Knot:
        """Fetch every source document and wire one ingest knot per document.

        Args:
            source_connector: The source yielding :class:`SourceDocument`s.
            loader: The loader turning bytes into a normalized document.
            chunking_strategy: The strategy splitting document text into chunks.
            upserter: The incremental upserter embedding/storing the deltas.
            max_concurrency: Maximum documents processed simultaneously.

        Returns:
            The sink of the inner pipeline: a ``Parameter`` defaulting to an
            empty :class:`IngestionReport` when the source yields no
            documents, or an :class:`Aggregator` over one ``_DocumentIngest``
            per document whose output is the aggregate :class:`IngestionReport`.

        Raises:
            ValueError: If ``max_concurrency`` is less than 1.
        """
        if max_concurrency < 1:
            raise ValueError(
                f"_IngestionRunner: max_concurrency must be >= 1, got {max_concurrency}"
            )
        documents = [doc async for doc in source_connector.fetch()]
        source_errors: tuple[tuple[str, str], ...] = tuple(source_connector.errors)
        self._mutable_live_documents = len(documents)
        self._mutable_max_concurrency = max_concurrency
        if not documents:
            return Parameter(
                "empty_report",
                IngestionReport,
                default=IngestionReport(
                    documents_processed=0,
                    chunks_embedded=0,
                    chunks_unchanged=0,
                    chunks_removed=0,
                    errors=source_errors,
                ),
                _config=KnotConfig(id="empty_report"),
            )
        per_document: dict[str, Knot] = {
            f"doc_{index}": _DocumentIngest(
                document=document,
                loader=loader,
                chunking_strategy=chunking_strategy,
                upserter=upserter,
                _config=KnotConfig(id=f"ingest_{index}", concurrency_group=self._concurrency_group),
            )
            for index, document in enumerate(documents)
        }
        return Aggregator(
            combine=functools.partial(self._build_report, len(documents), source_errors),
            _config=KnotConfig(id="report"),
            **per_document,
        )

    @staticmethod
    def _build_report(
        count: int,
        source_errors: tuple[tuple[str, str], ...],
        **outcomes: _DocumentOutcome,
    ) -> IngestionReport:
        """Fold every document's outcome (in document order) into the aggregate report."""
        processed = 0
        embedded = 0
        unchanged = 0
        removed = 0
        errors: list[tuple[str, str]] = list(source_errors)
        for index in range(count):
            outcome = outcomes[f"doc_{index}"]
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
