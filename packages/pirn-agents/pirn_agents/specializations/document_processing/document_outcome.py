"""``DocumentOutcome`` — per-document ETL result for the ingestion runner (F25-S5).

Returned by
:class:`~pirn_agents.specializations.document_processing.document_ingest.DocumentIngest`
for one source document: either the delta counts (embedded/unchanged/removed)
on success or an ``error`` string on an isolated failure. The runner folds
these into the final :class:`IngestionReport`.

``DocumentOutcome`` is ``Payload[DocumentOutcomeFrame, str]`` (PIR-868 pattern,
applied by PIR-874; ADR agents-speaks-core WS6b): the frame carries the delta
counts and error, ``data`` is the ``source_id`` the outcome is about. The
constructor keeps the named fields; read them back as ``metadata.<field>`` and
``data``.

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.document_processing.document_outcome_frame import (
    DocumentOutcomeFrame,
)


class DocumentOutcome(AgentResult[DocumentOutcomeFrame, str]):
    """Per-document result carried back to the aggregation loop."""

    def __init__(
        self,
        source_id: str,
        embedded: int = 0,
        unchanged: int = 0,
        removed: int = 0,
        error: str | None = None,
    ) -> None:
        frame = DocumentOutcomeFrame(
            embedded=embedded, unchanged=unchanged, removed=removed, error=error
        )
        super().__init__(metadata=frame, data=source_id)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["source_id"] = self.data
        return audit
