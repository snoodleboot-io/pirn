"""``_DocumentOutcome`` — per-document ETL result for the ingestion runner (F25-S5).

A tiny internal carrier returned by ``_IngestionRunner._ingest_one`` for one
source document: either the delta counts (embedded/unchanged/removed) on success
or an ``error`` string on an isolated failure. The runner folds these into the
final :class:`IngestionReport`.

Internal API.
"""

from __future__ import annotations


class _DocumentOutcome:
    """Per-document result carried back to the aggregation loop."""

    def __init__(
        self,
        *,
        source_id: str,
        embedded: int = 0,
        unchanged: int = 0,
        removed: int = 0,
        error: str | None = None,
    ) -> None:
        self.source_id = source_id
        self.embedded = embedded
        self.unchanged = unchanged
        self.removed = removed
        self.error = error
