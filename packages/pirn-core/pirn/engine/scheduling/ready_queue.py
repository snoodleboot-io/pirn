"""The queue of knots that may run as soon as a gate admits them."""

from __future__ import annotations

import heapq
from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirn.engine.admission.admission_gate import AdmissionGate
    from pirn.engine.admission.admission_ticket import AdmissionTicket
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

    A gate refuses a knot because its group is full or the run is full, and
    in either case every other knot of that group would be refused too, so
    passing over the rest of the group loses nothing.

    Entries are knot ids, not knot instances.  The engine replaces entries in
    the shed while a run is live (``Parameter`` binding after a mid-run
    merge), so the instance offered to the gate is looked up at the moment of
    admission.
    """

    def __init__(self) -> None:
        # Heaps of (sequence, topo_index, knot_id).  Ungrouped knots -- every
        # knot of a run that uses no groups -- live in one long-lived heap, so
        # that common case never touches the group dict.  A group's heap is
        # dropped as soon as it empties, so admission scans only live groups.
        self._ungrouped: list[tuple[int, int, str]] = []
        self._groups: dict[str, list[tuple[int, int, str]]] = {}
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
            if group is None:
                fifo = self._ungrouped
            else:
                fifo = self._groups.get(group)
                if fifo is None:
                    fifo = self._groups[group] = []
            heapq.heappush(fifo, (sequence, topo_index, knot_id))
            pushed += 1
        if pushed:
            self._size += pushed
            self._next_sequence += 1

    def pop_admissible(self, gate: AdmissionGate, shed: Shed) -> tuple[str, AdmissionTicket] | None:
        """Remove and return the longest-waiting knot the gate admits.

        Heads are offered in readiness order; a refused head stays queued and
        its group is passed over for this call.

        Args:
            gate: The run's admission gate.
            shed: The run's shed, used to look up the knot to offer.

        Returns:
            ``(knot_id, ticket)`` for the admitted knot, or ``None`` when the
            queue is empty or the gate refused every group's head.
        """
        if not self._groups:
            # The common case -- no groups in play -- needs no ordering pass.
            if not self._ungrouped:
                return None
            return self._admit_head(None, self._ungrouped, gate, shed)
        heads: list[tuple[tuple[int, int, str], str | None]] = [
            (fifo[0], group) for group, fifo in self._groups.items()
        ]
        if self._ungrouped:
            heads.append((self._ungrouped[0], None))
        # Entries are unique by knot id, so the group is never compared.
        heads.sort(key=lambda head: head[0])
        for _, group in heads:
            fifo = self._ungrouped if group is None else self._groups[group]
            admitted = self._admit_head(group, fifo, gate, shed)
            if admitted is not None:
                return admitted
        return None

    def _admit_head(
        self,
        group: str | None,
        fifo: list[tuple[int, int, str]],
        gate: AdmissionGate,
        shed: Shed,
    ) -> tuple[str, AdmissionTicket] | None:
        knot_id = fifo[0][2]
        ticket = gate.try_admit(shed.knot(knot_id))
        if ticket is None:
            return None
        heapq.heappop(fifo)
        if group is not None and not fifo:
            del self._groups[group]
        self._size -= 1
        return knot_id, ticket

    def __len__(self) -> int:
        return self._size

    def __bool__(self) -> bool:
        return self._size > 0
