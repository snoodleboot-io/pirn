from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from pirn.engine.shed.edge import Edge
from pirn.engine.shed.shed_error import ShedError

if TYPE_CHECKING:
    from pirn.core.knot import Knot


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
        if state == 0 and _visit_dfs(child_id, color, children_by_parent):
            return True
    color[kid] = 2
    return False


def detect_cycle(knot_ids: list[str], children_by_parent: dict[str, list[str]]) -> bool:
    """Return True if the graph contains a cycle."""
    color: dict[str, int] = {kid: 0 for kid in knot_ids}
    for kid in list(color.keys()):
        if color[kid] == 0 and _visit_dfs(kid, color, children_by_parent):
            return True
    return False


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

        s = cls()
        seen: set[int] = set()
        queue: deque[Knot] = deque(terminals)
        while queue:
            knot = queue.popleft()
            if id(knot) in seen:
                continue
            seen.add(id(knot))

            if knot.knot_id in s.knots and s.knots[knot.knot_id] is not knot:
                raise ShedError(f"two distinct knots share id {knot.knot_id!r}")
            s.knots[knot.knot_id] = knot
            s.children_by_parent.setdefault(knot.knot_id, [])

            edges: list[Edge] = []
            for input_name, parent in knot.parents.items():
                edges.append(Edge(child_id=knot.knot_id, parent_id=parent.knot_id, name=input_name))
                s.children_by_parent.setdefault(parent.knot_id, []).append(knot.knot_id)
                queue.append(parent)
            s.edges_by_child[knot.knot_id] = edges

        if detect_cycle(list(s.knots.keys()), s.children_by_parent):
            raise ShedError("cycle detected in shed")

        return s

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
        ready = sorted(kid for kid, d in in_degree.items() if d == 0)
        order: list[str] = []
        while ready:
            kid = ready.pop(0)
            order.append(kid)
            new_ready: list[str] = []
            for child_id in self.children_by_parent.get(kid, []):
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
            k = queue.popleft()
            if k.knot_id in self.knots:
                if self.knots[k.knot_id] is not k:
                    raise ShedError(f"two distinct knots share id {k.knot_id!r}")
                continue
            assert isinstance(k, _Knot)
            self.knots[k.knot_id] = k
            self.children_by_parent.setdefault(k.knot_id, [])
            edges: list[Edge] = []
            for input_name, parent in k.parents.items():
                edges.append(Edge(child_id=k.knot_id, parent_id=parent.knot_id, name=input_name))
                self.children_by_parent.setdefault(parent.knot_id, []).append(k.knot_id)
                queue.append(parent)
            self.edges_by_child[k.knot_id] = edges
            added.add(k.knot_id)

        if detect_cycle(list(self.knots.keys()), self.children_by_parent):
            for kid in added:
                self.knots.pop(kid, None)
                self.edges_by_child.pop(kid, None)
                for parent_kids in self.children_by_parent.values():
                    while kid in parent_kids:
                        parent_kids.remove(kid)
                self.children_by_parent.pop(kid, None)
            raise ShedError(f"absorbing knot {knot.knot_id!r} would introduce a cycle")

        return bool(added)
