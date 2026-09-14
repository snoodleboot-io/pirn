"""``_BackpressureGate`` — one engine-backed pool: an ``AdmissionGate`` plus shedding.

The shared building block behind the deprecated
:class:`~pirn_agents.performance.backpressure_semaphore.BackpressureSemaphore`
(one pool) and :class:`~pirn_agents.resilience.bulkhead.Bulkhead` (one pool
per backend) -- ADR agents-speaks-core, WS4b/PIR-866. Where the pre-migration
classes held a private ``asyncio.Semaphore`` the engine's own
``AdmissionGate``/``ConcurrencyLimits`` could not see or steer, this pool is
a real ``pirn.engine.admission.limited_admission_gate.LimitedAdmissionGate``:
the same in-flight counter, lock and waiter-wakeup logic a knot's admission
uses inside a run. What it adds on top -- a bounded wait *queue* (shedding
with a typed ``asyncio.QueueFull`` once ``max_queue_depth`` callers are
already parked) and an ``acquire_timeout`` -- has no core equivalent outside
a running ``Tapestry``, where that role belongs to the ``ReadyQueue`` and
``KnotConfig.timeout``; this class is the documented seam for a caller with
no graph of its own to run.

Algorithm:
    1. Build one ``LimitedAdmissionGate`` from a ``ConcurrencyLimits``: a
       single named group (``group=<name>``, one cap) when isolating a named
       backend, or a bare ``max_in_flight`` cap otherwise.
    2. ``acquire()``: if ``max_queue_depth`` is set and already met, raise
       ``asyncio.QueueFull`` immediately (shedding, never queuing past the
       bound). Otherwise count this caller as waiting and loop
       ``try_admit``/``wait_for_release`` -- optionally wrapped in
       ``asyncio.timeout`` -- until a ticket is issued; track it.
    3. ``release(ticket=None)``: with no ticket, pop whichever ticket this
       pool is holding (a plain counting semaphore has no notion of *which*
       unit is freed either); with one, release exactly that ticket -- the
       real ``AdmissionGate.release`` contract, used when a caller (e.g.
       ``Bulkhead``) already knows which ticket it holds.
    4. The ``AdmissionGate`` surface (``has_capacity``, ``try_admit``,
       ``wait_for_release``, ``current_limit``, ``set_limit``) delegates
       straight through to the wrapped gate, so this pool is itself a real,
       usable ``AdmissionGate`` -- not only a semaphore-shaped facade.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from pirn.core.knot_config import KnotConfig
from pirn.engine.admission.admission_gate import AdmissionGate
from pirn.engine.admission.admission_release_error import AdmissionReleaseError
from pirn.engine.admission.limited_admission_gate import LimitedAdmissionGate

from pirn_agents.performance._admission_slot_knot import _AdmissionSlotKnot
from pirn_agents.performance.concurrency_config import ConcurrencyConfig

if TYPE_CHECKING:
    from pirn.core.knot import Knot
    from pirn.engine.admission.admission_ticket import AdmissionTicket


class _BackpressureGate(AdmissionGate):
    """A ``ConcurrencyConfig``-sized ``LimitedAdmissionGate`` with queue-depth shedding."""

    def __init__(self, config: ConcurrencyConfig, *, group: str | None = None) -> None:
        """Build the pool.

        Args:
            config: Sizing and backpressure posture for this one pool.
            group: When given, this pool isolates one named concurrency
                group (``Bulkhead``'s per-backend pools); ``None`` builds a
                bare run-wide-shaped cap (``BackpressureSemaphore``'s single
                pool).

        Raises:
            TypeError: If ``config`` is not a :class:`ConcurrencyConfig`.
        """
        if not isinstance(config, ConcurrencyConfig):
            raise TypeError(
                f"_BackpressureGate: config must be a ConcurrencyConfig, "
                f"got {type(config).__name__}"
            )
        self._config = config
        self._group = group
        self._gate = LimitedAdmissionGate(config.to_concurrency_limits(group=group))
        self._token: Knot = _AdmissionSlotKnot(
            _config=KnotConfig(id="backpressure-slot", concurrency_group=group)
        )
        self._waiting = 0
        # Keyed by id(ticket), not ticket equality: ``AdmissionTicket`` is a
        # frozen dataclass that compares by value, and every ticket this
        # pool's single reused token produces shares the same
        # knot_id/group/held -- so two distinct, simultaneously-held tickets
        # are mutually "==" while being different objects the underlying
        # gate tracks by identity (``LimitedAdmissionGate._holders``). A
        # value-equality container (``list.remove``/``in``) could silently
        # drop bookkeeping for the wrong one; identity is the only safe key.
        self._live_tickets: dict[int, AdmissionTicket] = {}

    @property
    def config(self) -> ConcurrencyConfig:
        """The config this pool was built from."""
        return self._config

    @property
    def in_flight(self) -> int:
        """Number of slots currently held by this pool."""
        return len(self._live_tickets)

    @property
    def waiting(self) -> int:
        """Number of callers currently blocked in :meth:`acquire`."""
        return self._waiting

    async def acquire(self) -> None:
        """Acquire one slot, honouring the queue bound and acquire timeout.

        Raises:
            asyncio.QueueFull: If ``max_queue_depth`` is set and the wait
                queue is already full -- the backpressure signal to shed load.
            TimeoutError: If ``acquire_timeout`` elapses before a slot frees.
        """
        depth = self._config.max_queue_depth
        if depth is not None and self._waiting >= depth:
            raise asyncio.QueueFull(f"_BackpressureGate: wait queue full (max_queue_depth={depth})")
        self._waiting += 1
        try:
            timeout = self._config.acquire_timeout
            if timeout is not None:
                async with asyncio.timeout(timeout):
                    ticket = await self._admit_or_wait()
            else:
                ticket = await self._admit_or_wait()
        finally:
            self._waiting -= 1
        self._live_tickets[id(ticket)] = ticket

    async def _admit_or_wait(self) -> AdmissionTicket:
        """Loop ``try_admit``/``wait_for_release`` until a ticket is issued."""
        while True:
            ticket = self._gate.try_admit(self._token)
            if ticket is not None:
                return ticket
            await self._gate.wait_for_release()

    def release(self, ticket: AdmissionTicket | None = None) -> None:
        """Release one previously acquired slot.

        Args:
            ticket: The exact ticket to release, when the caller has one
                (the real ``AdmissionGate`` contract). ``None`` (the
                pre-migration bare-semaphore contract) releases whichever
                ticket this pool currently holds -- correct because a
                counting semaphore has no notion of *which* unit is freed
                either.

        Raises:
            AdmissionReleaseError: If ``ticket`` is given but this pool does
                not hold it (the wrapped gate's own check), or ``None`` is
                given and this pool holds nothing.
        """
        if ticket is None:
            if not self._live_tickets:
                raise AdmissionReleaseError("_BackpressureGate: no held slot to release")
            _, ticket = self._live_tickets.popitem()
        else:
            # Discard only if tracked here: a ticket obtained through
            # ``try_admit`` always is (see below), so this never masks a
            # foreign ticket -- ``self._gate.release`` below is the one
            # place that actually validates and raises for that.
            self._live_tickets.pop(id(ticket), None)
        self._gate.release(ticket)

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Acquire a slot for the duration of the ``async with`` block.

        The slot is always released, even if the body raises, so a failing
        operation never leaks concurrency capacity.
        """
        await self.acquire()
        try:
            yield
        finally:
            self.release()

    # ------------------------------------------------- AdmissionGate surface

    def has_capacity(self) -> bool:
        """Whether this pool's budget has a free slot."""
        return self._gate.has_capacity()

    def try_admit(self, knot: Knot) -> AdmissionTicket | None:
        """Admit *knot* if this pool's budget has room; see ``AdmissionGate``.

        A ticket this returns is tracked the same way :meth:`acquire` tracks
        one, so :meth:`release` (with or without an explicit ticket) and
        :attr:`in_flight` see it too.
        """
        ticket = self._gate.try_admit(knot)
        if ticket is not None:
            self._live_tickets[id(ticket)] = ticket
        return ticket

    async def wait_for_release(self) -> None:
        """Suspend until this pool may have freed a slot; see ``AdmissionGate``."""
        await self._gate.wait_for_release()

    def current_limit(self, group: str | None) -> int | None:
        """The live cap in force; see ``AdmissionGate``."""
        return self._gate.current_limit(group)

    def set_limit(self, group: str | None, limit: int) -> None:
        """Change the live cap; see ``AdmissionGate``."""
        self._gate.set_limit(group, limit)
