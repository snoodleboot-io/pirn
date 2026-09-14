"""``ConcurrencyConfig`` — deprecated: one bounded pool's settings, as a ``ConcurrencyLimits``.

Deprecated (ADR agents-speaks-core, WS4b/PIR-866). Before this migration a
``ConcurrencyConfig`` was a free-standing value backing a private
``asyncio.Semaphore`` (see the pre-migration
:class:`~pirn_agents.performance.backpressure_semaphore.BackpressureSemaphore`);
it is now literally a subclass of core's
:class:`~pirn.core.concurrency.concurrency_limits.ConcurrencyLimits`, so
``isinstance(config, ConcurrencyLimits)`` holds and
:meth:`to_concurrency_limits` gives the exact object a real engine run
consumes. ``max_concurrency`` is kept as the pre-migration keyword and
attribute name (a plain ``ConcurrencyLimits.max_in_flight`` under the hood);
``max_queue_depth``/``acquire_timeout`` are the two knobs core's
``AdmissionGate`` has no equivalent for outside a running ``Tapestry`` --
see :class:`~pirn_agents.performance._backpressure_gate._BackpressureGate`,
the seam this value feeds.

A pipeline wired through the engine should reach for
``KnotConfig(concurrency_group=...)`` on its knots and
``ConcurrencyLimits(groups={...})`` on the run directly, rather than this
value.
"""

from __future__ import annotations

import warnings
from typing import Any

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pydantic import PrivateAttr


class ConcurrencyConfig(ConcurrencyLimits):
    """Deprecated: bounded-concurrency + backpressure settings for one pool."""

    # Private attrs, not pydantic fields: neither has a core ``ConcurrencyLimits``
    # equivalent, so they ride alongside it as plain runtime state rather than
    # widening the model's own schema. ``PrivateAttr`` is the pydantic-v2
    # sanctioned way to hold such state on an otherwise-frozen model.
    _max_queue_depth: int | None = PrivateAttr(default=None)
    _acquire_timeout: float | None = PrivateAttr(default=None)

    def __init__(
        self,
        *,
        max_concurrency: int = 8,
        max_queue_depth: int | None = None,
        acquire_timeout: float | None = None,
    ) -> None:
        """Build the config.

        Args:
            max_concurrency: Maximum simultaneously in-flight operations
                (``ConcurrencyLimits.max_in_flight`` under the hood). Must
                be >= 1. Defaults to 8, matching the pre-migration default.
            max_queue_depth: Maximum number of callers allowed to *wait* for
                a slot at once. ``None`` (the default) means an unbounded
                wait queue. A concrete bound turns overflow into a typed
                ``asyncio.QueueFull``.
            acquire_timeout: Seconds a caller may wait for a slot before
                giving up, or ``None`` for no timeout.

        Raises:
            ValueError: If any argument is out of range.
        """
        if (
            isinstance(max_concurrency, bool)
            or not isinstance(max_concurrency, int)
            or max_concurrency < 1
        ):
            raise ValueError(
                f"ConcurrencyConfig: max_concurrency must be an int >= 1, got {max_concurrency!r}"
            )
        if max_queue_depth is not None and (
            isinstance(max_queue_depth, bool)
            or not isinstance(max_queue_depth, int)
            or max_queue_depth < 0
        ):
            raise ValueError(
                f"ConcurrencyConfig: max_queue_depth must be a non-negative int or None, "
                f"got {max_queue_depth!r}"
            )
        if acquire_timeout is not None and (
            isinstance(acquire_timeout, bool)
            or not isinstance(acquire_timeout, (int, float))
            or acquire_timeout <= 0
        ):
            raise ValueError(
                f"ConcurrencyConfig: acquire_timeout must be a positive number or None, "
                f"got {acquire_timeout!r}"
            )
        warnings.warn(
            "ConcurrencyConfig is deprecated (ADR agents-speaks-core WS4b/PIR-866): "
            "use ConcurrencyLimits directly, or KnotConfig(concurrency_group=...) on "
            "the knots that do the work",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(max_in_flight=max_concurrency)
        self._max_queue_depth = max_queue_depth
        self._acquire_timeout = acquire_timeout

    @property
    def max_concurrency(self) -> int:
        """The bound, under its pre-deprecation name (``max_in_flight`` under the hood)."""
        assert self.max_in_flight is not None
        return self.max_in_flight

    @property
    def max_queue_depth(self) -> int | None:
        """Maximum callers allowed to wait for a slot at once, or ``None`` for unbounded."""
        return self._max_queue_depth

    @property
    def acquire_timeout(self) -> float | None:
        """Seconds a caller may wait for a slot, or ``None`` for no timeout."""
        return self._acquire_timeout

    def to_concurrency_limits(self, *, group: str | None = None) -> ConcurrencyLimits:
        """The equivalent core :class:`ConcurrencyLimits` for a real engine run.

        Args:
            group: When given, the returned limits cap that one named group
                at :attr:`max_concurrency` instead of the run-wide budget --
                the shape :class:`~pirn_agents.resilience.bulkhead.Bulkhead`
                needs, one call per backend.
        """
        if group is None:
            return ConcurrencyLimits(max_in_flight=self.max_concurrency)
        return ConcurrencyLimits(groups={group: self.max_concurrency})

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Deprecated compat: the pre-migration audit projection."""
        return {
            "max_concurrency": self.max_concurrency,
            "max_queue_depth": self.max_queue_depth,
            "acquire_timeout": self.acquire_timeout,
        }
