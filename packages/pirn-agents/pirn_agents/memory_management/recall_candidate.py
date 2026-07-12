"""``RecallCandidate`` — a record paired with its raw query-relevance score.

Ranked recall takes candidates the retrieval layer already scored: a
:class:`~pirn_agents.memory_management.memory_record.MemoryRecord` and the
``relevance`` score a vector/hybrid search (F4) assigned it for the query. The
scale of ``relevance`` is backend-defined (cosine, BM25, RRF, …); the ranker
normalises it before fusing, so this value object stays scale-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.memory_management.memory_record import MemoryRecord


@dataclass(frozen=True)
class RecallCandidate(PirnOpaqueValue):
    """A memory record and its raw, backend-defined relevance score.

    Attributes
    ----------
    record:
        The candidate memory record.
    relevance:
        The raw relevance score from the retrieval backend (any scale).
    """

    record: MemoryRecord
    relevance: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.record, MemoryRecord):
            raise TypeError(
                f"RecallCandidate: record must be a MemoryRecord, got {type(self.record).__name__}"
            )
        if not isinstance(self.relevance, (int, float)) or isinstance(self.relevance, bool):
            raise TypeError("RecallCandidate: relevance must be a real number")

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"record": self.record.id, "relevance": float(self.relevance)}
