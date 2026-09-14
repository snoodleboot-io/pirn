# pyright: reportUnnecessaryIsInstance=false
# runtime-bound arguments: explicit type guards are house style (docs/contributing/domain-knots.md)
"""A gate that enforces a run's ``ConcurrencyLimits``."""

from __future__ import annotations

import asyncio
import threading
from collections import Counter
from typing import TYPE_CHECKING

from pirn.core.concurrency.undefined_concurrency_group_error import (
    UndefinedConcurrencyGroupError,
)
from pirn.engine.admission.admission import Admission
from pirn.engine.admission.admission_limit_error import AdmissionLimitError
from pirn.engine.admission.admission_release_error import AdmissionReleaseError
from pirn.engine.admission.admission_ticket import AdmissionTicket

if TYPE_CHECKING:
    from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
    from pirn.core.knot import Knot


class LimitedAdmission(Admission):
    """Admits a knot only while the run's global and group budgets have room.

    A knot takes one global slot when ``max_in_flight`` is set, and one slot
    of its group when the limits cap that group.  Admission takes both or
    neither: a refused knot holds nothing while it waits, so a knot that
    cannot get its group slot never sits on a global slot another knot could
    use.

    The gate counts; it does not queue.  Which waiting knot is offered a freed
    slot first -- FIFO within a group, readiness order across groups -- is the
    ``ReadyQueue``'s job.

    Threading: one gate is shared by a whole run tree (ADR agents-speaks-core,
    WS0b): a ``SubTapestry`` inner run inherits the enclosing run's gate by
    identity, and under ``ThreadDispatcher`` that inner run executes on a
    worker thread with an event loop of its own.  ``try_admit``, ``release``
    and ``wait_for_release`` may therefore be called from several loops on
    several threads at once.  The counters are guarded by a ``threading.Lock``
    and every waiter is remembered with the loop it was created on, so a
    release wakes it through ``loop.call_soon_threadsafe`` -- the only way to
    touch a future from another thread that does not hang (PIR-841 design
    §5.4.5, M6x).  No asyncio primitive is ever awaited under the lock.

    Tickets are tracked by identity, not by knot id: a shared gate sees inner
    and outer knots that may share an id, and a slot must be released by the
    very ticket that took it.

    Algorithm:
        ``try_admit(knot)``, under the lock:

        1. If the limits define groups and the knot's group is not one of
           them, raise ``UndefinedConcurrencyGroupError``.
        2. If ``max_in_flight`` is set and reached, refuse (``None``).
        3. If the knot's group is capped and full, refuse.
        4. Otherwise take the global slot and, if capped, the group slot,
           remember the ticket by identity, and return it.

        ``release(ticket)``: under the lock, refuse a ticket not held; give
        the slots back; take every waiter.  Outside the lock, resolve each
        waiter on its own loop via ``call_soon_threadsafe``.

        ``wait_for_release()``: under the lock, return at once when nothing
        is held; otherwise register a future on the calling loop.  Await it
        outside the lock.
    """

    def __init__(self, limits: ConcurrencyLimits) -> None:
        """Build a gate enforcing *limits*.

        Args:
            limits: The run's limits.  An unbounded value is accepted and
                admits everything, but the engine uses
                ``UnboundedAdmission`` for that instead.
        """
        self._limits = limits
        # The live caps.  Seeded from ``limits`` and adjusted by
        # ``set_limit``; ``limits`` itself stays the run's declared value.
        self._max_in_flight = limits.max_in_flight
        self._group_limits: dict[str, int] = dict(limits.groups)
        self._in_flight = 0
        self._group_in_flight: Counter[str] = Counter()
        # Identities of the tickets holding a slot; guards against a double or
        # foreign release.  Identity, not knot id: a gate shared across a run
        # tree meets inner and outer knots with the same id.
        self._holders: set[int] = set()
        # Waiters with the loop each was created on, so a release from
        # another thread can wake it safely.
        self._waiters: list[tuple[asyncio.AbstractEventLoop, asyncio.Future[None]]] = []
        self._lock = threading.Lock()

    @property
    def limits(self) -> ConcurrencyLimits:
        """The limits this gate was built from; ``current_limit`` gives the live caps."""
        return self._limits

    def current_limit(self, group: str | None) -> int | None:
        """Return the live cap for *group* (``None`` for the run-wide cap)."""
        with self._lock:
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
        with self._lock:
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
        """How many admitted knots have not been released, across every run sharing the gate."""
        with self._lock:
            return self._in_flight

    def has_capacity(self) -> bool:
        """Whether the run-wide budget has a free slot.

        ``False`` only when ``max_in_flight`` is set and reached; a full group
        does not count, because knots of other groups could still start.
        """
        with self._lock:
            return self._max_in_flight is None or self._in_flight < self._max_in_flight

    def in_flight_in(self, group: str) -> int:
        """How many admitted knots hold a slot of *group*.

        Args:
            group: A group name.  A group the limits do not cap holds no
                slots, so it always reports ``0``.
        """
        with self._lock:
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
        with self._lock:
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
            ticket = AdmissionTicket(knot_id=knot.knot_id, group=held_group)
            self._holders.add(id(ticket))
            return ticket

    def release(self, ticket: AdmissionTicket) -> None:
        """Free the slots *ticket* holds and wake anything waiting for one.

        Args:
            ticket: A ticket this gate issued and has not had back yet.

        Raises:
            AdmissionReleaseError: If this gate is not holding *ticket*,
                because it was released already or issued elsewhere.
        """
        with self._lock:
            if id(ticket) not in self._holders:
                raise AdmissionReleaseError(
                    f"knot {ticket.knot_id!r} holds no slot in this gate; "
                    "its ticket was released already or was issued by another gate"
                )
            self._holders.discard(id(ticket))
            self._in_flight -= 1
            if ticket.group is not None:
                self._group_in_flight[ticket.group] -= 1
            waiters, self._waiters = self._waiters, []
        # Outside the lock: a waiter's loop may be another thread's, and
        # resolving it schedules a callback there rather than touching the
        # future directly.
        for loop, waiter in waiters:
            if loop.is_closed():
                continue
            loop.call_soon_threadsafe(LimitedAdmission._resolve_waiter, waiter)

    @staticmethod
    def _resolve_waiter(waiter: asyncio.Future[None]) -> None:
        """Resolve *waiter* on its own loop; a cancelled waiter is left alone."""
        if not waiter.done():
            waiter.set_result(None)

    async def wait_for_release(self) -> None:
        """Suspend until a slot is released, or return at once if none is held.

        With nothing held every budget is empty, so there is nothing to wait
        for; returning keeps a caller from parking forever.  The future is
        registered with the calling loop so a release from another thread's
        loop can still wake it.
        """
        loop = asyncio.get_running_loop()
        with self._lock:
            if self._in_flight == 0:
                return
            waiter: asyncio.Future[None] = loop.create_future()
            self._waiters.append((loop, waiter))
        await waiter
