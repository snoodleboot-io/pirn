"""Unresolved-parent bookkeeping for the engine's admission loop."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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

    The tracker also owns the coordinates that make a run's reported order
    independent of the order knots happen to finish in:

    * ``level`` -- the knot's depth: ``0`` for a root, otherwise one more than
      its deepest parent.  For a static graph this is exactly the wave the
      old loop would have run the knot in.  A knot registered mid-run from
      inside a known knot is also placed one past that registrar.
    * ``topo_index`` -- the knot's position in ``Shed.topological_order()``,
      which sorts ties by knot id.

    ``sort_key`` combines them into the order lineage, exceptions, skips and
    outputs are reported in.  For static graphs and for knots registered by a
    known knot it reproduces the wave loop's order exactly.

    A knot registered mid-run with *no* known registrar -- from a plain
    thread, an external orchestrator, or a durable store's background
    delivery -- has no place in the graph that timing does not decide.  Such
    knots go into a final *bucket* (tier ``1``) that sorts after every knot
    with a known level, ordered by registration sequence and then knot id.
    Knots they register in turn keep the registrar-plus-one rule inside the
    bucket.  Only the reported order is affected; scheduling stays eager.

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
        # 0 for knots with a known level; 1 for the registrar-less bucket.
        self._tiers: dict[str, int] = {}
        # Registration sequence of mid-run knots, in arrival order.
        self._sequence: dict[str, int] = {}
        self._topo_index: dict[str, int] = {}
        self._resolved: set[str] = set()
        order = shed.topological_order()
        self._reindex(order)
        for knot_id in order:
            self._track_static(knot_id)

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

    def merge(self, added: Sequence[str], registrars: Mapping[str, str]) -> list[str]:
        """Start tracking knots that were merged into the shed mid-run.

        Call this after the knots are in the shed with their edges.  A merged
        knot counts only parents that have not resolved yet, because a parent
        that already has a result is served from it.

        A merged knot whose registrar is known and tracked takes the highest
        tier among its registrar and parents, and sits one level past every
        one of them in that tier.  A merged knot with no known registrar joins
        the bucket, one level past any parents already in the bucket.

        Args:
            added: Ids of the knots just merged into the shed, in the order
                they were registered; that order is their registration
                sequence.  Ids already tracked are ignored.
            registrars: The id of the knot that registered each merged knot,
                for those registered from inside a dispatched knot.

        Returns:
            The merged knots that are ready at once, in topological order.
        """
        new_ids = [knot_id for knot_id in added if knot_id not in self._unresolved]
        for knot_id in new_ids:
            self._sequence.setdefault(knot_id, len(self._sequence))
        pending = set(new_ids)
        order = self._shed.topological_order()
        self._reindex(order)
        ready: list[str] = []
        for knot_id in order:
            if knot_id not in pending:
                continue
            self._track_newcomer(knot_id, registrars.get(knot_id))
            if self._unresolved[knot_id] == 0:
                ready.append(knot_id)
        return ready

    def is_tracked(self, knot_id: str) -> bool:
        """Return whether *knot_id* belongs to the tracked shed."""
        return knot_id in self._unresolved

    def level(self, knot_id: str) -> int:
        """Return the depth of *knot_id* within its tier: ``0`` for a root.

        Args:
            knot_id: A tracked knot.
        """
        return self._levels[knot_id]

    def tier(self, knot_id: str) -> int:
        """Return ``0`` for a knot with a known level, ``1`` for the bucket.

        Args:
            knot_id: A tracked knot.
        """
        return self._tiers[knot_id]

    def topo_index(self, knot_id: str) -> int:
        """Return the position of *knot_id* in the shed's topological order.

        Args:
            knot_id: A tracked knot.
        """
        return self._topo_index[knot_id]

    def sort_key(self, knot_id: str, dispatched: bool) -> tuple[int, int, int, int, str]:
        """Return the key that orders a run's per-knot records.

        For a knot with a known level the key is ``(0, level, dispatched,
        topo_index, "")``.  ``dispatched`` preserves one more detail of the
        wave loop's order: within a level, a knot resolved without dispatch
        (skipped, or failed for a missing parent) was recorded before any
        knot that ran.

        For a knot in the registrar-less bucket it is ``(1, level,
        dispatched, registration_sequence, knot_id)``: after every known-level
        knot, and independent of timing.

        Args:
            knot_id: The knot the record belongs to.  An id the tracker does
                not know sorts after every tracked knot.
            dispatched: Whether the knot was dispatched rather than resolved
                by the engine without running.

        Returns:
            A tuple that sorts in the run's reporting order.
        """
        if knot_id not in self._levels:
            return (2, 0, 1, 0, knot_id)
        ran = 1 if dispatched else 0
        if self._tiers[knot_id] == 0:
            return (0, self._levels[knot_id], ran, self._topo_index[knot_id], "")
        return (1, self._levels[knot_id], ran, self._sequence[knot_id], knot_id)

    # ------------------------------------------------------------ internals

    def _count_unresolved(self, knot_id: str) -> None:
        edges = self._shed.edges_by_child.get(knot_id, [])
        self._unresolved[knot_id] = sum(1 for e in edges if e.parent_id not in self._resolved)

    def _track_static(self, knot_id: str) -> None:
        self._count_unresolved(knot_id)
        edges = self._shed.edges_by_child.get(knot_id, [])
        self._tiers[knot_id] = 0
        self._levels[knot_id] = 1 + max((self._levels[e.parent_id] for e in edges), default=-1)

    def _track_newcomer(self, knot_id: str, registrar: str | None) -> None:
        self._count_unresolved(knot_id)
        anchors = [e.parent_id for e in self._shed.edges_by_child.get(knot_id, [])]
        if registrar is not None and registrar in self._tiers:
            anchors.append(registrar)
            tier = max(self._tiers[anchor] for anchor in anchors)
        else:
            tier = 1
        self._tiers[knot_id] = tier
        # One past every anchor in the same tier.  A bucket knot's parents with
        # a known level say nothing about its place inside the bucket.
        self._levels[knot_id] = 1 + max(
            (self._levels[anchor] for anchor in anchors if self._tiers[anchor] == tier),
            default=-1,
        )

    def _reindex(self, order: list[str]) -> None:
        self._topo_index = {knot_id: index for index, knot_id in enumerate(order)}

    def _in_topo_order(self, knot_ids: list[str]) -> list[str]:
        if len(knot_ids) < 2:
            return knot_ids
        return sorted(knot_ids, key=self._topo_index.__getitem__)
