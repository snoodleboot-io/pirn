"""Unresolved-parent bookkeeping for the engine's admission loop."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirn.engine.shed.shed import Shed


class DependencyTracker:
    """Knows, for every knot in a shed, how many of its parents are unresolved.

    A knot is *ready* when that count reaches zero.  The engine reports each
    knot it resolves (ran, skipped or failed) through ``resolve``, which
    returns exactly the children that became ready as a result.  Readiness is
    therefore found in time proportional to the edges touched, not by
    rescanning the whole topological order on every step: the wave loop this
    replaced did the latter, which made a chain of *n* knots cost O(n^2)
    (PIR-841).

    The tracker also owns the two coordinates that make a run's reported
    order independent of the order knots happen to finish in:

    * ``level`` -- the knot's depth: ``0`` for a root, otherwise one more than
      its deepest parent.  For a static graph this is exactly the wave the
      old loop would have run the knot in.
    * ``topo_index`` -- the knot's position in ``Shed.topological_order()``,
      which sorts ties by knot id.

    ``sort_key`` combines them into the order lineage, exceptions, skips and
    outputs are reported in, reproducing the wave loop's order exactly.

    The tracker reads edges from the shed it was built over and never writes
    to it.  Knots merged into the shed mid-run are announced with ``merge``.
    """

    def __init__(self, shed: Shed) -> None:
        """Index *shed*: parent counts, levels and topological positions.

        Args:
            shed: The run's shed.  Must be acyclic, which ``Shed`` guarantees.
        """
        self._shed = shed
        self._unresolved: dict[str, int] = {}
        self._levels: dict[str, int] = {}
        self._topo_index: dict[str, int] = {}
        self._resolved: set[str] = set()
        order = shed.topological_order()
        self._reindex(order)
        for knot_id in order:
            self._track(knot_id, floor=0)

    def initially_ready(self) -> list[str]:
        """Return the knots with no unresolved parent, in topological order.

        Returns:
            Every tracked, unresolved knot whose parents have all resolved.
        """
        ready = [
            knot_id
            for knot_id, count in self._unresolved.items()
            if count == 0 and knot_id not in self._resolved
        ]
        return self._in_topo_order(ready)

    def resolve(self, knot_id: str) -> list[str]:
        """Record that *knot_id* has a result and release its children.

        Args:
            knot_id: A tracked knot that has not been resolved before.

        Returns:
            The children that became ready because of this resolution, in
            topological order.  A child listed once per edge to *knot_id* is
            still returned once.
        """
        self._resolved.add(knot_id)
        newly_ready: list[str] = []
        for child_id in self._shed.children_by_parent.get(knot_id, []):
            if child_id not in self._unresolved or child_id in self._resolved:
                continue
            self._unresolved[child_id] -= 1
            if self._unresolved[child_id] == 0:
                newly_ready.append(child_id)
        return self._in_topo_order(newly_ready)

    def merge(self, added: Iterable[str], floors: Mapping[str, int]) -> list[str]:
        """Start tracking knots that were merged into the shed mid-run.

        Call this after the knots are in the shed with their edges.  A merged
        knot counts only parents that have not resolved yet, because a parent
        that already has a result is served from it.

        Args:
            added: Ids of the knots just merged into the shed.
            floors: The lowest level each merged knot may take, keyed by id.
                A knot absent from the mapping has floor ``0``.  The floor
                places a knot no earlier than the point in the run at which
                it was registered, which a parentless knot could not
                otherwise express.

        Returns:
            The merged knots that are ready at once, in topological order.
        """
        added_ids = set(added)
        order = self._shed.topological_order()
        self._reindex(order)
        ready: list[str] = []
        for knot_id in order:
            if knot_id not in added_ids or knot_id in self._unresolved:
                continue
            self._track(knot_id, floor=floors.get(knot_id, 0))
            if self._unresolved[knot_id] == 0:
                ready.append(knot_id)
        return ready

    def is_tracked(self, knot_id: str) -> bool:
        """Return whether *knot_id* belongs to the tracked shed."""
        return knot_id in self._unresolved

    def level(self, knot_id: str) -> int:
        """Return the depth of *knot_id*: ``0`` for a root.

        Args:
            knot_id: A tracked knot.
        """
        return self._levels[knot_id]

    def topo_index(self, knot_id: str) -> int:
        """Return the position of *knot_id* in the shed's topological order.

        Args:
            knot_id: A tracked knot.
        """
        return self._topo_index[knot_id]

    def sort_key(self, knot_id: str, dispatched: bool) -> tuple[int, int, int]:
        """Return the key that orders a run's per-knot records.

        The key is ``(level, dispatched, topo_index)``.  The middle element
        preserves one more detail of the wave loop's order: within a level, a
        knot resolved without dispatch (skipped, or failed for a missing
        parent) was recorded before any knot that ran.

        Args:
            knot_id: The knot the record belongs to.  An id the tracker does
                not know sorts after every tracked knot.
            dispatched: Whether the knot was dispatched rather than resolved
                by the engine without running.

        Returns:
            A tuple that sorts in the run's reporting order.
        """
        if knot_id not in self._levels:
            beyond = len(self._topo_index) + 1
            return (beyond, 1, beyond)
        return (self._levels[knot_id], 1 if dispatched else 0, self._topo_index[knot_id])

    # ------------------------------------------------------------ internals

    def _track(self, knot_id: str, floor: int) -> None:
        edges = self._shed.edges_by_child.get(knot_id, [])
        self._unresolved[knot_id] = sum(1 for e in edges if e.parent_id not in self._resolved)
        deepest_parent = max((self._levels[e.parent_id] for e in edges), default=-1)
        self._levels[knot_id] = max(floor, deepest_parent + 1)

    def _reindex(self, order: list[str]) -> None:
        self._topo_index = {knot_id: index for index, knot_id in enumerate(order)}

    def _in_topo_order(self, knot_ids: list[str]) -> list[str]:
        if len(knot_ids) < 2:
            return knot_ids
        return sorted(knot_ids, key=self._topo_index.__getitem__)
