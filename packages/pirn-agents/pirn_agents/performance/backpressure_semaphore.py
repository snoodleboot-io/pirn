"""``BackpressureSemaphore`` — deprecated: a single ``_BackpressureAdmission``, by its old name.

Deprecated (ADR agents-speaks-core, WS4b/PIR-866). Before this migration this
class held a private ``asyncio.Semaphore`` the engine's own ``AdmissionGate``
could not see or steer. It is now a thin wrapper over one
:class:`~pirn_agents.performance._backpressure_admission._BackpressureAdmission` --
itself a real :class:`~pirn.engine.admission.admission_gate.AdmissionGate`,
built from the ``ConcurrencyConfig``'s equivalent
:class:`~pirn.core.concurrency.concurrency_limits.ConcurrencyLimits` -- so
this class enforces nothing of its own; every admission decision and the
in-flight bookkeeping live in the wrapped gate. ``acquire``/``release``/
``slot`` are kept for one deprecation cycle so an existing caller (e.g.
:func:`~pirn_agents.evaluation.run_eval.run_eval`) keeps working unchanged.

A pipeline wired through the engine should reach for
``KnotConfig(concurrency_group=...)`` on its knots and
``ConcurrencyLimits(groups={...})`` on the run directly, instead of building
one of these.
"""

from __future__ import annotations

import warnings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from pirn.engine.admission.admission_gate import AdmissionGate

from pirn_agents.performance._backpressure_admission import _BackpressureAdmission
from pirn_agents.performance.concurrency_config import ConcurrencyConfig

if TYPE_CHECKING:
    from pirn.core.knot import Knot
    from pirn.engine.admission.admission_ticket import AdmissionTicket


class BackpressureSemaphore(AdmissionGate):
    """Deprecated: a concurrency limiter that queues or sheds load per a shared config."""

    def __init__(self, config: ConcurrencyConfig) -> None:
        """Build the limiter from a :class:`ConcurrencyConfig`.

        Raises:
            TypeError: If ``config`` is not a :class:`ConcurrencyConfig`.
        """
        if not isinstance(config, ConcurrencyConfig):
            raise TypeError(
                f"BackpressureSemaphore: config must be a ConcurrencyConfig, "
                f"got {type(config).__name__}"
            )
        warnings.warn(
            "BackpressureSemaphore is deprecated (ADR agents-speaks-core WS4b/PIR-866): "
            "wire KnotConfig(concurrency_group=...) knots under a run's ConcurrencyLimits "
            "instead",
            DeprecationWarning,
            stacklevel=2,
        )
        self._pool = _BackpressureAdmission(config)

    @property
    def config(self) -> ConcurrencyConfig:
        """The config this limiter was built from."""
        return self._pool.config

    @property
    def in_flight(self) -> int:
        """Number of slots currently held."""
        return self._pool.in_flight

    @property
    def waiting(self) -> int:
        """Number of callers currently blocked waiting for a slot."""
        return self._pool.waiting

    async def acquire(self) -> None:
        """Acquire one slot, honouring the queue bound and acquire timeout.

        Raises:
            asyncio.QueueFull: If ``max_queue_depth`` is set and the wait
                queue is already full -- the backpressure signal to shed load.
            TimeoutError: If ``acquire_timeout`` elapses before a slot frees.
        """
        await self._pool.acquire()

    def release(self, ticket: AdmissionTicket | None = None) -> None:
        """Release one previously acquired slot.

        Args:
            ticket: The exact ticket to release (the real ``AdmissionGate``
                contract), or ``None`` (the pre-migration bare-semaphore
                contract) to release whichever slot this limiter currently
                holds.
        """
        self._pool.release(ticket)

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Acquire a slot for the duration of the ``async with`` block.

        The slot is always released, even if the body raises, so a failing
        operation never leaks concurrency capacity.
        """
        async with self._pool.slot():
            yield

    # ------------------------------------------------- AdmissionGate surface

    def has_capacity(self) -> bool:
        """Whether this limiter's budget has a free slot."""
        return self._pool.has_capacity()

    def try_admit(self, knot: Knot) -> AdmissionTicket | None:
        """Admit *knot* if this limiter's budget has room; see ``AdmissionGate``."""
        return self._pool.try_admit(knot)

    async def wait_for_release(self) -> None:
        """Suspend until this limiter may have freed a slot; see ``AdmissionGate``."""
        await self._pool.wait_for_release()

    def current_limit(self, group: str | None) -> int | None:
        """The live cap in force; see ``AdmissionGate``."""
        return self._pool.current_limit(group)

    def set_limit(self, group: str | None, limit: int) -> None:
        """Change the live cap; see ``AdmissionGate``."""
        self._pool.set_limit(group, limit)
