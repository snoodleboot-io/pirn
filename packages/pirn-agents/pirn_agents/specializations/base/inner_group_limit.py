"""``InnerGroupLimit`` — a per-run carrier for a container's inner group cap.

A container that decides the concurrency cap of its inner run from a run-time
input has to hand that value from ``process()`` to ``_inner_concurrency()``,
which the framework calls afterwards with no arguments. Holding it on the
instance (``self._mutable_max_concurrency``) makes it *graph* state: the knot
object is shared by every run of the tapestry it belongs to, so two concurrent
runs overwrite each other's cap and at least one of them executes under a
budget it never asked for — the same class of defect ``Parameter.bound_copy``
exists to prevent for bound parameter values (PIR-802).

A :class:`~contextvars.ContextVar` is copied per asyncio task, so each run
reads back exactly what its own ``process()`` wrote and writes nothing the
other run can see.

Algorithm:
    1. ``process()`` calls :meth:`declare` with the number of knots it actually
       placed in the group and the cap they must share.
    2. ``declare`` stores ``ConcurrencyLimits(groups={group: cap})`` in the
       context var — or ``None`` when the group has no members, since naming an
       unused group only raises ``UnusedConcurrencyGroupWarning``.
    3. ``_inner_concurrency()`` returns :meth:`current`, which reads the value
       back out of this run's own context.

Internal API.
"""

from __future__ import annotations

from contextvars import ContextVar

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits


class InnerGroupLimit:
    """Carries one container's inner concurrency-group cap for the current run."""

    def __init__(self, group: str) -> None:
        """Declare the carrier for ``group``.

        Args:
            group: The ``KnotConfig.concurrency_group`` the cap applies to.
        """
        self._group = group
        self._current: ContextVar[ConcurrencyLimits | None] = ContextVar(
            f"pirn_agents.inner_group_limit.{group}", default=None
        )

    @property
    def group(self) -> str:
        """The concurrency group this carrier caps."""
        return self._group

    def declare(self, *, members: int, max_concurrency: int) -> None:
        """Record this run's cap for the group.

        Args:
            members: How many knots ``process()`` placed in the group.
            max_concurrency: The cap those knots share.
        """
        if members <= 0:
            self._current.set(None)
            return
        self._current.set(ConcurrencyLimits(groups={self._group: max_concurrency}))

    def current(self) -> ConcurrencyLimits | None:
        """This run's cap, or ``None`` when the group has no members."""
        return self._current.get()
