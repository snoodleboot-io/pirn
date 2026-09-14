"""``_DocumentOutcome`` — per-document ETL result for the ingestion runner (F25-S5).

A tiny internal carrier returned by
:class:`~pirn_agents.specializations.document_processing._document_ingest._DocumentIngest`
for one source document: either the delta counts (embedded/unchanged/removed)
on success or an ``error`` string on an isolated failure. The runner folds
these into the final :class:`IngestionReport`. A frozen dataclass rather than
a plain class (PIR-867) so it has a pydantic-native schema: it is now a
knot's `process()` return type, and every field is a plain, serialisable
scalar, so no :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue` mixin is
needed.

Internal API.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _DocumentOutcome:
    """Per-document result carried back to the aggregation loop."""

    source_id: str
    embedded: int = 0
    unchanged: int = 0
    removed: int = 0
    error: str | None = None
