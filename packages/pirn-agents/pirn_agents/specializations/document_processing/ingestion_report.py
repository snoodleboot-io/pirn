"""``IngestionReport`` — the aggregate outcome of an ingestion run (F25-S5 / PIR-585).

Summarizes one :class:`IngestionPipeline` run: how many documents were processed
and, across them, how many chunks were embedded (new/changed), left unchanged
(the incremental win), and removed, plus the isolated per-source failures so a
caller can act on them without the run having crashed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class IngestionReport(PirnOpaqueValue):
    """Aggregate counters and errors for one ingestion run.

    Attributes
    ----------
    documents_processed:
        Number of source documents successfully loaded, chunked, and upserted.
    chunks_embedded:
        Total new/changed chunks embedded across all documents.
    chunks_unchanged:
        Total chunks skipped because their content hash was already indexed.
    chunks_removed:
        Total stale chunk records deleted across all documents.
    errors:
        ``(source_id, error)`` pairs for sources that failed to fetch or ingest;
        each is isolated so it never aborts the run.
    """

    documents_processed: int
    chunks_embedded: int
    chunks_unchanged: int
    chunks_removed: int
    errors: tuple[tuple[str, str], ...] = field(default_factory=tuple)
