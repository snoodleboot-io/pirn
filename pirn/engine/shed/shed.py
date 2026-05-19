from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from pirn.engine.shed.edge import Edge
from pirn.engine.shed.shed_error import ShedError

if TYPE_CHECKING:
    from pirn.core.knot import Knot


class CycleDetector:
    """DFS-based cycle detector for knot subgraphs.

    Stateless utility wrapping the three-color DFS: 0=white, 1=grey,
    2=black.  Exposed as static methods so call sites do not need to
    instantiate the detector.
    """

    @staticmethod
    def _visit_dfs(
        kid: str,
        color: dict[str, int],
        children_by_parent: dict[str, list[str]],
    ) -> bool:
        """Single DFS step for cycle detection.  0=white, 1=grey, 2=black."""
        color[kid] = 1
        for child_id in children_by_parent.get(kid, []):
            state = color.get(child_id, 0)
            if state == 1:
                return True
            if state == 0 and CycleDetector._visit_dfs(child_id, color, children_by_parent):
                return True
        color[kid] = 2
        return False

    @staticmethod
    def detect(knot_ids: list[str], children_by_parent: dict[str, list[str]]) -> bool:
        """Return True if the graph contains a cycle."""
        color: dict[str, int] = {kid: 0 for kid in knot_ids}
        for kid in list(color.keys()):
            if color[kid] == 0 and CycleDetector._visit_dfs(kid, color, children_by_parent):
                return True
        return False


def detect_cycle(knot_ids: list[str], children_by_parent: dict[str, list[str]]) -> bool:
    """Return True if the graph contains a cycle.

    Thin wrapper kept for external callers; delegates to
    ``CycleDetector.detect``.
    """
    return CycleDetector.detect(knot_ids, children_by_parent)


class Shed:
    """An immutable-after-construction view of a knot subgraph.

    Built via Shed.from_terminals(terminals).  The engine treats this as
    read-only after construction; there is no mutation API beyond
    merge_knot (used in extensible mode between waves).
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

    def merge_knot(self, knot: Knot) -> bool:
        """Add a knot to the shed mid-run, walking its parent chain."""
        from pirn.core.knot import Knot as _Knot

        if knot.knot_id in self.knots:
            existing = self.knots[knot.knot_id]
            if existing is knot:
                return False
            raise ShedError(f"two distinct knots share id {knot.knot_id!r}")

        added: set[str] = set()
        queue: deque[Knot] = deque([knot])
        while queue:
            candidate = queue.popleft()
            if candidate.knot_id in self.knots:
                if self.knots[candidate.knot_id] is not candidate:
                    raise ShedError(f"two distinct knots share id {candidate.knot_id!r}")
                continue
            assert isinstance(candidate, _Knot)
            self.knots[candidate.knot_id] = candidate
            self.children_by_parent.setdefault(candidate.knot_id, [])
            edges: list[Edge] = []
            for input_name, parent in candidate.parents.items():
                edges.append(
                    Edge(child_id=candidate.knot_id, parent_id=parent.knot_id, name=input_name)
                )
                self.children_by_parent.setdefault(parent.knot_id, []).append(candidate.knot_id)
                queue.append(parent)
            self.edges_by_child[candidate.knot_id] = edges
            added.add(candidate.knot_id)

        if CycleDetector.detect(list(self.knots.keys()), self.children_by_parent):
            for kid in added:
                self.knots.pop(kid, None)
                self.edges_by_child.pop(kid, None)
                for parent_kids in self.children_by_parent.values():
                    while kid in parent_kids:
                        parent_kids.remove(kid)
                self.children_by_parent.pop(kid, None)
            raise ShedError(f"absorbing knot {knot.knot_id!r} would introduce a cycle")

        return bool(added)
