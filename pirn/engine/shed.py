"""Shed — the per-run cross-section through the tapestry.

In weaving, a *shed* is the opening the loom forms when specific warp
threads are raised so the weft can pass through for one row.  Each pass
of the weft = one shed = one cross-section of the cloth.

In ``pirn``, the engine forms a ``Shed`` for each run: a derived,
read-only view of which knots will run for this terminal-set, with
parents walked, edges resolved, and a topologically-sorted execution
order ready.  The shed is ephemeral — built per run, consumed by the
walker, discarded when the run ends.

A ``Tapestry`` is the persistent loom-state (which knots exist).  A
``Shed`` is the moment-to-moment "what's about to happen" view.

Built via ``Shed.from_terminals(terminals)`` — never directly.  An
engine internal; not part of the public API.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from pirn.core.knot import Knot


class ShedError(Exception):
    """Raised for structural problems found during shed derivation
    (cycles, id collisions, etc.).  Setup-time errors, allowed to
    propagate."""


class Edge(BaseModel):
    """Wiring connection: ``parent_id`` feeds ``child_id`` at input ``name``."""

    model_config = ConfigDict(frozen=True)

    child_id: str
    parent_id: str
    name: str


class Shed:
    """An immutable-after-construction view of a knot subgraph.

    Build via ``Shed.from_terminals(terminals)``.  After construction the
    instance is read-only by convention — the engine treats it as such,
    and there is no mutation API.

    The class is plain Python (not a Pydantic model) because the
    construction routine builds up internal state during a BFS walk
    (appending to lists in ``children_by_parent``, etc.), which
    Pydantic's frozen models forbid.  Callers should treat the public
    attributes as read-only.
    """

    __slots__ = ("children_by_parent", "edges_by_child", "knots")

    def __init__(self) -> None:
        self.knots: dict[str, Knot] = {}
        self.edges_by_child: dict[str, list[Edge]] = {}
        self.children_by_parent: dict[str, list[str]] = {}

    # ---------------------------------------------------------- factories

    @classmethod
    def from_terminals(cls, terminals: list[Knot] | Knot) -> Shed:
        """Build a shed from terminal knot(s) by walking parent references.

        Discovers every knot reachable.  Raises ``ShedError`` if a cycle
        is detected (cycles can only be created by manipulating
        ``_mutable_parents`` directly; correctly-constructed knots can't
        cycle since parents must exist before children).
        """
        from pirn.core.knot import Knot as _Knot

        if isinstance(terminals, _Knot):
            terminals = [terminals]

        s = cls()

        # BFS from each terminal, collecting knots and edges.
        seen: set[int] = set()  # by id() to avoid hash issues
        queue: deque[Knot] = deque(terminals)
        while queue:
            knot = queue.popleft()
            if id(knot) in seen:
                continue
            seen.add(id(knot))

            # Insert.
            if knot.knot_id in s.knots and s.knots[knot.knot_id] is not knot:
                raise ShedError(f"two distinct knots share id {knot.knot_id!r}")
            s.knots[knot.knot_id] = knot
            s.children_by_parent.setdefault(knot.knot_id, [])

            edges: list[Edge] = []
            for input_name, parent in knot.parents.items():
                edges.append(
                    Edge(
                        child_id=knot.knot_id,
                        parent_id=parent.knot_id,
                        name=input_name,
                    )
                )
                s.children_by_parent.setdefault(parent.knot_id, []).append(knot.knot_id)
                queue.append(parent)
            s.edges_by_child[knot.knot_id] = edges

        # Cycle check.
        if s._has_cycle():
            raise ShedError("cycle detected in shed")

        return s

    # --------------------------------------------------------------- views

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
        """Kahn's algorithm; stable order within each layer for determinism."""
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

    # ----------------------------------------------------- mid-run extension

    def merge_knot(self, knot: Knot) -> bool:
        """Add a knot to the shed mid-run, walking its parent chain.

        Returns ``True`` if the knot was new (and therefore additions
        actually happened), ``False`` if the knot was already present
        (idempotent).

        Raises ``ShedError`` if absorbing the knot would introduce a
        cycle, or if its id collides with a different existing knot.

        Used by the engine in ``extensible`` mode: when a registration
        callback fires mid-run, the engine accumulates new knots and
        merges them between waves.  Newcomers reachable from existing
        roots become ready when their parents complete.
        """
        from pirn.core.knot import Knot as _Knot

        if knot.knot_id in self.knots:
            existing = self.knots[knot.knot_id]
            if existing is knot:
                return False
            raise ShedError(f"two distinct knots share id {knot.knot_id!r}")

        # BFS from this knot to absorb any new ancestors too.
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
                edges.append(
                    Edge(
                        child_id=k.knot_id,
                        parent_id=parent.knot_id,
                        name=input_name,
                    )
                )
                self.children_by_parent.setdefault(parent.knot_id, []).append(k.knot_id)
                queue.append(parent)
            self.edges_by_child[k.knot_id] = edges
            added.add(k.knot_id)

        if self._has_cycle():
            # Roll back so the shed stays usable.
            for kid in added:
                self.knots.pop(kid, None)
                self.edges_by_child.pop(kid, None)
                # Remove from any parent's children list.
                for parent_kids in self.children_by_parent.values():
                    while kid in parent_kids:
                        parent_kids.remove(kid)
                self.children_by_parent.pop(kid, None)
            raise ShedError(f"absorbing knot {knot.knot_id!r} would introduce a cycle")

        return bool(added)

    # -------------------------------------------------------------- internal

    def _has_cycle(self) -> bool:
        WHITE, GREY, BLACK = 0, 1, 2
        color: dict[str, int] = {kid: WHITE for kid in self.knots}

        def visit(kid: str) -> bool:
            color[kid] = GREY
            for child_id in self.children_by_parent.get(kid, []):
                if color[child_id] == GREY:
                    return True
                if color[child_id] == WHITE and visit(child_id):
                    return True
            color[kid] = BLACK
            return False

        for kid in list(color.keys()):
            if color[kid] == WHITE and visit(kid):
                return True
        return False
