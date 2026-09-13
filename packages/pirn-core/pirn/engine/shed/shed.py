from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from pirn.engine.shed.cycle_detector import CycleDetector
from pirn.engine.shed.edge import Edge
from pirn.engine.shed.shed_error import ShedError

if TYPE_CHECKING:
    from pirn.core.knot import Knot


def detect_cycle(knot_ids: list[str], children_by_parent: dict[str, list[str]]) -> bool:
    """Return True if the graph contains a cycle.

    Thin wrapper kept for external callers; delegates to
    ``CycleDetector.detect``.
    """
    return CycleDetector.detect(knot_ids, children_by_parent)


class Shed:
    """An immutable-after-construction view of a knot subgraph.

    Built via Shed.from_terminals(terminals).  There is no mutation API: the
    engine owns every post-construction change to a shed and makes it by
    writing the dicts directly.  Two such writes exist, both id-keyed:
    ``Engine._merge_new_knots`` inserts knots registered mid-run under
    ``extensible=True``, and ``Engine._bind_parameters`` replaces each
    ``Parameter`` with a run-scoped ``bound_copy`` (PIR-802).

    Anything added here must therefore key off ``knot_id`` alone.  A shed
    entry is not guaranteed to be the same *object* the caller's graph holds
    -- ``bound_copy`` returns a new instance under the same id, and
    ``Knot.__eq__``/``__hash__`` are identity, so an identity comparison
    against a graph knot reports a mismatch that is not one (PIR-811).
    """

    __slots__ = ("children_by_parent", "edges_by_child", "knots")

    def __init__(self) -> None:
        self.knots: dict[str, Knot] = {}
        self.edges_by_child: dict[str, list[Edge]] = {}
        self.children_by_parent: dict[str, list[str]] = {}

    @classmethod
    def from_terminals(cls, terminals: list[Knot] | Knot) -> Shed:
        """Build a shed from terminal knot(s) by walking parent references."""
        from pirn.core.knot import Knot as _Knot

        if isinstance(terminals, _Knot):
            terminals = [terminals]

        shed = cls()
        seen: set[int] = set()
        queue: deque[Knot] = deque(terminals)
        while queue:
            knot = queue.popleft()
            if id(knot) in seen:
                continue
            seen.add(id(knot))

            if knot.knot_id in shed.knots and shed.knots[knot.knot_id] is not knot:
                raise ShedError(f"two distinct knots share id {knot.knot_id!r}")
            shed.knots[knot.knot_id] = knot
            shed.children_by_parent.setdefault(knot.knot_id, [])

            edges: list[Edge] = []
            for input_name, parent in knot.parents.items():
                edges.append(Edge(child_id=knot.knot_id, parent_id=parent.knot_id, name=input_name))
                shed.children_by_parent.setdefault(parent.knot_id, []).append(knot.knot_id)
                queue.append(parent)
            shed.edges_by_child[knot.knot_id] = edges

        if CycleDetector.detect(list(shed.knots.keys()), shed.children_by_parent):
            raise ShedError("cycle detected in shed")

        return shed

    def __contains__(self, knot_id: str) -> bool:
        return knot_id in self.knots

    def __len__(self) -> int:
        return len(self.knots)

    def knot(self, knot_id: str) -> Knot:
        try:
            return self.knots[knot_id]
        except KeyError as exc:
            raise ShedError(f"no knot with id {knot_id!r}") from exc

    def parents_of(self, knot_id: str) -> list[Edge]:
        if knot_id not in self.knots:
            raise ShedError(f"no knot with id {knot_id!r}")
        return list(self.edges_by_child.get(knot_id, []))

    def children_of(self, knot_id: str) -> list[str]:
        if knot_id not in self.knots:
            raise ShedError(f"no knot with id {knot_id!r}")
        return list(self.children_by_parent.get(knot_id, []))

    def roots(self) -> list[Knot]:
        return [k for k in self.knots.values() if not self.edges_by_child.get(k.knot_id)]

    def leaves(self) -> list[Knot]:
        return [k for k in self.knots.values() if not self.children_by_parent.get(k.knot_id)]

    def topological_order(self) -> list[str]:
        in_degree: dict[str, int] = {kid: 0 for kid in self.knots}
        for edges in self.edges_by_child.values():
            for e in edges:
                in_degree[e.child_id] += 1
        ready = sorted(kid for kid, in_deg in in_degree.items() if in_deg == 0)
        order: list[str] = []
        while ready:
            knot_id = ready.pop(0)
            order.append(knot_id)
            new_ready: list[str] = []
            for child_id in self.children_by_parent.get(knot_id, []):
                in_degree[child_id] -= 1
                if in_degree[child_id] == 0:
                    new_ready.append(child_id)
            ready = sorted(ready + new_ready)
        if len(order) != len(self.knots):
            raise ShedError("cycle detected during topological sort")
        return order
