"""``NodeExpansionFrame`` — lineage metadata for a :class:`NodeExpansion`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class NodeExpansionFrame(PirnOpaqueValue):
    """What one neighbourhood query asked for and how much came back.

    Attributes
    ----------
    node_id:
        The frontier node that was expanded.
    direction:
        The neighbour direction followed.
    limit:
        The per-node fanout cap the query was given.
    neighbor_count:
        How many neighbours the store returned.
    """

    node_id: str
    direction: str
    limit: int
    neighbor_count: int

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "direction": self.direction,
            "limit": self.limit,
            "neighbor_count": self.neighbor_count,
        }
