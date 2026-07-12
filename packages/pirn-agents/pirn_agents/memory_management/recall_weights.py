"""``RecallWeights`` — the tunable relevance/recency/importance blend for recall.

Ranked recall fuses three signals into one score; :class:`RecallWeights` holds
their non-negative coefficients so the blend is configurable and provider-neutral
(the same weights apply over any hybrid-retrieval backend). Defaults weight all
three equally. Weights are used as-is — the ranker normalises each *signal* into a
common range, so the weights alone govern their relative influence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class RecallWeights(PirnOpaqueValue):
    """Non-negative fusion coefficients for the three recall signals.

    Attributes
    ----------
    relevance:
        Weight on query-relevance (vector/rerank similarity).
    recency:
        Weight on how recently the memory was created or accessed.
    importance:
        Weight on the record's caller-assigned importance.
    """

    relevance: float = 1.0
    recency: float = 1.0
    importance: float = 1.0

    def __post_init__(self) -> None:
        for name in ("relevance", "recency", "importance"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TypeError(f"RecallWeights: {name} must be a real number")
            if value < 0:
                raise ValueError(f"RecallWeights: {name} must be >= 0, got {value!r}")

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "relevance": float(self.relevance),
            "recency": float(self.recency),
            "importance": float(self.importance),
        }
