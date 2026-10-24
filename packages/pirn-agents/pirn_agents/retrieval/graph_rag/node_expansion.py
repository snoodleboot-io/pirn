"""``NodeExpansion`` — the ``Payload`` one frontier expansion hands back.

``NodeExpansion`` is ``Payload[NodeExpansionFrame, tuple[GraphNeighbor, ...]]``
(PIR-874): ``data`` is the neighbours the store returned, in its order, and
``metadata`` records the node, direction and cap they were asked for.
:class:`~pirn_agents.retrieval.graph_stores.graph_neighbor.GraphNeighbor` is
the store's own record; the *query* is what crosses the knot boundary.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.payload import Payload
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.retrieval.graph_rag.node_expansion_frame import NodeExpansionFrame
from pirn_agents.retrieval.graph_stores.graph_neighbor import GraphNeighbor


class NodeExpansion(Payload[NodeExpansionFrame, tuple[GraphNeighbor, ...]]):
    """One node's neighbourhood, as the store answered it."""

    def __init__(
        self, node_id: str, direction: str, limit: int, neighbors: Sequence[GraphNeighbor]
    ) -> None:
        found = tuple(neighbors)
        super().__init__(
            metadata=NodeExpansionFrame(
                node_id=node_id, direction=direction, limit=limit, neighbor_count=len(found)
            ),
            data=found,
        )

    @staticmethod
    def _audit_form(value: PirnOpaqueValue) -> Any:
        """Audit a nested value through the ``PirnOpaqueValue`` contract it shares with this one."""
        return value._pirn_audit_dict()

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["neighbors"] = [self._audit_form(neighbor) for neighbor in self.data]
        return audit

    def __eq__(self, other: object) -> bool:
        """Structural equality: same concrete type, equal metadata and data."""
        if type(other) is not type(self):
            return NotImplemented
        return self._metadata == other._metadata and self._data == other._data
