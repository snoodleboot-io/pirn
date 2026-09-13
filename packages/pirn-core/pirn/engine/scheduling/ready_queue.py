"""The queue of knots that may run as soon as a gate admits them."""

from __future__ import annotations

import heapq
from collections.abc import Iterable
from typing import TYPE_CHECKING

from pirn.engine.admission.admission_ticket import AdmissionTicket

if TYPE_CHECKING:
    from pirn.core.knot import Knot
    from pirn.engine.admission.admission_gate import AdmissionGate
    from pirn.engine.shed.shed import Shed


class ReadyQueue:
    """Ready knots, one FIFO per concurrency group, ordered by readiness.

    Knots that become ready together -- the roots of a run, or the children a
    single resolution released -- are pushed as one batch and share a
    readiness sequence number.  Every entry is ordered by ``(sequence,
    topo_index)``: first come, first served across batches, and topological
    order within a batch.  So a knot that became ready later can never
    overtake one that has been waiting longer, which is what keeps an
    open-ended loop from starving work queued before it.

    Entries are kept in one FIFO per ``KnotConfig.concurrency_group`` (one more
    for ungrouped knots).  Admission offers the FIFO heads to the gate in
    readiness order and passes over a head the gate refuses (PIR-841, design
    §6):

    * **No head-of-line blocking across groups.**  Four saturated API calls
      at the front of the queue never hold up the local knots behind them.
    * **FIFO within a group.**  Nothing queued behind a refused head in its
      own group is offered, so a knot cannot be overtaken by a sibling that
      became ready after it, however long it waits.

    **Cost does not grow with the number of groups.**  The group heads live in
    a heap, so the next head is found in O(log groups).  When the gate has no
    run-wide capacity no leaf is offered at all; only a slot-free container
    knot at the head of the line still starts.  When it has capacity but
    refuses a head, that group is full, and every knot of the group would be
    refused too, so the group is *parked*: it is not offered again until
    ``unpark`` says one of its slots came back.  A saturated group therefore
    costs one refusal per release of its own slots, not one per admission.

    Entries are knot ids, not knot instances.  The engine replaces entries in
    the shed while a run is live (``Parameter`` binding after a mid-run
    merge), so the instance offered to the gate is looked up at the moment of
    admission.
    """

    def __init__(self) -> None:
        # Heaps of (sequence, topo_index, knot_id).  Ungrouped knots -- every
        # knot of a run that uses no groups -- live in one long-lived heap, so
        # that common case never touches the group structures.
        self._ungrouped: list[tuple[int, int, str]] = []
        self._ungrouped_parked = False
        # A group's heap is dropped as soon as it empties.
        self._groups: dict[str, list[tuple[int, int, str]]] = {}
        # Heap of (head entry, group) for unparked groups.  Entries go stale
        # when a group's head changes or it is parked; they are discarded
        # lazily when they reach the top.
        self._heads: list[tuple[tuple[int, int, str], str]] = []
        self._parked: set[str] = set()
        self._size = 0
        self._next_sequence = 0

    def push_batch(self, entries: Iterable[tuple[int, str, str | None]]) -> None:
        """Enqueue knots that became ready at the same moment.

        Args:
            entries: ``(topo_index, knot_id, concurrency_group)`` triples.
                Every triple in one call shares a readiness sequence number.
        """
        sequence = self._next_sequence
        pushed = 0
        for topo_index, knot_id, group in entries:
            entry = (sequence, topo_index, knot_id)
            pushed += 1
            if group is None:
                heapq.heappush(self._ungrouped, entry)
                continue
            fifo = self._groups.get(group)
            if fifo is None:
                fifo = self._groups[group] = []
            heapq.heappush(fifo, entry)
            if fifo[0] is entry and group not in self._parked:
                heapq.heappush(self._heads, (entry, group))
        if pushed:
            self._size += pushed
            self._next_sequence += 1

    def pop_admissible(self, gate: AdmissionGate, shed: Shed) -> tuple[str, AdmissionTicket] | None:
        """Remove and return the longest-waiting knot the gate admits.

        Heads are offered in readiness order.  A refused head stays queued,
        and its group is parked until ``unpark`` is called for it.

        Args:
            gate: The run's admission gate.
            shed: The run's shed, used to look up the knot to offer.

        A *container* knot (``Knot._holds_admission_slot`` is ``False``) is
        admitted without consulting the gate, even when the gate has no
        run-wide capacity: it holds no slot, so nothing it waits on can be
        waiting on it (ADR agents-speaks-core, WS0b).  Heads are still
        offered in readiness order, so a container queued behind a leaf the
        gate cannot yet admit waits its turn; that is a delay, never a
        deadlock, because a leaf never waits on a container.

        Args:
            gate: The run's admission gate.
            shed: The run's shed, used to look up the knot to offer.

        Returns:
            ``(knot_id, ticket)`` for the admitted knot, or ``None`` when the
            queue is empty, the gate has no run-wide capacity for the head
            in line, or every unparked group's head was refused.
        """
        if not self._size:
            return None
        capacity = gate.has_capacity()
        while True:
            group_head = self._live_group_head()
            ungrouped_head = (
                self._ungrouped[0] if self._ungrouped and not self._ungrouped_parked else None
            )
            if ungrouped_head is not None and (
                group_head is None or ungrouped_head < group_head[0]
            ):
                knot_id = ungrouped_head[2]
                ticket = self._admit(gate, shed.knot(knot_id), capacity)
                if ticket is None:
                    if not capacity:
                        return None
                    self._ungrouped_parked = True
                    continue
                heapq.heappop(self._ungrouped)
                self._size -= 1
                return knot_id, ticket
            if group_head is None:
                return None
            entry, group = group_head
            knot_id = entry[2]
            ticket = self._admit(gate, shed.knot(knot_id), capacity)
            if ticket is None:
                if not capacity:
                    return None
                heapq.heappop(self._heads)
                self._parked.add(group)
                continue
            heapq.heappop(self._heads)
            fifo = self._groups[group]
            heapq.heappop(fifo)
            self._size -= 1
            if fifo:
                heapq.heappush(self._heads, (fifo[0], group))
            else:
                del self._groups[group]
            return knot_id, ticket

    @staticmethod
    def _admit(gate: AdmissionGate, knot: Knot, capacity: bool) -> AdmissionTicket | None:
        """Admit *knot*: slot-free for a container, through *gate* for a leaf.

        Args:
            gate: The run's admission gate.
            knot: The knot at the head of the line.
            capacity: ``gate.has_capacity()`` as read at the start of this
                pass; a leaf is refused outright when it is ``False``, so a
                full run-wide budget costs one call rather than one refusal
                per group.

        Returns:
            The ticket, or ``None`` when the gate refuses the knot.
        """
        if not type(knot)._holds_admission_slot:
            return AdmissionTicket(knot_id=knot.knot_id, held=False)
        if not capacity:
            return None
        return gate.try_admit(knot)

    def unpark(self, group: str | None) -> None:
        """Offer *group* again: one of its slots, or run-wide capacity, came back.

        Args:
            group: The group to re-offer; ``None`` re-offers ungrouped knots.
                A group that is not parked is left as it is.
        """
        if group is None:
            self._ungrouped_parked = False
            return
        if group not in self._parked:
            return
        self._parked.discard(group)
        fifo = self._groups.get(group)
        if fifo:
            heapq.heappush(self._heads, (fifo[0], group))

    def unpark_all(self) -> None:
        """Offer every parked group again."""
        self._ungrouped_parked = False
        for group in self._parked:
            fifo = self._groups.get(group)
            if fifo:
                heapq.heappush(self._heads, (fifo[0], group))
        self._parked.clear()

    def waiting_in(self, group: str | None) -> int:
        """How many ready knots of *group* are still queued.

        Args:
            group: A concurrency group, or ``None`` for ungrouped knots.
        """
        if group is None:
            return len(self._ungrouped)
        fifo = self._groups.get(group)
        return len(fifo) if fifo else 0

    def _live_group_head(self) -> tuple[tuple[int, int, str], str] | None:
        heads = self._heads
        while heads:
            entry, group = heads[0]
            fifo = self._groups.get(group)
            if group not in self._parked and fifo and fifo[0] == entry:
                return heads[0]
            heapq.heappop(heads)
        return None

    def __len__(self) -> int:
        return self._size

    def __bool__(self) -> bool:
        return self._size > 0
