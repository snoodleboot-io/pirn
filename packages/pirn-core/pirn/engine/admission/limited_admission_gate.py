"""A gate that enforces a run's ``ConcurrencyLimits``."""

from __future__ import annotations

import asyncio
from collections import Counter
from typing import TYPE_CHECKING

from pirn.core.concurrency.undefined_concurrency_group_error import (
    UndefinedConcurrencyGroupError,
)
from pirn.engine.admission.admission_gate import AdmissionGate
from pirn.engine.admission.admission_limit_error import AdmissionLimitError
from pirn.engine.admission.admission_release_error import AdmissionReleaseError
from pirn.engine.admission.admission_ticket import AdmissionTicket

if TYPE_CHECKING:
    from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
    from pirn.core.knot import Knot


class LimitedAdmissionGate(AdmissionGate):
    """Admits a knot only while the run's global and group budgets have room.

    A knot takes one global slot when ``max_in_flight`` is set, and one slot
    of its group when the limits cap that group.  Admission takes both or
    neither: a refused knot holds nothing while it waits, so a knot that
    cannot get its group slot never sits on a global slot another knot could
    use.

    The gate counts; it does not queue.  Which waiting knot is offered a freed
    slot first -- FIFO within a group, readiness order across groups -- is the
    ``ReadyQueue``'s job.

    Threading: the gate is single-threaded by contract.  The engine calls
    ``try_admit``, ``release`` and ``wait_for_release`` only from the run's
    event loop -- a knot dispatched to a worker thread (``ThreadDispatcher``)
    finishes as a task on that loop, and its slot is released there -- so
    the counters need no lock and no asyncio primitive is ever touched from
    another thread, which hangs (design §2.3, M6x).  Sharing one gate across
    the event loops of nested runs needs a thread-safe gate; that is PIR-841
    slice 3.
    """

    def __init__(self, limits: ConcurrencyLimits) -> None:
        """Build a gate enforcing *limits*.

        Args:
            limits: The run's limits.  An unbounded value is accepted and
                admits everything, but the engine uses
                ``UnboundedAdmissionGate`` for that instead.
        """
        self._limits = limits
        # The live caps.  Seeded from ``limits`` and adjusted by
        # ``set_limit``; ``limits`` itself stays the run's declared value.
        self._max_in_flight = limits.max_in_flight
        self._group_limits: dict[str, int] = dict(limits.groups)
        self._in_flight = 0
        self._group_in_flight: Counter[str] = Counter()
        # Knot ids holding a slot; guards against a double or foreign release.
        self._holders: set[str] = set()
        self._waiters: list[asyncio.Future[None]] = []

    @property
    def limits(self) -> ConcurrencyLimits:
        """The limits this gate was built from; ``current_limit`` gives the live caps."""
        return self._limits

    def current_limit(self, group: str | None) -> int | None:
        """Return the live cap for *group* (``None`` for the run-wide cap)."""
        if group is None:
            return self._max_in_flight
        return self._group_limits.get(group)

    def set_limit(self, group: str | None, limit: int) -> None:
        """Change the live cap for *group* without touching issued tickets.

        Args:
            group: A group the run's limits define, or ``None`` for the
                run-wide cap.
            limit: The new cap; at least 1.

        Raises:
            AdmissionLimitError: If *group* is not one the limits define or
                *limit* is below 1.
        """
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise AdmissionLimitError(f"admission limit must be an int >= 1, got {limit!r}")
        if group is None:
            self._max_in_flight = limit
            return
        if group not in self._group_limits:
            raise AdmissionLimitError(
                f"concurrency group {group!r} is not one this run defines "
                f"({sorted(self._group_limits)}); groups cannot be added mid-run"
            )
        self._group_limits[group] = limit

    @property
    def in_flight(self) -> int:
        """How many admitted knots have not been released."""
        return self._in_flight

    def has_capacity(self) -> bool:
        """Whether the run-wide budget has a free slot.

        ``False`` only when ``max_in_flight`` is set and reached; a full group
        does not count, because knots of other groups could still start.
        """
        return self._max_in_flight is None or self._in_flight < self._max_in_flight

    def in_flight_in(self, group: str) -> int:
        """How many admitted knots hold a slot of *group*.

        Args:
            group: A group name.  A group the limits do not cap holds no
                slots, so it always reports ``0``.
        """
        return self._group_in_flight[group]

    def try_admit(self, knot: Knot) -> AdmissionTicket | None:
        """Admit *knot* if both its global and its group budget have room.

        Args:
            knot: The ready knot asking to start.

        Returns:
            A ticket recording the slots taken, or ``None`` -- holding
            nothing -- if either budget is full.

        Raises:
            UndefinedConcurrencyGroupError: If the limits define groups and
                *knot*'s group is not one of them.  Tags are ignored when the
                limits define no groups.
        """
        group = knot.config.concurrency_group
        group_limit = self._group_limits.get(group) if group is not None else None
        if group is not None and group_limit is None and self._limits.groups:
            raise UndefinedConcurrencyGroupError(knot.knot_id, group, self._limits.groups)
        if self._max_in_flight is not None and self._in_flight >= self._max_in_flight:
            return None
        held_group: str | None = None
        if group is not None and group_limit is not None:
            if self._group_in_flight[group] >= group_limit:
                return None
            self._group_in_flight[group] += 1
            held_group = group
        self._in_flight += 1
        self._holders.add(knot.knot_id)
        return AdmissionTicket(knot_id=knot.knot_id, group=held_group)

    def release(self, ticket: AdmissionTicket) -> None:
        """Free the slots *ticket* holds and wake anything waiting for one.

        Args:
            ticket: A ticket this gate issued and has not had back yet.

        Raises:
            AdmissionReleaseError: If this gate is not holding *ticket*'s knot,
                because the ticket was released already or issued elsewhere.
        """
        if ticket.knot_id not in self._holders:
            raise AdmissionReleaseError(
                f"knot {ticket.knot_id!r} holds no slot in this gate; "
                "its ticket was released already or was issued by another gate"
            )
        self._holders.discard(ticket.knot_id)
        self._in_flight -= 1
        if ticket.group is not None:
            self._group_in_flight[ticket.group] -= 1
        if self._waiters:
            waiters, self._waiters = self._waiters, []
            for waiter in waiters:
                if not waiter.done():
                    waiter.set_result(None)

    async def wait_for_release(self) -> None:
        """Suspend until a slot is released, or return at once if none is held.

        With nothing held every budget is empty, so there is nothing to wait
        for; returning keeps a caller from parking forever.
        """
        if self._in_flight == 0:
            return
        waiter: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._waiters.append(waiter)
        await waiter
