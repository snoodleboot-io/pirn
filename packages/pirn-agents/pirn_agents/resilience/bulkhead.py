"""``Bulkhead`` — deprecated: one ``_BackpressureAdmission`` per backend, created on first use.

Deprecated (ADR agents-speaks-core, WS4b/PIR-866). Before this migration each
backend key got its own private
:class:`~pirn_agents.performance.backpressure_semaphore.BackpressureSemaphore`
holding an ``asyncio.Semaphore`` the engine could not see. Each backend now
gets its own :class:`~pirn_agents.performance._backpressure_admission._BackpressureAdmission`
-- a real :class:`~pirn.engine.admission.admission_gate.AdmissionGate` built
from ``ConcurrencyLimits(groups={backend: n})`` -- so "one bounded pool per
backend" is literally "one concurrency group per backend" now: the backend
name *is* the group name a real engine run would declare on
``ConcurrencyLimits.groups``, and every ticket this class hands out or takes
back carries that name as ``AdmissionTicket.group``. Because the pools stay
independent (one gate each, not one shared gate with several groups),
saturating one backend's pool only makes *its* callers queue -- calls to
other backends keep flowing, exactly as before.

Callers acquire a slot for a backend via the :meth:`slot` async context
manager, unchanged. This class also implements
:class:`~pirn.engine.admission.admission_gate.AdmissionGate` directly:
``try_admit``/``release`` read the backend off ``KnotConfig.concurrency_group``
/ ``AdmissionTicket.group`` and route to that backend's pool, for a caller
that already has a knot and wants gate semantics without going through
``slot``. ``wait_for_release`` is deliberately left unimplemented (the base
class's ``NotImplementedError``): "wait until any of several independent
per-backend pools frees a slot" has no single meaningful answer at this
aggregate level, and nothing here needs it -- :meth:`slot` waits on one
named backend's own pool directly.

A caller with a fixed, known set of backends and a real engine run should
declare ``ConcurrencyLimits(groups={backend: n, ...})`` on that run directly
instead of this shim -- one gate, every backend's cap enforced together.
This class exists for the case ``ConcurrencyLimits`` cannot express: backend
keys discovered lazily, sized from :class:`BulkheadConfig`'s ``default``,
with no fixed set known up front.
"""

from __future__ import annotations

import warnings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from pirn.engine.admission.admission_gate import AdmissionGate
from pirn.engine.admission.admission_limit_error import AdmissionLimitError
from pirn.engine.admission.admission_release_error import AdmissionReleaseError

from pirn_agents.performance._backpressure_admission import _BackpressureAdmission
from pirn_agents.resilience.bulkhead_config import BulkheadConfig

if TYPE_CHECKING:
    from pirn.core.knot import Knot
    from pirn.engine.admission.admission_ticket import AdmissionTicket


class Bulkhead(AdmissionGate):
    """Deprecated: per-backend isolated concurrency pools, created on first use."""

    def __init__(self, config: BulkheadConfig | None = None) -> None:
        """Build the bulkhead.

        Args:
            config: Per-backend pool sizing; defaults to a stock
                :class:`BulkheadConfig` (one default pool for every backend).

        Raises:
            TypeError: If ``config`` is not a :class:`BulkheadConfig`.
        """
        resolved = config if config is not None else BulkheadConfig()
        if not isinstance(resolved, BulkheadConfig):
            raise TypeError(
                f"Bulkhead: config must be a BulkheadConfig or None, got {type(resolved).__name__}"
            )
        warnings.warn(
            "Bulkhead is deprecated (ADR agents-speaks-core WS4b/PIR-866): declare "
            "ConcurrencyLimits(groups={backend: n, ...}) on the run and "
            "KnotConfig(concurrency_group=backend) on the knots that call it instead",
            DeprecationWarning,
            stacklevel=2,
        )
        self._config = resolved
        self._pools: dict[str, _BackpressureAdmission] = {}

    def _pool(self, backend: str) -> _BackpressureAdmission:
        pool = self._pools.get(backend)
        if pool is None:
            pool = _BackpressureAdmission(self._config.for_backend(backend), group=backend)
            self._pools[backend] = pool
        return pool

    def backends(self) -> tuple[str, ...]:
        """The backend keys that currently have a live pool."""
        return tuple(self._pools)

    def in_flight(self, backend: str) -> int:
        """Slots currently held for ``backend`` (0 if it has no pool yet)."""
        pool = self._pools.get(backend)
        return 0 if pool is None else pool.in_flight

    def waiting(self, backend: str) -> int:
        """Callers currently waiting for a slot in ``backend``'s pool."""
        pool = self._pools.get(backend)
        return 0 if pool is None else pool.waiting

    @asynccontextmanager
    async def slot(self, backend: str) -> AsyncIterator[None]:
        """Hold one slot in ``backend``'s isolated pool for the block's duration.

        Delegates to that backend's
        :class:`~pirn_agents.performance._backpressure_admission._BackpressureAdmission`,
        so its bound, queue-depth backpressure, and acquire timeout all apply
        -- independently of every other backend's pool.

        Raises:
            asyncio.QueueFull: If the backend's wait queue is bounded and full.
            TimeoutError: If the backend's acquire timeout elapses.
        """
        async with self._pool(backend).slot():
            yield

    # ------------------------------------------------- AdmissionGate surface

    def has_capacity(self) -> bool:
        """Always ``True``: pools are independent, so no *run-wide* budget is ever full."""
        return True

    def try_admit(self, knot: Knot) -> AdmissionTicket | None:
        """Admit *knot* into its backend's pool.

        The backend is ``knot.config.concurrency_group``: this is the one
        place ``Bulkhead`` reads it, so a caller wiring a real knot through
        this gate names the backend exactly as it would a concurrency group
        on a real run.

        Raises:
            ValueError: If *knot* has no ``concurrency_group``.
        """
        backend = knot.config.concurrency_group
        if backend is None:
            raise ValueError(
                f"Bulkhead: knot {knot.knot_id!r} has no concurrency_group; "
                "Bulkhead admits by backend"
            )
        return self._pool(backend).try_admit(knot)

    def release(self, ticket: AdmissionTicket) -> None:
        """Return *ticket* to the backend pool that issued it (``ticket.group``).

        Raises:
            AdmissionReleaseError: If ``ticket.group`` names no live pool.
        """
        backend = ticket.group
        if backend is None or backend not in self._pools:
            raise AdmissionReleaseError(f"Bulkhead: no backend pool holds {ticket!r}")
        self._pools[backend].release(ticket)

    def current_limit(self, group: str | None) -> int | None:
        """The cap for backend ``group``, from its live pool if one exists, else its config."""
        if group is None:
            return None
        pool = self._pools.get(group)
        if pool is not None:
            return pool.current_limit(group)
        return self._config.for_backend(group).max_concurrency

    def set_limit(self, group: str | None, limit: int) -> None:
        """Change the cap for backend ``group``, creating its pool if needed.

        Raises:
            AdmissionLimitError: If ``group`` is ``None`` -- ``Bulkhead`` has
                no run-wide cap to adjust.
        """
        if group is None:
            raise AdmissionLimitError("Bulkhead: no run-wide cap to adjust; pass a backend name")
        self._pool(group).set_limit(group, limit)
