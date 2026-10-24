"""``TraversalFrame`` — lineage metadata for a :class:`TraversalResult`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class TraversalFrame(PirnOpaqueValue):
    """Run-level facts about one bounded neighbourhood traversal.

    The frame half of the ``Payload[TraversalFrame, Subgraph]`` split (PIR-874,
    following PIR-868): the bounds the traversal ran under and how far it got,
    as opposed to the subgraph it collected.

    Attributes
    ----------
    direction:
        The neighbour direction followed.
    max_depth, max_fanout, max_nodes:
        The :class:`TraversalBudget` the traversal ran under.
    hops:
        How many hops actually ran — fewer than ``max_depth`` when the
        frontier emptied first.
    node_count, edge_count:
        The size of the collected subgraph.
    """

    direction: str
    max_depth: int
    max_fanout: int
    max_nodes: int
    hops: int
    node_count: int
    edge_count: int

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "max_depth": self.max_depth,
            "max_fanout": self.max_fanout,
            "max_nodes": self.max_nodes,
            "hops": self.hops,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
        }
