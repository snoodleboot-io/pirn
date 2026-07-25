"""``RankedMemory`` — one scored result of ranked recall.

The output unit of :class:`~pirn_agents.memory_management.ranked_recall.RankedRecall`:
the recalled :class:`~pirn_agents.memory_management.memory_record.MemoryRecord`, its
fused composite ``score``, and the three normalised component signals that
produced it. Surfacing the components (not just the total) keeps ranking
explainable and testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.memory_management.memory_record import MemoryRecord


@dataclass(frozen=True)
class RankedMemory(PirnOpaqueValue):
    """A recalled record with its composite score and normalised components.

    Attributes
    ----------
    record:
        The recalled memory record.
    score:
        The weighted composite of the three normalised signals.
    relevance:
        The normalised query-relevance signal in ``[0, 1]``.
    recency:
        The normalised recency signal in ``[0, 1]``.
    importance:
        The normalised importance signal in ``[0, 1]``.
    """

    record: MemoryRecord
    score: float
    relevance: float
    recency: float
    importance: float

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "record": self.record.id,
            "score": float(self.score),
            "relevance": float(self.relevance),
            "recency": float(self.recency),
            "importance": float(self.importance),
        }
