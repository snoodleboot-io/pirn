from __future__ import annotations

from collections import deque
from collections.abc import Iterator
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

    The walk is **iterative**.  It used to recurse one Python frame per graph
    level, which capped usable graph depth at roughly 980 knots — the engine
    validates the graph on every run, so a deep chain died with a
    ``RecursionError`` before executing.  ``LoopSubTapestry`` chains iterations
    through parent edges, one level per iteration, so an open-ended
    conversational loop hit that ceiling in the ordinary course of doing its
    job.  Measured: DFS depth tracks iteration count 1:1.  See PIR-766/PIR-763.
    """

    @staticmethod
    def detect(knot_ids: list[str], children_by_parent: dict[str, list[str]]) -> bool:
        """Return True if the graph contains a cycle.

        Iterative three-colour DFS: 0=white (unvisited), 1=grey (on the current
        path), 2=black (fully explored).  An edge to a grey node closes a cycle.

        Args:
            knot_ids: The nodes to use as DFS roots.
            children_by_parent: Adjacency mapping.  Children absent from
                ``knot_ids`` are treated as white and explored, matching the
                previous recursive implementation.

        Returns:
            True if the graph contains a cycle reachable from any root.
        """
        color: dict[str, int] = {kid: 0 for kid in knot_ids}
        for root in list(color.keys()):
            if color[root] != 0:
                continue
            color[root] = 1
            # Each frame is the node plus its *partially consumed* child
            # iterator, which is what lets the walk resume where it left off
            # after descending — the explicit stand-in for a call stack.
            stack: list[tuple[str, Iterator[str]]] = [
                (root, iter(children_by_parent.get(root, [])))
            ]
            while stack:
                node, children = stack[-1]
                descended = False
                for child_id in children:
                    state = color.get(child_id, 0)
                    if state == 1:
                        return True
                    if state == 0:
                        color[child_id] = 1
                        stack.append((child_id, iter(children_by_parent.get(child_id, []))))
                        descended = True
                        break
                if not descended:
                    color[node] = 2
                    stack.pop()
        return False


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
