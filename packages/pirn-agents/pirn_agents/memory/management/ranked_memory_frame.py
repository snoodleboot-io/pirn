"""``RankedMemoryFrame`` — the scoring half of a :class:`RankedMemory` (PIR-868, PIR-874)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class RankedMemoryFrame(PirnOpaqueValue):
    """The composite score and normalised components of one ranked recall.

    Attributes
    ----------
    score:
        The weighted composite of the three normalised signals.
    relevance:
        The normalised query-relevance signal in ``[0, 1]``.
    recency:
        The normalised recency signal in ``[0, 1]``.
    importance:
        The normalised importance signal in ``[0, 1]``.
    """

    score: float
    relevance: float
    recency: float
    importance: float

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "score": float(self.score),
            "relevance": float(self.relevance),
            "recency": float(self.recency),
            "importance": float(self.importance),
        }
