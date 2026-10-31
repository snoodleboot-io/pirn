"""``SeedLookup`` — the ``Payload`` one seed read hands back.

``SeedLookup`` is ``Payload[SeedLookupFrame, GraphNode | None]`` (PIR-874):
``data`` is the store's node, or ``None`` when the id is unknown, and
``metadata`` says which id was asked for and whether it was found.
:class:`~pirn_agents.retrieval.graph_stores.graph_node.GraphNode` is the
store's own record and crosses a dozen signatures as one; the *read* is what
crosses the knot boundary here, and that is what gets the frame.
"""

from __future__ import annotations

from typing import Any

from pirn.core.payload import Payload
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.retrieval.graph_rag.seed_lookup_frame import SeedLookupFrame
from pirn_agents.retrieval.graph_stores.graph_node import GraphNode


class SeedLookup(Payload[SeedLookupFrame, GraphNode | None]):
    """One seed id resolved against the graph store."""

    def __init__(self, node_id: str, node: GraphNode | None) -> None:
        super().__init__(
            metadata=SeedLookupFrame(node_id=node_id, found=node is not None), data=node
        )

    @staticmethod
    def _audit_form(value: PirnOpaqueValue) -> Any:
        """Audit a nested value through the ``PirnOpaqueValue`` contract it shares with this one."""
        return value._pirn_audit_dict()

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["node"] = None if self.data is None else self._audit_form(self.data)
        return audit

    def __eq__(self, other: object) -> bool:
        """Structural equality: same concrete type, equal metadata and data."""
        if type(other) is not type(self):
            return NotImplemented
        return self._metadata == other._metadata and self._data == other._data
