"""``CandidateRoutingFrame`` — lineage metadata for a :class:`CandidateRouting`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class CandidateRoutingFrame(PirnOpaqueValue):
    """How a set of route candidates came to be ordered.

    Attributes
    ----------
    order:
        The candidate names in the order chosen, highest confidence first.
    confidences:
        The confidence per candidate name the ordering was made from; empty
        when the ordering was handed over rather than computed.
    """

    order: tuple[str, ...]
    confidences: Mapping[str, float] = field(default_factory=dict[str, float])

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"order": list(self.order), "confidences": dict(self.confidences)}
