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
    """FIFO of ready knots, ordered by when they became ready.

    Knots that become ready together -- the roots of a run, or the children a
    single resolution released -- are pushed as one batch and share a
    readiness sequence number.  The queue orders by ``(sequence, topo_index)``:
    first come, first served across batches, and topological order within a
    batch.  So a knot that became ready later can never overtake one that has
    been waiting longer, which is what keeps an open-ended loop from starving
    work queued before it.

    Entries are knot ids, not knot instances.  The engine replaces entries in
    the shed while a run is live (``Parameter`` binding after a mid-run
    merge), so the instance offered to the gate is looked up at the moment of
    admission.
    """

    def __init__(self) -> None:
        self._heap: list[tuple[int, int, str]] = []
        self._next_sequence = 0

    def push_batch(self, entries: Iterable[tuple[int, str]]) -> None:
        """Enqueue knots that became ready at the same moment.

        Args:
            entries: ``(topo_index, knot_id)`` pairs.  Every pair in one call
                shares a readiness sequence number.
        """
        sequence = self._next_sequence
        pushed = False
        for topo_index, knot_id in entries:
            heapq.heappush(self._heap, (sequence, topo_index, knot_id))
            pushed = True
        if pushed:
            self._next_sequence += 1

    def pop_admissible(self, gate: AdmissionGate, shed: Shed) -> tuple[str, AdmissionTicket] | None:
        """Remove and return the longest-waiting knot the gate admits.

        Args:
            gate: The run's admission gate.
            shed: The run's shed, used to look up the knot to offer.

        Returns:
            ``(knot_id, ticket)`` for the admitted knot, or ``None`` when the
            queue is empty or the gate refused the head, which stays queued.
        """
        if not self._heap:
            return None
        _, _, knot_id = self._heap[0]
        ticket = gate.try_admit(shed.knot(knot_id))
        if ticket is None:
            return None
        heapq.heappop(self._heap)
        return knot_id, ticket

    def __len__(self) -> int:
        return len(self._heap)

    def __bool__(self) -> bool:
        return bool(self._heap)
