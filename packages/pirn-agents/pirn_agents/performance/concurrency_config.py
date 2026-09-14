"""``ConcurrencyConfig`` — deprecated: one bounded pool's settings.

Deprecated (ADR agents-speaks-core, WS4b/PIR-866). Before this migration this
value backed a private ``asyncio.Semaphore`` (see the pre-migration
:class:`~pirn_agents.performance.backpressure_semaphore.BackpressureSemaphore`).
:meth:`to_concurrency_limits` gives the exact core
:class:`~pirn.core.concurrency.concurrency_limits.ConcurrencyLimits` a real
engine run would consume for the same posture -- the ``max_queue_depth``/
``acquire_timeout`` knobs core's ``AdmissionGate`` has no equivalent for
outside a running ``Tapestry`` stay here, layered on top by
:class:`~pirn_agents.performance._backpressure_admission._BackpressureAdmission`, the
seam this value feeds.

Kept a plain frozen dataclass rather than a ``ConcurrencyLimits`` subclass on
purpose: several callers (``agent/parallel_tool_executor.py`` and three
``specializations/`` pipelines) read ``ConcurrencyConfig.max_concurrency`` as
a **class-level** literal default (``max_concurrency: Knot | int =
ConcurrencyConfig.max_concurrency``) -- a pattern a pydantic ``BaseModel``
subclass cannot support (pydantic v2 does not expose field defaults as class
attributes; a ``@property`` returns the descriptor itself on class access,
not its computed value). Changing those call sites is out of this lane's
ownership for the three ``specializations/`` files; see
``packages/pirn-core/docs/FRAMEWORK_REFERENCE.md`` §6 for the disclosed
trade-off.

A pipeline wired through the engine should reach for
``KnotConfig(concurrency_group=...)`` on its knots and
``ConcurrencyLimits(groups={...})`` on the run directly, rather than this
value.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ConcurrencyConfig(PirnOpaqueValue):
    """Deprecated: bounded-concurrency + backpressure settings for one pool.

    Attributes:
        max_concurrency: Maximum simultaneously in-flight operations. Must be
            >= 1. Defaults to 8, matching the pre-migration default.
        max_queue_depth: Maximum number of callers allowed to *wait* for a
            slot at once. ``None`` (the default) means an unbounded wait
            queue. A concrete bound turns overflow into a typed
            ``asyncio.QueueFull``.
        acquire_timeout: Seconds a caller may wait for a slot before giving
            up, or ``None`` for no timeout.
    """

    max_concurrency: int = 8
    max_queue_depth: int | None = None
    acquire_timeout: float | None = None

    def __post_init__(self) -> None:
        """Validate the bound and optional backpressure knobs; warn deprecated."""
        if (
            isinstance(self.max_concurrency, bool)
            or not isinstance(self.max_concurrency, int)
            or self.max_concurrency < 1
        ):
            raise ValueError(
                f"ConcurrencyConfig: max_concurrency must be an int >= 1, "
                f"got {self.max_concurrency!r}"
            )
        depth = self.max_queue_depth
        if depth is not None and (
            isinstance(depth, bool) or not isinstance(depth, int) or depth < 0
        ):
            raise ValueError(
                f"ConcurrencyConfig: max_queue_depth must be a non-negative int or None, "
                f"got {depth!r}"
            )
        timeout = self.acquire_timeout
        if timeout is not None and (
            isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0
        ):
            raise ValueError(
                f"ConcurrencyConfig: acquire_timeout must be a positive number or None, "
                f"got {timeout!r}"
            )
        warnings.warn(
            "ConcurrencyConfig is deprecated (ADR agents-speaks-core WS4b/PIR-866): "
            "use ConcurrencyLimits directly, or KnotConfig(concurrency_group=...) on "
            "the knots that do the work",
            DeprecationWarning,
            stacklevel=2,
        )

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
        return {
            "max_concurrency": self.max_concurrency,
            "max_queue_depth": self.max_queue_depth,
            "acquire_timeout": self.acquire_timeout,
        }
