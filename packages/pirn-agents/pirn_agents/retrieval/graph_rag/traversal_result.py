"""``TraversalResult`` — the ``Payload`` a bounded graph traversal hands back.

``TraversalResult`` is ``Payload[TraversalFrame, Subgraph]`` (PIR-874, following
the PIR-868 pattern): ``data`` is the collected
:class:`~pirn_agents.retrieval.graph_rag.subgraph.Subgraph` — the record every
downstream retriever and renderer already consumes, unchanged — and
``metadata`` is the :class:`~pirn_agents.retrieval.graph_rag.traversal_frame.TraversalFrame`
with the bounds it ran under and how far it got. A bare subgraph crossing the
knot boundary said nothing about the budget that shaped it.
"""

from __future__ import annotations

from typing import Any

from pirn.core.payload import Payload
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.retrieval.graph_rag.subgraph import Subgraph
from pirn_agents.retrieval.graph_rag.traversal_budget import TraversalBudget
from pirn_agents.retrieval.graph_rag.traversal_frame import TraversalFrame


class TraversalResult(Payload[TraversalFrame, Subgraph]):
    """The collected subgraph plus the traversal's bounds and reach."""

    def __init__(
        self, subgraph: Subgraph, *, direction: str, budget: TraversalBudget, hops: int
    ) -> None:
        frame = TraversalFrame(
            direction=direction,
            max_depth=budget.max_depth,
            max_fanout=budget.max_fanout,
            max_nodes=budget.max_nodes,
            hops=hops,
            node_count=len(subgraph.nodes),
            edge_count=len(subgraph.edges),
        )
        super().__init__(metadata=frame, data=subgraph)

    @staticmethod
    def _audit_form(value: PirnOpaqueValue) -> Any:
        """Audit a nested value through the ``PirnOpaqueValue`` contract it shares with this one."""
        return value._pirn_audit_dict()

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["subgraph"] = self._audit_form(self.data)
        return audit

    def __eq__(self, other: object) -> bool:
        """Structural equality: same concrete type, equal metadata and data."""
        if type(other) is not type(self):
            return NotImplemented
        return self._metadata == other._metadata and self._data == other._data
